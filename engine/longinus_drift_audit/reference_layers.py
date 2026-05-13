"""7-Layer Reference Model — extraction utilities.

SKILL.md §"7-Layer Reference Model" 의 layer-별 의미 추출.
"""
from __future__ import annotations

from typing import Iterable

from models import CodeSymbol, KgRefRecord, LayerCoverage, ReferenceSite


def compress_kg_ref(*, sourceId: str, sourcePath: str) -> str:
    """L6 — Information Compression.

    한 줄 ``# KG: <sourceId>`` (sourcePath은 추론 가능: file:line of the comment) 가
    7 layer 의미를 동시에 운반함.
    """
    return f"# KG: {sourceId}  // {sourcePath}"


def layer_coverage(*, sites: Iterable[ReferenceSite], total_kg_refs: int, pierce_rate: float) -> LayerCoverage:
    """간이 layer coverage — 모든 site 가 정상이면 각 layer 1.0.

    pierce_rate (L7): 코드 lines per KG ref. ``1`` 이상이면 healthy.
    """
    sites_list = list(sites)
    if not sites_list:
        return LayerCoverage(
            L1_address=1.0 if total_kg_refs == 0 else 0.0,
            L2_lifetime=1.0,
            L3_type=1.0,
            L4_semiotic=1.0,
            L5_distributed=1.0,
            L6_compression=1.0 if total_kg_refs == 0 else 0.0,
            L7_aesthetic_pierce_rate=pierce_rate,
        )

    l1 = sum(1 for s in sites_list if s.sourcePath) / len(sites_list)
    l2 = sum(1 for s in sites_list if s.drift_detected_at is None) / len(sites_list)
    l3 = sum(1 for s in sites_list if s.drift_score == 0.0) / len(sites_list)
    l4 = sum(1 for s in sites_list if s.sourceId and s.sourcePath) / len(sites_list)
    l5 = 1.0  # KG MERGE는 always-idempotent (caller guaranteed)
    l6 = 1.0 if total_kg_refs <= len(sites_list) * 2 else 0.5  # compression ratio
    return LayerCoverage(
        L1_address=l1, L2_lifetime=l2, L3_type=l3, L4_semiotic=l4,
        L5_distributed=l5, L6_compression=l6,
        L7_aesthetic_pierce_rate=pierce_rate,
    )


def make_pierce_rate(*, total_code_symbols: int, total_kg_refs: int) -> float:
    """L7 — pierce rate. *최소 침습으로 최대 추적*.

    Definition: kg_refs / code_symbols. 0.5 ≈ 절반의 심볼이 KG-referenced.
    """
    if total_code_symbols == 0:
        return 0.0
    return min(total_kg_refs / total_code_symbols, 1.0)


def symbol_to_reference_site(
    *, sym: CodeSymbol, kg_record: KgRefRecord
) -> ReferenceSite:
    return ReferenceSite(
        sourceId=kg_record.sourceId,
        sourcePath=sym.sourcePath,
    )
