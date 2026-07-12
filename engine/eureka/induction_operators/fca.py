"""FCA (Formal Concept Analysis) induction operator.

Ganter-Wille 1999 fundamental theorem. Extent/intent Galois closure. Idempotent.

Theory↔code bridge (colimit): the academic grounding (THEORY/유레카/PROM_16_EUREKA_
ACADEMIC_REPORT.md §C4) states "ILP predicate-invention ⇔ FCA concept-lattice ⇔
category-theory colimit" — the *same construction in three languages*. Eureka's
Phase-2 synthesis is characterized categorically as a colimit, but is *realized in
code by this Galois closure* (concept-lattice join), NOT by a literal `colimit`
symbol. Per user verdict 2026-05-29 the colimit framing was downgraded to a
Phase-2 sub-step (colimit ⊊ eureka); the operational form is FCA here +
community-merge in stages.py + anti_unify (Plotkin LGG) on the code-template path.

Completeness fix (2026-07-12, prom16-eureka-fca-fsm): the prior enumeration computed
only the object concepts γ(g)=({g}″,{g}′) — the ⋁-dense generators — and thus MISSED
every proper meet-concept (a concept that is the intersection of two-or-more object
extents but is not itself any single {g}″). The full lattice B(K) is now enumerated
via Ganter's NextClosure (1984): all closed intents in lectic order, each exactly
once, O(1) concept memory, no dedup bookkeeping. See THEORY/eureka_fca_lattice/
PROM_16_FCA_FSM_REPORT.md and lesson-eureka-fca-incompleteness-singleton-closures-2026-07-12.
# KG: eureka-canonical-2026-05-26 (colimit_subsumption_2026_05_29), consensus-eureka-academic-grounding-2026-05-26

Constraint per seed-prom16lag-conflict-fca-dense-avoid-vs-sparse-rec-2026-05-20:
- Use only when formal context is binary or conceptually-scaled
- Bound |concepts| via the concept-count budget (MAX_CONCEPTS) — degenerate/dense
  contexts blow up to 2^min(|G|,|M|); above budget → fall back to AMIE+ or Leiden.
- Batch size ≤ 500 nodes. Above threshold → fall back to AMIE+ or Leiden.
- Stability is NEVER used to prune during enumeration (it is non-anti-monotone and
  #P-complete → silent concept loss); it is a POST-hoc output ranking/filter only.
"""
# KG: eureka-canonical-2026-05-26

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


MAX_BATCH = 500
# Concept-count circuit breaker (prom16 scalability lever): a full concept lattice is
# worst-case exponential (contranominal scale). Above this, fall back rather than OOM.
MAX_CONCEPTS = 100_000


@dataclass(frozen=True)
class FormalConcept:
    # KG: eureka-canonical-2026-05-26
    extent: frozenset[str]
    intent: frozenset[str]
    stability: float


@dataclass(frozen=True)
class FcaResult:
    # KG: eureka-canonical-2026-05-26
    concepts: tuple[FormalConcept, ...]
    pruned: int
    fallback_reason: str | None


# ── Galois derivations (the two prime operators of the antitone connection) ──────


def _all_attributes(context: Mapping[str, frozenset[str]]) -> frozenset[str]:
    out: set[str] = set()
    for attrs in context.values():
        out |= attrs
    return frozenset(out)


def _intent_of(
    extent: frozenset[str],
    context: Mapping[str, frozenset[str]],
    all_attrs: frozenset[str],
) -> frozenset[str]:
    """A′ (derive-up): attributes shared by every object in ``extent``.

    Empty extent ⇒ all attributes (the intersection over the empty family is the
    universe M — a vacuously-true set). This is what makes ∅″ the top concept's intent.
    """
    members = [context[o] for o in extent if o in context]
    if not members:
        return all_attrs
    return frozenset.intersection(*members)


def _extent_of(
    intent: frozenset[str],
    context: Mapping[str, frozenset[str]],
) -> frozenset[str]:
    """B′ (derive-down): objects that carry every attribute in ``intent``.

    Empty intent ⇒ all objects (every object trivially has the empty attribute set).
    """
    return frozenset(o for o, attrs in context.items() if intent <= attrs)


def _close_intent(
    intent: frozenset[str],
    context: Mapping[str, frozenset[str]],
    all_attrs: frozenset[str],
) -> frozenset[str]:
    """Intent closure B″ = up(down(B)). Extensive, monotone, IDEMPOTENT."""
    return _intent_of(_extent_of(intent, context), context, all_attrs)


