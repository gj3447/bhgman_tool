"""Small shared invariants for Slice 2 application services."""

from __future__ import annotations

from datetime import datetime, timedelta

from engine.apt_runtime.domain.canonical import canonical_sha256
from engine.apt_runtime.domain.effect_runtime import (
    EffectExecutionGrant,
    RuntimeBudget,
    RuntimeUsage,
    progress_signature,
)
from engine.apt_runtime.domain.events import EventSchemaError, validate_rfc3339_utc_z
from engine.apt_runtime.domain.state import EffectLifecycle, EffectState
from engine.apt_runtime.ports.effect_queue import LeaseRecord
from engine.apt_runtime.ports.event_store import OutboxRecord

from .effect_runtime_errors import EffectRuntimeStateError


def _verify_outbox_effect(outbox: OutboxRecord, effect: EffectState) -> None:
    expected = {
        "capability": effect.capability,
        "provider": effect.provider,
        "risk_class": effect.risk_class,
        "idempotency_key": effect.idempotency_key,
        "input_ref": effect.input_ref,
        "input_hash": effect.input_hash,
    }
    if dict(outbox.payload) != expected:
        raise EffectRuntimeStateError("outbox payload differs from canonical queued effect")


def _require_canonical_lease(
    effect: EffectState, record: LeaseRecord, lifecycle: EffectLifecycle
) -> None:
    if effect.lifecycle is not lifecycle:
        raise EffectRuntimeStateError(
            f"canonical effect must be {lifecycle.value}, got {effect.lifecycle.value}"
        )
    if effect.lease_token != record.lease_token or effect.lease_owner != record.lease_owner:
        raise EffectRuntimeStateError("queue lease is stale relative to canonical effect fencing")
    _require_canonical_grant_binding(effect, record)


def _require_canonical_grant_binding(effect: EffectState, record: LeaseRecord) -> None:
    if (
        effect.grant_ref != record.grant_ref
        or effect.grant_hash != record.grant_hash
        or effect.authorization_ref != record.authorization_ref
        or effect.authorization_hash != record.authorization_hash
    ):
        raise EffectRuntimeStateError("queue grant binding differs from the canonical lease fact")
    rebuilt = EffectExecutionGrant(
        grant_ref=record.grant_ref,
        cycle_id=record.stream_id,
        effect_id=effect.effect_id,
        capability=effect.capability,
        provider=effect.provider,
        risk_class=effect.risk_class,
        config_version=record.config_version,
        resource_claims=record.resource_claims,
        budget=record.budget,
        authorization_ref=record.authorization_ref,
        authorization_hash=record.authorization_hash,
    )
    if rebuilt.grant_hash != record.grant_hash:
        raise EffectRuntimeStateError("durable queue context does not reproduce its grant hash")


def _same_identity(left: object, right: object) -> bool:
    fields = (
        "cycle_id",
        "effect_id",
        "capability",
        "provider",
        "risk_class",
        "idempotency_key",
        "input_hash",
        "lease_token",
        "attempt",
    )
    return all(getattr(left, field, None) == getattr(right, field, None) for field in fields)


def _provider_matches(adapter: object, effect: EffectState) -> bool:
    return (
        getattr(adapter, "provider", None) == effect.provider
        and effect.capability in getattr(adapter, "capabilities", frozenset())
        and effect.risk_class in getattr(adapter, "risk_classes", frozenset())
    )


def _grant_matches(
    effect: EffectState,
    cycle_id: str,
    config_version: str,
    grant: EffectExecutionGrant,
) -> bool:
    return (
        grant.cycle_id == cycle_id
        and grant.effect_id == effect.effect_id
        and grant.capability == effect.capability
        and grant.provider == effect.provider
        and grant.risk_class == effect.risk_class
        and grant.config_version == config_version
    )


def _correlation_id(record: LeaseRecord) -> str:
    return f"effect-runtime:{record.stream_id}:{record.effect_id}"


def _reconciliation_ref(record: LeaseRecord, attempt: int, evidence_refs: tuple[str, ...]) -> str:
    if evidence_refs:
        return evidence_refs[0]
    digest = canonical_sha256(
        {
            "attempt": attempt,
            "effect_id": record.effect_id,
            "lease_token": record.lease_token,
            "stream_id": record.stream_id,
        }
    )
    return f"reconciliation://unknown/{digest}"


def _unknown_usage_delta(record: LeaseRecord, attempt: int, observation: str) -> RuntimeUsage:
    return RuntimeUsage(
        attempts=0,
        progress_signature=progress_signature(
            {
                "effect_id": record.effect_id,
                "observation": observation,
            }
        ),
    )


