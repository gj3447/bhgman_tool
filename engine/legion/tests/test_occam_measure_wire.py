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

# KG: LakatosTree_Bhgman6CommanderOoptdd_20260624 (measurement-driven conditional dispatch),
#     7cmd-measurement-driven-conditional-dispatch-2026-05-30
"""

from __future__ import annotations

from engine.legion.commanders import _measure_occam, default_stages
from engine.legion.legion import Legion
from engine.legion.legion_models import CommanderStage


def _occam_stage() -> CommanderStage:
    return next(s for s in default_stages() if s.name == "occam")


def _hygiene(candidates=(), superseded=0) -> dict:
    """summarize_occam_result 모양의 최소 hygiene dict."""
    return {
        "mode": "occam",
        "candidates": [{"stale": f"n{i}", "current": "cur", "sigma": s, "verdict": "SUPERSEDE"}
                       for i, s in enumerate(candidates)],
        "superseded_candidates": superseded,
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


def test_measure_occam_dead_count_from_superseded():
    m = _measure_occam({"hygiene": _hygiene(candidates=(0.9,), superseded=12)})
    assert m.measure()["dead_node_count"] == 12.0


def test_measure_occam_no_candidates_keeps_honest_default():
    """후보 없음/무점수 → 1.0 (검증 불필요, 항상-발화 장식 아님)."""
    m = _measure_occam({"hygiene": _hygiene(candidates=(), superseded=0)})
    assert m.measure()["supersession_confidence"] == 1.0


def test_measure_occam_ignores_none_sigma():
    hyg = _hygiene(candidates=(0.6,))
    hyg["candidates"].append({"stale": "x", "current": "c", "sigma": None, "verdict": None})
    m = _measure_occam({"hygiene": hyg})
    assert m.measure()["supersession_confidence"] == 0.6  # None 무시, 0.6 유지


def test_measure_occam_degraded_returns_none():
    """degraded stub(=candidates 키 없음) → None: dispatch 없음, crash 없음."""
    assert _measure_occam({"hygiene": {"mode": "degraded", "reason": "occam failed"}}) is None
    assert _measure_occam({}) is None  # hygiene 부재


# ── 배선 3 (NOVEL): 낮은 σ → naesengmoon verify dispatch 가 실제로 발화 ────────
def test_low_sigma_fires_naesengmoon_verify():
    m = _measure_occam({"hygiene": _hygiene(candidates=(0.5,))})
    fired = [d for d in m.decide_dispatch(cycle_id="omw-fire")
             if d.metric_name == "supersession_confidence"]
    assert fired, "낮은 σ 는 <0.7 naesengmoon verify dispatch 를 발화해야"
    assert fired[0].target_commander == "naesengmoon"


def test_all_confident_no_dispatch():
    """판별 반대쪽: 전부 σ≥0.7 → supersession_confidence dispatch 미발화."""
    m = _measure_occam({"hygiene": _hygiene(candidates=(0.8, 0.95), superseded=1)})
    fired = [d for d in m.decide_dispatch(cycle_id="omw-nofire")
             if d.metric_name == "supersession_confidence"]
    assert not fired


def test_many_stale_fires_self_supersede():
    m = _measure_occam({"hygiene": _hygiene(candidates=(0.9,), superseded=15)})
    targets = {d.target_commander for d in m.decide_dispatch(cycle_id="omw-batch")
               if d.metric_name == "dead_node_count"}
    assert "occam" in targets, ">10 stale 는 occam self-supersede batch 를 발화해야"


# ── 배선 3-통합: legion.run 루프가 occam 팩토리를 실제로 집어 dispatch 를 수집 ──
def test_legion_run_collects_occam_dispatch_decision():
    """end-to-end: _measure_and_dispatch 가 occam 스테이지의 measure= 를 집어 낮은 σ 에서
    naesengmoon decision 을 LegionRun.dispatch_decisions 로 수집한다(런타임 배선 증명)."""
    stage = CommanderStage(
        "occam", "정리", ("run_cypher",), ("hygiene",),
        lambda ctx: {"hygiene": _hygiene(candidates=(0.4,))},
        measure=_measure_occam,
    )
    run = Legion().register(stage).run({"run_cypher": lambda c, p: [], "cycle_id": "omw-e2e"})
    assert run.completed
    fired = [d for d in run.dispatch_decisions
             if d.metric_name == "supersession_confidence" and d.target_commander == "naesengmoon"]
    assert fired, f"legion.run 이 occam dispatch 를 수집해야; got {run.dispatch_decisions}"
