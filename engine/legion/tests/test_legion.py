"""Legion orchestrator TDD — Contract-bound handoff + 나생문 oracle gate.

# KG: adr-seven-commander-legion-architecture-2026-05-27
"""

from __future__ import annotations

from legion import CANONICAL_ORDER, Legion
from legion_models import CommanderStage


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
