"""Threshold derivation pipeline — ROC Youden J / Bayesian MAP / CUSUM.

PROM 16 threshold-derivation P1 ActionPlan: bridge from academic methods to
actual KG historical data. Each derivation function takes raw (score, outcome)
pairs and returns (threshold, evidence_metadata).

# KG: actionplan-threshold-derivation-2026-05-30 P1
# KG: mitigation-derive-naesengmoon-roc-youden-j-immediate-2026-05-30
"""

from engine.legion.threshold_derivation.bayesian_map import (
    BayesianMAPResult,
    derive_bayesian_map,
)
from engine.legion.threshold_derivation.brier import BrierResult, brier_score
from engine.legion.threshold_derivation.config import (
    ThresholdEntry,
    load_thresholds,
)
from engine.legion.threshold_derivation.cusum import (
    CusumChart,
    DriftSignal,
    DualWindowCUSUM,
)
from engine.legion.threshold_derivation.roc_youden import (
    DerivationResult,
    derive_roc_youden_j,
)

__all__ = [
    "BayesianMAPResult",
    "BrierResult",
    "CusumChart",
    "DerivationResult",
    "DriftSignal",
    "DualWindowCUSUM",
    "ThresholdEntry",
    "brier_score",
    "derive_bayesian_map",
    "derive_roc_youden_j",
    "load_thresholds",
]
