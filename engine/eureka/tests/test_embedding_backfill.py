"""임베딩 backfill TDD — 텍스트 추출 + cypher 빌더(label allowlist) + dry-run/apply 루프.

모델 불필요 (embed_fn 주입식 fake).

# KG: eureka-canonical-2026-05-26
"""

from __future__ import annotations

import pytest
from engine.eureka.embedding_backfill import (
    TEXT_FIELDS,
    backfill,
    fetch_unembedded_cypher,
    node_text,
    set_embeddings_cypher,
)


def _embed(texts):
    return [[float(len(t))] * 4 for t in texts]  # deterministic 4-dim fake


class _ReadRunner:
    def __init__(self, batches):
        self.batches = list(batches)
        self.i = 0
        self.calls = []

    def __call__(self, cy, pa):
        self.calls.append((cy, pa))
        b = self.batches[self.i] if self.i < len(self.batches) else []
        self.i += 1
        return b


class _WriteRunner:
    def __init__(self):
        self.calls = []

    def __call__(self, cy, pa):
        self.calls.append((cy, pa))
        return [{"set_count": len(pa.get("rows", []))}]


# ── text extraction ───────────────────────────────────────────────────────


def test_node_text_joins_nonempty_fields():
    assert node_text("lesson-1", ["title", None, "", "body"]) == "title body"


def test_node_text_falls_back_to_name():
    assert node_text("lesson-1", [None, ""]) == "lesson-1"


# ── cypher builders + label allowlist ───────────────────────────────────────


def test_fetch_cypher_valid_label():
    cy = fetch_unembedded_cypher("Lesson")
    assert "n:Lesson" in cy and "embedding IS NULL" in cy and "$fields" in cy


def test_fetch_cypher_rejects_unknown_label():
    with pytest.raises(ValueError, match="allowlist"):
        fetch_unembedded_cypher("Lesson) DETACH DELETE n //")  # injection attempt


def test_set_cypher_rejects_unknown_label():
    with pytest.raises(ValueError):
        set_embeddings_cypher("Evil")


def test_known_labels_have_fields():
    assert "Lesson" in TEXT_FIELDS and "name" in TEXT_FIELDS["Lesson"]


# ── backfill dry-run / apply ─────────────────────────────────────────────────


def test_backfill_dry_run_does_not_write():
    read = _ReadRunner([[{"name": "a", "vals": ["x"]}, {"name": "b", "vals": ["y"]}]])
    write = _WriteRunner()
    rep = backfill(read, write, _embed, "Lesson")  # dry_run defaults True
    assert rep.dry_run is True
    assert rep.embedded == 0
    assert write.calls == []  # no write in dry-run
    assert "2 node" in rep.note


def test_backfill_apply_embeds_and_writes_until_empty():
    # batch1 (2 nodes) → batch2 empty → stop
    read = _ReadRunner([[{"name": "a", "vals": ["x"]}, {"name": "b", "vals": ["y"]}], []])
    write = _WriteRunner()
    rep = backfill(read, write, _embed, "Lesson", dry_run=False)
    assert rep.embedded == 2
    assert rep.batches == 1
    assert len(write.calls) == 1
    rows = write.calls[0][1]["rows"]
    assert rows[0]["name"] == "a" and len(rows[0]["emb"]) == 4  # embedding attached


def test_backfill_respects_max_nodes():
    read = _ReadRunner([[{"name": "a", "vals": ["x"]}], [{"name": "b", "vals": ["y"]}], []])
    write = _WriteRunner()
    rep = backfill(read, write, _embed, "Lesson", batch_size=1, max_nodes=1, dry_run=False)
    assert rep.embedded == 1  # stopped at max_nodes


def test_backfill_no_write_runner_forces_dry_run():
    read = _ReadRunner([[{"name": "a", "vals": ["x"]}]])
    rep = backfill(read, None, _embed, "Lesson", dry_run=False)
    assert rep.dry_run is True
    assert rep.embedded == 0
