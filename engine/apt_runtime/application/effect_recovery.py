"""Crash-recovery convergence for Slice 2 effect leases.

Recovery compares the operational queue with replayed canonical state.  It can
repair a projection, abandon a pre-event reservation, or move an expired lease
to reconciliation, but it never calls an external executor or guesses that an
unknown write was not applied.

# KG: apt-tpa-legion-engine-canon-2026-06-12
# Design: ADRs/apt-vnext-slice2-effect-runtime-2026-07-14.md
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

from engine.apt_runtime.domain.canonical import canonical_sha256
from engine.apt_runtime.domain.effect_runtime import ReconciliationOutcome
from engine.apt_runtime.domain.events import (
    EventSchemaError,
    EventType,
    GuardResult,
    validate_rfc3339_utc_z,
)
from engine.apt_runtime.domain.fsm_spec import FsmSpec
from engine.apt_runtime.domain.reducer import replay
from engine.apt_runtime.domain.state import EffectLifecycle, EffectState
from engine.apt_runtime.ports.effect_queue import (
    EffectQueue,
    LeaseRecord,
    LeaseStatus,
    ReconciliationProbePermitState,
)
from engine.apt_runtime.ports.effects import Clock
from engine.apt_runtime.ports.event_store import EventStore

from ._effect_runtime_support import (
    _correlation_id,
    _require_canonical_grant_binding,
)
from .effect_facts import EffectFactWriter
from .effect_runtime_errors import EffectRuntimeStateError, EffectSchedulerError


class RecoveryAction(str, Enum):
    """Auditable projection/canonical convergence performed for one lease."""

    ABANDONED_RESERVATION = "ABANDONED_RESERVATION"
    RETRY_QUEUED = "RETRY_QUEUED"
    MARKED_RECONCILING = "MARKED_RECONCILING"
    CLOSED_SUCCEEDED = "CLOSED_SUCCEEDED"
    CLOSED_CANCELLED = "CLOSED_CANCELLED"
    REPAIRED_HEARTBEAT = "REPAIRED_HEARTBEAT"
    PROBE_IN_FLIGHT = "PROBE_IN_FLIGHT"
    PROBE_TAKEOVER_READY = "PROBE_TAKEOVER_READY"
    PROBE_CONCLUSION_PENDING = "PROBE_CONCLUSION_PENDING"


@dataclass(frozen=True, slots=True)
class RecoveryRecord:
    """One recovery decision and the resulting queue record."""

    action: RecoveryAction
    lease: LeaseRecord


class EffectRecovery:
    """Converge expired or stale queue rows against authoritative replay."""

    def __init__(
        self,
        store: EventStore,
        queue: EffectQueue,
        spec: FsmSpec,
        clock: Clock,
        *,
        heartbeat_stale_after_seconds: int,
    ) -> None:
        if not isinstance(store, EventStore):
            raise EffectSchedulerError("store must implement EventStore")
        if not isinstance(queue, EffectQueue):
            raise EffectSchedulerError("queue must implement EffectQueue")
        if not isinstance(spec, FsmSpec):
            raise EffectSchedulerError("spec must be an FsmSpec")
        if not isinstance(clock, Clock):
            raise EffectSchedulerError("clock must implement Clock")
        if (
            isinstance(heartbeat_stale_after_seconds, bool)
            or not isinstance(heartbeat_stale_after_seconds, int)
            or heartbeat_stale_after_seconds < 1
        ):
            raise EffectSchedulerError("heartbeat_stale_after_seconds must be positive")
        self._store = store
        self._queue = queue
        self._spec = spec
        self._clock = clock
        self._heartbeat_stale_after_seconds = heartbeat_stale_after_seconds
        self._facts = EffectFactWriter(store, spec)

    def recover(self) -> tuple[RecoveryRecord, ...]:
        """Converge every queue-selected stale/expired lease without blind retry."""

        observed_at = self._clock.now_utc()
        validate_rfc3339_utc_z("observed_at", observed_at)
        heartbeat_before = _format_instant(
            _instant(observed_at) - timedelta(seconds=self._heartbeat_stale_after_seconds)
        )
        _require_recovery_threshold(heartbeat_before, observed_at)
        candidates = self._queue.recoverable(
            observed_at=observed_at,
            heartbeat_before=heartbeat_before,
        )
        return tuple(
            self._recover_one(record, observed_at, heartbeat_before) for record in candidates
        )

    def _recover_one(
        self,
        record: LeaseRecord,
        observed_at: str,
        heartbeat_before: str,
    ) -> RecoveryRecord:
        effect, config_version = self._load_recovery_context(record)
        self._require_queue_binding(record, effect, config_version)
        probe_recovery = self._recover_probe(record, effect, observed_at)
        if probe_recovery is not None:
            return probe_recovery
        terminal = self._close_if_canonical_terminal(record, effect, observed_at)
        if terminal is not None:
            return terminal
        return self._recover_nonterminal(
            record,
            effect,
            observed_at,
            heartbeat_before,
        )

    def _load_recovery_context(self, record: LeaseRecord) -> tuple[EffectState, str]:
        history = tuple(self._store.load(record.stream_id))
        if not history:
            raise EffectRuntimeStateError("recoverable lease has no canonical cycle")
        try:
            state = replay(history, self._spec)
            effect = state.effect(record.effect_id)
        except KeyError as exc:
            raise EffectRuntimeStateError("recoverable lease names an unknown effect") from exc
        return effect, state.config_version

    def _require_queue_binding(
        self,
        record: LeaseRecord,
        effect: EffectState,
        config_version: str,
    ) -> None:
        if record.lease_token not in effect.lease_token_history:
            return
        if record.config_version != config_version:
            raise EffectRuntimeStateError(
                "recoverable queue config differs from the canonical cycle"
            )
        if effect.lease_token == record.lease_token:
            self._require_queue_owner(record, effect.lease_owner, "lease")
        elif _is_latest_attempt(effect, record):
            self._require_queue_owner(record, effect.attempts[-1].lease_owner, "attempt")
        _require_canonical_grant_binding(effect, record)

    def _require_queue_owner(
        self,
        record: LeaseRecord,
        canonical_owner: str | None,
        source: str,
    ) -> None:
        if canonical_owner != record.lease_owner:
            raise EffectRuntimeStateError(
                f"recoverable queue owner differs from the canonical {source}"
            )

    def _recover_probe(
        self,
        record: LeaseRecord,
        effect: EffectState,
        observed_at: str,
    ) -> RecoveryRecord | None:
        permit = record.probe_permit
        if permit is None:
            return None
        if permit.state is ReconciliationProbePermitState.CONCLUDED:
            return self._recover_concluded(record, effect, observed_at)
        if _instant(observed_at) < _instant(permit.expires_at):
            return RecoveryRecord(RecoveryAction.PROBE_IN_FLIGHT, record)
        return RecoveryRecord(RecoveryAction.PROBE_TAKEOVER_READY, record)

    def _recover_nonterminal(
        self,
        record: LeaseRecord,
        effect: EffectState,
        observed_at: str,
        heartbeat_before: str,
    ) -> RecoveryRecord:
        if effect.lifecycle is EffectLifecycle.PENDING or effect.lease_token != record.lease_token:
            return self._abandon_reservation(record, observed_at)
        repaired = self._repair_heartbeat_projection(record, effect)
        if repaired is not record and not _is_recoverable(repaired, observed_at, heartbeat_before):
            return RecoveryRecord(RecoveryAction.REPAIRED_HEARTBEAT, repaired)
        return self._recover_lifecycle(repaired, effect, observed_at)

    def _abandon_reservation(
        self,
        record: LeaseRecord,
        observed_at: str,
    ) -> RecoveryRecord:
        lease = self._queue.finish(
            record.lease_token,
            status=LeaseStatus.ABANDONED,
            completed_at=observed_at,
            reason="orphaned or fenced reservation",
        )
        return RecoveryRecord(RecoveryAction.ABANDONED_RESERVATION, lease)

    def _recover_lifecycle(
        self,
        record: LeaseRecord,
        effect: EffectState,
        observed_at: str,
    ) -> RecoveryRecord:
        if effect.lifecycle is EffectLifecycle.LEASED:
            projected = self._ensure_active(record)
            return self._expire_leased(projected, effect, observed_at)
        if effect.lifecycle is EffectLifecycle.RUNNING:
            projected = self._ensure_running(record, effect)
            return self._timeout_running(projected, effect, observed_at)
        if effect.lifecycle is EffectLifecycle.FAILED:
            return self._recover_failed(record, effect, observed_at)
        if effect.lifecycle is EffectLifecycle.TIMED_OUT:
            return self._recover_timed_out(record, effect, observed_at)
        raise EffectRuntimeStateError(
            f"unsupported recoverable canonical state {effect.lifecycle.value}"
        )

    def _recover_failed(
        self,
        record: LeaseRecord,
        effect: EffectState,
        observed_at: str,
    ) -> RecoveryRecord:
        projected = self._ensure_running(record, effect)
        reconciliation_ref = record.reconciliation_ref or _recovery_ref(record, "known-failure")
        lease = self._queue.mark_reconciling(
            projected.lease_token,
            observed_at=observed_at,
            reconciliation_ref=reconciliation_ref,
            reason=effect.reasons[-1],
        )
        return RecoveryRecord(RecoveryAction.MARKED_RECONCILING, lease)

    def _recover_timed_out(
        self,
        record: LeaseRecord,
        effect: EffectState,
        observed_at: str,
    ) -> RecoveryRecord:
        if not _is_latest_attempt(effect, record):
            return self._retry_preexecution(
                self._ensure_active(record),
                _latest_reconciliation_ref(effect, record.lease_token),
                observed_at,
            )
        projected = self._ensure_running(record, effect)
        reconciliation_ref = _latest_reconciliation_ref(effect, record.lease_token)
        lease = self._queue.mark_reconciling(
            projected.lease_token,
            observed_at=observed_at,
            reconciliation_ref=reconciliation_ref,
            reason="canonical timeout projection repaired",
        )
        return RecoveryRecord(RecoveryAction.MARKED_RECONCILING, lease)

    def _recover_concluded(
        self,
        record: LeaseRecord,
        effect: EffectState,
        observed_at: str,
    ) -> RecoveryRecord:
        """Finalize already-canonical facts or leave a sealed observation resumable."""

        permit = record.probe_permit
        assert permit is not None
        assert permit.state is ReconciliationProbePermitState.CONCLUDED
        assert permit.conclusion is not None
        conclusion = permit.conclusion
        if (
            effect.lifecycle is EffectLifecycle.SUCCEEDED
            and conclusion.outcome is ReconciliationOutcome.APPLIED
        ):
            lease = self._queue.finish(
                record.lease_token,
                status=LeaseStatus.SUCCEEDED,
                completed_at=permit.concluded_at or observed_at,
                reconciliation_ref=conclusion.evidence_refs[0],
                probe_permit=permit,
            )
            return RecoveryRecord(RecoveryAction.CLOSED_SUCCEEDED, lease)
        if (
            effect.lifecycle is EffectLifecycle.PENDING
            and conclusion.outcome is ReconciliationOutcome.NOT_APPLIED
        ):
            lease = self._queue.finish(
                record.lease_token,
                status=LeaseStatus.ABANDONED,
                completed_at=permit.concluded_at or observed_at,
                reconciliation_ref=conclusion.evidence_refs[0],
                reason=conclusion.reason,
                probe_permit=permit,
            )
            return RecoveryRecord(RecoveryAction.RETRY_QUEUED, lease)
        if effect.lifecycle is EffectLifecycle.CANCELLED:
            if conclusion.outcome is ReconciliationOutcome.NOT_APPLIED:
                lease = self._queue.finish(
                    record.lease_token,
                    status=LeaseStatus.CANCELLED,
                    completed_at=permit.concluded_at or observed_at,
                    reconciliation_ref=conclusion.evidence_refs[0],
                    reason=conclusion.reason,
                    probe_permit=permit,
                )
                return RecoveryRecord(RecoveryAction.CLOSED_CANCELLED, lease)
            reconciliation_ref = (
                conclusion.result_ref
                if conclusion.outcome is ReconciliationOutcome.APPLIED
                else conclusion.evidence_refs[0]
            )
            assert reconciliation_ref is not None
            reason = conclusion.reason or (
                "APPLIED after canonical cancellation; compensation required; "
                f"durable result {conclusion.result_ref}"
            )
            lease = self._queue.mark_reconciling(
                record.lease_token,
                observed_at=permit.concluded_at or observed_at,
                reconciliation_ref=reconciliation_ref,
                reason=reason,
                probe_permit=permit,
            )
            return RecoveryRecord(RecoveryAction.MARKED_RECONCILING, lease)
        return RecoveryRecord(RecoveryAction.PROBE_CONCLUSION_PENDING, record)

    def _close_if_canonical_terminal(
        self, record: LeaseRecord, effect: EffectState, observed_at: str
    ) -> RecoveryRecord | None:
        mapping = {
            EffectLifecycle.SUCCEEDED: (
                LeaseStatus.SUCCEEDED,
                RecoveryAction.CLOSED_SUCCEEDED,
            ),
            EffectLifecycle.CANCELLED: (
                LeaseStatus.CANCELLED,
                RecoveryAction.CLOSED_CANCELLED,
            ),
        }
        selected = mapping.get(effect.lifecycle)
        if selected is None:
            return None
        if (
            effect.lifecycle is EffectLifecycle.CANCELLED
            and effect.attempts
            and effect.attempts[-1].lease_token == record.lease_token
        ):
            projected = self._ensure_running(record, effect)
            reconciliation_ref = record.reconciliation_ref or _recovery_ref(
                record, "cancelled-outcome"
            )
            lease = self._queue.mark_reconciling(
                projected.lease_token,
                observed_at=observed_at,
                reconciliation_ref=reconciliation_ref,
                reason="canonical cancellation has a started attempt; outcome is unresolved",
            )
            return RecoveryRecord(RecoveryAction.MARKED_RECONCILING, lease)
        cancelled_prelease = (
            effect.lifecycle is EffectLifecycle.CANCELLED and record.status is LeaseStatus.RESERVED
        )
        if record.lease_token not in effect.lease_token_history and not cancelled_prelease:
            raise EffectRuntimeStateError("terminal effect does not recognize queue lease token")
        projected = record
        if effect.attempts and effect.attempts[-1].lease_token == record.lease_token:
            projected = self._ensure_running(record, effect)
        status, action = selected
        reason = effect.reasons[-1] if effect.reasons else None
        lease = self._queue.finish(
            projected.lease_token,
            status=status,
            completed_at=observed_at,
            reconciliation_ref=(
                effect.reconciliation_refs[-1] if effect.reconciliation_refs else None
            ),
            reason=reason,
        )
        return RecoveryRecord(action, lease)

    def _repair_heartbeat_projection(self, record: LeaseRecord, effect: EffectState) -> LeaseRecord:
        if effect.heartbeat_at is None or effect.lease_expiry is None:
            return record
        if not (
            _instant(effect.heartbeat_at) > _instant(record.heartbeat_at)
            and _instant(effect.lease_expiry) > _instant(record.lease_expiry)
        ):
            return record
        if effect.lifecycle is EffectLifecycle.RUNNING:
            projected = self._ensure_running(record, effect)
        else:
            projected = self._ensure_active(record)
        return self._queue.heartbeat(
            projected.lease_token,
            lease_owner=projected.lease_owner,
            heartbeat_at=effect.heartbeat_at,
            lease_expiry=effect.lease_expiry,
        )

    def _expire_leased(
        self, record: LeaseRecord, effect: EffectState, observed_at: str
    ) -> RecoveryRecord:
        assert effect.heartbeat_at is not None
        assert effect.lease_expiry is not None
        reconciliation_ref = _recovery_ref(record, "lease-expired")
        self._facts.append(
            cycle_id=record.stream_id,
            effect_id=record.effect_id,
            event_type=EventType.EFFECT_LEASE_EXPIRED,
            payload={
                "lease_token": record.lease_token,
                "reconciliation_ref": reconciliation_ref,
                "expected_heartbeat_at": effect.heartbeat_at,
                "expected_lease_expiry": effect.lease_expiry,
            },
            occurred_at=observed_at,
            actor="effect-runtime-recovery",
            correlation_id=_correlation_id(record),
            causation_id=record.lease_token,
        )
        return self._retry_preexecution(record, reconciliation_ref, observed_at)

    def _retry_preexecution(
        self,
        record: LeaseRecord,
        reconciliation_ref: str,
        observed_at: str,
    ) -> RecoveryRecord:
        self._facts.append(
            cycle_id=record.stream_id,
            effect_id=record.effect_id,
            event_type=EventType.EFFECT_RETRY_QUEUED,
            payload={
                "guard_result": GuardResult.PASS.value,
                "guard_evidence_refs": (reconciliation_ref,),
                "lease_token": record.lease_token,
                "reconciliation_ref": reconciliation_ref,
                "reconciliation_outcome": ReconciliationOutcome.NOT_APPLIED.value,
            },
            occurred_at=observed_at,
            actor="effect-runtime-recovery",
            correlation_id=_correlation_id(record),
            causation_id=reconciliation_ref,
        )
        lease = self._queue.finish(
            record.lease_token,
            status=LeaseStatus.ABANDONED,
            completed_at=observed_at,
            reconciliation_ref=reconciliation_ref,
            reason="pre-execution lease expired; commit barrier proves NOT_APPLIED",
        )
        return RecoveryRecord(RecoveryAction.RETRY_QUEUED, lease)

    def _timeout_running(
        self, record: LeaseRecord, effect: EffectState, observed_at: str
    ) -> RecoveryRecord:
        if not effect.attempts:
            raise EffectRuntimeStateError("running effect lacks an attempt audit")
        assert effect.heartbeat_at is not None
        assert effect.lease_expiry is not None
        reconciliation_ref = _recovery_ref(record, "execution-timeout")
        self._facts.append(
            cycle_id=record.stream_id,
            effect_id=record.effect_id,
            event_type=EventType.EFFECT_TIMED_OUT,
            payload={
                "attempt": effect.current_attempt,
                "lease_token": record.lease_token,
                "reconciliation_ref": reconciliation_ref,
                "expected_heartbeat_at": effect.heartbeat_at,
                "expected_lease_expiry": effect.lease_expiry,
            },
            occurred_at=observed_at,
            actor="effect-runtime-recovery",
            correlation_id=_correlation_id(record),
            causation_id=record.lease_token,
        )
        lease = self._queue.mark_reconciling(
            record.lease_token,
            observed_at=observed_at,
            reconciliation_ref=reconciliation_ref,
            reason="running worker heartbeat or lease expired",
        )
        return RecoveryRecord(RecoveryAction.MARKED_RECONCILING, lease)

    def _ensure_active(self, record: LeaseRecord) -> LeaseRecord:
        if record.status is LeaseStatus.RESERVED:
            return self._queue.activate(record.lease_token, activated_at=record.claimed_at)
        if record.status in {
            LeaseStatus.ACTIVE,
            LeaseStatus.RUNNING,
            LeaseStatus.RECONCILING,
        }:
            return record
        raise EffectRuntimeStateError(f"cannot repair active projection from {record.status.value}")

    def _ensure_running(self, record: LeaseRecord, effect: EffectState) -> LeaseRecord:
        projected = self._ensure_active(record)
        if projected.status is LeaseStatus.ACTIVE:
            if not effect.attempts:
                raise EffectRuntimeStateError("canonical effect has no attempt to project")
            attempt = effect.attempts[-1]
            return self._queue.start(
                projected.lease_token,
                lease_owner=projected.lease_owner,
                attempt=attempt.attempt,
                started_at=attempt.started_at,
            )
        if projected.status in {LeaseStatus.RUNNING, LeaseStatus.RECONCILING}:
            return projected
        raise EffectRuntimeStateError("queue projection cannot be advanced to RUNNING")


def _latest_reconciliation_ref(effect: EffectState, lease_token: str) -> str:
    if (
        effect.attempts
        and effect.attempts[-1].lease_token == lease_token
        and effect.attempts[-1].reconciliation_refs
    ):
        return effect.attempts[-1].reconciliation_refs[-1]
    if effect.reconciliation_refs:
        return effect.reconciliation_refs[-1]
    raise EffectRuntimeStateError("timed-out effect lacks reconciliation evidence")


def _is_latest_attempt(effect: EffectState, record: LeaseRecord) -> bool:
    return bool(effect.attempts) and effect.attempts[-1].lease_token == record.lease_token


def _instant(value: str) -> datetime:
    return datetime.fromisoformat(value[:-1] + "+00:00")


def _format_instant(value: datetime) -> str:
    return value.isoformat(timespec="seconds").replace("+00:00", "Z")


def _is_recoverable(record: LeaseRecord, observed_at: str, heartbeat_before: str) -> bool:
    return _instant(record.lease_expiry) <= _instant(observed_at) or _instant(
        record.heartbeat_at
    ) <= _instant(heartbeat_before)


def _require_recovery_threshold(heartbeat_before: str, observed_at: str) -> None:
    try:
        validate_rfc3339_utc_z("heartbeat_before", heartbeat_before)
        validate_rfc3339_utc_z("observed_at", observed_at)
    except EventSchemaError as exc:
        raise EffectRuntimeStateError(str(exc)) from exc
    if _instant(heartbeat_before) > _instant(observed_at):
        raise EffectRuntimeStateError("heartbeat_before cannot be later than observed_at")


def _recovery_ref(record: LeaseRecord, kind: str) -> str:
    digest = canonical_sha256(
        {
            "effect_id": record.effect_id,
            "kind": kind,
            "lease_token": record.lease_token,
            "stream_id": record.stream_id,
        }
    )
    return f"recovery://effect-runtime/{kind}/{digest}"


__all__ = ["EffectRecovery", "RecoveryAction", "RecoveryRecord"]
