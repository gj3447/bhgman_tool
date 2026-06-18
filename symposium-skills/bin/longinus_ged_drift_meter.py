#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
longinus_ged_drift_meter.py
============================
GED (Graph Edit Distance) drift meter for SYMPOSIUM Longinus reference layer.

Quantifies KG <-> Code drift by computing approximate Graph Edit Distance
between two labeled graphs (e.g., a Knowledge Graph subgraph and a Code AST
graph) using Hungarian bipartite approximation.

Algorithm
---------
- Sanfeliu & Fu (1983) "A Distance Measure between Attributed Relational
  Graphs for Pattern Recognition", IEEE T-SMC 13(3):353-362, defines
  GED(G1, G2) as the minimum total cost of an edit sequence transforming
  G1 into G2 over edit ops {insert_node, delete_node, relabel_node,
  insert_edge, delete_edge, relabel_edge}.
- Riesen & Bunke (2009) "Approximate graph edit distance computation by
  means of bipartite graph matching", Image and Vision Computing
  27(7):950-959, approximates GED via Hungarian assignment on a
  (|V1|+|V2|) x (|V1|+|V2|) cost matrix that combines node substitution
  cost with locally induced edge edit cost.

Severity classification (BHGMAN / Longinus thresholds)
-------------------------------------------------------
- PIERCED   : normalized GED <= 0.05  (essentially identical)
- MINOR     : 0.05 <  ged <= 0.10
- MODERATE  : 0.10 <  ged <= 0.15
- CRITICAL  : 0.15 <  ged           (drift breach)

Input format (JSON / dict)
--------------------------
{
  "nodes": [{"id": "n1", "label": "Foo", "attrs": {...}}, ...],
  "edges": [{"source": "n1", "target": "n2", "label": "DEPENDS_ON"}, ...]
}

CLI
---
    python3 longinus_ged_drift_meter.py \\
        --graph1 a.json --graph2 b.json [--normalize] [--json]

# KG: longinus-ged-drift-meter-2026-05-09
# KG: longinus-hardening-master-plan-2026-05-06 (parent canonical)
# KG: SA_methodology_v4_triple_upgrade (Longinus 7-Layer Reference Model)
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
from scipy.optimize import linear_sum_assignment

# ---------------------------------------------------------------------------
# Constants — BHGMAN / Longinus drift severity thresholds
# ---------------------------------------------------------------------------
THRESHOLD_PIERCED = 0.05
THRESHOLD_MINOR = 0.10
THRESHOLD_MODERATE = 0.15
# > MODERATE => CRITICAL

# Default unit edit costs (Sanfeliu-Fu §III.B uniform-cost variant)
DEFAULT_NODE_INSERT_COST = 1.0
DEFAULT_NODE_DELETE_COST = 1.0
DEFAULT_NODE_RELABEL_COST = 1.0
DEFAULT_EDGE_INSERT_COST = 1.0
DEFAULT_EDGE_DELETE_COST = 1.0
DEFAULT_EDGE_RELABEL_COST = 1.0


