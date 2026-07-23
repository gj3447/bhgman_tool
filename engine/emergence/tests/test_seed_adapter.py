"""Tests — production SeedFn adapter (embed_fn + Neo4j knn -> two_stage_retrieve SeedFn).

Offline: fake embedder + fake cypher runner prove the composition without live embeddings.

# KG: finding-prom16-hipporag2-embedding-populate-gap-2026-07-13,
#     engineboy-emergence-engine-fsm-design-2026-07-13
"""
from __future__ import annotations

from engine.embedding.neo4j_vector import VectorIndexSpec
from engine.emergence import EmergenceEngine
from engine.emergence.activation import two_stage_retrieve
from engine.emergence.protocols import AccessEvent
from engine.emergence.seed_adapter import embedding_seed_fn

SPEC = VectorIndexSpec(index_name="emerged_idx", label="EmergedElement")


def _co_access(eng: EmergenceEngine, a: str, b: str, n: int, start: float = 0.0) -> None:
    for i in range(n):
        eng.ingest(
            AccessEvent(event_id=f"{a}-{b}-{i}", element_key=a, actor="human",
                        ts=start + i, co_keys=(b,))
        )


def test_seed_fn_maps_query_to_knn_hits() -> None:
    calls: list[tuple[str, dict]] = []

    def fake_run(cypher: str, params: dict) -> list[dict]:
        calls.append((cypher, params))
        return [{"id": "A", "score": 0.92, "text": "A"}, {"id": "C", "score": 0.61, "text": "C"}]

    seed = embedding_seed_fn(lambda q: [0.1, 0.2, 0.3], fake_run, SPEC, k_seed=5)
    got = seed("some query")

    assert got == {"A": 0.92, "C": 0.61}
    assert calls and "db.index.vector.queryNodes" in calls[0][0]   # it really went through knn
    assert calls[0][1]["vec"] == [0.1, 0.2, 0.3]                   # the embedding is the query vector


def test_seed_fn_empty_when_embedder_unavailable() -> None:
    # OD-5 gate: embed_fn -> None yields {} without touching the KG (no crash).
    touched: list[int] = []
    seed = embedding_seed_fn(lambda q: None, lambda c, p: touched.append(1) or [], SPEC)
    assert seed("q") == {}
    assert touched == []


def test_seed_fn_empty_when_index_unpopulated() -> None:
    # OD-5 gate: knn returns [] on an empty index -> {}.
    seed = embedding_seed_fn(lambda q: [0.0, 0.0], lambda c, p: [], SPEC)
    assert seed("q") == {}


def test_two_stage_retrieve_with_embedding_seed_fn() -> None:
    # end-to-end: the adapter seeds A, PPR spreads over the emerged edge to traffic-neighbour B.
    eng = EmergenceEngine()
    _co_access(eng, "A", "B", n=5)
    seed = embedding_seed_fn(
        lambda q: [1.0, 0.0],
        lambda c, p: [{"id": "A", "score": 0.9, "text": "A"}],
        SPEC,
    )
    out = two_stage_retrieve(eng, "query", seed, t=6.0, k_seed=1, top_k=10)
    keys = [a.node_key for a in out]
    assert "A" in keys and "B" in keys
