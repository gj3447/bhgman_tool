"""Code scanner — extract source symbols + `# KG: xxx` references.

Python symbols are extracted with the stdlib ``ast`` module (real structured
signatures: annotations, return types, ``/`` positional-only, ``*`` keyword-only,
``*args``/``**kwargs``, multi-line signatures, async, class bases). On a
``SyntaxError`` the scanner falls back to the original line-regex so a single
un-parseable file never blanks the whole scan. Other languages still go through
the regex/LSP path.

# KG: longinus-parallel-scan-2026-05-18 (L1 parallel scan PRELIMINARY)
"""

from __future__ import annotations

import ast
import os
import re
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Iterable, Iterator

from engine.longinus_drift_audit.models import CodeSymbol


_DEFAULT_PARALLEL_THRESHOLD = int(os.environ.get("LONGINUS_PARALLEL_FILE_THRESHOLD", "5000"))
"""File-count threshold below which scan_root stays sequential.

Empirical break-even on M-series macOS (bench/bench_parallel.py 2026-05-18):
regex-only per-file scan is so cheap (~50μs) that ProcessPool spawn + pickle
IPC dominates until ~5000 files. Below that, sequential is faster.

If you swap the scanner for AST/tree-sitter/GumTree (per-file work ~5-50ms),
drop this threshold to ~50-100 — parallel will then dominate by ncpus.

Override: env LONGINUS_PARALLEL_FILE_THRESHOLD or kwarg ``threshold=``.

# KG: lesson-longinus-parallel-breakeven-2026-05-18
"""


_KG_REF_PATTERN = re.compile(r"#\s*KG:\s*([a-zA-Z0-9_\-./, ]+)")
_PY_FUNC = re.compile(r"^def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(([^)]*)\)")
_PY_CLASS = re.compile(r"^class\s+([A-Z][a-zA-Z0-9_]*)")


def iter_files(root: Path, *, suffixes: Iterable[str] = (".py",)) -> Iterator[Path]:
    """root 아래 surface files (build/cache 디렉토리 제외)."""
    skip_parts = {".pytest_cache", "__pycache__", ".lake", ".venv", "node_modules"}
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if any(part in skip_parts for part in p.parts):
            continue
        if p.suffix in suffixes:
            yield p


def scan_kg_refs(file_path: Path) -> list[tuple[int, list[str]]]:
    """Per-line `# KG: ...` reference extraction.

    Returns: list of (line_number, [kg_ref, ...]).
    """
    out: list[tuple[int, list[str]]] = []
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return out
    for i, line in enumerate(content.splitlines(), start=1):
        m = _KG_REF_PATTERN.search(line)
        if m:
            refs_raw = m.group(1)
            refs = [r.strip() for r in refs_raw.split(",") if r.strip()]
            if refs:
                out.append((i, refs))
    return out


def _arg_str(arg: ast.arg) -> str:
    """``name`` or ``name: annotation``."""
    s = arg.arg
    if arg.annotation is not None:
        s += f": {ast.unparse(arg.annotation)}"
    return s


def _positional_parts(a: ast.arguments) -> list[str]:
    pos = a.posonlyargs + a.args
    ndef = len(a.defaults)
    parts: list[str] = []
    for i, arg in enumerate(pos):
        s = _arg_str(arg)
        di = i - (len(pos) - ndef)
        if di >= 0:
            s += f" = {ast.unparse(a.defaults[di])}"
        parts.append(s)
    if a.posonlyargs:
        parts.insert(len(a.posonlyargs), "/")
    return parts


def _keyword_parts(a: ast.arguments) -> list[str]:
    parts: list[str] = []
    if a.vararg:
        parts.append("*" + _arg_str(a.vararg))
    elif a.kwonlyargs:
        parts.append("*")
    for i, arg in enumerate(a.kwonlyargs):
        s = _arg_str(arg)
        if a.kw_defaults[i] is not None:
            s += f" = {ast.unparse(a.kw_defaults[i])}"
        parts.append(s)
    if a.kwarg:
        parts.append("**" + _arg_str(a.kwarg))
    return parts


def _format_signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    """Canonical signature string from a function's ast args (+ return type).

    ``def bar(x, y)`` → ``"x, y"`` (back-compat: callers grep for bare names);
    annotated/defaulted/posonly/kwonly/varargs are all rendered faithfully, e.g.
    ``"a, /, b, *args, c = 1, **kw"`` and ``"x: int = 0 -> bool"``.
    """
    parts = _positional_parts(node.args) + _keyword_parts(node.args)
    sig = ", ".join(parts)
    if node.returns is not None:
        sig += f" -> {ast.unparse(node.returns)}"
    return sig


