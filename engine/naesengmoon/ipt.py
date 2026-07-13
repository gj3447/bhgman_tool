"""IPT — Isomorphic Perturbation Testing lens (나생문 oracle-lens 강화 primitive).

A verifier that PASSes a claim in one surface form but FLIPs on a logically-equivalent
restatement is exploiting the *form*, not verifying the *relation*. This is the RLVR
extensional shortcut: reasoners abandon rule-induction and enumerate instance-level labels
that satisfy a form-checking verifier without capturing the relation (arXiv:2604.15149,
ICLR 2026). Detection = rerun the verifier over logically-isomorphic restatements and require
verdict INVARIANCE; variance ⇒ ESCALATE (the single-form PASS is untrustworthy).

Verifier-agnostic: `verify_fn` may be an oracle lens (compiler/execution — the trustworthy
gate) or a judgment lens (LLM). IPT strengthens *either* by making surface-form overfit visible.
Isomorphs are supplied by the caller (only the caller knows what is meaning-preserving for a
given claim); `generate_isomorphs` provides a couple of deterministic structure-preserving
transforms for common cases (alpha-renaming, commutative reordering).

Pure-python (stdlib only). No external services.

# KG: finding-prom16-ipt-isomorphic-perturbation-lens-2026-07-13,
#     naesengmoon-canonical-2026-05-19, formal-cathedral-detection-2026-05-27
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import Enum

# A verifier maps a claim string -> pass/fail (oracle or judgment lens).
VerifyFn = Callable[[str], bool]


class IptVerdict(str, Enum):
    # KG: naesengmoon-canonical-2026-05-19
    ROBUST_PASS = "robust_pass"  # base passed AND invariant across every isomorph
    ROBUST_FAIL = "robust_fail"  # base failed AND invariant
    ESCALATE = "escalate"  # verdict varied across isomorphs → surface-form exploit


@dataclass(frozen=True)
class IptResult:
    # KG: naesengmoon-canonical-2026-05-19
    verdict: IptVerdict
    base_passed: bool
    invariant: bool
    n_variants: int
    flipped: tuple[str, ...]  # isomorphs whose verdict differed from the base
    summary: str


def ipt_check(
    base_claim: str, variants: Sequence[str], verify_fn: VerifyFn
) -> IptResult:
    # KG: naesengmoon-canonical-2026-05-19
    """Verdict must be invariant across logically-isomorphic restatements.

    ROBUST_PASS / ROBUST_FAIL only when every variant agrees with the base; any disagreement
    ⇒ ESCALATE (the verifier is form-sensitive, so its PASS cannot be trusted — hand to a
    stronger oracle per formal-cathedral escalate-to-oracle)."""
    base_passed = bool(verify_fn(base_claim))
    flipped = tuple(v for v in variants if bool(verify_fn(v)) != base_passed)
    invariant = not flipped
    if not invariant:
        verdict = IptVerdict.ESCALATE
    elif base_passed:
        verdict = IptVerdict.ROBUST_PASS
    else:
        verdict = IptVerdict.ROBUST_FAIL
    summary = (
        f"base={'PASS' if base_passed else 'FAIL'} over {len(variants)} isomorph(s): "
        + (
            "invariant → " + verdict.value
            if invariant
            else f"{len(flipped)} flipped → ESCALATE (surface-form exploit)"
        )
    )
    return IptResult(
        verdict=verdict,
        base_passed=base_passed,
        invariant=invariant,
        n_variants=len(variants),
        flipped=flipped,
        summary=summary,
    )


# ---- structure-preserving perturbations (caller asserts applicability) ----------

_IDENT = re.compile(r"[A-Za-z_]\w*")


def rename_placeholders(claim: str, mapping: dict[str, str]) -> str:
    # KG: naesengmoon-canonical-2026-05-19
    """Consistent alpha-rename of identifier tokens. Meaning-preserving under alpha-equivalence
    (bound-variable renaming); numbers/operators/unmapped tokens are left verbatim."""
    return _IDENT.sub(lambda m: mapping.get(m.group(0), m.group(0)), claim)


def reorder_commutative(claim: str, sep: str) -> str:
    # KG: naesengmoon-canonical-2026-05-19
    """Reverse the order of clauses separated by `sep`. Meaning-preserving ONLY when `sep`
    is a commutative connective (∧ / , / +) — the caller guarantees that."""
    return sep.join(reversed(claim.split(sep)))


def generate_isomorphs(
    claim: str,
    *,
    renames: dict[str, str] | None = None,
    commutative_sep: str | None = None,
) -> list[str]:
    # KG: naesengmoon-canonical-2026-05-19
    """Build deterministic logically-isomorphic restatements of `claim`, excluding the base.

    Applies each requested transform independently (alpha-rename, commutative reorder). Returns
    de-duplicated variants that differ from `claim`."""
    out: list[str] = []
    if renames:
        out.append(rename_placeholders(claim, renames))
    if commutative_sep is not None and commutative_sep in claim:
        out.append(reorder_commutative(claim, commutative_sep))
    seen: set[str] = set()
    uniq: list[str] = []
    for v in out:
        if v != claim and v not in seen:
            seen.add(v)
            uniq.append(v)
    return uniq


__all__ = [
    "IptResult",
    "IptVerdict",
    "VerifyFn",
    "generate_isomorphs",
    "ipt_check",
    "rename_placeholders",
    "reorder_commutative",
]
