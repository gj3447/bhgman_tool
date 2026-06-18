"""재배맨 value objects — 순수 dataclass (계획 트리 + 씨앗 + apply 결과).

occam/hades models와 동형: frozen dataclass, IO 없음, 내부 value만.

# KG: 재배맨-v2-subagent-runtime-protocol, jaebaeman-planfirst-essence-reframe-2026-05-27,
#     span-gap3-jaebaeman-seed-fk-2026-05-14 (9-field seed bundle)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

# SKILL.md v2.4 §p3: fractal 무한 증식 차단. depth ∈ [0, MAX_DEPTH].
MAX_DEPTH = 3


class SeedStatus(str, Enum):
    # KG: 재배맨-v2-subagent-runtime-protocol
    READY = "READY"  # 심긴 직후 (dispatch 대기)
    DISPATCHED = "DISPATCHED"
    COLLECTED = "COLLECTED"
    FAILED = "FAILED"


class GerminationMethod(str, Enum):
    # KG: 재배맨-v2-subagent-runtime-protocol
    SINGLETON = "singleton"  # 자식 없는 단일 목표
    DECOMPOSE = "decompose"  # 상위 계획에서 분해되어 발아
    MANUAL = "manual"


@dataclass(frozen=True)
class Goal:
    # KG: 재배맨-v2-subagent-runtime-protocol
    """계획의 입력 — 하나의 목표. anchor = 발아 원천 KG 노드(FK, 있으면)."""

    name: str
    objective: str
    task_type: str = "research"
    target_domain: str = ""
    anchor: str | None = None  # FK → :AtomicSpan/:Span/임의 KG 노드 name


@dataclass(frozen=True)
class PlanNode:
    # KG: 재배맨-v2-subagent-runtime-protocol
    """계획 트리 한 노드 = 씨앗 하나. children = 하위 계획(계획에 대한 계획).

    initial algebra `μX.(CHUPiece + List X)`의 한 layer: 잎(children=())이면 CHUPiece,
    가지면 List X. depth = 발아 세대(루트=0).
    """

    name: str
    objective: str
    task_type: str
    target_domain: str
    depth: int
    anchor: str | None
    germination_method: GerminationMethod
    children: tuple["PlanNode", ...] = ()

    @property
    def is_leaf(self) -> bool:
        return not self.children


@dataclass(frozen=True)
class SeedRecord:
    # KG: 재배맨-v2-subagent-runtime-protocol
    """materialize 대상 씨앗의 식별 정보 (PlanNode를 flatten한 한 줄)."""

    name: str
    skill: str
    source_id: str  # FK anchor (없으면 자기 자신 name = self-anchored root)
    display_name: str
    task_type: str
    target_domain: str
    expected_outcome: str
    germination_method: str
    depth: int
    parent: str | None = None  # 상위 PlanNode name (DECOMPOSES_TO 엣지 source)


class ViolationCode(str, Enum):
    # KG: 재배맨-v2-subagent-runtime-protocol
    """씨앗 불변식 위반 코드. E1/E3/E4 = SKILL.md v2.2/v2.4 error variants 거울."""

    E1_ORPHAN_ANCHOR = "E1_ORPHAN_ANCHOR"  # 외부 anchor(source_id)가 KG에 없음 (FK orphan)
    E3_MULTIPLE_SEED_PER_ANCHOR = (
        "E3_MULTIPLE_SEED_PER_ANCHOR"  # 한 anchor에 활성 씨앗 2+ (1:1 위반)
    )
    E4_DEPTH_RANGE = "E4_DEPTH_RANGE"  # depth ∉ [0, MAX_DEPTH] (NULL 포함)
    DUP_SEED_NAME = "DUP_SEED_NAME"  # 배치 내 씨앗 name 중복 (PK 충돌)
    DANGLING_PARENT = "DANGLING_PARENT"  # DECOMPOSES_TO parent가 배치에 없음 (트리 끊김)


@dataclass(frozen=True)
class SeedViolation:
    # KG: 재배맨-v2-subagent-runtime-protocol
    """불변식 위반 1건. fail-closed 게이트가 모아서 raise/report."""

    code: ViolationCode
    seed_id: str
    detail: str


@dataclass(frozen=True)
class SeedApplyResult:
    # KG: 재배맨-v2-subagent-runtime-protocol
    """씨앗 심기 결과. dry_run=True면 planned만, write 없음 (covenant: MERGE-only)."""

    seeded: tuple[str, ...] = ()
    planned_cyphers: tuple[tuple[str, dict], ...] = ()
    dry_run: bool = True
    applied_count: int = 0
    notes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class PlanResult:
    # KG: 재배맨-v2-subagent-runtime-protocol
    """재배맨 1회 실행 결과 — 계획 트리 + 평탄화된 씨앗 + apply 결과."""

    goal: str
    plan: PlanNode
    seeds: tuple[SeedRecord, ...]
    apply_result: SeedApplyResult
    depth_max: int = 0
    leaf_count: int = 0
    violations: tuple[SeedViolation, ...] = ()

    @property
    def summary(self) -> str:
        a = self.apply_result
        mode = "DRY-RUN (no write)" if a.dry_run else f"APPLIED {a.applied_count}"
        viol = f" BLOCKED({len(self.violations)} violation)" if self.violations else ""
        return (
            f"jaebaeman[{self.goal}]: planned_seeds={len(self.seeds)} "
            f"depth_max={self.depth_max} leaves={self.leaf_count} → {mode}{viol}"
        )


__all__ = [
    "MAX_DEPTH",
    "GerminationMethod",
    "Goal",
    "PlanNode",
    "PlanResult",
    "SeedApplyResult",
    "SeedRecord",
    "SeedStatus",
    "SeedViolation",
    "ViolationCode",
]
