"""재배맨 planner — 순수 재귀 meta-planning (IO 없음).

사용자 정전: "계획에 대한 계획을 계획 자체를 ai가 연쇄적으로 짜서". 한 목표(Goal)를
하위 목표들로 *연쇄적으로* unfold → 계획 트리(PlanNode). 각 노드 = 씨앗 하나.

형식: anamorphism(unfold) over `μX.(CHUPiece + List X)`. 분해 규칙 `decompose`는 주입식
(KG 구조 기반 / 정적 spec / LLM 등) — planner는 트리 조립 + depth 불변식 강제만 책임진다
(occam이 "분류"만 하고 IO는 adapter가 하듯, 분해 *판단*은 주입, 구조 *보장*은 여기).

불변식 (SKILL.md v2.4 §p3, E4 DepthInvariantViolation):
  - depth ∈ [0, MAX_DEPTH]. depth>MAX_DEPTH → 하드 fail (fractal 무한 증식 차단).
  - 모든 노드 depth NOT NULL (정수).

# KG: jaebaeman-planfirst-essence-reframe-2026-05-27, lesson-jaebaeman-depth-invariant-2026-05-14,
#     lesson-prom64-jaebaeman-chu-agentfolder-2026-04-29 (initial algebra anamorphism)
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable, Iterator
from dataclasses import replace
from itertools import islice

from engine.jaebaeman.jaebaeman_models import (
    MAX_DEPTH,
    GerminationMethod,
    Goal,
    PlanNode,
    SeedRecord,
)

# decompose(node) → 그 노드를 분해한 하위 목표들. 빈 리스트 = 잎(더 이상 분해 안 함).
DecomposeFn = Callable[[PlanNode], "list[Goal]"]


class DepthInvariantViolation(ValueError):
    """depth가 [0, MAX_DEPTH]를 벗어남 (SKILL.md E4). fractal 무한 증식 차단."""


def _node_from_goal(goal: Goal, depth: int, method: GerminationMethod) -> PlanNode:
    return PlanNode(
        name=goal.name,
        objective=goal.objective,
        task_type=goal.task_type,
        target_domain=goal.target_domain,
        depth=depth,
        anchor=goal.anchor,
        germination_method=method,
    )


def plan(
    goal: Goal,
    decompose: DecomposeFn,
    *,
    max_depth: int = MAX_DEPTH,
    _depth: int = 0,
    _method: GerminationMethod = GerminationMethod.SINGLETON,
) -> PlanNode:
    """Goal을 계획 트리로 unfold. decompose가 하위 목표를 주면 재귀, 빈 리스트면 잎.

    max_depth에 닿으면 분해를 멈추고 잎으로 종료(하드 stop). _depth/_method는 내부 재귀용.
    """
    if _depth < 0 or _depth > max_depth:
        raise DepthInvariantViolation(
            f"depth={_depth} out of [0,{max_depth}] for '{goal.name}' "
            "— fractal 무한 증식 차단 (SKILL.md v2.4 E4)."
        )
    node = _node_from_goal(goal, _depth, _method)
    if _depth >= max_depth:
        return node  # 하드 stop: 더 깊이 분해하지 않는다 (잎으로 종료)
    subgoals = decompose(node)
    if not subgoals:
        return node  # 자연 잎 (분해 규칙이 더 쪼갤 게 없다고 판단)
    children = tuple(
        plan(
            sg,
            decompose,
            max_depth=max_depth,
            _depth=_depth + 1,
            _method=GerminationMethod.DECOMPOSE,
        )
        for sg in subgoals
    )
    return replace(node, children=children)


def plan_lazy(
    goal: Goal,
    decompose: DecomposeFn,
    *,
    fuel: int | None = None,
    max_depth: int = MAX_DEPTH,
) -> Iterator[PlanNode]:
    """ν(coinductive) 모드 — productive corecursive unfold. 소비한 만큼만 전개(lazy).

    eager ``plan()``이 트리 전체를 즉시 build하는 μ 모드라면, 이건 frontier를 BFS로 yield하며
    ``fuel``(최대 노드 수) 또는 ``max_depth``까지만 productive 전개. 각 yield 노드는 frontier라
    children=() (다음 노드는 다음 next()에서). PROM 64 D3 ν쌍, B4 권고(eager 유지·flag 분리).

    불변식: ``fuel`` 충분(≥ eager 노드 수) + 동일 ``max_depth``면 산출 노드 *집합* = walk(plan(...)).
    무한 decompose라도 fuel/observation budget이 productive 종료 보장(C3 안전가드).
    """
    queue: deque[tuple[Goal, int, GerminationMethod]] = deque(
        [(goal, 0, GerminationMethod.SINGLETON)]
    )
    produced = 0
    while queue:
        if fuel is not None and produced >= fuel:
            return
        g, depth, method = queue.popleft()
        if depth < 0 or depth > max_depth:
            raise DepthInvariantViolation(
                f"depth={depth} out of [0,{max_depth}] for '{g.name}' (lazy unfold)."
            )
        node = _node_from_goal(g, depth, method)  # frontier: children=()
        yield node
        produced += 1
        if depth < max_depth:
            for sg in decompose(node):
                queue.append((sg, depth + 1, GerminationMethod.DECOMPOSE))


def take_n(it: Iterator[PlanNode], n: int) -> tuple[PlanNode, ...]:
    """lazy generator의 유한 prefix n개만 관찰(observation budget). islice 래퍼."""
    return tuple(islice(it, n))


def plan_lazy_pairs(
    goal: Goal,
    decompose: DecomposeFn,
    *,
    fuel: int | None = None,
    max_depth: int = MAX_DEPTH,
) -> list[tuple[PlanNode, "PlanNode | None"]]:
    """lazy BFS unfold, (node, parent) 쌍을 fuel개까지. coinductive 심기용(parent=DECOMPOSES_TO).

    plan_lazy와 같은 ν 전개지만 parent 링크를 보존 → to_seeds_pairs로 씨앗화 가능.
    fuel=None이면 max_depth까지 전부(= eager plan()과 노드집합 동일).
    """
    queue: deque[tuple[Goal, int, GerminationMethod, PlanNode | None]] = deque(
        [(goal, 0, GerminationMethod.SINGLETON, None)]
    )
    out: list[tuple[PlanNode, PlanNode | None]] = []
    while queue:
        if fuel is not None and len(out) >= fuel:
            break
        g, depth, method, parent = queue.popleft()
        if depth < 0 or depth > max_depth:
            raise DepthInvariantViolation(
                f"depth={depth} out of [0,{max_depth}] for '{g.name}' (lazy pairs)."
            )
        node = _node_from_goal(g, depth, method)
        out.append((node, parent))
        if depth < max_depth:
            for sg in decompose(node):
                queue.append((sg, depth + 1, GerminationMethod.DECOMPOSE, node))
    return out


def walk(node: PlanNode):
    """계획 트리 pre-order 순회 — (node, parent) 튜플 yield. 루트의 parent=None."""

    def _rec(n: PlanNode, parent: PlanNode | None):
        yield n, parent
        for c in n.children:
            yield from _rec(c, n)

    yield from _rec(node, None)


def depth_max(node: PlanNode) -> int:
    return max(n.depth for n, _ in walk(node))


def leaf_count(node: PlanNode) -> int:
    return sum(1 for n, _ in walk(node) if n.is_leaf)


def seed_name(plan_node: PlanNode, skill: str) -> str:
    """씨앗의 결정론 PK. 트리 위치(name)로 안정 — 같은 계획 재실행 시 MERGE로 멱등."""
    return f"seed-{skill}-{plan_node.name}"


def to_seeds(root: PlanNode, skill: str, *, expected_outcome: str = "") -> list[SeedRecord]:
    """계획 트리를 평탄화 → SeedRecord 리스트 (materialize 입력).

    sourceId(FK) = anchor가 있으면 anchor, 없으면 자기 name(self-anchored root). 1:1 invariant는
    adapter/실 KG 측 trigger가 강제 — 여기선 트리 위치를 그대로 보존.
    """
    return to_seeds_pairs(list(walk(root)), skill, expected_outcome=expected_outcome)


def _seed_from_pair(
    n: PlanNode, parent: PlanNode | None, skill: str, expected_outcome: str
) -> SeedRecord:
    sname = seed_name(n, skill)
    return SeedRecord(
        name=sname,
        skill=skill,
        # 외부 anchor 있으면 그게 FK, 없으면 self-anchored → 자기 seed name(=guard가 HAS_SEED 생략)
        source_id=n.anchor or sname,
        display_name=n.objective[:120] or n.name,
        task_type=n.task_type,
        target_domain=n.target_domain,
        expected_outcome=expected_outcome or f"{n.task_type} artifact for {n.name}",
        germination_method=n.germination_method.value,
        depth=n.depth,
        parent=seed_name(parent, skill) if parent is not None else None,
    )


def to_seeds_pairs(
    pairs: list[tuple[PlanNode, "PlanNode | None"]], skill: str, *, expected_outcome: str = ""
) -> list[SeedRecord]:
    """(node, parent) 쌍 리스트 → SeedRecord 리스트. eager walk() / lazy plan_lazy_pairs 공용."""
    return [_seed_from_pair(n, p, skill, expected_outcome) for n, p in pairs]


def static_decompose(tree: dict[str, list[Goal]]) -> DecomposeFn:
    """정적 분해 규칙 — {parent_goal_name: [child Goal, ...]}. KG 없이 계획을 직접 줄 때.

    AI가 짠 연쇄 계획(메타-플랜)을 dict로 넘기면 그대로 트리화. 미지 name → 잎.
    """

    def decompose(node: PlanNode) -> list[Goal]:
        return list(tree.get(node.name, []))

    return decompose


__all__ = [
    "DecomposeFn",
    "DepthInvariantViolation",
    "depth_max",
    "leaf_count",
    "plan",
    "plan_lazy",
    "plan_lazy_pairs",
    "seed_name",
    "static_decompose",
    "take_n",
    "to_seeds",
    "to_seeds_pairs",
    "walk",
]
