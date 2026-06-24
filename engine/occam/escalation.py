"""오캄 escalation — '불확실하면 자동 escalation' 게이트 (순수 함수, IO 없음).

오캄은 archive-only covenant라 잘못 supersede해도 reversible이지만, 그래도 KG 의미 계층을
왜곡할 수 있다. 이 모듈은 OccamReport의 *불확실* 케이스를 flag/report에 묻어두지 않고
적대적 검증 무기로 명시 routing한다 (challenge: flag 중심 → escalation 중심).

routing 규칙 (어느 케이스가 어느 무기로 가는가):
  · candidate, verdict=VERIFY (σ 회색지대) 또는 FLAG_ONLY        → 나생문 /tlb constitutional
  · candidate, verdict 미부착 + confidence=MEDIUM (디스크 truth   → 나생문 /tlb constitutional
    부재, line-count 휴리스틱 추정)                                 (자동 supersede 전 검증)
  · candidate, confidence=HIGH + verdict=SUPERSEDE/None          → escalation 없음 (확정, 안전)
  · disk-orphan (flag-only, machloket/Eilu va-Eilu)             → Longinus drift audit
    (진짜 dead인지 / 의도적 보존인지 KG↔disk 정합으로 판정)
  · semantic near-dup (byte identity 없음, embedding cosine)     → 나생문 /tlb constitutional
    (단독 supersede 금지 — semantic-only는 검증 필수)

산출물 EscalationPlan은 *실행 계획*이지 실행이 아니다 (재배맨 SOP / legion이 dispatch).
covenant 유지: 이 모듈은 KG도 disk도 건드리지 않는다 — 후보 → 검증요청 매핑만.

# KG: occam-kam-canonical-2026-05-26,
#     verdict-user-occam-gains-ontology-hygiene-responsibility-2026-05-27,
#     dt-occam-naesengmoon-confidence
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from engine.occam.occam_models import Confidence, OccamReport, SupersessionCandidate

# escalation 대상 무기 (5대 무기 중 적대적 검증 + 참조 접지).
TARGET_NAESENGMOON = "naesengmoon"  # 적대적 검증 (/tlb)
TARGET_LONGINUS = "longinus"  # KG↔code 참조 접지 / drift audit

_DEFAULT_LENS = "constitutional"  # 나생문 기본 LensSet (KG 등록된 임의 LensSet로 교체 가능)


@dataclass(frozen=True)
class EscalationItem:
    """검증 무기로 보내는 단일 escalation 요청 (실행 전 계획)."""

    target: str  # TARGET_NAESENGMOON | TARGET_LONGINUS
    subject: str  # 대상 노드 식별자 (name 우선, 없으면 path)
    reason: str  # 왜 escalate하는가 (감사 가능)
    command: str  # 권장 invocation (예: "/tlb <subject> --lens constitutional")
    lens: str | None = None  # 나생문 LensSet (longinus면 None)


@dataclass(frozen=True)
class EscalationPlan:
    """OccamReport에서 도출한 escalation 요청 묶음."""

    items: tuple[EscalationItem, ...] = ()

    @property
    def count(self) -> int:
        return len(self.items)

    @property
    def summary(self) -> str:
        if not self.items:
            return "occam[escalate]: 0 escalations (all candidates confirmed or none)"
        naes = sum(1 for i in self.items if i.target == TARGET_NAESENGMOON)
        longi = sum(1 for i in self.items if i.target == TARGET_LONGINUS)
        return f"occam[escalate]: {self.count} escalation(s) → 나생문={naes} longinus={longi}"


def _ident(node) -> str:
    """표시용 식별자 (never None) — name 우선, 없으면 sourcePath."""
    return getattr(node, "name", None) or getattr(node, "source_path", "?")


def _candidate_needs_verify(c: SupersessionCandidate) -> bool:
    """이 후보를 자동 supersede 전에 나생문으로 보내야 하는가.

    자동 통과(escalation 불요)는 *확신* 케이스뿐: disk-truth가 current를 확정(HIGH)하고
    σ도 SUPERSEDE(또는 σ 미배선). 그 외 전부 escalate — MEDIUM(line-count 추정), VERIFY/KEEP
    /FLAG_ONLY(σ가 obsolescence 근거 부족이라 판단), HIGH인데 σ가 SUPERSEDE 아님(불일치)."""
    confident_supersede = c.confidence is Confidence.HIGH and c.verdict in (None, "SUPERSEDE")
    return not confident_supersede


def _naesengmoon_item(subject: str, reason: str) -> EscalationItem:
    return EscalationItem(
        target=TARGET_NAESENGMOON,
        subject=subject,
        reason=reason,
        command=f"/tlb {subject} --lens {_DEFAULT_LENS}",
        lens=_DEFAULT_LENS,
    )


def build_escalation_plan(
    report: OccamReport,
    *,
    semantic_pairs: Iterable = (),
) -> EscalationPlan:
    """OccamReport(+ optional semantic near-dup 쌍) → EscalationPlan.

    불확실 후보는 나생문, disk-orphan은 Longinus로 routing. HIGH-confidence SUPERSEDE는
    escalation하지 않는다 (자동 supersede 안전). semantic_pairs는 semantic_dedup.NearDupPair
    iterable — byte identity 없는 의미론 중복은 항상 나생문 검증 (단독 supersede 금지).
    """
    items: list[EscalationItem] = []

    for c in report.candidates:
        if not _candidate_needs_verify(c):
            continue
        subject = _ident(c.stale)
        why = c.verdict or c.confidence.value
        items.append(
            _naesengmoon_item(
                subject,
                f"uncertain supersession ({why}) of '{subject}' → verify before archive: {c.reason}",
            )
        )

    for orphan in report.orphans:
        subject = _ident(orphan)
        items.append(
            EscalationItem(
                target=TARGET_LONGINUS,
                subject=subject,
                reason=(
                    f"disk-orphan '{subject}' (no live twin) — machloket/Eilu va-Eilu: "
                    f"confirm truly dead vs intentionally preserved via KG↔disk drift audit"
                ),
                command=f"/longinus audit {subject}",
                lens=None,
            )
        )

    for pair in semantic_pairs:
        drop = getattr(pair, "drop_id", "?")
        sim = getattr(pair, "similarity", 0.0)
        items.append(
            _naesengmoon_item(
                drop,
                f"semantic near-duplicate (cosine={sim:.2f}, no byte identity) of "
                f"'{getattr(pair, 'keep_id', '?')}' → verify before archive (no auto-supersede)",
            )
        )

    return EscalationPlan(items=tuple(items))


__all__ = [
    "TARGET_LONGINUS",
    "TARGET_NAESENGMOON",
    "EscalationItem",
    "EscalationPlan",
    "build_escalation_plan",
]
