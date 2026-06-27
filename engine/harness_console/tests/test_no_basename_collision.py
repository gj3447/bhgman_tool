"""Guard: no two init-less test dirs may share a test-module basename.

Under pytest's default ``import-mode=prepend``, a test file in a directory WITHOUT
an ``__init__.py`` is imported by its bare basename (e.g. ``test_store``). If two such
directories both hold ``test_store.py``, the second import collides with the first
(``import file mismatch``) and aborts collection of the ENTIRE suite with a hard error
— exactly the command CI runs (`pytest` from repo root over ``testpaths``).

This converts that brittle, suite-wide-fatal invariant into a single enforced unit
test: for every test-module basename that appears in more than one directory under
``engine/``, AT MOST ONE of those directories may lack an ``__init__.py`` package marker.

# KG: finding-pytest-basename-collision-suite-uncollectable-2026-06-26
"""

from __future__ import annotations

import collections
import pathlib


_ENGINE_ROOT = pathlib.Path(__file__).resolve().parents[2]


def _collision_offenders() -> dict[str, list[str]]:
    """basename -> [init-less dirs holding it], for basenames with >1 init-less dir."""
    by_name: dict[str, list[pathlib.Path]] = collections.defaultdict(list)
    for f in _ENGINE_ROOT.rglob("test_*.py"):
        if "tests" in f.parts:
            by_name[f.name].append(f)
    offenders: dict[str, list[str]] = {}
    for name, files in by_name.items():
        init_less = [
            str(f.parent.relative_to(_ENGINE_ROOT))
            for f in files
            if not (f.parent / "__init__.py").exists()
        ]
        if len(init_less) > 1:
            offenders[name] = sorted(init_less)
    return offenders


def test_no_initless_basename_collision() -> None:
    offenders = _collision_offenders()
    assert not offenders, (
        "Test-module basename(s) live in >1 directory that lacks __init__.py — under "
        "import-mode=prepend this aborts collection of the whole suite. Add an "
        "__init__.py to all but one of each group: "
        + "; ".join(f"{name} in {dirs}" for name, dirs in sorted(offenders.items()))
    )
