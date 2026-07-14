"""Slice 2 effect lease/attempt fencing falsifiers.

# KG: apt-tpa-legion-engine-canon-2026-06-12
# Design: SYMPOSIUM/THEORY/APT/vnext/APT_ENGINE_FSM_DESIGN_2026-07-13.md Slice 2
"""

from __future__ import annotations

import pytest

from engine.apt_runtime.domain.events import EventType
from engine.apt_runtime.domain.reducer import (
    GuardRejectedError,
    InvalidTransitionError,
    StaleEffectExecutionError,
    reduce_event,
)
from engine.apt_runtime.domain.state import EffectLifecycle, state_hash
from engine.apt_runtime.tests.test_reducer import (
    SPEC,
    cancel_payload,
    create_cycle,
    event,
    guard_payload,
    lease_payload,
    start_cycle,
)


LEASE_ONE_EXPIRY = "2026-07-13T01:00:00Z"
LEASE_TWO_EXPIRY = "2026-07-13T02:00:00Z"


def _effect_event(
    state,
    event_type: EventType,
    payload: dict[str, object],
    *,
    created_at: str = "2026-07-13T00:00:00Z",
):
    if event_type is EventType.EFFECT_LEASED:
        event_payload = lease_payload(**payload)
    elif event_type in {EventType.EFFECT_LEASE_EXPIRED, EventType.EFFECT_TIMED_OUT}:
        effect = state.effect("effect-1")
        event_payload = {
            **payload,
            "expected_heartbeat_at": effect.heartbeat_at,
            "expected_lease_expiry": effect.lease_expiry,
        }
    else:
        event_payload = payload
    return reduce_event(
        state,
        event(
            event_type,
            state.version + 1,
            effect_id="effect-1",
            payload=event_payload,
            created_at=created_at,
        ),
        SPEC,
    )


def _queued_effect():
    state = start_cycle(create_cycle())
    return _effect_event(
        state,
        EventType.EFFECT_QUEUED,
        {
            "capability": "workspace.mutate",
            "provider": "fake-worker",
            "risk_class": "REVERSIBLE_WRITE",
            "idempotency_key": "idem-effect-1",
            "input_ref": "artifact://input/1",
            "input_hash": "a" * 64,
        },
    )


def _leased_effect(
    *,
    owner: str = "worker-1",
    token: str = "lease-1",
    expiry: str = LEASE_ONE_EXPIRY,
):
    return _effect_event(
        _queued_effect(),
        EventType.EFFECT_LEASED,
        {"lease_owner": owner, "lease_token": token, "lease_expiry": expiry},
    )


def _running_effect(*, attempt: int = 1, token: str = "lease-1"):
    return _effect_event(
        _leased_effect(token=token),
        EventType.EFFECT_STARTED,
        {"attempt": attempt, "lease_token": token},
    )


def _failed_effect():
    return _effect_event(
        _running_effect(),
        EventType.EFFECT_FAILED,
        {"attempt": 1, "lease_token": "lease-1", "reason": "worker lost response"},
    )


def test_active_lease_identity_changes_the_canonical_state_hash() -> None:
    first = _leased_effect(owner="worker-1", token="lease-1", expiry=LEASE_ONE_EXPIRY)
    second = _leased_effect(owner="worker-2", token="lease-2", expiry=LEASE_TWO_EXPIRY)

    assert state_hash(first) != state_hash(second)
    assert first.effect("effect-1").lease_owner == "worker-1"
    assert second.effect("effect-1").lease_token == "lease-2"


def test_heartbeat_requires_the_active_owner_token_and_forward_times() -> None:
    heartbeat = EventType("EffectHeartbeatRecorded")
    state = _leased_effect()
    state = _effect_event(
        state,
        heartbeat,
        {
            "lease_owner": "worker-1",
            "lease_token": "lease-1",
            "heartbeat_at": "2026-07-13T00:30:00Z",
            "lease_expiry": LEASE_TWO_EXPIRY,
        },
        created_at="2026-07-13T00:30:00Z",
    )
    effect = state.effect("effect-1")
    assert effect.heartbeat_at == "2026-07-13T00:30:00Z"
    assert effect.lease_expiry == LEASE_TWO_EXPIRY

    for payload in (
        {
            "lease_owner": "stale-worker",
            "lease_token": "lease-1",
            "heartbeat_at": "2026-07-13T00:45:00Z",
            "lease_expiry": "2026-07-13T03:00:00Z",
        },
        {
            "lease_owner": "worker-1",
            "lease_token": "stale-token",
            "heartbeat_at": "2026-07-13T00:45:00Z",
            "lease_expiry": "2026-07-13T03:00:00Z",
        },
        {
            "lease_owner": "worker-1",
            "lease_token": "lease-1",
            "heartbeat_at": "2026-07-13T00:29:59Z",
            "lease_expiry": "2026-07-13T03:00:00Z",
        },
        {
            "lease_owner": "worker-1",
            "lease_token": "lease-1",
            "heartbeat_at": "2026-07-13T00:45:00Z",
            "lease_expiry": LEASE_ONE_EXPIRY,
        },
    ):
        with pytest.raises(StaleEffectExecutionError):
            _effect_event(state, heartbeat, payload)


