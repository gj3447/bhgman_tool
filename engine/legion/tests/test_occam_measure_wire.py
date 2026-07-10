"""occam measurement-driven dispatch 런타임 배선 (Tier-2 write-safety follow-up — RED-first).

`OccamMeasurement`(supersession_confidence<0.7 → naesengmoon verify, dead_node_count>10 →
occam self-supersede)와 그 decide_dispatch 는 이미 존재/검증되지만(test_measurement.py),
**legion 경로에서 죽어 있었다**: occam 스테이지가 `_stage_from_engine(OccamEngine())` 로
measure= 팩토리 없이 등록돼(_measure_and_dispatch 의 `stage.measure is None` early-return)
OccamMeasurement 가 런타임에 한 번도 인스턴스화되지 않았고, 설령 됐어도 supersession_confidence
는 생성자 기본 1.0 에 고정 → <0.7 dispatch 가 원리적으로 발화 불가(1.0<0.7=False).

prometheus grounding-wire(test_grounding_wire.py)와 동형으로 이 배선을 고정한다:
  1. occam 스테이지가 measure= 팩토리를 실제로 지닌다 (default_stages).
  2. _measure_occam 이 hygiene summary 의 실 candidate σ / stale 카운트로 값을 실계산한다
     (degraded/부재 → None, 정직 기본).
  3. (NOVEL) 낮은 σ 후보 → <0.7 naesengmoon verify dispatch 가 *실제로 발화* — runtime-dead
     시절엔 구조적으로 불가능했던 사건. 판별 반대쪽(전부 확신)은 미발화.

v2 정정 2종 (광역 측정 재배선 2026-07-10, 적대검증 정정 2 — RED-first 이중가드):
  a. dead_node_count 과대계수 봉합: 옛 소스 superseded_candidates(=len(candidates),
     KEEP/VERIFY/deferred 전량 포함)는 '정리 백로그'가 아니라 '스캔에 걸린 후보 수'였다 —
     전량-불확실 배치도 >10 self-supersede 를 오발화시켰다. 정직 소스 =
     len(hygiene["superseded"]) (확신-supersede 셋: apply 모드=실제 적용, dry-run=계획).
  b. σ-None 상향 편향 봉합: min(σ) 가 sigma=None(σ 미계산=최고 불확실) 후보를 버려
     배치 confidence 가 위로 편향됐다 — escalation 규율("σ 없는 확신은 없다")과 동형으로
     None 은 최고 불확실(0.0)로 계수한다. 후보 0건 = min 정의역 공집합 = 미측정(키 부재).

# KG: LakatosTree_Bhgman6CommanderOoptdd_20260624 (measurement-driven conditional dispatch),
#     7cmd-measurement-driven-conditional-dispatch-2026-05-30
# KG: bhgman-measurement-rewire-design-20260709 (정정 2: occam 과대계수·σ-None 편향)
"""

from __future__ import annotations

from engine.legion.commanders import _measure_occam, default_stages
from engine.legion.legion import Legion
from engine.legion.legion_models import CommanderStage


def _occam_stage() -> CommanderStage:
    return next(s for s in default_stages() if s.name == "occam")


def _hygiene(candidates=(), superseded=0) -> dict:
    """summarize_occam_result 모양의 최소 hygiene dict — superseded 는 확신-supersede
    식별자 *목록*(실제 summarize 와 동형; 여기선 개수로 합성), superseded_candidates 는
    옛 과대계수 축(=len(candidates), KEEP/VERIFY 포함)을 그대로 재현한다."""
    return {
        "mode": "occam",
        "candidates": [
            {"stale": f"n{i}", "current": "cur", "sigma": s, "verdict": "SUPERSEDE"}
            for i, s in enumerate(candidates)
        ],
        "superseded_candidates": len(candidates),
        "superseded": [f"sup_{i}" for i in range(superseded)],
    }


# ── 배선 1: 스테이지가 measure 팩토리를 지닌다 ────────────────────────────────
def test_occam_stage_carries_measure_factory():
    assert _occam_stage().measure is not None, "occam 스테이지에 measure= 팩토리가 배선돼야"


# ── 배선 2: 실 σ / 카운트에서 값 실계산 ──────────────────────────────────────
def test_measure_occam_confidence_is_min_candidate_sigma():
    """배치는 가장 낮은 후보 σ 만큼만 확신 — supersession_confidence = min σ."""
    m = _measure_occam({"hygiene": _hygiene(candidates=(0.9, 0.5, 0.8))})
    assert m is not None
    assert m.measure()["supersession_confidence"] == 0.5


def test_measure_occam_dead_count_from_confident_supersede_set():
    """정정 2a: dead_node_count 의 정직 소스는 확신-supersede 목록 len(superseded) —
    후보 수(superseded_candidates)가 아니다."""
    m = _measure_occam({"hygiene": _hygiene(candidates=(0.9,), superseded=12)})
    assert m.measure()["dead_node_count"] == 12.0


