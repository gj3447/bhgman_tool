"""enrich.py — cross-file CALLS resolution via jedi (LSP-grade name resolution).

PROM 16 A4 pitfall: tree-sitter strips semantic binding, so `ts_extractor`'s
file-local CALLS resolution misses cross-file calls (`from lib import helper;
helper()`). This enrichment pass uses **jedi** — the static-analysis engine behind
jedi-language-server — to goto-definition each unresolved call site and map it to a
`:CodeSymbol` defined elsewhere in the ingested set.

Why jedi (not a full LSP server / Stack Graphs):
    - lightweight, pure-Python, pip-only — same dependency philosophy that picked
      tree-sitter over Joern (no JVM, no daemon).
    - jedi *is* the LSP backend, so this is the "LSP enrichment" path. Stack Graphs
      (Rust, GitHub Semantic) remains the heavier alternative for scale name-binding.

Operates on a *set* of CodeGraphs (cross-file needs the whole project). Graceful
import: without jedi, enrich_calls is a no-op that reports jedi_available=False.

# KG: lesson-prom16-code-to-kg-tools-2026-05-28 (A4 semantic-binding pitfall),
      artifact-code-to-kg-poc2-tree-sitter-2026-05-29
"""

from __future__ import annotations

from pathlib import Path

try:
    from .ts_extractor import CodeGraph, SymbolEdge
except ImportError:  # pragma: no cover - bare-import bridge (pytest conftest)
    from engine.code_to_kg.ts_extractor import CodeGraph, SymbolEdge  # type: ignore

try:
    import jedi

    JEDI_AVAILABLE = True
except Exception:  # pragma: no cover - exercised only when dep absent
    jedi = None  # type: ignore
    JEDI_AVAILABLE = False


def _abs(path: str) -> str:
    try:
        return str(Path(path).resolve())
    except Exception:  # pragma: no cover - defensive
        return path


def _build_def_index(graphs: list[CodeGraph]) -> dict[tuple[str, int], str]:
    """(abs_path, def_line) → symbol_id for every function/method/class definition.

    jedi.goto returns a definition's (module_path, line); our SymbolNode stores
    (sourcePath, start_line) at the same def line, so this index is the join.
    Classes are included so INHERITS edges resolve cross-file too.
    """
    index: dict[tuple[str, int], str] = {}
    for g in graphs:
        for n in g.nodes:
            if n.kind in ("function", "method", "class"):
                index[(_abs(n.source_path), n.start_line)] = n.symbol_id
    return index


def enrich_calls(graphs: list[CodeGraph]) -> dict:
    """Resolve cross-file CALLS edges in place via jedi. Returns a counts summary.

    Only edges that are (a) CALLS, (b) still unresolved after the file-local pass,
    and (c) carry a call-site position are attempted. A jedi goto that lands on a
    definition present in the ingested set rewrites the edge to resolved.
    """
    if not JEDI_AVAILABLE:
        return {"jedi_available": False, "attempted": 0, "newly_resolved": 0}

    index = _build_def_index(graphs)
    attempted = 0
    newly_resolved = 0

    for g in graphs:
        new_edges: list[SymbolEdge] = []
        for e in g.edges:
            target = _try_resolve(e, g, index, script_getter=lambda: _script(g))
            if target is _UNCHANGED:
                new_edges.append(e)
                continue
            attempted += 1
            if target is not None:
                new_edges.append(
                    SymbolEdge(e.src, e.rel, target, resolved=True, line=e.line, col=e.col)
                )
                newly_resolved += 1
            else:
                new_edges.append(e)
        g.edges = new_edges

    return {
        "jedi_available": True,
        "attempted": attempted,
        "newly_resolved": newly_resolved,
    }


_UNCHANGED = object()  # sentinel: edge is not an enrichment candidate


_ENRICHABLE = ("CALLS", "INHERITS")


def _try_resolve(edge: SymbolEdge, graph: CodeGraph, index, script_getter):
    """Return symbol_id (resolved), None (attempted, no hit), or _UNCHANGED."""
    if edge.rel not in _ENRICHABLE or edge.resolved or edge.line is None or edge.col is None:
        return _UNCHANGED
    script = script_getter()
    if script is None:
        return None
    try:
        defs = script.goto(edge.line, edge.col, follow_imports=True)
    except Exception:  # noqa: BLE001 - jedi raises on odd positions; treat as miss
        return None
    for d in defs:
        if d.module_path is None or d.line is None:
            continue
        hit = index.get((_abs(str(d.module_path)), d.line))
        if hit is not None and hit != edge.src:
            return hit
    return None


_SCRIPT_CACHE: dict[str, object] = {}


def _script(graph: CodeGraph):
    """jedi.Script for a graph's source file, cached. None if path is not a file."""
    path = graph.source_path
    if path in _SCRIPT_CACHE:
        return _SCRIPT_CACHE[path]
    p = Path(path)
    script = jedi.Script(path=str(p)) if p.is_file() else None
    _SCRIPT_CACHE[path] = script
    return script


__all__ = ["enrich_calls", "JEDI_AVAILABLE"]
