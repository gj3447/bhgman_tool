"""EmbeddingService tests — fake encoder, no model download / no live DB."""

from __future__ import annotations

import pytest

from engine.embedding.service import EmbeddingService, make_service
from engine.embedding.neo4j_vector import VectorIndexSpec


class FakeEncoder:
    """Deterministic 3-d encoder; len-based so similar texts cluster."""

    is_real_model = False

    def encode(self, text: str) -> list[float]:
        n = float(len(text))
        return [n, 1.0, 0.0]


class FakeNeo4j:
    def __init__(self, rows_by_fragment=None):
        self.calls = []
        self._rows = rows_by_fragment or {}

    def __call__(self, cypher, params):
        self.calls.append((cypher, params))
        for frag, rows in self._rows.items():
            if frag in cypher:
                return rows
        return []


def _spec(dim=768):
    return VectorIndexSpec(index_name="vec_lesson", label="Lesson", dimensions=dim)


def test_dim_auto_aligns_to_encoder():
    # spec declares 768 but the encoder emits 3-d → service rewrites spec dim to 3.
    svc = EmbeddingService(spec=_spec(768), encoder=FakeEncoder())
    assert svc.spec.dimensions == 3
    assert svc.is_real_model is False


def test_ensure_index_requires_backend():
    svc = EmbeddingService(spec=_spec(3), encoder=FakeEncoder())
    with pytest.raises(RuntimeError, match="CypherRunner"):
        svc.ensure_index()
    with pytest.raises(RuntimeError):
        svc.search("q")


def test_backfill_apply_routes_through_backend():
    fake = FakeNeo4j(
        {
            "IS NULL": [{"id": "a", "text": "alpha"}],
            "setNodeVectorProperty": [{"n": 1}],
        }
    )
    svc = EmbeddingService(spec=_spec(3), run_cypher=fake, encoder=FakeEncoder())
    rep = svc.backfill(apply=True)
    assert rep.embedded == 1
    assert any("setNodeVectorProperty" in c for c, _ in fake.calls)


def test_search_in_memory_fallback_ranks_by_similarity():
    svc = EmbeddingService(spec=_spec(3), encoder=FakeEncoder())  # no runner → infra-0
    items = [("short", "hi"), ("longer", "hello world!!")]
    # query "hello world!!" (len 13) should rank the same-length node first
    hits = svc.search_in_memory(items, "hello world!!", k=2)
    assert hits[0].node_id == "longer"


def test_make_service_defaults_index_name():
    svc = make_service(label="Finding", encoder=FakeEncoder())
    assert svc.spec.index_name == "vec_finding" and svc.spec.label == "Finding"
