"""TDD — CodeGraph → KG sinks (local JSON store + Neo4j Cypher).

# KG: lesson-prom16-code-to-kg-tools-2026-05-28, bhgman-local-kg-backend-2026-05-28
"""

from __future__ import annotations

import pytest

from ts_extractor import TREE_SITTER_AVAILABLE, extract_python_source
from kg_writer import to_cypher, write_local, UMBRELLA_LABEL

pytestmark = pytest.mark.skipif(not TREE_SITTER_AVAILABLE, reason="tree-sitter not installed")

SAMPLE = "def a():\n    return b()\n\n\ndef b():\n    return 1\n"


# ── Neo4j Cypher sink ──────────────────────────────────────────────────────


def test_to_cypher_emits_merge_for_every_node():
    g = extract_python_source(SAMPLE, "m.py")
    stmts = to_cypher(g)
    prefix = "MERGE (s:" + UMBRELLA_LABEL
    merges = [s for s in stmts if s.startswith(prefix)]
    assert len(merges) == g.node_count()
    # umbrella + specific label both set
    assert any("SET s:CodeFunction" in s for s in merges)


def test_to_cypher_weaves_to_sourcecodenode():
    g = extract_python_source(SAMPLE, "m.py")
    stmts = to_cypher(g)
    assert any("SourceCodeNode {sourcePath: 'm.py'}" in s and "DERIVED_FROM" in s for s in stmts)


def test_to_cypher_resolved_call_edge():
    g = extract_python_source(SAMPLE, "m.py")
    stmts = to_cypher(g)
    # a() calls b() — both in-file → resolved CALLS by symbol_id
    assert any(":CALLS" in s and "m.py::a" in s and "m.py::b" in s for s in stmts)


def test_to_cypher_external_stub_for_imports():
    g = extract_python_source("import os\n\ndef f():\n    return os.getcwd()\n", "x.py")
    stmts = to_cypher(g, include_external=True)
    assert any("CodeExternal {name: 'os'}" in s for s in stmts)
    assert any(":IMPORTS" in s for s in stmts)


def test_to_cypher_is_escaped():
    # apostrophes in names would break naive cypher; ensure escaping
    g = extract_python_source("def f():\n    return 1\n", "o'brien.py")
    stmts = to_cypher(g)
    assert any("o\\'brien.py" in s for s in stmts)


# ── local JSON store sink ──────────────────────────────────────────────────


class FakeStore:
    """Minimal LocalKgStore duck — merge_node / find_one / add_edge."""

    def __init__(self):
        self.nodes = []
        self.edges = []

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
        si, di = self.nodes.index(src), self.nodes.index(dst)
        e = {"src": si, "type": type_, "dst": di}
        if e not in self.edges:
            self.edges.append(e)


def test_write_local_merges_nodes_and_edges():
    g = extract_python_source(SAMPLE, "m.py")
    store = FakeStore()
    summary = write_local(g, store)
    assert summary["nodes_merged"] == g.node_count()
    assert summary["edges"]["DEFINES"] == 2  # a, b
    assert summary["edges"]["CALLS"] == 1  # a -> b
    # every node carries umbrella + specific label
    labels = [set(n["labels"]) for n in store.nodes]
    assert all(UMBRELLA_LABEL in ls for ls in labels)


def test_write_local_is_idempotent():
    g = extract_python_source(SAMPLE, "m.py")
    store = FakeStore()
    write_local(g, store)
    n_after_first = len(store.nodes)
    e_after_first = len(store.edges)
    write_local(g, store)  # second pass
    assert len(store.nodes) == n_after_first  # no duplicate nodes
    assert len(store.edges) == e_after_first  # no duplicate edges


def test_write_local_weaves_to_existing_sourcecodenode():
    g = extract_python_source(SAMPLE, "m.py")
    store = FakeStore()
    # pretend Longinus already ingested this file as a SourceCodeNode
    store.merge_node("SourceCodeNode", "sourcePath", "m.py", {"sha256": "x", "lineCount": 6})
    summary = write_local(g, store)
    assert summary["derived_from"] == 1
    assert any(e["type"] == "DERIVED_FROM" for e in store.edges)
