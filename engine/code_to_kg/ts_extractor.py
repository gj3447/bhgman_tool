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
        # functions/methods become the enclosing scope for nested CALLS
        new_enclosing = ctx.enclosing_func if is_class else sym_id
        self.walk(child, _Ctx(sym_id, f"{qualname}.", new_enclosing))

    def _on_import(self, child: "Node", ctx: _Ctx) -> None:
        for mod in _imported_modules(child, self.src):
            self.graph.edges.append(SymbolEdge(self.mod_id, "IMPORTS", mod, resolved=False))
        self.walk(child, ctx)

    def _on_call(self, child: "Node", ctx: _Ctx) -> None:
        callee = _callee_name(child, self.src)
        if callee:
            self.graph.edges.append(SymbolEdge(ctx.enclosing_func, "CALLS", callee, resolved=False))
        self.walk(child, ctx)


def _resolve_calls(graph: CodeGraph) -> None:
    """Second pass: resolve CALLS dst to a symbol_id when the callee name matches a
    function/method defined in this file (best-effort, file-local scope)."""
    by_name: dict[str, str] = {}
    for n in graph.nodes:
        if n.kind in ("function", "method"):
            by_name.setdefault(n.name, n.symbol_id)
    graph.edges = [
        SymbolEdge(e.src, "CALLS", by_name[e.dst], resolved=True)
        if e.rel == "CALLS" and e.dst in by_name
        else e
        for e in graph.edges
    ]


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


def _callee_name(call_node: "Node", src: bytes) -> Optional[str]:
    """Return the bare callee name for `foo(...)` or `obj.foo(...)`."""
    fn = call_node.child_by_field_name("function")
    if fn is None:
        return None
    if fn.type == "identifier":
        return _text(fn, src)
    if fn.type == "attribute":
        attr = fn.child_by_field_name("attribute")
        return _text(attr, src) if attr is not None else None
    return None


def extract_python_file(path: str | Path) -> CodeGraph:
    """Extract a CodeGraph from a Python file on disk."""
    p = Path(path)
    source = p.read_text(encoding="utf-8", errors="replace")
    return extract_python_source(source, source_path=str(p))
