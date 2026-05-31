"""Floating concept-node scan — Longinus binding discipline (enforcement side).

A concept node (AbstractClass / ResearchFinding / Lesson / Concept / KnowledgeHub)
is *floating* when it has NO edge connecting it to a SourceCodeNode — i.e. it was
created without a Longinus binding to source, so it cannot be reached by legion
synthesis or TPA design-recovery and effectively "floats".

This is the missing third orphan scan, complementing:
  - reverse_orphan_scan: Code→KG  (a code symbol with no `# KG:` ref)
  - forward_orphan_scan:  KG→disk (a :KnowledgeHub with no package_path)
  - floating_scan (here): KG-internal (a concept node with no binding to source)

Pure (no IO). Feed it LocalKgStore.nodes + .edges (lists of {labels,props} / {src,type,dst}).

# KG: lesson-concept-nodes-created-without-longinus-binding-float-2026-05-29,
#     bhgman-local-kg-backend-2026-05-28
"""

from __future__ import annotations

from typing import Any

CONCEPT_LABELS: tuple[str, ...] = (
    "AbstractClass",
    "ResearchFinding",
    "Finding",
    "Lesson",
    "Concept",
    "KnowledgeHub",
)
SOURCE_LABEL = "SourceCodeNode"


def _source_indices(nodes: list[dict[str, Any]], source_label: str) -> set[int]:
    return {i for i, n in enumerate(nodes) if source_label in n.get("labels", [])}


def _bound_indices(edges: list[dict[str, Any]], src_idx: set[int]) -> set[int]:
    """Node indices that touch a SourceCodeNode via any edge (either direction)."""
    bound: set[int] = set()
    for e in edges:
        s, d = e.get("src"), e.get("dst")
        if d in src_idx and s is not None:
            bound.add(s)
        if s in src_idx and d is not None:
            bound.add(d)
    return bound


def find_floating_concepts(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    *,
    concept_labels: tuple[str, ...] = CONCEPT_LABELS,
    source_label: str = SOURCE_LABEL,
) -> list[str]:
    """Return names of concept nodes with NO edge to any SourceCodeNode (floating)."""
    src_idx = _source_indices(nodes, source_label)
    bound = _bound_indices(edges, src_idx)
    floating: list[str] = []
    for i, n in enumerate(nodes):
        if i in bound:
            continue
        if any(lbl in concept_labels for lbl in n.get("labels", [])):
            floating.append(n.get("props", {}).get("name", f"node[{i}]"))
    return floating


def floating_ratio(*, total_concepts: int, floating_count: int) -> float:
    """floating / total concept nodes. 0.0 = all bound, 1.0 = all floating."""
    if total_concepts <= 0:
        return 0.0
    return floating_count / total_concepts


__all__ = ["CONCEPT_LABELS", "find_floating_concepts", "floating_ratio"]
