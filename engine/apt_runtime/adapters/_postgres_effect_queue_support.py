"""Shared deterministic policy helpers for the PostgreSQL effect queue."""

from __future__ import annotations

import hashlib
from datetime import datetime

from engine.apt_runtime.domain.canonical import MAX_SIGNED_64, normalize_text
from engine.apt_runtime.domain.events import EventSchemaError, validate_rfc3339_utc_z
from engine.apt_runtime.ports.effect_queue import (
    LeaseConflict,
    LeaseRecord,
    LeaseStatus,
    ReconciliationProbePermit,
    ReconciliationProbePermitState,
    TERMINAL_LEASE_STATUSES,
)


NONTERMINAL_VALUES = tuple(
    status.value for status in LeaseStatus if status not in TERMINAL_LEASE_STATUSES
)
JOURNAL_ACTIONS = frozenset(
    {
        "RESERVED",
        "ACTIVATED",
        "HEARTBEAT_RECORDED",
        "STARTED",
        "RECONCILING",
        "PROBE_ACQUIRED",
        "PROBE_CONCLUDED",
        "USAGE_RECORDED",
        "FINISHED",
    }
)
LATEST_ACTIONS = {
    LeaseStatus.RESERVED: frozenset({"RESERVED"}),
    LeaseStatus.ACTIVE: frozenset({"ACTIVATED", "HEARTBEAT_RECORDED"}),
    LeaseStatus.RUNNING: frozenset({"STARTED", "HEARTBEAT_RECORDED"}),
    LeaseStatus.RECONCILING: frozenset({"RECONCILING", "PROBE_ACQUIRED", "PROBE_CONCLUDED"}),
    LeaseStatus.SUCCEEDED: frozenset({"FINISHED"}),
    LeaseStatus.FAILED: frozenset({"FINISHED"}),
    LeaseStatus.CANCELLED: frozenset({"FINISHED"}),
    LeaseStatus.ABANDONED: frozenset({"FINISHED"}),
}
FINISH_TRANSITIONS = {
    LeaseStatus.RESERVED: frozenset({LeaseStatus.CANCELLED, LeaseStatus.ABANDONED}),
    LeaseStatus.ACTIVE: frozenset(
        {LeaseStatus.FAILED, LeaseStatus.CANCELLED, LeaseStatus.ABANDONED}
    ),
    LeaseStatus.RUNNING: frozenset(
        {LeaseStatus.SUCCEEDED, LeaseStatus.FAILED, LeaseStatus.CANCELLED}
    ),
    LeaseStatus.RECONCILING: frozenset(
        {
            LeaseStatus.SUCCEEDED,
            LeaseStatus.FAILED,
            LeaseStatus.CANCELLED,
            LeaseStatus.ABANDONED,
        }
    ),
}


def text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")
    normalized = normalize_text(value)
    if "\x00" in normalized:
        raise ValueError(f"{name} cannot contain U+0000")
    return normalized


def timestamp(name: str, value: object) -> str:
    value = text(name, value)
    try:
        validate_rfc3339_utc_z(name, value)
    except EventSchemaError as exc:
        raise ValueError(str(exc)) from exc
    return value


def instant(value: str) -> datetime:
    return datetime.fromisoformat(value[:-1] + "+00:00")


def positive_attempt(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= MAX_SIGNED_64:
        raise ValueError("attempt must be a signed 64-bit positive integer")
    return value


def require_concluded_permit(
    current: LeaseRecord,
    supplied: ReconciliationProbePermit | None,
) -> None:
    """Allow a mutation to clear only its exact sealed permit generation."""

    held = current.probe_permit
    if held is None:
        if supplied is not None:
            raise LeaseConflict("supplied probe permit is no longer current")
        return
    if supplied != held or held.state is not ReconciliationProbePermitState.CONCLUDED:
        raise LeaseConflict("active or stale probe generation cannot mutate the lease")


def lock_key(namespace: str, identity: str) -> int:
    digest = hashlib.sha256(f"{namespace}\x00{identity}".encode()).digest()[:8]
    return int.from_bytes(digest, byteorder="big", signed=True)


__all__ = [
    "FINISH_TRANSITIONS",
    "JOURNAL_ACTIONS",
    "LATEST_ACTIONS",
    "NONTERMINAL_VALUES",
    "instant",
    "lock_key",
    "positive_attempt",
    "require_concluded_permit",
    "text",
    "timestamp",
]
