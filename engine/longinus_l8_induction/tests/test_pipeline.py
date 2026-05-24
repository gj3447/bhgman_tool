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