def test_running_effect_heartbeat_preserves_attempt_and_extends_lease() -> None:
    state = _running_effect()
    state = _effect_event(
        state,
        EventType.EFFECT_HEARTBEAT_RECORDED,
        {
            "lease_owner": "worker-1",
            "lease_token": "lease-1",
            "heartbeat_at": "2026-07-13T00:30:00Z",
            "lease_expiry": LEASE_TWO_EXPIRY,
        },
        created_at="2026-07-13T00:30:00Z",
    )

    effect = state.effect("effect-1")
    assert effect.lifecycle is EffectLifecycle.RUNNING
    assert effect.current_attempt == 1
    assert effect.attempts[0].outcome.value == "RUNNING"
    assert effect.heartbeat_at == "2026-07-13T00:30:00Z"


def test_stale_attempt_result_cannot_complete_a_retried_effect() -> None:
    state = _failed_effect()
    state = _effect_event(
        state,
        EventType.EFFECT_RETRY_QUEUED,
        guard_payload(
            lease_token="lease-1",
            reconciliation_ref="reconciliation://not-applied/1",
            reconciliation_outcome="NOT_APPLIED",
        ),
    )
    state = _effect_event(
        state,
        EventType.EFFECT_LEASED,
        {
            "lease_owner": "worker-2",
            "lease_token": "lease-2",
            "lease_expiry": LEASE_TWO_EXPIRY,
        },
    )
    state = _effect_event(
        state,
        EventType.EFFECT_STARTED,
        {"attempt": 2, "lease_token": "lease-2"},
    )

    with pytest.raises(StaleEffectExecutionError):
        _effect_event(
            state,
            EventType.EFFECT_SUCCEEDED,
            {
                "attempt": 1,
                "lease_token": "lease-1",
                "result_ref": "artifact://stale-attempt/1",
                "result_hash": "b" * 64,
            },
        )

    effect = state.effect("effect-1")
    assert effect.lifecycle is EffectLifecycle.RUNNING
    assert effect.current_attempt == 2
    assert tuple(attempt.attempt for attempt in effect.attempts) == (1, 2)


def test_retry_cannot_reuse_a_historical_lease_token() -> None:
    state = _failed_effect()
    state = _effect_event(
        state,
        EventType.EFFECT_RETRY_QUEUED,
        guard_payload(
            lease_token="lease-1",
            reconciliation_ref="reconciliation://not-applied/1",
            reconciliation_outcome="NOT_APPLIED",
        ),
    )

    with pytest.raises(StaleEffectExecutionError, match="cannot be reused"):
        _effect_event(
            state,
            EventType.EFFECT_LEASED,
            {
                "lease_owner": "worker-2",
                "lease_token": "lease-1",
                "lease_expiry": LEASE_TWO_EXPIRY,
            },
        )

    effect = state.effect("effect-1")
    assert effect.lifecycle is EffectLifecycle.PENDING
    assert effect.lease_token_history == ("lease-1",)


def test_attempt_numbers_are_strictly_monotonic() -> None:
    with pytest.raises(StaleEffectExecutionError, match="next monotonic attempt"):
        _running_effect(attempt=2)


