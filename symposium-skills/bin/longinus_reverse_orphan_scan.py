#!/usr/bin/env python3
"""
longinus_reverse_orphan_scan.py — Longinus v3.1 Reverse Orphan Scan
────────────────────────────────────────────────────────────────────

Code → KG missing-detection / BX PutGet violation surfacing.

Paradigm shift (v3 → v3.1):
    forward (v3):   KG ref  → grep code → exists?           (Missing drift)
    reverse (v3.1): code symbol → KG ref → exists?  ★ NEW   (PutGet violation)
                    ↓ if absent → label :ORPHAN_REFERENCE

This is the *blind-spot fix* — code symbols that are wired but never
crystallized in the KG. PutGet law (Foster-Pierce-Walker 2007 TOPLAS):
    get(put(v, s)) = v
A code symbol with no KG referent breaks the round-trip — KG cannot
recover what code already asserts.

Crate/Script-level binding (v3.1):
    Cargo.toml / package.json / __main__ entry 단위 binding 도 ORPHAN
    검출 가능 (function/class 단위 외 추가 layer).

KG canonical:
    - BHGMAN/longinus/SOURCES.md §"Reverse Orphan Scan v3.1"
    - longinus-hardening-master-plan-2026-05-06
    - lesson-cs-reference-semantics-2026-04-16
    - bhgman 9 ORPHAN_REFERENCE preserve (iter 35-36)
    - A6 Reverse Orphan Scan (Dragon Book dead-code / reachability)
    - PutGet violation = Missing drift (5-drift catalog)

# KG: longinus-reverse-orphan-scan-2026-05-09 (:ProductionTool)
# KG: BHGMAN/longinus/SOURCES.md v3.1 §A6
# KG: longinus-hardening-master-plan-2026-05-06

──────────────────────────────────────────────────────────────────
Modes:
    --dry-run             : extract symbols + JSON output (no KG write)
    --neo4j               : query Neo4j to classify each symbol (fallback dry-run if unreachable)
    --label               : when used with --neo4j, MERGE ORPHAN_REFERENCE label
    --crate-script        : also extract crate/script-level entries
    --json                : machine-readable JSON output (default human)
    --path PATH           : root directory to scan (default: SKILLS/bin/)
    --include-tests       : include test_*.py / *_test.py (default exclude)

Smoke test:
    python3 longinus_reverse_orphan_scan.py --path /Users/lagyeongjun/CD/SYMPOSIUM/SKILLS/bin --dry-run --json
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Iterable

# ── Configuration ─────────────────────────────────────────────────

NEO4J_URL = os.environ.get(
    "NEO4J_URL", "http://neo4j.metahumotonic.com/db/neo4j/tx/commit"
)
NEO4J_AUTH = os.environ.get("NEO4J_AUTH", "neo4j:neo4jpassword")

DEFAULT_SCAN_ROOT = "/Users/lagyeongjun/CD/SYMPOSIUM/SKILLS/bin"

# Symbol kinds we extract from Python AST (function/class/main-entry)
EXTRACTED_KINDS = {"function", "class", "method", "module_main", "script_main"}

# Crate/Script-level filenames (v3.1 binding)
CRATE_SCRIPT_FILES = {
    "Cargo.toml": "rust_crate",
    "package.json": "npm_package",
    "pyproject.toml": "python_package",
    "setup.py": "python_setup",
    "go.mod": "go_module",
    "__main__.py": "python_main_entry",
}

# Files we never want to recurse into
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv",
             ".lake", "packages", "_archive", "_backup", "_old"}


# ── Data classes ──────────────────────────────────────────────────


@dataclass
class CodeSymbol:
    """A code-side symbol candidate for KG referent lookup.

    Mirrors :CodeSymbol KG node shape used in Longinus 7-Layer L3 (CODE_SYMBOL).
    """
    path: str          # absolute file path
    symbol: str        # symbol name (function / class / crate / etc.)
    kind: str          # function | class | method | module_main | crate | script
    lineno: int = 0
    end_lineno: int = 0
    parent: str = ""   # parent class for methods
    layer: str = "L3_CODE_SYMBOL"  # default L3, crate-level uses L7_CRATE_SCRIPT

    @property
    def fqn(self) -> str:
        """Fully-qualified name. parent.symbol when method."""
        return f"{self.parent}.{self.symbol}" if self.parent else self.symbol


@dataclass
class ScanResult:
    scan_root: str
    files_scanned: int = 0
    symbols_total: int = 0
    crate_script_total: int = 0
    orphan_candidates: list[CodeSymbol] = field(default_factory=list)
    bound_symbols: list[CodeSymbol] = field(default_factory=list)
    skipped_files: list[str] = field(default_factory=list)
    neo4j_reachable: bool = False
    label_writes_attempted: int = 0
    label_writes_succeeded: int = 0


# ── AST extraction (Python — covers SKILLS/bin/) ──────────────────


def _is_test_file(path: Path) -> bool:
    n = path.name
    return n.startswith("test_") or n.endswith("_test.py") or "/tests/" in str(path)


def _walk_python_files(root: Path, include_tests: bool) -> Iterable[Path]:
    for dirpath, dirnames, filenames in os.walk(root):
        # in-place prune
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if not fn.endswith(".py"):
                continue
            p = Path(dirpath) / fn
            if not include_tests and _is_test_file(p):
                continue
            yield p


def extract_symbols_python(file_path: Path) -> tuple[list[CodeSymbol], bool]:
    """Return (symbols, ok). ok=False on parse error.

    Extracts FunctionDef / AsyncFunctionDef / ClassDef. Methods get
    parent=ClassName. Top-level `if __name__ == '__main__':` blocks
    surface as kind=script_main.
    """
    try:
        src = file_path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(src, filename=str(file_path))
    except (SyntaxError, UnicodeDecodeError, OSError):
        return [], False

    symbols: list[CodeSymbol] = []
    abs_path = str(file_path.resolve())

    def _add_function(node, parent_class: str = ""):
        kind = "method" if parent_class else "function"
        symbols.append(CodeSymbol(
            path=abs_path,
            symbol=node.name,
            kind=kind,
            lineno=node.lineno,
            end_lineno=getattr(node, "end_lineno", node.lineno),
            parent=parent_class,
        ))

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            _add_function(node)
        elif isinstance(node, ast.ClassDef):
            symbols.append(CodeSymbol(
                path=abs_path,
                symbol=node.name,
                kind="class",
                lineno=node.lineno,
                end_lineno=getattr(node, "end_lineno", node.lineno),
            ))
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    _add_function(child, parent_class=node.name)
        elif isinstance(node, ast.If):
            # Detect `if __name__ == "__main__":` script entry
            try:
                test = node.test
                if (isinstance(test, ast.Compare)
                        and isinstance(test.left, ast.Name)
                        and test.left.id == "__name__"
                        and len(test.comparators) == 1
                        and isinstance(test.comparators[0], ast.Constant)
                        and test.comparators[0].value == "__main__"):
                    symbols.append(CodeSymbol(
                        path=abs_path,
                        symbol=f"__main__::{file_path.stem}",
                        kind="script_main",
                        lineno=node.lineno,
                        end_lineno=getattr(node, "end_lineno", node.lineno),
                        layer="L7_CRATE_SCRIPT",
                    ))
            except Exception:
                pass

    return symbols, True


# ── Crate / script-level (v3.1) ──────────────────────────────────


def extract_crate_script(root: Path) -> list[CodeSymbol]:
    """Extract crate/package-level binding entries.

    v3.1 spec:
        Cargo.toml      → rust_crate
        package.json    → npm_package
        pyproject.toml  → python_package
        __main__.py     → python_main_entry
    """
    found: list[CodeSymbol] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if fn in CRATE_SCRIPT_FILES:
                p = Path(dirpath) / fn
                kind = CRATE_SCRIPT_FILES[fn]
                # symbol = basename of containing directory (crate name proxy)
                crate_name = Path(dirpath).name or fn
                found.append(CodeSymbol(
                    path=str(p.resolve()),
                    symbol=crate_name,
                    kind=kind,
                    lineno=1,
                    end_lineno=1,
                    layer="L7_CRATE_SCRIPT",
                ))
    return found


# ── Neo4j Cypher ──────────────────────────────────────────────────


def _cypher_call(stmt: str, params: dict | None = None, timeout_s: int = 10):
    body: dict = {"statement": stmt}
    if params:
        body["parameters"] = params
    payload = json.dumps({"statements": [body]})
    try:
        out = subprocess.check_output(
            [
                "curl", "-sf", "-m", str(timeout_s),
                "-u", NEO4J_AUTH,
                "-H", "Content-Type: application/json",
                "-d", payload,
                NEO4J_URL,
            ],
            timeout=timeout_s + 5,
            stderr=subprocess.DEVNULL,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return None
    try:
        return json.loads(out.decode())
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None


def neo4j_reachable() -> bool:
    res = _cypher_call("RETURN 1 AS ok", timeout_s=5)
    if not res or "results" not in res:
        return False
    try:
        return res["results"][0]["data"][0]["row"][0] == 1
    except (KeyError, IndexError):
        return False


# Canonical reverse-orphan classification query (v3.1).
# A CodeSymbol is :ORPHAN_REFERENCE iff no :KGNode REFERENCES it.
REVERSE_ORPHAN_QUERY = """
MATCH (cs:CodeSymbol) WHERE cs.path = $path AND cs.symbol = $symbol
OPTIONAL MATCH (kg:KGNode)-[:REFERENCES]->(cs)
WITH cs, count(kg) AS ref_count
WHERE ref_count = 0
SET cs:ORPHAN_REFERENCE
RETURN cs.path AS orphan_path, cs.symbol AS orphan_symbol
""".strip()

# Existence check: does any KG referent point at (path, symbol)?
# Tolerant — accepts ReferenceSite.sourcePath, kg_ref strings, or :REFERENCES edge.
EXISTS_QUERY = """
OPTIONAL MATCH (rs:ReferenceSite)
  WHERE rs.sourcePath ENDS WITH $rel_path
    AND (rs.symbol = $symbol OR rs.kg_anchor CONTAINS $symbol OR rs.name CONTAINS $symbol)
