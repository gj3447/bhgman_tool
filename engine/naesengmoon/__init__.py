"""Naesengmoon decorrelation — honest effective-independence (n_eff) for the critic ensemble.

See engine/naesengmoon/decorrelation.py and consensus-prom8-naesengmoon-decorrelation-2026-05-31.
"""
# KG: naesengmoon-canonical-2026-05-19

from .decorrelation import (
    CriticKind,
    CriticVerdict,
    EnsembleResult,
    aggregate,
    effective_n,
    estimate_rho,
    flag_echo,
    prompt_echo_score,
)

__all__ = [
    "CriticKind",
    "CriticVerdict",
    "EnsembleResult",
    "aggregate",
    "effective_n",
    "estimate_rho",
    "flag_echo",
    "prompt_echo_score",
]