def _node_kg_refs(node: ast.AST, kg_per_line: dict[int, list[str]]) -> list[str]:
    """Union `# KG:` refs across a node's header span (decorators + multi-line
    signature), so an inline ref on any header line is attached to the symbol."""
    start = getattr(node, "lineno", None)
    if start is None:
        return []
    decos = getattr(node, "decorator_list", []) or []
    if decos:
        start = min(start, min(d.lineno for d in decos))
    body = getattr(node, "body", None)
    end = (body[0].lineno - 1) if body else getattr(node, "end_lineno", node.lineno)
    seen: list[str] = []
    for ln in range(start, max(start, end) + 1):
        for ref in kg_per_line.get(ln, []):
            if ref not in seen:
                seen.append(ref)
    return seen


def _symbols_via_ast(
    content: str, rel: str, kg_per_line: dict[int, list[str]]
) -> list[CodeSymbol] | None:
    """Top-level def/class via stdlib ast. Returns None on SyntaxError (→ regex)."""
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return None
    out: list[CodeSymbol] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out.append(
                CodeSymbol(
                    sourcePath=f"{rel}:{node.lineno}",
                    name=node.name,
                    kind="async_function" if isinstance(node, ast.AsyncFunctionDef) else "function",
                    signature=_format_signature(node),
                    kg_refs=_node_kg_refs(node, kg_per_line),
                )
            )
        elif isinstance(node, ast.ClassDef):
            bases = ", ".join(ast.unparse(b) for b in node.bases) or None
            out.append(
                CodeSymbol(
                    sourcePath=f"{rel}:{node.lineno}",
                    name=node.name,
                    kind="class",
                    signature=bases,
                    kg_refs=_node_kg_refs(node, kg_per_line),
                )
            )
    return out


def _symbols_via_regex(
    content: str, rel: str, kg_per_line: dict[int, list[str]]
) -> list[CodeSymbol]:
    """Line-regex fallback for files ast cannot parse (syntax error / partial)."""
    out: list[CodeSymbol] = []
    for i, line in enumerate(content.splitlines(), start=1):
        if mf := _PY_FUNC.match(line):
            out.append(
                CodeSymbol(
                    sourcePath=f"{rel}:{i}",
                    name=mf.group(1),
                    kind="function",
                    signature=mf.group(2).strip(),
                    kg_refs=kg_per_line.get(i, []),
                )
            )
        elif mc := _PY_CLASS.match(line):
            out.append(
                CodeSymbol(
                    sourcePath=f"{rel}:{i}",
                    name=mc.group(1),
                    kind="class",
                    kg_refs=kg_per_line.get(i, []),
                )
            )
    return out


def scan_python_symbols(file_path: Path) -> list[CodeSymbol]:
    """Top-level def/class symbols with real AST signatures (regex fallback)."""
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []
    kg_per_line = dict(scan_kg_refs(file_path))
    rel = str(file_path)
    syms = _symbols_via_ast(content, rel, kg_per_line)
    if syms is None:
        syms = _symbols_via_regex(content, rel, kg_per_line)
    return syms


def _scan_one_file(f: Path) -> tuple[list[CodeSymbol], list[tuple[Path, int, str]]]:
    """Top-level worker — picklable for ProcessPoolExecutor."""
    syms = scan_python_symbols(f)
    refs: list[tuple[Path, int, str]] = []
    for line_no, kg_names in scan_kg_refs(f):
        for name in kg_names:
            refs.append((f, line_no, name))
    return syms, refs


def scan_root(
    root: Path,
    *,
    parallel: bool = True,
    max_workers: int | None = None,
    threshold: int | None = None,
) -> tuple[list[CodeSymbol], list[tuple[Path, int, str]]]:
    """Returns (symbols, all_kg_refs_with_location).

    all_kg_refs: [(file, line, kg_ref_name)] flattened. line-level granular.

    Parallel (L1, 2026-05-18): when ``parallel`` and file count >= ``threshold``,
    dispatch per-file scan via ProcessPoolExecutor. Output is sorted by path so
    downstream GED / dict-keyed structures stay deterministic across both
    codepaths (sequential and parallel must produce byte-identical AuditReport).

    Env override: ``LONGINUS_PARALLEL_FILE_THRESHOLD`` (default 100).
    """
    files = sorted(iter_files(root))
    thresh = threshold if threshold is not None else _DEFAULT_PARALLEL_THRESHOLD

    if not parallel or len(files) < thresh:
        per_file = [_scan_one_file(f) for f in files]
    else:
        # chunksize reduces per-task pickle round trips. For regex-light work,
        # large chunks (~50-200) outperform the default chunksize=1.
        chunksize = max(1, len(files) // ((max_workers or os.cpu_count() or 4) * 4))
        with ProcessPoolExecutor(max_workers=max_workers) as ex:
            per_file = list(ex.map(_scan_one_file, files, chunksize=chunksize))

    syms: list[CodeSymbol] = []
    refs: list[tuple[Path, int, str]] = []
    for syms_i, refs_i in per_file:
        syms.extend(syms_i)
        refs.extend(refs_i)
    return syms, refs
