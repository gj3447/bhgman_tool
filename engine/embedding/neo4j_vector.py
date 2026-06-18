"""Neo4j native vector index layer — KG-systematic semantic substrate.

The shared bottom layer every commander rides for "체계적 Neo4j + 임베딩 적절히":
embeddings are *persisted into Neo4j* (a `:Label.embedding` vector property indexed
by a native VECTOR index) and queried with approximate kNN via
``db.index.vector.queryNodes`` — replacing the O(N²) in-memory pairwise scan that
``occam/semantic_dedup.py`` flagged as the documented follow-up:

    "스케일: 현재 O(N²) pairwise (수백 노드 OK). 대규모는 KG native vector index(kNN)로 후속."

Backend-agnostic: all I/O goes through an injected ``CypherRunner`` (live MCP /
``--local`` kg_local / fake-in-test). No driver import here — the caller owns the
connection, exactly like the rest of engine/.

Injection safety: index name / label / text+vector properties land in Cypher DDL
positions that *cannot* be parameterised, so each is validated as a bare identifier
before interpolation. Only the vector payload + limits flow as bound `$params`.

# KG: rf-semdist-occam-2026-06-01 (the follow-up this realises),
#     reference_neo4j_gds_vector_available (Neo4j has native vector index dim768),
#     occam-kam-canonical-2026-05-26, project-legion-unification-kg-engine-2026-06-01
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

CypherRunner = Callable[[str, dict], "list[dict]"]

# A Neo4j identifier we are willing to splice into DDL/labels unescaped. Deliberately
# stricter than Neo4j's own grammar (no backticked exotic names) — anything outside
# this is rejected rather than escaped, so there is no injection surface.
_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# cosine matches the embedder (vectors are L2-normalised); euclidean kept for parity.
_SIMILARITY = frozenset({"cosine", "euclidean"})


def _ident(kind: str, value: str) -> str:
    if not _IDENT.match(value):
        raise ValueError(f"unsafe {kind} identifier {value!r} (must match {_IDENT.pattern})")
    return value


@dataclass(frozen=True)
class VectorIndexSpec:
    """One node-label's vector index. ``text_prop`` is the source text to embed."""

    index_name: str
    label: str
    embedding_prop: str = "embedding"
    text_prop: str = "name"
    dimensions: int = 768
    similarity: str = "cosine"

    def __post_init__(self) -> None:
        _ident("index_name", self.index_name)
        _ident("label", self.label)
        _ident("embedding_prop", self.embedding_prop)
        _ident("text_prop", self.text_prop)
        if self.dimensions <= 0:
            raise ValueError(f"dimensions must be positive, got {self.dimensions}")
        if self.similarity not in _SIMILARITY:
            raise ValueError(f"similarity must be one of {sorted(_SIMILARITY)}")


@dataclass(frozen=True)
class Neighbor:
    """One kNN hit. ``score`` is cosine similarity in [0,1] for cosine indexes."""

    node_id: str
    score: float
    text: str | None = None


@dataclass(frozen=True)
class BackfillReport:
    index_name: str
    scanned: int
    embedded: int
    dry_run: bool

    @property
    def summary(self) -> str:
        mode = "DRY-RUN (PROPOSE)" if self.dry_run else f"WROTE {self.embedded}"
        return f"vector-backfill[{self.index_name}]: scanned={self.scanned} → {mode}"


def ensure_vector_index(run_cypher: CypherRunner, spec: VectorIndexSpec) -> None:
    """Idempotently create the native VECTOR index. No-op if it already exists."""
    cypher = (
        f"CREATE VECTOR INDEX {spec.index_name} IF NOT EXISTS "
        f"FOR (n:{spec.label}) ON (n.{spec.embedding_prop}) "
        "OPTIONS {indexConfig: {"
        "`vector.dimensions`: $dim, "
        "`vector.similarity_function`: $sim}}"
    )
    run_cypher(cypher, {"dim": spec.dimensions, "sim": spec.similarity})


def fetch_unembedded(
    run_cypher: CypherRunner, spec: VectorIndexSpec, *, key_prop: str = "name", limit: int = 1000
) -> list[tuple[str, str]]:
    """(node_key, text) for nodes that have text but no embedding yet."""
    _ident("key_prop", key_prop)
    cypher = (
        f"MATCH (n:{spec.label}) "
        f"WHERE n.{spec.text_prop} IS NOT NULL AND n.{spec.embedding_prop} IS NULL "
        f"RETURN n.{key_prop} AS id, n.{spec.text_prop} AS text "
        "LIMIT $limit"
    )
    rows = run_cypher(cypher, {"limit": limit})
    return [(r["id"], r["text"]) for r in rows if r.get("id") is not None and r.get("text")]


