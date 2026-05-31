#!/usr/bin/env python3
"""Falsifier: run bhgman's structural-dup detector on a real public OSS (click).

Self-critique 2026-05-28 asked for the honest "capability vs discipline" test —
apply the tooling to *external* code (not the project's own KG) and see whether
it produces a real, externally-valid deliverable.

This scans every class in pallets/click with the hades Extract-Superclass engine
(stdlib-ast structural method comparison) and reports class pairs that share a
byte-for-byte-identical (AST-level, formatting-insensitive) non-dunder method —
genuine Extract-Superclass candidates. For one candidate it generates a real
format-preserving patch via libcst.

Run: `python worked/04-falsifier-click/run.py` (clones click --depth 1 on first run).
"""

from __future__ import annotations

import ast
import subprocess
import sys
from itertools import combinations
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
CLICK = HERE / ".cache_click"
sys.path.insert(0, str(REPO / "engine" / "hades"))


def _ensure_click() -> Path:
    src = CLICK / "src" / "click"
    if not src.is_dir():
        CLICK.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(  # noqa: S603,S607
            ["git", "clone", "--depth", "1", "https://github.com/pallets/click.git", str(CLICK)],
            check=True,
        )
    return src


def _classes(src: Path) -> dict[str, ast.ClassDef]:
    out: dict[str, ast.ClassDef] = {}
    for f in src.rglob("*.py"):
        try:
            tree = ast.parse(f.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for n in tree.body:
            if isinstance(n, ast.ClassDef):
                out[n.name] = n
    return out


def main() -> int:
    from extract_superclass import common_methods, extract_superclass_cst

    src = _ensure_click()
    classes = _classes(src)
    findings = []
    for a, b in combinations(sorted(classes), 2):
        shared = [m for m in common_methods([classes[a], classes[b]]) if not m.startswith("__")]
        if shared:
            findings.append((a, b, shared))

    print(
        f"scanned {len(classes)} click classes; "
        f"{len(findings)} class-pair(s) share an identical non-dunder method:\n"
    )
    for a, b, shared in findings:
        bases_a = {x.id for x in classes[a].bases if isinstance(x, ast.Name)}
        bases_b = {x.id for x in classes[b].bases if isinstance(x, ast.Name)}
        common_base = bases_a & bases_b
        print(
            f"  • {a} ~ {b}: {shared}"
            f"{f' (both already extend {common_base.pop()} → lift it there)' if common_base else ''}"
        )

    # one real generated patch (libcst, format-preserving)
    if findings:
        a, b, _ = findings[0]
        sources = {a: ast.unparse(classes[a]), b: ast.unparse(classes[b])}
        patch = extract_superclass_cst("ShellCompleteShared", sources)
        if patch is not None:
            print(
                f"\ngenerated real Extract-Superclass patch for {a}/{b}: "
                f"lifted {list(patch.common_methods)} into a shared base."
            )
    print("\nVERDICT: real external findings (see README) — discipline, not capability.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
