"""Tests — Hades materialize sink (in-memory emerged graph -> Neo4j MERGE via injected run_cypher).

Offline: a fake runner captures the cypher so we assert the writes without a live KG.

# KG: engineboy-emergence-engine-fsm-design-2026-07-13, hades-canonical-2026-05-27
"""
from __future__ import annotations

import pytest

from engine.emergence import EmergenceEngine
from engine.emergence.hades_sink import Neo4jHadesSink
from engine.emergence.protocols import AccessEvent, ActivityState, Element


class FakeRunner:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def __call__(self, cypher: str, params: dict) -> list[dict]:
        self.calls.append((cypher, params))
        return []


def _co_access(eng: EmergenceEngine, a: str, b: str, n: int, start: float = 0.0) -> None:
    for i in range(n):
        eng.ingest(
            AccessEvent(event_id=f"{a}-{b}-{i}", element_key=a, actor="human",
                        ts=start + i, co_keys=(b,))
        )


def test_streaming_sink_merges_published_nodes() -> None:
    run = FakeRunner()
    sink = Neo4jHadesSink(run)
    eng = EmergenceEngine(sink=sink)
    _co_access(eng, "A", "B", n=3)

    assert sink.nodes_written > 0
    assert all("MERGE (n:EmergedElement {name: $key})" in c for c, _ in run.calls)
    assert all("n.emerged = true" in c for c, _ in run.calls)


def test_private_namespace_not_materialized() -> None:
    run = FakeRunner()
    sink = Neo4jHadesSink(run)
    sink(None, Element(key="secret", w=1.0, n=1, state=ActivityState.WARM, namespace="tenant:alice"))

    assert sink.nodes_written == 0
    assert sink.skipped_private == 1
    assert run.calls == []


def test_embedding_set_when_embed_fn_given() -> None:
    run = FakeRunner()
    sink = Neo4jHadesSink(run, embed_fn=lambda key: [0.1, 0.2, 0.3])
    sink(None, Element(key="A", w=2.0, n=4, state=ActivityState.HOT, namespace="shared"))

    assert sink.embeddings_set == 1
    cypher, params = run.calls[0]
    assert "n.embedding = $embed" in cypher
    assert params["embed"] == [0.1, 0.2, 0.3]
    assert params["tier"] == "L1"  # HOT -> L1


def test_flush_materializes_nodes_and_edges() -> None:
    run = FakeRunner()
    sink = Neo4jHadesSink(run)
    eng = EmergenceEngine()  # no streaming sink — persist the whole topology at the end
    # accessing BOTH directions makes A and B real nodes (co_keys alone only create edge endpoints,
    # which the edge MERGE still creates in Neo4j but does not count as a node write).
    _co_access(eng, "A", "B", n=4)
    _co_access(eng, "B", "A", n=2)

    stats = sink.flush(eng)
    assert stats["nodes_written"] >= 2   # A and B both accessed
    assert stats["edges_written"] >= 1   # the emerged Hebbian edge
    assert any("CO_ACTIVATES" in c for c, _ in run.calls)
    assert any("MERGE (a:EmergedElement {name: $src})" in c for c, _ in run.calls)


def test_rejects_unsafe_identifier() -> None:
    with pytest.raises(ValueError):
        Neo4jHadesSink(FakeRunner(), label="Bad-Label; DROP")
