"""TDD — jedi cross-file CALLS enrichment (PROM 16 A4 resolution).

# KG: lesson-prom16-code-to-kg-tools-2026-05-28
"""

from __future__ import annotations

import pytest

from engine.code_to_kg.ts_extractor import TREE_SITTER_AVAILABLE, extract_python_file
from engine.code_to_kg.enrich import enrich_calls, JEDI_AVAILABLE

pytestmark = pytest.mark.skipif(
    not (TREE_SITTER_AVAILABLE and JEDI_AVAILABLE),
    reason="tree-sitter or jedi not installed",
)

LIB = "def helper():\n    return 1\n\n\nclass Engine:\n    def run(self):\n        return 2\n"
APP = (
    "from lib import helper\n"
    "from lib import Engine\n"
    "\n"
    "def main():\n"
    "    e = Engine()\n"
    "    return helper() + e.run()\n"
)


def _ingest(tmp_path):
    (tmp_path / "lib.py").write_text(LIB)
    (tmp_path / "app.py").write_text(APP)
    glib = extract_python_file(tmp_path / "lib.py")
    gapp = extract_python_file(tmp_path / "app.py")
    return glib, gapp


def test_calls_unresolved_before_enrich(tmp_path):
    _glib, gapp = _ingest(tmp_path)
    # file-local pass: helper/Engine.run are defined in lib.py, not app.py → unresolved
    calls = gapp.edges_of("CALLS")
    assert calls, "expected CALLS edges in app.py"
    assert all(not e.resolved for e in calls)


def test_enrich_resolves_cross_file_function_call(tmp_path):
    glib, gapp = _ingest(tmp_path)
    summary = enrich_calls([glib, gapp])
    assert summary["jedi_available"] is True
    assert summary["newly_resolved"] >= 1
    resolved = {(e.src, e.dst) for e in gapp.edges_of("CALLS") if e.resolved}
    lib_path = str((tmp_path / "lib.py").resolve())
    # main() → helper defined in lib.py
    assert any(dst == f"{lib_path}::helper" for _src, dst in resolved)


def test_enrich_resolves_cross_file_method_call(tmp_path):
    glib, gapp = _ingest(tmp_path)
    enrich_calls([glib, gapp])
    lib_path = str((tmp_path / "lib.py").resolve())
    resolved = {e.dst for e in gapp.edges_of("CALLS") if e.resolved}
    # e.run() → Engine.run defined in lib.py
    assert f"{lib_path}::Engine.run" in resolved


def test_enrich_is_idempotent(tmp_path):
    glib, gapp = _ingest(tmp_path)
    first = enrich_calls([glib, gapp])
    second = enrich_calls([glib, gapp])
    # nothing new to resolve on the second pass
    assert second["newly_resolved"] == 0
    assert first["newly_resolved"] >= 1


def test_enrich_preserves_file_local_resolution(tmp_path):
    # a self-contained file: file-local pass already resolved its call
    (tmp_path / "solo.py").write_text("def a():\n    return b()\n\n\ndef b():\n    return 1\n")
    g = extract_python_file(tmp_path / "solo.py")
    before = {(e.src, e.dst) for e in g.edges_of("CALLS") if e.resolved}
    enrich_calls([g])
    after = {(e.src, e.dst) for e in g.edges_of("CALLS") if e.resolved}
    assert before == after  # already-resolved edges untouched
