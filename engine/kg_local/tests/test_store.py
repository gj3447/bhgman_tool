"""LocalKgStore TDD — JSON 영속 + 스키마 강제 + 그래프 연산.

# KG: bhgman-local-kg-backend-2026-05-28
"""

from __future__ import annotations

import pytest
from engine.kg_local.store import LocalKgStore


def test_merge_node_upsert_by_key(tmp_path):
    s = LocalKgStore(tmp_path / "kg.json")
    s.merge_node(
        "SourceCodeNode", "sourcePath", "a.py", {"name": "a", "sha256": "h", "lineCount": 1}
    )
    s.merge_node(
        "SourceCodeNode", "sourcePath", "a.py", {"name": "a2", "sha256": "h2", "lineCount": 2}
    )
    nodes = s.find_nodes("SourceCodeNode")
    assert len(nodes) == 1  # upsert, not duplicate
    assert nodes[0]["props"]["name"] == "a2" and nodes[0]["props"]["sha256"] == "h2"


def test_merge_node_enforces_required(tmp_path):
    s = LocalKgStore(tmp_path / "kg.json")
    with pytest.raises(ValueError, match="schema violation"):
        s.merge_node("SourceCodeNode", "sourcePath", "x.py", {"name": "x"})  # sha256/lineCount 결손


def test_save_load_roundtrip(tmp_path):
    p = tmp_path / "kg.json"
    s = LocalKgStore(p)
    a = s.merge_node("AbstractClass", "name", "ac", {})
    b = s.merge_node("Node", "name", "m", {})
    s.add_edge(b, "INSTANCE_OF", a)
    s.save()
    s2 = LocalKgStore(p)  # reload
    assert len(s2.nodes) == 2
    assert len(s2.edges) == 1 and s2.edges[0]["type"] == "INSTANCE_OF"


def test_add_edge_dedup(tmp_path):
    s = LocalKgStore(tmp_path / "kg.json")
    a = s.merge_node("AbstractClass", "name", "ac", {})
    b = s.merge_node("Node", "name", "m", {})
    s.add_edge(b, "INSTANCE_OF", a)
    s.add_edge(b, "INSTANCE_OF", a)  # 중복
    assert len(s.edges) == 1


def test_out_edges(tmp_path):
    s = LocalKgStore(tmp_path / "kg.json")
    o = s.merge_node("Topic", "name", "o", {})
    v = s.merge_node("Axis", "name", "math", {})
    s.add_edge(o, "ALIGNS_WITH_AXIS", v)
    edges = s.out_edges(o)
    assert edges == [("ALIGNS_WITH_AXIS", v)]
