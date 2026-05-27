"""오캄 value objects — 순수 dataclass (외부 검증 아님, 내부 value).

# KG: occam-kam-canonical-2026-05-26, occam-pass-bhgman_tool-2026-05-27
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Confidence(str, Enum):
    HIGH = "HIGH"  # disk sha가 현재 lineage를 확정
    MEDIUM = "MEDIUM"  # disk 진실 부재, line_count 휴리스틱으로 추정


@dataclass(frozen=True)
class NodeRecord:
    """KG SourceCodeNode 한 개의 식별 정보."""

    name: str
    source_path: str
    sha256: str
    line_count: int


@dataclass(frozen=True)
class SupersessionCandidate:
    """대체된 낡은 노드 → 현재 노드. covenant: supersede(archive)지 delete 아님."""

    stale: NodeRecord
    current: NodeRecord
    normalized_path: str
    reason: str
    confidence: Confidence
    action: str = "SUPERSEDED_BY"  # 고정 — 오캄은 archive만, delete 표현 부재


@dataclass(frozen=True)
class OccamReport:
    """오캄 pass 결과. delete 필드 없음 (covenant)."""

    candidates: tuple[SupersessionCandidate, ...] = ()
    scanned_nodes: int = 0
    groups_with_dups: int = 0
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def superseded_count(self) -> int:
        return len(self.candidates)
