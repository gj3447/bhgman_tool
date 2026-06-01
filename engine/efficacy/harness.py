"""효능 측정 하네스 — preflight 게이트 → metric vs baselines → 정직 verdict. 순수.

흐름 (모든 군단장 공통):
  1. run_preflight 3 게이트.
  2. 실패 → Verdict.UNMEASURABLE + 실패 사유 (수치 날조 금지).
  3. 통과 → 방향보정 AUC 산출 + baselines(random=0.5) 비교.
     · AUC > 0.5 → MEASURED
     · AUC ≤ 0.5 → BELOW_CHANCE (게이트는 통과했으나 효능 없음 실측)

# KG: efficacy-occam-sigma-ab-2026-06-01, project_bhgman_ab_falsifier_2026_05_30
"""

from __future__ import annotations

from collections.abc import Sequence

from engine.efficacy.falsifier import directional_auc, run_preflight
from engine.efficacy.models import (
    CommanderEfficacySpec,
    EfficacyResult,
    FalsifierKind,
    LabeledItem,
    Verdict,
)

_REASON = {
    FalsifierKind.CIRCULARITY: "라벨을 군단장 자신이 생성(동어반복)",
    FalsifierKind.SIGNAL_ABSENT: "metric 입력 신호가 데이터에 부재",
    FalsifierKind.SIGNAL_INVERTED: "주 신호가 기대와 반대 방향(chance 미만)",
}


def run_efficacy(spec: CommanderEfficacySpec, items: Sequence[LabeledItem]) -> EfficacyResult:
    """한 군단장 효능 측정. preflight 게이트가 결과의 신뢰성을 강제한다."""
    n_pos = sum(1 for it in items if it.is_positive)
    n_neg = len(items) - n_pos

    if not items:
        return EfficacyResult(
            commander=spec.commander,
            verdict=Verdict.UNMEASURABLE,
            auc=None,
            reason="oracle 미구축 — 라벨셋 0 (label_cypher 부재 또는 빈 결과)",
        )

    pre = run_preflight(items, spec.circularity_keywords, spec.expected_direction)

    if not pre.passed:
        reasons = "; ".join(_REASON[f] for f in pre.failures)
        return EfficacyResult(
            commander=spec.commander,
            verdict=Verdict.UNMEASURABLE,
            auc=pre.raw_auc,
            preflight=pre,
            n_positive=n_pos,
            n_negative=n_neg,
            reason=f"preflight FAIL: {reasons}",
        )

    auc = directional_auc(items, spec.expected_direction)
    verdict = Verdict.MEASURED if (auc is not None and auc > 0.5) else Verdict.BELOW_CHANCE
    return EfficacyResult(
        commander=spec.commander,
        verdict=verdict,
        auc=auc,
        baselines={"random": 0.5},
        preflight=pre,
        n_positive=n_pos,
        n_negative=n_neg,
        reason="3 게이트 통과 — AUC vs random(0.5)",
    )


__all__ = ["run_efficacy"]
