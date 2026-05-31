"""
profunctor_api.py — Profunctor optic interface contract (Wave 5).

Surface-layer API pattern for Longinus v3.4 BX lens stack. Following the
Pickering-Gibbons-Wu 2017 / Boisseau-Gibbons 2018 profunctor optic encoding
(Wander typeclass = native 1:N Traversal), this module exposes Python
Protocol types as *interface contracts* — not a runtime profunctor optic
engine (which would require rank-2 polymorphism Python lacks natively).

The actual data-flow engine is `delta_lens.py` (Diskin 2011) +
`edit_lens_line_range.py` (HPW 2012). This module gives downstream callers
a uniform, composable type signature for Lens / Traversal use cases.

References:
    Pickering, Gibbons, Wu. Profunctor Optics: Modular Data Accessors.
        Programming Journal 2017.
    Boisseau, Gibbons. What You Needa Know about Yoneda. ICFP 2018.

# KG: ATOM_Skill_longinus, ap-longinus-v34-bx-lens-substitute-2026-05-20,
      seed-bx-profunctor-traversal-api-2026-05-20,
      THEORY/LONGINUS/lean_audit/LonginusBxDeltaLens.lean
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Callable, Generic, Protocol, TypeVar, runtime_checkable

# Variance per profunctor optics: source consumed (contravariant), target produced
# (covariant), focus read out (covariant), focus written in (contravariant).
S = TypeVar("S", contravariant=True)  # source type
T = TypeVar("T", covariant=True)  # target type (post-update)
A = TypeVar("A", covariant=True)  # focused-element type
B = TypeVar("B", contravariant=True)  # focused-element after update


@runtime_checkable
class LensProto(Protocol, Generic[S, T, A, B]):
    """Lens interface contract — single-focus get/put (Foster style, 1:1).

    `view` extracts the focus; `update` writes back with the new value.
    Provided for backwards-compatibility with bx_lens.py callers; *new*
    Longinus v3.4 code should prefer TraversalProto (1:N) or DeltaLens.
    """

    def view(self, s: S) -> A: ...

    def update(self, s: S, b: B) -> T: ...


@runtime_checkable
class TraversalProto(Protocol, Generic[S, T, A, B]):
    """Traversal interface contract — natively handles 1:N (multiple foci).

    `modify_each` applies a transformation `f: A -> B` to every focus inside
    `s` and returns the rebuilt `t: T`. Profunctor `Wander` typeclass instance
    in Haskell; here exposed as a Protocol contract.
    """

    def modify_each(self, s: S, f: Callable[[A], B]) -> T: ...

    def to_list(self, s: S) -> Sequence[A]:
        """Collect all foci into a list (1:N flattening)."""
        ...
