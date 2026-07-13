"""창발 엔진 phase1 falsifier — 효능 주장 前 통과 필수.

F1 멱등 / F2 감쇠수렴 / F3 anti-Matthew + Activity FSM 단위.
(F4 ACL = phase2 Visibility FSM.)
"""
# KG: engineboy-emergence-engine-fsm-design-2026-07-13

from __future__ import annotations

import math

from engine.emergence import hawkes
from engine.emergence.engine import EmergenceEngine
from engine.emergence.protocols import (
    AccessEvent,
    ActivityState,
    Element,
    EmergenceConfig,
)
from engine.emergence.fsm import next_state
from engine.emergence.protocols import Action

S = ActivityState


def _stream(node="A", actor="human", n=10, start=0.0, step=1.0, tag="s"):
    return [
        AccessEvent(event_id=f"{tag}-{i}", element_key=node, actor=actor, ts=start + i * step)
        for i in range(n)
    ]


# ---------- F1: 멱등 (같은 이벤트 스트림 재생 → 동일 최종 상태) ----------
def test_f1_idempotent_replay():
    evs = _stream(n=20)
    eng = EmergenceEngine()
    for e in evs:
        eng.ingest(e)
    snap1 = {k: (v.w, v.n, v.state) for k, v in eng.snapshot().items()}

    # 같은 event_id 재생 → dedup → 불변
    deduped = 0
    for e in evs:
        tr = eng.ingest(e)
        deduped += int(tr.deduped)
    snap2 = {k: (v.w, v.n, v.state) for k, v in eng.snapshot().items()}

    assert deduped == len(evs)
    assert snap1 == snap2


def test_f1_determinism_two_engines():
    evs = _stream(n=30)
    a, b = EmergenceEngine(), EmergenceEngine()
    for e in evs:
        a.ingest(e)
        b.ingest(e)
    sa = {k: (round(v.w, 12), v.n, v.state) for k, v in a.snapshot().items()}
    sb = {k: (round(v.w, 12), v.n, v.state) for k, v in b.snapshot().items()}
    assert sa == sb


# ---------- F2: 감쇠 수렴 (정상율 → w* = κ/(1−e^{−λ/r})) ----------
def test_f2_decay_converges_to_equilibrium():
    lam, kappa, step = 0.1, 1.0, 1.0            # rate = 1/step = 1.0
    cfg = EmergenceConfig(lam=lam, kappa=kappa, l1_capacity=10_000)
    eng = EmergenceEngine(cfg=cfg)
    last_w = 0.0
    for i in range(300):
        tr = eng.ingest(
            AccessEvent(event_id=f"f2-{i}", element_key="X", actor="ai", ts=i * step)
        )
        last_w = tr.w
    w_star = hawkes.equilibrium_weight(kappa, rate=1.0 / step, lam=lam)
    assert abs(w_star - kappa / (1 - math.exp(-lam))) < 1e-9   # 해석해 자기검증
    assert abs(last_w - w_star) < 1e-6                          # 엔진이 평형 수렴


def test_f2_weight_tracks_access_rate():
    # 접근율 높을수록 평형 weight 높다 (weight ∝ rate)
    lam, kappa = 0.1, 1.0
    w_fast = hawkes.equilibrium_weight(kappa, rate=2.0, lam=lam)
    w_slow = hawkes.equilibrium_weight(kappa, rate=0.5, lam=lam)
    assert w_fast > w_slow


# ---------- F3: anti-Matthew ----------
def test_f3_mechanism_ucb_flips_near_tie_head_start():
    # anti-Matthew 의 진짜 성질: 가치 비슷한데 head-start 로 w 가 살짝 앞선
    # established 를, 미탐색 cold 가 UCB 로 역전. (높은 traffic 승리는 정상 — 대상 아님)
    c = 1.4
    total = 100
    w_cold, n_cold = 1.0, 1            # 갓 등장
    w_est, n_est = 1.8, 8              # head-start 로 w 약간 앞섬
    assert w_cold < w_est                                     # pure-w: established 우위
    u_cold = hawkes.ucb_score(w_cold, n_cold, total, c)
    u_est = hawkes.ucb_score(w_est, n_est, total, c)
    assert u_cold > u_est                                     # UCB: cold 역전 (탐색 보너스)


