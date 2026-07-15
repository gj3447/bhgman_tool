"""Threshold 단일 정본 (T1-3) — thresholds.toml ↔ measurement.py 이중 장부 봉합.

실측 drift (2026-07-15, 수정 전): 코드 15 규칙 중 TOML 이 올바로 담은 것은 6개뿐.
  * 이름/타깃 갈림 3쌍: sha256_drift_rate(0.05)↔sha256_drift_count(5) /
    rti_fvr↔RTI_FVR_pass_rate / hades→naesengmoon spec_ambiguity↔hades→eureka
    spec_ambiguity_score
  * TOML 누락 6: reference_orphan_count, dead_node_count, lens_disagreement_ratio,
    seed_freshness_score, TDD_GREEN_failure_count, binding_completeness
  * 값 불일치 1: subagent_collect_drift 코드 0.2 vs TOML 0.1

이건 튜닝 문제가 아니라 **발화 가능성** 문제다: decide_dispatch 는 metrics.get(rule.metric)
로 조회하므로, TOML 이름이 measure() 가 내는 키와 어긋난 채 런타임 정본이 되면 그 규칙은
영원히 미발화한다 (조용한 dead control).

정본 규약: metric 이름/타깃/구조 = 코드 (measure() 키 + STEVENS_SCALE 이 코드 이름을
쓴다) / threshold **값**과 comparator = TOML (P2-b '코드 수정 없이 튜닝'). 코드 상수는
삭제하지 않고 TOML 미수록 시 fallback 으로 강등한다 (supersession).

# KG: actionplan-threshold-derivation-2026-05-30, 7cmd-measurement-driven-conditional-dispatch-2026-05-30
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from engine.legion.measurement import (
    STEVENS_SCALE,
    EurekaMeasurement,
    HadesMeasurement,
    JaebaemanMeasurement,
    LonginusMeasurement,
    NaesengmoonMeasurement,
    OccamMeasurement,
    PrometheusMeasurement,
    resolve_thresholds,
)
from engine.legion.threshold_derivation.config import load_thresholds

_CLASSES = (
    PrometheusMeasurement,
    EurekaMeasurement,
    LonginusMeasurement,
    OccamMeasurement,
    NaesengmoonMeasurement,
    JaebaemanMeasurement,
    HadesMeasurement,
)

# TOML 에만 있는 비-dispatch 항목: Contract root 공리(결합도 0 → 대수 항등원)의 정전 수치
# 기록으로, CommanderMeasurement 규칙이 아니다. 파리티 대상에서 명시 제외 (은닉 아님).
# KG: apt-contract-root-axiom-2026-05-27
_NON_DISPATCH_TOML_KEYS = {("contract", "_identity_", "coupling_degree")}


def _code_rules() -> dict[tuple[str, str, str], tuple[float, str]]:
    out = {}
    for cls in _CLASSES:
        for r in cls.dispatch_thresholds:
            out[(r.source, r.target, r.metric)] = (float(r.threshold), r.direction)
    return out


def _toml_rules() -> dict[tuple[str, str, str], tuple[float, str]]:
    return {
        (e.commander, e.target_commander, e.metric): (float(e.value), e.comparator)
        for e in load_thresholds().values()
        if (e.commander, e.target_commander, e.metric) not in _NON_DISPATCH_TOML_KEYS
    }


def test_toml_and_code_cover_identical_rule_keys():
    """두 장부의 (source, target, metric) 키 집합이 정확히 일치해야 한다."""
    code, toml = _code_rules(), _toml_rules()
    assert set(code) == set(toml), (
        f"only-code={sorted(set(code) - set(toml))}\nonly-toml={sorted(set(toml) - set(code))}"
    )


def test_toml_and_code_agree_on_values():
    """키가 같으면 값·comparator 도 같아야 한다 (한쪽 단독 수정 = RED)."""
    code, toml = _code_rules(), _toml_rules()
    mismatch = {k: (code[k], toml[k]) for k in set(code) & set(toml) if code[k] != toml[k]}
    assert not mismatch, f"value drift (code, toml): {mismatch}"


def test_every_rule_metric_is_in_stevens_scale():
    """규칙 metric 은 Stevens scale 지도에 등재돼 있어야 한다 — 이름 drift 의 3번째 장부."""
    missing = [k for k in _code_rules() if (k[0], k[2]) not in STEVENS_SCALE]
    assert not missing, f"STEVENS_SCALE 미등재: {missing}"


def test_toml_values_win_at_runtime():
    """TOML 이 런타임 정본 — resolve_thresholds 가 코드 상수를 TOML 값으로 덮는다."""
    rules = resolve_thresholds(OccamMeasurement.dispatch_thresholds, "occam")
    by_metric = {r.metric: r for r in rules}
    entry = load_thresholds()[("occam", "supersession_confidence")]
    assert by_metric["supersession_confidence"].threshold == pytest.approx(entry.value)


def test_derivation_provenance_flows_into_rationale():
    """TOML 의 derivation_method 가 rationale 을 타고 :DispatchEvent.reason 까지 흐른다."""
    rules = resolve_thresholds(OccamMeasurement.dispatch_thresholds, "occam")
    r = next(x for x in rules if x.metric == "supersession_confidence")
    assert "bayesian_map_beta_bernoulli_berger_1985" in r.rationale


def test_missing_toml_entry_falls_back_to_code_constant():
    """TOML 미수록 규칙은 코드 상수로 fallback (삭제 아닌 강등) — 로더 실패 시에도 동일."""
    synthetic = (
        replace(
            OccamMeasurement.dispatch_thresholds[0],
            source="ghost",
            target="nowhere",
            metric="not_in_toml_metric",
            threshold=0.42,
        ),
    )
    rules = resolve_thresholds(synthetic, "ghost")
    assert rules[0].threshold == pytest.approx(0.42)


def test_resolve_is_fail_soft_when_loader_raises(monkeypatch):
    """TOML 파싱 실패가 dispatch 를 죽이면 안 된다 — 코드 상수로 조용히 fallback."""
    import engine.legion.measurement as m

    def boom():
        raise OSError("toml unreadable")

    monkeypatch.setattr(m, "load_thresholds", boom)
    rules = resolve_thresholds(OccamMeasurement.dispatch_thresholds, "occam")
    assert rules == OccamMeasurement.dispatch_thresholds