WITH count(rs) AS rs_count
OPTIONAL MATCH (cs:CodeSymbol {path: $abs_path, symbol: $symbol})<-[:REFERENCES]-(:KGNode)
WITH rs_count, count(cs) AS cs_ref_count
RETURN (rs_count + cs_ref_count) AS total_refs
""".strip()


def kg_has_referent(symbol: CodeSymbol, scan_root: Path) -> bool:
    rel_path = str(Path(symbol.path).resolve())
    res = _cypher_call(EXISTS_QUERY, {
        "rel_path": rel_path,
        "abs_path": rel_path,
        "symbol": symbol.symbol,
    })
    if not res:
        return False
    try:
        rows = res["results"][0]["data"]
        if not rows:
            return False
        return rows[0]["row"][0] > 0
    except (KeyError, IndexError, TypeError):
        return False


# Label-write Cypher — MERGE CodeSymbol + add :ORPHAN_REFERENCE label.
LABEL_ORPHAN_QUERY = """
MERGE (cs:CodeSymbol {path: $path, symbol: $symbol})
ON CREATE SET cs.created_at = datetime(), cs.kind = $kind, cs.layer = $layer,
              cs.lineno = $lineno, cs.parent = $parent
ON MATCH SET  cs.kind = $kind, cs.layer = $layer,
              cs.lineno = $lineno, cs.parent = $parent
