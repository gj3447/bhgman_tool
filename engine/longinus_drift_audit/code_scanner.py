"""grep-based code scanner — extract source symbols + `# KG: xxx` references.

LSP fallback. Real production may swap for tree-sitter / py-LSP / rust-analyzer.

# KG: longinus-parallel-scan-2026-05-18 (L1 parallel scan PRELIMINARY)
"""

from __future__ import annotations

import os
import re
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Iterable, Iterator

from models import CodeSymbol


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


def scan_python_symbols(file_path: Path) -> list[CodeSymbol]:
    """Top-level def/class symbols. signature 는 raw parameter string."""
    out: list[CodeSymbol] = []
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return out
    kg_per_line = dict(scan_kg_refs(file_path))
    rel = str(file_path)
    for i, line in enumerate(content.splitlines(), start=1):
        if mf := _PY_FUNC.match(line):
            sym = CodeSymbol(
                sourcePath=f"{rel}:{i}",
                name=mf.group(1),
                kind="function",
                signature=mf.group(2).strip(),
                kg_refs=kg_per_line.get(i, []),
            )
            out.append(sym)
        elif mc := _PY_CLASS.match(line):
            sym = CodeSymbol(
                sourcePath=f"{rel}:{i}",
                name=mc.group(1),
                kind="class",
                kg_refs=kg_per_line.get(i, []),
            )
            out.append(sym)
    return out


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
