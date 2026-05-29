"""ts_extractor.py — tree-sitter Python symbol extraction (POC 2 core).

Pure, offline, deterministic. No Neo4j, no network. Parses Python source into a
`CodeGraph` of `:CodeSymbol` nodes (module / class / function) plus DEFINES /
IMPORTS / CALLS edges. The KG writer (`kg_writer.py`) consumes this graph.

Symbol identity is a stable string `sourcePath::qualname` so re-ingesting the
same file MERGEs (idempotent) rather than duplicating — matching the existing
`:SourceCodeNode` convention (key = sourcePath) and the Longinus 7-tuple
ReferenceSite anchoring.

CALLS resolution is intentionally *best-effort by callee name* within the file
scope (PROM 16 A4 pitfall: tree-sitter strips semantic binding; full name
resolution needs LSP/Stack Graphs — deferred to a secondary enrichment pass).

# KG: lesson-prom16-code-to-kg-tools-2026-05-28, fp16lag-B4-impl-trends,
      rf-d10-functor-morphism-20260415 (partial functor: morphisms now captured)
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

try:  # graceful import (Longinus adapter convention, Wave 7a)
    import tree_sitter_python as _tsp
    from tree_sitter import Language, Node, Parser

    _PY_LANGUAGE = Language(_tsp.language())
    TREE_SITTER_AVAILABLE = True
except Exception:  # pragma: no cover - exercised only when dep absent
    _PY_LANGUAGE = None
    Node = object  # type: ignore
    TREE_SITTER_AVAILABLE = False


# ── data model ────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class SymbolNode:
    """One `:CodeSymbol` node. kind ∈ {module, class, function, method}."""

    symbol_id: str  # stable: f"{source_path}::{qualname}"
    name: str  # bare name, e.g. "foo"
    qualname: str  # dotted path within file, e.g. "Bar.foo"
    kind: str
    source_path: str
    start_line: int  # 1-indexed (Longinus convention)
    end_line: int
    sha256: str  # hash of the symbol's source span (drift baseline)
    language: str = "python"

    def as_props(self) -> dict:
        return {
            "symbol_id": self.symbol_id,
            "name": self.name,
            "qualname": self.qualname,
            "kind": self.kind,
            "sourcePath": self.source_path,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "sha256": self.sha256,
            "language": self.language,
        }


@dataclass(frozen=True)
class SymbolEdge:
    """A morphism: DEFINES | IMPORTS | CALLS. src/dst are symbol_id or raw name."""

    src: str
    rel: str
    dst: str
    resolved: bool = True  # False = unresolved name (best-effort CALLS/IMPORTS)
    # call-site position (1-indexed line, 0-indexed col) — only set on CALLS edges,
    # consumed by the jedi enrichment pass (enrich.py) for cross-file resolution.
    line: Optional[int] = None
    col: Optional[int] = None


@dataclass
class CodeGraph:
    source_path: str
    nodes: list[SymbolNode] = field(default_factory=list)
    edges: list[SymbolEdge] = field(default_factory=list)

    def node_count(self) -> int:
        return len(self.nodes)

    def edges_of(self, rel: str) -> list[SymbolEdge]:
        return [e for e in self.edges if e.rel == rel]


# ── helpers ───────────────────────────────────────────────────────────────


def _sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _text(node: "Node", src: bytes) -> str:
    return src[node.start_byte : node.end_byte].decode("utf-8", "replace")


def _name_of(node: "Node", src: bytes) -> Optional[str]:
    """Return the identifier text of a def/class node's `name` child."""
    name_node = node.child_by_field_name("name")
    return _text(name_node, src) if name_node is not None else None


# ── core extraction ───────────────────────────────────────────────────────


@dataclass
class _Ctx:
    """Walk context: where we are in the symbol tree."""

    parent_id: str
    qual_prefix: str
    enclosing_func: Optional[str]


class _PyWalker:
    """Single-pass tree-sitter walk → CodeGraph. Split per node-kind to keep each
    method's cognitive complexity low (complexipy ≤ 15 ratchet)."""

    def __init__(self, src: bytes, source_path: str, graph: CodeGraph, mod_id: str):
        self.src = src
        self.source_path = source_path
        self.graph = graph
        self.mod_id = mod_id

    def walk(self, node: "Node", ctx: _Ctx) -> None:
        for child in node.named_children:
            ctype = child.type
            if ctype in ("function_definition", "class_definition"):
                self._on_definition(child, ctype, ctx)
            elif ctype in ("import_statement", "import_from_statement"):
                self._on_import(child, ctx)
            elif ctype == "call" and ctx.enclosing_func is not None:
                self._on_call(child, ctx)
            else:
                self.walk(child, ctx)

    def _on_definition(self, child: "Node", ctype: str, ctx: _Ctx) -> None:
        name = _name_of(child, self.src)
        if name is None:
            return
        qualname = f"{ctx.qual_prefix}{name}" if ctx.qual_prefix else name
        is_class = ctype == "class_definition"
        kind = "class" if is_class else ("method" if ctx.qual_prefix else "function")
        sym_id = f"{self.source_path}::{qualname}"
        span = self.src[child.start_byte : child.end_byte]
        self.graph.nodes.append(
            SymbolNode(
                symbol_id=sym_id,
                name=name,
                qualname=qualname,
                kind=kind,
                source_path=self.source_path,
                start_line=child.start_point[0] + 1,
                end_line=child.end_point[0] + 1,
                sha256=_sha256(span),
            )
        )
        self.graph.edges.append(SymbolEdge(ctx.parent_id, "DEFINES", sym_id))
        if is_class:  # INHERITS edges (CRG absorption: type hierarchy)
            for base, line, col in _base_refs(child, self.src):
                self.graph.edges.append(
                    SymbolEdge(sym_id, "INHERITS", base, resolved=False, line=line, col=col)
                )
        # functions/methods become the enclosing scope for nested CALLS
        new_enclosing = ctx.enclosing_func if is_class else sym_id
        self.walk(child, _Ctx(sym_id, f"{qualname}.", new_enclosing))

    def _on_import(self, child: "Node", ctx: _Ctx) -> None:
        for mod in _imported_modules(child, self.src):
            self.graph.edges.append(SymbolEdge(self.mod_id, "IMPORTS", mod, resolved=False))
        self.walk(child, ctx)

    def _on_call(self, child: "Node", ctx: _Ctx) -> None:
        ref = _callee_ref(child, self.src)
        if ref is not None:
            name, line, col = ref
            self.graph.edges.append(
                SymbolEdge(ctx.enclosing_func, "CALLS", name, resolved=False, line=line, col=col)
            )
        self.walk(child, ctx)