def backfill_embeddings(
    run_cypher: CypherRunner,
    spec: VectorIndexSpec,
    embed_fn: Callable[[list[str]], "list[list[float]]"],
    *,
    key_prop: str = "name",
    limit: int = 1000,
    apply: bool = False,
) -> BackfillReport:
    """Embed every text-bearing node missing a vector and write it via the safe
    ``db.create.setNodeVectorProperty`` proc (validates dim against the index).

    PROPOSE by default (``apply=False`` only reports the count it *would* write) —
    consistent with the occam/hades non-destructive covenant. Writing an embedding
    is additive (no node mutation beyond the new vector prop), so apply is safe to
    enable, but stays opt-in for parity with the rest of legion.
    """
    _ident("key_prop", key_prop)
    pending = fetch_unembedded(run_cypher, spec, key_prop=key_prop, limit=limit)
    if not pending:
        return BackfillReport(spec.index_name, scanned=0, embedded=0, dry_run=not apply)

    texts = [t for _, t in pending]
    vectors = embed_fn(texts)
    if len(vectors) != len(pending):
        raise ValueError(f"embed_fn returned {len(vectors)} vectors for {len(pending)} texts")

    embedded = 0
    if apply:
        write = (
            f"MATCH (n:{spec.label}) WHERE n.{key_prop} = $id "
            f"CALL db.create.setNodeVectorProperty(n, '{spec.embedding_prop}', $vec) "
            "RETURN count(n) AS n"
        )
        for (node_id, _), vec in zip(pending, vectors):
            rows = run_cypher(write, {"id": node_id, "vec": vec})
            if rows and rows[0].get("n"):
                embedded += 1
    return BackfillReport(
        spec.index_name, scanned=len(pending), embedded=embedded, dry_run=not apply
    )


def knn(
    run_cypher: CypherRunner,
    spec: VectorIndexSpec,
    query_vector: list[float],
    *,
    k: int = 10,
    key_prop: str = "name",
    min_score: float = 0.0,
) -> list[Neighbor]:
    """Approximate k-nearest neighbours via the native vector index."""
    _ident("key_prop", key_prop)
    cypher = (
        f"CALL db.index.vector.queryNodes($index, $k, $vec) YIELD node, score "
        "WHERE score >= $min_score "
        f"RETURN node.{key_prop} AS id, score, node.{spec.text_prop} AS text "
        "ORDER BY score DESC"
    )
    rows = run_cypher(
        cypher,
        {"index": spec.index_name, "k": k, "vec": query_vector, "min_score": min_score},
    )
    return [
        Neighbor(node_id=r["id"], score=float(r["score"]), text=r.get("text"))
        for r in rows
        if r.get("id") is not None
    ]


def knn_pairs(
    run_cypher: CypherRunner,
    spec: VectorIndexSpec,
    items: list[tuple[str, list[float]]],
    *,
    threshold: float = 0.95,
    k: int = 10,
    key_prop: str = "name",
) -> list[tuple[str, str, float]]:
    """Near-duplicate (a_id, b_id, score) pairs via per-node kNN instead of O(N²).

    Each item probes the index for its k neighbours; self-hits and the symmetric
    duplicate (b,a) are dropped, leaving one ordered pair per dup with score≥θ.
    Caller (occam) keeps its own keep/drop tiebreak — this only surfaces candidates.
    """
    seen: set[frozenset[str]] = set()
    out: list[tuple[str, str, float]] = []
    for node_id, vec in items:
        for nb in knn(run_cypher, spec, vec, k=k + 1, key_prop=key_prop, min_score=threshold):
            if nb.node_id == node_id:
                continue
            pair_key = frozenset((node_id, nb.node_id))
            if pair_key in seen:
                continue
            seen.add(pair_key)
            out.append((node_id, nb.node_id, nb.score))
    out.sort(key=lambda p: (-p[2], p[0], p[1]))
    return out


__all__ = [
    "CypherRunner",
    "VectorIndexSpec",
    "Neighbor",
    "BackfillReport",
    "ensure_vector_index",
    "fetch_unembedded",
    "backfill_embeddings",
    "knn",
    "knn_pairs",
]