# ---------------------------------------------------------------------------
# Graph data model
# ---------------------------------------------------------------------------
@dataclass
class Graph:
    """Lightweight labeled graph (undirected by default for edge multiset).

    `nodes` is an ordered list of (node_id, label) tuples.
    `edges` is a list of (source_idx, target_idx, edge_label) tuples,
    where indices refer to positions in `nodes`.
    """

    nodes: List[Tuple[str, str]] = field(default_factory=list)
    edges: List[Tuple[int, int, str]] = field(default_factory=list)
    directed: bool = False

    @property
    def n(self) -> int:
        return len(self.nodes)

    @property
    def m(self) -> int:
        return len(self.edges)

    def adjacency_labels(self, node_idx: int) -> List[str]:
        """Multiset of incident edge labels for a node (used for star cost)."""
        out: List[str] = []
        for s, t, lbl in self.edges:
            if s == node_idx or t == node_idx:
                out.append(lbl)
        return out

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Graph":
        if not isinstance(d, dict):
            raise ValueError("Graph dict must be a JSON object")
        raw_nodes = d.get("nodes", [])
        raw_edges = d.get("edges", [])
        directed = bool(d.get("directed", False))

        nodes: List[Tuple[str, str]] = []
        id_to_idx: Dict[str, int] = {}
        for i, n in enumerate(raw_nodes):
            if not isinstance(n, dict):
                raise ValueError(f"Node #{i} must be an object")
            if "id" not in n:
                raise ValueError(f"Node #{i} missing 'id'")
            nid = str(n["id"])
            label = str(n.get("label", ""))
            if nid in id_to_idx:
                raise ValueError(f"Duplicate node id: {nid}")
            id_to_idx[nid] = i
            nodes.append((nid, label))

        edges: List[Tuple[int, int, str]] = []
        for j, e in enumerate(raw_edges):
            if not isinstance(e, dict):
                raise ValueError(f"Edge #{j} must be an object")
            src = str(e.get("source"))
            tgt = str(e.get("target"))
            lbl = str(e.get("label", ""))
            if src not in id_to_idx:
                raise ValueError(f"Edge #{j} unknown source: {src}")
            if tgt not in id_to_idx:
                raise ValueError(f"Edge #{j} unknown target: {tgt}")
            edges.append((id_to_idx[src], id_to_idx[tgt], lbl))

        return cls(nodes=nodes, edges=edges, directed=directed)


# ---------------------------------------------------------------------------
# Edit cost model
# ---------------------------------------------------------------------------
@dataclass
class CostModel:
    node_insert: float = DEFAULT_NODE_INSERT_COST
    node_delete: float = DEFAULT_NODE_DELETE_COST
    node_relabel: float = DEFAULT_NODE_RELABEL_COST
    edge_insert: float = DEFAULT_EDGE_INSERT_COST
    edge_delete: float = DEFAULT_EDGE_DELETE_COST
    edge_relabel: float = DEFAULT_EDGE_RELABEL_COST

    def node_subst(self, label1: str, label2: str) -> float:
        if label1 == label2:
            return 0.0
        return self.node_relabel

    def edge_subst(self, label1: str, label2: str) -> float:
        if label1 == label2:
            return 0.0
        return self.edge_relabel


# ---------------------------------------------------------------------------
# Star (local) edge cost — Riesen-Bunke 2009 §3.2
# ---------------------------------------------------------------------------
def _multiset_edit_cost(
    a: Sequence[str], b: Sequence[str], cost: CostModel
) -> float:
    """Approximate edit distance between two label multisets via Hungarian.

    Used as the local edge contribution attached to a node substitution
    (the 'star' around the node). Bounded by max(|a|, |b|) * relabel cost.
    """
    la, lb = list(a), list(b)
    na, nb = len(la), len(lb)
    if na == 0 and nb == 0:
        return 0.0
    size = na + nb
    big = float(
        max(cost.edge_insert, cost.edge_delete, cost.edge_relabel) * (size + 1)
    )
    M = np.full((size, size), big, dtype=float)
    # substitution block
    for i in range(na):
        for j in range(nb):
            M[i, j] = cost.edge_subst(la[i], lb[j])
    # deletion block (a -> eps)
    for i in range(na):
        M[i, nb + i] = cost.edge_delete
    # insertion block (eps -> b)
    for j in range(nb):
        M[na + j, j] = cost.edge_insert
    # eps -> eps block (free)
    for i in range(nb):
        for j in range(na):
            M[na + i, nb + j] = 0.0
    row_ind, col_ind = linear_sum_assignment(M)
    return float(M[row_ind, col_ind].sum())


