"""SQLite connection and canonical row helpers for the effect queue adapter.

Lifecycle policy stays in :mod:`sqlite_effect_queue`; this module owns the
transaction boundary, schema audit, durable row codec, and journal append path.

# KG: apt-tpa-legion-engine-canon-2026-06-12
# Design: ADRs/apt-vnext-slice2-effect-runtime-2026-07-14.md
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import sqlite3
from threading import RLock
from typing import Literal, cast

from engine.apt_runtime.domain.canonical import canonical_json_bytes, normalize_text
from engine.apt_runtime.domain.effect_runtime import (
    ResourceAccess,
    ResourceClaim,
    RuntimeUsage,
)
from engine.apt_runtime.domain.events import EventSchemaError, validate_rfc3339_utc_z
from engine.apt_runtime.ports.effect_queue import (
    EffectQueueCorruption,
    EffectQueueError,
    LeaseConflict,
    LeaseNotFound,
    LeaseRecord,
    LeaseRequest,
    LeaseStatus,
    ResourceClaimConflict,
    TERMINAL_LEASE_STATUSES,
)
from engine.apt_runtime.ports.event_store import StoreCorruption

from ._effect_queue_codec import (
    encode_budget,
    encode_claims,
    encode_probe_conclusion,
    lease_from_row,
)
from ._sqlite_effect_queue_integrity import (
    append_journal,
    assert_usage_shape,
    load_usage,
    validate_epoch_sequence,
    validate_lease_journal,
)
from ._sqlite_effect_queue_schema import (
    QUEUE_SCHEMA,
    QUEUE_SCHEMA_VERSION,
    EffectQueueSchemaError,
    validate_effect_queue_schema,
)
from ._store_codec import outbox_from_row


NONTERMINAL_LEASE_VALUES = tuple(
    status.value for status in LeaseStatus if status not in TERMINAL_LEASE_STATUSES
)


def queue_text(name: str, value: object) -> str:
    """Validate and NFC-normalize an operational identity."""

    if not isinstance(value, str) or not value:
        raise EffectQueueError(f"{name} must be a non-empty string")
    normalized = normalize_text(value)
    if "\x00" in normalized:
        raise EffectQueueError(f"{name} cannot contain U+0000")
    return normalized


def queue_timestamp(name: str, value: object) -> str:
    """Validate the queue's canonical UTC-Z timestamp profile."""

    text = queue_text(name, value)
    try:
        validate_rfc3339_utc_z(name, text)
    except EventSchemaError as exc:
        raise EffectQueueError(str(exc)) from exc
    return text


def queue_instant(value: str) -> datetime:
    """Parse a previously validated UTC-Z timestamp for chronological checks."""

    return datetime.fromisoformat(value[:-1] + "+00:00")


def require_at_or_after(name: str, value: str, floor: str) -> None:
    """Fence chronologically stale operational mutations."""

    if queue_instant(value) < queue_instant(floor):
        raise LeaseConflict(f"{name} cannot precede {floor!r}")


def _permit_values(record: LeaseRecord) -> tuple[object, ...]:
    permit = record.probe_permit
    if permit is None:
        return (None, None, None, None, None, None, None)
    conclusion_json: bytes | None = None
    conclusion_hash: str | None = None
    if permit.conclusion is not None:
        conclusion_json, conclusion_hash = encode_probe_conclusion(permit.conclusion)
    return (
        permit.permit_token,
        permit.state.value,
        permit.acquired_at,
        permit.expires_at,
        permit.concluded_at,
        conclusion_json,
        conclusion_hash,
    )


class _QueueTransaction:
    """Lock-scoped SQLite transaction that normalizes backend failures."""

    def __init__(self, queue: "_SqliteEffectQueueBackend", *, write: bool, operation: str) -> None:
        self._queue = queue
        self._write = write
        self._operation = operation

    def __enter__(self) -> None:
        self._queue._lock.acquire()
        try:
            self._queue._connection.execute("BEGIN IMMEDIATE" if self._write else "BEGIN")
        except sqlite3.DatabaseError as exc:
            self._queue._lock.release()
            raise EffectQueueError(f"failed to begin {self._operation} in SQLite: {exc}") from exc
        except BaseException:
            self._queue._lock.release()
            raise

    def __exit__(self, error_type: object, error: object, traceback: object) -> Literal[False]:
        try:
            if error_type is None:
                try:
                    self._queue._connection.execute("COMMIT")
                except sqlite3.DatabaseError as exc:
                    self._queue._rollback()
                    raise EffectQueueError(
                        f"failed to commit {self._operation} in SQLite: {exc}"
                    ) from exc
                return False
            self._queue._rollback()
            if isinstance(error, (EffectQueueError, KeyboardInterrupt, SystemExit)):
                return False
            if isinstance(error, StoreCorruption):
                raise EffectQueueCorruption(str(error)) from error
            if isinstance(error, sqlite3.DatabaseError):
                raise EffectQueueError(f"failed to {self._operation} in SQLite: {error}") from error
            return False
        finally:
            self._queue._lock.release()


