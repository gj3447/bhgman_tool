"""SQLite operational queue for the APT Slice 2 effect runtime.

The immutable ``apt_outbox`` remains the execution-request authority.  This
adapter adds fenced delivery state, global resource claims, usage accounting,
and a canonical journal while keeping lifecycle decisions explicit here.

# KG: apt-tpa-legion-engine-canon-2026-06-12
# Design: ADRs/apt-vnext-slice2-effect-runtime-2026-07-14.md
"""

from __future__ import annotations

from dataclasses import replace
from typing import cast

from engine.apt_runtime.domain.canonical import MAX_SIGNED_64
from engine.apt_runtime.domain.effect_runtime import RuntimeContractError, RuntimeUsage
from engine.apt_runtime.ports.effect_queue import (
    EffectQueue,
    EffectQueueCorruption,
    EffectQueueError,
    LeaseConflict,
    LeaseRecord,
    LeaseRequest,
    LeaseStatus,
    ReconciliationProbePermit,
    ReconciliationProbePermitState,
    ResourceClaimConflict,
    TERMINAL_LEASE_STATUSES,
)

from ._effect_queue_codec import encode_usage
from ._sqlite_effect_queue_backend import (
    NONTERMINAL_LEASE_VALUES,
    _SqliteEffectQueueBackend,
    queue_instant,
    queue_text,
    queue_timestamp,
    require_at_or_after,
)
from ._sqlite_effect_queue_probe import SqliteEffectQueueProbeMixin


