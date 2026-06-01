"""7군단장 효능 측정 라인 — value objects (순수).

오캄 σ 효능 A/B(efficacy-occam-sigma-ab-2026-06-01)에서 배운 것을 *모든 군단장*에 일반화:
효능 수치를 믿기 전에 3 falsifier 게이트(순환성/신호부재/신호역전)를 먼저 통과해야 한다.
못 통과하면 수치를 날조하지 말고 UNMEASURABLE + 사유로 정직 보고.

# KG: efficacy-occam-sigma-ab-2026-06-01, project_bhgman_ab_falsifier_2026_05_30,
#     feedback_efficacy_via_borrowed_theory_tests, 7cmd-measurement-driven-conditional-dispatch-2026-05-30
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Verdict(str, Enum):
    MEASURED = "MEASURED"  # 3 게이트 통과 + metric 산출
    BELOW_CHANCE = "BELOW_CHANCE"  # 게이트 통과했으나 metric ≤ chance (효능 없음 실측)
    UNMEASURABLE = "UNMEASURABLE"  # 게이트 실패 — 효능 측정 불가 (날조 금지)


class FalsifierKind(str, Enum):
    CIRCULARITY = "CIRCULARITY"  # 라벨을 그 군단장 자신의 로직이 만듦 → 동어반복
    SIGNAL_ABSENT = "SIGNAL_ABSENT"  # metric 입력 신호가 데이터에 없음
    SIGNAL_INVERTED = "SIGNAL_INVERTED"  # 주 신호가 기대와 반대 방향 (chance 미만)


class Direction(str, Enum):
    HIGHER = "higher"  # positive(예: stale)일수록 signal 큼
    LOWER = "lower"  # positive일수록 signal 작음


@dataclass(frozen=True)
class LabeledItem:
    """효능 평가 한 단위. signal=None 이면 신호 부재(가용성 계산에 반영)."""

    item_id: str
    is_positive: bool  # ground-truth 양성 (군단장이 작동해야 할 대상)
    signal: float | None  # 군단장 metric의 주 신호값 (없으면 None)
    provenance: str = ""  # 라벨 출처 텍스트 (순환성 검사용)


@dataclass(frozen=True)
class PreflightReport:
    """3 falsifier 게이트 결과. passed=True 여야 metric 신뢰 가능."""

    circularity_ratio: float  # 양성 라벨 중 군단장-생성 비율
    signal_availability: float  # signal not-None 비율
    raw_auc: float | None  # 방향보정 전 AUC (가용성 0이면 None)
    failures: tuple[FalsifierKind, ...] = ()

    @property
    def passed(self) -> bool:
        return not self.failures


@dataclass(frozen=True)
class CommanderEfficacySpec:
    """한 군단장의 효능 측정 명세. label_cypher 로 라벨셋 fetch (None이면 oracle 미구축)."""

    commander: str
    verb: str  # 획득/연결/정리/발견·창조/검증/출격/실현
    task: str  # 효능 주장 (무엇을 baseline보다 잘하는가)
    metric: str  # AUC / precision / drift-rate 등
    oracle_source: str  # ground-truth 출처 (인용 정전 우선)
    required_signal: str  # metric 입력으로 필요한 KG 필드/신호
    expected_direction: Direction
    circularity_keywords: tuple[str, ...] = ()  # provenance에 이게 있으면 군단장-생성 라벨
    label_cypher: str | None = None  # 라벨셋 fetch cypher (None = oracle 미구축)
    known_falsifier: str = ""


@dataclass(frozen=True)
class EfficacyResult:
    """한 군단장 효능 측정 결과."""

    commander: str
    verdict: Verdict
    auc: float | None
    baselines: dict[str, float] = field(default_factory=dict)
    preflight: PreflightReport | None = None
    n_positive: int = 0
    n_negative: int = 0
    reason: str = ""

    @property
    def summary(self) -> str:
        a = f"AUC={self.auc:.3f}" if self.auc is not None else "AUC=n/a"
        return (
            f"[{self.commander}] {self.verdict.value} {a} "
            f"(pos={self.n_positive}/neg={self.n_negative}) — {self.reason}"
        )


__all__ = [
    "CommanderEfficacySpec",
    "Direction",
    "EfficacyResult",
    "FalsifierKind",
    "LabeledItem",
    "PreflightReport",
    "Verdict",
]
