"""high_drift_node_ids — surface WHICH nodes drifted (the L5 provenance bridge), not just how
many. The Red artifact (test-first):

EmbeddingDriftReport computes per-node drifts to derive ``per_node_high_drift_count``, then
DISCARDS the node ids — so the L5 channel can say "N nodes drifted" but never "THESE nodes
drifted", which is useless for provenance. RED until the field exists.

# KG: ATOM_Skill_longinus
"""

from __future__ import annotations

from engine.longinus_drift_audit.embedding_channel import (
    NodeEmbedding,
    compute_embedding_drift,
)


def _emb(nid, vec):
    return NodeEmbedding(node_id=nid, vector=vec)


def test_high_drift_node_ids_names_the_drifted_node():
    # two identical anchors pin Procrustes ~I, so n3's flip stays high-drift.
    a = [_emb("n1", (1.0, 0.0)), _emb("n2", (0.0, 1.0)), _emb("n3", (1.0, 0.0))]
    b = [_emb("n1", (1.0, 0.0)), _emb("n2", (0.0, 1.0)), _emb("n3", (-1.0, 0.0))]
    r = compute_embedding_drift(a, b, opt_in=True, per_node_high_drift_threshold=0.4)
    assert r.high_drift_node_ids == ("n3",)
    assert len(r.high_drift_node_ids) == r.per_node_high_drift_count  # the invariant


def test_high_drift_node_ids_sorted_and_consistent():
    # 4 identical anchors pin Procrustes ~I; the two flipped nodes stay high-drift; ids sorted.
    anchors_a = [
        _emb("a1", (1.0, 0.0)),
        _emb("a2", (0.0, 1.0)),
        _emb("a3", (1.0, 1.0)),
        _emb("a4", (1.0, -1.0)),
    ]
    a = [*anchors_a, _emb("zed", (1.0, 0.0)), _emb("amy", (0.0, 1.0))]
    b = [*anchors_a, _emb("zed", (-1.0, 0.0)), _emb("amy", (0.0, -1.0))]
    r = compute_embedding_drift(a, b, opt_in=True, per_node_high_drift_threshold=0.4)
    assert r.high_drift_node_ids == ("amy", "zed")  # sorted
    assert len(r.high_drift_node_ids) == r.per_node_high_drift_count == 2


def test_no_drift_yields_empty_ids():
    a = [_emb("n1", (1.0, 0.0)), _emb("n2", (0.0, 1.0))]
    r = compute_embedding_drift(a, a, opt_in=True, per_node_high_drift_threshold=0.4)
    assert r.high_drift_node_ids == ()
    assert r.per_node_high_drift_count == 0


def test_empty_shared_yields_empty_ids():
    a = [_emb("n1", (1.0, 0.0))]
    b = [_emb("n2", (0.0, 1.0))]
    r = compute_embedding_drift(a, b, opt_in=True)
    assert r.high_drift_node_ids == ()
