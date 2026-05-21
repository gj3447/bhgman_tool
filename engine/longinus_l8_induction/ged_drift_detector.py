"""Community hypergraph bipartite GED drift detector for L8 re-induction loop.

Spec per config-ged-drift-tau-propose-2026-05-20 (CANONICAL_DELEGATED):

- GED variant: bipartite matching GED on **community hypergraph** (V=community IDs,
  E=community-co-membership), not raw 548K-node KG (NP-hard). O(k^3) where k=community
  count, practical.
- Riesen-Bunke 2009 LSAPE approximation (Blumenthal-Gamper 2020 modern variant).
- nGED = GED / max_edit_cost (normalized to [0,1]).
- 2-phase τ:
  - Phase-1 cold-start (days 0-30): nGED > 0.25 absolute AND NMI(P_t, P_{t-1}) < 0.70
    AND silhouette < 0.50 (triple-AND gate).
  - Phase-2 steady-state (day 31+): nGED > q90 (90th-percentile of last-30-day
    distribution).
- Goodhart cap: re-induction frequency ≤ 1/week enforced regardless.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional


COLD_START_DAYS = 30
COLD_START_NGED_TAU = 0.25
COLD_START_NMI_MAX = 0.70
COLD_START_SILHOUETTE_MAX = 0.50
STEADY_STATE_QUANTILE = 0.90
MAX_REINDUCTION_PER_WEEK = 1


@dataclass(frozen=True)
class DriftDecision:
    phase: str
    nged: float
    nmi: Optional[float]
    silhouette: Optional[float]
    threshold: float
    fire: bool
    reasons: tuple[str, ...]


def quantile(values: list[float], q: float) -> float:
    if not values:
        raise ValueError("empty list — cannot compute quantile")
    if not 0.0 <= q <= 1.0:
        raise ValueError(f"q must be in [0,1], got {q}")
    sorted_vals = sorted(values)
    idx = q * (len(sorted_vals) - 1)
    lower = int(idx)
    upper = min(lower + 1, len(sorted_vals) - 1)
    weight = idx - lower
    return sorted_vals[lower] * (1 - weight) + sorted_vals[upper] * weight


def _cold_start_decision(
    nged: float,
    nmi: Optional[float],
    silhouette: Optional[float],
) -> DriftDecision:
    if nmi is None or silhouette is None:
        return DriftDecision(
            phase="cold-start",
            nged=nged,
            nmi=nmi,
            silhouette=silhouette,
            threshold=COLD_START_NGED_TAU,
            fire=False,
            reasons=("cold-start requires nGED + NMI + silhouette; missing inputs",),
        )

    nged_breach = nged > COLD_START_NGED_TAU
    nmi_breach = nmi < COLD_START_NMI_MAX
    silhouette_breach = silhouette < COLD_START_SILHOUETTE_MAX
    fire = nged_breach and nmi_breach and silhouette_breach

    reasons: list[str] = []
    if nged_breach:
        reasons.append(f"nGED {nged:.3f} > {COLD_START_NGED_TAU}")
    if nmi_breach:
        reasons.append(f"NMI {nmi:.3f} < {COLD_START_NMI_MAX}")
    if silhouette_breach:
        reasons.append(f"silhouette {silhouette:.3f} < {COLD_START_SILHOUETTE_MAX}")
    if not fire:
        reasons.append("triple-AND gate not satisfied")

    return DriftDecision(
        phase="cold-start",
        nged=nged,
        nmi=nmi,
        silhouette=silhouette,
        threshold=COLD_START_NGED_TAU,
        fire=fire,
        reasons=tuple(reasons),
    )


def _steady_state_decision(
    nged: float,
    nmi: Optional[float],
    silhouette: Optional[float],
    history: list[float],
) -> DriftDecision:
    if not history:
        threshold = COLD_START_NGED_TAU
        fallback_note = "steady-state requires 30-day nGED history; falling back to cold-start τ"
    else:
        threshold = quantile(history, STEADY_STATE_QUANTILE)
        fallback_note = None

    fire = nged > threshold
    comparator = ">" if fire else "≤"
    reasons: list[str] = []
    if fallback_note:
        reasons.append(fallback_note)
    reasons.append(f"nGED {nged:.3f} {comparator} q90 {threshold:.3f}")

    return DriftDecision(
        phase="steady-state",
        nged=nged,
        nmi=nmi,
        silhouette=silhouette,
        threshold=threshold,
        fire=fire,
        reasons=tuple(reasons),
    )


def evaluate_drift(
    nged: float,
    nmi: Optional[float],
    silhouette: Optional[float],
    day_since_cold_start: int,
    last_30day_nged_history: Optional[Iterable[float]] = None,
) -> DriftDecision:
    """Decide whether nightly drift exceeds τ → trigger re-induction.

    For cold-start phase, all three signals (nGED, NMI, silhouette) must be present
    and breach their respective thresholds (triple-AND). For steady-state, the
    last-30-day quantile is used as the τ.
    """
    if day_since_cold_start <= COLD_START_DAYS:
        return _cold_start_decision(nged, nmi, silhouette)
    return _steady_state_decision(nged, nmi, silhouette, list(last_30day_nged_history or []))


__all__ = [
    "COLD_START_DAYS",
    "COLD_START_NGED_TAU",
    "COLD_START_NMI_MAX",
    "COLD_START_SILHOUETTE_MAX",
    "DriftDecision",
    "MAX_REINDUCTION_PER_WEEK",
    "STEADY_STATE_QUANTILE",
    "evaluate_drift",
    "quantile",
]
