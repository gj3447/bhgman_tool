"""Typed journal-state replay shared by SQLite and PostgreSQL queues.

# KG: apt-tpa-legion-engine-canon-2026-06-12
# Design: ADRs/apt-vnext-slice2-effect-runtime-2026-07-14.md
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import fields
from datetime import datetime

from engine.apt_runtime.domain.canonical import (
    CanonicalEncodingError,
    canonical_json_bytes,
    canonical_sha256,
)
from engine.apt_runtime.domain.effect_runtime import RuntimeUsage
from engine.apt_runtime.ports.effect_queue import (
    EffectQueueCorruption,
    LeaseRecord,
    LeaseStatus,
    ReconciliationProbePermitState,
    TERMINAL_LEASE_STATUSES,
)

from ._effect_queue_codec import decode_budget, decode_claims, decode_usage, lease_from_row


STATE_ACTIONS = frozenset(
    {
        "RESERVED",
        "ACTIVATED",
        "HEARTBEAT_RECORDED",
        "STARTED",
        "RECONCILING",
        "PROBE_ACQUIRED",
        "PROBE_CONCLUDED",
        "FINISHED",
    }
)
JOURNAL_ACTIONS = STATE_ACTIONS | {"USAGE_RECORDED"}
_LEASE_FIELDS = frozenset(field.name for field in fields(LeaseRecord))
_STATE_MUTATIONS = {
    "ACTIVATED": frozenset({"status", "activated_at", "heartbeat_at"}),
    "HEARTBEAT_RECORDED": frozenset({"heartbeat_at", "lease_expiry"}),
    "STARTED": frozenset({"status", "heartbeat_at", "attempt"}),
    "RECONCILING": frozenset({"status", "probe_permit", "reconciliation_ref", "reason"}),
    "PROBE_ACQUIRED": frozenset({"probe_generation", "probe_permit"}),
    "PROBE_CONCLUDED": frozenset({"probe_permit", "reconciliation_ref", "reason"}),
    "FINISHED": frozenset(
        {"status", "probe_permit", "reconciliation_ref", "reason", "completed_at"}
    ),
}
_FINISH_STEPS = {
    LeaseStatus.RESERVED: frozenset({LeaseStatus.ABANDONED, LeaseStatus.CANCELLED}),
    LeaseStatus.ACTIVE: frozenset(
        {LeaseStatus.ABANDONED, LeaseStatus.CANCELLED, LeaseStatus.FAILED}
    ),
    LeaseStatus.RUNNING: frozenset(
        {LeaseStatus.SUCCEEDED, LeaseStatus.FAILED, LeaseStatus.CANCELLED}
    ),
    LeaseStatus.RECONCILING: TERMINAL_LEASE_STATUSES,
}


def _instant(value: str) -> datetime:
    return datetime.fromisoformat(value[:-1] + "+00:00")


def _permit_columns(permit: object) -> dict[str, object]:
    if permit is None:
        return {
            "probe_token": None,
            "probe_state": None,
            "probe_acquired_at": None,
            "probe_expires_at": None,
            "probe_concluded_at": None,
            "probe_conclusion_json": None,
            "probe_conclusion_hash": None,
        }
    if not isinstance(permit, Mapping):
        raise EffectQueueCorruption("lease probe_permit projection is invalid")
    conclusion = permit.get("conclusion")
    return {
        "probe_token": permit.get("permit_token"),
        "probe_state": permit.get("state"),
        "probe_acquired_at": permit.get("acquired_at"),
        "probe_expires_at": permit.get("expires_at"),
        "probe_concluded_at": permit.get("concluded_at"),
        "probe_conclusion_json": None if conclusion is None else canonical_json_bytes(conclusion),
        "probe_conclusion_hash": None if conclusion is None else canonical_sha256(conclusion),
    }


def _lease_projection(value: object) -> LeaseRecord:
    if not isinstance(value, Mapping) or set(value) != _LEASE_FIELDS:
        raise EffectQueueCorruption("lease state journal has an incompatible field set")
    try:
        claims_blob = canonical_json_bytes(value["resource_claims"])
        budget_blob = canonical_json_bytes(value["budget"])
        claims = decode_claims(claims_blob, canonical_sha256(value["resource_claims"]))
        row = {
            **value,
            **_permit_columns(value["probe_permit"]),
            "claims_json": claims_blob,
            "claims_hash": canonical_sha256(value["resource_claims"]),
            "budget_json": budget_blob,
            "budget_hash": canonical_sha256(value["budget"]),
        }
        decode_budget(budget_blob, row["budget_hash"])
        record = lease_from_row(row, claims)
    except EffectQueueCorruption:
        raise
    except (CanonicalEncodingError, KeyError, TypeError, ValueError, RecursionError) as exc:
        raise EffectQueueCorruption(f"lease state journal is invalid: {exc}") from exc
    if canonical_json_bytes(record) != canonical_json_bytes(value):
        raise EffectQueueCorruption("lease state journal projection is not normalized")
    return record


def _usage_projection(value: object, location: str) -> RuntimeUsage:
    try:
        blob = canonical_json_bytes(value)
        usage = decode_usage(blob, canonical_sha256(value))
    except EffectQueueCorruption:
        raise
    except (CanonicalEncodingError, TypeError, ValueError, RecursionError) as exc:
        raise EffectQueueCorruption(f"{location} is invalid: {exc}") from exc
    if canonical_json_bytes(usage) != blob:
        raise EffectQueueCorruption(f"{location} is not normalized")
    return usage


def validate_usage_detail(document: object) -> None:
    """Validate an exact typed usage delta and accumulated snapshot."""

    if not isinstance(document, Mapping) or set(document) != {"delta", "usage"}:
        raise EffectQueueCorruption("usage journal detail must contain only delta and usage")
    _usage_projection(document["delta"], "usage journal delta")
    _usage_projection(document["usage"], "usage journal snapshot")


def _assert_carry_forward(action: str, previous: LeaseRecord, current: LeaseRecord) -> None:
    allowed = _STATE_MUTATIONS[action]
    for field in fields(LeaseRecord):
        if field.name in allowed:
            continue
        if getattr(previous, field.name) != getattr(current, field.name):
            raise EffectQueueCorruption(f"{action} journal illegally rewrites lease.{field.name}")


def _reserved(previous: LeaseRecord | None, current: LeaseRecord, _: str) -> bool:
    return previous is None and current.status is LeaseStatus.RESERVED


def _activated(previous: LeaseRecord | None, current: LeaseRecord, _: str) -> bool:
    return (
        previous is not None
        and previous.status is LeaseStatus.RESERVED
        and current.status is LeaseStatus.ACTIVE
    )


def _heartbeat(previous: LeaseRecord | None, current: LeaseRecord, _: str) -> bool:
    if previous is None or previous.status not in {LeaseStatus.ACTIVE, LeaseStatus.RUNNING}:
        return False
    if current.status is not previous.status:
        return False
    return _instant(current.heartbeat_at) > _instant(previous.heartbeat_at) and _instant(
        current.lease_expiry
    ) > _instant(previous.lease_expiry)


def _started(previous: LeaseRecord | None, current: LeaseRecord, _: str) -> bool:
    return (
        previous is not None
        and previous.status is LeaseStatus.ACTIVE
        and current.status is LeaseStatus.RUNNING
    )


def _reconciling(previous: LeaseRecord | None, current: LeaseRecord, _: str) -> bool:
    if previous is None or previous.status not in {
        LeaseStatus.ACTIVE,
        LeaseStatus.RUNNING,
        LeaseStatus.RECONCILING,
    }:
        return False
    if current.status is not LeaseStatus.RECONCILING or current.probe_permit is not None:
        return False
    held = previous.probe_permit
    return held is None or held.state is ReconciliationProbePermitState.CONCLUDED


def _probe_acquired(previous: LeaseRecord | None, current: LeaseRecord, at: str) -> bool:
    if previous is None or previous.status is not LeaseStatus.RECONCILING:
        return False
    permit = current.probe_permit
    if permit is None or permit.state is not ReconciliationProbePermitState.ACTIVE:
        return False
    if current.status is not LeaseStatus.RECONCILING:
        return False
    if current.probe_generation != previous.probe_generation + 1:
        return False
    prior = previous.probe_permit
    return prior is None or (
        prior.state is ReconciliationProbePermitState.ACTIVE
        and _instant(at) >= _instant(prior.expires_at)
    )


def _probe_concluded(previous: LeaseRecord | None, current: LeaseRecord, _: str) -> bool:
    if previous is None or previous.status is not LeaseStatus.RECONCILING:
        return False
    prior = previous.probe_permit
    sealed = current.probe_permit
    if prior is None or sealed is None:
        return False
    if prior.state is not ReconciliationProbePermitState.ACTIVE:
        return False
    return (
        current.status is LeaseStatus.RECONCILING
        and sealed.state is ReconciliationProbePermitState.CONCLUDED
        and sealed.permit_token == prior.permit_token
        and sealed.generation == prior.generation
        and sealed.acquired_at == prior.acquired_at
    )


def _finished(previous: LeaseRecord | None, current: LeaseRecord, _: str) -> bool:
    if previous is None or current.status not in _FINISH_STEPS.get(previous.status, frozenset()):
        return False
    held = previous.probe_permit
    return current.probe_permit is None and (
        held is None or held.state is ReconciliationProbePermitState.CONCLUDED
    )


_STEP_VALIDATORS: dict[str, Callable[[LeaseRecord | None, LeaseRecord, str], bool]] = {
    "RESERVED": _reserved,
    "ACTIVATED": _activated,
    "HEARTBEAT_RECORDED": _heartbeat,
    "STARTED": _started,
    "RECONCILING": _reconciling,
    "PROBE_ACQUIRED": _probe_acquired,
    "PROBE_CONCLUDED": _probe_concluded,
    "FINISHED": _finished,
}
_TIMESTAMP_FIELDS = {
    "RESERVED": "claimed_at",
    "ACTIVATED": "activated_at",
    "HEARTBEAT_RECORDED": "heartbeat_at",
    "STARTED": "heartbeat_at",
    "PROBE_ACQUIRED": "probe_permit.acquired_at",
    "PROBE_CONCLUDED": "probe_permit.concluded_at",
    "FINISHED": "completed_at",
}


def _state_timestamp(action: str, current: LeaseRecord) -> object:
    field = _TIMESTAMP_FIELDS.get(action)
    if field is None:
        return None
    if not field.startswith("probe_permit."):
        return getattr(current, field)
    if current.probe_permit is None:  # pragma: no cover - validator rejects first
        return None
    return getattr(current.probe_permit, field.split(".")[1])


def replay_state_step(
    action: object,
    document: object,
    previous: LeaseRecord | None,
    occurred_at: str,
) -> LeaseRecord:
    """Replay one action with exact transition, carry-forward, and time rules."""

    if not isinstance(document, Mapping) or set(document) != {"lease"}:
        raise EffectQueueCorruption("lease state journal detail must contain only lease")
    if not isinstance(action, str) or action not in _STEP_VALIDATORS:
        raise EffectQueueCorruption("effect lease journal contains an unknown state action")
    current = _lease_projection(document["lease"])
    if not _STEP_VALIDATORS[action](previous, current, occurred_at):
        raise EffectQueueCorruption("effect lease journal contains an illegal lease journal step")
    if previous is not None:
        _assert_carry_forward(action, previous, current)
    expected_at = _state_timestamp(action, current)
    if expected_at is not None and expected_at != occurred_at:
        raise EffectQueueCorruption(f"{action} journal time differs from lease state")
    if action == "RESERVED" and current.heartbeat_at != current.claimed_at:
        raise EffectQueueCorruption("RESERVED journal must anchor heartbeat_at to claimed_at")
    if action == "ACTIVATED" and current.heartbeat_at != occurred_at:
        raise EffectQueueCorruption("ACTIVATED journal must advance heartbeat_at")
    return current


__all__ = [
    "JOURNAL_ACTIONS",
    "STATE_ACTIONS",
    "replay_state_step",
    "validate_usage_detail",
]
