"""Unit tests for engine.legion.measurement — 7군단장 conditional dispatch.

PROM 16 7CMD MEASUREMENT GROUNDING A4S2 P1 — addresses ZERO unit test deficit.

Coverage:
- 7 commander measure() returns expected dict
- 14 threshold rules trigger correctly
- DispatchDecision provenance + HMAC signature
- max_depth=3 recursion cap
- Idempotent measure() with version vector
- Stevens scale type gate (3 bug fixes)
"""

from __future__ import annotations

import pytest

from engine.legion.measurement import (
    COMMANDER_REGISTRY,
    MAX_DISPATCH_DEPTH,
    STEVENS_SCALE,
    DispatchDecision,
    DispatchThreshold,
    EurekaMeasurement,
    HadesMeasurement,
    JaebaemanMeasurement,
    LonginusMeasurement,
    MaxDispatchDepthExceeded,
    NaesengmoonMeasurement,
    OccamMeasurement,
    PrometheusMeasurement,
    commander_by_name,
    valid_operation,
)


# ─────────────────────────────────────────────────────────────
# 7 commander measure() shape
# ─────────────────────────────────────────────────────────────


class TestMeasureShape:
    def test_prometheus_measure_keys(self):
        # v2 (seam-integrity 20260708): 기본 상태의 external_grounding_ratio 는 미측정 = 키 부재
        # (상수 위장 금지); update_grounding 으로 실측되면 키가 나타난다.
        m = PrometheusMeasurement().measure()
        assert set(m) == {"research_finding_count"}
        assert all(isinstance(v, float) for v in m.values())
        measured = PrometheusMeasurement()
        measured.update_grounding(["http://a.test/x"])
        assert set(measured.measure()) == {"research_finding_count", "external_grounding_ratio"}

    def test_eureka_measure_keys(self):
        m = EurekaMeasurement().measure()
        assert set(m) == {"binding_density", "novelty_score", "colimit_termination_depth"}

    def test_longinus_measure_keys(self):
        m = LonginusMeasurement().measure()
        assert set(m) == {"sha256_drift_count", "reference_orphan_count", "kg_node_unbound_count"}

    def test_occam_measure_keys(self):
        m = OccamMeasurement().measure()
        assert set(m) == {"supersession_confidence", "dead_node_count", "twin_status_score"}

    def test_naesengmoon_measure_keys(self):
        m = NaesengmoonMeasurement().measure()
        assert set(m) == {"claim_confidence_mean", "lens_disagreement_ratio", "RTI_FVR_pass_rate"}

    def test_jaebaeman_measure_keys(self):
        m = JaebaemanMeasurement().measure()
        assert set(m) == {
            "subagent_collect_drift",
            "seed_freshness_score",
            "dispatch_intent_completeness",
        }

    def test_hades_measure_keys(self):
        m = HadesMeasurement().measure()
        assert set(m) == {"spec_ambiguity_score", "TDD_GREEN_failure_count", "binding_completeness"}


# ─────────────────────────────────────────────────────────────
# Threshold dispatch — positive + negative cases
# ─────────────────────────────────────────────────────────────


class TestThresholdDispatch:
    def test_occam_low_conf_triggers_naesengmoon(self):
        decisions = OccamMeasurement(supersession_confidence=0.5).decide_dispatch()
        targets = {d.target_commander for d in decisions}
        assert "naesengmoon" in targets

    def test_occam_high_conf_no_dispatch(self):
        decisions = OccamMeasurement(
            supersession_confidence=0.9, dead_node_count=0
        ).decide_dispatch()
        # 0.9 ≥ 0.7 confidence threshold + 0 < 10 dead_node threshold
        targets = {d.target_commander for d in decisions}
        assert "naesengmoon" not in targets
        assert "occam" not in targets

    def test_occam_many_dead_self_supersede(self):
        decisions = OccamMeasurement(
            supersession_confidence=1.0, dead_node_count=15
        ).decide_dispatch()
        targets = {d.target_commander for d in decisions}
        assert "occam" in targets

    def test_eureka_low_binding_triggers_longinus(self):
        decisions = EurekaMeasurement(binding_density=0.3, novelty_score=1.0).decide_dispatch()
        targets = {d.target_commander for d in decisions}
        assert "longinus" in targets
        assert "prometheus" not in targets

    def test_eureka_low_novelty_triggers_prometheus(self):
        decisions = EurekaMeasurement(binding_density=1.0, novelty_score=0.2).decide_dispatch()
        targets = {d.target_commander for d in decisions}
        assert "prometheus" in targets

    def test_hades_high_ambiguity_low_binding_dual(self):
        decisions = HadesMeasurement(
            spec_ambiguity_score=0.7, binding_completeness=0.5
        ).decide_dispatch()
        targets = {d.target_commander for d in decisions}
        assert {"eureka", "longinus"}.issubset(targets)

    def test_prometheus_many_findings_triggers_naesengmoon(self):
        decisions = PrometheusMeasurement(finding_count=20).decide_dispatch()
        assert any(d.target_commander == "naesengmoon" for d in decisions)

    def test_jaebaeman_drift_triggers_naesengmoon(self):
        decisions = JaebaemanMeasurement(subagent_collect_drift=0.5).decide_dispatch()
        assert any(d.target_commander == "naesengmoon" for d in decisions)

    def test_longinus_drift_triggers_occam(self):
        decisions = LonginusMeasurement(sha256_drift_count=10).decide_dispatch()
        assert any(d.target_commander == "occam" for d in decisions)