_FINISH_TRANSITIONS = {
    LeaseStatus.RESERVED: frozenset({LeaseStatus.ABANDONED, LeaseStatus.CANCELLED}),
    LeaseStatus.ACTIVE: frozenset(
        {LeaseStatus.ABANDONED, LeaseStatus.CANCELLED, LeaseStatus.FAILED}
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
_GRANT_BINDING_FIELDS = (
    "grant_ref",
    "grant_hash",
    "config_version",
    "authorization_ref",
    "authorization_hash",
)


def _require_retry_authority(authority: LeaseRecord, request: LeaseRequest) -> None:
    if authority.budget != request.budget:
        raise LeaseConflict("runtime budget cannot change across retry epochs")
    if authority.resource_claims != request.resource_claims:
        raise LeaseConflict("resource claims cannot change across retry epochs")
    if any(getattr(authority, name) != getattr(request, name) for name in _GRANT_BINDING_FIELDS):
        raise LeaseConflict("execution grant cannot change across retry epochs")


class SqliteEffectQueue(
    SqliteEffectQueueProbeMixin,
    _SqliteEffectQueueBackend,
    EffectQueue,
):
    """Fenced SQLite effect-delivery coordinator sharing an event-store file."""

    def reserve(self, request: LeaseRequest) -> LeaseRecord:
        """Atomically reserve an exact immutable outbox request and its claims."""

        if not isinstance(request, LeaseRequest):
            raise EffectQueueError("request must be a LeaseRequest")
        keys = [claim.resource_key for claim in request.resource_claims]
        if len(set(keys)) != len(keys):
            raise ResourceClaimConflict(
                "one lease cannot claim the same resource with multiple access modes"
            )

        with self._write_transaction("reserve effect"):
            if (
                self._connection.execute(
                    "SELECT 1 FROM effect_runtime_leases WHERE lease_token = ?",
                    (request.lease_token,),
                ).fetchone()
                is not None
            ):
                raise LeaseConflict(f"lease_token {request.lease_token!r} was already used")
            self._verify_outbox(request)
            prior = self._latest_for_outbox(request.outbox.outbox_id)
            epoch = self._next_epoch(request, prior)
            self._assert_usage_shape(request.outbox.outbox_id, has_prior=prior is not None)
            self._assert_resource_claims_available(request.resource_claims)
            record = LeaseRecord(
                outbox_id=request.outbox.outbox_id,
                stream_id=request.outbox.stream_id,
                effect_id=request.outbox.effect_id,
                lease_token=request.lease_token,
                lease_epoch=epoch,
                lease_owner=request.lease_owner,
                status=LeaseStatus.RESERVED,
                claimed_at=request.claimed_at,
                activated_at=None,
                heartbeat_at=request.claimed_at,
                lease_expiry=request.lease_expiry,
                attempt=0,
                resource_claims=request.resource_claims,
                budget=request.budget,
                grant_ref=request.grant_ref,
                grant_hash=request.grant_hash,
                config_version=request.config_version,
                authorization_ref=request.authorization_ref,
                authorization_hash=request.authorization_hash,
            )
            self._insert_lease(record)
            for claim in record.resource_claims:
                self._connection.execute(
                    "INSERT INTO effect_runtime_resource_claims"
                    "(lease_token, resource_key, access) VALUES (?, ?, ?)",
                    (record.lease_token, claim.resource_key, claim.access.value),
                )
            if prior is None:
                usage_blob, usage_hash = encode_usage(RuntimeUsage())
                self._connection.execute(
                    "INSERT INTO effect_runtime_usage"
                    "(outbox_id, usage_json, usage_hash, updated_at) VALUES (?, ?, ?, ?)",
                    (record.outbox_id, usage_blob, usage_hash, record.claimed_at),
                )
            self._append_state_journal("RESERVED", record, record.claimed_at)
            return self._required_record(record.lease_token)

    def _next_epoch(self, request: LeaseRequest, prior: LeaseRecord | None) -> int:
        if prior is None:
            return 1
        if prior.status not in {LeaseStatus.FAILED, LeaseStatus.ABANDONED}:
            raise LeaseConflict(
                f"outbox {request.outbox.outbox_id!r} already has "
                f"{prior.status.value} lease epoch {prior.lease_epoch}"
            )
        authority = prior if prior.activated_at is not None else None
        if authority is None:
            row = self._connection.execute(
                "SELECT lease_token FROM effect_runtime_leases "
                "WHERE outbox_id = ? AND activated_at IS NOT NULL "
                "ORDER BY lease_epoch DESC LIMIT 1",
                (prior.outbox_id,),
            ).fetchone()
            if row is not None:
                authority = self._required_record(cast(str, row["lease_token"]))
        if authority is not None:
            _require_retry_authority(authority, request)
        assert prior.completed_at is not None
        require_at_or_after("claimed_at", request.claimed_at, prior.completed_at)
        if prior.lease_epoch == MAX_SIGNED_64:
            raise EffectQueueCorruption("lease epoch exceeds the signed 64-bit range")
        return prior.lease_epoch + 1

    def activate(self, lease_token: str, *, activated_at: str) -> LeaseRecord:
        """Activate a reservation only while its fencing TTL is still live."""

        lease_token = queue_text("lease_token", lease_token)
        activated_at = queue_timestamp("activated_at", activated_at)
        with self._write_transaction("activate lease"):
            current = self._required_record(lease_token)
            if current.status is LeaseStatus.ACTIVE and current.activated_at == activated_at:
                return current
            self._require_status(current, {LeaseStatus.RESERVED}, "activate")
            require_at_or_after("activated_at", activated_at, current.claimed_at)
            if queue_instant(activated_at) >= queue_instant(current.lease_expiry):
                raise LeaseConflict("expired reservation cannot be activated")
            updated = replace(
                current,
                status=LeaseStatus.ACTIVE,
                activated_at=activated_at,
                heartbeat_at=activated_at,
            )
            self._update_lease(updated)
            self._append_state_journal("ACTIVATED", updated, activated_at)
            return self._required_record(lease_token)

    def heartbeat(
        self,
        lease_token: str,
        *,
        lease_owner: str,
        heartbeat_at: str,
        lease_expiry: str,
    ) -> LeaseRecord:
        """Renew an ACTIVE/RUNNING lease without permitting stale-owner takeover."""

        lease_token = queue_text("lease_token", lease_token)
        lease_owner = queue_text("lease_owner", lease_owner)
        heartbeat_at = queue_timestamp("heartbeat_at", heartbeat_at)
        lease_expiry = queue_timestamp("lease_expiry", lease_expiry)
        if queue_instant(lease_expiry) <= queue_instant(heartbeat_at):
            raise LeaseConflict("lease_expiry must be later than heartbeat_at")
        with self._write_transaction("heartbeat lease"):
            current = self._required_record(lease_token)
            self._require_owner(current, lease_owner)
            self._require_status(current, {LeaseStatus.ACTIVE, LeaseStatus.RUNNING}, "heartbeat")
            if heartbeat_at == current.heartbeat_at and lease_expiry == current.lease_expiry:
                return current
            if queue_instant(heartbeat_at) < queue_instant(current.heartbeat_at):
                raise LeaseConflict("heartbeat_at cannot move backwards")
            if queue_instant(heartbeat_at) >= queue_instant(current.lease_expiry):
                raise LeaseConflict("an expired lease cannot be renewed")
            if queue_instant(lease_expiry) <= queue_instant(current.lease_expiry):
                raise LeaseConflict("heartbeat must extend lease_expiry")
            updated = replace(
                current,
                heartbeat_at=heartbeat_at,
                lease_expiry=lease_expiry,
            )
            self._update_lease(updated)
            self._append_state_journal("HEARTBEAT_RECORDED", updated, heartbeat_at)
            return self._required_record(lease_token)

    def start(
        self,
        lease_token: str,
        *,
        lease_owner: str,
        attempt: int,
        started_at: str,
    ) -> LeaseRecord:
        """Atomically win one externally executable attempt after its durable fact."""

        lease_token = queue_text("lease_token", lease_token)
        lease_owner = queue_text("lease_owner", lease_owner)
        started_at = queue_timestamp("started_at", started_at)
        if (
            isinstance(attempt, bool)
            or not isinstance(attempt, int)
            or not 1 <= attempt <= MAX_SIGNED_64
        ):
            raise EffectQueueError("attempt must be a signed 64-bit positive integer")
        with self._write_transaction("start lease"):
            current = self._required_record(lease_token)
            self._require_owner(current, lease_owner)
            self._require_status(current, {LeaseStatus.ACTIVE}, "start")
            require_at_or_after("started_at", started_at, cast(str, current.activated_at))
            if queue_instant(started_at) >= queue_instant(current.lease_expiry):
                raise LeaseConflict("an expired lease cannot start external execution")
            max_attempt = cast(
                int,
                self._connection.execute(
                    "SELECT COALESCE(MAX(attempt), 0) FROM effect_runtime_leases "
                    "WHERE outbox_id = ? AND lease_token <> ?",
                    (current.outbox_id, current.lease_token),
                ).fetchone()[0],
            )
            if attempt <= max_attempt:
                raise LeaseConflict(
                    f"attempt {attempt} is not newer than prior attempt {max_attempt}"
                )
            updated = replace(
                current,
                status=LeaseStatus.RUNNING,
                attempt=attempt,
                heartbeat_at=started_at,
            )
            self._update_lease(updated)
            self._append_state_journal("STARTED", updated, started_at)
            return self._required_record(lease_token)

    def mark_reconciling(
        self,
        lease_token: str,
        *,
        observed_at: str,
        reconciliation_ref: str,
        reason: str,
        probe_permit: ReconciliationProbePermit | None = None,
    ) -> LeaseRecord:
        """Retain claims while appending an uncertain/reconciled observation."""

        lease_token = queue_text("lease_token", lease_token)
        observed_at = queue_timestamp("observed_at", observed_at)
        reconciliation_ref = queue_text("reconciliation_ref", reconciliation_ref)
        reason = queue_text("reason", reason)
        with self._write_transaction("mark lease reconciling"):
            current = self._required_record(lease_token)
            if (
                current.status is LeaseStatus.RECONCILING
                and current.reconciliation_ref == reconciliation_ref
                and current.reason == reason
                and current.probe_permit is None
            ):
                return current
            self._require_status(
                current,
                {LeaseStatus.ACTIVE, LeaseStatus.RUNNING, LeaseStatus.RECONCILING},
                "mark reconciling",
            )
            require_at_or_after("observed_at", observed_at, current.heartbeat_at)
            _require_concluded_permit(current, probe_permit)
            updated = replace(
                current,
                status=LeaseStatus.RECONCILING,
                probe_permit=None,
                reconciliation_ref=reconciliation_ref,
                reason=reason,
            )
            self._update_lease(updated)
            self._append_state_journal("RECONCILING", updated, observed_at)
            return self._required_record(lease_token)

    def finish(
        self,
        lease_token: str,
        *,
        status: LeaseStatus,
        completed_at: str,
        reconciliation_ref: str | None = None,
        reason: str | None = None,
        probe_permit: ReconciliationProbePermit | None = None,
    ) -> LeaseRecord:
        """Make a legal terminal transition after its canonical fact is durable."""

        lease_token = queue_text("lease_token", lease_token)
        completed_at = queue_timestamp("completed_at", completed_at)
        try:
            status = LeaseStatus(status)
        except ValueError as exc:
            raise EffectQueueError("finish status must be a known lease status") from exc
        if status not in TERMINAL_LEASE_STATUSES:
            raise EffectQueueError("finish status must be terminal")
        reconciliation_ref = (
            None
            if reconciliation_ref is None
            else queue_text("reconciliation_ref", reconciliation_ref)
        )
        reason = None if reason is None else queue_text("reason", reason)
        if (
            status
            in {
                LeaseStatus.FAILED,
                LeaseStatus.CANCELLED,
                LeaseStatus.ABANDONED,
            }
            and reason is None
        ):
            raise EffectQueueError(f"{status.value} finish requires reason")

        with self._write_transaction("finish lease"):
            current = self._required_record(lease_token)
            if current.status in TERMINAL_LEASE_STATUSES:
                if (
                    current.status is status
                    and current.completed_at == completed_at
                    and current.reconciliation_ref == reconciliation_ref
                    and current.reason == reason
                ):
                    return current
                raise LeaseConflict("terminal lease is absorbing")
            if status not in _FINISH_TRANSITIONS.get(current.status, frozenset()):
                raise LeaseConflict(f"cannot finish {current.status.value} lease as {status.value}")
            require_at_or_after("completed_at", completed_at, current.heartbeat_at)
            _require_concluded_permit(current, probe_permit)
            updated = replace(
                current,
                status=status,
                probe_permit=None,
                reconciliation_ref=reconciliation_ref,
                reason=reason,
                completed_at=completed_at,
            )
            self._update_lease(updated)
            self._append_state_journal("FINISHED", updated, completed_at)
            return self._required_record(lease_token)

    def usage_for_outbox(self, outbox_id: str) -> RuntimeUsage:
        """Return validated accumulated usage, or zero before first reservation."""

        outbox_id = queue_text("outbox_id", outbox_id)
        with self._read_transaction("load effect usage"):
            self._require_outbox_id(outbox_id)
            self._latest_for_outbox(outbox_id)
            return self._load_usage(outbox_id)

    def record_usage(
        self,
        lease_token: str,
        *,
        delta: RuntimeUsage,
        observed_at: str,
    ) -> RuntimeUsage:
        """Atomically accumulate one explicit delta and journal the new snapshot."""

        lease_token = queue_text("lease_token", lease_token)
        observed_at = queue_timestamp("observed_at", observed_at)
        if not isinstance(delta, RuntimeUsage):
            raise EffectQueueError("delta must be RuntimeUsage")
        with self._write_transaction("record effect usage"):
            lease = self._required_record(lease_token)
            self._require_status(
                lease, {LeaseStatus.RUNNING, LeaseStatus.RECONCILING}, "record usage"
            )
            require_at_or_after("observed_at", observed_at, lease.heartbeat_at)
            current = self._load_usage(lease.outbox_id)
            try:
                updated = current.add(delta)
            except RuntimeContractError as exc:
                raise EffectQueueError(f"usage delta cannot be accumulated: {exc}") from exc
            usage_blob, usage_hash = encode_usage(updated)
            result = self._connection.execute(
                "UPDATE effect_runtime_usage SET usage_json = ?, usage_hash = ?, updated_at = ? "
                "WHERE outbox_id = ?",
                (usage_blob, usage_hash, observed_at, lease.outbox_id),
            )
            if result.rowcount != 1:
                raise EffectQueueCorruption("effect usage row disappeared during update")
            self._append_usage_journal(lease_token, delta, updated, observed_at)
            reloaded = self._load_usage(lease.outbox_id)
            if reloaded != updated:
                raise EffectQueueCorruption("effect usage write failed canonical read-back")
            return reloaded

    def load(self, lease_token: str) -> LeaseRecord | None:
        """Load one fencing epoch and validate its row, claims, and journal."""

        lease_token = queue_text("lease_token", lease_token)
        with self._read_transaction("load effect lease"):
            return self._record(lease_token)

    def latest_for_outbox(self, outbox_id: str) -> LeaseRecord | None:
        """Load the greatest validated lease epoch for a durable outbox row."""

        outbox_id = queue_text("outbox_id", outbox_id)
        with self._read_transaction("load latest effect lease"):
            return self._latest_for_outbox(outbox_id)

    def recoverable(self, *, observed_at: str, heartbeat_before: str) -> tuple[LeaseRecord, ...]:
        """Return expired or stale nonterminal leases in deterministic order."""

        observed_at = queue_timestamp("observed_at", observed_at)
        heartbeat_before = queue_timestamp("heartbeat_before", heartbeat_before)
        observed = queue_instant(observed_at)
        stale_before = queue_instant(heartbeat_before)
        if stale_before > observed:
            raise EffectQueueError("heartbeat_before cannot be later than observed_at")
        with self._read_transaction("load recoverable effect leases"):
            placeholders = ", ".join("?" for _ in NONTERMINAL_LEASE_VALUES)
            rows = self._connection.execute(
                f"SELECT lease_token FROM effect_runtime_leases WHERE status IN ({placeholders})",
                NONTERMINAL_LEASE_VALUES,
            ).fetchall()
            records = [self._required_record(cast(str, row["lease_token"])) for row in rows]
            selected = [
                record
                for record in records
                if queue_instant(record.lease_expiry) <= observed
                or queue_instant(record.heartbeat_at) <= stale_before
            ]
            return tuple(
                sorted(
                    selected,
                    key=lambda record: (
                        queue_instant(record.claimed_at),
                        record.outbox_id,
                        record.lease_epoch,
                    ),
                )
            )


def _require_concluded_permit(
    current: LeaseRecord,
    supplied: ReconciliationProbePermit | None,
) -> None:
    held = current.probe_permit
    if held is None:
        if supplied is not None:
            raise LeaseConflict("supplied probe permit is no longer current")
        return
    if supplied != held or held.state is not ReconciliationProbePermitState.CONCLUDED:
        raise LeaseConflict("active or stale probe generation cannot mutate the lease")


__all__ = ["SqliteEffectQueue"]
