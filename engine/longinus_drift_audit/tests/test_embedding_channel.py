"""Tests for L5 embedding cosine drift channel (v3.4 ALT1, 2026-05-19).

# KG: CONTRACT_EmbeddingChannel_v1_2026-05-19,
#     sa-longinus-v3.4-L5-embedding-2026-05-19,
#     wqi-longinus-v3.4-L5-embedding-channel-optional-2026-05-19
"""

from __future__ import annotations

import math

import pytest

from engine.longinus_drift_audit.embedding_channel import (
    EmbeddingDriftReport,
    LonginusEmbeddingOptInRequired,
    NodeEmbedding,
    compute_embedding_drift,
)


def _emb(node_id: str, *vals: float) -> NodeEmbedding:
    return NodeEmbedding(node_id=node_id, vector=tuple(vals))


def test_opt_in_false_raises_defeats_provenance_gate():
    """Default opt_in=False must raise LonginusEmbeddingOptInRequired."""
    a = [_emb("n1", 1.0, 0.0, 0.0)]
    b = [_emb("n1", 1.0, 0.0, 0.0)]
    with pytest.raises(LonginusEmbeddingOptInRequired, match="provenance"):
        compute_embedding_drift(a, b)


def test_opt_in_true_identical_perfect():
    """Identical embeddings, opt_in=True → mean_drift=0, severity PERFECT."""
    a = [_emb("n1", 1.0, 0.0, 0.0), _emb("n2", 0.0, 1.0, 0.0)]
    b = [_emb("n1", 1.0, 0.0, 0.0), _emb("n2", 0.0, 1.0, 0.0)]
    report = compute_embedding_drift(a, b, opt_in=True)
    assert report.mean_cosine_drift == pytest.approx(0.0, abs=1e-9)
    assert report.severity == "PERFECT"
    assert report.aligned_count == 2
    assert report.opt_in_acknowledged is True
    assert not report.warn
    assert not report.halt
    assert report.preliminary_longinus_novel is False


def test_completely_orthogonal_drift_one():
    """Orthogonal vectors → cosine=0 → drift=1 per node."""
    a = [_emb("n1", 1.0, 0.0), _emb("n2", 1.0, 0.0)]
    b = [_emb("n1", 0.0, 1.0), _emb("n2", 0.0, 1.0)]
    report = compute_embedding_drift(a, b, opt_in=True)
    # After diagonal-scaling alignment, still orthogonal axes → drift remains ~1.
    assert report.mean_cosine_drift > 0.9
    assert report.halt is True
    assert report.severity == "CRITICAL"
    assert report.preliminary_longinus_novel is True


def test_identical_up_to_uniform_scaling_aligns_to_zero():
    """Cosine is scale-invariant — B = 2*A → drift=0 without any alignment."""
    a = [_emb("n1", 1.0, 0.0, 0.0), _emb("n2", 0.0, 1.0, 0.0)]
    b = [_emb("n1", 2.0, 0.0, 0.0), _emb("n2", 0.0, 2.0, 0.0)]
    report = compute_embedding_drift(a, b, opt_in=True)
    assert report.mean_cosine_drift == pytest.approx(0.0, abs=1e-9)
    assert report.severity == "PERFECT"


def test_small_perturbation_below_warn():
    """Tiny rotation each vector → drift well below 0.08 warn."""
    # Vector slightly perturbed, ~1 deg → 1 - cos ~ 0.00015
    eps = 0.02
    a = [_emb(f"n{i}", 1.0, 0.0) for i in range(20)]
    b = [_emb(f"n{i}", math.cos(eps), math.sin(eps)) for i in range(20)]
    report = compute_embedding_drift(a, b, opt_in=True)
    assert report.mean_cosine_drift < 0.08
    assert not report.warn
    assert not report.halt
    assert report.severity in {"EXCELLENT", "ACCEPTABLE"}


def test_mean_crosses_warn_but_not_halt():
    """Rotate every shared vector enough to cross warn but stay below halt."""
    # cos(theta)=0.90 → drift=0.10 → above warn 0.08, below halt 0.20
    # Need many low-drift nodes so high_ratio doesn't trip.
    theta = math.acos(0.90)
    n = 100
    a = [_emb(f"n{i}", 1.0, 0.0) for i in range(n)]
    b = [_emb(f"n{i}", math.cos(theta), math.sin(theta)) for i in range(n)]
    report = compute_embedding_drift(a, b, opt_in=True)
    assert report.mean_cosine_drift > 0.08
    assert report.mean_cosine_drift < 0.20
    # high_drift count: 0.10 < 0.40 threshold → 0
    assert report.per_node_high_drift_count == 0
    assert report.warn is True
    assert report.halt is False


