"""Tests for the Neo4j vector substrate — fake CypherRunner, no live DB."""

from __future__ import annotations

import pytest

from engine.embedding.neo4j_vector import (
    VectorIndexSpec,
    backfill_embeddings,
    ensure_vector_index,
    fetch_unembedded,
    knn,
    knn_pairs,
)


class FakeNeo4j:
    """Records every (cypher, params) and serves canned rows by cypher fragment."""

    def __init__(self, rows_by_fragment: dict[str, list[dict]] | None = None):
        self.calls: list[tuple[str, dict]] = []
        self._rows = rows_by_fragment or {}

    def __call__(self, cypher: str, params: dict) -> list[dict]:
        self.calls.append((cypher, params))
        for fragment, rows in self._rows.items():
            if fragment in cypher:
                return rows
        return []


SPEC = VectorIndexSpec(index_name="vec_lesson", label="Lesson", text_prop="name", dimensions=4)


def _embed(texts: list[str]) -> list[list[float]]:
    # deterministic 4-d: length-bucketed unit-ish vectors (no model needed)
    out = []
    for t in texts:
        n = float(len(t))
        out.append([n, n / 2, 1.0, 0.0])
    return out


# ---------- identifier injection guard ----------


@pytest.mark.parametrize("bad", ["Lesson; DROP", "Lesson DETACH", "1abc", "a-b", "n.name"])
def test_label_injection_rejected(bad):
    with pytest.raises(ValueError, match="unsafe"):
        VectorIndexSpec(index_name="ok", label=bad)


def test_bad_similarity_and_dim_rejected():
    with pytest.raises(ValueError):
        VectorIndexSpec(index_name="ok", label="L", similarity="manhattan")
    with pytest.raises(ValueError):
        VectorIndexSpec(index_name="ok", label="L", dimensions=0)


# ---------- ensure_vector_index ----------


def test_ensure_index_emits_idempotent_ddl_with_bound_dim():
    fake = FakeNeo4j()
    ensure_vector_index(fake, SPEC)
    cypher, params = fake.calls[0]
    assert "CREATE VECTOR INDEX vec_lesson IF NOT EXISTS" in cypher
    assert "FOR (n:Lesson) ON (n.embedding)" in cypher
    assert params == {"dim": 4, "sim": "cosine"}


# ---------- fetch / backfill ----------


def test_fetch_unembedded_filters_nulls():
    fake = FakeNeo4j(
        {
            "IS NULL": [
                {"id": "a", "text": "alpha"},
                {"id": "b", "text": "beta"},
                {"id": None, "text": "x"},  # dropped (no key)
                {"id": "c", "text": None},  # dropped (no text)
            ]
        }
    )
    got = fetch_unembedded(fake, SPEC)
    assert got == [("a", "alpha"), ("b", "beta")]


def test_backfill_propose_writes_nothing():
    fake = FakeNeo4j({"IS NULL": [{"id": "a", "text": "alpha"}]})
    rep = backfill_embeddings(fake, SPEC, _embed, apply=False)
    assert rep.dry_run is True and rep.embedded == 0 and rep.scanned == 1
    assert not any("setNodeVectorProperty" in c for c, _ in fake.calls)


def test_backfill_apply_writes_vectors_via_safe_proc():
    fake = FakeNeo4j(
        {
            "IS NULL": [{"id": "a", "text": "alpha"}, {"id": "b", "text": "bb"}],
            "setNodeVectorProperty": [{"n": 1}],
        }
    )
    rep = backfill_embeddings(fake, SPEC, _embed, apply=True)
    assert rep.embedded == 2 and rep.dry_run is False
    writes = [(c, p) for c, p in fake.calls if "setNodeVectorProperty" in c]
    assert len(writes) == 2
    # vector payload flows as a bound param, never spliced into the string
    assert writes[0][1]["vec"] == _embed(["alpha"])[0]


def test_backfill_dim_mismatch_raises():
    fake = FakeNeo4j({"IS NULL": [{"id": "a", "text": "alpha"}]})
    with pytest.raises(ValueError, match="vectors for"):
        backfill_embeddings(fake, SPEC, lambda ts: [], apply=True)


# ---------- knn ----------


def test_knn_parses_and_orders():
    fake = FakeNeo4j(
        {
            "queryNodes": [
                {"id": "a", "score": 0.99, "text": "alpha"},
                {"id": "b", "score": 0.80, "text": "beta"},
            ]
        }
    )
    hits = knn(fake, SPEC, [1.0, 0.0, 0.0, 0.0], k=5, min_score=0.5)
    assert [h.node_id for h in hits] == ["a", "b"]
    assert hits[0].score == 0.99 and hits[0].text == "alpha"
    _, params = fake.calls[0]
    assert params["index"] == "vec_lesson" and params["k"] == 5 and params["min_score"] == 0.5


def test_knn_pairs_dedupes_symmetric_and_drops_self():
    # a's neighbours include itself + b; b's neighbours include a again (symmetric).
    fake = FakeNeo4j(
        {
            "queryNodes": [
                {"id": "a", "score": 1.0, "text": "x"},  # self-hit (dropped)
                {"id": "b", "score": 0.97, "text": "y"},
            ]
        }
    )
    items = [("a", [1, 0, 0, 0]), ("b", [1, 0, 0, 0])]
    pairs = knn_pairs(fake, SPEC, items, threshold=0.95)
    assert pairs == [("a", "b", 0.97)]  # one ordered pair, no (b,a) duplicate
