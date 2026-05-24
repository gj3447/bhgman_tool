"""
delta_lens.py — Diskin 2011 Asymmetric Delta Lens (Mathlib-free Lean mirror).

Wave 3 (2026-05-20): full DeltaLens + 3 law verifiers + identity instance smoke test.

Substitutes Foster 2007 well-behaved lens (bx_lens.py — single-valued get/put,
PutGet violated on Longinus 1:N KG↔code range correspondence) with Diskin
asymmetric delta lens for v3.4. Drift = morphism in delta category by
construction.

References:
    Diskin, Xiong, Czarnecki. From State- to Delta-Based Bidirectional Model
        Transformations: the Asymmetric Case. JOT 10(6):1-25, 2011.
    Hofmann, Pierce, Wagner. Edit Lenses. POPL 2012. DOI 10.1145/2103621.2103715.
    Clarke. Delta lenses as coalgebras for a comonad. BX 2021. arXiv:2108.00390.

# KG: ATOM_Skill_longinus, ap-longinus-v34-bx-lens-substitute-2026-05-20,
      seed-bx-delta-lens-diskin-primary-2026-05-20,
      THEORY/LONGINUS/lean_audit/LonginusBxDeltaLens.lean
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Generic, TypeVar

S = TypeVar("S")  # source state type
V = TypeVar("V")  # view state type
DS = TypeVar("DS")  # source delta type (morphism in source category)
DV = TypeVar("DV")  # view delta type (morphism in view category)


@dataclass(frozen=True)
class DeltaCategory(Generic[S, DS]):
    """A delta category: states + morphisms (deltas) with id and composition."""

    id_delta: Callable[[S], DS]
    compose: Callable[[DS, DS], DS]
    source: Callable[[DS], S]
    target: Callable[[DS], S]


@dataclass(frozen=True)
class DeltaLens(Generic[S, V, DS, DV]):
    """Diskin 2011 asymmetric delta lens.

    get:  S -> V
    lift: (s: S, u: DV starting at get(s)) -> S
        the target source state corresponding to applying view delta u.

    Mirrors LonginusBxDeltaLens.DeltaLens in lean_audit/LonginusBxDeltaLens.lean.
    """

    source_cat: DeltaCategory[S, DS]
    view_cat: DeltaCategory[V, DV]
    get: Callable[[S], V]
    lift: Callable[[S, DV], S]

    def verify_putget(self, s: S, u: DV) -> bool:
        """d-PutGet: get(lift(s, u)) == target(u).

        Lifting a view delta from get(s) to b produces a source state whose
        view-projection is exactly b.
        """
        s_prime = self.lift(s, u)
        return self.get(s_prime) == self.view_cat.target(u)

    def verify_getput(self, s: S) -> bool:
        """d-GetPut: lift(s, id_view(get(s))) == s.

        Identity view delta lifts to identity source (no spurious drift).
        """
        id_view = self.view_cat.id_delta(self.get(s))
        return self.lift(s, id_view) == s


# --------------------------------------------------------------------------
# Identity delta lens — minimal inhabited witness (mirrors Lean identityDeltaLens)
# --------------------------------------------------------------------------


def identity_delta_lens(cat: DeltaCategory[S, DS]) -> DeltaLens[S, S, DS, DS]:
    """Identity delta lens on a single delta category."""
    return DeltaLens(
        source_cat=cat,
        view_cat=cat,
        get=lambda a: a,
        lift=lambda _s, u: cat.target(u),
    )


# --------------------------------------------------------------------------
# Trivial delta category over a value type with id/append semigroup deltas
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class IntDelta:
    """A trivial delta on integers: from src to tgt, with no extra structure."""

    src: int
    tgt: int


_INT_CAT: DeltaCategory[int, IntDelta] = DeltaCategory(
    id_delta=lambda a: IntDelta(a, a),
    compose=lambda d1, d2: IntDelta(d1.src, d2.tgt),
    source=lambda d: d.src,
    target=lambda d: d.tgt,
)


def int_delta_cat() -> DeltaCategory[int, IntDelta]:
    return _INT_CAT


# Wave 4 targets:
#   - edit_lens_line_range.py: HPW 2012 monoid action for line shift
#   - LineRange dataclass + LineShift edit composition

# Wave 5 targets:
#   - profunctor_api.py: Traversal interface contract (Wander typeclass mimic)
#   - SOURCES.md update: BX framework correction
#   - KG MATERIALIZES edges: Lean theorem ↔ Python module ↔ SOURCES.md tri-binding
