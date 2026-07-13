"""Tests — spreading-activation retrieval over the traffic-emerged Hebbian graph.

engineboy vision realised: retrieval is a random-walk-with-restart (Personalized PageRank)
over edges whose weights EMERGED from co-access traffic (HeLa-Mem / Spreading-Activation
KG-RAG, arXiv:2604.16839 / 2512.15922). Two-stage = vector seed (P1) → PPR spread (P2),
the HippoRAG2 recipe fused with traffic weights.

# KG: finding-prom16-hela-mem-hebbian-engineboy-realized-2026-07-13,
#     finding-prom16-hipporag2-embedding-populate-gap-2026-07-13
"""

from __future__ import annotations

from engine.emergence import EmergenceEngine
from engine.emergence.activation import (
    Activation,
    spreading_activation,
    two_stage_retrieve,
)
from engine.emergence.protocols import AccessEvent


def _co_access(eng: EmergenceEngine, a: str, b: str, n: int, start: float = 0.0) -> None:
    """Drive n co-access events between a and b → an emerged Hebbian edge."""
    for i in range(n):
        eng.ingest(
            AccessEvent(event_id=f"{a}-{b}-{i}", element_key=a, actor="human",
                        ts=start + i, co_keys=(b,))
        )


def test_empty_seeds_returns_nothing() -> None:
    eng = EmergenceEngine()
    assert spreading_activation(eng, {}, t=10.0) == []
    assert spreading_activation(eng, {"ghost": 1.0}, t=10.0) == []  # seed absent from graph


def test_activation_spreads_to_traffic_neighbor() -> None:
    eng = EmergenceEngine()
    _co_access(eng, "A", "B", n=5)
    out = spreading_activation(eng, {"A": 1.0}, t=6.0, steps=2, top_k=10)
    keys = [a.node_key for a in out]
    assert "A" in keys  # seed retained (restart mass)
    assert "B" in keys  # reached via emerged edge
    assert all(isinstance(a, Activation) for a in out)


def test_stronger_traffic_edge_ranks_neighbor_higher() -> None:
    eng = EmergenceEngine()
    _co_access(eng, "A", "B", n=8)  # strong co-access
    _co_access(eng, "A", "C", n=1)  # weak co-access
    out = spreading_activation(eng, {"A": 1.0}, t=9.0, steps=2, top_k=10)
    rank = {a.node_key: a.activation for a in out}
    assert rank["B"] > rank["C"]  # traffic weight orders retrieval


def test_namespace_isolation_excludes_private() -> None:
    eng = EmergenceEngine()
    _co_access(eng, "A", "B", n=3)
    eng.ingest(
        AccessEvent(event_id="priv-1", element_key="secret", actor="alice",
                    ts=10.0, co_keys=("A",), acl="private")
    )
    out = spreading_activation(eng, {"A": 1.0}, t=11.0, namespace="shared", top_k=20)
    keys = [a.node_key for a in out]
    assert not any("tenant:" in k or k == "secret" for k in keys)


def test_two_stage_retrieve_uses_seed_fn_then_spreads() -> None:
    eng = EmergenceEngine()
    _co_access(eng, "A", "B", n=5)
    # seed_fn = the vector stage (P1); here a fixed stub mapping query → seed similarities
    def seed_fn(_query: str) -> dict[str, float]:
        return {"A": 0.9, "C": 0.1}

    out = two_stage_retrieve(eng, "some query", seed_fn, t=6.0, k_seed=1, top_k=10)
    keys = [a.node_key for a in out]
    assert "A" in keys and "B" in keys  # top-1 seed A, spread to B


def test_recency_reorders_via_decay() -> None:
    # PPR transitions are row-normalised, so decay shows up in *relative* allocation between
    # competing edges: a recently-reinforced neighbor out-draws an equally-frequent but stale one.
    eng = EmergenceEngine()
    _co_access(eng, "A", "B", n=4, start=0.0)     # old co-access (~t=3)
    _co_access(eng, "A", "C", n=4, start=100.0)   # recent co-access (~t=103)
    out = {a.node_key: a.activation for a in spreading_activation(eng, {"A": 1.0}, t=104.0)}
    assert out["C"] > out["B"]  # the decayed old edge yields less activation than the fresh one
