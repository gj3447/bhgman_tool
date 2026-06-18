"""engine.embedding — shared semantic substrate (Neo4j native vector index + embedder).

The bottom layer the 7 legion commanders ride for "체계적 Neo4j + 임베딩 적절히":
persist node embeddings into a Neo4j VECTOR index and query them with approximate kNN,
with a graceful in-memory fallback at infra-0. Backend-agnostic via injected CypherRunner.

# KG: project-legion-unification-kg-engine-2026-06-01, reference_neo4j_gds_vector_available
"""

from __future__ import annotations

from engine.embedding.neo4j_vector import (
    BackfillReport,
    Neighbor,
    VectorIndexSpec,
    backfill_embeddings,
    ensure_vector_index,
    knn,
    knn_pairs,
)
from engine.embedding.service import EmbeddingService, make_service

__all__ = [
    "VectorIndexSpec",
    "Neighbor",
    "BackfillReport",
    "ensure_vector_index",
    "backfill_embeddings",
    "knn",
    "knn_pairs",
    "EmbeddingService",
    "make_service",
]
