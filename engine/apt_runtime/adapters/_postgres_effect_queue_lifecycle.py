"""Lease lifecycle operations for the PostgreSQL effect queue adapter."""

from __future__ import annotations

from collections.abc import Mapping
from contextlib import AbstractContextManager
from typing import TYPE_CHECKING, NoReturn

from engine.apt_runtime.domain.canonical import MAX_SIGNED_64
from engine.apt_runtime.domain.effect_runtime import ResourceClaim
from engine.apt_runtime.ports.effect_queue import (
    EffectQueueCorruption,
    EffectQueueError,
    LeaseConflict,
    LeaseRecord,
    LeaseRequest,
    LeaseStatus,
    ReconciliationProbePermit,
)
from engine.apt_runtime.ports.event_store import OutboxRecord

from ._effect_queue_codec import encode_budget, encode_claims
from ._postgres_effect_queue_support import (
    instant,
    positive_attempt,
    require_concluded_permit,
    text,
    timestamp,
)

if TYPE_CHECKING:
    from psycopg import Connection
    from psycopg.rows import DictRow


def _validate_retry_authority(authority: LeaseRecord, request: LeaseRequest) -> None:
    if authority.budget != request.budget:
        raise LeaseConflict("runtime budget cannot change across lease epochs")
    if authority.resource_claims != request.resource_claims:
        raise LeaseConflict("resource claims cannot change across lease epochs")
    grant_identity = (
        "grant_ref",
        "grant_hash",
        "config_version",
        "authorization_ref",
        "authorization_hash",
    )
    if any(getattr(authority, field) != getattr(request, field) for field in grant_identity):
        raise LeaseConflict("execution grant cannot change across lease epochs")


