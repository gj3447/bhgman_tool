"""Floating concept-node scan TDD — Longinus binding discipline.

# KG: lesson-concept-nodes-created-without-longinus-binding-float-2026-05-29
"""

from __future__ import annotations

from floating_scan import find_floating_concepts, floating_ratio


def _kg():
    nodes = [
        {"labels": ["SourceCodeNode"], "props": {"name": "src-a", "sourcePath": "a.py"}},
        {"labels": ["AbstractClass"], "props": {"name": "BoundConcept"}},  # idx1 → src0
        {"labels": ["AbstractClass"], "props": {"name": "FloatingConcept"}},  # idx2 floating
        {"labels": ["ResearchFinding"], "props": {"name": "FloatingFinding"}},  # idx3 floating
        {"labels": ["SourceCodeNode"], "props": {"name": "src-b", "sourcePath": "b.py"}},  # noise
    ]
    edges = [{"src": 1, "type": "INSTANCE_OF", "dst": 0}]  # BoundConcept bound to src-a
    return nodes, edges


def test_finds_floating_only():
    nodes, edges = _kg()
    assert set(find_floating_concepts(nodes, edges)) == {"FloatingConcept", "FloatingFinding"}


def test_bound_concept_excluded():
    nodes, edges = _kg()
    assert "BoundConcept" not in find_floating_concepts(nodes, edges)


def test_binding_via_reverse_edge_also_counts():
    # edge pointing FROM source TO concept still counts as bound (either direction).
    nodes = [
        {"labels": ["SourceCodeNode"], "props": {"name": "s", "sourcePath": "s.py"}},
        {"labels": ["AbstractClass"], "props": {"name": "C"}},
    ]
    edges = [{"src": 0, "type": "MATERIALIZES", "dst": 1}]
    assert find_floating_concepts(nodes, edges) == []


def test_source_nodes_are_not_reported():
    nodes = [{"labels": ["SourceCodeNode"], "props": {"name": "lonely-src", "sourcePath": "x.py"}}]
    assert find_floating_concepts(nodes, []) == []  # source nodes are not "concepts"


def test_empty_kg():
    assert find_floating_concepts([], []) == []


def test_ratio():
    assert floating_ratio(total_concepts=3, floating_count=2) == 2 / 3
    assert floating_ratio(total_concepts=0, floating_count=0) == 0.0
