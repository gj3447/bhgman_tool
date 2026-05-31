from engine.eureka.induction_operators.fca import MAX_BATCH, induce_fca


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
