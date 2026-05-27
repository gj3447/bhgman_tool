"""Leiden-family induction operator TDD — 실구현 검증 (NotImplementedError 제거).

# KG: challenge-occam-pass-bhgman_tool-bakeoff-not-completed-2026-05-27 (3-way bake-off unblock)
"""

from induction_operators.leiden_llm import MAX_NODES, induce_leiden_llm


def _two_cluster_context():
    """두 개의 뚜렷한 클러스터: {a,b,c} 공유 X/Y, {d,e,f} 공유 P/Q. 교차 속성 없음."""
    return {
        "a": frozenset({"X", "Y"}),
        "b": frozenset({"X", "Y"}),
        "c": frozenset({"X", "Y", "Z"}),
        "d": frozenset({"P", "Q"}),
        "e": frozenset({"P", "Q"}),
        "f": frozenset({"P", "Q", "R"}),
    }


def test_two_clusters_become_two_communities():
    result = induce_leiden_llm(_two_cluster_context(), min_extent=2, min_stability=0.0)
    assert result.fallback_reason is None
    # 두 클러스터가 서로 분리돼야 (공유 속성 없어 cross-edge 0).
    assert len(result.concepts) == 2
    extents = sorted(tuple(sorted(c.extent)) for c in result.concepts)
    assert extents == [("a", "b", "c"), ("d", "e", "f")]


def test_community_intent_is_shared_attributes():
    result = induce_leiden_llm(_two_cluster_context(), min_extent=2, min_stability=0.0)
    by_member = {tuple(sorted(c.extent)): c for c in result.concepts}
    xy = by_member[("a", "b", "c")]
    # a,b,c 공통 교집합 = {X, Y} (c만 Z 추가).
    assert xy.intent == frozenset({"X", "Y"})


def test_stability_in_unit_interval():
    result = induce_leiden_llm(_two_cluster_context(), min_extent=2, min_stability=0.0)
    for c in result.concepts:
        assert 0.0 <= c.stability <= 1.0


def test_min_extent_prunes_singletons():
    # 속성이 전부 disjoint → edge 0 → 전부 싱글톤 → min_extent=2로 전부 pruned.
    ctx = {"a": frozenset({"x"}), "b": frozenset({"y"}), "c": frozenset({"z"})}
    result = induce_leiden_llm(ctx, min_extent=2)
    assert result.concepts == ()
    assert result.pruned >= 1


def test_empty_context():
    result = induce_leiden_llm({})
    assert result.concepts == ()
    assert result.fallback_reason is None


def test_oversize_falls_back_to_gds():
    ctx = {f"o{i}": frozenset({"x"}) for i in range(MAX_NODES + 1)}
    result = induce_leiden_llm(ctx)
    assert result.fallback_reason is not None
    assert "gds.leiden" in result.fallback_reason


def test_determinism_same_input_same_output():
    ctx = _two_cluster_context()
    r1 = induce_leiden_llm(ctx, min_extent=2)
    r2 = induce_leiden_llm(ctx, min_extent=2)
    assert [tuple(sorted(c.extent)) for c in r1.concepts] == [
        tuple(sorted(c.extent)) for c in r2.concepts
    ]


def test_resolution_higher_yields_more_communities():
    # 약하게 연결된 두 그룹(공유 속성 1개 다리). 높은 γ는 더 잘게 쪼갬.
    ctx = {
        "a": frozenset({"X", "Y", "BRIDGE"}),
        "b": frozenset({"X", "Y"}),
        "c": frozenset({"P", "Q", "BRIDGE"}),
        "d": frozenset({"P", "Q"}),
    }
    low = induce_leiden_llm(ctx, resolution=0.1, min_extent=1, min_stability=0.0)
    high = induce_leiden_llm(ctx, resolution=5.0, min_extent=1, min_stability=0.0)
    assert len(high.concepts) >= len(low.concepts)
