"""변종-불변식 TDD — 성능 변종이 출력을 바꾸지 않는다 (Longinus test_parallel_invariant 거울).

성능 테스트는 단독으로 존재하면 안 된다: 빠른 경로(lazy ν / batch)가 느린 경로(eager μ)와
*같은 결과*를 낸다는 invariant와 짝이어야 "틀린 답을 빠르게" 최적화를 막는다.
(Longinus: parallel ≡ sequential byte-equal. 여기: eager μ ≡ lazy ν node-set + plant order-invariant.)

# KG: lesson-jaebaeman-engine-impl-prom16-2026-06-01 (C2 μ/ν 동치),
#     finding-jbm-eng-B4 (eager 유지·lazy flag 분리)
"""

from __future__ import annotations

import pytest

from engine.jaebaeman.jaebaeman_models import Goal
from engine.jaebaeman.kg_adapter import plant_seeds
from engine.jaebaeman.planner import (
    DepthInvariantViolation,
    plan,
    plan_lazy,
    static_decompose,
    take_n,
    to_seeds,
    walk,
)


def _identity(node) -> tuple:
    """비교용 노드 신원 (children 링크 제외 — eager는 nested, lazy는 frontier)."""
    return (
        node.name,
        node.depth,
        node.germination_method,
        node.anchor,
        node.objective,
        node.task_type,
        node.target_domain,
    )


def _branching_tree(branching: int, depth: int) -> dict[str, list[Goal]]:
    """b-ary 합성 분해 규칙 dict (root 'g' 아래 깊이 depth까지 b children)."""
    tree: dict[str, list[Goal]] = {}

    def expand(name: str, d: int) -> None:
        if d >= depth:
            return
        children = [Goal(name=f"{name}.{i}", objective=f"obj {name}.{i}") for i in range(branching)]
        tree[name] = children
        for c in children:
            expand(c.name, d + 1)

    expand("g", 0)
    return tree


# ── eager μ ≡ lazy ν : 산출 노드 집합 동일 ────────────────────────────────────
class TestEagerLazyEquiv:
    def test_singleton(self):
        g = Goal(name="g", objective="solo")
        eager = {_identity(n) for n, _ in walk(plan(g, lambda _n: []))}
        lazy = {_identity(n) for n in plan_lazy(g, lambda _n: [])}
        assert eager == lazy

    @pytest.mark.parametrize("branching,depth", [(2, 3), (3, 3), (4, 2)])
    def test_branching_node_set_equal(self, branching, depth):
        tree = _branching_tree(branching, depth)
        dec = static_decompose(tree)
        g = Goal(name="g", objective="root")
        eager = {_identity(n) for n, _ in walk(plan(g, dec, max_depth=depth))}
        lazy = {_identity(n) for n in plan_lazy(g, dec, max_depth=depth)}
        assert eager == lazy
        assert len(eager) == len(lazy)  # 중복 없음

    def test_natural_leaf_stops_both(self):
        # 'g.0'에서 분해 중단 → 양쪽 다 거기서 잎
        tree = {"g": [Goal(name="g.0", objective="a"), Goal(name="g.1", objective="b")]}
        dec = static_decompose(tree)
        g = Goal(name="g", objective="r")
        eager = {_identity(n) for n, _ in walk(plan(g, dec))}
        lazy = {_identity(n) for n in plan_lazy(g, dec)}
        assert eager == lazy


# ── lazy productivity / fuel / depth ─────────────────────────────────────────
class TestLazyProductivity:
    def test_fuel_caps_production(self):
        # 무한 분해 규칙이어도 fuel이 productive 종료
        def always_two(node):
            return [
                Goal(name=node.name + ".0", objective="x"),
                Goal(name=node.name + ".1", objective="y"),
            ]

        produced = take_n(plan_lazy(Goal(name="g", objective="g"), always_two, max_depth=99), 5)
        assert len(produced) == 5  # 무한 트리에서 정확히 5개만 (productive)

    def test_take_n_is_prefix(self):
        tree = _branching_tree(2, 3)
        g = Goal(name="g", objective="r")
        first3 = take_n(plan_lazy(g, static_decompose(tree)), 3)
        first5 = take_n(plan_lazy(g, static_decompose(tree)), 5)
        assert [_identity(n) for n in first3] == [_identity(n) for n in first5[:3]]

    def test_lazy_depth_violation_raises(self):
        gen = plan_lazy(Goal(name="g", objective="g"), lambda _n: [], max_depth=-1)
        with pytest.raises(DepthInvariantViolation):
            next(gen)


# ── plant materialization : seed 순서 무관 (order-invariant) ──────────────────
class TestPlantOrderInvariant:
    def test_planned_cypher_set_independent_of_seed_order(self):
        tree = _branching_tree(3, 2)
        seeds = to_seeds(
            plan(Goal(name="g", objective="r"), static_decompose(tree), max_depth=2), "jaebaeman"
        )

        def plan_set(ss):
            res = plant_seeds(ss, dry_run=True)
            # (cypher, sorted params items) 멀티셋 — 순서 무관 비교
            return sorted((c, tuple(sorted(p.items()))) for c, p in res.planned_cyphers)

        forward = plan_set(seeds)
        reverse = plan_set(list(reversed(seeds)))
        assert forward == reverse  # 같은 KG 상태로 수렴 (materialization 순서 독립)


# ── coinductive 모드 (P3 병존) : fuel-bounded 심기 ────────────────────────────
class TestCoinductiveRunner:
    def test_fuel_bounds_seed_count(self):
        from engine.jaebaeman.jaebaeman_runner import run_jaebaeman

        tree = _branching_tree(3, 3)  # 큰 트리
        res = run_jaebaeman(
            Goal(name="g", objective="r"),
            decompose=static_decompose(tree),
            coinductive=True,
            fuel=5,
        )
        assert len(res.seeds) == 5  # fuel 정확히 5개만 심음 (productive)

    def test_coinductive_full_equals_eager_seedset(self):
        from engine.jaebaeman.jaebaeman_runner import run_jaebaeman

        tree = _branching_tree(2, 3)
        dec = static_decompose(tree)
        eager = run_jaebaeman(Goal(name="g", objective="r"), decompose=dec, max_depth=3)
        lazy = run_jaebaeman(
            Goal(name="g", objective="r"), decompose=dec, coinductive=True, fuel=None, max_depth=3
        )
        assert {s.name for s in eager.seeds} == {s.name for s in lazy.seeds}  # fuel=None ≡ eager

    def test_coinductive_preserves_decomposes_to_parent(self):
        from engine.jaebaeman.jaebaeman_runner import run_jaebaeman

        tree = {"g": [Goal(name="a", objective="A")], "a": [Goal(name="b", objective="B")]}
        res = run_jaebaeman(
            Goal(name="g", objective="r"), decompose=static_decompose(tree), coinductive=True
        )
        by_name = {s.name: s for s in res.seeds}
        # parent 링크(DECOMPOSES_TO) 보존: a→g, b→a
        assert by_name["seed-jaebaeman-a"].parent == "seed-jaebaeman-g"
        assert by_name["seed-jaebaeman-b"].parent == "seed-jaebaeman-a"
