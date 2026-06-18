"""Naesengmoon decorrelation core — honest effective-independence (n_eff) of a critic ensemble.

LLM critics fail in correlated common-mode (same family / shared executor framing → shared
misread), so N agreeing critics ≠ N independent votes. This module computes effective
independence and aggregates verdicts so correlated agreement is NOT inflated into confidence.

Grounding (consensus-prom8-naesengmoon-decorrelation-2026-05-31):
  • n_eff = n_oracle + n_judgment / (1 + (n_judgment-1)·ρ)   — Kish 1965 design effect
  • oracle critics (compiler / Lean / cypher-recount) are substrate-disjoint → independent.
  • prompt-echo: executor framing leaking into a critic's reasoning ⇒ shared-misread risk,
    flagged via bigram overlap and excluded from the judgment tally (this session's failure mode).

Pure-python (stdlib only). No external services. See engine/naesengmoon/tests.
# KG: consensus-prom8-naesengmoon-decorrelation-2026-05-31,
#     finding-prom8nm-D1-neff-ev, finding-prom8nm-D2-neff-wire, finding-prom8nm-B2-lens-wire
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from enum import Enum
from itertools import combinations

# Conservative prior for same-family LLM critics when ρ can't be measured
# (empirical floor ρ≥0.35 on zero-knowledge prompts; same-family ρ≈0.7–0.8 — arXiv:2602.08003).
DEFAULT_RHO = 0.7
ECHO_THRESHOLD = 0.65  # bigram-overlap above this ⇒ critic echoed the executor's framing


class CriticKind(str, Enum):
    # KG: naesengmoon-canonical-2026-05-19
    ORACLE = "oracle"  # deterministic checker — substrate-disjoint from LLMs
    JUDGMENT = "judgment"  # LLM critic — subject to correlated common-mode failure


@dataclass
class CriticVerdict:
    # KG: naesengmoon-canonical-2026-05-19
    lens: str
    kind: CriticKind
    passed: bool
    model_family: str = "unknown"
    echo_suspect: bool = False


@dataclass
class EnsembleResult:
    # KG: naesengmoon-canonical-2026-05-19
    verdict: str  # PASS | CONDITIONAL_PASS | FAIL
    n_critics: int  # total dispatched
    n_oracle: int
    n_judgment: int  # judgment critics actually counted (echo-suspects excluded)
    n_echo_excluded: int
    rho: float
    n_eff: float
    raw_coverage: float  # naive pass-fraction
    adjusted_confidence: float  # raw × shrinkage(n_eff / participating)
    summary: str


# ---- n_eff (Kish design effect) -------------------------------------------------


def effective_n(n_oracle: int, n_judgment: int, rho: float) -> float:
    # KG: naesengmoon-canonical-2026-05-19
    """Oracle critics stay independent; judgment critics collapse under correlation ρ."""
    rho = min(max(rho, 0.0), 1.0)
    if n_judgment <= 1:
        judgment_eff = float(n_judgment)
    else:
        judgment_eff = n_judgment / (1.0 + (n_judgment - 1) * rho)
    return n_oracle + judgment_eff


def _pearson_binary(a: list[bool], b: list[bool]) -> float | None:
    n = min(len(a), len(b))
    xa = [1.0 if a[i] else 0.0 for i in range(n)]
    xb = [1.0 if b[i] else 0.0 for i in range(n)]
    ma, mb = sum(xa) / n, sum(xb) / n
    va = sum((x - ma) ** 2 for x in xa)
    vb = sum((x - mb) ** 2 for x in xb)
    if va == 0 or vb == 0:
        return None  # a critic with no variance (always-pass) → correlation undefined
    cov = sum((xa[i] - ma) * (xb[i] - mb) for i in range(n))
    return cov / math.sqrt(va * vb)


def estimate_rho(vote_matrix: list[list[bool]]) -> float | None:
    # KG: naesengmoon-canonical-2026-05-19
    """Mean pairwise correlation of binary votes over a shared known-answer probe set.

    vote_matrix[c] = critic c's PASS/FAIL votes on the same probe items. None if < 2 usable
    critics or all pairs degenerate. Clamped to [0,1] (negative correlation → treat as 0)."""
    critics = [v for v in vote_matrix if len(v) >= 2]
    if len(critics) < 2:
        return None
    corrs = [r for a, b in combinations(critics, 2) if (r := _pearson_binary(a, b)) is not None]
    if not corrs:
        return None
    return max(0.0, sum(corrs) / len(corrs))


# ---- prompt-echo detector -------------------------------------------------------

_TOKEN = re.compile(r"[a-z0-9]+")


def _bigrams(text: str) -> set[tuple[str, str]]:
    toks = _TOKEN.findall(text.lower())
    return {(toks[i], toks[i + 1]) for i in range(len(toks) - 1)}


_MIN_HINT_BIGRAMS = (
    3  # below this a hint is too short to reliably distinguish echo from coincidence
)


def prompt_echo_score(executor_hint: str, critic_reasoning: str) -> float:
    # KG: naesengmoon-canonical-2026-05-19
    """Overlap coefficient of bigrams — fraction of the executor's framing echoed by the critic.

    High ⇒ the critic likely inherited the executor's hypothesis rather than verifying
    independently (the 1st-naesengmoon prompt-echo REFUTE → steelman PASS flip, this session).

    A short hint (< _MIN_HINT_BIGRAMS) scores 0.0: with only a bigram or two, ANY critic that
    happens to use those words trivially saturates the overlap coefficient to 1.0 and falsely
    flags an independent critic as an echo (W3-N)."""
    hb = _bigrams(executor_hint)
    cb = _bigrams(critic_reasoning)
    if len(hb) < _MIN_HINT_BIGRAMS or not cb:
        return 0.0
    return len(hb & cb) / len(hb)


def flag_echo(
    verdicts: list[CriticVerdict],
    executor_hint: str,
    reasonings: dict[str, str],
    threshold: float = ECHO_THRESHOLD,
) -> None:
    # KG: naesengmoon-canonical-2026-05-19
    """Mutate JUDGMENT verdicts: set echo_suspect when their reasoning echoes the executor."""
    for v in verdicts:
        if v.kind is CriticKind.JUDGMENT and v.lens in reasonings:
            if prompt_echo_score(executor_hint, reasonings[v.lens]) > threshold:
                v.echo_suspect = True


# ---- correlation-aware aggregation ----------------------------------------------


def _verdict_label(
    oracle_fail: bool, all_pass: bool, adjusted: float, raw: float, n_eff: float, n_oracle: int
) -> str:
    if oracle_fail:
        return "FAIL"  # oracle hard-gate — judgment critics cannot override
    # No oracle + low effective n (≤ a lone or correlated judgment) can NEVER be a clean
    # PASS. This guard MUST precede the all_pass shortcut: a single judgment critic sits at
    # n_eff=1.0 with adjusted=1.0 and was reaching PASS through it (W3-D).
    if n_eff < 1.5 and n_oracle == 0:
        return "CONDITIONAL_PASS"  # correlated/lone judgment only → capped, never a clean PASS
    if all_pass and adjusted >= 0.90:
        return "PASS"
    if raw >= 0.60:
        return "CONDITIONAL_PASS"
    return "FAIL"


def aggregate(verdicts: list[CriticVerdict], rho: float | None = None) -> EnsembleResult:
    # KG: naesengmoon-canonical-2026-05-19
    """Oracle-veto + independence-weighted judgment → honest verdict carrying n_eff.

    rho: measured inter-critic correlation (via estimate_rho); falls back to DEFAULT_RHO."""
    oracles = [v for v in verdicts if v.kind is CriticKind.ORACLE]
    judgments = [v for v in verdicts if v.kind is CriticKind.JUDGMENT and not v.echo_suspect]
    n_echo = sum(1 for v in verdicts if v.kind is CriticKind.JUDGMENT and v.echo_suspect)

    n_oracle, n_judgment = len(oracles), len(judgments)
    participating = oracles + judgments
    rho_used = DEFAULT_RHO if rho is None else min(max(rho, 0.0), 1.0)
    n_eff = effective_n(n_oracle, n_judgment, rho_used)

    oracle_fail = any(not o.passed for o in oracles)
    raw = (sum(1 for v in participating if v.passed) / len(participating)) if participating else 0.0
    all_pass = bool(participating) and all(v.passed for v in participating)
    shrink = (n_eff / len(participating)) if participating else 0.0
    adjusted = raw * shrink

    verdict = _verdict_label(oracle_fail, all_pass, adjusted, raw, n_eff, n_oracle)
    summary = (
        f"{len(verdicts)} critics ({n_oracle} oracle + {n_judgment} judgment"
        + (f", {n_echo} echo-excluded" if n_echo else "")
        + f"), ρ={rho_used:.2f}, n_eff≈{n_eff:.2f}. "
        f"raw={raw:.2f} → adjusted={adjusted:.2f}. verdict={verdict}."
    )
    return EnsembleResult(
        verdict,
        len(verdicts),
        n_oracle,
        n_judgment,
        n_echo,
        rho_used,
        n_eff,
        raw,
        adjusted,
        summary,
    )