def test_mean_crosses_halt_threshold():
    """Rotate every shared vector by 60deg → drift=0.5 each → mean > halt."""
    theta = math.acos(0.5)
    n = 50
    a = [_emb(f"n{i}", 1.0, 0.0) for i in range(n)]
    b = [_emb(f"n{i}", math.cos(theta), math.sin(theta)) for i in range(n)]
    report = compute_embedding_drift(a, b, opt_in=True)
    assert report.mean_cosine_drift >= 0.20
    assert report.warn is True
    assert report.halt is True
    assert report.preliminary_longinus_novel is True
    assert report.severity == "CRITICAL"


def test_per_node_high_drift_triggers_halt_independently():
    """Mean below halt but >5% nodes with drift > 0.40 → halt fires anyway."""
    # 100 nodes; 6 with drift=1 (orthogonal), 94 identical (drift=0).
    # Mean = 6/100 = 0.06 (below warn 0.08), but high_ratio = 6% > 5% → halt.
    a = []
    b = []
    for i in range(94):
        a.append(_emb(f"n{i}", 1.0, 0.0))
        b.append(_emb(f"n{i}", 1.0, 0.0))
    for i in range(94, 100):
        a.append(_emb(f"n{i}", 1.0, 0.0))
        b.append(_emb(f"n{i}", 0.0, 1.0))
    report = compute_embedding_drift(a, b, opt_in=True)
    # high_drift_count must catch the 6 orthogonal pairs
    assert report.per_node_high_drift_count == 6
    assert report.per_node_high_drift_ratio == pytest.approx(0.06)
    # Halt fires via high-drift route even though mean < halt threshold
    assert report.halt is True
    assert report.warn is True


def test_threshold_validation_warn_out_of_range():
    with pytest.raises(ValueError, match="warn_mean_threshold"):
        compute_embedding_drift([], [], opt_in=True, warn_mean_threshold=3.0)


def test_threshold_validation_halt_below_warn():
    with pytest.raises(ValueError, match="halt_mean_threshold"):
        compute_embedding_drift(
            [], [], opt_in=True, warn_mean_threshold=0.5, halt_mean_threshold=0.1
        )


def test_threshold_validation_high_drift_ratio_out_of_range():
    with pytest.raises(ValueError, match="high_drift_ratio_threshold"):
        compute_embedding_drift([], [], opt_in=True, high_drift_ratio_threshold=1.5)


def test_preliminary_longinus_novel_set_on_halt():
    """Mirror of L2 pattern — halt=True forces preliminary tag."""
    n = 30
    a = [_emb(f"n{i}", 1.0, 0.0) for i in range(n)]
    b = [_emb(f"n{i}", 0.0, 1.0) for i in range(n)]
    report = compute_embedding_drift(a, b, opt_in=True)
    assert report.halt is True
    assert report.preliminary_longinus_novel is True


def test_preliminary_tag_clear_on_no_halt():
    """No halt → preliminary flag must remain False (mirror L2 pattern)."""
    a = [_emb("n1", 1.0, 0.0)]
    b = [_emb("n1", 1.0, 0.0)]
    report = compute_embedding_drift(a, b, opt_in=True)
    assert report.halt is False
    assert report.preliminary_longinus_novel is False


def test_pydantic_round_trip():
    """EmbeddingDriftReport must serialize / deserialize via Pydantic."""
    a = [_emb("n1", 1.0, 0.0), _emb("n2", 0.0, 1.0)]
    b = [_emb("n1", 1.0, 0.0), _emb("n2", 0.0, 1.0)]
    report = compute_embedding_drift(a, b, opt_in=True)
    d = report.model_dump()
    assert d["opt_in_acknowledged"] is True
    assert d["aligned_count"] == 2
    assert d["alignment_method"] in {
        "procrustes-orthogonal",
        "diagonal-scaling-stub",
        "identity",
    }
    # Round-trip
    restored = EmbeddingDriftReport.model_validate(d)
    assert restored.mean_cosine_drift == report.mean_cosine_drift
    assert restored.preliminary_longinus_novel == report.preliminary_longinus_novel


def test_empty_inputs_no_shared_returns_perfect():
    """No shared nodes → identity alignment, mean=0, severity PERFECT."""
    a = [_emb("n1", 1.0, 0.0)]
    b = [_emb("n2", 0.0, 1.0)]
    report = compute_embedding_drift(a, b, opt_in=True)
    assert report.aligned_count == 0
    assert report.mean_cosine_drift == 0.0
    assert report.severity == "PERFECT"
    assert report.alignment_method == "identity"
    assert not report.warn


def test_dimension_mismatch_raises():
    """Mismatched vector dimensions between A and B for same node → ValueError."""
    a = [_emb("n1", 1.0, 0.0, 0.0)]
    b = [_emb("n1", 1.0, 0.0)]
    with pytest.raises(ValueError, match="dimension"):
        compute_embedding_drift(a, b, opt_in=True)


def test_node_embedding_frozen():
    """NodeEmbedding is frozen (Pydantic ConfigDict frozen=True)."""
    e = _emb("n1", 1.0, 0.0)
    with pytest.raises((TypeError, ValueError)):
        e.node_id = "other"  # type: ignore[misc]
