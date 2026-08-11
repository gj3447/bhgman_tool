"""Conformance tests for Eureka's pure local-only lifecycle reducer."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from engine.eureka.lifecycle import (
    EffectType,
    LifecycleConfiguration,
    LifecycleContext,
    LifecycleEvent,
    LifecycleEventType,
    LifecycleState,
    RejectionCode,
    TERMINAL_STATES,
    step,
)


_HASH_A = "a" * 64
_HASH_B = "b" * 64
_HASH_C = "c" * 64
_HASH_D = "d" * 64
_DEADLINE = datetime(2030, 1, 1, tzinfo=timezone.utc)


def _configuration(*, steps_remaining: int = 16) -> LifecycleConfiguration:
    return LifecycleConfiguration(
        LifecycleState.INIT,
        LifecycleContext(
            run_id="run-1",
            steps_remaining=steps_remaining,
            run_deadline=_DEADLINE,
            max_correction_rounds=1,
        ),
    )


def _event(
    event_type: LifecycleEventType | str,
    *,
    event_id: str,
    **payload,
) -> LifecycleEvent:
    return LifecycleEvent(
        type=event_type,
        run_id="run-1",
        actor="test-runner",
        event_id=event_id,
        payload=payload,
    )


def _advance(
    configuration: LifecycleConfiguration,
    event_type: LifecycleEventType,
    *,
    event_id: str,
    **payload,
) -> LifecycleConfiguration:
    result = step(configuration, _event(event_type, event_id=event_id, **payload))
    assert result.accepted, result.rejection
    return result.configuration


def _to_falsify() -> LifecycleConfiguration:
    configuration = _configuration()
    configuration = _advance(
        configuration,
        LifecycleEventType.START,
        event_id="1",
    )
    configuration = _advance(
        configuration,
        LifecycleEventType.PATTERNS_READY,
        event_id="2",
        evidence_hash=_HASH_A,
    )
    configuration = _advance(
        configuration,
        LifecycleEventType.ASSOCIATIONS_READY,
        event_id="3",
        evidence_hash=_HASH_A,
        association_hash=_HASH_B,
    )
    configuration = _advance(
        configuration,
        LifecycleEventType.CANDIDATES_READY,
        event_id="4",
        candidate_batch_hash=_HASH_C,
        producer_id="producer-1",
        producer_family="family-producer",
    )
    return _advance(
        configuration,
        LifecycleEventType.COMPRESSION_COMPLETED,
        event_id="5",
        candidate_hash=_HASH_C,
        evidence_hash=_HASH_A,
        producer_id="producer-1",
    )


def _evaluation(initial_verdict: str, **overrides) -> LifecycleEvent:
    payload = {
        "candidate_hash": _HASH_C,
        "evidence_hash": _HASH_A,
        "producer_id": "producer-1",
        "evaluator_id": "evaluator-1",
        "evaluator_family": "family-evaluator",
        "receipt_hash": _HASH_D,
        "verdict": initial_verdict,
        "receipt_verified": True,
        "deterministic_gates_passed": True,
    }
    payload.update(overrides)
    return _event(LifecycleEventType.EVALUATION_RECORDED, event_id="6", **payload)


def test_local_happy_path_is_exactly_propose_only():
    configuration = _configuration()
    expected = [
        (LifecycleEventType.START, {}, LifecycleState.DETECT, EffectType.REQUEST_PATTERN_DETECTION),
        (
            LifecycleEventType.PATTERNS_READY,
            {"evidence_hash": _HASH_A},
            LifecycleState.ASSOCIATE,
            EffectType.REQUEST_ASSOCIATIONS,
        ),
        (
            LifecycleEventType.ASSOCIATIONS_READY,
            {"evidence_hash": _HASH_A, "association_hash": _HASH_B},
            LifecycleState.DIVERGE,
            EffectType.REQUEST_CANDIDATE_GENERATION,
        ),
        (
            LifecycleEventType.CANDIDATES_READY,
            {
                "candidate_batch_hash": _HASH_C,
                "producer_id": "producer-1",
                "producer_family": "family-producer",
            },
            LifecycleState.COMPRESS,
            None,
        ),
        (
            LifecycleEventType.COMPRESSION_COMPLETED,
            {
                "candidate_hash": _HASH_C,
                "evidence_hash": _HASH_A,
                "producer_id": "producer-1",
            },
            LifecycleState.FALSIFY,
            EffectType.REQUEST_INDEPENDENT_EVALUATION,
        ),
    ]
    for index, (event_type, payload, target, effect_type) in enumerate(expected, start=1):
        result = step(
            configuration,
            _event(event_type, event_id=str(index), **payload),
        )
        assert result.accepted, result.rejection
        assert result.configuration.state is target
        assert [command.type for command in result.commands] == (
            [effect_type] if effect_type is not None else []
        )
        configuration = result.configuration

    passed = step(configuration, _evaluation("PASS"))
    assert passed.accepted
    assert passed.configuration.state is LifecycleState.READY_TO_PROPOSE

    proposed = step(
        passed.configuration,
        _event(
            LifecycleEventType.RETURN_LOCAL_PROPOSAL,
            event_id="7",
            candidate_hash=_HASH_C,
            proposal_hash=_HASH_B,
        ),
    )
    assert proposed.accepted
    assert proposed.configuration.state is LifecycleState.PROPOSED
    assert [command.type for command in proposed.commands] == [
        EffectType.RECORD_LOCAL_PROPOSAL
    ]
    assert "ACCEPTED" not in {state.value for state in LifecycleState}
    assert "ACCEPTED" not in {effect.value for effect in EffectType}


def test_only_bound_independent_pass_can_reach_ready_to_propose():
    cases = (
        {"candidate_hash": _HASH_B},
        {"evidence_hash": _HASH_B},
        {"receipt_hash": "not-a-digest"},
        {"receipt_verified": False},
        {"deterministic_gates_passed": False},
        {"evaluator_id": "producer-1"},
        {"evaluator_family": "family-producer"},
        {"verdict": "REJECT"},
    )
    for overrides in cases:
        result = step(_to_falsify(), _evaluation("PASS", **overrides))
        assert result.accepted
        assert result.configuration.state is LifecycleState.REJECTED


def test_revision_is_bounded_and_returns_to_falsify():
    revise = step(_to_falsify(), _evaluation("REVISE"))
    assert revise.accepted
    assert revise.configuration.state is LifecycleState.REVISE
    assert [command.type for command in revise.commands] == [EffectType.REQUEST_REVISION]

    revised = step(
        revise.configuration,
        _event(
            LifecycleEventType.REVISION_READY,
            event_id="7",
            candidate_hash=_HASH_B,
            evidence_hash=_HASH_A,
            producer_id="producer-1",
        ),
    )
    assert revised.accepted
    assert revised.configuration.state is LifecycleState.FALSIFY
    assert revised.configuration.context.correction_round == 1

    second_revision = step(
        revised.configuration,
        _evaluation("REVISE", candidate_hash=_HASH_B),
    )
    assert second_revision.accepted
    assert second_revision.configuration.state is LifecycleState.REJECTED


@pytest.mark.parametrize(
    ("event_type", "payload", "terminal"),
    (
        (
            LifecycleEventType.PLATEAU,
            {"fingerprint": _HASH_A, "gain": 0.0},
            LifecycleState.PLATEAU,
        ),
        (
            LifecycleEventType.RETRIES_EXHAUSTED,
            {"failure_class": "transient"},
            LifecycleState.RETRY_EXHAUSTED,
        ),
    ),
)
def test_revision_terminal_events_are_typed(event_type, payload, terminal):
    revise = step(_to_falsify(), _evaluation("REVISE"))
    assert revise.accepted
    result = step(
        revise.configuration,
        _event(event_type, event_id=f"terminal-{event_type.value}", **payload),
    )
    assert result.accepted
    assert result.configuration.state is terminal


def test_invalid_event_is_rejected_without_state_change_and_audited():
    configuration = _configuration()
    result = step(
        configuration,
        _event(LifecycleEventType.PATTERNS_READY, event_id="bad", evidence_hash=_HASH_A),
    )
    assert result.accepted is False
    assert result.rejection is not None
    assert result.rejection.code is RejectionCode.INVALID_EVENT
    assert result.configuration == configuration
    assert [command.type for command in result.commands] == [
        EffectType.AUDIT_INVALID_TRANSITION
    ]


def test_unknown_event_is_rejected_explicitly():
    result = step(_configuration(), _event("ACCEPTED", event_id="bad"))
    assert result.accepted is False
    assert result.rejection is not None
    assert result.rejection.code is RejectionCode.INVALID_EVENT


def test_terminal_states_are_isolated():
    for terminal in TERMINAL_STATES:
        configuration = LifecycleConfiguration(terminal, _configuration().context)
        result = step(configuration, _event(LifecycleEventType.START, event_id="late"))
        assert result.accepted is False
        assert result.rejection is not None
        assert result.rejection.code is RejectionCode.TERMINAL_STATE
        assert result.configuration.state is terminal


def test_timeout_guard_rejects_early_observation_and_accepts_due_deadline():
    configuration = _configuration()
    early = step(
        configuration,
        _event(
            LifecycleEventType.TIMEOUT,
            event_id="early",
            deadline=_DEADLINE.isoformat(),
            observed_at=(_DEADLINE - timedelta(seconds=1)).isoformat(),
        ),
    )
    assert early.accepted is False
    assert early.rejection is not None
    assert early.rejection.code is RejectionCode.GUARD_FALSE

    due = step(
        configuration,
        _event(
            LifecycleEventType.TIMEOUT,
            event_id="due",
            deadline=_DEADLINE.isoformat(),
            observed_at=_DEADLINE.isoformat(),
        ),
    )
    assert due.accepted
    assert due.configuration.state is LifecycleState.TIMED_OUT


@pytest.mark.parametrize(
    "state",
    (
        LifecycleState.INIT,
        LifecycleState.DETECT,
        LifecycleState.ASSOCIATE,
        LifecycleState.DIVERGE,
        LifecycleState.COMPRESS,
        LifecycleState.FALSIFY,
        LifecycleState.REVISE,
        LifecycleState.READY_TO_PROPOSE,
    ),
)
@pytest.mark.parametrize(
    ("event_type", "payload", "terminal"),
    (
        (LifecycleEventType.CANCEL, {"reason": "operator request"}, LifecycleState.CANCELED),
        (
            LifecycleEventType.TIMEOUT,
            {"deadline": _DEADLINE.isoformat(), "observed_at": _DEADLINE.isoformat()},
            LifecycleState.TIMED_OUT,
        ),
        (
            LifecycleEventType.BUDGET_EXHAUSTED,
            {"budget_kind": "steps"},
            LifecycleState.BUDGET_EXHAUSTED,
        ),
    ),
)
def test_safe_state_interrupts_have_terminal_paths(state, event_type, payload, terminal):
    configuration = LifecycleConfiguration(state, _to_falsify().context)
    result = step(
        configuration,
        _event(event_type, event_id=f"interrupt-{state.value}-{event_type.value}", **payload),
    )
    assert result.accepted
    assert result.configuration.state is terminal


def test_zero_step_budget_requires_typed_budget_event():
    configuration = _configuration(steps_remaining=0)
    blocked = step(configuration, _event(LifecycleEventType.START, event_id="start"))
    assert blocked.accepted is False
    assert blocked.rejection is not None
    assert blocked.rejection.code is RejectionCode.STEP_BUDGET_EXHAUSTED

    exhausted = step(
        configuration,
        _event(
            LifecycleEventType.BUDGET_EXHAUSTED,
            event_id="budget",
            budget_kind="steps",
        ),
    )
    assert exhausted.accepted
    assert exhausted.configuration.state is LifecycleState.BUDGET_EXHAUSTED
    assert exhausted.configuration.context.steps_remaining == 0


def test_payload_and_run_identity_fail_closed():
    missing = step(
        _configuration(),
        _event(LifecycleEventType.PATTERNS_READY, event_id="missing"),
    )
    assert missing.accepted is False
    assert missing.rejection is not None
    assert missing.rejection.code is RejectionCode.INVALID_PAYLOAD

    wrong_run = LifecycleEvent(
        type=LifecycleEventType.START,
        run_id="another-run",
        actor="test-runner",
        event_id="wrong-run",
    )
    mismatch = step(_configuration(), wrong_run)
    assert mismatch.accepted is False
    assert mismatch.rejection is not None
    assert mismatch.rejection.code is RejectionCode.RUN_ID_MISMATCH


def test_runtime_vocabulary_is_bound_to_machine_readable_contract():
    contract_path = (
        Path(__file__).resolve().parents[1]
        / "contracts"
        / "semantic-creative-fsm.v1.json"
    )
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    machine = contract["machines"][0]
    contract_states = {item["id"] for item in machine["states"]}
    contract_events = set(contract["event_schemas"])
    contract_effects = set(contract["effects"])

    assert {state.value for state in LifecycleState} <= contract_states
    assert {event.value for event in LifecycleEventType} <= contract_events
    assert {effect.value for effect in EffectType} <= contract_effects
    assert "ACCEPTED" not in contract_states
