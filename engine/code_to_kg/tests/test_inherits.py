"""TDD — INHERITS edges + confidence_tier (code-review-graph absorption).

CRG (tirth8205) carries type-hierarchy edges + edge-level confidence tiers that
our :CodeSymbol schema lacked. This covers the absorbed subset.

# KG: lesson-prom16-code-to-kg-tools-2026-05-28, finding-crg-scip-isomorphism-2026-05-29
"""

from __future__ import annotations

import pytest

from ts_extractor import TREE_SITTER_AVAILABLE, extract_python_source, extract_python_file
from kg_writer import to_cypher, write_local
from enrich import enrich_calls, JEDI_AVAILABLE

pytestmark = pytest.mark.skipif(not TREE_SITTER_AVAILABLE, reason="tree-sitter not installed")

SAMPLE = (
    "class Base:\n"
    "    pass\n"
    "\n"
    "\n"
    "class Widget(Base):\n"
    "    pass\n"
    "\n"
    "\n"
    "class Mixed(Base, external.Thing):\n"
    "    pass\n"
)


def test_inherits_edge_file_local_resolved():
    g = extract_python_source(SAMPLE, "m.py")
    inh = g.edges_of("INHERITS")
    pairs = {(e.src, e.dst, e.resolved) for e in inh}
    # Widget(Base) → Base defined in-file → resolved to symbol_id
    assert ("m.py::Widget", "m.py::Base", True) in pairs


def test_inherits_external_base_unresolved():
    g = extract_python_source(SAMPLE, "m.py")
    inh = g.edges_of("INHERITS")
    # external.Thing → last segment 'Thing', not in-file → unresolved name
    assert any(e.dst == "Thing" and not e.resolved for e in inh)


def test_inherits_in_cypher_with_tier():
    g = extract_python_source(SAMPLE, "m.py")
    stmts = to_cypher(g)
    # resolved INHERITS → edge by id + EXTRACTED tier
    assert any(":INHERITS" in s and "EXTRACTED" in s and "m.py::Base" in s for s in stmts)
    # unresolved external base → AMBIGUOUS tier
    assert any(":INHERITS" in s and "AMBIGUOUS" in s for s in stmts)


def test_defines_edge_carries_extracted_tier():
    g = extract_python_source(SAMPLE, "m.py")
    stmts = to_cypher(g)
    assert any(":DEFINES" in s and "confidence_tier = 'EXTRACTED'" in s for s in stmts)


def test_write_local_counts_inherits():
    g = extract_python_source(SAMPLE, "m.py")

    class FakeStore:
        def __init__(self):
            self.nodes, self.edges = [], []

        def find_one(self, prop, value, label=None):
            for n in self.nodes:
                if label is not None and label not in n["labels"]:
                    continue
                if n["props"].get(prop) == value:
                    return n
            return None

        def merge_node(self, label, key_prop, key_val, props):
            node = self.find_one(key_prop, key_val, label)
            if node is None:
                node = {"labels": [label], "props": {}}
                self.nodes.append(node)
            if label not in node["labels"]:
                node["labels"].append(label)
            node["props"].update({key_prop: key_val, **props})
            return node

        def add_edge(self, src, type_, dst):
            e = {"src": self.nodes.index(src), "type": type_, "dst": self.nodes.index(dst)}
            if e not in self.edges:
                self.edges.append(e)

    store = FakeStore()
    summary = write_local(g, store)
    # Widget→Base resolved in-file (Mixed→Base too) = 2 resolved INHERITS
    assert summary["edges"]["INHERITS"] == 2


@pytest.mark.skipif(not JEDI_AVAILABLE, reason="jedi not installed")
def test_inherits_resolves_cross_file_via_jedi(tmp_path):
    (tmp_path / "base.py").write_text("class Base:\n    pass\n")
    (tmp_path / "sub.py").write_text("from base import Base\n\n\nclass Sub(Base):\n    pass\n")
    gbase = extract_python_file(tmp_path / "base.py")
    gsub = extract_python_file(tmp_path / "sub.py")
    # before enrich: Sub(Base) is unresolved (Base not in sub.py)
    assert all(not e.resolved for e in gsub.edges_of("INHERITS"))
    enrich_calls([gbase, gsub])
    base_path = str((tmp_path / "base.py").resolve())
    resolved = {e.dst for e in gsub.edges_of("INHERITS") if e.resolved}
    assert f"{base_path}::Base" in resolved
