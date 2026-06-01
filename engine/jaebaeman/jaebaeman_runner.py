"""재배맨 end-to-end runner — plan(unfold) → to_seeds(flatten) → plant_seeds(MERGE).

orchestration만. 재귀 분해 = planner.py, IO = kg_adapter. dry-run 기본(occam/hades 대칭).

decompose 규칙은 두 경로:
  - anchor 주어지고 KG 연결 있으면 → kg_decompose (KG 구조에서 하위 계획 읽어 연쇄 unfold).
  - 아니면 → 단일 루트 씨앗 (self-anchored, depth 0). 정적 계획은 plan()에 직접 static_decompose 주입.

# KG: jaebaeman-planfirst-essence-reframe-2026-05-27, 재배맨-v2-subagent-runtime-protocol,
#     project-legion-unification-kg-engine-2026-06-01
"""

from __future__ import annotations

from engine.jaebaeman.jaebaeman_models import MAX_DEPTH, Goal, PlanResult
from engine.jaebaeman.kg_adapter import CypherRunner, kg_decompose, plant_seeds
from engine.jaebaeman.planner import (
    DecomposeFn,
    depth_max,
    leaf_count,
    plan,
    to_seeds,
)


def _singleton_decompose(_node) -> list[Goal]:
    """분해 안 함 — 루트 1개 씨앗만 (KG 구조 없거나 anchor 없을 때)."""
    return []


def run_jaebaeman(
    goal: Goal,
    run_cypher: CypherRunner | None = None,
    write_cypher: CypherRunner | None = None,
    *,
    skill: str = "jaebaeman",
    cycle_id: str = "jaebaeman-cli",
    apply: bool = False,
    max_depth: int = MAX_DEPTH,
    decompose: DecomposeFn | None = None,
    expected_outcome: str = "",
) -> PlanResult:
    """목표를 계획 트리로 unfold하고 씨앗으로 심는다. apply=False(기본) → planned만, write 없음.

    decompose 명시 주입(static_decompose 등) > anchor+run_cypher 기반 kg_decompose > singleton.
    """
    if decompose is None:
        if goal.anchor is not None and run_cypher is not None:
            decompose = kg_decompose(run_cypher)
        else:
            decompose = _singleton_decompose

    tree = plan(goal, decompose, max_depth=max_depth)
    seeds = to_seeds(tree, skill, expected_outcome=expected_outcome)
    apply_result = plant_seeds(
        seeds, write_cypher=write_cypher, cycle_id=cycle_id, dry_run=not apply
    )
    return PlanResult(
        goal=goal.name,
        plan=tree,
        seeds=tuple(seeds),
        apply_result=apply_result,
        depth_max=depth_max(tree),
        leaf_count=leaf_count(tree),
    )


__all__ = ["run_jaebaeman"]
