"""In-memory vector store with cosine similarity search.

KG: span-phase2-hnsw-memory-skeleton-2026-05-13 (planned :AtomicSpan)
KG: finding-prom16-parallelism-bhgman-dep-A4 (thread-safety, lock on add)

Backend selection:
- hnswlib (preferred, HNSW approximate NN, O(log N))
- linear scan fallback (no external dep, O(N) — adequate for skeleton + tests)

The hnswlib path is *optional* — skeleton works without it.

Thread-safety: ``add`` / ``add_many`` mutate ``_records`` / ``_next_label`` /
``_hnsw_id_to_label`` non-atomically, and hnswlib's ``add_items`` is documented
as not thread-safe for concurrent writes. A module ``threading.Lock`` guards
the write path. ``search`` / ``get`` are read-only and safe to run concurrently
with each other but not with a concurrent ``add`` (the lock serializes writes
against readers via context guard on the write side only).
"""

from __future__ import annotations

import dataclasses as dc
import threading
from typing import Any, Iterable


@dc.dataclass(frozen=True)
class SearchResult:
    """One hit from a similarity search."""

    id: str
    score: float  # cosine similarity in [0, 1] (after L2-normalization)
    metadata: dict[str, Any]


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """L2-normalized cosine sim. Expects pre-normalized vectors but verifies."""
    if len(a) != len(b):
        raise ValueError(f"dim mismatch: {len(a)} vs {len(b)}")
    dot = sum(x * y for x, y in zip(a, b))
    # Already normalized in embedder; clamp for floating-point safety
    return max(-1.0, min(1.0, dot))


class VectorStore:
    """In-memory vector store. HNSW backend if hnswlib available, else linear scan."""

    def __init__(self, dim: int, *, prefer_hnsw: bool = True):
        self.dim = dim
        self._records: list[tuple[str, list[float], dict[str, Any]]] = []
        self._hnsw: Any = None
        self._hnsw_id_to_label: dict[str, int] = {}
        self._next_label = 0
        # Bernstein W∩W guard: _records.append + _next_label += 1 + hnsw.add_items
        # is non-atomic; serialize the write path.
        # KG: finding-prom16-parallelism-bhgman-dep-A4
        self._write_lock = threading.Lock()
        if prefer_hnsw:
            try:
                import hnswlib  # noqa: F401

                self._hnsw = hnswlib.Index(space="cosine", dim=dim)
                self._hnsw.init_index(max_elements=10000, ef_construction=200, M=16)
            except ImportError:
                self._hnsw = None

    @property
    def backend(self) -> str:
        return "hnswlib" if self._hnsw is not None else "linear-scan"

    @property
    def size(self) -> int:
        return len(self._records)

    def add(self, id: str, vector: list[float], metadata: dict[str, Any] | None = None) -> None:
        if len(vector) != self.dim:
            raise ValueError(f"vector dim {len(vector)} != store dim {self.dim}")
        meta = dict(metadata or {})
        # Serialize: dup check + append + label increment + hnsw add must be one critical section.
        with self._write_lock:
            if any(r[0] == id for r in self._records):
                raise ValueError(f"id already present: {id}")
            self._records.append((id, list(vector), meta))
            if self._hnsw is not None:
                label = self._next_label
                self._next_label += 1
                self._hnsw_id_to_label[id] = label
                self._hnsw.add_items([vector], [label])

    def add_many(self, items: Iterable[tuple[str, list[float], dict[str, Any] | None]]) -> int:
        n = 0
        for id, vec, meta in items:
            self.add(id, vec, meta or {})
            n += 1
        return n

    def search(self, query: list[float], top_k: int = 5) -> list[SearchResult]:
        if len(query) != self.dim:
            raise ValueError(f"query dim {len(query)} != store dim {self.dim}")
        if not self._records:
            return []
        top_k = max(1, min(top_k, len(self._records)))
        if self._hnsw is not None:
            labels, distances = self._hnsw.knn_query([query], k=top_k)
            label_to_id = {v: k for k, v in self._hnsw_id_to_label.items()}
            results: list[SearchResult] = []
            for label, dist in zip(labels[0], distances[0]):
                id = label_to_id[int(label)]
                _, _, meta = next(r for r in self._records if r[0] == id)
                # hnswlib cosine distance = 1 - cosine_similarity
                score = 1.0 - float(dist)
                results.append(SearchResult(id=id, score=score, metadata=meta))
            return results
        # Linear scan fallback
        scored = [(id, _cosine_similarity(query, vec), meta) for id, vec, meta in self._records]
        scored.sort(key=lambda x: x[1], reverse=True)
        return [
            SearchResult(id=id, score=score, metadata=meta) for id, score, meta in scored[:top_k]
        ]

    def get(self, id: str) -> tuple[list[float], dict[str, Any]] | None:
        for rid, vec, meta in self._records:
            if rid == id:
                return vec, meta
        return None
