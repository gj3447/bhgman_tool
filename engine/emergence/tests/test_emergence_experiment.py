"""창발 falsifier — 국소 규칙만으로 잠재 의미 구조가 복원되는가.

울프람 계산 불가역성: 닫힌 식이 아니라 *돌려서* 창발을 확인한다.
"""
# KG: engineboy-emergence-engine-fsm-design-2026-07-13

from __future__ import annotations

from engine.emergence.experiment import LATENT, POPULARITY, run_experiment, _CLUSTER_OF


def test_hebbian_recovers_latent_clusters():
    # 엔진에 클러스터를 알려주지 않았는데 Hebbian 엣지가 경계를 복원
    r = run_experiment(seed=7)
    assert r.structure_emerged
    assert r.intra_edge_mean > 10 * r.inter_edge_mean     # 강한 분리
    # 최강 엣지들은 클러스터-내
    for a, b, _ in r.top_edges[:5]:
        assert _CLUSTER_OF[a] == _CLUSTER_OF[b]


def test_hierarchy_favors_popular_cluster():
    # 계층 상단(HOT)은 인기 클러스터가 더 많이 차지 (traffic ∝ 계층)
    r = run_experiment(seed=7)
    counts = {name: 0 for name in LATENT}
    for c in r.hot_concepts:
        counts[_CLUSTER_OF[c]] += 1
    most_popular = max(POPULARITY, key=POPULARITY.get)
    least_popular = min(POPULARITY, key=POPULARITY.get)
    assert counts[most_popular] >= counts[least_popular]
    assert counts[most_popular] >= 1


def test_experiment_deterministic():
    a = run_experiment(seed=7)
    b = run_experiment(seed=7)
    assert a.hot_concepts == b.hot_concepts
    assert abs(a.intra_edge_mean - b.intra_edge_mean) < 1e-9
