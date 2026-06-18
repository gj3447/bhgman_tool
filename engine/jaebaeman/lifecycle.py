"""재배맨 씨앗 lifecycle 구동 (공학적 완성) — 심긴 READY 씨앗을 DISPATCHED→COLLECTED로.

지금까지 엔진은 씨앗을 READY로 *심기*만 했다 (kg_adapter). SeedStatus enum + Lean lifecycle
(SeedLifecycle.lean Step)은 *모델*만 했고 *구동*은 없었다 — 4-phase SOP(Seed→Dispatch→Collect→
Write)의 Phase 2~4가 끊겨 있었다. 이 모듈이 그 빚을 갚는다: planted 씨앗 → dispatcher 출격 →
결과 수확 → status 전이 write.

설계:
  - dispatcher 주입 (Dispatcher = list[SeedRecord] → list[SeedOutcome]). fake로 테스트 / 실=ThreadPool.
  - **병렬은 여기 산다**: agent_dispatcher가 engine.agents.dispatch.dispatch_parallel(ThreadPoolExecutor)
    로 N 씨앗 동시 출격 (결정론 계획 코어는 sequential이 맞고, IO-bound dispatch만 병렬 — 측정 근거).
  - covenant: status는 SET만 (READY→DISPATCHED→COLLECTED/FAILED). DELETE/DETACH/REMOVE 부재 assert.
  - dry-run 기본: write_cypher 있어도 apply=False면 status write 안 함.

Lean 정전 (SeedLifecycle.lean Step): ready→dispatched→collected (archive) / dispatched→failed.
실패 격리: 한 씨앗 FAILED가 나머지 COLLECTED를 막지 않음 (dispatch_parallel과 동일).

# KG: lesson-jaebaeman-engine-impl-prom16-2026-06-01, 재배맨-v2-subagent-runtime-protocol (4-phase SOP),
#     jaebaeman-planfirst-essence-reframe-2026-05-27 (dispatch = plan-first의 instantiation)
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from engine.jaebaeman.jaebaeman_models import SeedRecord, SeedStatus

CypherRunner = Callable[[str, dict], "list[dict]"]
FORBIDDEN_TOKENS = ("DELETE", "DETACH", "REMOVE")


@dataclass(frozen=True)
class SeedOutcome:
    # KG: 재배맨-v2-subagent-runtime-protocol
    """한 씨앗의 dispatch 결과 + terminal status (COLLECTED | FAILED)."""

    seed_name: str
    status: SeedStatus
    detail: str = ""


# dispatcher: 씨앗 배치 → outcome 배치 (READY→DISPATCHED→terminal을 내부 수행, 병렬 가능).
Dispatcher = Callable[["list[SeedRecord]"], "list[SeedOutcome]"]


@dataclass(frozen=True)
class LifecycleResult:
    # KG: 재배맨-v2-subagent-runtime-protocol
    outcomes: tuple[SeedOutcome, ...] = ()
    planned_status_writes: tuple[tuple[str, dict], ...] = ()
    dry_run: bool = True
    applied_count: int = 0
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def collected(self) -> int:
        return sum(1 for o in self.outcomes if o.status is SeedStatus.COLLECTED)

    @property
    def failed(self) -> int:
        return sum(1 for o in self.outcomes if o.status is SeedStatus.FAILED)

    @property
    def summary(self) -> str:
        mode = "DRY-RUN (no write)" if self.dry_run else f"APPLIED {self.applied_count}"
        return (
            f"jaebaeman-lifecycle: dispatched={len(self.outcomes)} "
            f"collected={self.collected} failed={self.failed} → {mode}"
        )


# status 전이 write (covenant: SET만). READY→DISPATCHED→COLLECTED/FAILED.
# NOTE: 씨앗 lifecycle 종결값은 'COLLECTED'(Lean SeedLifecycle 정전). KG 전역 done-status인
# 'COMPLETED'와 다르므로 t_dep_unlock 트리거(IN-list=COMPLETED)는 COLLECTED 씨앗의 BLOCKED
# 의존자를 자동 unlock하지 않는다 — 의도된 분리. 의존 unlock 필요 시 별도 매핑(범위 밖).
_STATUS_SET = (
    "MATCH (s:SubagentTaskSpec {name: $name}) "
    "SET s.status = $status, s.lifecycleUpdatedAt = datetime() "
    "RETURN s.name AS updated"
)


def _assert_covenant(cypher: str) -> None:
    up = cypher.upper()
    violations = [t for t in FORBIDDEN_TOKENS if t in up]
    if violations:
        raise AssertionError(f"lifecycle covenant violation: {violations} in status cypher")


def build_status_write(outcome: SeedOutcome) -> tuple[str, dict]:
    # KG: 재배맨-v2-subagent-runtime-protocol
    """씨앗 status 전이 cypher + params. covenant: 파괴 토큰 부재 assert."""
    _assert_covenant(_STATUS_SET)
    return _STATUS_SET, {"name": outcome.seed_name, "status": outcome.status.value}


def drive_seeds(
    seeds: list[SeedRecord],
    dispatcher: Dispatcher,
    *,
    write_cypher: CypherRunner | None = None,
    apply: bool = False,
) -> LifecycleResult:
    # KG: 재배맨-v2-subagent-runtime-protocol
    """READY 씨앗을 dispatcher로 출격→수확하고 terminal status를 KG에 write. dry-run 기본.

    dispatcher가 Phase 2(dispatch)+3(collect)를 수행(병렬 가능), 이 함수가 Phase 4(status write).
    apply=False면 status write 안 함 (planned만). 실패 격리는 dispatcher 책임.
    """
    outcomes = list(dispatcher(list(seeds)))
    plans = [build_status_write(o) for o in outcomes]
    if not apply or write_cypher is None:
        return LifecycleResult(
            outcomes=tuple(outcomes),
            planned_status_writes=tuple(plans),
            dry_run=True,
            notes=("dry-run: status 전이 planned only (covenant SET, no write)",),
        )
    for cypher, params in plans:
        write_cypher(cypher, params)
    return LifecycleResult(
        outcomes=tuple(outcomes),
        planned_status_writes=tuple(plans),
        dry_run=False,
        applied_count=len(plans),
        notes=(f"applied {len(plans)} status transition(s)",),
    )


def agent_dispatcher(
    client,
    *,
    model: str = "claude-haiku-4-5-20251001",
    max_workers: int = 8,
    system: str = "너는 계획 실행기다. 주어진 작업을 간결히 수행하고 결과를 보고하라.",
) -> Dispatcher:
    # KG: 재배맨-v2-subagent-runtime-protocol
    """실 dispatcher — engine.agents.dispatch.dispatch_parallel(ThreadPoolExecutor) 래핑.

    **병렬 출격**: N 씨앗을 동시에 (IO-bound LLM 호출 겹치기). web off = 공정 예산.
    runtime 불가/실패는 dispatch_parallel이 SeedOutcome.FAILED로 격리.
    """
    from engine.agents.dispatch import SubagentSpec, dispatch_parallel  # noqa: PLC0415

    def dispatch(seeds: list[SeedRecord]) -> list[SeedOutcome]:
        specs = [
            SubagentSpec(
                name=s.name,
                system=system,
                user=f"{s.display_name}\n기대 산출: {s.expected_outcome}",
                model=model,
                web_search=False,
            )
            for s in seeds
        ]
        results = dispatch_parallel(specs, client, max_workers=max_workers)
        return [
            SeedOutcome(
                seed_name=r.name,
                status=SeedStatus.COLLECTED if r.ok else SeedStatus.FAILED,
                detail=(r.text[:200] if r.ok else r.error),
            )
            for r in results
        ]

    return dispatch


__all__ = [
    "CypherRunner",
    "Dispatcher",
    "FORBIDDEN_TOKENS",
    "LifecycleResult",
    "SeedOutcome",
    "agent_dispatcher",
    "build_status_write",
    "drive_seeds",
]
