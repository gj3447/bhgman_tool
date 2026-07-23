"""재배맨 = legion dispatch substrate — 정전 "재배맨(출격) = Legion.run 루프 자체" 배선.

unwired였던 새 재배맨 엔진(planner/lifecycle/telemetry)을 legion 실행 경로에 *꽂아* load-bearing으로
만든다 (그 전엔 CLI `jaebaeman`만 호출 = 실사용자 0). legion stage 실행(Contract-bound 순차)은
보존하고, 재배맨이 그 위 orchestration substrate로:
  (1) run을 seed plan으로 표현            — planner.plan / to_seeds
  (2) stage outcome → seed lifecycle 구동 — lifecycle.drive_seeds / SeedOutcome
  (3) 실행을 RunRecord 감사노드로 발행      — telemetry.RunRecord / record_to_kg

이로써 planner/lifecycle/telemetry가 `bhgman-tool legion` 경로에서 *실제로 실행*된다.
재배맨이 stage 실행을 *재구현*하지 않음(legion.run이 executor) — 재배맨은 plan·lifecycle·audit 층.
이 retrospective 한계는 ADR 수준으로 강등 기록 + 기계 oracle 고정됨 (jbm-s4 G5):
ADRs/legion-runtime-shape-review-2026-06-20.md §G5 Addendum (G5-C1~C4),
oracle = engine/legion/tests/test_dispatch_identity.py. 무음 승격 불가.

# KG: bihaenggiman-legioncommanders-2026-05-26 (재배맨=출격 substrate),
#     jaebaeman-planfirst-essence-reframe-2026-05-27, lesson-jaebaeman-engine-impl-prom16-2026-06-01,
#     adr-seven-commander-legion-architecture-2026-05-27
"""

from __future__ import annotations

from engine.jaebaeman.jaebaeman_models import Goal, SeedRecord, SeedStatus
from engine.jaebaeman.lifecycle import CypherRunner, LifecycleResult, SeedOutcome, drive_seeds
from engine.jaebaeman.planner import plan, static_decompose, to_seeds
from engine.jaebaeman.telemetry import RunRecord, record_to_kg
from engine.legion.commanders import build_default_legion, default_stages
from engine.legion.legion import GateFn, LegionRun

LEGION_GOAL = "legion-cycle"


def plan_legion_seeds() -> list[SeedRecord]:
    """6 commander verb를 재배맨 seed chain(CANONICAL_ORDER)으로 — planner를 legion에 load-bearing.

    루트 seed(legion-cycle) + 6 leaf seed(획득..실현), parent=DECOMPOSES_TO로 plan 구조 보존.
    """
    verbs = [s.verb for s in default_stages()]
    tree = {
        LEGION_GOAL: [Goal(name=f"legion::{v}", objective=v, task_type="commander") for v in verbs]
    }
    root = plan(
        Goal(name=LEGION_GOAL, objective="6 commander closed loop"),
        static_decompose(tree),
        max_depth=1,
    )
    return to_seeds(root, skill="legion")


def outcomes_to_seed_outcomes(seeds: list[SeedRecord], run: LegionRun) -> list[SeedOutcome]:
    """legion stage outcome(CANONICAL_ORDER 순) → seed lifecycle outcome. 루트는 cycle 집계."""
    stage_ocs = list(run.outcomes)
    leaf_seeds = [s for s in seeds if s.parent is not None]
    out: list[SeedOutcome] = []
    for i, s in enumerate(leaf_seeds):
        ok = i < len(stage_ocs) and stage_ocs[i].ok
        detail = stage_ocs[i].detail if i < len(stage_ocs) else "stage not reached (loop halted)"
        out.append(SeedOutcome(s.name, SeedStatus.COLLECTED if ok else SeedStatus.FAILED, detail))
    root = next((s for s in seeds if s.parent is None), None)
    if root is not None:
        status = SeedStatus.COLLECTED if run.completed else SeedStatus.FAILED
        out.insert(0, SeedOutcome(root.name, status, "legion cycle"))
    return out


def run_legion_via_jaebaeman(
    ctx: dict,
    *,
    run_id: str = "legion-run",
    write_cypher: CypherRunner | None = None,
    apply: bool = False,
    gate: GateFn | None = None,
) -> dict:
    """재배맨 substrate로 legion 1회 실행. legion.run이 executor, 재배맨이 plan·lifecycle·audit 층.

    반환: {legion_run, lifecycle, run_record, seeds}. apply=True + write_cypher면 RunRecord persist.

    ``gate``: per-stage oracle hard-stop(GateFn) — Legion.run 으로 관통시킨다(T0-3). 이전엔 이
    substrate 가 gate 를 삼켜 정방향 3진입점(CLI/bot/MCP)이 ADR 이 명시한 나생문 oracle gate 를
    영영 못 썼다. None(default)이면 legion 은 게이트 없이 실행 — 기존 동작 불변.
    """
    seeds = plan_legion_seeds()
    run = build_default_legion().run(context=ctx, gate=gate)
    lifecycle: LifecycleResult = drive_seeds(
        seeds,
        lambda _s: outcomes_to_seed_outcomes(seeds, run),
        write_cypher=write_cypher,
        apply=apply,
    )
    leaves = sum(1 for s in seeds if s.parent is not None)
    record = RunRecord(
        run_id=run_id,
        goal=LEGION_GOAL,
        planned_seeds=len(seeds),
        depth_max=1,
        leaf_count=leaves,
        dispatched=len(lifecycle.outcomes),
        collected=lifecycle.collected,
        failed=lifecycle.failed,
    )
    if apply and write_cypher is not None:
        record_to_kg(record, write_cypher)
    return {"legion_run": run, "lifecycle": lifecycle, "run_record": record, "seeds": seeds}


__all__ = [
    "LEGION_GOAL",
    "outcomes_to_seed_outcomes",
    "plan_legion_seeds",
    "run_legion_via_jaebaeman",
]
