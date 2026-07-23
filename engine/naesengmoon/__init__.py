"""Naesengmoon decorrelation — honest effective-independence (n_eff) for the critic ensemble.

See engine/naesengmoon/decorrelation.py and consensus-prom8-naesengmoon-decorrelation-2026-05-31.

Two aggregation algebras, deliberately BOTH public (T1-1):
  * ``aggregate`` (decorrelation) — numeric Kish-n_eff algebra over bare CriticVerdicts.
    Production callers (legion _run_verify, ooptdd adapter) sit here.
  * ``decide`` (NCP-1 consensus) — richer policy algebra over Votes carrying evidence (HR11)
    and executor/reviewer (D20). NOT a drop-in for aggregate: a naive vote_from_critic
    delegation diverges on 3/4 canonical cases because CriticVerdict cannot supply the
    evidence/roles the admissibility gate demands (pinned in tests/test_consensus_interop.py).
    Callers that CAN supply evidence + distinct roles should prefer ``decide``.
Both algebras share the universal n_eff clean-PASS floor (no self-labeled-oracle exemption).
"""
# KG: naesengmoon-canonical-2026-05-19

from .consensus import (
    DEFAULT_POLICY,
    MIN_EFF_FOR_CLEAN_PASS,
    Admission,
    ConsensusResult,
    Disposition,
    Escalation,
    LensClass,
    Policy,
    PolicyKind,
    Vote,
    VoteValue,
    admit,
    decide,
    vote_from_critic,
)
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
    "DEFAULT_POLICY",
    "MIN_EFF_FOR_CLEAN_PASS",
    "Admission",
    "ConsensusResult",
    "CriticKind",
    "CriticVerdict",
    "Disposition",
    "EnsembleResult",
    "Escalation",
    "IptResult",
    "IptVerdict",
    "KgCorroborationOracle",
    "LensClass",
    "Policy",
    "PolicyKind",
    "RewardHackVerdict",
    "Vote",
    "VoteValue",
    "admit",
    "aggregate",
    "decide",
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
    "vote_from_critic",
]