SET cs:ORPHAN_REFERENCE
SET cs.orphan_detected_at = datetime(),
    cs.orphan_detector = 'longinus-reverse-orphan-scan-2026-05-09',
    cs.bx_law_violated = 'PutGet'
RETURN cs.path AS path, cs.symbol AS symbol
""".strip()


def write_orphan_label(symbol: CodeSymbol) -> bool:
    res = _cypher_call(LABEL_ORPHAN_QUERY, {
        "path": symbol.path,
        "symbol": symbol.symbol,
        "kind": symbol.kind,
        "layer": symbol.layer,
        "lineno": symbol.lineno,
        "parent": symbol.parent,
    })
    if not res:
        return False
    try:
        return len(res["results"][0]["data"]) > 0
    except (KeyError, IndexError):
        return False


# ── Main scan ─────────────────────────────────────────────────────


def run_scan(
    scan_root: Path,
    *,
    dry_run: bool,
    neo4j: bool,
    label: bool,
    crate_script: bool,
    include_tests: bool,
) -> ScanResult:
    result = ScanResult(scan_root=str(scan_root.resolve()))

    # 1) symbol harvest (Python AST)
    all_symbols: list[CodeSymbol] = []
    for f in _walk_python_files(scan_root, include_tests=include_tests):
        result.files_scanned += 1
        syms, ok = extract_symbols_python(f)
        if not ok:
            result.skipped_files.append(str(f))
            continue
        all_symbols.extend(syms)

    # 2) crate / script-level (v3.1)
    if crate_script:
        crate_syms = extract_crate_script(scan_root)
        result.crate_script_total = len(crate_syms)
        all_symbols.extend(crate_syms)

    result.symbols_total = len(all_symbols)

    # 3) classification — KG referent check
    if neo4j and not dry_run:
        result.neo4j_reachable = neo4j_reachable()
    else:
        result.neo4j_reachable = False

    if dry_run or not result.neo4j_reachable:
        # Without KG access, every extracted symbol is a candidate.
        # Caller is responsible for de-noising.
        result.orphan_candidates = list(all_symbols)
    else:
        for s in all_symbols:
            if kg_has_referent(s, scan_root):
                result.bound_symbols.append(s)
            else:
                result.orphan_candidates.append(s)
                if label:
                    result.label_writes_attempted += 1
                    if write_orphan_label(s):
                        result.label_writes_succeeded += 1

    return result


# ── Output formatting ─────────────────────────────────────────────


def render_json(result: ScanResult) -> str:
    payload = {
        "tool": "longinus-reverse-orphan-scan",
        "version": "3.1",
        "kg_ref": "longinus-reverse-orphan-scan-2026-05-09",
        "scan_root": result.scan_root,
        "files_scanned": result.files_scanned,
        "symbols_total": result.symbols_total,
        "crate_script_total": result.crate_script_total,
        "skipped_files": result.skipped_files,
        "neo4j_reachable": result.neo4j_reachable,
        "label_writes_attempted": result.label_writes_attempted,
        "label_writes_succeeded": result.label_writes_succeeded,
        "orphan_candidate_count": len(result.orphan_candidates),
        "orphan_candidates": [asdict(s) for s in result.orphan_candidates],
        "bound_count": len(result.bound_symbols),
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


def render_human(result: ScanResult) -> str:
    lines = [
        f"Longinus v3.1 Reverse Orphan Scan",
        f"  scan root        : {result.scan_root}",
        f"  files scanned    : {result.files_scanned}",
        f"  symbols total    : {result.symbols_total}",
        f"  crate/script lvl : {result.crate_script_total}",
        f"  skipped (parse)  : {len(result.skipped_files)}",
        f"  neo4j reachable  : {result.neo4j_reachable}",
        f"  orphan candidates: {len(result.orphan_candidates)}",
        f"  bound symbols    : {len(result.bound_symbols)}",
        f"  labels written   : {result.label_writes_succeeded}/{result.label_writes_attempted}",
        "",
        "ORPHAN_REFERENCE candidates (PutGet violation):",
    ]
    for s in result.orphan_candidates[:200]:
        lines.append(f"  - [{s.kind:14s}] {s.fqn:40s} {s.path}:{s.lineno}")
    if len(result.orphan_candidates) > 200:
        lines.append(f"  ... ({len(result.orphan_candidates) - 200} more)")
    return "\n".join(lines)


# ── CLI ───────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=("Longinus v3.1 Reverse Orphan Scan — code → KG missing "
                     "detection (BX PutGet violation). KG: "
                     "longinus-reverse-orphan-scan-2026-05-09")
    )
    parser.add_argument("--path", default=DEFAULT_SCAN_ROOT,
                        help=f"directory to scan (default: {DEFAULT_SCAN_ROOT})")
    parser.add_argument("--dry-run", action="store_true",
                        help="extract symbols only, no KG queries")
    parser.add_argument("--neo4j", action="store_true",
                        help="query Neo4j to classify symbols (auto-fallback if unreachable)")
    parser.add_argument("--label", action="store_true",
                        help="when --neo4j set, MERGE :ORPHAN_REFERENCE label on detected symbols")
    parser.add_argument("--crate-script", action="store_true",
                        help="also extract crate/script-level entries (Cargo.toml/package.json/__main__)")
    parser.add_argument("--include-tests", action="store_true",
                        help="include test_*.py / *_test.py (default: skipped)")
    parser.add_argument("--json", action="store_true",
                        help="emit machine-readable JSON")
    args = parser.parse_args(argv)

    if args.label and not args.neo4j:
        print("warning: --label requires --neo4j; ignoring --label",
              file=sys.stderr)
        args.label = False

    scan_root = Path(args.path).expanduser().resolve()
    if not scan_root.exists():
        print(f"error: scan root not found: {scan_root}", file=sys.stderr)
        return 2
    if not scan_root.is_dir():
        print(f"error: scan root is not a directory: {scan_root}", file=sys.stderr)
        return 2

    result = run_scan(
        scan_root,
        dry_run=args.dry_run,
        neo4j=args.neo4j,
        label=args.label,
        crate_script=args.crate_script,
        include_tests=args.include_tests,
    )

    if args.json:
        print(render_json(result))
    else:
        print(render_human(result))

    # Exit code: 0 if no orphans (or pure dry-run), 1 if orphans found in --neo4j mode
    if args.neo4j and result.neo4j_reachable and result.orphan_candidates:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
