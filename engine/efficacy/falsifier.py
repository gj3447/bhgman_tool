"""효능 측정 3-falsifier 게이트 — 이 라인의 심장 (순수 함수).

오캄 σ A/B(efficacy-occam-sigma-ab-2026-06-01)에서 효능 측정을 막은 3가지를 일반화한
pre-flight 게이트. metric을 믿기 *전* 강제. 어느 하나라도 실패면 UNMEASURABLE.

  1. CIRCULARITY    — 양성 라벨을 그 군단장 자신의 로직이 만들었나 (provenance ∩ keywords).
                      >threshold → 동어반복, 효능 아닌 self-prediction.
  2. SIGNAL_ABSENT  — metric 입력 신호(signal)가 데이터에 실제 있나 (non-None 비율).
                      <threshold → 잴 신호가 없음.
  3. SIGNAL_INVERTED — 주 신호가 기대 방향으로 chance 이상 분리하나 (방향보정 AUC).
                      기대 미만 → 신호가 거꾸로 (오캄 twin율 41<59 사례).

# KG: efficacy-occam-sigma-ab-2026-06-01, feedback_efficacy_via_borrowed_theory_tests,
#     feedback_self_review_needs_empirical_check
"""

from __future__ import annotations

from collections.abc import Sequence

from engine.efficacy.metrics import auc_mann_whitney
from engine.efficacy.models import (
    Direction,
    FalsifierKind,
    LabeledItem,
    PreflightReport,
)

# 기본 임계 — circularity 절반 초과면 오염, 신호 가용 절반 미만이면 부재.
CIRCULARITY_MAX = 0.5
AVAILABILITY_MIN = 0.5


def circularity_ratio(items: Sequence[LabeledItem], keywords: Sequence[str]) -> float:
    """양성 라벨 중 provenance가 군단장 keyword를 포함하는 비율. keyword 없으면 0."""
    positives = [it for it in items if it.is_positive]
    if not positives or not keywords:
        return 0.0
    lowered = [k.lower() for k in keywords]
    hits = sum(
        1 for it in positives if any(k in (it.provenance or "").lower() for k in lowered)
    )
    return hits / len(positives)


def signal_availability(items: Sequence[LabeledItem]) -> float:
    """signal not-None 비율. 빈 셋이면 0.0."""
    if not items:
        return 0.0
    return sum(1 for it in items if it.signal is not None) / len(items)


def directional_auc(items: Sequence[LabeledItem], direction: Direction) -> float | None:
    """방향보정 AUC: 신호 있는 항목만, LOWER 기대면 1-AUC로 뒤집어 '높을수록 양성' 정규화.

    신호 있는 pos/neg 둘 다 있어야 산출, 아니면 None."""
    pos = [it.signal for it in items if it.is_positive and it.signal is not None]
    neg = [it.signal for it in items if not it.is_positive and it.signal is not None]
    if not pos or not neg:
        return None
    raw = auc_mann_whitney(pos, neg)
    return 1.0 - raw if direction is Direction.LOWER else raw


def run_preflight(
    items: Sequence[LabeledItem],
    keywords: Sequence[str],
    direction: Direction,
    circularity_max: float = CIRCULARITY_MAX,
    availability_min: float = AVAILABILITY_MIN,
) -> PreflightReport:
    """3 게이트 실행. 통과(failures 빈튜플) 시에만 metric 신뢰."""
    circ = circularity_ratio(items, keywords)
    avail = signal_availability(items)
    auc = directional_auc(items, direction)

    failures: list[FalsifierKind] = []
    if circ > circularity_max:
        failures.append(FalsifierKind.CIRCULARITY)
    if avail < availability_min:
        failures.append(FalsifierKind.SIGNAL_ABSENT)
    # 신호가 충분히 있는데(부재 게이트 통과) chance 미만이면 역전. 가용성 실패 시 중복 보고 안 함.
    # auc==0.5(정확히 chance)는 역전 아님 — 게이트 통과시키고 harness가 BELOW_CHANCE로 판정.
    if avail >= availability_min and auc is not None and auc < 0.5:
        failures.append(FalsifierKind.SIGNAL_INVERTED)

    return PreflightReport(
        circularity_ratio=circ,
        signal_availability=avail,
        raw_auc=auc,
        failures=tuple(failures),
    )


__all__ = [
    "AVAILABILITY_MIN",
    "CIRCULARITY_MAX",
    "circularity_ratio",
    "directional_auc",
    "run_preflight",
    "signal_availability",
]
