"""측정 keystone — 3-상태 None-default (광역 측정 재배선 2026-07-10, slice 0 이중가드).

guard_defect(결함 재현, 음성 오라클): 7 Measurement 클래스의 __init__ 기본값(15+개)이
전부 '비발화쪽 상수'(1.0/0.0)에 고정된 채 measure() 가 이를 "측정값"으로 보고했다 —
측정 없이 전-정상(all-clear)을 위장하는 죽은 상수(3층 deadness 중 ②상수 거짓말).
PR#61(occam else-1.0)/PR#63(grounding empty-0.0) 이 국소 봉합한 규칙의 base-class
통일이 없었다. 이 축은 keystone 을 revert 하면 다시 RED 가 된다.

guard_mechanism(메커니즘 실재, 양성 오라클): None=미측정은 measure() 키 부재로 흘러
decide_dispatch 가 스킵(미측정은 어떤 게이트도 통과 못 하고, 측정실패로도 위장 안 함)
하되, 실측정 값은 키로 등장해 기존 14+ 발화 규칙의 발화 능력을 전부 보존한다
(monotone: 새 발화 0 = dead-σ 회귀 불가, 기존 발화 보존).

HARD-CORE(설계 2026-07-09): "threshold 는 EXECUTED 측정값에만 발화; 부재(빈집합축약·
infra없음·경계I/O없음·stage없음)=None/omit, 어느 방향 상수도 금지; 정직배선은
live-crossable 수를 줄인다."

# KG: 7cmd-measurement-driven-conditional-dispatch-2026-05-30
# KG: bhgman-measurement-rewire-design-20260709 (keystone slice 0)
"""

from __future__ import annotations

import pytest

from engine.legion.measurement import (
    COMMANDER_REGISTRY,
    EurekaMeasurement,
    HadesMeasurement,
    JaebaemanMeasurement,
    LonginusMeasurement,
    NaesengmoonMeasurement,
    OccamMeasurement,
    PrometheusMeasurement,
)

# ── guard_defect: 기본 상태 = 미측정 = 키 0개 (상수 위장 금지) ────────────────


@pytest.mark.parametrize("name", sorted(COMMANDER_REGISTRY))
def test_default_state_exposes_no_metric_keys(name: str):
    """미측정 기본 상태의 measure() 는 빈 dict — 1.0(전-정상)도 0.0(측정된 영)도
    위장 노출하지 않는다. None=미측정 ≠ 0.0=측정된 영."""
    assert COMMANDER_REGISTRY[name]().measure() == {}


@pytest.mark.parametrize("name", sorted(COMMANDER_REGISTRY))
def test_default_state_never_fires(name: str):
    """미측정은 발화 불가 — decide_dispatch 는 없는 키를 스킵한다 (게이트 통과 불가)."""
    assert COMMANDER_REGISTRY[name]().decide_dispatch(cycle_id="keystone-none") == []


def test_partial_measurement_exposes_only_measured_keys():
    """부분 측정 = 측정된 키만 등장 — 미측정 형제 메트릭이 상수로 딸려 나오지 않는다."""
    assert OccamMeasurement(dead_node_count=3).measure() == {"dead_node_count": 3.0}
    assert EurekaMeasurement(novelty_score=0.9).measure() == {"novelty_score": 0.9}
    assert LonginusMeasurement(kg_node_unbound_count=2).measure() == {
        "kg_node_unbound_count": 2.0
    }


def test_naesengmoon_empty_distribution_omits_mean():
    """빈집합축약 금지: claim 분포가 비면 mean 은 미측정(키 부재) — 상수 1.0 금지."""
    assert "claim_confidence_mean" not in NaesengmoonMeasurement().measure()
    m = NaesengmoonMeasurement(claim_confidence_distribution=(0.6, 1.0))
    assert m.measure()["claim_confidence_mean"] == pytest.approx(0.8)


# ── guard_mechanism: 실측정은 기존 발화 능력을 전부 보존 (monotone) ───────────

_FIRING_CASES = [
    # (measurement, fired metric, fired target) — 14 threshold 규칙의 발화쪽 대표들.
    (lambda: PrometheusMeasurement(finding_count=20), "research_finding_count", "naesengmoon"),
    (lambda: EurekaMeasurement(binding_density=0.3), "binding_density", "longinus"),
    (lambda: EurekaMeasurement(novelty_score=0.2), "novelty_score", "prometheus"),
    (lambda: LonginusMeasurement(sha256_drift_count=10), "sha256_drift_count", "occam"),
    (
        lambda: LonginusMeasurement(reference_orphan_count=11),
        "reference_orphan_count",
        "prometheus",
    ),
    (
        lambda: OccamMeasurement(supersession_confidence=0.5),
        "supersession_confidence",
        "naesengmoon",
    ),
    (lambda: OccamMeasurement(dead_node_count=15), "dead_node_count", "occam"),
    (
        lambda: NaesengmoonMeasurement(lens_agreement_ratio=0.5),
        "lens_disagreement_ratio",
        "user_verdict_trigger",
    ),
    (lambda: NaesengmoonMeasurement(RTI_FVR_pass_rate=0.5), "RTI_FVR_pass_rate", "naesengmoon"),
    (
        lambda: JaebaemanMeasurement(subagent_collect_drift=0.5),
        "subagent_collect_drift",
        "naesengmoon",
    ),
    (lambda: JaebaemanMeasurement(seed_freshness_score=0.2), "seed_freshness_score", "prometheus"),
    (lambda: HadesMeasurement(spec_ambiguity_score=0.7), "spec_ambiguity_score", "eureka"),
    (
        lambda: HadesMeasurement(TDD_GREEN_failure_count=4),
        "TDD_GREEN_failure_count",
        "prometheus",
    ),
    (lambda: HadesMeasurement(binding_completeness=0.5), "binding_completeness", "longinus"),
]


@pytest.mark.parametrize(
    "build,metric,target", _FIRING_CASES, ids=[c[1] for c in _FIRING_CASES]
)
def test_measured_value_preserves_firing(build, metric, target):
    """실측정 값이 threshold 를 넘으면 발화한다 — keystone 은 기존 발화를 죽이지 않는다."""
    fired = [
        d for d in build().decide_dispatch(cycle_id="keystone-fire") if d.metric_name == metric
    ]
    assert fired, f"{metric} 실측정 발화가 keystone 이후에도 살아 있어야"
    assert fired[0].target_commander == target


def test_update_measures_from_unmeasured_state():
    """미측정 → update() 실측정 → 발화: 3-상태 전이의 양성 오라클."""
    m = EurekaMeasurement()
    assert m.decide_dispatch() == []
    m.update(novelty_score=0.2)
    assert any(d.metric_name == "novelty_score" for d in m.decide_dispatch())


def test_grounding_discrimination_survives_keystone():
    """판별력 counter(judge_grounding_liveness 축 3과 동형): 실측 비접지 → 발화,
    실측 완전접지 → 미발화 — keystone 이 판별력을 지우지 않았음."""
    dead = PrometheusMeasurement()
    dead.update_grounding(["", "not a url"])
    assert any(d.metric_name == "external_grounding_ratio" for d in dead.decide_dispatch())
    live = PrometheusMeasurement()
    live.update_grounding(["http://a.test/x"])
    assert not any(d.metric_name == "external_grounding_ratio" for d in live.decide_dispatch())
