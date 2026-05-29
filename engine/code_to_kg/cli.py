"""cli.py — code_to_kg ingestion entry point.

Usage:
    python -m engine.code_to_kg.cli ingest <path> [--local] [--cypher] [--json]

Modes (bhgman --local convention):
    --local   : MERGE into the stdlib JSON LocalKgStore (~/.bhgman/kg.json). neo4j 0.
    --cypher  : print idempotent MERGE Cypher for the canonical Neo4j KG (no exec).
    (default) : --cypher (safe, no write) + a counts summary on stderr.

<path> may be a single .py file or a directory (recursed for *.py, .venv skipped).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Support both `python -m engine.code_to_kg.cli` (package) and direct bare import.
try:
    from .ts_extractor import extract_python_file, TREE_SITTER_AVAILABLE
    from .kg_writer import write_local, to_cypher
except ImportError:  # pragma: no cover - direct script run
    from ts_extractor import extract_python_file, TREE_SITTER_AVAILABLE  # type: ignore
    from kg_writer import write_local, to_cypher  # type: ignore


def _iter_py_files(path: Path):
    if path.is_file():
        yield path
        return
    for p in sorted(path.rglob("*.py")):
        if ".venv" in p.parts or "node_modules" in p.parts or "__pycache__" in p.parts:
            continue
        yield p


def cmd_ingest(args: argparse.Namespace) -> int:
    if not TREE_SITTER_AVAILABLE:
        print(
            "tree-sitter not installed: pip install tree-sitter tree-sitter-python",
            file=sys.stderr,
        )
        return 2

    root = Path(args.path).expanduser()
    if not root.exists():
        print(f"path not found: {root}", file=sys.stderr)
        return 2

    files = list(_iter_py_files(root))
    totals = {"files": 0, "nodes": 0, "defines": 0, "calls": 0, "imports": 0}
    cypher_all: list[str] = []
    store = None
    if args.local:
        # kg_local/store.py uses bare imports (`from schema import ...`); put its
        # dir on sys.path the same way the occam/kg_local conftest bridges do.
        kg_local_dir = Path(__file__).resolve().parent.parent / "kg_local"
        if str(kg_local_dir) not in sys.path:
            sys.path.insert(0, str(kg_local_dir))
        from store import LocalKgStore  # noqa: PLC0415

        store = LocalKgStore()

    for f in files:
        graph = extract_python_file(f)
        totals["files"] += 1
        totals["nodes"] += graph.node_count()
        totals["defines"] += len(graph.edges_of("DEFINES"))
        totals["calls"] += len([e for e in graph.edges_of("CALLS") if e.resolved])
        totals["imports"] += len(graph.edges_of("IMPORTS"))
        if args.local:
            write_local(graph, store)
        else:
            cypher_all.extend(to_cypher(graph))

    if args.local:
        store.save()
        print(f"[code_to_kg] local KG updated: {store.path}", file=sys.stderr)
    else:
        for stmt in cypher_all:
            print(stmt + ";")

    print(json.dumps({"summary": totals}, ensure_ascii=False), file=sys.stderr)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="code_to_kg", description="tree-sitter source → KG")
    sub = p.add_subparsers(dest="cmd", required=True)
    ing = sub.add_parser("ingest", help="parse Python source → KG symbols")
    ing.add_argument("path", help="a .py file or a directory")
    ing.add_argument("--local", action="store_true", help="write to local JSON KG (neo4j 0)")
    ing.add_argument("--cypher", action="store_true", help="emit Neo4j MERGE Cypher (default)")
    ing.set_defaults(func=cmd_ingest)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