def _resolve_calls(graph: CodeGraph) -> None:
    """Second pass: resolve CALLS → file-local function/method and INHERITS →
    file-local class, by bare name (best-effort, file-local scope)."""
    callable_by_name: dict[str, str] = {}
    class_by_name: dict[str, str] = {}
    for n in graph.nodes:
        if n.kind in ("function", "method"):
            callable_by_name.setdefault(n.name, n.symbol_id)
        elif n.kind == "class":
            class_by_name.setdefault(n.name, n.symbol_id)

    def _resolved(e: SymbolEdge) -> SymbolEdge:
        if e.rel == "CALLS" and e.dst in callable_by_name:
            return SymbolEdge(e.src, "CALLS", callable_by_name[e.dst], True, e.line, e.col)
        if e.rel == "INHERITS" and e.dst in class_by_name:
            return SymbolEdge(e.src, "INHERITS", class_by_name[e.dst], True, e.line, e.col)
        return e

    graph.edges = [_resolved(e) for e in graph.edges]


def extract_python_source(source: str, source_path: str = "<memory>") -> CodeGraph:
    """Extract a CodeGraph from Python source text. Pure / offline."""
    if not TREE_SITTER_AVAILABLE:  # pragma: no cover
        raise RuntimeError(
            "tree-sitter not installed. `pip install tree-sitter tree-sitter-python`"
        )

    src = source.encode("utf-8")
    tree = Parser(_PY_LANGUAGE).parse(src)
    root = tree.root_node

    graph = CodeGraph(source_path=source_path)
    mod_id = f"{source_path}::<module>"
    graph.nodes.append(
        SymbolNode(
            symbol_id=mod_id,
            name=Path(source_path).stem,
            qualname="<module>",
            kind="module",
            source_path=source_path,
            start_line=1,
            end_line=root.end_point[0] + 1,
            sha256=_sha256(src),
        )
    )

    _PyWalker(src, source_path, graph, mod_id).walk(root, _Ctx(mod_id, "", None))
    _resolve_calls(graph)
    return graph


def _imported_modules(node: "Node", src: bytes) -> list[str]:
    """Extract imported module names from import / import-from statements."""
    out: list[str] = []
    if node.type == "import_from_statement":
        mod = node.child_by_field_name("module_name")
        if mod is not None:
            out.append(_text(mod, src))
        return out
    # plain `import a, b.c as d`
    for child in node.named_children:
        if child.type in ("dotted_name", "aliased_import"):
            target = child
            if child.type == "aliased_import":
                target = child.child_by_field_name("name") or child
            out.append(_text(target, src))
    return out


def _callee_ref(call_node: "Node", src: bytes) -> Optional[tuple[str, int, int]]:
    """Return (callee_name, line, col) for `foo(...)` or `obj.foo(...)`.

    line is 1-indexed, col 0-indexed — the position of the callee *identifier*
    (the method name for attribute calls), for jedi goto in enrich.py.
    """
    fn = call_node.child_by_field_name("function")
    if fn is None:
        return None
    target = fn
    if fn.type == "attribute":
        target = fn.child_by_field_name("attribute")
    if target is None or target.type != "identifier":
        return None
    return _text(target, src), target.start_point[0] + 1, target.start_point[1]


def _base_refs(class_node: "Node", src: bytes) -> list[tuple[str, int, int]]:
    """Return [(base_name, line, col)] for a class's superclasses (INHERITS).

    Bare name for `Base`; last attribute segment for `pkg.Base` (matches callee
    convention). Position is the base identifier's, for jedi cross-file resolution.
    """
    sup = class_node.child_by_field_name("superclasses")
    if sup is None:
        return []
    out: list[tuple[str, int, int]] = []
    for base in sup.named_children:
        target = base
        if base.type == "attribute":
            target = base.child_by_field_name("attribute")
        if target is None or target.type != "identifier":
            continue
        out.append((_text(target, src), target.start_point[0] + 1, target.start_point[1]))
    return out


def extract_python_file(path: str | Path) -> CodeGraph:
    """Extract a CodeGraph from a Python file on disk."""
    p = Path(path)
    source = p.read_text(encoding="utf-8", errors="replace")
    return extract_python_source(source, source_path=str(p))
