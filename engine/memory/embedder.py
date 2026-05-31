"""Embedder — text → fixed-dim vector.

KG: span-phase2-hnsw-memory-skeleton-2026-05-13 (planned :AtomicSpan)

Two backends:
- sentence-transformers (preferred, real semantic embeddings)
- hash-based deterministic fallback (no network, no model download required)

The fallback is *not* a real semantic embedding — it's a deterministic
hash-spread vector. Useful for tests + scenarios where the user hasn't
installed sentence-transformers yet. Marketing-honest: this is *not* RAG;
it's a placeholder so the API works.
"""
# KG: bihaenggiman-legioncommanders-2026-05-26

from __future__ import annotations

import hashlib
import math
import struct
from typing import Any


DEFAULT_DIM = 384  # matches all-MiniLM-L6-v2 dimension


class Embedder:
    """Wraps sentence-transformers if available, else hash fallback."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2", dim: int = DEFAULT_DIM):
        self.model_name = model_name
        self.dim = dim
        self._model: Any = None
        self._is_real = False
        try:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(model_name)
            self._is_real = True
        except ImportError:
            self._model = None  # use hash fallback

    @property
    def is_real_model(self) -> bool:
        return self._is_real

    def encode(self, text: str) -> list[float]:
        if self._is_real:
            vec = self._model.encode(text, normalize_embeddings=True)
            return vec.tolist() if hasattr(vec, "tolist") else list(vec)
        return _hash_embed(text, self.dim)


def _hash_embed(text: str, dim: int) -> list[float]:
    """Deterministic hash-based pseudo-embedding.

    Uses SHA-256 of text expanded into `dim` floats in [-1, 1].
    NOT a semantic embedding — distance between two unrelated strings
    is essentially random. Provided so the API is callable without
    sentence-transformers installed.
    """
    out: list[float] = []
    seed = hashlib.sha256(text.encode("utf-8")).digest()
    needed_bytes = dim * 4  # 4 bytes per float32
    # Extend seed deterministically
    blob = b""
    counter = 0
    while len(blob) < needed_bytes:
        chunk = hashlib.sha256(seed + counter.to_bytes(4, "big")).digest()
        blob += chunk
        counter += 1
    # Unpack 4 bytes at a time as uint32, normalize to [-1, 1]
    for i in range(dim):
        chunk = blob[i * 4 : i * 4 + 4]
        n = struct.unpack(">I", chunk)[0]
        # Map [0, 2^32) → [-1, 1)
        out.append((n / (1 << 31)) - 1.0)
    # L2-normalize for cosine-similarity compatibility
    norm = math.sqrt(sum(x * x for x in out))
    if norm > 0:
        out = [x / norm for x in out]
    return out


# Module-level convenience
_default_embedder: Embedder | None = None


def embed_text(text: str) -> list[float]:
    """Embed text using the default (lazily-created) Embedder."""
    global _default_embedder
    if _default_embedder is None:
        _default_embedder = Embedder()
    return _default_embedder.encode(text)
