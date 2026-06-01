"""A/B decompose 비교 코어 (PROM 16 P4/C6) — 두 분해 전략의 구조 발산 측정.

bench는 runner, 비교 *로직*은 여기(engine 패키지, 단위 테스트 대상). occam.py↔occam_runner.py
처럼 로직/실행 분리. Goodhart 가드: 단일 품질 점수 없음 — node/depth/jaccard/arm-only raw만.

# KG: lesson-jaebaeman-engine-impl-prom16-2026-06-01 (C6), finding-jbm-eng-D3
"""

from __future__ import annotations

from engine.jaebaeman.jaebaeman_models import MAX_DEPTH, Goal
from engine.jaebaeman.planner import DecomposeFn, depth_max, leaf_count, plan, walk


def _tree_stats(tree) -> dict:
    names = sorted({n.name for n, _ in walk(tree)})
    return {
        "node_count": len(names),
        "depth_max": depth_max(tree),
        "leaf_count": leaf_count(tree),
        "names": names,
    }


def compare_decompose(
    goal: Goal, arm_a: DecomposeFn, arm_b: DecomposeFn, *, max_depth: int = MAX_DEPTH
) -> dict:
    """두 분해 전략의 계획 트리 구조 발산 (공정: 같은 goal/max_depth). raw 비교 dict, 단일점수 없음."""
    sa = _tree_stats(plan(goal, arm_a, max_depth=max_depth))
    sb = _tree_stats(plan(goal, arm_b, max_depth=max_depth))
    na, nb = set(sa["names"]), set(sb["names"])
    union = na | nb
    return {
        "goal": goal.name,
        "max_depth": max_depth,
        "arm_a": {k: v for k, v in sa.items() if k != "names"},
        "arm_b": {k: v for k, v in sb.items() if k != "names"},
        "jaccard": round(len(na & nb) / len(union), 3) if union else 1.0,
        "a_only": sorted(na - nb),
        "b_only": sorted(nb - na),
        "note": "raw 구조 발산만. 품질 판단은 외부 oracle (Goodhart 가드).",
    }


__all__ = ["compare_decompose"]