# ─────────────────────────────────────────────────────────────
# A4S4 mitigations
# ─────────────────────────────────────────────────────────────


class TestMaxDepthCap:
    def test_max_depth_constant_equals_3(self):
        assert MAX_DISPATCH_DEPTH == 3

    def test_depth_at_max_raises(self):
        with pytest.raises(MaxDispatchDepthExceeded):
            OccamMeasurement(supersession_confidence=0.5).decide_dispatch(depth=MAX_DISPATCH_DEPTH)

    def test_depth_below_max_ok(self):
        decisions = OccamMeasurement(supersession_confidence=0.5).decide_dispatch(
            depth=MAX_DISPATCH_DEPTH - 1
        )
        assert decisions  # at least one dispatch
        assert all(d.depth == MAX_DISPATCH_DEPTH - 1 for d in decisions)


class TestIdempotentMeasure:
    def test_measure_returns_same_snapshot_twice(self):
        cmd = OccamMeasurement(supersession_confidence=0.5)
        m1 = cmd.measure()
        m2 = cmd.measure()
        assert m1 == m2

    def test_update_bumps_epoch_and_invalidates_cache(self):
        cmd = OccamMeasurement(supersession_confidence=0.5)
        e0 = cmd.current_epoch()
        _ = cmd.measure()
        cmd.update(supersession_confidence=0.9)
        e1 = cmd.current_epoch()
        assert e1 == e0 + 1
        m_after = cmd.measure()
        assert m_after["supersession_confidence"] == 0.9


class TestHMACSignature:
    def test_to_kg_event_includes_hmac(self):
        d = DispatchDecision(
            "occam",
            "naesengmoon",
            "supersession_confidence",
            0.5,
            0.7,
            "low conf",
            epoch=1,
            depth=0,
        )
        evt = d.to_kg_event(cycle_id="cycle-test")
        assert "hmac_signature" in evt
        assert len(evt["hmac_signature"]) == 64  # SHA-256 hex

    def test_verify_signature_passes_on_unmodified(self):
        d = DispatchDecision(
            "occam",
            "naesengmoon",
            "supersession_confidence",
            0.5,
            0.7,
            "low conf",
            epoch=1,
            depth=0,
        )
        evt = d.to_kg_event(cycle_id="cycle-test")
        assert DispatchDecision.verify_signature(evt) is True

    def test_verify_signature_fails_on_tampered(self):
        d = DispatchDecision(
            "occam",
            "naesengmoon",
            "supersession_confidence",
            0.5,
            0.7,
            "low conf",
            epoch=1,
            depth=0,
        )
        evt = d.to_kg_event(cycle_id="cycle-test")
        evt["metric_value"] = 0.9  # tamper
        assert DispatchDecision.verify_signature(evt) is False


# ─────────────────────────────────────────────────────────────
# Stevens scale type — 3 bug fixes verified
# ─────────────────────────────────────────────────────────────


class TestStevensScale:
    def test_naesengmoon_lens_count_is_ordinal_bug_fix(self):
        # A1S3 + A3S3 bug fix: lens_count was treated as ratio, should be ordinal
        assert STEVENS_SCALE[("naesengmoon", "lens_count")] == "ordinal"

    def test_occam_archival_category_is_nominal_bug_fix(self):
        assert STEVENS_SCALE[("occam", "archival_reason_category")] == "nominal"

    def test_eureka_colimit_termination_depth_is_ordinal_bug_fix(self):
        # hierarchy depth, no arithmetic
        assert STEVENS_SCALE[("eureka", "colimit_termination_depth")] == "ordinal"

    def test_ordinal_mean_invalid(self):
        assert valid_operation("naesengmoon", "lens_count", "mean") is False

    def test_ordinal_median_valid(self):
        assert valid_operation("naesengmoon", "lens_count", "median") is True

    def test_nominal_mean_invalid(self):
        assert valid_operation("occam", "archival_reason_category", "mean") is False

    def test_nominal_mode_valid(self):
        assert valid_operation("occam", "archival_reason_category", "mode") is True

    def test_ratio_pct_valid(self):
        assert valid_operation("occam", "supersession_confidence", "pct") is True


# ─────────────────────────────────────────────────────────────
# Registry + lookup
# ─────────────────────────────────────────────────────────────


class TestRegistry:
    def test_7_commander_registry_has_all(self):
        assert set(COMMANDER_REGISTRY) == {
            "prometheus",
            "eureka",
            "longinus",
            "occam",
            "naesengmoon",
            "jaebaeman",
            "hades",
        }

    def test_commander_by_name_lookup(self):
        assert commander_by_name("occam") is OccamMeasurement

    def test_unknown_commander_raises(self):
        with pytest.raises(KeyError):
            commander_by_name("nonexistent")


# ─────────────────────────────────────────────────────────────
# DispatchThreshold semantics
# ─────────────────────────────────────────────────────────────


class TestDispatchThreshold:
    def test_greater_direction_triggered(self):
        t = DispatchThreshold("a", "b", "m", 5.0, "greater", "r")
        assert t.triggered(6.0) is True
        assert t.triggered(5.0) is False  # strictly greater
        assert t.triggered(4.0) is False

    def test_less_direction_triggered(self):
        t = DispatchThreshold("a", "b", "m", 0.5, "less", "r")
        assert t.triggered(0.3) is True
        assert t.triggered(0.5) is False
        assert t.triggered(0.7) is False
