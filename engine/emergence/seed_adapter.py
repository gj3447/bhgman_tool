"""Production SeedFn adapter — embedding kNN behind two_stage_retrieve's injected seed seam.

`activation.two_stage_retrieve` takes a `SeedFn` (query text -> {node_key: score}); this composes
the real embedding stage with the Neo4j native-HNSW `knn` behind it:

    query --embed_fn--> vector --knn(shared index)--> {node_id: similarity}

Both heavy dependencies stay INJECTED (`embed_fn`, `run_cypher`) so the composition is pure and
offline-testable — the same discipline activation.py already follows by injecting `seed_fn`.

Live effect is gated on OD-5 (embedding populate): if `embed_fn` returns None (embedder
unavailable) or the index is empty, the SeedFn yields {} and `two_stage_retrieve` returns []
— an honest empty result, never a crash.

Pure-python (stdlib only).

# KG: finding-prom16-hipporag2-embedding-populate-gap-2026-07-13,
#     engineboy-emergence-engine-fsm-design-2026-07-13, reference_neo4j_gds_vector_available
"""
from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence

from engine.emergence.activation import SeedFn

Vector = Sequence[float]
# text -> embedding, or None when the embedder is unavailable (OD-5 not yet populated).
EmbedFn = Callable[[str], "Vector | None"]


def embedding_seed_fn(
    embed_fn: EmbedFn,
    run_cypher,
    spec,
    *,
    k_seed: int = 5,
    min_score: float = 0.0,
) -> SeedFn:
    """Build a `SeedFn`: query -> {node_id: similarity} via `embed_fn` + Neo4j HNSW `knn`.

    Queries only the shared index (`spec`), so private/tenant nodes are never proposed as seeds
    (Visibility D3, mirrored from Neo4jVectorResolver). Returns {} when the embedder yields None
    or the index has no hits, so `two_stage_retrieve` degrades to [] instead of failing.
    """
    from engine.embedding.neo4j_vector import knn

    def seed(query: str) -> Mapping[str, float]:
        vec = embed_fn(query)
        if vec is None:
            return {}
        hits = knn(
            run_cypher,
            spec,
            list(vec),
            k=k_seed,
            key_prop=spec.text_prop,
            min_score=min_score,
        )
        return {h.node_id: h.score for h in hits}

    return seed


__all__ = ["EmbedFn", "embedding_seed_fn"]
