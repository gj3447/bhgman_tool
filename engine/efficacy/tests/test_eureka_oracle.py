"""eureka recovery oracle 순수 함수 테스트 — planted 구성 / recall / naive baseline."""

from __future__ import annotations

from engine.efficacy.eureka_oracle import (
    _DECOY,
    build_planted_context,
    naive_extents,
    recovery_recall,
)


# ── build_planted_context ────────────────────────────────────────────────────────
def test_planted_shape_and_cyclic_pairs():
    ctx, planted = build_planted_context(k=6, objects_per=4)
    assert len(planted) == 6
    assert all(len(g) == 4 for g in planted)
    assert len(ctx) == 24  # 6 concepts × 4 objects, disjoint
    # 각 객체는 cyclic-pair 2속성 + decoy.
    o00 = ctx["o_0_0"]
    assert _DECOY in o00
    assert "a_0" in o00 and "a_1" in o00


def test_each_single_attr_spans_two_concepts():
    ctx, _ = build_planted_context(k=6, objects_per=4)
    # a_1 은 개념0(둘째)·개념1(첫째)에 모두 → 단일속성으론 식별 불가.
    holders = {o for o, attrs in ctx.items() if "a_1" in attrs}
    assert {f"o_0_{j}" for j in range(4)} <= holders
    assert {f"o_1_{j}" for j in range(4)} <= holders


# ── recovery_recall ──────────────────────────────────────────────────────────────
def test_recall_perfect_when_extents_match():
    planted = [frozenset({"a", "b"}), frozenset({"c", "d"})]
    assert recovery_recall(planted, planted) == 1.0


def test_recall_zero_when_overincluded_below_thresh():
    planted = [frozenset({"a", "b"})]
    over = [frozenset({"a", "b", "c", "d", "e"})]  # Jaccard 2/5 = 0.4 < 0.8
    assert recovery_recall(over, planted) == 0.0


def test_recall_empty_planted():
    assert recovery_recall([frozenset({"x"})], []) == 0.0


# ── naive baseline fails on cyclic-pair structure ────────────────────────────────
def test_naive_single_attr_cannot_recover_cyclic_concepts():
    ctx, planted = build_planted_context(k=6, objects_per=4)
    naive_recall = recovery_recall(naive_extents(ctx), planted)
    assert naive_recall == 0.0  # 단일속성 extent는 항상 2개 개념 병합 → Jaccard<0.8