def _execution_usage_delta(usage: RuntimeUsage) -> RuntimeUsage:
    return RuntimeUsage(
        attempts=0,
        runtime_seconds=usage.runtime_seconds,
        cost_units=usage.cost_units,
        no_progress=usage.no_progress,
        reconciliation_probes=usage.reconciliation_probes,
        progress_signature=usage.progress_signature,
    )


def _with_canonical_attempts(usage: RuntimeUsage, attempts: int) -> RuntimeUsage:
    if usage.attempts >= attempts:
        return usage
    return RuntimeUsage(
        attempts=attempts,
        runtime_seconds=usage.runtime_seconds,
        cost_units=usage.cost_units,
        no_progress=usage.no_progress,
        reconciliation_probes=usage.reconciliation_probes,
        progress_signature=usage.progress_signature,
    )


def _require_live_lease(record: LeaseRecord, observed_at: str, operation: str) -> None:
    observed = _require_queue_chronology(record, observed_at, operation)
    heartbeat = datetime.fromisoformat(record.heartbeat_at[:-1] + "+00:00")
    expiry = datetime.fromisoformat(record.lease_expiry[:-1] + "+00:00")
    if operation == "heartbeat" and observed <= heartbeat:
        raise EffectRuntimeStateError("cannot heartbeat: heartbeat time must move forward")
    if operation != "heartbeat" and observed < heartbeat:
        raise EffectRuntimeStateError(
            f"cannot {operation}: clock moved before the durable heartbeat"
        )
    if observed >= expiry:
        raise EffectRuntimeStateError(
            f"cannot {operation}: lease expired before canonical fact commit"
        )


def _require_queue_chronology(record: LeaseRecord, observed_at: str, operation: str) -> datetime:
    try:
        validate_rfc3339_utc_z("observed_at", observed_at)
    except EventSchemaError as exc:
        raise EffectRuntimeStateError(str(exc)) from exc
    observed = datetime.fromisoformat(observed_at[:-1] + "+00:00")
    claimed = datetime.fromisoformat(record.claimed_at[:-1] + "+00:00")
    heartbeat = datetime.fromisoformat(record.heartbeat_at[:-1] + "+00:00")
    activated = (
        None
        if record.activated_at is None
        else datetime.fromisoformat(record.activated_at[:-1] + "+00:00")
    )
    if (
        observed < claimed
        or observed < heartbeat
        or (activated is not None and observed < activated)
    ):
        raise EffectRuntimeStateError(
            f"cannot {operation}: clock moved before the durable lease chronology"
        )
    return observed


def _lease_is_expired(record: LeaseRecord, observed_at: str) -> bool:
    validate_rfc3339_utc_z("observed_at", observed_at)
    observed = datetime.fromisoformat(observed_at[:-1] + "+00:00")
    expiry = datetime.fromisoformat(record.lease_expiry[:-1] + "+00:00")
    return observed >= expiry


def _require_initial_deadline(claimed_at: str, lease_expiry: str, budget: RuntimeBudget) -> None:
    try:
        validate_rfc3339_utc_z("claimed_at", claimed_at)
        validate_rfc3339_utc_z("lease_expiry", lease_expiry)
    except EventSchemaError as exc:
        raise EffectRuntimeStateError(str(exc)) from exc
    claimed = datetime.fromisoformat(claimed_at[:-1] + "+00:00")
    expiry = datetime.fromisoformat(lease_expiry[:-1] + "+00:00")
    if expiry > claimed + timedelta(seconds=budget.max_runtime_seconds):
        raise EffectRuntimeStateError("lease expiry exceeds the immutable runtime deadline")


def _require_heartbeat_extension(
    record: LeaseRecord,
    *,
    heartbeat_at: str,
    lease_expiry: str,
) -> None:
    try:
        validate_rfc3339_utc_z("lease_expiry", lease_expiry)
    except EventSchemaError as exc:
        raise EffectRuntimeStateError(str(exc)) from exc
    heartbeat = datetime.fromisoformat(heartbeat_at[:-1] + "+00:00")
    current_expiry = datetime.fromisoformat(record.lease_expiry[:-1] + "+00:00")
    candidate = datetime.fromisoformat(lease_expiry[:-1] + "+00:00")
    claimed = datetime.fromisoformat(record.claimed_at[:-1] + "+00:00")
    if candidate <= current_expiry or candidate <= heartbeat:
        raise EffectRuntimeStateError("heartbeat lease_expiry must extend the current live lease")
    if candidate > claimed + timedelta(seconds=record.budget.max_runtime_seconds):
        raise EffectRuntimeStateError("heartbeat lease_expiry exceeds the runtime deadline")


__all__ = []
