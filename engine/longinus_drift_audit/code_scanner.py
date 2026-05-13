"""grep-based code scanner — extract source symbols + `# KG: xxx` references.

LSP fallback. Real production may swap for tree-sitter / py-LSP / rust-analyzer.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable, Iterator

from models import CodeSymbol


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


def scan_root(root: Path) -> tuple[list[CodeSymbol], list[tuple[Path, int, str]]]:
    """Returns (symbols, all_kg_refs_with_location).

    all_kg_refs: [(file, line, kg_ref_name)] flattened. line-level granular.
    """
    syms: list[CodeSymbol] = []
    refs: list[tuple[Path, int, str]] = []
    for f in iter_files(root):
        syms.extend(scan_python_symbols(f))
        for line_no, kg_names in scan_kg_refs(f):
            for name in kg_names:
                refs.append((f, line_no, name))
    return syms, refs
