"""효능 metric — AUC (Mann-Whitney U) + 분류 지표. 순수 함수.

AUC = P(signal_pos > signal_neg) + 0.5·P(tie) — Mann-Whitney U 통계량의 정규화.
오캄 A/B에서 cypher로 했던 것을 코드화 (손계산 3711/9072=0.409 검증된 식).

# KG: efficacy-occam-sigma-ab-2026-06-01
"""

from __future__ import annotations

from collections.abc import Sequence


def auc_mann_whitney(pos_scores: Sequence[float], neg_scores: Sequence[float]) -> float:
    """AUC = pairwise concordance. pos/neg 중 하나라도 비면 0.5 (정보 없음).

    tie는 0.5로 계산 (이진 신호에서도 정확). O(n·m) — 효능셋은 작아 충분."""
    n_pos, n_neg = len(pos_scores), len(neg_scores)
    if n_pos == 0 or n_neg == 0:
        return 0.5
    concord = 0.0
    for p in pos_scores:
        for q in neg_scores:
            if p > q:
                concord += 1.0
            elif p == q:
                concord += 0.5
    return concord / (n_pos * n_neg)


def precision_recall_f1(
    true_pos: int, false_pos: int, false_neg: int
) -> tuple[float, float, float]:
    """precision / recall / F1. 분모 0이면 해당 지표 0.0."""
    precision = true_pos / (true_pos + false_pos) if (true_pos + false_pos) else 0.0
    recall = true_pos / (true_pos + false_neg) if (true_pos + false_neg) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return precision, recall, f1


__all__ = ["auc_mann_whitney", "precision_recall_f1"]
