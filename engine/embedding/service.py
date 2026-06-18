"""EmbeddingService — one object every commander calls for semantic ops.

Ties the existing ``memory.Embedder`` (sentence-transformers, hash fallback) to the
Neo4j native vector index (``neo4j_vector``). When no ``CypherRunner`` is supplied it
degrades to the in-memory ``memory.VectorStore`` so engines stay runnable at infra-0
(the --local / no-KG path), matching legion's "infra 0 still works" covenant.

The embedding *dimension* is read from the live embedder rather than hard-coded, so a
384-d MiniLM and a 768-d mpnet both produce a correctly-sized index. The Neo4j index
dim is whatever the embedder actually emits — no silent 384/768 mismatch.

# KG: bihaenggiman-legioncommanders-2026-05-26, project-legion-unification-kg-engine-2026-06-01,
#     reference_neo4j_gds_vector_available
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

from engine.embedding.neo4j_vector import (
    BackfillReport,
    CypherRunner,
    Neighbor,
    VectorIndexSpec,
    backfill_embeddings,
    ensure_vector_index,
    knn,
    knn_pairs,
)


class _Encoder:
    """Minimal protocol the service needs: text(s) → vector(s)."""

    def encode(self, text: str) -> list[float]: ...  # pragma: no cover


def _l2_normalize(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vec))
    return [x / norm for x in vec] if norm else list(vec)


def _default_encoder() -> _Encoder:
    from engine.memory.embedder import Embedder  # noqa: PLC0415 — optional heavy import

    return Embedder()


@dataclass
class EmbeddingService:
    """Semantic substrate facade. Stateless apart from the encoder + optional runner."""

    spec: VectorIndexSpec
    run_cypher: CypherRunner | None = None
    encoder: _Encoder | None = None
    write_cypher: CypherRunner | None = None

    def __post_init__(self) -> None:
        if self.encoder is None:
            self.encoder = _default_encoder()
        # align the index dim to whatever the encoder actually emits (no 384/768 lie).
        probe = self.embed_one("dimension probe")
        if len(probe) != self.spec.dimensions:
            self.spec = replace(self.spec, dimensions=len(probe))

    # ---- embedding ----
    def embed_one(self, text: str) -> list[float]:
        return list(self.encoder.encode(text))  # type: ignore[union-attr]

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_one(t) for t in texts]

    @property
    def is_real_model(self) -> bool:
        return bool(getattr(self.encoder, "is_real_model", False))

    # ---- Neo4j-backed path ----
    def ensure_index(self) -> None:
        if self.run_cypher is None:
            raise RuntimeError("ensure_index needs a CypherRunner (no Neo4j backend wired)")
        ensure_vector_index(self.run_cypher, self.spec)

    def backfill(
        self, *, key_prop: str = "name", limit: int = 1000, apply: bool = False
    ) -> BackfillReport:
        if self.run_cypher is None:
            raise RuntimeError("backfill needs a CypherRunner")
        writer = self.write_cypher or self.run_cypher
        return backfill_embeddings(
            self.run_cypher if not apply else writer,
            self.spec,
            self.embed_many,
            key_prop=key_prop,
            limit=limit,
            apply=apply,
        )

    def search(
        self, query_text: str, *, k: int = 10, key_prop: str = "name", min_score: float = 0.0
    ) -> list[Neighbor]:
        """kNN over the Neo4j index (preferred). Raises if no backend — callers that
        want the in-memory path use ``search_in_memory`` explicitly."""
        if self.run_cypher is None:
            raise RuntimeError("search needs a CypherRunner; use search_in_memory for infra-0")
        return knn(
            self.run_cypher,
            self.spec,
            self.embed_one(query_text),
            k=k,
            key_prop=key_prop,
            min_score=min_score,
        )

    def near_duplicate_pairs(
        self,
        items: list[tuple[str, list[float]]],
        *,
        threshold: float = 0.95,
        k: int = 10,
        key_prop: str = "name",
    ) -> list[tuple[str, str, float]]:
        if self.run_cypher is None:
            raise RuntimeError("near_duplicate_pairs (kNN) needs a CypherRunner")
        return knn_pairs(
            self.run_cypher, self.spec, items, threshold=threshold, k=k, key_prop=key_prop
        )

    # ---- infra-0 in-memory fallback ----
    def search_in_memory(
        self, items: list[tuple[str, str]], query_text: str, *, k: int = 10
    ) -> list[Neighbor]:
        """No-Neo4j path: build a transient in-memory store from (id, text) and query.
        O(N) linear scan — adequate for the hundreds-of-nodes --local case."""
        from engine.memory.vector_store import VectorStore  # noqa: PLC0415

        # VectorStore's cosine assumes L2-normalised input (it clamps the raw dot to
        # [-1,1] rather than normalising). The real Embedder normalises; defensively
        # normalise here too so the fallback is correct for any injected encoder.
        store = VectorStore(dim=self.spec.dimensions, prefer_hnsw=False)
        for node_id, text in items:
            store.add(node_id, _l2_normalize(self.embed_one(text)), {"text": text})
        hits = store.search(_l2_normalize(self.embed_one(query_text)), top_k=k)
        return [Neighbor(node_id=h.id, score=h.score, text=h.metadata.get("text")) for h in hits]


def make_service(
    *,
    label: str,
    index_name: str | None = None,
    text_prop: str = "name",
    run_cypher: CypherRunner | None = None,
    write_cypher: CypherRunner | None = None,
    encoder: _Encoder | None = None,
) -> EmbeddingService:
    """Convenience constructor. Index name defaults to ``vec_<label_lowercased>``."""
    name = index_name or f"vec_{label.lower()}"
    spec = VectorIndexSpec(index_name=name, label=label, text_prop=text_prop)
    return EmbeddingService(
        spec=spec, run_cypher=run_cypher, write_cypher=write_cypher, encoder=encoder
    )


__all__ = ["EmbeddingService", "make_service"]
