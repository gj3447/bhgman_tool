"""효능 라인 KG runner — 주입 CypherRunner로 군단장 라벨셋 fetch → harness.

occam/kg_adapter 와 동일한 CypherRunner 패턴 (실전=Neo4j, 테스트=fake rows).
label_cypher 없는 군단장은 oracle 미구축 → UNMEASURABLE 직행 (fetch 안 함).

# KG: efficacy-occam-sigma-ab-2026-06-01
"""

from __future__ import annotations

from collections.abc import Callable

from engine.efficacy.commanders import COMMANDERS
from engine.efficacy.harness import run_efficacy
from engine.efficacy.models import (
    CommanderEfficacySpec,
    EfficacyResult,
    LabeledItem,
    Verdict,
)

CypherRunner = Callable[[str, dict], "list[dict]"]

MIN_LABELS = 10  # 양/음 합 이보다 적으면 통계 신뢰 불가 (소표본 정직 라벨)


def _row_to_item(row: dict) -> LabeledItem:
    sig = row.get("signal")
    return LabeledItem(
        item_id=str(row.get("item_id", "?")),
        is_positive=bool(row.get("is_positive")),
        signal=None if sig is None else float(sig),
        provenance=str(row.get("provenance") or ""),
    )


def evaluate_commander(spec: CommanderEfficacySpec, run_cypher: CypherRunner) -> EfficacyResult:
    """한 군단장 효능 측정. label_cypher 없으면 oracle 미구축으로 UNMEASURABLE."""
    if spec.label_cypher is None:
        return EfficacyResult(
            commander=spec.commander,
            verdict=Verdict.UNMEASURABLE,
            auc=None,
            reason=f"oracle 미구축 — {spec.known_falsifier or spec.oracle_source}",
        )
    rows = run_cypher(spec.label_cypher, {})
    items = [_row_to_item(r) for r in rows]
    result = run_efficacy(spec, items)
    if (
        result.n_positive + result.n_negative < MIN_LABELS
        and result.verdict != Verdict.UNMEASURABLE
    ):
        return EfficacyResult(
            commander=spec.commander,
            verdict=Verdict.UNMEASURABLE,
            auc=result.auc,
            preflight=result.preflight,
            n_positive=result.n_positive,
            n_negative=result.n_negative,
            reason=f"소표본(n={result.n_positive + result.n_negative}<{MIN_LABELS}) — 통계 신뢰 불가",
        )
    return result


def evaluate_all(run_cypher: CypherRunner) -> list[EfficacyResult]:
    """7군단장 전체 효능맵."""
    return [evaluate_commander(spec, run_cypher) for spec in COMMANDERS]


__all__ = ["CypherRunner", "MIN_LABELS", "evaluate_all", "evaluate_commander"]
