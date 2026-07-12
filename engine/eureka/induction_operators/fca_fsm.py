"""Induction FSM for FCA concept-lattice building.

Makes eureka's concept induction an explicit, inspectable state machine with a
discovery RE-ENTRY edge — the design from prom16-eureka-fca-fsm (THEORY/
eureka_fca_lattice/PROM_16_FCA_FSM_REPORT.md §4).

The batch enumeration itself is Ganter NextClosure in fca.py (enumerate_concepts);
this module wires it as a pipeline of named states and exposes the discovery re-entry
(add_object / add_attribute) that corresponds to the science-feedback-loop
discovery → PH2 re-entry. Per the research the correct control structure is a plain
enum-driven pipeline (NOT a statechart library): the heavy lifting is the recursive
closure enumeration, and the state machine only sequences it + handles re-entry.

States (report §4):
  SEED → ATTR_SCAN → CLOSE → (canonicity) → EMIT → MEET_EXTRACT → LATTICE_BUILD → DONE
  discovery: REENTRY re-seeds with the augmented context.

Re-entry cost note: add_object/add_attribute recompute the lattice on the augmented
context (correct, and cheap at eureka's bounded scale ≤ MAX_BATCH). AddIntent (van der
Merwe 2004) O(|L|·|G|²) in-place update is the documented optimization for
high-frequency streaming — deferred; the re-entry SEAM is here so it can be swapped in
without changing callers.
# KG: eureka-canonical-2026-05-26, lesson-eureka-fca-incompleteness-singleton-closures-2026-07-12
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping

from engine.eureka.induction_operators.fca import (
    FormalConcept,
    _approx_stability,
    covering_relation,
    enumerate_concepts,
)


class InductionState(str, Enum):
    """Explicit states of the induction pipeline (report §4)."""

    SEED = "seed"
    ATTR_SCAN = "attr_scan"
    EMIT = "emit"
    MEET_EXTRACT = "meet_extract"
    LATTICE_BUILD = "lattice_build"
    DONE = "done"
    REENTRY = "reentry"


@dataclass(frozen=True)
class ConceptLattice:
    """A complete concept lattice: concepts + Hasse covering + the FSM trace.

    covers holds (lower_idx, upper_idx) pairs indexing into ``concepts``; the edge is
    directed specific(smaller extent) → general(larger extent). Binding these to the KG
    as :SUBCLASS_OF is longinus's job (eureka emits nodes; longinus binds edges).
    """

    concepts: tuple[FormalConcept, ...]
    covers: tuple[tuple[int, int], ...]
    trace: tuple[InductionState, ...]


@dataclass
class InductionFSM:
    """Explicit FCA induction state machine over a growing formal context.

    Usage:
        fsm = InductionFSM(context)
        lattice = fsm.build()                    # batch
        lattice = fsm.add_object("g9", {"a"})    # discovery re-entry
    """

    context: dict[str, frozenset[str]] = field(default_factory=dict)
    _trace: list[InductionState] = field(default_factory=list, repr=False)

    def __post_init__(self) -> None:
        # normalise attribute sets to frozenset without mutating the caller's mapping
        self.context = {o: frozenset(a) for o, a in self.context.items()}

    # ── batch build (SEED → … → LATTICE_BUILD) ──────────────────────────────────
    def build(self) -> ConceptLattice:
        """Run the full induction pipeline once and return the complete lattice."""
        self._trace = [InductionState.SEED, InductionState.ATTR_SCAN]
        raw = enumerate_concepts(self.context)  # ATTR_SCAN→CLOSE→canonicity→EMIT (NextClosure)
        self._trace.append(InductionState.EMIT)
        # MEET_EXTRACT: NextClosure already yields the complete set incl. meet-concepts;
        # this state is where per-concept stability + naming callbacks would attach.
        self._trace.append(InductionState.MEET_EXTRACT)
        concepts = tuple(
            FormalConcept(extent=e, intent=i, stability=_approx_stability(e, self.context))
            for (e, i) in raw
        )
        covers = tuple(covering_relation([(c.extent, c.intent) for c in concepts]))
        self._trace.append(InductionState.LATTICE_BUILD)
        self._trace.append(InductionState.DONE)
        return ConceptLattice(concepts=concepts, covers=covers, trace=tuple(self._trace))

    # ── discovery re-entry (REENTRY → SEED …) ───────────────────────────────────
    def add_object(self, obj: str, attrs: frozenset[str] | set[str]) -> ConceptLattice:
        """Discovery re-entry: a new object streams in → augment context and resume.

        Corresponds to the science-feedback-loop discovery → PH2 re-entry: the induction
        does not restart from scratch conceptually — it resumes with the grown context.
        (Implementation recomputes; see module docstring for the AddIntent optimization.)
        """
        self.context = {**self.context, obj: frozenset(attrs)}
        lattice = self.build()
        return ConceptLattice(
            concepts=lattice.concepts,
            covers=lattice.covers,
            trace=(InductionState.REENTRY, *lattice.trace),
        )

    def add_attribute(self, obj_attrs: Mapping[str, frozenset[str] | set[str]]) -> ConceptLattice:
        """Discovery re-entry via new attributes on existing (or new) objects."""
        grown = dict(self.context)
        for obj, attrs in obj_attrs.items():
            grown[obj] = grown.get(obj, frozenset()) | frozenset(attrs)
        self.context = grown
        lattice = self.build()
        return ConceptLattice(
            concepts=lattice.concepts,
            covers=lattice.covers,
            trace=(InductionState.REENTRY, *lattice.trace),
        )


__all__ = ["ConceptLattice", "InductionFSM", "InductionState"]
