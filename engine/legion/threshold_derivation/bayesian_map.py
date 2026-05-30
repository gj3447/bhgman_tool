"""Beta-Bernoulli Bayesian MAP threshold derivation.

Academic:
- Berger J.O. 1985 "Statistical Decision Theory and Bayesian Analysis" Springer.
- Conjugate prior Beta(α, β) for Bernoulli likelihood → posterior Beta(α+k, β+n-k).
- MAP threshold τ* = (α+k-1)/(α+β+n-2) for the posterior mode.

PROM 16 P2(a): Occam supersession_confidence. KG currently has 0 instrumented
samples (legacy OccamPass nodes carry qualitative verdict only); this module
provides the derivation function so that once instrument_occam_supersession()
accumulates N≥30 logged decisions, threshold derives directly.

# KG: actionplan-threshold-derivation-2026-05-30 P2(a)
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BayesianMAPResult:
    """Frozen result of a Beta-Bernoulli MAP derivation."""

    threshold: float
    posterior_alpha: float
    posterior_beta: float
    n_samples: int
    n_successes: int
    prior_alpha: float
    prior_beta: float
    method: str = "bayesian_map_beta_bernoulli_berger_1985"
    citation: str = "Berger J.O. 1985 Statistical Decision Theory, Springer §3"

    def to_kg_props(self) -> dict[str, float | str | int]:
        return {
            "threshold": self.threshold,
            "posterior_alpha": self.posterior_alpha,
            "posterior_beta": self.posterior_beta,
            "n_samples": self.n_samples,
            "n_successes": self.n_successes,
            "prior_alpha": self.prior_alpha,
            "prior_beta": self.prior_beta,
            "method": self.method,
            "citation": self.citation,
        }


def derive_bayesian_map(
    successes: int,
    total: int,
    prior_alpha: float = 1.0,
    prior_beta: float = 1.0,
) -> BayesianMAPResult:
    """Derive Beta-Bernoulli MAP threshold.

    Args:
        successes: number of positive outcomes (k).
        total: total observations (n).
        prior_alpha, prior_beta: Beta prior hyperparameters.
            Default (1, 1) = uniform / Laplace's rule of succession.

    Raises:
        ValueError: if total < 30 (power-analysis adequacy floor per Cohen 1988).
        ValueError: if successes > total or any input is negative.
    """
    if total < 30:
        raise ValueError(
            f"N={total} below Cohen 1988 power-analysis adequacy floor (≥30). "
            f"Derivation unsound; instrument and accumulate more data."
        )
    if successes < 0 or total < 0 or successes > total:
        raise ValueError(f"Invalid counts: k={successes}, n={total}")
    if prior_alpha <= 0 or prior_beta <= 0:
        raise ValueError(f"Prior hyperparameters must be positive: α={prior_alpha}, β={prior_beta}")

    post_alpha = prior_alpha + successes
    post_beta = prior_beta + total - successes

    if post_alpha + post_beta <= 2:
        threshold = 0.5
    else:
        threshold = (post_alpha - 1.0) / (post_alpha + post_beta - 2.0)
    threshold = max(0.0, min(1.0, threshold))

    return BayesianMAPResult(
        threshold=threshold,
        posterior_alpha=post_alpha,
        posterior_beta=post_beta,
        n_samples=total,
        n_successes=successes,
        prior_alpha=prior_alpha,
        prior_beta=prior_beta,
    )