def test_expiry_and_not_applied_retry_clear_only_the_active_lease_and_keep_audit() -> None:
    state = _effect_event(
        _leased_effect(),
        EventType.EFFECT_LEASE_EXPIRED,
        {
            "lease_token": "lease-1",
            "reconciliation_ref": "reconciliation://expired/1",
        },
    )
    expired = state.effect("effect-1")
    assert expired.lifecycle is EffectLifecycle.TIMED_OUT
    assert expired.lease_token == "lease-1"
    assert expired.reconciliation_refs == ("reconciliation://expired/1",)

    state = _effect_event(
        state,
        EventType.EFFECT_RETRY_QUEUED,
        guard_payload(
            lease_token="lease-1",
            reconciliation_ref="reconciliation://not-applied/1",
            reconciliation_outcome="NOT_APPLIED",
        ),
    )
    retried = state.effect("effect-1")
    assert retried.lifecycle is EffectLifecycle.PENDING
    assert retried.lease_owner is None
    assert retried.lease_token is None
    assert retried.lease_expiry is None
    assert retried.heartbeat_at is None
    assert retried.lease_token_history == ("lease-1",)
    assert retried.reconciliation_refs == (
        "reconciliation://expired/1",
        "reconciliation://not-applied/1",
    )


def test_unknown_reconciliation_cannot_clear_the_lease_or_queue_a_retry() -> None:
    state = _failed_effect()
    with pytest.raises(GuardRejectedError, match="NOT_APPLIED"):
        _effect_event(
            state,
            EventType.EFFECT_RETRY_QUEUED,
            guard_payload(
                lease_token="lease-1",
                reconciliation_ref="reconciliation://unknown/1",
                reconciliation_outcome="UNKNOWN",
            ),
        )

    effect = state.effect("effect-1")
    assert effect.lifecycle is EffectLifecycle.FAILED
    assert effect.lease_token == "lease-1"


def test_timed_out_unknown_attempt_can_later_reconcile_to_success() -> None:
    state = _effect_event(
        _running_effect(),
        EventType.EFFECT_TIMED_OUT,
        {
            "attempt": 1,
            "lease_token": "lease-1",
            "reconciliation_ref": "reconciliation://unknown/1",
        },
    )
    timed_out = state.effect("effect-1")
    assert timed_out.lifecycle is EffectLifecycle.TIMED_OUT
    assert timed_out.lease_token == "lease-1"

    state = _effect_event(
        state,
        EventType.EFFECT_SUCCEEDED,
        {
            "attempt": 1,
            "lease_token": "lease-1",
            "result_ref": "artifact://reconciled/1",
            "result_hash": "d" * 64,
        },
    )
    effect = state.effect("effect-1")
    assert effect.lifecycle is EffectLifecycle.SUCCEEDED
    assert effect.lease_token is None
    assert tuple(outcome.value for outcome in effect.attempts[0].outcome_history) == (
        "RUNNING",
        "TIMED_OUT",
        "SUCCEEDED",
    )
    assert effect.attempts[0].reconciliation_refs == ("reconciliation://unknown/1",)


def test_cancelled_effect_is_absorbing_even_if_a_worker_returns_late() -> None:
    state = _effect_event(
        _running_effect(),
        EventType.EFFECT_CANCELLED,
        cancel_payload("operator cancelled"),
    )
    effect = state.effect("effect-1")
    assert effect.lifecycle is EffectLifecycle.CANCELLED
    assert effect.lease_token is None
    assert effect.attempts[0].outcome.value == "CANCELLED"

    with pytest.raises(InvalidTransitionError):
        _effect_event(
            state,
            EventType.EFFECT_SUCCEEDED,
            {
                "attempt": 1,
                "lease_token": "lease-1",
                "result_ref": "artifact://late/1",
                "result_hash": "e" * 64,
            },
        )


def test_attempt_audit_retains_failure_and_success_results_across_retry() -> None:
    state = _failed_effect()
    state = _effect_event(
        state,
        EventType.EFFECT_RETRY_QUEUED,
        guard_payload(
            lease_token="lease-1",
            reconciliation_ref="reconciliation://not-applied/1",
            reconciliation_outcome="NOT_APPLIED",
        ),
    )
    state = _effect_event(
        state,
        EventType.EFFECT_LEASED,
        {
            "lease_owner": "worker-2",
            "lease_token": "lease-2",
            "lease_expiry": LEASE_TWO_EXPIRY,
        },
    )
    state = _effect_event(
        state,
        EventType.EFFECT_STARTED,
        {"attempt": 2, "lease_token": "lease-2"},
    )
    state = _effect_event(
        state,
        EventType.EFFECT_SUCCEEDED,
        {
            "attempt": 2,
            "lease_token": "lease-2",
            "result_ref": "artifact://result/2",
            "result_hash": "c" * 64,
        },
    )

    first, second = state.effect("effect-1").attempts
    assert first.outcome.value == "FAILED"
    assert first.reason == "worker lost response"
    assert second.outcome.value == "SUCCEEDED"
    assert second.result_ref == "artifact://result/2"
    assert second.result_hash == "c" * 64
