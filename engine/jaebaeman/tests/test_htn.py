"""HTN method 계층 TDD (PROM 16 P2) — 다중 method + precondition + selection.

# KG: lesson-jaebaeman-engine-impl-prom16-2026-06-01 (C1), finding-jbm-eng-A1, finding-jbm-eng-A4
"""

from __future__ import annotations

from engine.jaebaeman.htn import (
    DecomposeMethod,
    applicable_methods,
    first_applicable,
    kg_method_decompose,
    method_decompose,
    min_cost,
    static_method,
)
from engine.jaebaeman.jaebaeman_models import Goal
from engine.jaebaeman.planner import plan, walk


def _names(tree):
    return [n.name for n, _ in walk(tree)]


# ── in-memory method registry ────────────────────────────────────────────────
def test_no_method_is_primitive_leaf():
    dec = method_decompose({})  # 빈 registry → 모든 task primitive
    tree = plan(Goal(name="g", objective="x"), dec)
    assert tree.is_leaf and _names(tree) == ["g"]


def test_single_method_decomposes():
    reg = {
        "g": [static_method("m", [Goal(name="a", objective="A"), Goal(name="b", objective="B")])]
    }
    tree = plan(Goal(name="g", objective="r"), method_decompose(reg))
    assert _names(tree) == ["g", "a", "b"]


def test_precondition_selects_applicable_method():
    # 두 method: 첫째 precondition False, 둘째 True → 둘째 선택 (first-applicable)
    reg = {
        "g": [
            static_method("deep", [Goal(name="x", objective="X")], precondition=lambda _n: False),
            static_method("shallow", [Goal(name="y", objective="Y")], precondition=lambda _n: True),
        ]
    }
    tree = plan(Goal(name="g", objective="r"), method_decompose(reg))
    assert _names(tree) == ["g", "y"]  # shallow method 선택


def test_no_applicable_method_is_leaf():
    reg = {
        "g": [static_method("m", [Goal(name="a", objective="A")], precondition=lambda _n: False)]
    }
    tree = plan(Goal(name="g", objective="r"), method_decompose(reg))
    assert tree.is_leaf  # 적용 가능 method 없음 → 잎


def test_precondition_uses_node_depth():
    # depth 기반 precondition — 같은 task라도 depth에 따라 다른 method
    reg = {
        "g": [
            static_method(
                "only-at-0",
                [Goal(name="g", objective="recur")],
                precondition=lambda n: n.depth == 0,
            )
        ]
    }
    # g가 자기를 재귀 분해하되 depth>0에선 precondition False → 잎. depth cap도 함께 작동.
    tree = plan(Goal(name="g", objective="r"), method_decompose(reg), max_depth=3)
    # depth0 g → method 적용 → child g(depth1), depth1 g → precondition False → 잎
    assert _names(tree) == ["g", "g"]


def test_first_applicable_returns_none_when_all_fail():
    methods = [static_method("m", [], precondition=lambda _n: False)]

    class _N:
        depth = 0

    assert first_applicable(_N(), methods) is None


def test_expand_fn_method_dynamic_subgoals():
    # method.expand가 node에 따라 동적으로 subgoal 생성 (정적 아님)
    m = DecomposeMethod(
        name="dyn",
        expand=lambda n: [Goal(name=f"{n.name}.child", objective="c")],
    )
    tree = plan(Goal(name="root", objective="r"), method_decompose({"root": [m]}))
    assert _names(tree) == ["root", "root.child"]


# ── KG-backed method registry ────────────────────────────────────────────────
def test_kg_method_decompose_picks_first_nonempty_by_ord():
    rows_by_task = {
        "g": [
            {"method": "m0", "ord": 0, "subgoals": []},  # ord 0 but empty → skip
            {"method": "m1", "ord": 1, "subgoals": [{"name": "a", "objective": "A"}]},
        ]
    }

    def run_cypher(cypher, params):
        if "-[:HAS_METHOD]->(m:DecomposeMethod)" in cypher:
            return rows_by_task.get(params["task"], [])
        return []

    tree = plan(Goal(name="g", objective="r", anchor="g"), kg_method_decompose(run_cypher))
    assert _names(tree) == ["g", "a"]


def test_kg_method_decompose_no_methods_is_leaf():
    tree = plan(Goal(name="g", objective="r", anchor="g"), kg_method_decompose(lambda _c, _p: []))
    assert tree.is_leaf


# ── 충돌 정렬 고도화 (min_cost selector) ──────────────────────────────────────
def test_min_cost_resolves_conflict():
    # 두 method 다 applicable(precondition None) → 충돌. min_cost가 cheap 선택 (등록순 아님)
    reg = {
        "g": [
            static_method("expensive", [Goal(name="x", objective="X")], cost=5.0),
            static_method("cheap", [Goal(name="y", objective="Y")], cost=1.0),
        ]
    }
    tree = plan(Goal(name="g", objective="r"), method_decompose(reg, selector=min_cost))
    assert _names(tree) == ["g", "y"]  # cheap(cost 1) 선택 — first_applicable였으면 x


def test_first_applicable_vs_min_cost_differ_on_order():
    reg = {
        "g": [
            static_method("expensive", [Goal(name="x", objective="X")], cost=5.0),
            static_method("cheap", [Goal(name="y", objective="Y")], cost=1.0),
        ]
    }
    fa = plan(Goal(name="g", objective="r"), method_decompose(reg, selector=first_applicable))
    mc = plan(Goal(name="g", objective="r"), method_decompose(reg, selector=min_cost))
    assert _names(fa) == ["g", "x"]  # 등록순 첫째
    assert _names(mc) == ["g", "y"]  # 최소 cost


def test_min_cost_tie_break_by_name():
    reg = {
        "g": [
            static_method("zeta", [Goal(name="z", objective="Z")], cost=2.0),
            static_method("alpha", [Goal(name="a", objective="A")], cost=2.0),
        ]
    }
    tree = plan(Goal(name="g", objective="r"), method_decompose(reg, selector=min_cost))
    assert _names(tree) == ["g", "a"]  # cost 동률 → name 사전순 'alpha'


def test_applicable_methods_counts_conflict():
    class _N:
        depth = 0

    methods = [
        static_method("m1", [], precondition=lambda _n: True),
        static_method("m2", [], precondition=lambda _n: False),
        static_method("m3", [], precondition=lambda _n: True),
    ]
    applicable = applicable_methods(_N(), methods)
    assert len(applicable) == 2  # m1, m3 applicable (m2 precondition False) → 충돌 2


def test_min_cost_respects_precondition():
    # 최저 cost지만 precondition False → 제외, 다음 applicable 선택
    reg = {
        "g": [
            static_method(
                "cheap-blocked",
                [Goal(name="x", objective="X")],
                cost=0.1,
                precondition=lambda _n: False,
            ),
            static_method("ok", [Goal(name="y", objective="Y")], cost=3.0),
        ]
    }
    tree = plan(Goal(name="g", objective="r"), method_decompose(reg, selector=min_cost))
    assert _names(tree) == ["g", "y"]  # cheap는 precondition fail → ok 선택
