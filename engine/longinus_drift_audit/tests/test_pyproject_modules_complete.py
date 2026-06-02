"""Guard: pyproject py-modules must list every top-level module.

setuptools `py-modules` is an explicit allowlist — any top-level *.py not in it
is silently dropped from a non-editable wheel build (editable installs mask the
gap). This test fails the moment a new top-level module is added without
registering it, so the manifest cannot drift out of sync again.

Origin: 2026-06-02 found 21 of 36 modules missing from the manifest.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

_PKG_ROOT = Path(__file__).resolve().parent.parent
# Not shippable as py-modules: package marker, test bootstrap, build script.
_EXCLUDE = {"__init__", "conftest", "setup"}


def _disk_modules() -> set[str]:
    return {p.stem for p in _PKG_ROOT.glob("*.py")} - _EXCLUDE


def _registered_modules() -> set[str]:
    data = tomllib.loads((_PKG_ROOT / "pyproject.toml").read_text())
    return set(data["tool"]["setuptools"]["py-modules"])


def test_pyproject_lists_every_top_level_module():
    disk = _disk_modules()
    registered = _registered_modules()
    missing = sorted(disk - registered)
    ghost = sorted(registered - disk)
    assert not missing, f"top-level modules absent from pyproject py-modules: {missing}"
    assert not ghost, f"pyproject py-modules lists non-existent modules: {ghost}"