def test_f3_ucb_surfaces_more_cold_start_than_pure_weight():
    # 집계 수준: near-value 혼합 스트림에서 UCB top-K 가 순수-w 보다
    # cold-start 를 더 많이 포함 (Matthew 억제 탈출, 방향성만 주장).
    cfg = EmergenceConfig(lam=0.01, kappa=1.0, ucb_c=2.0, l1_capacity=10_000)
    eng = EmergenceEngine(cfg=cfg)
    t = 0.0
    # 20 established-mediocre: 각 2회 (w≈2, head-start)
    for p in range(20):
        for _ in range(2):
            eng.ingest(AccessEvent(f"est-{p}-{t}", f"EST{p}", "human", t))
            t += 1.0
    # 20 cold-start: 각 1회 (w≈1, 낮음)
    for cc in range(20):
        eng.ingest(AccessEvent(f"cold-{cc}", f"COLD{cc}", "human", t))
        t += 1.0

    t_eval = t
    total = eng._total_node_n
    ranked_w, ranked_ucb = [], []
    for key, e in eng.snapshot().items():
        w_dec = hawkes.decayed_weight(e.w, e.t_last, t_eval, cfg.lam)
        ranked_w.append((key, w_dec))
        ranked_ucb.append((key, hawkes.ucb_score(w_dec, e.n, total, cfg.ucb_c)))
    K = 20
    top_w = {k for k, _ in sorted(ranked_w, key=lambda x: x[1], reverse=True)[:K]}
    top_ucb = {k for k, _ in sorted(ranked_ucb, key=lambda x: x[1], reverse=True)[:K]}

    cold_in_w = sum(1 for k in top_w if k.startswith("COLD"))
    cold_in_ucb = sum(1 for k in top_ucb if k.startswith("COLD"))
    assert cold_in_ucb > cold_in_w   # UCB 가 순수-w 보다 cold-start 더 많이 surface


# ---------- Activity FSM 단위 ----------
def _elem(state, w, n, created=0.0, since=0.0):
    return Element(key="e", w=w, n=n, state=state, created_ts=created, state_since=since)


def test_fsm_nascent_to_warm():
    cfg = EmergenceConfig()
    st, act = next_state(_elem(S.NASCENT, w=1.5, n=3), t=1.0, score=1.5,
                         l1_has_capacity=True, cfg=cfg)
    assert st is S.WARM and act is Action.INSERT_L2


def test_fsm_nascent_cold_start_archive():
    cfg = EmergenceConfig()
    st, act = next_state(_elem(S.NASCENT, w=0.1, n=1, created=0.0), t=cfg.t_grace + 1,
                         score=0.1, l1_has_capacity=True, cfg=cfg)
    assert st is S.DORMANT and act is Action.ARCHIVE


def test_fsm_warm_to_hot_needs_capacity():
    cfg = EmergenceConfig()
    e = _elem(S.WARM, w=5.0, n=10)
    st_no, _ = next_state(e, t=1.0, score=9.0, l1_has_capacity=False, cfg=cfg)
    st_yes, act = next_state(e, t=1.0, score=9.0, l1_has_capacity=True, cfg=cfg)
    assert st_no is S.WARM                       # 용량 없으면 대기
    assert st_yes is S.HOT and act is Action.PROMOTE_L1


def test_fsm_hot_hysteresis_no_flap():
    cfg = EmergenceConfig()  # theta_hot=3.0, hysteresis=0.5
    # w=2.6 은 theta_hot 밑이지만 hysteresis 대역(>2.5) → HOT 유지
    st, _ = next_state(_elem(S.HOT, w=2.6, n=10), t=1.0, score=2.6,
                       l1_has_capacity=True, cfg=cfg)
    assert st is S.HOT
    # w=2.4 < theta_hot - h → COOLING
    st2, act2 = next_state(_elem(S.HOT, w=2.4, n=10), t=1.0, score=2.4,
                           l1_has_capacity=True, cfg=cfg)
    assert st2 is S.COOLING and act2 is Action.MARK_COOLING


def test_fsm_no_hard_delete_dormant_revivable():
    cfg = EmergenceConfig()
    # DORMANT + 재접근(w bump) → 되살아남 (삭제 terminal 없음)
    st, act = next_state(_elem(S.DORMANT, w=1.2, n=5), t=1.0, score=1.2,
                         l1_has_capacity=True, cfg=cfg)
    assert st is S.WARM and act is Action.REEMERGE