class _SqliteEffectQueueBackend:
    """Private storage base used by the public lifecycle adapter."""

    def __init__(self, database: str | Path, *, busy_timeout_ms: int = 5_000) -> None:
        if (
            isinstance(busy_timeout_ms, bool)
            or not isinstance(busy_timeout_ms, int)
            or busy_timeout_ms < 1
        ):
            raise EffectQueueError("busy_timeout_ms must be a positive integer")
        self._database = str(database)
        self._lock = RLock()
        try:
            self._connection = sqlite3.connect(
                self._database,
                isolation_level=None,
                timeout=busy_timeout_ms / 1_000,
                check_same_thread=False,
            )
            self._connection.row_factory = sqlite3.Row
            self._connection.execute("PRAGMA foreign_keys = ON")
            self._connection.execute(f"PRAGMA busy_timeout = {busy_timeout_ms}")
            if self._database != ":memory:":
                self._connection.execute("PRAGMA journal_mode = WAL")
            self._connection.execute("PRAGMA synchronous = FULL")
        except sqlite3.DatabaseError as exc:
            raise EffectQueueError(f"failed to open SQLite effect queue: {exc}") from exc

    def init_schema(self) -> None:
        """Create queue v2 atomically, then verify its exact physical signature."""

        with self._lock:
            try:
                self._connection.executescript(f"BEGIN IMMEDIATE;\n{QUEUE_SCHEMA}")
                outbox_table = self._connection.execute(
                    "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'apt_outbox'"
                ).fetchone()
                if outbox_table is None:
                    raise EffectQueueCorruption(
                        "SQLite effect queue requires an initialized apt_outbox table"
                    )
                self._connection.execute(
                    "INSERT OR IGNORE INTO effect_runtime_schema(singleton, schema_version) "
                    "VALUES (1, ?)",
                    (QUEUE_SCHEMA_VERSION,),
                )
                rows = self._connection.execute(
                    "SELECT singleton, schema_version FROM effect_runtime_schema"
                ).fetchall()
                if len(rows) != 1 or tuple(rows[0]) != (1, QUEUE_SCHEMA_VERSION):
                    raise EffectQueueCorruption(
                        "SQLite effect-runtime schema version marker is incompatible"
                    )
                try:
                    validate_effect_queue_schema(self._connection)
                except EffectQueueSchemaError as exc:
                    raise EffectQueueCorruption(str(exc)) from exc
                self._audit_foreign_keys()
                self._connection.execute("COMMIT")
            except EffectQueueError:
                self._rollback()
                raise
            except sqlite3.DatabaseError as exc:
                self._rollback()
                raise EffectQueueError(f"failed to initialize SQLite effect queue: {exc}") from exc
            except BaseException:
                self._rollback()
                raise

    def _audit_foreign_keys(self) -> None:
        for table in (
            "effect_runtime_leases",
            "effect_runtime_resource_claims",
            "effect_runtime_usage",
            "effect_runtime_journal",
            "effect_runtime_journal_heads",
        ):
            if self._connection.execute(f"PRAGMA foreign_key_check({table})").fetchall():
                raise EffectQueueCorruption(
                    f"SQLite effect-runtime foreign-key corruption in {table}"
                )

    def close(self) -> None:
        """Close the adapter-owned connection."""

        with self._lock:
            self._connection.close()

    def _write_transaction(self, operation: str) -> _QueueTransaction:
        return _QueueTransaction(self, write=True, operation=operation)

    def _read_transaction(self, operation: str) -> _QueueTransaction:
        return _QueueTransaction(self, write=False, operation=operation)

    def _rollback(self) -> None:
        if self._connection.in_transaction:
            self._connection.execute("ROLLBACK")

    def _verify_outbox(self, request: LeaseRequest) -> None:
        row = self._outbox_row(request.outbox.outbox_id)
        if row is None:
            raise LeaseNotFound(f"outbox {request.outbox.outbox_id!r} is not durably requested")
        try:
            stored = outbox_from_row(row)
        except StoreCorruption as exc:
            raise EffectQueueCorruption(str(exc)) from exc
        if stored != request.outbox:
            raise LeaseConflict("lease request does not exactly match immutable apt_outbox")

    def _require_outbox_id(self, outbox_id: str) -> None:
        row = self._outbox_row(outbox_id)
        if row is None:
            raise LeaseNotFound(f"outbox {outbox_id!r} is not durably requested")
        try:
            outbox_from_row(row)
        except StoreCorruption as exc:
            raise EffectQueueCorruption(str(exc)) from exc

    def _outbox_row(self, outbox_id: str) -> sqlite3.Row | None:
        return self._connection.execute(
            "SELECT outbox_id, stream_id, effect_id, command_id, payload_json, "
            "payload_hash, created_at FROM apt_outbox WHERE outbox_id = ?",
            (outbox_id,),
        ).fetchone()

    def _insert_lease(self, record: LeaseRecord) -> None:
        claims_blob, claims_hash = encode_claims(record.resource_claims)
        budget_blob, budget_hash = encode_budget(record.budget)
        permit_values = _permit_values(record)
        self._connection.execute(
            "INSERT INTO effect_runtime_leases("
            "lease_token, outbox_id, stream_id, effect_id, lease_epoch, lease_owner, "
            "status, claimed_at, activated_at, heartbeat_at, lease_expiry, attempt, "
            "claims_json, claims_hash, budget_json, budget_hash, grant_ref, grant_hash, "
            "config_version, authorization_ref, authorization_hash, probe_generation, "
            "probe_token, probe_state, probe_acquired_at, probe_expires_at, "
            "probe_concluded_at, probe_conclusion_json, probe_conclusion_hash, "
            "reconciliation_ref, "
            "reason, completed_at) VALUES ("
            "?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, "
            "?, ?, ?, ?, ?, ?, ?, ?)",
            (
                record.lease_token,
                record.outbox_id,
                record.stream_id,
                record.effect_id,
                record.lease_epoch,
                record.lease_owner,
                record.status.value,
                record.claimed_at,
                record.activated_at,
                record.heartbeat_at,
                record.lease_expiry,
                record.attempt,
                claims_blob,
                claims_hash,
                budget_blob,
                budget_hash,
                record.grant_ref,
                record.grant_hash,
                record.config_version,
                record.authorization_ref,
                record.authorization_hash,
                record.probe_generation,
                *permit_values,
                record.reconciliation_ref,
                record.reason,
                record.completed_at,
            ),
        )

    def _update_lease(self, record: LeaseRecord) -> None:
        permit_values = _permit_values(record)
        result = self._connection.execute(
            "UPDATE effect_runtime_leases SET status = ?, activated_at = ?, heartbeat_at = ?, "
            "lease_expiry = ?, attempt = ?, probe_generation = ?, probe_token = ?, "
            "probe_state = ?, probe_acquired_at = ?, probe_expires_at = ?, "
            "probe_concluded_at = ?, probe_conclusion_json = ?, probe_conclusion_hash = ?, "
            "reconciliation_ref = ?, reason = ?, completed_at = ? "
            "WHERE lease_token = ?",
            (
                record.status.value,
                record.activated_at,
                record.heartbeat_at,
                record.lease_expiry,
                record.attempt,
                record.probe_generation,
                *permit_values,
                record.reconciliation_ref,
                record.reason,
                record.completed_at,
                record.lease_token,
            ),
        )
        if result.rowcount != 1:
            raise EffectQueueCorruption("effect lease disappeared during fenced update")

    def _decoded_record(self, lease_token: str) -> LeaseRecord | None:
        row = self._connection.execute(
            "SELECT * FROM effect_runtime_leases WHERE lease_token = ?", (lease_token,)
        ).fetchone()
        if row is None:
            return None
        claim_rows = self._connection.execute(
            "SELECT resource_key, access FROM effect_runtime_resource_claims "
            "WHERE lease_token = ? ORDER BY resource_key, access",
            (lease_token,),
        ).fetchall()
        try:
            claims = tuple(
                sorted(
                    (
                        ResourceClaim(
                            resource_key=cast(str, item["resource_key"]),
                            access=ResourceAccess(item["access"]),
                        )
                        for item in claim_rows
                    ),
                    key=canonical_json_bytes,
                )
            )
            record = lease_from_row(row, claims)
        except StoreCorruption as exc:
            raise EffectQueueCorruption(str(exc)) from exc
        except (TypeError, ValueError) as exc:
            raise EffectQueueCorruption(f"stored resource claim is invalid: {exc}") from exc
        return record

    def _validate_outbox_epochs(self, record: LeaseRecord) -> None:
        outbox_row = self._outbox_row(record.outbox_id)
        if outbox_row is None:
            raise EffectQueueCorruption("effect lease references a missing apt_outbox row")
        try:
            outbox = outbox_from_row(outbox_row)
        except StoreCorruption as exc:
            raise EffectQueueCorruption(str(exc)) from exc
        validate_epoch_sequence(self._connection, record.outbox_id)
        rows = self._connection.execute(
            "SELECT lease_token FROM effect_runtime_leases "
            "WHERE outbox_id = ? ORDER BY lease_epoch",
            (record.outbox_id,),
        ).fetchall()
        for row in rows:
            token = cast(str, row["lease_token"])
            candidate = record if token == record.lease_token else self._decoded_record(token)
            if candidate is None:  # pragma: no cover - selected in the same transaction
                raise EffectQueueCorruption("effect lease disappeared during epoch audit")
            if (candidate.stream_id, candidate.effect_id) != (
                outbox.stream_id,
                outbox.effect_id,
            ):
                raise EffectQueueCorruption(
                    "effect lease identity differs from immutable apt_outbox"
                )
            validate_lease_journal(self._connection, candidate)

    def _record(self, lease_token: str) -> LeaseRecord | None:
        record = self._decoded_record(lease_token)
        if record is None:
            return None
        self._validate_outbox_epochs(record)
        return record

    def _required_record(self, lease_token: str) -> LeaseRecord:
        record = self._record(lease_token)
        if record is None:
            raise LeaseNotFound(f"lease_token {lease_token!r} does not exist")
        return record

    def _latest_for_outbox(self, outbox_id: str) -> LeaseRecord | None:
        row = self._connection.execute(
            "SELECT lease_token FROM effect_runtime_leases "
            "WHERE outbox_id = ? ORDER BY lease_epoch DESC LIMIT 1",
            (outbox_id,),
        ).fetchone()
        if row is None:
            return None
        return self._required_record(cast(str, row["lease_token"]))

    def _assert_resource_claims_available(self, requested: tuple[ResourceClaim, ...]) -> None:
        status_slots = ", ".join("?" for _ in NONTERMINAL_LEASE_VALUES)
        rows = self._connection.execute(
            "SELECT lease_token FROM effect_runtime_leases "
            f"WHERE status IN ({status_slots}) ORDER BY lease_token",
            NONTERMINAL_LEASE_VALUES,
        ).fetchall()
        for row in rows:
            lease = self._required_record(cast(str, row["lease_token"]))
            for held in lease.resource_claims:
                for claim in requested:
                    if claim.conflicts_with(held):
                        raise ResourceClaimConflict(
                            f"resource scope {claim.resource_key!r} conflicts with held "
                            f"scope {held.resource_key!r} on lease {lease.lease_token!r} "
                            f"for outbox {lease.outbox_id!r}"
                        )

    def _append_state_journal(self, action: str, record: LeaseRecord, occurred_at: str) -> None:
        append_journal(
            self._connection,
            lease_token=record.lease_token,
            action=action,
            occurred_at=occurred_at,
            detail={"lease": record},
        )

    def _append_usage_journal(
        self,
        lease_token: str,
        delta: RuntimeUsage,
        usage: RuntimeUsage,
        occurred_at: str,
    ) -> None:
        append_journal(
            self._connection,
            lease_token=lease_token,
            action="USAGE_RECORDED",
            occurred_at=occurred_at,
            detail={"delta": delta, "usage": usage},
        )

    def _assert_usage_shape(self, outbox_id: str, *, has_prior: bool) -> None:
        assert_usage_shape(self._connection, outbox_id, has_prior=has_prior)

    def _load_usage(self, outbox_id: str) -> RuntimeUsage:
        return load_usage(self._connection, outbox_id)

    @staticmethod
    def _require_status(record: LeaseRecord, allowed: set[LeaseStatus], operation: str) -> None:
        if record.status not in allowed:
            expected = ", ".join(sorted(status.value for status in allowed))
            raise LeaseConflict(
                f"cannot {operation} {record.status.value} lease; expected {expected}"
            )

    @staticmethod
    def _require_owner(record: LeaseRecord, lease_owner: str) -> None:
        if record.lease_owner != lease_owner:
            raise LeaseConflict(
                f"lease owner {lease_owner!r} does not hold token {record.lease_token!r}"
            )


__all__ = [
    "NONTERMINAL_LEASE_VALUES",
    "_SqliteEffectQueueBackend",
    "queue_instant",
    "queue_text",
    "queue_timestamp",
    "require_at_or_after",
]
