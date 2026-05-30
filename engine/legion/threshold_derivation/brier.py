"""Brier score calibration measurement.

Academic: Brier G.W. 1950 "Verification of forecasts expressed in terms of
probability" Monthly Weather Review 78:1-3.

BS = (1/N) Σ (p_i - o_i)^2 where p_i is predicted probability, o_i ∈ {0,1}.
Lower is better; 0 = perfect calibration, 0.25 = random binary forecast.

Decomposition (Murphy 1973):
  BS = Reliability - Resolution + Uncertainty
  Reliability ↓ when forecasts match observed frequencies in bins.

PROM 16 P2(d): per-decision Brier score on the DispatchDecision history.

# KG: actionplan-threshold-derivation-2026-05-30 P2(d)
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BrierResult:
    """Frozen Brier score + decomposition."""

    brier_score: float
    reliability: float
    resolution: float
    uncertainty: float
    n_samples: int
    n_bins: int
    method: str = "brier_1950_with_murphy_1973_decomposition"
    citation: str = "Brier 1950 + Murphy 1973"

    def to_kg_props(self) -> dict[str, float | str | int]:
        return {
            "brier_score": self.brier_score,
            "reliability": self.reliability,
            "resolution": self.resolution,
            "uncertainty": self.uncertainty,
            "n_samples": self.n_samples,
            "n_bins": self.n_bins,
            "method": self.method,
            "citation": self.citation,
        }


def brier_score(predictions: list[tuple[float, int]]) -> BrierResult:
    """Compute Brier score with Murphy 1973 decomposition.

    Args:
        predictions: list of (predicted_probability, outcome) with outcome ∈ {0,1}.

    Raises:
        ValueError: if predictions empty or invalid.
    """
    if not predictions:
        raise ValueError("predictions must be non-empty")
    n = len(predictions)
    for p, o in predictions:
        if not 0.0 <= p <= 1.0:
            raise ValueError(f"probability out of [0,1]: {p}")
        if o not in (0, 1):
            raise ValueError(f"outcome must be 0 or 1, got {o}")

    bs = sum((p - o) ** 2 for p, o in predictions) / n

    base_rate = sum(o for _, o in predictions) / n
    uncertainty = base_rate * (1 - base_rate)

    n_bins = 10
    bins: list[list[tuple[float, int]]] = [[] for _ in range(n_bins)]
    for p, o in predictions:
        idx = min(int(p * n_bins), n_bins - 1)
        bins[idx].append((p, o))

    reliability = 0.0
    resolution = 0.0
    for bucket in bins:
        if not bucket:
            continue
        nk = len(bucket)
        avg_p = sum(p for p, _ in bucket) / nk
        avg_o = sum(o for _, o in bucket) / nk
        reliability += (nk / n) * (avg_p - avg_o) ** 2
        resolution += (nk / n) * (avg_o - base_rate) ** 2

    return BrierResult(
        brier_score=bs,
        reliability=reliability,
        resolution=resolution,
        uncertainty=uncertainty,
        n_samples=n,
        n_bins=n_bins,
    )
