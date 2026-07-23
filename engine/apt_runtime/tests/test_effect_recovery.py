"""Crash-boundary falsifiers for the Slice 2 effect recovery service.

# KG: apt-tpa-legion-engine-canon-2026-06-12
# Design: ADRs/apt-vnext-slice2-effect-runtime-2026-07-14.md
"""

from __future__ import annotations

from pathlib import Path

import pytest

from engine.apt_runtime.application.effect_facts import EffectFactWriter
from engine.apt_runtime.application.effect_recovery import EffectRecovery, RecoveryAction
from engine.apt_runtime.application.effect_runtime_errors import EffectRuntimeStateError
from engine.apt_runtime.domain.effect_runtime import ExecutionOutcome
from engine.apt_runtime.domain.events import EventType
from engine.apt_runtime.domain.state import EffectLifecycle
from engine.apt_runtime.ports.effect_queue import LeaseRequest, LeaseStatus
from engine.apt_runtime.ports.effects import EffectExecutionRequest
from engine.apt_runtime.tests.test_effect_scheduler import (
    CLAIMS,
    DEFAULT_BUDGET,
    INPUT,
    NOW,
    SPEC,
    ReturningExecutor,
    RuntimeHarness,
    _lease,
    _grant,
    _open_runtime,
    _state,
    _cancel_authorization,
)


EXPIRY = "2026-07-14T00:05:00Z"
OBSERVED = "2026-07-14T00:10:00Z"


@pytest.fixture
def runtime(tmp_path: Path):
    opened = _open_runtime(tmp_path / "recovery.sqlite3")
    try:
        yield opened
    finally:
        opened.close()


def _reserve(runtime: RuntimeHarness, token: str = "recovery-lease"):
    grant = _grant()
    return runtime.queue.reserve(
        LeaseRequest(
            outbox=runtime.outbox,
            lease_token=token,
            lease_owner="worker-recovery",
            claimed_at=NOW,
            lease_expiry=EXPIRY,
            resource_claims=CLAIMS,
            budget=DEFAULT_BUDGET,
            grant_ref=grant.grant_ref,
            grant_hash=grant.grant_hash,
            config_version=grant.config_version,
            authorization_ref=grant.authorization_ref,
            authorization_hash=grant.authorization_hash,
        )
    )


def _append(
    runtime: RuntimeHarness,
    event_type: EventType,
    payload: dict[str, object],
    occurred_at: str,
) -> None:
    EffectFactWriter(runtime.store, SPEC).append(
        cycle_id=runtime.outbox.stream_id,
        effect_id=runtime.outbox.effect_id,
        event_type=event_type,
        payload=payload,
        occurred_at=occurred_at,
        actor="worker-recovery",
        correlation_id="recovery-correlation",
        causation_id="recovery-cause",
    )


def _lease_fact(runtime: RuntimeHarness, token: str) -> None:
    record = runtime.queue.load(token)
    assert record is not None
    _append(
        runtime,
        EventType.EFFECT_LEASED,
        {
            "lease_owner": "worker-recovery",
            "lease_token": token,
            "lease_expiry": EXPIRY,
            "grant_ref": record.grant_ref,
            "grant_hash": record.grant_hash,
            "config_version": record.config_version,
            "authorization_ref": record.authorization_ref,
            "authorization_hash": record.authorization_hash,
        },
        NOW,
    )


def _running_projection(runtime: RuntimeHarness, token: str = "recovery-lease"):
    record = _reserve(runtime, token)
    _lease_fact(runtime, token)
    runtime.queue.activate(token, activated_at=NOW)
    _append(
        runtime,
        EventType.EFFECT_STARTED,
        {"attempt": 1, "lease_token": token},
        "2026-07-14T00:01:00Z",
    )
    return runtime.queue.start(
        token,
        lease_owner=record.lease_owner,
        attempt=1,
        started_at="2026-07-14T00:01:00Z",
    )


def _recover(runtime: RuntimeHarness):
    runtime.clock.value = OBSERVED
    return EffectRecovery(
        runtime.store,
        runtime.queue,
        SPEC,
        runtime.clock,
        heartbeat_stale_after_seconds=240,
    ).recover()


def test_orphaned_reserved_claim_is_abandoned_without_external_execution(
    runtime: RuntimeHarness,
) -> None:
    record = _reserve(runtime)
    assert record.status is LeaseStatus.RESERVED
    assert _state(runtime).effect("effect-1").lifecycle is EffectLifecycle.PENDING

    recovered = _recover(runtime)

    assert len(recovered) == 1
    assert recovered[0].action is RecoveryAction.ABANDONED_RESERVATION
    assert recovered[0].lease.status is LeaseStatus.ABANDONED
    assert recovered[0].lease.reason == "orphaned or fenced reservation"
    assert _state(runtime).effect("effect-1").lifecycle is EffectLifecycle.PENDING


