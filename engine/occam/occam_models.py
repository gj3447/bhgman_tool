"""오캄 value objects — 순수 dataclass (외부 검증 아님, 내부 value).

# KG: occam-kam-canonical-2026-05-26, occam-pass-bhgman_tool-2026-05-27
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Confidence(str, Enum):
    # KG: occam-kam-canonical-2026-05-26
    HIGH = "HIGH"  # disk sha가 현재 lineage를 확정
    MEDIUM = "MEDIUM"  # disk 진실 부재, line_count 휴리스틱으로 추정


@dataclass(frozen=True)
class NodeRecord:
    # KG: occam-kam-canonical-2026-05-26
    """KG SourceCodeNode 한 개의 식별 정보."""

    name: str
    source_path: str
    sha256: str
    line_count: int


@dataclass(frozen=True)
class SupersessionCandidate:
    # KG: occam-kam-canonical-2026-05-26
    """대체된 낡은 노드 → 현재 노드. covenant: supersede(archive)지 delete 아님."""

    stale: NodeRecord
    current: NodeRecord
    normalized_path: str
    reason: str
    confidence: Confidence
    action: str = "SUPERSEDED_BY"  # 고정 — 오캄은 archive만, delete 표현 부재
    # 정량 scoring (scoring.score_node). score_meta 미주입 시 None (기존 동작 불변).
    score: float | None = None  # σ ∈ [0,1] — 아카이브 안전도
    verdict: str | None = None  # SUPERSEDE / VERIFY / KEEP / PROTECTED / FLAG_ONLY


@dataclass(frozen=True)
class OccamReport:
    # KG: occam-kam-canonical-2026-05-26
    """오캄 pass 결과. delete 필드 없음 (covenant).

    orphans = 디스크에서 사라진 경로의 노드 중 *동일 sha live twin 부재*인 것.
    auto-supersede 안 함 (machloket/Eilu va-Eilu: 의도적 보존 노드일 수 있음) — flag-only,
    사용자/Longinus 판단 대상. live twin 있는 disk-orphan은 candidates(이동=HIGH)로 간다.
    """

    candidates: tuple[SupersessionCandidate, ...] = ()
    scanned_nodes: int = 0
    groups_with_dups: int = 0
    notes: tuple[str, ...] = field(default_factory=tuple)
    orphans: tuple[NodeRecord, ...] = ()

    @property
    def superseded_count(self) -> int:
        return len(self.candidates)

    @property
    def orphan_count(self) -> int:
        return len(self.orphans)
