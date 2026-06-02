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
# KG: eureka-canonical-2026-05-26 (colimit_subsumption_2026_05_29), consensus-eureka-academic-grounding-2026-05-26

Constraint per seed-prom16lag-conflict-fca-dense-avoid-vs-sparse-rec-2026-05-20:
- Use only when formal context is binary or conceptually-scaled
- Bound |concepts| via iceberg-lattice (Roth-Obiedkov-Kourie 2008) or stability pruning
- Batch size ≤ 500 nodes. Above threshold → fall back to AMIE+ or Leiden.
"""
# KG: eureka-canonical-2026-05-26

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


MAX_BATCH = 500


@dataclass(frozen=True)
class FormalConcept:
    extent: frozenset[str]
    intent: frozenset[str]
    stability: float


@dataclass(frozen=True)
class FcaResult:
    concepts: tuple[FormalConcept, ...]
    pruned: int
    fallback_reason: str | None


def _closure(
    seeds: frozenset[str],
    context: Mapping[str, frozenset[str]],
) -> tuple[frozenset[str], frozenset[str]]:
    """Compute Galois closure: (extent → intent → extent)."""
    if not seeds:
        intent = frozenset.intersection(*context.values()) if context else frozenset()
        return frozenset(context.keys()), intent

    intent = frozenset.intersection(*(context[o] for o in seeds if o in context))
    extent = frozenset(o for o, attrs in context.items() if intent <= attrs)
    return extent, intent


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

    ext_list = list(extent)
    n = len(ext_list)
    if n <= 8:
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
    """Induce formal concepts from a binary context {object → attribute set}.

    Returns concepts with extent ≥ min_extent AND stability ≥ min_stability.
    Falls back early if batch exceeds MAX_BATCH.
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

    seen: set[tuple[frozenset[str], frozenset[str]]] = set()
    survivors: list[FormalConcept] = []
    pruned = 0

    objects = list(context.keys())
    for obj in objects:
        extent, intent = _closure(frozenset({obj}), context)
        key = (extent, intent)
        if key in seen:
            continue
        seen.add(key)
        if len(extent) < min_extent:
            pruned += 1
            continue
        stability = _approx_stability(extent, context)
        if stability < min_stability:
            pruned += 1
            continue
        survivors.append(FormalConcept(extent=extent, intent=intent, stability=stability))

    survivors.sort(key=lambda c: (-c.stability, -len(c.extent)))
    return FcaResult(concepts=tuple(survivors), pruned=pruned, fallback_reason=None)


__all__ = ["FcaResult", "FormalConcept", "MAX_BATCH", "induce_fca"]
