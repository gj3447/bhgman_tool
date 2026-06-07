"""재배맨 end-to-end runner — plan(unfold) → to_seeds(flatten) → plant_seeds(MERGE).

orchestration만. 재귀 분해 = planner.py, IO = kg_adapter. dry-run 기본(occam/hades 대칭).

decompose 규칙은 두 경로:
  - anchor 주어지고 KG 연결 있으면 → kg_decompose (KG 구조에서 하위 계획 읽어 연쇄 unfold).
  - 아니면 → 단일 루트 씨앗 (self-anchored, depth 0). 정적 계획은 plan()에 직접 static_decompose 주입.

# KG: jaebaeman-planfirst-essence-reframe-2026-05-27, 재배맨-v2-subagent-runtime-protocol,
#     project-legion-unification-kg-engine-2026-06-01
"""

from __future__ import annotations

from engine.jaebaeman.invariants import validate_seed_invariants
from engine.jaebaeman.jaebaeman_models import MAX_DEPTH, Goal, PlanResult, SeedApplyResult
from engine.jaebaeman.kg_adapter import CypherRunner, kg_decompose, plant_seeds, read_ready_seeds
from engine.jaebaeman.lifecycle import Dispatcher, LifecycleResult, drive_seeds
from engine.jaebaeman.planner import (
    DecomposeFn,
    depth_max,
    leaf_count,
    plan,
    plan_lazy_pairs,
    to_seeds,
    to_seeds_pairs,
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
    validate: bool = True,
    coinductive: bool = False,
    fuel: int | None = None,
) -> PlanResult:
    """목표를 계획 트리로 unfold하고 씨앗으로 심는다. apply=False(기본) → planned만, write 없음.

    decompose 명시 주입(static_decompose 등) > anchor+run_cypher 기반 kg_decompose > singleton.
    validate=True(기본): plant 전 불변식 게이트(P1). 위반 + apply 시 *fail-closed* — write 차단.
    coinductive=True: ν 모드 — eager 트리 빌드 대신 lazy BFS unfold를 fuel개 노드까지만 심는다
    (P3 병존, depth cap도 함께 작동). fuel=None이면 max_depth까지 전부(=eager 노드집합).
    """
    if decompose is None:
        if goal.anchor is not None and run_cypher is not None:
            decompose = kg_decompose(run_cypher)
        else:
            decompose = _singleton_decompose

    if coinductive:
        pairs = plan_lazy_pairs(goal, decompose, fuel=fuel, max_depth=max_depth)
        seeds = to_seeds_pairs(pairs, skill, expected_outcome=expected_outcome)
        tree = pairs[0][0] if pairs else plan(goal, _singleton_decompose, max_depth=0)
        has_child = {id(p) for _, p in pairs if p is not None}
        depth_max_v = max((n.depth for n, _ in pairs), default=0)
        leaf_count_v = sum(1 for n, _ in pairs if id(n) not in has_child)
    else:
        tree = plan(goal, decompose, max_depth=max_depth)
        seeds = to_seeds(tree, skill, expected_outcome=expected_outcome)
        depth_max_v = depth_max(tree)
        leaf_count_v = leaf_count(tree)

    violations = (
        validate_seed_invariants(seeds, run_cypher=run_cypher, max_depth=max_depth)
        if validate
        else []
    )
    # fail-closed: 위반 있으면 apply여도 write 금지 (dry-run으로 강등, 위반 surface)
    blocked = bool(violations)
    if blocked:
        apply_result = SeedApplyResult(
            seeded=tuple(s.name for s in seeds),
            planned_cyphers=(),
            dry_run=True,
            applied_count=0,
            notes=(
                f"BLOCKED by {len(violations)} invariant violation(s) — write 차단 (fail-closed)",
            ),
        )
    else:
        apply_result = plant_seeds(
            seeds, write_cypher=write_cypher, cycle_id=cycle_id, dry_run=not apply
        )
    return PlanResult(
        goal=goal.name,
        plan=tree,
        seeds=tuple(seeds),
        apply_result=apply_result,
        depth_max=depth_max_v,
        leaf_count=leaf_count_v,
        violations=tuple(violations),
    )


def germinate_ready_seeds(
    dispatcher: Dispatcher,
    run_cypher: CypherRunner,
    *,
    cycle_id: str,
    write_cypher: CypherRunner | None = None,
    apply: bool = False,
    limit: int | None = None,
) -> LifecycleResult:
    """씨앗→발아→동작 핸드오프: KG의 READY 씨앗을 read-back → dispatcher 출격 → status write.

    run_jaebaeman(plan→plant, Phase 0~1)의 다음 단계(Phase 2~4). plant_seeds로 심긴 READY
    :SubagentTaskSpec를 read_ready_seeds로 다시 읽어(발아 입력) drive_seeds로 출격·수확·status 전이.
    dispatcher 주입: agent_dispatcher(client)=실 LLM 출격(동작) / fake=테스트.

    **cycle_id 필수** — 전역 READY 씨앗(KG 누적분) 무차별 dispatch 방지. 보통 직전 plant의 cycle_id.
    **apply가 dispatch+write 둘 다의 게이트**: apply=False면 dispatcher를 *호출하지 않고*(LLM 비용 0)
    READY 씨앗 수만 보고하는 진짜 dry-run. apply=True에서만 실제 출격(LLM)+status write.

    이전엔 READY 씨앗을 다시 읽어 dispatch하는 코드가 부재해 씨앗(KG)이 dispatch의 dead-end였다
    (감사 finding-jaebaeman-seed-dispatch-handoff-unwired-2026-06-07). 이 함수가 그 한 가닥을 잇는다.
    """
    seeds = read_ready_seeds(run_cypher, limit=limit, cycle_id=cycle_id)
    if not apply:
        return LifecycleResult(
            outcomes=(),
            dry_run=True,
            notes=(
                f"dry-run: cycle '{cycle_id}'에 발아 대기 READY 씨앗 {len(seeds)}개 "
                "(--apply로 출격+status write; dispatch 미실행 = LLM 비용 0)",
            ),
        )
    return drive_seeds(seeds, dispatcher, write_cypher=write_cypher, apply=True)


__all__ = ["germinate_ready_seeds", "run_jaebaeman"]
