"""Naesengmoon 3-lens calibration audit — quarterly cadence.

PROM 16 P3(c): independent adversarial review of a derived threshold across:
  Lens 1 (mathematical): permutation test for null ECE / overfitting check.
  Lens 2 (formal type): scale axiom + monotonicity check (Lean spec mirror).
  Lens 3 (constitutional): borderline-instance spot-check, ≥10 cases.

Output: AuditVerdict with PASS / CONDITIONAL_BLOCK + per-lens record.

# KG: actionplan-threshold-derivation-2026-05-30 P3(c)
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class LensVerdict(Enum):
    PASS = "pass"
    CONDITIONAL = "conditional"
    BLOCK = "block"


@dataclass(frozen=True)
class LensRecord:
    name: str
    verdict: LensVerdict
    confidence: float
    note: str


@dataclass(frozen=True)
class AuditVerdict:
    threshold: float
    overall: LensVerdict
    lenses: tuple[LensRecord, ...]
    method: str = "naesengmoon_3lens_calibration_audit_2026_05_30"

    def to_kg_props(self) -> dict[str, float | str]:
        return {
            "threshold": self.threshold,
            "overall": self.overall.value,
            "lens_count": len(self.lenses),
            "method": self.method,
            "summary": "; ".join(f"{lens.name}={lens.verdict.value}" for lens in self.lenses),
        }


def _permutation_overfit_lens(
    actual_ece: float,
    null_ece_mean: float,
    null_ece_std: float,
) -> LensRecord:
    threshold = null_ece_mean + 2.0 * null_ece_std
    if actual_ece > threshold:
        return LensRecord(
            name="mathematical_permutation",
            verdict=LensVerdict.BLOCK,
            confidence=0.92,
            note=f"actual ECE {actual_ece:.3f} > null mean+2σ {threshold:.3f} → overfitting",
        )
    if actual_ece > null_ece_mean + null_ece_std:
        return LensRecord(
            name="mathematical_permutation",
            verdict=LensVerdict.CONDITIONAL,
            confidence=0.78,
            note=f"actual ECE {actual_ece:.3f} above null +1σ — increase regularization",
        )
    return LensRecord(
        name="mathematical_permutation",
        verdict=LensVerdict.PASS,
        confidence=0.88,
        note=f"actual ECE {actual_ece:.3f} ≤ null mean+1σ",
    )


def _formal_type_lens(scale_valid: bool, monotone_valid: bool) -> LensRecord:
    if not scale_valid:
        return LensRecord(
            name="formal_type",
            verdict=LensVerdict.BLOCK,
            confidence=1.0,
            note="Stevens scale axiom violation",
        )
    if not monotone_valid:
        return LensRecord(
            name="formal_type",
            verdict=LensVerdict.CONDITIONAL,
            confidence=0.82,
            note="monotonicity check fails — derivation may not narrow with N",
        )
    return LensRecord(
        name="formal_type",
        verdict=LensVerdict.PASS,
        confidence=0.96,
        note="Stevens scale + monotonicity intact",
    )


def _constitutional_lens(disagreement_ratio: float) -> LensRecord:
    if disagreement_ratio > 0.20:
        return LensRecord(
            name="constitutional_spot_check",
            verdict=LensVerdict.BLOCK,
            confidence=0.85,
            note=f"disagreement {disagreement_ratio:.2%} > 20% — borderline broken",
        )
    if disagreement_ratio > 0.10:
        return LensRecord(
            name="constitutional_spot_check",
            verdict=LensVerdict.CONDITIONAL,
            confidence=0.72,
            note=f"disagreement {disagreement_ratio:.2%} in 10-20% — review borderline cases",
        )
    return LensRecord(
        name="constitutional_spot_check",
        verdict=LensVerdict.PASS,
        confidence=0.90,
        note=f"disagreement {disagreement_ratio:.2%} ≤ 10%",
    )


def _aggregate(lenses: tuple[LensRecord, ...]) -> LensVerdict:
    """All-PASS → PASS. Any BLOCK → BLOCK. Else CONDITIONAL."""
    verdicts = [lens.verdict for lens in lenses]
    if any(v == LensVerdict.BLOCK for v in verdicts):
        return LensVerdict.BLOCK
    if all(v == LensVerdict.PASS for v in verdicts):
        return LensVerdict.PASS
    return LensVerdict.CONDITIONAL


def audit_threshold(
    threshold: float,
    actual_ece: float,
    null_ece_mean: float,
    null_ece_std: float,
    scale_valid: bool,
    monotone_valid: bool,
    disagreement_ratio: float,
) -> AuditVerdict:
    """Run 3-lens calibration audit; return aggregate verdict."""
    lenses = (
        _permutation_overfit_lens(actual_ece, null_ece_mean, null_ece_std),
        _formal_type_lens(scale_valid, monotone_valid),
        _constitutional_lens(disagreement_ratio),
    )
    return AuditVerdict(
        threshold=threshold,
        overall=_aggregate(lenses),
        lenses=lenses,
    )