def test_durable_lease_before_activation_retries_because_executor_never_started(
    runtime: RuntimeHarness,
) -> None:
    record = _reserve(runtime)
    _lease_fact(runtime, record.lease_token)
    queued = runtime.queue.load(record.lease_token)
    assert queued is not None
    assert queued.status is LeaseStatus.RESERVED
    assert _state(runtime).effect("effect-1").lifecycle is EffectLifecycle.LEASED

    recovered = _recover(runtime)

    assert recovered[0].action is RecoveryAction.RETRY_QUEUED
    assert recovered[0].lease.status is LeaseStatus.ABANDONED
    effect = _state(runtime).effect("effect-1")
    assert effect.lifecycle is EffectLifecycle.PENDING
    assert effect.current_attempt == 0
    event_types = tuple(event.event_type for event in runtime.store.load(runtime.outbox.stream_id))
    assert event_types[-2:] == (EventType.EFFECT_LEASE_EXPIRED, EventType.EFFECT_RETRY_QUEUED)


def test_recovery_resumes_crash_between_preexecution_expiry_and_retry(
    runtime: RuntimeHarness,
) -> None:
    record = _reserve(runtime)
    _lease_fact(runtime, record.lease_token)
    runtime.queue.activate(record.lease_token, activated_at=NOW)
    _append(
        runtime,
        EventType.EFFECT_LEASE_EXPIRED,
        {
            "lease_token": record.lease_token,
            "reconciliation_ref": "recovery://preexecution/crash",
            "expected_heartbeat_at": record.heartbeat_at,
            "expected_lease_expiry": record.lease_expiry,
        },
        OBSERVED,
    )
    assert _state(runtime).effect("effect-1").lifecycle is EffectLifecycle.TIMED_OUT

    recovered = _recover(runtime)

    assert recovered[0].action is RecoveryAction.RETRY_QUEUED
    assert recovered[0].lease.status is LeaseStatus.ABANDONED
    assert _state(runtime).effect("effect-1").lifecycle is EffectLifecycle.PENDING


def test_expired_running_attempt_becomes_timed_out_and_reconciling(
    runtime: RuntimeHarness,
) -> None:
    running = _running_projection(runtime)
    assert running.status is LeaseStatus.RUNNING

    recovered = _recover(runtime)

    assert recovered[0].action is RecoveryAction.MARKED_RECONCILING
    assert recovered[0].lease.status is LeaseStatus.RECONCILING
    effect = _state(runtime).effect("effect-1")
    assert effect.lifecycle is EffectLifecycle.TIMED_OUT
    assert effect.attempts[-1].outcome.value == "TIMED_OUT"
    assert effect.attempts[-1].reconciliation_refs
    assert runtime.store.load(runtime.outbox.stream_id)[-1].event_type is EventType.EFFECT_TIMED_OUT


def test_terminal_canonical_success_closes_crashed_running_projection(
    runtime: RuntimeHarness,
) -> None:
    running = _running_projection(runtime)
    _append(
        runtime,
        EventType.EFFECT_SUCCEEDED,
        {
            "attempt": 1,
            "lease_token": running.lease_token,
            "result_ref": "artifact://result/recovered",
            "result_hash": "d" * 64,
        },
        "2026-07-14T00:02:00Z",
    )
    queued = runtime.queue.load(running.lease_token)
    assert queued is not None
    assert queued.status is LeaseStatus.RUNNING
    assert _state(runtime).effect("effect-1").lifecycle is EffectLifecycle.SUCCEEDED

    recovered = _recover(runtime)

    assert recovered[0].action is RecoveryAction.CLOSED_SUCCEEDED
    assert recovered[0].lease.status is LeaseStatus.SUCCEEDED
    assert _recover(runtime) == ()


def test_heartbeat_is_canonical_and_wrong_owner_cannot_renew(
    runtime: RuntimeHarness,
) -> None:
    lease = runtime.scheduler.lease(
        runtime.outbox,
        lease_owner="worker-1",
        lease_expiry="2026-07-14T00:20:00Z",
        grant=_grant(),
    )
    runtime.clock.value = "2026-07-14T00:10:00Z"
    renewed = runtime.scheduler.heartbeat(
        lease.lease_token,
        lease_owner="worker-1",
        lease_expiry="2026-07-14T00:50:00Z",
    )

    assert renewed.heartbeat_at == runtime.clock.value
    assert _state(runtime).effect("effect-1").heartbeat_at == runtime.clock.value
    with pytest.raises(EffectRuntimeStateError, match="does not hold"):
        runtime.scheduler.heartbeat(
            lease.lease_token,
            lease_owner="stale-worker",
            lease_expiry="2026-07-14T00:55:00Z",
        )


def test_late_success_after_cancellation_cannot_reopen_effect(
    runtime: RuntimeHarness,
) -> None:
    lease = _lease(runtime)

    def cancel_before_return(request: EffectExecutionRequest) -> None:
        runtime.scheduler.cancel(
            request.lease_token,
            authorization=_cancel_authorization(),
        )

    runtime.clock.value = "2026-07-14T00:01:00Z"
    observation = runtime.scheduler.execute(
        lease.lease_token,
        input=INPUT,
        executor=ReturningExecutor(
            ExecutionOutcome.SUCCEEDED,
            before_return=cancel_before_return,
        ),
    )

    queued = runtime.queue.load(lease.lease_token)
    assert queued is not None
    assert observation.lease.status is LeaseStatus.RECONCILING
    assert queued.status is LeaseStatus.RECONCILING
    assert _state(runtime).effect("effect-1").lifecycle is EffectLifecycle.CANCELLED
