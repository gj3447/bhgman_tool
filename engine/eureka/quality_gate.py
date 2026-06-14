"""Quality gate for AbstractCategory promotion before MERGE.

Thresholds per consensus seed-prom16lag-cons-quality-gate-silhouette-modularity-2026-05-20:
- silhouette s̄ ≥ 0.50 (Rousseeuw 1987)
- modularity Q ≥ 0.30 (Newman 2006 PNAS)
- FCA concept stability σ ≥ 0.50 (Roth-Obiedkov-Kourie 2008) when formal context applicable
- AMI ≥ 0.50 (Vinh-Epps-Bailey 2010) for supervised re-runs
- Goodhart cap (Zaveri 2016) — reject silhouette/modularity/AMI > 0.95 as a gamed proxy.
  fca_stability is EXEMPT: a fully-cohesive concept legitimately scores 1.0 (W1-E).
"""
# KG: eureka-canonical-2026-05-26

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


SILHOUETTE_MIN = 0.50
MODULARITY_MIN = 0.30
FCA_STABILITY_MIN = 0.50
AMI_MIN = 0.50
GOODHART_CAP = 0.95


@dataclass(frozen=True)
class QualityReport:
    silhouette: Optional[float]
    modularity: Optional[float]
    fca_stability: Optional[float]
    ami: Optional[float]
    passed: bool
    reasons: tuple[str, ...]


def evaluate(
    silhouette: Optional[float] = None,
    modularity: Optional[float] = None,
    fca_stability: Optional[float] = None,
    ami: Optional[float] = None,
) -> QualityReport:
    reasons: list[str] = []
    passed = True

    if silhouette is not None and silhouette < SILHOUETTE_MIN:
        passed = False
        reasons.append(f"silhouette {silhouette:.3f} < {SILHOUETTE_MIN}")

    if modularity is not None and modularity < MODULARITY_MIN:
        passed = False
        reasons.append(f"modularity {modularity:.3f} < {MODULARITY_MIN}")

    if fca_stability is not None and fca_stability < FCA_STABILITY_MIN:
        passed = False
        reasons.append(f"fca_stability {fca_stability:.3f} < {FCA_STABILITY_MIN}")

    if ami is not None and ami < AMI_MIN:
        passed = False
        reasons.append(f"ami {ami:.3f} < {AMI_MIN}")

    # Goodhart cap (Zaveri 2016): near-perfect silhouette/modularity/AMI signal a gamed
    # proxy. fca_stability is EXEMPT — a fully-cohesive formal concept legitimately scores
    # 1.0 (its extent exactly closes its intent); capping it rejected the STRONGEST
    # abstractions and halted the pipeline before stage 5 (W1-E).
    for label, value in [
        ("silhouette", silhouette),
        ("modularity", modularity),
        ("ami", ami),
    ]:
        if value is not None and value > GOODHART_CAP:
            passed = False
            reasons.append(
                f"{label} {value:.3f} > Goodhart cap {GOODHART_CAP} — suspect artifact, reject"
            )

    if all(v is None for v in [silhouette, modularity, fca_stability, ami]):
        passed = False
        reasons.append("no quality metric provided")

    return QualityReport(
        silhouette=silhouette,
        modularity=modularity,
        fca_stability=fca_stability,
        ami=ami,
        passed=passed,
        reasons=tuple(reasons),
    )


__all__ = [
    "AMI_MIN",
    "FCA_STABILITY_MIN",
    "GOODHART_CAP",
    "MODULARITY_MIN",
    "QualityReport",
    "SILHOUETTE_MIN",
    "evaluate",
]