class PostgresEffectQueueLifecycleMixin:
    """Reservation, activation, execution fencing, reconciliation, and finish."""

    if TYPE_CHECKING:
        _database_error: type[Exception]

        def _connect(self, *, read_only: bool = False) -> Connection[DictRow]: ...
        def _durable_write(self, connection: Connection[DictRow]) -> None: ...
        def _advisory_lock(
            self, connection: Connection[DictRow], namespace: str, identity: str
        ) -> None: ...
        def _verify_requested_outbox(
            self, connection: Connection[DictRow], requested: OutboxRecord
        ) -> None: ...
        def _lease_row(
            self,
            connection: Connection[DictRow],
            lease_token: str,
            *,
            for_update: bool = False,
        ) -> DictRow | None: ...
        def _decode_lease(
            self,
            connection: Connection[DictRow],
            row: Mapping[str, object],
            *,
            validate_context: bool,
        ) -> LeaseRecord: ...
        def _ensure_usage_ledger(
            self,
            connection: Connection[DictRow],
            *,
            outbox_id: str,
            initialized_at: str,
            prior_exists: bool,
        ) -> None: ...
        def _assert_resources_available(
            self,
            connection: Connection[DictRow],
            requested: tuple[ResourceClaim, ...],
        ) -> None: ...
        def _append_state_journal(
            self,
            connection: Connection[DictRow],
            lease_token: str,
            action: str,
            occurred_at: str,
        ) -> None: ...
        def _required_lease(
            self, connection: Connection[DictRow], lease_token: str
        ) -> LeaseRecord: ...
        def _hit_failpoint(self, location: str) -> None: ...
        def _write_lease(
            self, lease_token: str
        ) -> AbstractContextManager[tuple[Connection[DictRow], LeaseRecord]]: ...
        def _require_live_observation(
            self, current: LeaseRecord, observed_at: str, field_name: str
        ) -> None: ...
        def _raise_database_error(self, operation: str, exc: Exception) -> NoReturn: ...

    def _activated_retry_authority(
        self,
        connection: Connection[DictRow],
        request: LeaseRequest,
        prior: LeaseRecord,
    ) -> LeaseRecord | None:
        if prior.activated_at is not None:
            return prior
        row = connection.execute(
            "SELECT * FROM effect_runtime_leases WHERE outbox_id = %s "
            "AND activated_at IS NOT NULL ORDER BY lease_epoch DESC LIMIT 1 FOR UPDATE",
            (request.outbox.outbox_id,),
        ).fetchone()
        return None if row is None else self._decode_lease(connection, row, validate_context=False)

    def _prior_for_request(
        self, connection: Connection[DictRow], request: LeaseRequest
    ) -> LeaseRecord | None:
        row = connection.execute(
            "SELECT * FROM effect_runtime_leases WHERE outbox_id = %s "
            "ORDER BY lease_epoch DESC LIMIT 1 FOR UPDATE",
            (request.outbox.outbox_id,),
        ).fetchone()
        if row is None:
            return None
        prior = self._decode_lease(connection, row, validate_context=True)
        if prior.status not in {LeaseStatus.FAILED, LeaseStatus.ABANDONED}:
            raise LeaseConflict(
                f"{prior.status.value} is nonterminal or absorbing and cannot be retried"
            )
        authority = self._activated_retry_authority(connection, request, prior)
        if authority is not None:
            _validate_retry_authority(authority, request)
        if prior.completed_at is None or instant(request.claimed_at) < instant(prior.completed_at):
            raise LeaseConflict("retry claimed_at cannot precede prior completion")
        return prior

    def _insert_reservation(
        self,
        connection: Connection[DictRow],
        request: LeaseRequest,
        epoch: int,
    ) -> None:
        claims_json, claims_hash = encode_claims(request.resource_claims)
        budget_json, budget_hash = encode_budget(request.budget)
        connection.execute(
            "INSERT INTO effect_runtime_leases"
            "(lease_token, outbox_id, stream_id, effect_id, lease_epoch, lease_owner, "
            "status, claimed_at, activated_at, heartbeat_at, lease_expiry, attempt, "
            "claims_json, claims_hash, budget_json, budget_hash, grant_ref, grant_hash, "
            "config_version, authorization_ref, authorization_hash, probe_generation, "
            "probe_token, probe_state, probe_acquired_at, probe_expires_at, "
            "probe_concluded_at, probe_conclusion_json, probe_conclusion_hash, "
            "reconciliation_ref, "
            "reason, completed_at) VALUES "
            "(%s, %s, %s, %s, %s, %s, %s, %s, NULL, %s, %s, %s, %s, %s, %s, %s, "
            "%s, %s, %s, %s, %s, 0, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, "
            "NULL, NULL)",
            (
                request.lease_token,
                request.outbox.outbox_id,
                request.outbox.stream_id,
                request.outbox.effect_id,
                epoch,
                request.lease_owner,
                LeaseStatus.RESERVED.value,
                request.claimed_at,
                request.claimed_at,
                request.lease_expiry,
                0,
                claims_json,
                claims_hash,
                budget_json,
                budget_hash,
                request.grant_ref,
                request.grant_hash,
                request.config_version,
                request.authorization_ref,
                request.authorization_hash,
            ),
        )
        for claim in request.resource_claims:
            connection.execute(
                "INSERT INTO effect_runtime_resource_claims"
                "(lease_token, resource_key, access) VALUES (%s, %s, %s)",
                (request.lease_token, claim.resource_key, claim.access.value),
            )

    def _reserve_locked(
        self, connection: Connection[DictRow], request: LeaseRequest
    ) -> LeaseRecord:
        self._verify_requested_outbox(connection, request.outbox)
        if self._lease_row(connection, request.lease_token, for_update=True) is not None:
            raise LeaseConflict("lease_token already exists")
        prior = self._prior_for_request(connection, request)
        self._ensure_usage_ledger(
            connection,
            outbox_id=request.outbox.outbox_id,
            initialized_at=request.claimed_at,
            prior_exists=prior is not None,
        )
        self._assert_resources_available(connection, request.resource_claims)
        epoch = 1 if prior is None else prior.lease_epoch + 1
        if epoch > MAX_SIGNED_64:
            raise EffectQueueCorruption("lease epoch exceeds signed 64-bit range")
        self._insert_reservation(connection, request, epoch)
        self._append_state_journal(connection, request.lease_token, "RESERVED", request.claimed_at)
        self._hit_failpoint("reserve_before_commit")
        return self._required_lease(connection, request.lease_token)

    def reserve(self, request: LeaseRequest) -> LeaseRecord:
        """Reserve an exact immutable outbox row under a new fencing token."""

        if not isinstance(request, LeaseRequest):
            raise ValueError("request must be a LeaseRequest")
        try:
            with self._connect() as connection:
                with connection.transaction():
                    self._durable_write(connection)
                    self._advisory_lock(connection, "outbox", request.outbox.outbox_id)
                    self._advisory_lock(connection, "resource-index", "all")
                    for resource_key in sorted(
                        claim.resource_key for claim in request.resource_claims
                    ):
                        self._advisory_lock(connection, "resource", resource_key)
                    return self._reserve_locked(connection, request)
        except EffectQueueError:
            raise
        except Exception as exc:
            self._raise_database_error("reserve PostgreSQL effect lease", exc)

    def activate(self, lease_token: str, *, activated_at: str) -> LeaseRecord:
        """Promote only a live RESERVED row after EffectLeased commits."""

        lease_token = text("lease_token", lease_token)
        activated_at = timestamp("activated_at", activated_at)
        try:
            with self._write_lease(lease_token) as (connection, current):
                if current.status is LeaseStatus.ACTIVE and current.activated_at == activated_at:
                    return current
                if current.status is not LeaseStatus.RESERVED:
                    raise LeaseConflict("only a RESERVED lease can be activated")
                self._require_live_observation(current, activated_at, "activated_at")
                connection.execute(
                    "UPDATE effect_runtime_leases SET status = %s, activated_at = %s, "
                    "heartbeat_at = %s WHERE lease_token = %s",
                    (
                        LeaseStatus.ACTIVE.value,
                        activated_at,
                        activated_at,
                        lease_token,
                    ),
                )
                self._append_state_journal(connection, lease_token, "ACTIVATED", activated_at)
                self._hit_failpoint("activate_before_commit")
                return self._required_lease(connection, lease_token)
        except EffectQueueError:
            raise
        except Exception as exc:
            self._raise_database_error("activate PostgreSQL effect lease", exc)

    def heartbeat(
        self,
        lease_token: str,
        *,
        lease_owner: str,
        heartbeat_at: str,
        lease_expiry: str,
    ) -> LeaseRecord:
        """Renew an ACTIVE/RUNNING token without reviving an expired lease."""

        lease_token = text("lease_token", lease_token)
        lease_owner = text("lease_owner", lease_owner)
        heartbeat_at = timestamp("heartbeat_at", heartbeat_at)
        lease_expiry = timestamp("lease_expiry", lease_expiry)
        if instant(lease_expiry) <= instant(heartbeat_at):
            raise ValueError("lease_expiry must be later than heartbeat_at")
        try:
            with self._write_lease(lease_token) as (connection, current):
                if current.status not in {
                    LeaseStatus.ACTIVE,
                    LeaseStatus.RUNNING,
                }:
                    raise LeaseConflict("heartbeat requires an ACTIVE or RUNNING lease")
                if current.lease_owner != lease_owner:
                    raise LeaseConflict("heartbeat lease_owner does not own the fencing token")
                if current.heartbeat_at == heartbeat_at and current.lease_expiry == lease_expiry:
                    return current
                self._require_live_observation(current, heartbeat_at, "heartbeat_at")
                if instant(lease_expiry) <= instant(current.lease_expiry):
                    raise LeaseConflict("heartbeat must extend lease_expiry")
                connection.execute(
                    "UPDATE effect_runtime_leases SET heartbeat_at = %s, lease_expiry = %s "
                    "WHERE lease_token = %s",
                    (heartbeat_at, lease_expiry, lease_token),
                )
                self._append_state_journal(
                    connection,
                    lease_token,
                    "HEARTBEAT_RECORDED",
                    heartbeat_at,
                )
                self._hit_failpoint("heartbeat_before_commit")
                return self._required_lease(connection, lease_token)
        except EffectQueueError:
            raise
        except Exception as exc:
            self._raise_database_error("heartbeat PostgreSQL effect lease", exc)

    def start(
        self,
        lease_token: str,
        *,
        lease_owner: str,
        attempt: int,
        started_at: str,
    ) -> LeaseRecord:
        """Atomically enter RUNNING once; duplicate delivery must reconcile."""

        lease_token = text("lease_token", lease_token)
        lease_owner = text("lease_owner", lease_owner)
        attempt = positive_attempt(attempt)
        started_at = timestamp("started_at", started_at)
        try:
            with self._write_lease(lease_token) as (connection, current):
                if current.status is not LeaseStatus.ACTIVE:
                    raise LeaseConflict("start requires an ACTIVE lease")
                if current.lease_owner != lease_owner:
                    raise LeaseConflict("start lease_owner does not own the fencing token")
                self._require_live_observation(current, started_at, "started_at")
                row = connection.execute(
                    "SELECT COALESCE(MAX(attempt), 0) AS max_attempt "
                    "FROM effect_runtime_leases WHERE outbox_id = %s AND lease_token <> %s",
                    (current.outbox_id, current.lease_token),
                ).fetchone()
                if row is None:  # pragma: no cover - aggregate returns one row
                    raise EffectQueueCorruption("could not inspect prior effect attempts")
                if attempt <= row["max_attempt"]:
                    raise LeaseConflict(
                        f"attempt {attempt} is not newer than prior attempt {row['max_attempt']}"
                    )
                connection.execute(
                    "UPDATE effect_runtime_leases SET status = %s, attempt = %s, "
                    "heartbeat_at = %s WHERE lease_token = %s",
                    (
                        LeaseStatus.RUNNING.value,
                        attempt,
                        started_at,
                        lease_token,
                    ),
                )
                self._append_state_journal(connection, lease_token, "STARTED", started_at)
                self._hit_failpoint("start_before_commit")
                return self._required_lease(connection, lease_token)
        except EffectQueueError:
            raise
        except Exception as exc:
            self._raise_database_error("start PostgreSQL effect lease", exc)

    def mark_reconciling(
        self,
        lease_token: str,
        *,
        observed_at: str,
        reconciliation_ref: str,
        reason: str,
        probe_permit: ReconciliationProbePermit | None = None,
    ) -> LeaseRecord:
        """Retain claims while an ambiguous outcome is repeatedly reconciled."""

        lease_token = text("lease_token", lease_token)
        observed_at = timestamp("observed_at", observed_at)
        reconciliation_ref = text("reconciliation_ref", reconciliation_ref)
        reason = text("reason", reason)
        try:
            with self._write_lease(lease_token) as (connection, current):
                if current.status is LeaseStatus.RECONCILING:
                    if (
                        current.reconciliation_ref == reconciliation_ref
                        and current.reason == reason
                        and current.probe_permit is None
                    ):
                        return current
                elif current.status not in {
                    LeaseStatus.ACTIVE,
                    LeaseStatus.RUNNING,
                }:
                    raise LeaseConflict("reconciliation requires ACTIVE, RUNNING, or RECONCILING")
                if instant(observed_at) < instant(current.heartbeat_at):
                    raise LeaseConflict("observed_at cannot precede the current heartbeat")
                require_concluded_permit(current, probe_permit)
                connection.execute(
                    "UPDATE effect_runtime_leases SET status = %s, probe_token = NULL, "
                    "probe_state = NULL, probe_acquired_at = NULL, probe_expires_at = NULL, "
                    "probe_concluded_at = NULL, probe_conclusion_json = NULL, "
                    "probe_conclusion_hash = NULL, reconciliation_ref = %s, reason = %s "
                    "WHERE lease_token = %s",
                    (
                        LeaseStatus.RECONCILING.value,
                        reconciliation_ref,
                        reason,
                        lease_token,
                    ),
                )
                self._append_state_journal(connection, lease_token, "RECONCILING", observed_at)
                self._hit_failpoint("reconciling_before_commit")
                return self._required_lease(connection, lease_token)
        except EffectQueueError:
            raise
        except Exception as exc:
            self._raise_database_error("mark PostgreSQL effect lease reconciling", exc)


__all__ = ["PostgresEffectQueueLifecycleMixin"]
