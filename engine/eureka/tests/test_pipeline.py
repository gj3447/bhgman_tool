from pipeline import PipelineConfig, run
from protocols import StageResult


def test_pipeline_runs_to_completion_with_fca_input():
    context = {
        "node_a": frozenset({"axis_x", "axis_y"}),
        "node_b": frozenset({"axis_x", "axis_y"}),
        "node_c": frozenset({"axis_x", "axis_y"}),
    }
    cfg = PipelineConfig(cycle_id="test-cycle-2026-05-20")
    result = run(reference_sites=[], formal_context=context, config=cfg)

    stage_names = [s.stage for s in result.stages]
    assert "1-extract" in stage_names
    assert "4-induce-fca" in stage_names
    induce_result = next(s for s in result.stages if s.stage == "4-induce-fca")
    assert induce_result.ok
    assert induce_result.payload["abstract_classes"] >= 1


def test_pipeline_empty_input_no_crash():
    cfg = PipelineConfig(cycle_id="empty-test")
    result = run(reference_sites=[], formal_context={}, config=cfg)
    extract = next(s for s in result.stages if s.stage == "1-extract")
    assert extract.payload["count"] == 0


def test_notimplemented_stages_recorded_explicit():
    cfg = PipelineConfig(cycle_id="explicit-stub-test")
    result = run(reference_sites=[], formal_context={}, config=cfg)
    community = next(s for s in result.stages if s.stage == "2-community")
    assert community.ok is False
    assert community.payload == {"not_implemented": True}
    assert "Leiden" in community.error


class _FakeStage:
    name = "2-community"

    def run(self, context):
        return StageResult(
            stage="2-community",
            ok=True,
            payload={"injected": True, "size": len(context.get("candidates", []))},
        )


def test_injected_stage_runs_in_place_of_stub():
    cfg = PipelineConfig(cycle_id="injection-test", stage_community=_FakeStage())
    result = run(reference_sites=[{"id": "x"}, {"id": "y"}], formal_context={}, config=cfg)
    community = next(s for s in result.stages if s.stage == "2-community")
    assert community.ok is True
    assert community.payload["injected"] is True
    assert community.payload["size"] == 2


# ── amie3 operator dispatch (Java 주입식, 2026-05-27) ──────────────────────


def test_pipeline_amie3_method_dispatches_to_adapter():
    """config.method='amie3' → induce_via_amie3 경유. fake amie3_runner 주입(Java 불필요)."""
    from amie3_adapter import formal_context_to_triples  # noqa: PLC0415
    from induction_operators.amie3 import Amie3Result, HornRule  # noqa: PLC0415
    from pipeline import PipelineConfig, stage_4_induce  # noqa: PLC0415

    context = {
        "Topology": frozenset({"AXIS:Math", "DOMAIN:Algebra"}),
        "Group Theory": frozenset({"AXIS:Math", "DOMAIN:Algebra"}),
        "Algebra": frozenset({"AXIS:Math", "DOMAIN:Algebra"}),
    }

    def fake_amie3(triples, **kw):
        assert list(triples) == formal_context_to_triples(context)
        rule = HornRule(
            body="?x AXIS Math",
            head="?x DOMAIN Algebra",
            head_coverage=0.5,
            std_confidence=0.9,
            pca_confidence=0.9,
            positive_examples=3,
            body_size=3,
            pca_body_size=3,
        )
        return Amie3Result(
            rules=(rule,), triples_input=len(list(triples)), raw_stdout_lines=(), elapsed_sec=0.0
        )

    cfg = PipelineConfig(
        cycle_id="amie3-test", method="amie3", amie3_runner=fake_amie3, amie3_min_pca=0.5
    )
    acs, edges, fca_result = stage_4_induce(context, cfg.cycle_id, cfg)
    assert len(acs) == 1
    assert acs[0].inductionMethod == "amie3"
    assert acs[0].name.startswith("ac_amie3_")
    assert set(acs[0].extent) == {"Topology", "Group Theory", "Algebra"}


def test_pipeline_default_method_is_fca():
    from pipeline import PipelineConfig, stage_4_induce  # noqa: PLC0415

    context = {
        "A": frozenset({"X:1", "Y:2"}),
        "B": frozenset({"X:1", "Y:2"}),
    }
    cfg = PipelineConfig(cycle_id="fca-default")
    acs, _edges, _r = stage_4_induce(context, cfg.cycle_id, cfg)
    assert all(ac.inductionMethod == "fca" for ac in acs)