def _closure(
    seeds: frozenset[str],
    context: Mapping[str, frozenset[str]],
) -> tuple[frozenset[str], frozenset[str]]:
    """Compute Galois closure from an OBJECT seed set: (extent → intent → extent).

    Retained for _approx_stability (which reasons over object subsets). The lattice
    enumeration uses the intent-side closure (_close_intent) via NextClosure.
    """
    if not seeds:
        intent = frozenset.intersection(*context.values()) if context else frozenset()
        return frozenset(context.keys()), intent

    intent = frozenset.intersection(*(context[o] for o in seeds if o in context))
    extent = frozenset(o for o, attrs in context.items() if intent <= attrs)
    return extent, intent


# ── Complete concept enumeration — Ganter NextClosure (1984) ─────────────────────


def enumerate_concepts(
    context: Mapping[str, frozenset[str]],
) -> list[tuple[frozenset[str], frozenset[str]]]:
    """Enumerate ALL formal concepts (the complete lattice B(K)) as (extent, intent).

    Ganter's NextClosure: closed intents in lectic order over a fixed linear attribute
    order, each generated exactly once with polynomial delay and O(1) concept memory
    (no visited-set). Includes the top concept (G, ∅″) and bottom (M′, M). This is the
    complete replacement for the old singleton-only γ(g) loop, which missed meet-concepts.

    Reference: B. Ganter, "Two Basic Algorithms in Concept Analysis" (1984).
    """
    all_attrs = _all_attributes(context)
    order = sorted(all_attrs)
    rank = {m: i for i, m in enumerate(order)}
    full = frozenset(order)

    def clo(b: frozenset[str]) -> frozenset[str]:
        return _close_intent(b, context, all_attrs)

    current = clo(frozenset())
    concepts: list[tuple[frozenset[str], frozenset[str]]] = [
        (_extent_of(current, context), current)
    ]

    # NextClosure: scan attributes DESCENDING; drop present ones, and for the first
    # absent m whose candidate closure adds nothing lectically-smaller than m, advance.
    while current != full:
        nxt: frozenset[str] | None = None
        work = set(current)
        for m in reversed(order):
            if m in work:
                work.discard(m)
                continue
            below = frozenset(x for x in work if rank[x] < rank[m])
            candidate = clo(below | {m})
            # acceptance: candidate∖current has no attribute lectically below m
            if not any(rank[y] < rank[m] for y in (candidate - current)):
                nxt = candidate
                break
        if nxt is None:  # pragma: no cover — reachable only if current already == full
            break
        current = nxt
        concepts.append((_extent_of(current, context), current))

    return concepts


# ── Basic-Theorem meet / join (the missing meet-concepts, in closed form) ────────


def concept_meet(
    c1: tuple[frozenset[str], frozenset[str]],
    c2: tuple[frozenset[str], frozenset[str]],
    context: Mapping[str, frozenset[str]],
    all_attrs: frozenset[str] | None = None,
) -> tuple[frozenset[str], frozenset[str]]:
    """Infimum ⋀ = ( A₁∩A₂ , (A₁∩A₂)′ ). The extent-intersection is already closed;
    the intent is derived from it (equivalently (B₁∪B₂)″ — the union of intents is
    NOT closed, so it must be re-closed; that asymmetry is the classic bug)."""
    if all_attrs is None:
        all_attrs = _all_attributes(context)
    ext = c1[0] & c2[0]
    return ext, _intent_of(ext, context, all_attrs)


def concept_join(
    c1: tuple[frozenset[str], frozenset[str]],
    c2: tuple[frozenset[str], frozenset[str]],
    context: Mapping[str, frozenset[str]],
) -> tuple[frozenset[str], frozenset[str]]:
    """Supremum ⋁ = ( (B₁∩B₂)′ , B₁∩B₂ ). Dual of meet: intent-intersection is closed,
    extent is derived (the extent-UNION would NOT be closed — do not return it raw)."""
    intent = c1[1] & c2[1]
    return _extent_of(intent, context), intent


def covering_relation(
    concepts: list[tuple[frozenset[str], frozenset[str]]],
) -> list[tuple[int, int]]:
    """Hasse covering (transitive reduction) as (lower_idx, upper_idx) pairs.

    Concept enumeration ≠ lattice order: covering edges are a SEPARATE pass. This is
    the O(|L|²·|L|) minimal-strict-superset form; for large lattices prefer Lindig
    upper-neighbours / Bordat / Nourine-Raynaud O(|L|·|G|). Edge direction is
    specific(smaller extent) → general(larger extent); the KG binding (:SUBCLASS_OF)
    is longinus's job, not eureka's.
    """
    ext = [c[0] for c in concepts]
    n = len(ext)
    covers: list[tuple[int, int]] = []
    for i in range(n):
        a = ext[i]
        supers = [j for j in range(n) if j != i and a < ext[j]]
        for j in supers:
            cj = ext[j]
            if not any(k != j and ext[k] < cj for k in supers):
                covers.append((i, j))
    return covers


