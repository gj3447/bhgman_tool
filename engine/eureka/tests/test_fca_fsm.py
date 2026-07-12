"""Tests for the FCA induction FSM (explicit states + discovery re-entry)."""

from engine.eureka.induction_operators.fca import enumerate_concepts
from engine.eureka.induction_operators.fca_fsm import InductionFSM, InductionState


def _ctx() -> dict[str, frozenset[str]]:
    return {
        "1": frozenset({"a", "b"}),
        "2": frozenset({"a", "c"}),
        "3": frozenset({"a", "b", "c"}),
    }


def test_build_matches_enumerate_concepts():
    ctx = _ctx()
    lat = InductionFSM(ctx).build()
    got = {(c.extent, c.intent) for c in lat.concepts}
    assert got == set(enumerate_concepts(ctx))
    assert len(lat.concepts) == len(got)  # each concept once


def test_trace_states_in_order():
    lat = InductionFSM(_ctx()).build()
    assert lat.trace == (
        InductionState.SEED,
        InductionState.ATTR_SCAN,
        InductionState.EMIT,
        InductionState.MEET_EXTRACT,
        InductionState.LATTICE_BUILD,
        InductionState.DONE,
    )


def test_covers_direction_specific_to_general():
    lat = InductionFSM(_ctx()).build()
    assert lat.covers  # diamond+ lattice has covering edges
    for lo, hi in lat.covers:
        assert lat.concepts[lo].extent < lat.concepts[hi].extent


def test_add_object_reentry_equals_fresh_build():
    fsm = InductionFSM({"1": frozenset({"a", "b"}), "2": frozenset({"a", "c"})})
    fsm.build()
    reentry = fsm.add_object("3", {"a", "b", "c"})
    fresh = InductionFSM(_ctx()).build()
    assert {(c.extent, c.intent) for c in reentry.concepts} == {
        (c.extent, c.intent) for c in fresh.concepts
    }
    assert reentry.trace[0] == InductionState.REENTRY


def test_add_attribute_reentry_grows_context():
    fsm = InductionFSM({"1": frozenset({"a"}), "2": frozenset({"a"})})
    lat = fsm.add_attribute({"1": {"b"}})
    assert fsm.context["1"] == frozenset({"a", "b"})
    assert lat.trace[0] == InductionState.REENTRY
    fresh = InductionFSM({"1": frozenset({"a", "b"}), "2": frozenset({"a"})}).build()
    assert {(c.extent, c.intent) for c in lat.concepts} == {
        (c.extent, c.intent) for c in fresh.concepts
    }


def test_reentry_recovers_concept_absent_before():
    """Before object 3 arrives, ({1,3},{a,b}) cannot exist; after re-entry it does."""
    fsm = InductionFSM({"1": frozenset({"a", "b"}), "2": frozenset({"a", "c"})})
    before = {c.extent for c in fsm.build().concepts}
    assert frozenset({"1", "3"}) not in before
    lat = fsm.add_object("3", {"a", "b", "c"})
    by_extent = {c.extent: c.intent for c in lat.concepts}
    assert by_extent.get(frozenset({"1", "3"})) == frozenset({"a", "b"})


def test_caller_mapping_not_mutated():
    original = {"1": {"a", "b"}}
    fsm = InductionFSM(original)  # type: ignore[arg-type]
    fsm.add_object("2", {"a"})
    assert original == {"1": {"a", "b"}}  # caller's dict untouched