# ---------------------------------------------------------------------------
# Hungarian bipartite GED approximation (Riesen-Bunke 2009)
# ---------------------------------------------------------------------------
def hungarian_ged(
    g1: Graph, g2: Graph, cost: Optional[CostModel] = None
) -> Tuple[float, List[Tuple[Optional[int], Optional[int]]]]:
    """Compute approximate GED via Hungarian assignment on the
    (n1+n2) x (n1+n2) cost matrix.

    Returns (ged_value, mapping) where mapping is a list of
    (i, j) pairs with i in [0..n1) or None (epsilon), j in [0..n2) or None.
    """
    cost = cost or CostModel()
    n1, n2 = g1.n, g2.n
    size = n1 + n2

    if size == 0:
        return 0.0, []

    # Pre-compute incident edge labels per node
    star1 = [g1.adjacency_labels(i) for i in range(n1)]
    star2 = [g2.adjacency_labels(j) for j in range(n2)]

    big = float(
        max(
            cost.node_insert,
            cost.node_delete,
            cost.node_relabel,
            cost.edge_insert,
            cost.edge_delete,
            cost.edge_relabel,
        )
        * (size + g1.m + g2.m + 1)
    )
    C = np.full((size, size), big, dtype=float)

    # Top-left: substitutions (n1 x n2)
    for i in range(n1):
        for j in range(n2):
            node_part = cost.node_subst(g1.nodes[i][1], g2.nodes[j][1])
            edge_part = _multiset_edit_cost(star1[i], star2[j], cost)
            # Star cost is divided by 2 because each edge is shared by
            # two endpoints in undirected case. Riesen-Bunke 2009 eq.6.
            C[i, j] = node_part + edge_part / 2.0

    # Top-right: deletion (n1 x n2 epsilon columns) — diagonal
    for i in range(n1):
        # cost of deleting node i + deleting all its incident edges
        edge_del_cost = len(star1[i]) * cost.edge_delete / 2.0
        C[i, n2 + i] = cost.node_delete + edge_del_cost

    # Bottom-left: insertion (n2 epsilon rows x n2)
    for j in range(n2):
        edge_ins_cost = len(star2[j]) * cost.edge_insert / 2.0
        C[n1 + j, j] = cost.node_insert + edge_ins_cost

    # Bottom-right: epsilon -> epsilon (free)
    for i in range(n2):
        for j in range(n1):
            C[n1 + i, n2 + j] = 0.0

    row_ind, col_ind = linear_sum_assignment(C)

    # Reconstruct logical mapping (i_in_g1 or None, j_in_g2 or None)
    mapping: List[Tuple[Optional[int], Optional[int]]] = []
    for r, c in zip(row_ind, col_ind):
        i = r if r < n1 else None
        j = c if c < n2 else None
        if i is None and j is None:
            continue
        mapping.append((i, j))

    # Riesen-Bunke gives a UPPER BOUND via assignment sum. Use as approximation.
    node_part_sum = float(C[row_ind, col_ind].sum())

    # Edge correction: recompute exact edge cost induced by mapping to avoid
    # double-counting from star halving when both endpoints are matched.
    edge_cost = _induced_edge_cost(g1, g2, mapping, cost)

    # The sum C already contains halved star contributions for substitutions.
    # We replace star-derived edge contribution with the exact induced cost
    # for tighter accuracy on small graphs.
    node_only_sum = 0.0
    for r, c in zip(row_ind, col_ind):
        if r < n1 and c < n2:
            node_only_sum += cost.node_subst(g1.nodes[r][1], g2.nodes[c][1])
        elif r < n1 and c >= n2:
            node_only_sum += cost.node_delete
        elif r >= n1 and c < n2:
            node_only_sum += cost.node_insert
        # else: free

    ged = node_only_sum + edge_cost
    # Sanity: assignment-sum is also a valid upper bound; keep min.
    ged = min(ged, node_part_sum)
    return ged, mapping


