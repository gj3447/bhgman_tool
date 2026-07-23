"""Pure Slice 2 effect lease, attempt, and reconciliation state updates.

The parent reducer owns envelope/spec/work-generation validation. This module
owns the smaller effect-internal fencing contract so the aggregate reducer does
not become a second fat-file implementation of the effect FSM.

# KG: apt-tpa-legion-engine-canon-2026-06-12
# Design: SYMPOSIUM/THEORY/APT/vnext/APT_ENGINE_FSM_DESIGN_2026-07-13.md Slice 2
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from typing import Mapping

from .events import EventEnvelope, EventType
from .state import (
    EffectAttemptOutcome,
    EffectAttemptRecord,
    EffectLifecycle,
    EffectState,
)


class EffectFenceViolation(ValueError):
    """A worker fact does not match the currently fenced lease/attempt."""


class EffectRetryRejected(ValueError):
    """A retry was requested without a NOT_APPLIED reconciliation result."""


def _required_string(payload: Mapping[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise EffectFenceViolation(f"effect payload field {key!r} must be a non-empty string")
    return value


def _audit_append(values: tuple[str, ...], value: str) -> tuple[str, ...]:
    return values if value in values else (*values, value)


def _timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value[:-1] + "+00:00")


def _require_forward_timestamp(name: str, candidate: str, baseline: str) -> None:
    if _timestamp(candidate) <= _timestamp(baseline):
        raise EffectFenceViolation(f"{name} must move strictly forward")


def _require_not_before(name: str, candidate: str, baseline: str) -> None:
    if _timestamp(candidate) < _timestamp(baseline):
        raise EffectFenceViolation(f"{name} cannot move backwards")


def _require_active_lease_token(effect: EffectState, event: EventEnvelope) -> str:
    token = _required_string(event.payload, "lease_token")
    if effect.lease_token is None or token != effect.lease_token:
        raise EffectFenceViolation("effect fact carries a stale lease token")
    return token


def _require_active_attempt(effect: EffectState, event: EventEnvelope) -> EffectAttemptRecord:
    token = _require_active_lease_token(effect, event)
    raw_attempt = event.payload.get("attempt")
    if raw_attempt != effect.current_attempt or not effect.attempts:
        raise EffectFenceViolation("effect fact carries a stale attempt number")
    attempt = effect.attempts[-1]
    if attempt.lease_token != token:
        raise EffectFenceViolation("effect attempt is not bound to the active lease")
    return attempt


def _lease_effect(
    effect: EffectState, event: EventEnvelope, lifecycle: EffectLifecycle
) -> EffectState:
    owner = _required_string(event.payload, "lease_owner")
    token = _required_string(event.payload, "lease_token")
    expiry = _required_string(event.payload, "lease_expiry")
    if token in effect.lease_token_history:
        raise EffectFenceViolation("effect lease token cannot be reused")
    supplied_grant = (
        _required_string(event.payload, "grant_ref"),
        _required_string(event.payload, "grant_hash"),
        _required_string(event.payload, "authorization_ref"),
        _required_string(event.payload, "authorization_hash"),
    )
    retained_grant = (
        effect.grant_ref,
        effect.grant_hash,
        effect.authorization_ref,
        effect.authorization_hash,
    )
    if effect.grant_ref is not None and retained_grant != supplied_grant:
        raise EffectFenceViolation("effect retry cannot change its canonical execution grant")
    if _timestamp(expiry) <= _timestamp(event.created_at):
        raise EffectFenceViolation("lease_expiry must be later than the lease fact")
    return replace(
        effect,
        lifecycle=lifecycle,
        lease_owner=owner,
        lease_token=token,
        lease_expiry=expiry,
        heartbeat_at=event.created_at,
        grant_ref=supplied_grant[0],
        grant_hash=supplied_grant[1],
        authorization_ref=supplied_grant[2],
        authorization_hash=supplied_grant[3],
        lease_token_history=(*effect.lease_token_history, token),
    )


def _heartbeat_effect(
    effect: EffectState, event: EventEnvelope, lifecycle: EffectLifecycle
) -> EffectState:
    _require_active_lease_token(effect, event)
    owner = _required_string(event.payload, "lease_owner")
    heartbeat_at = _required_string(event.payload, "heartbeat_at")
    expiry = _required_string(event.payload, "lease_expiry")
    if owner != effect.lease_owner:
        raise EffectFenceViolation("effect heartbeat carries a stale lease owner")
    if heartbeat_at != event.created_at:
        raise EffectFenceViolation("heartbeat_at must equal the event created_at")
    assert effect.heartbeat_at is not None
    assert effect.lease_expiry is not None
    _require_forward_timestamp("heartbeat_at", heartbeat_at, effect.heartbeat_at)
    _require_forward_timestamp("lease_expiry", expiry, effect.lease_expiry)
    if _timestamp(expiry) <= _timestamp(heartbeat_at):
        raise EffectFenceViolation("lease_expiry must remain after heartbeat_at")
    return replace(
        effect,
        lifecycle=lifecycle,
        heartbeat_at=heartbeat_at,
        lease_expiry=expiry,
    )


def _start_effect(
    effect: EffectState, event: EventEnvelope, lifecycle: EffectLifecycle
) -> EffectState:
    token = _require_active_lease_token(effect, event)
    raw_attempt = event.payload.get("attempt")
    expected_attempt = effect.current_attempt + 1
    if raw_attempt != expected_attempt:
        raise EffectFenceViolation(
            f"effect start must name the next monotonic attempt {expected_attempt}"
        )
    assert isinstance(raw_attempt, int)
    assert effect.lease_owner is not None
    assert effect.heartbeat_at is not None
    assert effect.lease_expiry is not None
    _require_not_before("effect start", event.created_at, effect.heartbeat_at)
    if _timestamp(event.created_at) >= _timestamp(effect.lease_expiry):
        raise EffectFenceViolation("effect cannot start at or after lease expiry")
    attempt = EffectAttemptRecord(
        attempt=raw_attempt,
        lease_token=token,
        lease_owner=effect.lease_owner,
        started_at=event.created_at,
    )
    return replace(
        effect,
        lifecycle=lifecycle,
        heartbeat_at=event.created_at,
        current_attempt=raw_attempt,
        attempts=(*effect.attempts, attempt),
    )


def _finish_attempt(
    effect: EffectState,
    event: EventEnvelope,
    outcome: EffectAttemptOutcome,
    *,
    result_ref: str | None = None,
    result_hash: str | None = None,
    reason: str | None = None,
    reconciliation_ref: str | None = None,
) -> tuple[EffectAttemptRecord, tuple[str, ...], tuple[str, ...]]:
    current = _require_active_attempt(effect, event)
    _require_not_before("effect outcome", event.created_at, current.started_at)
    if current.completed_at is not None:
        _require_not_before("reconciled effect outcome", event.created_at, current.completed_at)
    outcomes = (*current.outcome_history, outcome)
    reasons = current.reasons if reason is None else (*current.reasons, reason)
    reconciliations = (
        current.reconciliation_refs
        if reconciliation_ref is None
        else _audit_append(current.reconciliation_refs, reconciliation_ref)
    )
    updated = replace(
        current,
        outcome_history=outcomes,
        completed_at=event.created_at,
        result_ref=result_ref,
        result_hash=result_hash,
        reasons=reasons,
        reconciliation_refs=reconciliations,
    )
    effect_reasons = effect.reasons if reason is None else (*effect.reasons, reason)
    effect_reconciliations = (
        effect.reconciliation_refs
        if reconciliation_ref is None
        else _audit_append(effect.reconciliation_refs, reconciliation_ref)
    )
    return updated, effect_reasons, effect_reconciliations


def _succeed_effect(
    effect: EffectState, event: EventEnvelope, lifecycle: EffectLifecycle
) -> EffectState:
    result_ref = _required_string(event.payload, "result_ref")
    result_hash = _required_string(event.payload, "result_hash")
    attempt, reasons, reconciliations = _finish_attempt(
        effect,
        event,
        EffectAttemptOutcome.SUCCEEDED,
        result_ref=result_ref,
        result_hash=result_hash,
    )
    return replace(
        effect,
        lifecycle=lifecycle,
        attempts=(*effect.attempts[:-1], attempt),
        result_ref=result_ref,
        result_hash=result_hash,
        lease_owner=None,
        lease_token=None,
        lease_expiry=None,
        heartbeat_at=None,
        reasons=reasons,
        reconciliation_refs=reconciliations,
    )


def _fail_effect(
    effect: EffectState, event: EventEnvelope, lifecycle: EffectLifecycle
) -> EffectState:
    reason = _required_string(event.payload, "reason")
    attempt, reasons, reconciliations = _finish_attempt(
        effect, event, EffectAttemptOutcome.FAILED, reason=reason
    )
    return replace(
        effect,
        lifecycle=lifecycle,
        attempts=(*effect.attempts[:-1], attempt),
        reasons=reasons,
        reconciliation_refs=reconciliations,
    )


def _expire_lease(
    effect: EffectState, event: EventEnvelope, lifecycle: EffectLifecycle
) -> EffectState:
    _require_active_lease_token(effect, event)
    assert effect.heartbeat_at is not None
    assert effect.lease_expiry is not None
    if (
        _required_string(event.payload, "expected_heartbeat_at") != effect.heartbeat_at
        or _required_string(event.payload, "expected_lease_expiry") != effect.lease_expiry
    ):
        raise EffectFenceViolation("lease expiry fact was decided from a stale heartbeat")
    _require_not_before("lease expiry fact", event.created_at, effect.heartbeat_at)
    reconciliation_ref = _required_string(event.payload, "reconciliation_ref")
    return replace(
        effect,
        lifecycle=lifecycle,
        reconciliation_refs=_audit_append(effect.reconciliation_refs, reconciliation_ref),
    )


def _timeout_effect(
    effect: EffectState, event: EventEnvelope, lifecycle: EffectLifecycle
) -> EffectState:
    assert effect.heartbeat_at is not None
    assert effect.lease_expiry is not None
    if (
        _required_string(event.payload, "expected_heartbeat_at") != effect.heartbeat_at
        or _required_string(event.payload, "expected_lease_expiry") != effect.lease_expiry
    ):
        raise EffectFenceViolation("effect timeout was decided from a stale heartbeat")
    reconciliation_ref = _required_string(event.payload, "reconciliation_ref")
    attempt, reasons, reconciliations = _finish_attempt(
        effect,
        event,
        EffectAttemptOutcome.TIMED_OUT,
        reconciliation_ref=reconciliation_ref,
    )
    return replace(
        effect,
        lifecycle=lifecycle,
        attempts=(*effect.attempts[:-1], attempt),
        reasons=reasons,
        reconciliation_refs=reconciliations,
    )


def _retry_effect(
    effect: EffectState, event: EventEnvelope, lifecycle: EffectLifecycle
) -> EffectState:
    _require_active_lease_token(effect, event)
    outcome = _required_string(event.payload, "reconciliation_outcome")
    if outcome != "NOT_APPLIED":
        raise EffectRetryRejected("effect retry requires reconciliation_outcome NOT_APPLIED")
    reconciliation_ref = _required_string(event.payload, "reconciliation_ref")
    if effect.attempts and effect.attempts[-1].completed_at is not None:
        _require_not_before(
            "effect retry", event.created_at, effect.attempts[-1].completed_at or ""
        )
    return replace(
        effect,
        lifecycle=lifecycle,
        lease_owner=None,
        lease_token=None,
        lease_expiry=None,
        heartbeat_at=None,
        reconciliation_refs=_audit_append(effect.reconciliation_refs, reconciliation_ref),
    )


def _cancel_effect(
    effect: EffectState, event: EventEnvelope, lifecycle: EffectLifecycle
) -> EffectState:
    reason = _required_string(event.payload, "reason")
    attempts = effect.attempts
    if effect.heartbeat_at is not None:
        _require_not_before("effect cancellation", event.created_at, effect.heartbeat_at)
    if effect.attempts:
        current = effect.attempts[-1]
        _require_not_before("effect cancellation", event.created_at, current.started_at)
        if current.completed_at is not None:
            _require_not_before("effect cancellation", event.created_at, current.completed_at)
    if effect.lifecycle is EffectLifecycle.RUNNING:
        current = effect.attempts[-1]
        cancelled = replace(
            current,
            outcome_history=(*current.outcome_history, EffectAttemptOutcome.CANCELLED),
            completed_at=event.created_at,
            reasons=(*current.reasons, reason),
        )
        attempts = (*effect.attempts[:-1], cancelled)
    return replace(
        effect,
        lifecycle=lifecycle,
        attempts=attempts,
        lease_owner=None,
        lease_token=None,
        lease_expiry=None,
        heartbeat_at=None,
        reasons=(*effect.reasons, reason),
    )


def reduce_effect_state(
    effect: EffectState, event: EventEnvelope, lifecycle: EffectLifecycle
) -> EffectState:
    """Apply an already-authorized effect transition with lease fencing."""

    handlers = {
        EventType.EFFECT_LEASED: _lease_effect,
        EventType.EFFECT_HEARTBEAT_RECORDED: _heartbeat_effect,
        EventType.EFFECT_STARTED: _start_effect,
        EventType.EFFECT_SUCCEEDED: _succeed_effect,
        EventType.EFFECT_FAILED: _fail_effect,
        EventType.EFFECT_LEASE_EXPIRED: _expire_lease,
        EventType.EFFECT_TIMED_OUT: _timeout_effect,
        EventType.EFFECT_RETRY_QUEUED: _retry_effect,
        EventType.EFFECT_CANCELLED: _cancel_effect,
    }
    handler = handlers.get(event.event_type)
    if handler is None:
        return replace(effect, lifecycle=lifecycle)
    return handler(effect, event, lifecycle)


__all__ = [
    "EffectFenceViolation",
    "EffectRetryRejected",
    "reduce_effect_state",
]