def test_deferred_only_batch_does_not_overcount_dead():
    """guard_defect(정정 2a, 음성 오라클): 전량 KEEP/VERIFY/deferred(확신-supersede 0)
    배치 12건 → dead_node_count 는 0(측정된 영)이어야 하고 >10 self-supersede 는 침묵.
    옛 소스(superseded_candidates=12)는 여기서 오발화했다."""
    m = _measure_occam({"hygiene": _hygiene(candidates=(0.9,) * 12, superseded=0)})
    assert m.measure()["dead_node_count"] == 0.0
    fired = [
        d for d in m.decide_dispatch(cycle_id="omw-overcount") if d.metric_name == "dead_node_count"
    ]
    assert not fired, "불확실 백로그가 self-supersede 배치를 오발화시키면 안 된다"


def test_measure_occam_no_candidates_is_unmeasured_confidence():
    """후보 0건 = min(σ) 정의역 공집합 = supersession_confidence 미측정(키 부재) —
    keystone HARD-CORE(빈집합축약 금지): '검증 불필요'조차 1.0 상수로 위장하지 않는다.
    dead_node_count 는 실행된 스캔의 카운트라 측정된 영(0.0)으로 남는다(None≠0.0)."""
    m = _measure_occam({"hygiene": _hygiene(candidates=(), superseded=0)})
    metrics = m.measure()
    assert "supersession_confidence" not in metrics
    assert metrics["dead_node_count"] == 0.0
    assert m.decide_dispatch(cycle_id="omw-empty") == []


def test_measure_occam_none_sigma_counts_as_most_uncertain():
    """guard_defect(정정 2b, 음성 오라클): sigma=None(σ 미계산) 후보는 최고 불확실로
    계수한다 — 옛 min(σ) 은 None 을 버려 confidence 가 0.6 으로 위로 편향됐고,
    'σ 없는 확신은 없다'(escalation 규율)와 모순됐다."""
    hyg = _hygiene(candidates=(0.6,))
    hyg["candidates"].append({"stale": "x", "current": "c", "sigma": None, "verdict": None})
    m = _measure_occam({"hygiene": hyg})
    assert m.measure()["supersession_confidence"] == 0.0  # None = 최고 불확실
    fired = [
        d
        for d in m.decide_dispatch(cycle_id="omw-nonesigma")
        if d.metric_name == "supersession_confidence"
    ]
    assert fired and fired[0].target_commander == "naesengmoon"


def test_measure_occam_degraded_returns_none():
    """degraded stub(=candidates 키 없음) → None: dispatch 없음, crash 없음."""
    assert _measure_occam({"hygiene": {"mode": "degraded", "reason": "occam failed"}}) is None
    assert _measure_occam({}) is None  # hygiene 부재


# ── 배선 3 (NOVEL): 낮은 σ → naesengmoon verify dispatch 가 실제로 발화 ────────
def test_low_sigma_fires_naesengmoon_verify():
    m = _measure_occam({"hygiene": _hygiene(candidates=(0.5,))})
    fired = [
        d
        for d in m.decide_dispatch(cycle_id="omw-fire")
        if d.metric_name == "supersession_confidence"
    ]
    assert fired, "낮은 σ 는 <0.7 naesengmoon verify dispatch 를 발화해야"
    assert fired[0].target_commander == "naesengmoon"


def test_all_confident_no_dispatch():
    """판별 반대쪽: 전부 σ≥0.7 → supersession_confidence dispatch 미발화."""
    m = _measure_occam({"hygiene": _hygiene(candidates=(0.8, 0.95), superseded=1)})
    fired = [
        d
        for d in m.decide_dispatch(cycle_id="omw-nofire")
        if d.metric_name == "supersession_confidence"
    ]
    assert not fired


def test_many_stale_fires_self_supersede():
    m = _measure_occam({"hygiene": _hygiene(candidates=(0.9,), superseded=15)})
    targets = {
        d.target_commander
        for d in m.decide_dispatch(cycle_id="omw-batch")
        if d.metric_name == "dead_node_count"
    }
    assert "occam" in targets, ">10 stale 는 occam self-supersede batch 를 발화해야"


# ── 배선 3-통합: legion.run 루프가 occam 팩토리를 실제로 집어 dispatch 를 수집 ──
def test_legion_run_collects_occam_dispatch_decision():
    """end-to-end: _measure_and_dispatch 가 occam 스테이지의 measure= 를 집어 낮은 σ 에서
    naesengmoon decision 을 LegionRun.dispatch_decisions 로 수집한다(런타임 배선 증명)."""
    stage = CommanderStage(
        "occam",
        "정리",
        ("run_cypher",),
        ("hygiene",),
        lambda ctx: {"hygiene": _hygiene(candidates=(0.4,))},
        measure=_measure_occam,
    )
    run = Legion().register(stage).run({"run_cypher": lambda c, p: [], "cycle_id": "omw-e2e"})
    assert run.completed
    fired = [
        d
        for d in run.dispatch_decisions
        if d.metric_name == "supersession_confidence" and d.target_commander == "naesengmoon"
    ]
    assert fired, f"legion.run 이 occam dispatch 를 수집해야; got {run.dispatch_decisions}"