# Exact (deterministic) subset enumeration up to this extent size — 2^12 = 4096 subsets is
# cheap, so concept stability is reproducible + exact below it (above it, sampling with a fixed
# sorted order keeps it deterministic). Raised from 8 to close q-eureka-nondeterminism.
_EXACT_STABILITY_MAX_EXTENT = 12


def _approx_stability(
    extent: frozenset[str],
    context: Mapping[str, frozenset[str]],
    samples: int = 32,
) -> float:
    """Approximate concept stability (Roth-Obiedkov-Kourie 2008 sampling estimator).

    σ(C) = |{D ⊆ extent : closure(D)_intent = intent}| / 2^|extent|.
    Exact computation is exponential; this samples random subsets.
    """
    import random

    if not extent:
        return 0.0
    _, target_intent = _closure(extent, context)
    if not target_intent:
        return 1.0 if not extent else 0.0

    # sorted (not list(frozenset)) → deterministic, hash-seed-independent order: the residual
    # sampling path below is now reproducible across processes (was the lone non-determinism).
    ext_list = sorted(extent)
    n = len(ext_list)
    if n <= _EXACT_STABILITY_MAX_EXTENT:
        total = 2**n
        stable_count = 0
        for mask in range(total):
            subset = frozenset(ext_list[i] for i in range(n) if (mask >> i) & 1)
            _, sub_intent = _closure(subset, context)
            if sub_intent == target_intent:
                stable_count += 1
        return stable_count / total

    rng = random.Random(0)
    stable_count = 0
    for _ in range(samples):
        subset = frozenset(o for o in ext_list if rng.random() < 0.5)
        _, sub_intent = _closure(subset, context)
        if sub_intent == target_intent:
            stable_count += 1
    return stable_count / samples


def induce_fca(
    context: Mapping[str, frozenset[str]],
    min_extent: int = 2,
    min_stability: float = 0.5,
) -> FcaResult:
    # KG: eureka-canonical-2026-05-26
    """Induce formal concepts from a binary context {object → attribute set}.

    Enumerates the COMPLETE concept lattice (NextClosure — includes meet-concepts),
    then applies OUTPUT filters: extent ≥ min_extent (support, anti-monotone/safe),
    non-trivial intent (drops the top concept when nothing is shared), and stability
    ≥ min_stability (post-hoc quality filter — never used to prune enumeration).
    Falls back early if batch exceeds MAX_BATCH or the lattice exceeds MAX_CONCEPTS.
    """
    if len(context) > MAX_BATCH:
        return FcaResult(
            concepts=(),
            pruned=0,
            fallback_reason=(
                f"context size {len(context)} > MAX_BATCH {MAX_BATCH}; "
                "use AMIE3 or Leiden-LLM operator instead"
            ),
        )
    if not context:
        return FcaResult(concepts=(), pruned=0, fallback_reason=None)

    all_concepts = enumerate_concepts(context)
    if len(all_concepts) > MAX_CONCEPTS:
        return FcaResult(
            concepts=(),
            pruned=0,
            fallback_reason=(
                f"lattice size {len(all_concepts)} > MAX_CONCEPTS {MAX_CONCEPTS} "
                "(dense/degenerate context); use AMIE3 or Leiden-LLM operator instead"
            ),
        )

    survivors: list[FormalConcept] = []
    pruned = 0
    for extent, intent in all_concepts:
        if len(extent) < min_extent or not intent:
            pruned += 1
            continue
        stability = _approx_stability(extent, context)
        if stability < min_stability:
            pruned += 1
            continue
        survivors.append(FormalConcept(extent=extent, intent=intent, stability=stability))

    survivors.sort(key=lambda c: (-c.stability, -len(c.extent)))
    return FcaResult(concepts=tuple(survivors), pruned=pruned, fallback_reason=None)


__all__ = [
    "FcaResult",
    "FormalConcept",
    "MAX_BATCH",
    "MAX_CONCEPTS",
    "concept_join",
    "concept_meet",
    "covering_relation",
    "enumerate_concepts",
    "induce_fca",
]
