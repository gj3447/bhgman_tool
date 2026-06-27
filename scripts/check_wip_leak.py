#!/usr/bin/env python3
"""Fail if any git-TRACKED engine module imports an UNTRACKED engine module.

The CI-parity blind spot that bit us twice: the dev working tree has files CI never sees —
editable sibling installs (ooptdd) and untracked WIP modules (engine/kg_harness/). A committed
file that imports such a module passes locally (the module is present) but dies on CI with
ModuleNotFoundError. The pytest harness gate runs the working tree, so it can't see this.

This static gate closes it: scan every tracked engine/*.py for `import engine.X` / `from
engine.X import …` and assert engine.X resolves to a tracked file. Untracked → leak.
"""
from __future__ import annotations

import pathlib
import re
import subprocess
import sys

_IMPORT_RE = re.compile(r"^[ \t]*(?:from|import)[ \t]+(engine\.[A-Za-z0-9_.]+)", re.M)


def _tracked() -> set[str]:
    out = subprocess.run(
        ["git", "ls-files", "engine"], capture_output=True, text=True, check=True
    ).stdout
    return set(out.split())


def _resolves(module: str, tracked: set[str]) -> bool:
    """engine.kg_harness -> engine/kg_harness.py | engine/kg_harness/__init__.py tracked?

    Walk prefixes longest-first so `from engine.cli.runtime import x` checks runtime.py, and a
    `from engine.pkg import submod` style still passes when engine/pkg/__init__.py is tracked."""
    parts = module.split(".")
    for end in range(len(parts), 1, -1):
        base = "/".join(parts[:end])
        if f"{base}.py" in tracked or f"{base}/__init__.py" in tracked:
            return True
    return False


def main() -> int:
    tracked = _tracked()
    leaks: list[str] = []
    for f in sorted(p for p in tracked if p.endswith(".py")):
        text = pathlib.Path(f).read_text(errors="ignore")
        for m in _IMPORT_RE.finditer(text):
            module = m.group(1)
            if not _resolves(module, tracked):
                leaks.append(f"{f}: imports untracked module `{module}`")
    if leaks:
        print("WIP-LEAK — tracked code depends on untracked modules (CI will ModuleNotFoundError):")
        for line in leaks:
            print(f"  {line}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
