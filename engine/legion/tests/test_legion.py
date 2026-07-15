"""Legion orchestrator TDD — Contract-bound handoff + 나생문 oracle gate.

# KG: adr-seven-commander-legion-architecture-2026-05-27
"""

from __future__ import annotations

from engine.legion.legion import CANONICAL_ORDER, Legion
from engine.legion.legion_models import CommanderStage


def _stage(name, verb, requires, provides, out):
    return CommanderStage(name, verb, requires, provides, run=lambda ctx: out)


def test_canonical_pipeline_runs_in_order():
    legion = (
        Legion()
        .register(_stage("prometheus", "획득", (), ("knowledge",), {"knowledge": "K"}))
        .register(
            _stage("longinus", "연결", ("knowledge",), ("linked_graph",), {"linked_graph": "G"})
        )
        .register(
            _stage("eureka", "창조", ("linked_graph",), ("abstractions",), {"abstractions": ["A"]})
        )
        .register(_stage("occam", "정리", ("abstractions",), ("superseded",), {"superseded": []}))
    )
    run = legion.run(context={})
    assert run.completed is True
    assert run.ran == 4
    assert [o.verb for o in run.outcomes] == ["획득", "연결", "창조", "정리"]
    assert run.contract_violation is None


def test_contract_violation_when_requires_unmet():
    # eureka가 linked_graph 요구하는데 롱기누스 없이 등록 → contract 위반
    legion = (
        Legion()
        .register(_stage("prometheus", "획득", (), ("knowledge",), {"knowledge": "K"}))
        .register(
            _stage("eureka", "창조", ("linked_graph",), ("abstractions",), {"abstractions": ["A"]})
        )
    )
    run = legion.run(context={})
    assert run.completed is False
    assert run.contract_violation is not None
    assert "eureka requires" in run.contract_violation
    assert run.ran == 1  # prometheus만 돎


def test_provides_contract_enforced():
    # stage가 선언한 provides를 실제로 안 내놓으면 위반
    legion = Legion().register(_stage("liar", "창조", (), ("abstractions",), {"wrong_key": 1}))
    run = legion.run(context={})
    assert run.completed is False
    assert "did not provide" in run.contract_violation


def test_oracle_gate_hard_stops_pipeline():
    # 나생문 oracle gate가 eureka 직후 FAIL → 파이프라인 정지 (occam 안 돎)
    calls = {"n": 0}

    def gate(ctx):
        calls["n"] += 1
        # 둘째 호출(eureka 후)에서 FAIL
        return (calls["n"] != 2, "syntax error" if calls["n"] == 2 else "PASS")

    legion = (
        Legion()
        .register(_stage("longinus", "연결", (), ("linked_graph",), {"linked_graph": "G"}))
        .register(
            _stage("eureka", "창조", ("linked_graph",), ("abstractions",), {"abstractions": ["A"]})
        )
        .register(_stage("occam", "정리", ("abstractions",), ("superseded",), {"superseded": []}))
    )
    run = legion.run(context={}, gate=gate)
    assert run.completed is False
    assert run.gate_failure is not None
    assert "eureka" in run.gate_failure
    # occam은 실행되지 않음 — outcomes에 occam ok=True 없음
    assert not any(o.stage == "occam" and o.ok for o in run.outcomes)


def test_oracle_gate_all_pass_completes():
    legion = Legion().register(
        _stage("eureka", "창조", (), ("abstractions",), {"abstractions": ["A"]})
    )
    run = legion.run(context={}, gate=lambda ctx: (True, "PASS"))
    assert run.completed is True


def test_canonical_order_constant():
    # 종착 실현(하데스) 추가 2026-05-30 — 정방향 합성 종착 = 추상→구체 (APT/SCW)
    assert CANONICAL_ORDER == ("획득", "연결", "창조", "정리", "검증", "실현")


def test_full_forward_pipeline_terminates_in_realize():
    # 6-stage 정방향: 검증 통과 추상 → 하데스가 구체 코드로 실현 (종착)
    legion = (
        Legion()
        .register(_stage("prometheus", "획득", (), ("knowledge",), {"knowledge": "K"}))
        .register(
            _stage("longinus", "연결", ("knowledge",), ("linked_graph",), {"linked_graph": "G"})
        )
        .register(
            _stage("eureka", "창조", ("linked_graph",), ("abstractions",), {"abstractions": ["A"]})
        )
        .register(_stage("occam", "정리", ("abstractions",), ("superseded",), {"superseded": []}))
        .register(
            _stage("naesengmoon", "검증", ("abstractions",), ("verdict",), {"verdict": "PASS"})
        )
        .register(
            _stage(
                "hades",
                "실현",
                ("verdict", "abstractions"),
                ("source_code",),
                {"source_code": "src"},
            )
        )
    )
    run = legion.run(context={})
    assert run.completed is True
    assert run.ran == 6
    assert [o.verb for o in run.outcomes] == ["획득", "연결", "창조", "정리", "검증", "실현"]
    assert run.outcomes[-1].verb == "실현"  # 종착 = 하데스


# ── W2-A: runtime measurement-driven dispatch (measure() + decide_dispatch()) ──


