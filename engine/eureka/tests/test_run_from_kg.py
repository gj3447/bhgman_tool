"""Phase 1 integration TDD — run_from_kg: stage_0(KG-extract) → induce_fca end-to-end.

fake CypherRunner로 realistic context 주입 → 비자명 concept 생산 확인.
실측 oracle (eureka-formal-context-smoketest phase0_oracle_pass): 321 obj → Topology/
GroupTheory/AbstractAlgebra 등 latent 군집. 여기선 deterministic fixture로 wiring 검증.

# KG: eureka-formal-context-smoketest-2026-05-27 (phase1 wiring), consensus-eureka-design-synthesis-2026-05-27
"""

from __future__ import annotations

from pipeline import PipelineConfig, run_from_kg


def _math_and_compiler_rows(query, params):
    """실측 군집 모사: 수학 4 + 컴파일러 4 (각 군집 공통 facet 공유)."""
    math_attrs = [
        "ALIGNS_WITH_AXIS:Structural Mathematics",
        "USES_ABSTRACT_DOMAIN:Algebraic and Topological Structure",
    ]
    comp_attrs = [
        "ALIGNS_WITH_AXIS:Machine and Resource",
        "USES_ABSTRACT_DOMAIN:Intermediate Representation and Lowering",
    ]
    return [
        {"object": "Topology", "attributes": math_attrs},
        {"object": "Group Theory", "attributes": math_attrs},
        {"object": "Abstract Algebra", "attributes": math_attrs},
        {"object": "Spectral Sequences", "attributes": math_attrs},
        {"object": "Operators", "attributes": comp_attrs},
        {"object": "Writing the Grammar", "attributes": comp_attrs},
        {"object": "Using Parsers", "attributes": comp_attrs},
        {"object": "Basic Syntax", "attributes": comp_attrs},
    ]


def test_run_from_kg_records_stage_0():
    pr = run_from_kg(_math_and_compiler_rows, PipelineConfig(cycle_id="phase1-test"))
    s0 = pr.stages[0]
    assert s0.stage == "0-kg-extract-formal-context"
    assert s0.ok is True
    assert s0.payload["objects"] == 8


def test_run_from_kg_induces_concepts():
    pr = run_from_kg(_math_and_compiler_rows, PipelineConfig(cycle_id="phase1-test"))
    induce = next(s for s in pr.stages if s.stage == "4-induce-fca")
    # 수학 군집 + 컴파일러 군집 = 비자명 concept 생산 (extent≥2 = min_extent default)
    assert induce.payload["abstract_classes"] >= 1


def test_fidelity_stage_skipped_without_runner():
    pr = run_from_kg(_math_and_compiler_rows, PipelineConfig(cycle_id="phase1-test"))
    fid = [s for s in pr.stages if s.stage == "4.8-fidelity-gate"]
    if fid:  # acs 생산됐을 때만 stage 존재
        assert "skipped" in fid[0].payload


def test_fidelity_stage_runs_with_runner():
    from fidelity_gate import FidelityConfig

    def fid_runner(query, params):  # 멤버가 witness로 cohere (PASS)
        return [
            {"witness": "IN_CATEGORY", "top_shared": 4, "extent": 4},
            {"witness": "RELATED_TO", "top_shared": 4, "extent": 4},
        ]

    cfg = PipelineConfig(
        cycle_id="phase2-test", fidelity_runner=fid_runner, fidelity_cfg=FidelityConfig()
    )
    pr = run_from_kg(_math_and_compiler_rows, cfg)
    fid = [s for s in pr.stages if s.stage == "4.8-fidelity-gate"]
    if fid:
        assert "results" in fid[0].payload


def test_run_from_kg_empty_context_no_crash():
    pr = run_from_kg(lambda q, p: [], PipelineConfig(cycle_id="phase1-empty"))
    assert pr.stages[0].stage == "0-kg-extract-formal-context"
    assert pr.stages[0].ok is False  # 빈 context
    assert pr.stages[0].payload["objects"] == 0
