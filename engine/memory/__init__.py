"""bhgman_tool memory backend — lightweight in-memory vector store.

KG: span-phase2-hnsw-memory-skeleton-2026-05-13 (planned :AtomicSpan)
APT v26.1 Phase 2 — skeleton stage.

Design:
- In-memory HNSW (via hnswlib if available, else linear-scan fallback).
- Embedder: sentence-transformers if available, else hash-based fallback.
- All operations deterministic given the same inputs.
- No persistence by default (skeleton stage); add persistence in Phase 3.

Goodhart safeguard: NO claim of "150x-12,500x faster" or similar marketing.
Performance is *not* the headline value; correctness + simplicity is.
"""
from __future__ import annotations

from .vector_store import VectorStore, SearchResult
from .embedder import Embedder, embed_text

__all__ = ["VectorStore", "SearchResult", "Embedder", "embed_text"]
__version__ = "0.1.0"