def test_runtime_measurement_emits_dispatch_decision():
    """A stage carrying a measure factory now produces DispatchDecision records at RUNTIME
    when a measured metric crosses its threshold (Legion.run() never called measure() before)."""
    from engine.legion.commanders import _measure_prometheus

    over = CommanderStage(
        "prometheus",
        "획득",
        (),
        ("acquired",),
        run=lambda _ctx: {
            "acquired": {"mode": "kg-deterministic", "fetched": True, "findings": 20}
        },
        measure=_measure_prometheus,
    )
    run = Legion().register(over).run(context={})
    assert run.completed
    targets = {d.target_commander for d in run.dispatch_decisions}
    assert "naesengmoon" in targets  # finding_count 20 > 16 → dispatch verification


def test_below_threshold_emits_no_dispatch_decision():
    from engine.legion.commanders import _measure_prometheus

    under = CommanderStage(
        "prometheus",
        "획득",
        (),
        ("acquired",),
        run=lambda _ctx: {"acquired": {"findings": 3}},
        measure=_measure_prometheus,
    )
    run = Legion().register(under).run(context={})
    assert run.dispatch_decisions == ()


def test_stage_without_measure_factory_records_nothing():
    stage = _stage("x", "획득", (), ("k",), {"k": "v"})  # no measure
    assert Legion().register(stage).run(context={}).dispatch_decisions == ()


def test_dispatch_decision_emitted_via_write_cypher():
    from engine.legion.commanders import _measure_prometheus

    calls: list = []

    def wc(cypher, params):
        calls.append((cypher, params))
        return []

    over = CommanderStage(
        "prometheus",
        "획득",
        (),
        ("acquired",),
        run=lambda _ctx: {"acquired": {"fetched": True, "findings": 20}},
        measure=_measure_prometheus,
    )
    run = Legion().register(over).run(context={"write_cypher": wc})
    assert run.dispatch_decisions  # ≥1 decision
    assert any("DispatchEvent" in c for c, _ in calls)  # emitted as :DispatchEvent


def test_dispatch_event_persisted_to_local_kg(tmp_path):
    from engine.kg_local.runner import make_local_runner
    from engine.kg_local.store import LocalKgStore
    from engine.legion.commanders import _measure_prometheus

    store = LocalKgStore(tmp_path / "kg.json")
    runner = make_local_runner(store)
    over = CommanderStage(
        "prometheus",
        "획득",
        (),
        ("acquired",),
        run=lambda _ctx: {"acquired": {"fetched": True, "findings": 20}},
        measure=_measure_prometheus,
    )
    Legion().register(over).run(context={"write_cypher": runner})
    assert store.find_nodes("DispatchEvent")  # the decision reached the KG


# ── PROM16 typed taxonomy: programming errors are no longer silently swallowed (GAP-1) ──


class _BoomMeasure:
    """A measurement whose decide_dispatch() raises the given error."""

    def __init__(self, exc):
        self._exc = exc

    def decide_dispatch(self, *, cycle_id=None):
        raise self._exc


def _measured_stage(exc):
    return CommanderStage(
        "prometheus",
        "획득",
        (),
        ("acquired",),
        run=lambda _ctx: {"acquired": True},
        measure=lambda _ctx: _BoomMeasure(exc),
    )


def test_transient_measurement_failure_is_still_absorbed():
    """A KG/network blip during measurement leaves the run intact with no decisions
    (the pre-existing best-effort contract, now scoped to transient only)."""
    run = Legion().register(_measured_stage(ConnectionError("kg blip"))).run(context={})
    assert run.completed is True
    assert run.dispatch_decisions == ()


def test_programming_error_in_measurement_is_reraised():
    """A deterministic bug must surface instead of vanishing behind `except Exception`
    (it used to make the daemon tick forever on an invisible defect)."""
    import pytest

    with pytest.raises(AttributeError, match="deterministic bug"):
        Legion().register(_measured_stage(AttributeError("deterministic bug"))).run(context={})


def test_transient_write_cypher_failure_keeps_provenance_best_effort():
    from engine.legion.commanders import _measure_prometheus

    def wc(_cypher, _params):
        raise ConnectionError("neo4j down")

    over = CommanderStage(
        "prometheus",
        "획득",
        (),
        ("acquired",),
        run=lambda _ctx: {"acquired": {"fetched": True, "findings": 20}},
        measure=_measure_prometheus,
    )
    run = Legion().register(over).run(context={"write_cypher": wc})
    assert run.completed is True  # provenance is best-effort against transient failure
    assert run.dispatch_decisions  # the decision still lives in LegionRun


def test_programming_error_in_provenance_write_is_reraised():
    import pytest

    from engine.legion.commanders import _measure_prometheus

    def wc(_cypher, _params):
        raise TypeError("bad param shape")

    over = CommanderStage(
        "prometheus",
        "획득",
        (),
        ("acquired",),
        run=lambda _ctx: {"acquired": {"fetched": True, "findings": 20}},
        measure=_measure_prometheus,
    )
    with pytest.raises(TypeError, match="bad param shape"):
        Legion().register(over).run(context={"write_cypher": wc})