def _induced_edge_cost(
    g1: Graph,
    g2: Graph,
    mapping: List[Tuple[Optional[int], Optional[int]]],
    cost: CostModel,
) -> float:
    """Exact edge-edit cost induced by a fixed node mapping.

    Each edge (u, v, lbl) in g1 maps to (f(u), f(v)) in g2; if both endpoints
    matched and an edge with same label exists -> 0; if labels differ ->
    relabel; if no such edge -> delete. Symmetric for g2 -> insert.
    """
    f1to2: Dict[int, Optional[int]] = {}
    f2to1: Dict[int, Optional[int]] = {}
    for i, j in mapping:
        if i is not None:
            f1to2[i] = j
        if j is not None:
            f2to1[j] = i

    def canon(a: int, b: int, directed: bool) -> Tuple[int, int]:
        return (a, b) if directed else (min(a, b), max(a, b))

    edges2_map: Dict[Tuple[int, int], List[str]] = {}
    for s, t, lbl in g2.edges:
        key = canon(s, t, g2.directed)
        edges2_map.setdefault(key, []).append(lbl)

    used2: set = set()
    total = 0.0

    for s, t, lbl in g1.edges:
        fs = f1to2.get(s)
        ft = f1to2.get(t)
        if fs is None or ft is None:
            # at least one endpoint deleted -> edge deleted
            total += cost.edge_delete
            continue
        key = canon(fs, ft, g1.directed)
        # find an unused matching edge in g2 with same key
        candidates = edges2_map.get(key, [])
        match_idx = None
        for k, lbl2 in enumerate(candidates):
            if (key, k) in used2:
                continue
            match_idx = k
            break
        if match_idx is None:
            total += cost.edge_delete
        else:
            used2.add((key, match_idx))
            total += cost.edge_subst(lbl, candidates[match_idx])

    # Remaining g2 edges -> insertions
    for s, t, lbl in g2.edges:
        key = canon(s, t, g2.directed)
        # find first unused
        pool = edges2_map.get(key, [])
        # we already consumed entries by index in `used2`
        # count unused
        for k, lbl2 in enumerate(pool):
            if (key, k) in used2:
                continue
            # Determine if both endpoints are images of g1 nodes
            rs = f2to1.get(s)
            rt = f2to1.get(t)
            if rs is not None and rt is not None:
                # both endpoints came from g1 but no g1-edge matched -> insert
                total += cost.edge_insert
            else:
                total += cost.edge_insert
            used2.add((key, k))

    return total


# ---------------------------------------------------------------------------
# Severity classification
# ---------------------------------------------------------------------------
def classify_severity(normalized_ged: float) -> str:
    if normalized_ged <= THRESHOLD_PIERCED:
        return "PIERCED"
    if normalized_ged <= THRESHOLD_MINOR:
        return "MINOR"
    if normalized_ged <= THRESHOLD_MODERATE:
        return "MODERATE"
    return "CRITICAL"


def normalize_ged(raw_ged: float, g1: Graph, g2: Graph) -> float:
    """Normalize by the maximum possible edit cost (full delete + insert)."""
    max_cost = float(
        g1.n + g2.n + g1.m + g2.m
    )  # uniform unit cost upper bound
    if max_cost <= 0:
        return 0.0
    return raw_ged / max_cost


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def measure_drift(
    graph1: Dict[str, Any] | Graph,
    graph2: Dict[str, Any] | Graph,
    cost: Optional[CostModel] = None,
    normalize: bool = True,
) -> Dict[str, Any]:
    """One-shot drift measurement entry point.

    Returns dict with raw_ged, normalized_ged, severity, mapping_size, n1, n2.
    """
    g1 = graph1 if isinstance(graph1, Graph) else Graph.from_dict(graph1)
    g2 = graph2 if isinstance(graph2, Graph) else Graph.from_dict(graph2)
    raw, mapping = hungarian_ged(g1, g2, cost=cost)
    norm = normalize_ged(raw, g1, g2) if normalize else raw
    severity = classify_severity(norm if normalize else min(norm, 1.0))
    return {
        "raw_ged": raw,
        "normalized_ged": norm,
        "severity": severity,
        "mapping_size": len(mapping),
        "n1": g1.n,
        "n2": g2.n,
        "m1": g1.m,
        "m2": g2.m,
        "algorithm": "Hungarian bipartite (Riesen-Bunke 2009)",
        "thresholds": {
            "PIERCED": THRESHOLD_PIERCED,
            "MINOR": THRESHOLD_MINOR,
            "MODERATE": THRESHOLD_MODERATE,
        },
    }


