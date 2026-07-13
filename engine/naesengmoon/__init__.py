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
from .ipt import (
    IptResult,
    IptVerdict,
    generate_isomorphs,
    ipt_check,
    rename_placeholders,
    reorder_commutative,
)
from .kg_corroboration import KgCorroborationOracle, kg_corroboration_oracle
from .reward_hack_guard import RewardHackVerdict, guard_patch

__all__ = [
    "CriticKind",
    "CriticVerdict",
    "EnsembleResult",
    "IptResult",
    "IptVerdict",
    "KgCorroborationOracle",
    "RewardHackVerdict",
    "aggregate",
    "effective_n",
    "estimate_rho",
    "flag_echo",
    "generate_isomorphs",
    "guard_patch",
    "ipt_check",
    "kg_corroboration_oracle",
    "prompt_echo_score",
    "rename_placeholders",
    "reorder_commutative",
]
