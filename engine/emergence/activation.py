"""Spreading-activation retrieval over the traffic-emerged Hebbian graph.

The emergence engine turns co-access traffic into weighted Hebbian edges (Hawkes decay).
Retrieval is then a random-walk-with-restart (Personalized PageRank) over those *emerged*
weights: activation starts at the seed set, spreads through high-traffic edges, decays through
weak ones. This is the engineboy vision made operational — weights that emerged from search
traffic (human+AI) drive retrieval, not a static PageRank (HeLa-Mem arXiv:2604.16839,
Spreading-Activation KG-RAG arXiv:2512.15922).

`two_stage_retrieve` fuses it with a vector seed stage (`seed_fn`): kNN over the populated
embedding index proposes seeds, PPR over traffic weights expands them — the HippoRAG2 recipe
(vector seed → PPR) with traffic-emerged edges instead of a fixed graph. `seed_fn` is injected
so the (heavy) embedding stage stays decoupled and this core is pure + testable.

Respects the Visibility invariant: retrieval defaults to the `shared` (upper-world) namespace,
so private/tenant elements never leak into a shared spread (D3 ACL).

Pure-python (stdlib only).

# KG: finding-prom16-hela-mem-hebbian-engineboy-realized-2026-07-13,
#     finding-prom16-hipporag2-embedding-populate-gap-2026-07-13,
#     engineboy-emergence-engine-fsm-design-2026-07-13
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from engine.emergence import hawkes
from engine.emergence.engine import EmergenceEngine

# query text -> {node_key: seed_score}. The vector (P1) stage plugs in here.
SeedFn = Callable[[str], Mapping[str, float]]


@dataclass(frozen=True)
class Activation:
    # KG: engineboy-emergence-engine-fsm-design-2026-07-13
    node_key: str
    activation: float


def _adjacency(
    engine: EmergenceEngine, t: float, namespace: str | None
) -> dict[str, list[tuple[str, float]]]:
    """Undirected adjacency with time-decayed edge weights (edges with w≤0 drop out)."""
    adj: dict[str, list[tuple[str, float]]] = {}
    for e in engine.edges.values():
        if e.src is None or e.dst is None:
            continue
        if namespace is not None and e.namespace != namespace:
            continue
        w = hawkes.decayed_weight(e.w, e.t_last, t, engine.cfg.lam)
        if w <= 0.0:
            continue
        adj.setdefault(e.src, []).append((e.dst, w))
        adj.setdefault(e.dst, []).append((e.src, w))
    return adj


def spreading_activation(
    engine: EmergenceEngine,
    seeds: Mapping[str, float],
    *,
    t: float,
    steps: int = 2,
    damping: float = 0.85,
    top_k: int = 10,
    namespace: str | None = "shared",
) -> list[Activation]:
    # KG: finding-prom16-hela-mem-hebbian-engineboy-realized-2026-07-13
    """Personalized PageRank over traffic-emerged edges, restarting to `seeds`.

    a ← damping·(Wᵀa) + (1−damping)·p, where p is the seed distribution and W is the
    row-normalised (traffic-weighted, time-decayed) transition matrix. `steps` = hops.
    Seeds absent from the graph (or outside `namespace`) are dropped. Returns nodes ranked by
    accumulated activation, top_k."""
    p = {
        k: v
        for k, v in seeds.items()
        if v > 0.0
        and k in engine.nodes
        and (namespace is None or engine.nodes[k].namespace == namespace)
    }
    total = sum(p.values())
    if total <= 0.0:
        return []
    p = {k: v / total for k, v in p.items()}

    adj = _adjacency(engine, t, namespace)
    a: dict[str, float] = dict(p)
    for _ in range(max(0, steps)):
        nxt: dict[str, float] = {k: (1.0 - damping) * pv for k, pv in p.items()}
        for i, ai in a.items():
            neigh = adj.get(i)
            if not neigh:
                continue
            deg = sum(w for _, w in neigh)
            if deg <= 0.0:
                continue
            share = damping * ai
            for j, w in neigh:
                nxt[j] = nxt.get(j, 0.0) + share * (w / deg)
        a = nxt

    ranked = sorted(a.items(), key=lambda kv: kv[1], reverse=True)
    return [Activation(k, v) for k, v in ranked[:top_k] if v > 0.0]


def two_stage_retrieve(
    engine: EmergenceEngine,
    query: str,
    seed_fn: SeedFn,
    *,
    t: float,
    k_seed: int = 5,
    top_k: int = 10,
    steps: int = 2,
    damping: float = 0.85,
    namespace: str | None = "shared",
) -> list[Activation]:
    # KG: finding-prom16-hipporag2-embedding-populate-gap-2026-07-13
    """HippoRAG2 recipe: vector-seed (`seed_fn`) → PPR spread over traffic weights.

    `seed_fn(query)` returns candidate {node_key: similarity} (the embedding kNN stage). The
    top `k_seed` become the PPR restart distribution."""
    scored = seed_fn(query)
    top = dict(sorted(scored.items(), key=lambda kv: kv[1], reverse=True)[:k_seed])
    return spreading_activation(
        engine, top, t=t, steps=steps, damping=damping, top_k=top_k, namespace=namespace
    )


__all__ = ["Activation", "SeedFn", "spreading_activation", "two_stage_retrieve"]
