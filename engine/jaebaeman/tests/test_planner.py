"""재배맨 planner TDD — 순수 재귀 unfold + depth 불변식.

# KG: jaebaeman-planfirst-essence-reframe-2026-05-27, lesson-jaebaeman-depth-invariant-2026-05-14
"""

from __future__ import annotations

import pytest

from engine.jaebaeman.jaebaeman_models import GerminationMethod, Goal
from engine.jaebaeman.planner import (
    DepthInvariantViolation,
    depth_max,
    leaf_count,
    plan,
    static_decompose,
    to_seeds,
    walk,
)


def _no_decompose(_node):
    return []


def test_singleton_goal_is_single_leaf_root():
    root = plan(Goal(name="g", objective="solve g"), _no_decompose)
    assert root.depth == 0
    assert root.is_leaf
    assert root.germination_method is GerminationMethod.SINGLETON
    assert depth_max(root) == 0
    assert leaf_count(root) == 1


def test_recursive_decompose_builds_tree():
    tree = {
        "root": [Goal(name="a", objective="A"), Goal(name="b", objective="B")],
        "a": [Goal(name="a1", objective="A1")],
    }
    root = plan(Goal(name="root", objective="R"), static_decompose(tree))
    names = [n.name for n, _ in walk(root)]
    assert names == ["root", "a", "a1", "b"]  # pre-order
    assert depth_max(root) == 2
    assert leaf_count(root) == 2  # a1, b
    # 분해되어 발아한 자식은 germination=decompose
    a = root.children[0]
    assert a.germination_method is GerminationMethod.DECOMPOSE


def test_depth_hard_stop_at_max_depth():
    # 무한 분해 규칙: 모든 노드가 자식 1개를 또 낳음
    def always_one(node):
        return [Goal(name=node.name + ".c", objective="deeper")]

    root = plan(Goal(name="g", objective="g"), always_one, max_depth=2)
    # depth 0,1,2 까지만 — depth 2가 잎 (하드 stop, 더 안 쪼갬)
    assert depth_max(root) == 2
    leaf = [n for n, _ in walk(root) if n.is_leaf]
    assert len(leaf) == 1 and leaf[0].depth == 2


def test_negative_depth_raises():
    with pytest.raises(DepthInvariantViolation):
        plan(Goal(name="g", objective="g"), _no_decompose, _depth=-1)


def test_to_seeds_flattens_with_fk_and_parent_edges():
    tree = {"root": [Goal(name="a", objective="A", anchor="span-a")]}
    root = plan(Goal(name="root", objective="R", anchor="span-root"), static_decompose(tree))
    seeds = to_seeds(root, skill="apt-scw")
    assert [s.name for s in seeds] == ["seed-apt-scw-root", "seed-apt-scw-a"]
    # root = self/anchor-bound, parent None; child = DECOMPOSES_TO parent
    assert seeds[0].parent is None
    assert seeds[0].source_id == "span-root"
    assert seeds[1].parent == "seed-apt-scw-root"
    assert seeds[1].source_id == "span-a"
    assert all(0 <= s.depth <= 3 for s in seeds)


def test_seed_name_is_deterministic_idempotent():
    g = Goal(name="x", objective="X")
    s1 = to_seeds(plan(g, _no_decompose), "jaebaeman")
    s2 = to_seeds(plan(g, _no_decompose), "jaebaeman")
    assert [s.name for s in s1] == [s.name for s in s2]  # 같은 계획 → 같은 PK (MERGE 멱등)
