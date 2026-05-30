"""ROC sweep + Youden J statistic threshold derivation.

Academic: Youden W.J. 1950 "Index for rating diagnostic tests." Cancer 3:32-35.
  J = sensitivity + specificity - 1
  Optimal threshold τ* = argmax_τ J(τ)

PROM 16 P1(a): Naesengmoon confidence-as-proxy derivation from KG VR data.
N=35 (current real count, not the subagent-claimed N=43 which was inflated).

# KG: actionplan-threshold-derivation-2026-05-30 P1
# KG: mitigation-derive-naesengmoon-roc-youden-j-immediate-2026-05-30
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final


APPROVED_VERDICTS: Final[frozenset[str]] = frozenset(
    {
        "APPROVED",
        "PASS",
        "UPHELD",
        "APPROVED_AFTER_FIX",
        "APPROVED_WITH_CONDITIONS",
        "APPROVED_WITH_CORRECTIONS",
        "APPROVED_PENDING_EXTERNAL_D20",
        "PASS_v08-A1",
        "CONDITIONAL_APPROVED",
        "CONDITIONAL_PASS",
        "CONDITIONAL_PASS_REMEDIATED",
        "CONDITIONAL_APPROVED_WITH_RECONCILIATION",
        "CONDITIONAL_APPROVED_WITH_DISSENT",
    }
)
REJECTED_VERDICTS: Final[frozenset[str]] = frozenset(
    {
        "REJECTED",
        "REJECT",
        "FAIL",
        "REQUIRES_CHANGES",
    }
)


def label_outcome(verdict: str) -> int | None:
    """Map verdict string to binary outcome: 1=approved, 0=rejected, None=ambiguous."""
    if verdict in APPROVED_VERDICTS:
        return 1
    if verdict in REJECTED_VERDICTS:
        return 0
    return None


@dataclass(frozen=True)
class DerivationResult:
    """Frozen result of a ROC Youden J sweep."""

    threshold: float
    youden_j: float
    sensitivity: float
    specificity: float
    n_total: int
    n_positive: int
    n_negative: int
    method: str = "roc_youden_j_1950"
    citation: str = "Youden W.J. 1950 Cancer 3:32-35"

    def to_kg_props(self) -> dict[str, float | str | int]:
        return {
            "threshold": self.threshold,
            "youden_j": self.youden_j,
            "sensitivity": self.sensitivity,
            "specificity": self.specificity,
            "n_total": self.n_total,
            "n_positive": self.n_positive,
            "n_negative": self.n_negative,
            "method": self.method,
            "citation": self.citation,
        }


def derive_roc_youden_j(
    pairs: list[tuple[float, int]],
) -> DerivationResult:
    """Sweep ROC, return τ* maximizing Youden J.

    Args:
        pairs: list of (score, outcome) where outcome ∈ {0, 1}.

    Raises:
        ValueError: if N < 30 (power-analysis adequacy floor per Cohen 1988).
    """
    n = len(pairs)
    if n < 30:
        raise ValueError(
            f"N={n} below Cohen 1988 power-analysis adequacy floor (≥30). "
            f"Derivation unsound; collect more data or accept PROVISIONAL only."
        )

    pos = sum(1 for _, y in pairs if y == 1)
    neg = n - pos
    if pos == 0 or neg == 0:
        raise ValueError("Both classes must have ≥1 instance for ROC sweep.")

    candidates = sorted({s for s, _ in pairs})
    best = DerivationResult(
        threshold=candidates[0],
        youden_j=-1.0,
        sensitivity=0.0,
        specificity=0.0,
        n_total=n,
        n_positive=pos,
        n_negative=neg,
    )

    for tau in candidates:
        tp = sum(1 for s, y in pairs if s >= tau and y == 1)
        fn = sum(1 for s, y in pairs if s < tau and y == 1)
        tn = sum(1 for s, y in pairs if s < tau and y == 0)
        fp = sum(1 for s, y in pairs if s >= tau and y == 0)
        sens = tp / (tp + fn) if (tp + fn) else 0.0
        spec = tn / (tn + fp) if (tn + fp) else 0.0
        j = sens + spec - 1
        if j > best.youden_j:
            best = DerivationResult(
                threshold=tau,
                youden_j=j,
                sensitivity=sens,
                specificity=spec,
                n_total=n,
                n_positive=pos,
                n_negative=neg,
            )
    return best
