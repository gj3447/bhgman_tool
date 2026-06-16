"""pytest for engine/memory/ vector store + embedder skeleton.

KG: span-phase2-hnsw-memory-skeleton-2026-05-13 (planned :AtomicSpan)
APT v26.1 Phase 2 SCW verification gate.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent))  # engine/memory parent

from memory import VectorStore, Embedder, embed_text
from memory.embedder import _hash_embed, DEFAULT_DIM


# ─── Embedder ───────────────────────────────────────────────────────────


def test_default_embedder_returns_correct_dim():
    vec = embed_text("hello world")
    assert len(vec) == DEFAULT_DIM


def test_hash_embed_deterministic():
    a = _hash_embed("foo", DEFAULT_DIM)
    b = _hash_embed("foo", DEFAULT_DIM)
    assert a == b


def test_hash_embed_different_texts_differ():
    a = _hash_embed("foo", DEFAULT_DIM)
    b = _hash_embed("bar", DEFAULT_DIM)
    assert a != b


def test_hash_embed_l2_normalized():
    vec = _hash_embed("normalize me", 384)
    norm_squared = sum(x * x for x in vec)
    # L2-normalized vectors have norm = 1 (within float epsilon)
    assert abs(norm_squared - 1.0) < 1e-6


def test_embedder_class_is_callable():
    emb = Embedder()
    vec = emb.encode("test text")
    assert len(vec) == emb.dim


def test_embedder_falls_back_when_sentence_transformer_init_fails(monkeypatch):
    class BrokenSentenceTransformer:
        def __init__(self, _model_name):
            raise OSError("offline")

    monkeypatch.setitem(
        sys.modules,
        "sentence_transformers",
        types.SimpleNamespace(SentenceTransformer=BrokenSentenceTransformer),
    )
    emb = Embedder()
    assert emb.is_real_model is False
    assert emb.fallback_reason is not None
    assert len(emb.encode("offline fallback")) == emb.dim


# ─── VectorStore ────────────────────────────────────────────────────────


def test_store_empty_initial():
    store = VectorStore(dim=8)
    assert store.size == 0
    assert store.search([0.0] * 8) == []


def test_store_add_and_size():
    store = VectorStore(dim=4)
    store.add("a", [1.0, 0.0, 0.0, 0.0])
    store.add("b", [0.0, 1.0, 0.0, 0.0])
    assert store.size == 2


def test_store_rejects_dim_mismatch_on_add():
    store = VectorStore(dim=4)
    with pytest.raises(ValueError, match="dim"):
        store.add("x", [1.0, 0.0])


def test_store_rejects_duplicate_id():
    store = VectorStore(dim=2)
    store.add("a", [1.0, 0.0])
    with pytest.raises(ValueError, match="already present"):
        store.add("a", [0.0, 1.0])


def test_store_search_returns_most_similar_first():
    store = VectorStore(dim=4, prefer_hnsw=False)  # use linear-scan for determinism
    store.add("a", [1.0, 0.0, 0.0, 0.0])
    store.add("b", [0.0, 1.0, 0.0, 0.0])
    store.add("c", [0.7071, 0.7071, 0.0, 0.0])
    results = store.search([1.0, 0.0, 0.0, 0.0], top_k=3)
    assert results[0].id == "a"  # exact match
    assert results[1].id == "c"  # 0.7071 similarity
    assert results[2].id == "b"  # 0.0 similarity
    assert results[0].score > results[1].score > results[2].score


def test_store_search_top_k_caps():
    store = VectorStore(dim=4, prefer_hnsw=False)
    store.add("a", [1.0, 0.0, 0.0, 0.0])
    results = store.search([1.0, 0.0, 0.0, 0.0], top_k=10)
    assert len(results) == 1


def test_store_metadata_preserved():
    store = VectorStore(dim=2)
    store.add("a", [1.0, 0.0], {"label": "first", "kg_id": "lesson-1"})
    results = store.search([1.0, 0.0])
    assert results[0].metadata == {"label": "first", "kg_id": "lesson-1"}


def test_store_get_retrieves_vector_and_metadata():
    store = VectorStore(dim=2)
    store.add("x", [0.5, 0.5], {"k": "v"})
    retrieved = store.get("x")
    assert retrieved is not None
    vec, meta = retrieved
    assert vec == [0.5, 0.5]
    assert meta == {"k": "v"}


def test_store_get_missing_returns_none():
    store = VectorStore(dim=2)
    assert store.get("nope") is None


def test_store_add_many_returns_count():
    store = VectorStore(dim=2)
    items = [
        ("a", [1.0, 0.0], None),
        ("b", [0.0, 1.0], {"meta": True}),
    ]
    count = store.add_many(items)
    assert count == 2
    assert store.size == 2


def test_store_backend_reports_correctly():
    store = VectorStore(dim=4, prefer_hnsw=False)
    assert store.backend == "linear-scan"


# ─── Integration: embedder + store ─────────────────────────────────────


def test_embed_and_store_round_trip():
    """End-to-end: embed two texts, store both, retrieve via search."""
    store = VectorStore(dim=DEFAULT_DIM, prefer_hnsw=False)
    store.add("doc1", embed_text("the quick brown fox"), {"text": "the quick brown fox"})
    store.add("doc2", embed_text("a slow green turtle"), {"text": "a slow green turtle"})
    # Search with one of the docs themselves should rank itself first
    query = embed_text("the quick brown fox")
    results = store.search(query, top_k=2)
    assert results[0].id == "doc1"
    assert results[0].score > 0.99  # near-1 self-similarity
