"""fidelity_gate TDD — consilience(witness) 측정 + SOFT verdict + ensemble k.

# KG: consensus-eureka-design-synthesis-2026-05-27 (SF1-4), eureka-formal-context-smoketest-2026-05-27
"""

from __future__ import annotations

from engine.eureka.fidelity_gate import (
    DEFAULT_WITNESS_RELS,
    FidelityConfig,
    assess_fidelity,
    fidelity_witness_cypher,
    run_fidelity_gate,
)


def test_high_consilience_passes():
    # 2 witness가 ≥30% 공유 → ensemble k=2 PASS
    rows = [
        {"witness": "IN_CATEGORY", "top_shared": 60, "extent": 100},
        {"witness": "RELATED_TO", "top_shared": 40, "extent": 100},
        {"witness": "ABOUT", "top_shared": 5, "extent": 100},
    ]
    v = assess_fidelity("c", rows)
    assert v.witnesses_passing == 2
    assert v.passed is True
    assert v.witness_top_share["IN_CATEGORY"] == 0.6


def test_thin_abstraction_soft_warns():
    # facet으로만 정의 → witness로 흩어짐 (compiler-frontend 실측 패턴 모사)
    rows = [
        {"witness": "ABOUT", "top_shared": 64, "extent": 324},  # 0.20 < 0.30
        {"witness": "IN_CATEGORY", "top_shared": 0, "extent": 324},
        {"witness": "RELATED_TO", "top_shared": 0, "extent": 324},
    ]
    v = assess_fidelity("compiler", rows)
    assert v.witnesses_passing == 0
    assert v.passed is False  # SOFT_WARN
    assert "SOFT_WARN" in v.detail


def test_single_witness_below_ensemble_k():
    rows = [
        {"witness": "IN_CATEGORY", "top_shared": 80, "extent": 100},  # 0.8 PASS
        {"witness": "RELATED_TO", "top_shared": 10, "extent": 100},  # fail
    ]
    v = assess_fidelity("c", rows)
    assert v.witnesses_passing == 1
    assert v.passed is False  # k=2 미달 → 단일 proxy 금지(SF3)


def test_zero_extent_no_crash():
    v = assess_fidelity("empty", [{"witness": "ABOUT", "top_shared": 0, "extent": 0}])
    assert v.extent == 0
    assert v.passed is False


def test_witness_cypher_excludes_facets_uses_instance_of():
    q, params = fidelity_witness_cypher("c", FidelityConfig())
    assert "INSTANCE_OF" in q
    assert "ALIGNS_WITH_AXIS" not in params["witness_rels"]  # facet 제외
    assert "IN_CATEGORY" in params["witness_rels"]
    assert params["concept"] == "c"


def test_run_fidelity_gate_with_fake_runner():
    def fake(query, params):
        return [
            {"witness": "IN_CATEGORY", "top_shared": 50, "extent": 100},
            {"witness": "SAME_TRADITION", "top_shared": 45, "extent": 100},
        ]

    v = run_fidelity_gate("c", fake)
    assert v.passed is True and v.witnesses_passing == 2


def test_default_witnesses_are_held_out_relations():
    assert "IN_CATEGORY" in DEFAULT_WITNESS_RELS
    assert "ALIGNS_WITH_AXIS" not in DEFAULT_WITNESS_RELS  # 형성 facet은 witness 아님
