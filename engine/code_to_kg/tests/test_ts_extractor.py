"""TDD — tree-sitter Python symbol extraction (POC 2 core).

# KG: lesson-prom16-code-to-kg-tools-2026-05-28
"""

from __future__ import annotations

import pytest

from engine.code_to_kg.ts_extractor import (
    TREE_SITTER_AVAILABLE,
    extract_python_source,
)

pytestmark = pytest.mark.skipif(not TREE_SITTER_AVAILABLE, reason="tree-sitter not installed")

SAMPLE = """
import os
from pathlib import Path

GLOBAL = 1


def helper(x):
    return x + 1


class Widget:
    def __init__(self, n):
        self.n = n

    def render(self):
        return helper(self.n)
"""


def _graph():
    return extract_python_source(SAMPLE, source_path="sample.py")


def test_module_node_present():
    g = _graph()
    mods = [n for n in g.nodes if n.kind == "module"]
    assert len(mods) == 1
    assert mods[0].symbol_id == "sample.py::<module>"
    assert mods[0].source_path == "sample.py"


def test_function_class_method_extracted():
    g = _graph()
    kinds = {n.qualname: n.kind for n in g.nodes}
    assert kinds["helper"] == "function"
    assert kinds["Widget"] == "class"
    assert kinds["Widget.__init__"] == "method"
    assert kinds["Widget.render"] == "method"


def test_defines_edges_nest_correctly():
    g = _graph()
    defines = {(e.src, e.dst) for e in g.edges_of("DEFINES")}
    assert ("sample.py::<module>", "sample.py::helper") in defines
    assert ("sample.py::<module>", "sample.py::Widget") in defines
    # methods are DEFINES children of the class, not the module
    assert ("sample.py::Widget", "sample.py::Widget.render") in defines
    assert ("sample.py::Widget", "sample.py::Widget.__init__") in defines


def test_imports_captured():
    g = _graph()
    imported = {e.dst for e in g.edges_of("IMPORTS")}
    assert "os" in imported
    assert "pathlib" in imported


def test_calls_resolved_to_local_symbol():
    g = _graph()
    # Widget.render calls helper() — helper is defined in-file → resolved edge
    resolved = [e for e in g.edges_of("CALLS") if e.resolved]
    pairs = {(e.src, e.dst) for e in resolved}
    assert ("sample.py::Widget.render", "sample.py::helper") in pairs


def test_sha256_is_span_specific():
    g = _graph()
    by_q = {n.qualname: n for n in g.nodes}
    # different symbols hash differently; module hash != function hash
    assert by_q["helper"].sha256 != by_q["Widget"].sha256
    assert by_q["<module>"].sha256 != by_q["helper"].sha256
    assert len(by_q["helper"].sha256) == 64  # hex sha256


def test_idempotent_extraction():
    g1 = extract_python_source(SAMPLE, "sample.py")
    g2 = extract_python_source(SAMPLE, "sample.py")
    ids1 = sorted(n.symbol_id for n in g1.nodes)
    ids2 = sorted(n.symbol_id for n in g2.nodes)
    assert ids1 == ids2  # stable symbol identity → MERGE-safe


def test_syntax_error_recovers_gracefully():
    # tree-sitter error recovery (PROM 16 A4): partial source still yields symbols
    g = extract_python_source("def good():\n    return 1\n\ndef bad(:\n", "broken.py")
    names = {n.name for n in g.nodes}
    assert "good" in names
