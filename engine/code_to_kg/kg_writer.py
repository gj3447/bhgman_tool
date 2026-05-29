"""kg_writer.py — CodeGraph → KG (local JSON store OR Neo4j Cypher).

Two sinks, same graph (bhgman `--local` convention, cf. occam/eureka/hades):
    - write_local(graph, store): MERGE into the stdlib JSON LocalKgStore (offline,
      deterministic, test-friendly, neo4j 0 calls).
    - to_cypher(graph): emit idempotent MERGE statements for the canonical Neo4j
      KG (run via db-query / mcp__neo4j__write_neo4j_cypher).

Isolation + weaving (PROM 16 권고 / user verdict "기존 스키마랑 자유롭게 엮기"):
    - every node carries the umbrella label `:CodeSymbol` → the whole POC graph is
      one removable/queryable set (KG pollution guard).
    - the module node links to any pre-existing `:SourceCodeNode` with the SAME
      sourcePath via `(:CodeSymbol)-[:DERIVED_FROM]->(:SourceCodeNode)` — so
      tree-sitter symbols hang off Longinus's existing file nodes instead of
      forking a parallel universe.

# KG: lesson-prom16-code-to-kg-tools-2026-05-28, SourceCodeNode (weave target),
      bhgman-local-kg-backend-2026-05-28
"""

from __future__ import annotations

try:  # package import (engine.code_to_kg) vs bare-import bridge (pytest conftest)
    from .ts_extractor import CodeGraph, SymbolEdge
except ImportError:  # pragma: no cover
    from ts_extractor import CodeGraph, SymbolEdge  # type: ignore

UMBRELLA_LABEL = "CodeSymbol"
# kind → extra specific label
KIND_LABEL = {
    "module": "CodeModule",
    "class": "CodeClass",
    "function": "CodeFunction",
    "method": "CodeFunction",
}


# ── local JSON store sink ──────────────────────────────────────────────────


def write_local(graph: CodeGraph, store) -> dict:
    """MERGE the CodeGraph into a LocalKgStore. Returns a counts summary.

    `store` is an `engine.kg_local.store.LocalKgStore` (duck-typed: needs
    merge_node / find_one / add_edge). Idempotent on symbol_id.
    """
    node_by_id = {}
    for n in graph.nodes:
        specific = KIND_LABEL.get(n.kind, UMBRELLA_LABEL)
        node = store.merge_node(UMBRELLA_LABEL, "symbol_id", n.symbol_id, n.as_props())
        if specific not in node["labels"]:
            node["labels"].append(specific)
        node_by_id[n.symbol_id] = node

    # weave: module node → existing SourceCodeNode (same sourcePath), if present
    derived = 0
    mod_id = f"{graph.source_path}::<module>"
    if mod_id in node_by_id:
        scn = store.find_one("sourcePath", graph.source_path, "SourceCodeNode")
        if scn is not None:
            store.add_edge(node_by_id[mod_id], "DERIVED_FROM", scn)
            derived += 1

    edge_counts = {"DEFINES": 0, "IMPORTS": 0, "CALLS": 0, "INHERITS": 0}
    for e in graph.edges:
        both_in = e.src in node_by_id and e.dst in node_by_id
        if e.rel == "DEFINES" and both_in:
            store.add_edge(node_by_id[e.src], "DEFINES", node_by_id[e.dst])
            edge_counts["DEFINES"] += 1
        elif e.rel in ("CALLS", "INHERITS") and e.resolved and both_in:
            store.add_edge(node_by_id[e.src], e.rel, node_by_id[e.dst])
            edge_counts[e.rel] += 1
        # unresolved IMPORTS/CALLS/INHERITS (external names) are kept as node
        # properties only in local mode (no synthetic external node) — see
        # to_cypher for the external-stub policy.

    return {
        "nodes_merged": len(node_by_id),
        "derived_from": derived,
        "edges": edge_counts,
        "unresolved": sum(1 for e in graph.edges if not e.resolved),
    }


# ── Neo4j Cypher sink ──────────────────────────────────────────────────────


def to_cypher(graph: CodeGraph, *, include_external: bool = True) -> list[str]:
    """Emit idempotent MERGE statements for the canonical Neo4j KG.

    External IMPORTS/CALLS targets (names not defined in-file) MERGE as lightweight
    `:CodeSymbol:CodeExternal {name}` stubs when include_external — so the import/call
    surface is queryable without claiming a resolved definition.
    """
    stmts: list[str] = []

    for n in graph.nodes:
        specific = KIND_LABEL.get(n.kind, UMBRELLA_LABEL)
        p = n.as_props()
        set_clause = ", ".join(f"s.{k} = {_lit(v)}" for k, v in p.items() if k != "symbol_id")
        stmts.append(
            f"MERGE (s:{UMBRELLA_LABEL} {{symbol_id: {_lit(n.symbol_id)}}}) "
            f"SET s:{specific}, {set_clause}"
        )

    # weave to existing SourceCodeNode (no-op if absent)
    mod_id = f"{graph.source_path}::<module>"
    stmts.append(
        f"MATCH (m:{UMBRELLA_LABEL} {{symbol_id: {_lit(mod_id)}}}) "
        f"MATCH (f:SourceCodeNode {{sourcePath: {_lit(graph.source_path)}}}) "
        f"MERGE (m)-[:DERIVED_FROM]->(f)"
    )

    seen_external: set[str] = set()
    for e in graph.edges:
        if e.rel == "DEFINES":
            stmts.append(_edge_by_id(e, "EXTRACTED"))
        elif e.rel in ("CALLS", "INHERITS") and e.resolved:
            # resolved to an in-set definition (file-local or jedi) = high confidence
            stmts.append(_edge_by_id(e, "EXTRACTED"))
        elif include_external and not e.resolved:
            # external import / unresolved call|inherit → name-only stub = AMBIGUOUS
            if e.dst not in seen_external:
                stmts.append(f"MERGE (x:{UMBRELLA_LABEL}:CodeExternal {{name: {_lit(e.dst)}}})")
                seen_external.add(e.dst)
            stmts.append(
                f"MATCH (a:{UMBRELLA_LABEL} {{symbol_id: {_lit(e.src)}}}) "
                f"MATCH (x:CodeExternal {{name: {_lit(e.dst)}}}) "
                f"MERGE (a)-[r:{e.rel}]->(x) SET r.confidence_tier = 'AMBIGUOUS'"
            )
    return stmts


def _edge_by_id(e: SymbolEdge, tier: str) -> str:
    """MERGE an edge between two in-set symbols, tagging confidence_tier.

    confidence_tier (CRG absorption, aligns with Longinus EXTRACTED/INFERRED/
    AMBIGUOUS enum): resolved-to-definition edges = EXTRACTED.
    """
    return (
        f"MATCH (a:{UMBRELLA_LABEL} {{symbol_id: {_lit(e.src)}}}) "
        f"MATCH (b:{UMBRELLA_LABEL} {{symbol_id: {_lit(e.dst)}}}) "
        f"MERGE (a)-[r:{e.rel}]->(b) SET r.confidence_tier = {_lit(tier)}"
    )


def _lit(v) -> str:
    """Cypher literal for str/int. Strings single-quoted with escaping."""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    s = str(v).replace("\\", "\\\\").replace("'", "\\'")
    return f"'{s}'"


__all__ = ["write_local", "to_cypher", "UMBRELLA_LABEL", "KIND_LABEL"]
