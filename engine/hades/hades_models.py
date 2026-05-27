"""하데스(Hades) 모델 — 실현(추상→구체↓) 결과 타입. 유레카의 dual.

# KG: hades-canonical-2026-05-27
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class RealizeStatus(str, Enum):
    PLANNED = "PLANNED"  # dry-run 계획만 (기본)
    REFUSED = "REFUSED"  # 가드 위반 (PROVISIONAL/REJECTED, >max_sites 등)
    APPLIED = "APPLIED"  # 실제 실현됨 (dry_run=False + apply)


@dataclass(frozen=True)
class MaterializationPlan:
    """추상→구체 실현 계획. operations + 역연산(undo) = reversibility-first."""

    concept: str
    kind: str  # 'kg' | 'code'
    operations: tuple[str, ...]  # 실현 연산 (cypher MERGE / refactor 기술)
    undo: tuple[str, ...]  # 역연산 (covenant: 모든 실현은 되돌릴 수 있어야)
    reversible: bool = True


@dataclass(frozen=True)
class RealizeVerdict:
    concept: str
    status: RealizeStatus
    plan: MaterializationPlan | None
    reason: str
    applied: bool = False


__all__ = ["MaterializationPlan", "RealizeStatus", "RealizeVerdict"]
