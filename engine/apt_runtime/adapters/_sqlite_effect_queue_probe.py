"""Crash-resumable reconciliation probe permits for the SQLite queue."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from engine.apt_runtime.domain.canonical import MAX_SIGNED_64
from engine.apt_runtime.domain.effect_runtime import RuntimeUsage
from engine.apt_runtime.ports.effect_queue import (
    EffectQueueCorruption,
    LeaseConflict,
    LeaseRecord,
    LeaseStatus,
    ReconciliationProbeAcquisition,
    ReconciliationProbeConclusion,
    ReconciliationProbeConflict,
    ReconciliationProbeExhausted,
    ReconciliationProbePermit,
    ReconciliationProbePermitState,
)

from ._effect_queue_codec import encode_usage
from ._sqlite_effect_queue_backend import (
    queue_instant,
    queue_text,
    queue_timestamp,
    require_at_or_after,
)

if TYPE_CHECKING:
    from sqlite3 import Connection


class SqliteEffectQueueProbeMixin:
    """Atomic permit acquire/takeover/seal operations."""

    if TYPE_CHECKING:
        _connection: Connection

        def _write_transaction(self, operation: str): ...
        def _required_record(self, lease_token: str) -> LeaseRecord: ...
        def _require_status(
            self, record: LeaseRecord, allowed: set[LeaseStatus], operation: str
        ) -> None: ...
        def _load_usage(self, outbox_id: str) -> RuntimeUsage: ...
        def _update_lease(self, record: LeaseRecord) -> None: ...
        def _append_state_journal(
            self, action: str, record: LeaseRecord, occurred_at: str
        ) -> None: ...
        def _append_usage_journal(
            self,
            lease_token: str,
            delta: RuntimeUsage,
            usage: RuntimeUsage,
            observed_at: str,
        ) -> None: ...

    def begin_reconciliation_probe(
        self,
        lease_token: str,
        *,
        permit_token: str,
        acquired_at: str,
        expires_at: str,
    ) -> ReconciliationProbeAcquisition:
        """Acquire a fresh generation or take over an expired ACTIVE generation.

        A takeover inherits the already charged logical probe. This prevents a
        process crash from consuming the entire immutable probe budget.
        """

        lease_token = queue_text("lease_token", lease_token)
        permit_token = queue_text("permit_token", permit_token)
        acquired_at = queue_timestamp("acquired_at", acquired_at)
        expires_at = queue_timestamp("expires_at", expires_at)
        if queue_instant(expires_at) <= queue_instant(acquired_at):
            raise LeaseConflict("probe expires_at must be later than acquired_at")
        with self._write_transaction("begin reconciliation probe"):
            lease = self._required_record(lease_token)
            self._require_status(lease, {LeaseStatus.RECONCILING}, "begin probe")
            require_at_or_after("acquired_at", acquired_at, lease.heartbeat_at)
            prior = lease.probe_permit
            takeover = prior is not None
            if prior is not None:
                if prior.state is ReconciliationProbePermitState.CONCLUDED:
                    raise ReconciliationProbeConflict(
                        "a concluded reconciliation probe awaits durable finalization"
                    )
                if queue_instant(acquired_at) < queue_instant(prior.expires_at):
                    raise ReconciliationProbeConflict(
                        "an unexpired reconciliation probe is already in flight"
                    )
            if lease.probe_generation >= MAX_SIGNED_64:
                raise EffectQueueCorruption("probe generation exceeds signed 64-bit range")
            usage = self._load_usage(lease.outbox_id)
            charged = not takeover
            if charged and usage.reconciliation_probes >= lease.budget.max_reconciliation_probes:
                raise ReconciliationProbeExhausted("the reconciliation probe budget is exhausted")
            permit = ReconciliationProbePermit(
                permit_token=permit_token,
                generation=lease.probe_generation + 1,
                state=ReconciliationProbePermitState.ACTIVE,
                acquired_at=acquired_at,
                expires_at=expires_at,
            )
            updated_lease = replace(
                lease,
                probe_generation=permit.generation,
                probe_permit=permit,
            )
            self._update_lease(updated_lease)
            self._append_state_journal("PROBE_ACQUIRED", updated_lease, acquired_at)
            if charged:
                delta = RuntimeUsage(reconciliation_probes=1)
                usage = usage.add(delta)
                usage_blob, usage_hash = encode_usage(usage)
                result = self._connection.execute(
                    "UPDATE effect_runtime_usage SET usage_json = ?, usage_hash = ?, "
                    "updated_at = ? WHERE outbox_id = ?",
                    (usage_blob, usage_hash, acquired_at, lease.outbox_id),
                )
                if result.rowcount != 1:
                    raise EffectQueueCorruption("effect usage row disappeared during probe permit")
                self._append_usage_journal(lease_token, delta, usage, acquired_at)
            return ReconciliationProbeAcquisition(
                permit=permit,
                usage=self._load_usage(lease.outbox_id),
                charged=charged,
            )

    def conclude_reconciliation_probe(
        self,
        lease_token: str,
        *,
        permit: ReconciliationProbePermit,
        concluded_at: str,
        expires_at: str,
        conclusion: ReconciliationProbeConclusion,
        reconciliation_ref: str,
        reason: str,
    ) -> LeaseRecord:
        """Atomically seal an exact live generation with resumable evidence."""

        lease_token = queue_text("lease_token", lease_token)
        if not isinstance(permit, ReconciliationProbePermit):
            raise LeaseConflict("permit must be a ReconciliationProbePermit")
        if permit.state is not ReconciliationProbePermitState.ACTIVE:
            raise LeaseConflict("only an ACTIVE permit can be concluded")
        if not isinstance(conclusion, ReconciliationProbeConclusion):
            raise LeaseConflict("conclusion must be a ReconciliationProbeConclusion")
        concluded_at = queue_timestamp("concluded_at", concluded_at)
        expires_at = queue_timestamp("expires_at", expires_at)
        reconciliation_ref = queue_text("reconciliation_ref", reconciliation_ref)
        reason = queue_text("reason", reason)
        if queue_instant(concluded_at) < queue_instant(permit.acquired_at):
            raise LeaseConflict("concluded_at cannot precede permit acquisition")
        if queue_instant(concluded_at) >= queue_instant(permit.expires_at):
            raise ReconciliationProbeConflict("an expired probe generation cannot conclude")
        if queue_instant(expires_at) <= queue_instant(concluded_at):
            raise LeaseConflict("conclusion expires_at must be later than concluded_at")
        sealed = replace(
            permit,
            state=ReconciliationProbePermitState.CONCLUDED,
            expires_at=expires_at,
            concluded_at=concluded_at,
            conclusion=conclusion,
        )
        with self._write_transaction("conclude reconciliation probe"):
            lease = self._required_record(lease_token)
            self._require_status(lease, {LeaseStatus.RECONCILING}, "conclude probe")
            if lease.probe_permit == sealed:
                if lease.reconciliation_ref == reconciliation_ref and lease.reason == reason:
                    return lease
                raise ReconciliationProbeConflict(
                    "sealed probe conclusion was replayed with different evidence"
                )
            if lease.probe_permit != permit:
                raise ReconciliationProbeConflict(
                    "probe generation was expired, replaced, or otherwise fenced"
                )
            updated = replace(
                lease,
                probe_permit=sealed,
                reconciliation_ref=reconciliation_ref,
                reason=reason,
            )
            self._update_lease(updated)
            self._append_state_journal("PROBE_CONCLUDED", updated, concluded_at)
            return self._required_record(lease_token)


__all__ = ["SqliteEffectQueueProbeMixin"]
