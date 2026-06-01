"""재배맨 HTN method 계층 (PROM 16 P2) — 한 task에 다중 method + precondition + selection.

현재 단일 `decompose_fn`은 한 goal을 *한 가지* 방법으로만 분해한다. HTN(GTPyhop/SHOP3)의
핵심은 *한 compound task를 여러 method로 분해 가능*하고, 각 method가 precondition으로 guard되며,
selector가 적용 가능한 method를 고른다는 것. 이 모듈이 그 method 계층을 `DecomposeFn`으로
*생산*한다 — `planner.plan()`은 그대로 그 DecomposeFn을 소비(blast radius 0).

semantics:
  - method 없는 task = primitive(잎). 적용 가능한 method 없는 compound도 잎(gap, log 가능).
  - method.expand(node) -> 하위 Goal 리스트 (GTPyhop @task method body).
  - method.precondition(node) -> bool (None = 항상 적용). SHOP3 precondition axiom.
  - selector(node, methods) -> 고른 method | None (default first-applicable).

# KG: lesson-jaebaeman-engine-impl-prom16-2026-06-01 (C1 method registry),
#     finding-jbm-eng-A1 (GTPyhop/SHOP3), finding-jbm-eng-A4 (CompoundTask/Method/precondition)
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from engine.jaebaeman.jaebaeman_models import Goal, PlanNode
from engine.jaebaeman.planner import DecomposeFn

# method body: node → 하위 Goal 리스트. precondition: node → 적용 가능?
ExpandFn = Callable[[PlanNode], "list[Goal]"]
PreconditionFn = Callable[[PlanNode], bool]
CypherRunner = Callable[[str, dict], "list[dict]"]


@dataclass(frozen=True)
class DecomposeMethod:
    """한 compound task를 분해하는 한 가지 방법. precondition으로 guard (GTPyhop method)."""

    name: str
    expand: ExpandFn
    precondition: PreconditionFn | None = None  # None = 항상 적용

    def applicable(self, node: PlanNode) -> bool:
        return self.precondition is None or self.precondition(node)


# task key(default=name) → 적용 순서대로 정렬된 method 리스트.
MethodRegistry = dict[str, "list[DecomposeMethod]"]
MethodSelector = Callable[[PlanNode, "list[DecomposeMethod]"], "DecomposeMethod | None"]
KeyOf = Callable[[PlanNode], str]


def first_applicable(node: PlanNode, methods: list[DecomposeMethod]) -> DecomposeMethod | None:
    """precondition 통과하는 첫 method (등록 순서 = 우선순위). HTN 기본 selection."""
    return next((m for m in methods if m.applicable(node)), None)


def static_method(
    name: str, subgoals: list[Goal], precondition: PreconditionFn | None = None
) -> DecomposeMethod:
    """정적 subgoal 리스트를 method로 — expand가 항상 같은 subgoals 반환 (간편 생성자)."""
    frozen = tuple(subgoals)
    return DecomposeMethod(name=name, expand=lambda _n: list(frozen), precondition=precondition)


def method_decompose(
    registry: MethodRegistry,
    *,
    key_of: KeyOf | None = None,
    selector: MethodSelector = first_applicable,
) -> DecomposeFn:
    """method registry로부터 DecomposeFn 생산. method 없으면/적용 불가면 잎([]).

    key_of: task 식별 (default node.name). type 기반 reuse 시 task_type 등으로 교체.
    """
    key = key_of or (lambda n: n.name)

    def decompose(node: PlanNode) -> list[Goal]:
        methods = registry.get(key(node), [])
        if not methods:
            return []  # primitive / 미등록 → 잎
        chosen = selector(node, methods)
        return chosen.expand(node) if chosen is not None else []

    return decompose


# ── KG-backed method registry (HAS_METHOD → DECOMPOSES_TO) ───────────────────
_FETCH_METHODS = (
    "MATCH (t {name: $task})-[:HAS_METHOD]->(m:DecomposeMethod) "
    "OPTIONAL MATCH (m)-[:DECOMPOSES_TO]->(sub) "
    "WITH m, coalesce(m.ord, 0) AS ord, "
    "collect({name: sub.name, objective: coalesce(sub.objective, sub.name)}) AS subgoals "
    "RETURN m.name AS method, ord, subgoals ORDER BY ord"
)


def methods_cypher(task: str) -> tuple[str, dict]:
    return _FETCH_METHODS, {"task": task}


def kg_method_decompose(run_cypher: CypherRunner, *, task_type: str = "research") -> DecomposeFn:
    """KG HAS_METHOD/DECOMPOSES_TO에서 method 로드 → ord 순 첫 non-empty method 선택.

    precondition은 KG 측 ord(우선순위)로 단순화 (rich precondition은 in-memory method_decompose).
    anchor 우선 task 키, 없으면 node.name. kg_decompose의 method-aware 버전.
    """

    def decompose(node: PlanNode) -> list[Goal]:
        task = node.anchor or node.name
        rows = run_cypher(*methods_cypher(task))
        for r in rows:
            subs = [s for s in (r.get("subgoals") or []) if s and s.get("name")]
            if subs:
                return [
                    Goal(
                        name=s["name"],
                        objective=s.get("objective") or s["name"],
                        task_type=task_type,
                        anchor=s["name"],
                    )
                    for s in subs
                ]
        return []

    return decompose


__all__ = [
    "CypherRunner",
    "DecomposeMethod",
    "ExpandFn",
    "MethodRegistry",
    "MethodSelector",
    "PreconditionFn",
    "first_applicable",
    "kg_method_decompose",
    "method_decompose",
    "methods_cypher",
    "static_method",
]
