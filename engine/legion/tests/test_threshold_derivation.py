"""Tests for ROC Youden J threshold derivation.

PROM 16 P1(a) ActionPlan: real VR data (N=35) ROC sweep + Cohen-N≥30 gate.
"""

from __future__ import annotations

import pytest

from engine.legion.threshold_derivation.roc_youden import (
    APPROVED_VERDICTS,
    REJECTED_VERDICTS,
    DerivationResult,
    derive_roc_youden_j,
    label_outcome,
)


class TestLabelOutcome:
    def test_approved_maps_to_1(self) -> None:
        for v in APPROVED_VERDICTS:
            assert label_outcome(v) == 1

    def test_rejected_maps_to_0(self) -> None:
        for v in REJECTED_VERDICTS:
            assert label_outcome(v) == 0

    def test_unknown_returns_none(self) -> None:
        assert label_outcome("BORDERLINE") is None
        assert label_outcome("PARTIAL") is None
        assert label_outcome("INTENTIONAL_EDIT") is None


class TestDeriveRocYoudenJ:
    def test_rejects_below_30_samples(self) -> None:
        pairs = [(0.5 + 0.01 * i, i % 2) for i in range(29)]
        with pytest.raises(ValueError, match="Cohen 1988"):
            derive_roc_youden_j(pairs)

    def test_perfect_separation_yields_j_equals_1(self) -> None:
        # 15 negatives below 0.5, 15 positives above 0.5
        pairs = [(0.1 + 0.01 * i, 0) for i in range(15)]
        pairs += [(0.8 + 0.01 * i, 1) for i in range(15)]
        result = derive_roc_youden_j(pairs)
        assert result.youden_j == pytest.approx(1.0)
        assert result.sensitivity == pytest.approx(1.0)
        assert result.specificity == pytest.approx(1.0)
        assert 0.5 <= result.threshold <= 0.85

    def test_random_yields_j_near_0(self) -> None:
        # Alternating labels at uniform scores → no separation
        pairs = [(0.1 + 0.01 * i, i % 2) for i in range(40)]
        result = derive_roc_youden_j(pairs)
        assert result.youden_j < 0.3

    def test_returns_frozen_dataclass(self) -> None:
        pairs = [(0.1 + 0.01 * i, 0) for i in range(15)]
        pairs += [(0.8 + 0.01 * i, 1) for i in range(15)]
        result = derive_roc_youden_j(pairs)
        assert isinstance(result, DerivationResult)
        with pytest.raises(AttributeError):
            result.threshold = 0.0  # type: ignore[misc]

    def test_kg_props_serializes(self) -> None:
        pairs = [(0.1 + 0.01 * i, 0) for i in range(15)]
        pairs += [(0.8 + 0.01 * i, 1) for i in range(15)]
        result = derive_roc_youden_j(pairs)
        props = result.to_kg_props()
        assert props["method"] == "roc_youden_j_1950"
        assert props["citation"] == "Youden W.J. 1950 Cancer 3:32-35"
        assert props["n_total"] == 30
        assert "threshold" in props
        assert "youden_j" in props

    def test_real_vr_distribution_n35(self) -> None:
        """Smoke test with the real KG VR distribution (N=35 confidence values).

        Values pulled 2026-05-30 from MATCH (vr:ValidationResult)
        WHERE vr.confidence IS NOT NULL AND vr.verdict IS NOT NULL.
        Excludes BORDERLINE / PARTIAL / INTENTIONAL_EDIT (ambiguous).
        """
        real_data = [
            (0.0, "REJECTED"),
            (0.42, "CONDITIONAL_APPROVED"),
            (0.55, "PARTIAL"),
            (0.62, "CONDITIONAL_PASS"),
            (0.62, "CONDITIONAL_APPROVED"),
            (0.62, "REQUIRES_CHANGES"),
            (0.68, "CONDITIONAL_APPROVED"),
            (0.71, "CONDITIONAL_APPROVED"),
            (0.71, "CONDITIONAL_APPROVED"),
            (0.71, "CONDITIONAL_APPROVED"),
            (0.71, "CONDITIONAL_APPROVED"),
            (0.71, "CONDITIONAL_APPROVED"),
            (0.72, "CONDITIONAL_APPROVED"),
            (0.72, "CONDITIONAL_APPROVED"),
            (0.74, "CONDITIONAL_APPROVED"),
            (0.74, "CONDITIONAL_APPROVED"),
            (0.74, "CONDITIONAL_APPROVED"),
            (0.74, "CONDITIONAL_APPROVED"),
            (0.78, "CONDITIONAL_APPROVED"),
            (0.78, "CONDITIONAL_APPROVED"),
            (0.78, "CONDITIONAL_APPROVED"),
            (0.78, "CONDITIONAL_PASS"),
            (0.78, "CONDITIONAL_APPROVED"),
            (0.82, "CONDITIONAL_PASS_REMEDIATED"),
            (0.82, "CONDITIONAL_PASS"),
            (0.82, "CONDITIONAL_PASS"),
            (0.84, "APPROVED"),
            (0.84, "CONDITIONAL_PASS"),
            (0.88, "CONDITIONAL_PASS"),
            (0.92, "APPROVED"),
            (0.92, "INTENTIONAL_EDIT"),
            (0.95, "APPROVED"),
            (0.95, "REJECTED"),
        ]
        pairs: list[tuple[float, int]] = []
        for score, verdict in real_data:
            y = label_outcome(verdict)
            if y is not None:
                pairs.append((score, y))
        assert len(pairs) >= 30, f"need ≥30 labeled; got {len(pairs)}"
        result = derive_roc_youden_j(pairs)
        assert 0.0 <= result.threshold <= 1.0
        assert -1.0 <= result.youden_j <= 1.0
