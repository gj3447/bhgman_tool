from engine.eureka.induction_operators.fca import (
    MAX_BATCH,
    _all_attributes,
    _close_intent,
    concept_join,
    concept_meet,
    covering_relation,
    enumerate_concepts,
    induce_fca,
)


def test_simple_context_produces_concept():
    context = {
        "obj_a": frozenset({"attr_x", "attr_y"}),
        "obj_b": frozenset({"attr_x", "attr_y"}),
        "obj_c": frozenset({"attr_x"}),
    }
    result = induce_fca(context, min_extent=2, min_stability=0.0)
    assert result.fallback_reason is None
    assert len(result.concepts) >= 1
    top = result.concepts[0]
    assert "attr_x" in top.intent


def test_singleton_extent_pruned():
    context = {
        "a": frozenset({"x"}),
        "b": frozenset({"y"}),
        "c": frozenset({"z"}),
    }
    result = induce_fca(context, min_extent=2, min_stability=0.0)
    assert result.concepts == ()
    assert result.pruned >= 1


def test_oversize_context_falls_back():
    context = {f"obj_{i}": frozenset({"x"}) for i in range(MAX_BATCH + 1)}
    result = induce_fca(context)
    assert result.fallback_reason is not None
    assert "AMIE3" in result.fallback_reason or "Leiden" in result.fallback_reason


def test_empty_context():
    result = induce_fca({})
    assert result.concepts == ()
    assert result.fallback_reason is None


# ── completeness fix (prom16-eureka-fca-fsm-2026-07-12): meet-concepts recovered ──


def test_meet_concept_recovered_not_just_singletons():
    """The regression: ({1,2},{a}) is a MEET of the two object concepts — extent 2, but
    NOT any single {g}″ (those have extent 1). The old singleton-only loop returned () at
    min_extent=2; complete enumeration (NextClosure) recovers the meet-concept."""
    context = {"1": frozenset({"a", "b"}), "2": frozenset({"a", "c"})}
    result = induce_fca(context, min_extent=2, min_stability=0.0)
    assert len(result.concepts) == 1
    c = result.concepts[0]
    assert c.extent == frozenset({"1", "2"})
    assert c.intent == frozenset({"a"})


def test_enumerate_concepts_complete_lattice():
    """Full lattice B(K), each closed concept exactly once (oracle count)."""
    context = {"1": frozenset({"a", "b"}), "2": frozenset({"a", "c"})}
    concepts = enumerate_concepts(context)
    intents = {c[1] for c in concepts}
    # diamond: TOP({1,2},{a}) / ({1},{a,b}) / ({2},{a,c}) / BOTTOM(∅,{a,b,c})
    assert len(concepts) == 4
    assert intents == {
        frozenset({"a"}),
        frozenset({"a", "b"}),
        frozenset({"a", "c"}),
        frozenset({"a", "b", "c"}),
    }
    assert len(intents) == len(concepts)  # each unique (no duplicate generation)


def test_closure_is_idempotent_and_extensive():
    context = {
        "1": frozenset({"a", "b"}),
        "2": frozenset({"a", "c"}),
        "3": frozenset({"b"}),
    }
    allattr = _all_attributes(context)
    for seed in (
        frozenset(),
        frozenset({"a"}),
        frozenset({"b"}),
        frozenset({"a", "b"}),
        allattr,
    ):
        once = _close_intent(seed, context, allattr)
        assert _close_intent(once, context, allattr) == once  # idempotent
        assert seed <= once  # extensive


def test_meet_intent_is_reclosed_not_raw_union():
    """The asymmetry trap: meet-intent must be re-closed with ″, it is NOT the raw
    union of the two intents. Here up(A₁∩A₂)={a,b,c} but B₁∪B₂={a,b}."""
    context = {
        "1": frozenset({"a", "b", "c"}),
        "2": frozenset({"a", "b", "c"}),
        "3": frozenset({"a"}),
        "4": frozenset({"b"}),
    }
    c1 = (frozenset({"1", "2", "3"}), frozenset({"a"}))
    c2 = (frozenset({"1", "2", "4"}), frozenset({"b"}))
    me, mi = concept_meet(c1, c2, context)
    assert me == frozenset({"1", "2"})
    assert mi == frozenset({"a", "b", "c"})
    assert mi != (c1[1] | c2[1])  # raw union {a,b} would be WRONG (non-concept)


def test_join_extent_is_derived_not_raw_union():
    context = {"1": frozenset({"a", "b"}), "2": frozenset({"a", "c"})}
    c1 = (frozenset({"1"}), frozenset({"a", "b"}))
    c2 = (frozenset({"2"}), frozenset({"a", "c"}))
    je, ji = concept_join(c1, c2, context)
    assert ji == frozenset({"a"})  # intent-intersection (already closed)
    assert je == frozenset({"1", "2"})  # down({a}), NOT the raw extent union


def test_covering_relation_diamond():
    context = {"1": frozenset({"a", "b"}), "2": frozenset({"a", "c"})}
    concepts = enumerate_concepts(context)
    covers = covering_relation(concepts)
    assert len(covers) == 4  # diamond: 2 up from bottom, 2 up to top
    for lo, hi in covers:
        assert concepts[lo][0] < concepts[hi][0]  # extent strictly grows upward
