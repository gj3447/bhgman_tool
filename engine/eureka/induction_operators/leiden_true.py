"""True-Leiden community induction operator (opt-in upgrade over offline CNM).

The default offline operator (``leiden_llm.induce_leiden_llm``) is deterministic
greedy modularity (Newman 2004 / Clauset-Newman-Moore) — the same *family* as
Leiden but **not the Leiden algorithm itself**. This operator runs the genuine
**Leiden algorithm** (Traag-Waltman-vanEck 2019) via ``leidenalg`` + ``igraph``,
which additionally guarantees well-connected communities (Louvain/CNM can split
a community into disconnected pieces).

Same input (formal context ``{object → attribute set}``), same output
(``FcaResult`` of ``FormalConcept``) — a drop-in for the CNM operator, so a
bake-off compares algorithm quality on identical I/O. Reuses the shared
similarity-graph + concept-assembly helpers from ``leiden_llm``.

Requires the optional ``leidenalg``/``python-igraph`` deps
(``pip install bhgman_tool[eureka-leiden]``). Absent → raise a clear error so
the caller can fall back to the no-dep CNM operator.

# KG: eureka-canonical-2026-05-26, consensus-eureka-academic-grounding-2026-05-26 (Leiden-LLM C-line)
"""

from __future__ import annotations

from collections.abc import Mapping

from engine.eureka.induction_operators.fca import FcaResult
from engine.eureka.induction_operators.leiden_llm import (
    MAX_NODES,
    _build_similarity_graph,
    assemble_fca,
)


def _true_leiden_communities(
    objs: list[str],
    adj: dict[str, dict[str, int]],
    resolution: float,
    seed: int,
) -> list[frozenset[str]]:
    """Genuine Leiden partition of the weighted similarity graph (deterministic via seed)."""
    import igraph
    import leidenalg

    idx = {o: i for i, o in enumerate(objs)}
    edges: list[tuple[int, int]] = []
    weights: list[int] = []
    seen: set[tuple[int, int]] = set()
    for o in objs:
        for nb, w in adj[o].items():
            e = (idx[o], idx[nb]) if idx[o] < idx[nb] else (idx[nb], idx[o])
            if e in seen:
                continue
            seen.add(e)
            edges.append(e)
            weights.append(w)
    graph = igraph.Graph(n=len(objs), edges=edges)
    if weights:
        graph.es["weight"] = weights
    part = leidenalg.find_partition(
        graph,
        leidenalg.RBConfigurationVertexPartition,
        weights="weight" if weights else None,
        resolution_parameter=resolution,
        seed=seed,
    )
    return [frozenset(objs[i] for i in comm) for comm in part]


def induce_leiden_true(
    context: Mapping[str, frozenset[str]],
    *,
    resolution: float = 1.0,
    min_extent: int = 2,
    min_stability: float = 0.0,
    max_nodes: int = MAX_NODES,
    seed: int = 42,
) -> FcaResult:
    """formal context → genuine Leiden community induction → FcaResult(FormalConcept).

    Drop-in for induce_leiden_llm; same pruning/sort. >max_nodes → gds.leiden fallback.
    """
    try:
        import igraph  # noqa: F401
        import leidenalg  # noqa: F401
    except ImportError as e:  # pragma: no cover - optional dep
        raise RuntimeError(
            "induce_leiden_true needs leidenalg+igraph — pip install bhgman_tool[eureka-leiden] "
            "(or use induce_leiden_llm, the no-dep offline CNM operator)"
        ) from e

    if len(context) > max_nodes:
        return FcaResult(
            concepts=(),
            pruned=0,
            fallback_reason=(
                f"context size {len(context)} > max_nodes {max_nodes}; "
                "delegate to gds.leiden (γ-sweep) for this scale"
            ),
        )

    objs, adj = _build_similarity_graph(context)
    communities = _true_leiden_communities(objs, adj, resolution, seed)
    return assemble_fca(
        communities, context, adj, min_extent=min_extent, min_stability=min_stability
    )


__all__ = ["induce_leiden_true"]
