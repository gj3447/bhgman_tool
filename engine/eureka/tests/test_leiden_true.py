"""True-Leiden operator ([eureka-leiden] optional extra) — genuine Traag 2019 Leiden."""

from __future__ import annotations

import pytest

pytest.importorskip("leidenalg")
pytest.importorskip("igraph")

from engine.eureka.induction_operators.leiden_llm import induce_leiden_llm  # noqa: E402
from engine.eureka.induction_operators.leiden_true import induce_leiden_true  # noqa: E402

# Two clear clusters by shared attributes: {a,b,c} share {p,q}; {d,e} share {r,s}.
_CTX = {
    "a": frozenset({"p", "q"}),
    "b": frozenset({"p", "q"}),
    "c": frozenset({"p", "q"}),
    "d": frozenset({"r", "s"}),
    "e": frozenset({"r", "s"}),
}


def test_true_leiden_recovers_clusters():
    res = induce_leiden_true(_CTX, min_extent=2)
    extents = sorted(sorted(c.extent) for c in res.concepts)
    assert ["a", "b", "c"] in extents
    assert ["d", "e"] in extents


def test_true_leiden_deterministic_with_seed():
    a = induce_leiden_true(_CTX, seed=42)
    b = induce_leiden_true(_CTX, seed=42)
    assert [sorted(c.extent) for c in a.concepts] == [sorted(c.extent) for c in b.concepts]


def test_same_output_shape_as_cnm():
    # drop-in: same FcaResult type + FormalConcept fields as the no-dep CNM operator
    t = induce_leiden_true(_CTX, min_extent=2)
    c = induce_leiden_llm(_CTX, min_extent=2)
    assert type(t) is type(c)
    assert {f for con in t.concepts for f in con.intent}  # intents populated
    for con in t.concepts:
        assert 0.0 <= con.stability <= 1.0


def test_large_context_delegates():
    big = {str(i): frozenset({"x"}) for i in range(3)}
    res = induce_leiden_true(big, max_nodes=2)
    assert res.fallback_reason is not None and "gds.leiden" in res.fallback_reason