# ---------------------------------------------------------------------------
# Smoke test
# ---------------------------------------------------------------------------
def _smoke_graph_a() -> Dict[str, Any]:
    return {
        "nodes": [
            {"id": "n1", "label": "Foo"},
            {"id": "n2", "label": "Bar"},
            {"id": "n3", "label": "Baz"},
        ],
        "edges": [
            {"source": "n1", "target": "n2", "label": "DEPENDS_ON"},
            {"source": "n2", "target": "n3", "label": "DEPENDS_ON"},
        ],
    }


def _smoke_graph_b_one_edge_diff() -> Dict[str, Any]:
    # same nodes; one edge has different label (DEPENDS_ON -> CALLS)
    return {
        "nodes": [
            {"id": "n1", "label": "Foo"},
            {"id": "n2", "label": "Bar"},
            {"id": "n3", "label": "Baz"},
        ],
        "edges": [
            {"source": "n1", "target": "n2", "label": "DEPENDS_ON"},
            {"source": "n2", "target": "n3", "label": "CALLS"},
        ],
    }


def run_smoke() -> Dict[str, Any]:
    a = _smoke_graph_a()
    b_identity = _smoke_graph_a()
    b_diff = _smoke_graph_b_one_edge_diff()
    r_id = measure_drift(a, b_identity, normalize=True)
    r_diff = measure_drift(a, b_diff, normalize=True)
    return {
        "identity": r_id,
        "1-edge-diff": r_diff,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(
        prog="longinus_ged_drift_meter",
        description=(
            "GED drift meter (Sanfeliu-Fu 1983 / Riesen-Bunke 2009). "
            "Measures KG <-> Code drift via Hungarian bipartite GED."
        ),
    )
    p.add_argument("--graph1", help="Path to graph1 JSON")
    p.add_argument("--graph2", help="Path to graph2 JSON")
    p.add_argument(
        "--normalize",
        action="store_true",
        default=True,
        help="Normalize GED to [0,1] (default: on)",
    )
    p.add_argument(
        "--no-normalize",
        dest="normalize",
        action="store_false",
        help="Disable normalization",
    )
    p.add_argument(
        "--json",
        action="store_true",
        help="Output result as JSON to stdout",
    )
    p.add_argument(
        "--smoke",
        action="store_true",
        help="Run built-in smoke test and exit",
    )
    args = p.parse_args(argv)

    if args.smoke:
        result = run_smoke()
        print(json.dumps(result, indent=2))
        # exit 0 if identity == 0 else 1
        return 0 if result["identity"]["raw_ged"] == 0.0 else 1

    if not args.graph1 or not args.graph2:
        p.error("--graph1 and --graph2 are required (or use --smoke)")

    g1 = _load_json(args.graph1)
    g2 = _load_json(args.graph2)
    result = measure_drift(g1, g2, normalize=args.normalize)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"raw_ged          = {result['raw_ged']:.4f}")
        print(f"normalized_ged   = {result['normalized_ged']:.4f}")
        print(f"severity         = {result['severity']}")
        print(f"|V1|,|V2|        = {result['n1']}, {result['n2']}")
        print(f"|E1|,|E2|        = {result['m1']}, {result['m2']}")
        print(f"algorithm        = {result['algorithm']}")
    # exit code: 0 if PIERCED/MINOR, 1 if MODERATE/CRITICAL
    return 0 if result["severity"] in ("PIERCED", "MINOR") else 1


if __name__ == "__main__":
    sys.exit(main())
