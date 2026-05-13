"""Graph Edit Distance — Sanfeliu-Fu 1983 + Hungarian bipartite (Riesen-Bunke 2009).

GED(G_kg, G_code) = Σ(c_ins + c_del + c_relabel)
Drift Score = GED / max(|V_kg|, |V_code|)

본 prototype 은 *간단한 label-based* GED (full graph isomorphism 아님).
실 production: networkx graph_edit_distance 위임 권장.
"""
from __future__ import annotations

from typing import Iterable

from models import CodeSymbol, GedReport, KgRefRecord


def compute_ged(
    *,
    kg_refs: dict[str, KgRefRecord],
    code_symbols: Iterable[CodeSymbol],
    cost_insert: int = 1,
    cost_delete: int = 1,
    cost_relabel: int = 1,
) -> GedReport:
    """Label-based GED — node identity by sourceId/symbol-name.

    - insertions: KG ref 존재 ∧ 코드에서 미참조 (코드 측에 *추가*해야 함)
    - deletions: 코드 ref 존재 ∧ KG 미존재 (KG 측 *삭제* 또는 코드 측 *제거*)
    - relabels: sourceId 매치 ∧ sourcePath 불일치 (label 차이)
    """
    kg_names = set(kg_refs.keys())
    code_kg_refs: dict[str, list[CodeSymbol]] = {}
    syms = list(code_symbols)
    for s in syms:
        for ref in s.kg_refs:
            code_kg_refs.setdefault(ref, []).append(s)

    code_names = set(code_kg_refs.keys())

    # Insertions: in KG, not in code
    only_kg = kg_names - code_names
    # Deletions: in code, not in KG
    only_code = code_names - kg_names
    # Relabels: in both, but sourcePath differs
    common = kg_names & code_names
    relabels = 0
    for name in common:
        kg_path = kg_refs[name].sourcePath
        code_paths = {s.sourcePath for s in code_kg_refs[name]}
        if kg_path not in code_paths:
            relabels += 1

    insertions = len(only_kg)
    deletions = len(only_code)

    ged = insertions * cost_insert + deletions * cost_delete + relabels * cost_relabel

    kg_size = len(kg_names)
    code_size = len(code_names)
    denom = max(kg_size, code_size, 1)
    normalized = ged / denom
    if normalized > 1.0:
        normalized = 1.0

    return GedReport(
        kg_node_count=kg_size,
        code_node_count=code_size,
        insertions=insertions,
        deletions=deletions,
        relabels=relabels,
        ged_total=ged,
        normalized_score=normalized,
    )


def drift_score_to_severity(score: float) -> str:
    """0.0 (clean) ~ 1.0 (catastrophic) → human-readable."""
    if score == 0.0:
        return "PERFECT"
    if score < 0.05:
        return "EXCELLENT"
    if score < 0.15:
        return "ACCEPTABLE"
    if score < 0.35:
        return "DEGRADED"
    return "CRITICAL"
