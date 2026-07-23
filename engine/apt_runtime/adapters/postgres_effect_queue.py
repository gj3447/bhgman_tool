"""PostgreSQL operational effect queue with fencing and resource exclusion.

Every public operation owns a short-lived psycopg connection. Reservations
serialize first on immutable outbox identity and then on sorted resource
identities. External execution may cross the ACTIVE -> RUNNING fence exactly
once; duplicate delivery after that fence is recovery/reconciliation work.

# KG: apt-tpa-legion-engine-canon-2026-06-12
# Design: ADRs/apt-vnext-slice2-effect-runtime-2026-07-14.md
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, cast

from engine.apt_runtime.domain.canonical import MAX_SIGNED_64
from engine.apt_runtime.domain.effect_runtime import RuntimeUsage
from engine.apt_runtime.ports.effect_queue import (
    EffectQueue,
    EffectQueueCorruption,
    EffectQueueError,
    LeaseConflict,
    LeaseNotFound,
    LeaseRecord,
    LeaseStatus,
    ReconciliationProbeAcquisition,
    ReconciliationProbeConclusion,
    ReconciliationProbeConflict,
    ReconciliationProbeExhausted,
    ReconciliationProbePermit,
    ReconciliationProbePermitState,
)

from ._effect_queue_codec import encode_probe_conclusion, encode_usage
from ._postgres_effect_queue_connection import (
    PostgresEffectQueueConnectionMixin,
)
from ._postgres_effect_queue_finish import PostgresEffectQueueFinishMixin
from ._postgres_effect_queue_internals import (
    PostgresEffectQueueInternalsMixin,
)
from ._postgres_effect_queue_journal import PostgresEffectQueueJournalMixin
from ._postgres_effect_queue_lifecycle import (
    PostgresEffectQueueLifecycleMixin,
)
from ._postgres_effect_queue_schema import (
    EffectQueueSchemaSignatureError,
    QUEUE_SCHEMA_GUARD_STATEMENTS,
    QUEUE_SCHEMA_STATEMENTS,
    QUEUE_SCHEMA_VERSION,
    validate_effect_queue_schema_signature,
)
from ._postgres_effect_queue_support import (
    NONTERMINAL_VALUES,
    instant,
    text,
    timestamp,
)

if TYPE_CHECKING:
    from psycopg import Connection
    from psycopg.rows import DictRow, RowFactory


def _probe_takeover(prior: ReconciliationProbePermit | None, acquired_at: str) -> bool:
    if prior is None:
        return False
    if prior.state is ReconciliationProbePermitState.CONCLUDED:
        raise ReconciliationProbeConflict(
            "a concluded reconciliation probe awaits durable finalization"
        )
    if instant(acquired_at) < instant(prior.expires_at):
        raise ReconciliationProbeConflict("an unexpired reconciliation probe is already in flight")
    return True


class PostgresEffectQueue(
    PostgresEffectQueueConnectionMixin,
    PostgresEffectQueueJournalMixin,
    PostgresEffectQueueInternalsMixin,
    PostgresEffectQueueLifecycleMixin,
    PostgresEffectQueueFinishMixin,
    EffectQueue,
):
    """Durable PostgreSQL lease journal implementing the Slice 2 queue port."""

    def __init__(
        self,
        dsn: str,
        *,
        connect_timeout_seconds: int = 5,
        failpoint: Callable[[str], None] | None = None,
    ) -> None:
        self._dsn = text("dsn", dsn)
        if (
            isinstance(connect_timeout_seconds, bool)
            or not isinstance(connect_timeout_seconds, int)
            or connect_timeout_seconds < 1
        ):
            raise ValueError("connect_timeout_seconds must be a positive integer")
        if failpoint is not None and not callable(failpoint):
            raise ValueError("failpoint must be callable")
        try:
            import psycopg
            from psycopg import IsolationLevel
            from psycopg.rows import dict_row
        except ImportError as exc:  # pragma: no cover - minimal installation
            raise ImportError(
                "Install bhgman_tool[apt-postgres] to use PostgresEffectQueue"
            ) from exc
        self._connect_factory: Callable[..., Connection[DictRow]] = psycopg.connect
        self._row_factory: RowFactory[DictRow] = dict_row
        self._database_error: type[Exception] = psycopg.Error
        self._repeatable_read = IsolationLevel.REPEATABLE_READ
        self._connect_timeout_seconds = connect_timeout_seconds
        self._failpoint = failpoint

    def init_schema(self) -> None:
        """Create queue v2 atomically and reject physical signature drift."""

        try:
            with self._connect() as connection:
                with connection.transaction():
                    self._durable_write(connection)
                    self._advisory_lock(connection, "schema", "apt-effect-runtime-v2")
                    existing = connection.execute(
                        "SELECT EXISTS ("
                        "SELECT 1 FROM pg_catalog.pg_class AS c "
                        "JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace "
                        "WHERE n.nspname = current_schema() "
                        "AND c.relname = 'effect_runtime_schema' AND c.relkind = 'r'"
                        ") AS present"
                    ).fetchone()
                    fresh_schema = existing is None or not existing["present"]
                    for statement in QUEUE_SCHEMA_STATEMENTS:
                        connection.execute(statement)
                    if fresh_schema:
                        for statement in QUEUE_SCHEMA_GUARD_STATEMENTS:
                            connection.execute(statement)
                    connection.execute(
                        "INSERT INTO effect_runtime_schema(singleton, schema_version) "
                        "VALUES (1, %s) ON CONFLICT (singleton) DO NOTHING",
                        (QUEUE_SCHEMA_VERSION,),
                    )
                    row = connection.execute(
                        "SELECT schema_version FROM effect_runtime_schema WHERE singleton = 1"
                    ).fetchone()
                    if row is None or row["schema_version"] != QUEUE_SCHEMA_VERSION:
                        raise EffectQueueCorruption(
                            "PostgreSQL effect-runtime schema version is incompatible"
                        )
                    try:
                        validate_effect_queue_schema_signature(connection)
                    except EffectQueueSchemaSignatureError as exc:
                        raise EffectQueueCorruption(str(exc)) from exc
        except EffectQueueError:
            raise
        except Exception as exc:
            self._raise_database_error("initialize PostgreSQL effect-runtime schema", exc)

    def close(self) -> None:
        """Release adapter resources; every connection is operation-scoped."""

    def usage_for_outbox(self, outbox_id: str) -> RuntimeUsage:
        """Load accumulated usage, or zero for a known unreserved outbox."""

        outbox_id = text("outbox_id", outbox_id)
        try:
            with self._read_transaction() as connection:
                row = connection.execute(
                    "SELECT usage_json, usage_hash, updated_at "
                    "FROM effect_runtime_usage WHERE outbox_id = %s",
                    (outbox_id,),
                ).fetchone()
                if row is None:
                    outbox = connection.execute(
                        "SELECT * FROM apt_outbox WHERE outbox_id = %s",
                        (outbox_id,),
                    ).fetchone()
                    if outbox is None:
                        raise LeaseNotFound(f"unknown outbox {outbox_id!r}")
                    self._decode_outbox(outbox)
                    lease = connection.execute(
                        "SELECT 1 AS present FROM effect_runtime_leases "
                        "WHERE outbox_id = %s LIMIT 1",
                        (outbox_id,),
                    ).fetchone()
                    if lease is not None:
                        raise EffectQueueCorruption("lease epochs have no runtime usage ledger")
                    return RuntimeUsage()
                usage = self._decode_usage_row(row)
                latest = connection.execute(
                    "SELECT * FROM effect_runtime_leases WHERE outbox_id = %s "
                    "ORDER BY lease_epoch DESC LIMIT 1",
                    (outbox_id,),
                ).fetchone()
                if latest is None:
                    raise EffectQueueCorruption("usage ledger exists without a lease epoch")
                self._decode_lease(connection, latest, validate_context=True)
                return usage
        except EffectQueueError:
            raise
        except Exception as exc:
            self._raise_database_error("load PostgreSQL effect usage", exc)

    def record_usage(
        self,
        lease_token: str,
        *,
        delta: RuntimeUsage,
        observed_at: str,
    ) -> RuntimeUsage:
        """Atomically accumulate one explicit RUNNING/RECONCILING delta."""

        lease_token = text("lease_token", lease_token)
        if not isinstance(delta, RuntimeUsage):
            raise ValueError("delta must be RuntimeUsage")
        observed_at = timestamp("observed_at", observed_at)
        try:
            with self._write_lease(lease_token) as (connection, current):
                if current.status.value not in {"RUNNING", "RECONCILING"}:
                    raise LeaseConflict("usage requires a RUNNING or RECONCILING lease")
                if instant(observed_at) < instant(current.heartbeat_at):
                    raise LeaseConflict("observed_at cannot precede the current heartbeat")
                row = connection.execute(
                    "SELECT usage_json, usage_hash, updated_at "
                    "FROM effect_runtime_usage WHERE outbox_id = %s FOR UPDATE",
                    (current.outbox_id,),
                ).fetchone()
                if row is None:
                    raise EffectQueueCorruption("lease has no runtime usage ledger")
                accumulated = self._decode_usage_row(row)
                if instant(observed_at) < instant(cast(str, row["updated_at"])):
                    raise LeaseConflict("observed_at cannot precede the usage ledger")
                total = accumulated.add(delta)
                usage_json, usage_hash = encode_usage(total)
                connection.execute(
                    "UPDATE effect_runtime_usage SET usage_json = %s, usage_hash = %s, "
                    "updated_at = %s WHERE outbox_id = %s",
                    (
                        usage_json,
                        usage_hash,
                        observed_at,
                        current.outbox_id,
                    ),
                )
                self._append_journal(
                    connection,
                    lease_token,
                    "USAGE_RECORDED",
                    observed_at,
                    {"delta": delta, "usage": total},
                )
                self._hit_failpoint("usage_before_commit")
                return total
        except EffectQueueError:
            raise
        except Exception as exc:
            self._raise_database_error("record PostgreSQL effect usage", exc)

    def begin_reconciliation_probe(
        self,
        lease_token: str,
        *,
        permit_token: str,
        acquired_at: str,
        expires_at: str,
    ) -> ReconciliationProbeAcquisition:
        """Acquire or take over one generation in a row-locked transaction."""

        lease_token = text("lease_token", lease_token)
        permit_token = text("permit_token", permit_token)
        acquired_at = timestamp("acquired_at", acquired_at)
        expires_at = timestamp("expires_at", expires_at)
        if instant(expires_at) <= instant(acquired_at):
            raise LeaseConflict("probe expires_at must be later than acquired_at")
        try:
            with self._write_lease(lease_token) as (connection, current):
                if current.status is not LeaseStatus.RECONCILING:
                    raise LeaseConflict("probe permit requires a RECONCILING lease")
                if instant(acquired_at) < instant(current.heartbeat_at):
                    raise LeaseConflict("acquired_at cannot precede the current heartbeat")
                takeover = _probe_takeover(current.probe_permit, acquired_at)
                if current.probe_generation >= MAX_SIGNED_64:
                    raise EffectQueueCorruption("probe generation exceeds signed 64-bit range")
                row = connection.execute(
                    "SELECT usage_json, usage_hash, updated_at "
                    "FROM effect_runtime_usage WHERE outbox_id = %s FOR UPDATE",
                    (current.outbox_id,),
                ).fetchone()
                if row is None:
                    raise EffectQueueCorruption("lease has no runtime usage ledger")
                usage = self._decode_usage_row(row)
                charged = not takeover
                if (
                    charged
                    and usage.reconciliation_probes >= current.budget.max_reconciliation_probes
                ):
                    raise ReconciliationProbeExhausted(
                        "the reconciliation probe budget is exhausted"
                    )
                if instant(acquired_at) < instant(cast(str, row["updated_at"])):
                    raise LeaseConflict("acquired_at cannot precede the usage ledger")
                permit = ReconciliationProbePermit(
                    permit_token=permit_token,
                    generation=current.probe_generation + 1,
                    state=ReconciliationProbePermitState.ACTIVE,
                    acquired_at=acquired_at,
                    expires_at=expires_at,
                )
                connection.execute(
                    "UPDATE effect_runtime_leases SET probe_generation = %s, "
                    "probe_token = %s, probe_state = %s, probe_acquired_at = %s, "
                    "probe_expires_at = %s, probe_concluded_at = NULL, "
                    "probe_conclusion_json = NULL, probe_conclusion_hash = NULL "
                    "WHERE lease_token = %s",
                    (
                        permit.generation,
                        permit.permit_token,
                        permit.state.value,
                        permit.acquired_at,
                        permit.expires_at,
                        lease_token,
                    ),
                )
                self._append_state_journal(connection, lease_token, "PROBE_ACQUIRED", acquired_at)
                if charged:
                    delta = RuntimeUsage(reconciliation_probes=1)
                    usage = usage.add(delta)
                    usage_json, usage_hash = encode_usage(usage)
                    connection.execute(
                        "UPDATE effect_runtime_usage SET usage_json = %s, usage_hash = %s, "
                        "updated_at = %s WHERE outbox_id = %s",
                        (usage_json, usage_hash, acquired_at, current.outbox_id),
                    )
                    self._append_journal(
                        connection,
                        lease_token,
                        "USAGE_RECORDED",
                        acquired_at,
                        {"delta": delta, "usage": usage},
                    )
                return ReconciliationProbeAcquisition(permit, usage, charged)
        except EffectQueueError:
            raise
        except Exception as exc:
            self._raise_database_error("begin PostgreSQL reconciliation probe", exc)

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
        """Seal an exact live generation with crash-resumable observation data."""

        lease_token = text("lease_token", lease_token)
        if not isinstance(permit, ReconciliationProbePermit):
            raise LeaseConflict("permit must be a ReconciliationProbePermit")
        if permit.state is not ReconciliationProbePermitState.ACTIVE:
            raise LeaseConflict("only an ACTIVE permit can be concluded")
        if not isinstance(conclusion, ReconciliationProbeConclusion):
            raise LeaseConflict("conclusion must be a ReconciliationProbeConclusion")
        concluded_at = timestamp("concluded_at", concluded_at)
        expires_at = timestamp("expires_at", expires_at)
        reconciliation_ref = text("reconciliation_ref", reconciliation_ref)
        reason = text("reason", reason)
        if instant(concluded_at) < instant(permit.acquired_at):
            raise LeaseConflict("concluded_at cannot precede permit acquisition")
        if instant(concluded_at) >= instant(permit.expires_at):
            raise ReconciliationProbeConflict("an expired probe generation cannot conclude")
        if instant(expires_at) <= instant(concluded_at):
            raise LeaseConflict("conclusion expires_at must be later than concluded_at")
        sealed = ReconciliationProbePermit(
            permit_token=permit.permit_token,
            generation=permit.generation,
            state=ReconciliationProbePermitState.CONCLUDED,
            acquired_at=permit.acquired_at,
            expires_at=expires_at,
            concluded_at=concluded_at,
            conclusion=conclusion,
        )
        conclusion_json, conclusion_hash = encode_probe_conclusion(conclusion)
        try:
            with self._write_lease(lease_token) as (connection, current):
                if current.status is not LeaseStatus.RECONCILING:
                    raise LeaseConflict("probe conclusion requires a RECONCILING lease")
                if current.probe_permit == sealed:
                    if (
                        current.reconciliation_ref == reconciliation_ref
                        and current.reason == reason
                    ):
                        return current
                    raise ReconciliationProbeConflict(
                        "sealed probe conclusion was replayed with different evidence"
                    )
                if current.probe_permit != permit:
                    raise ReconciliationProbeConflict(
                        "probe generation was expired, replaced, or otherwise fenced"
                    )
                connection.execute(
                    "UPDATE effect_runtime_leases SET probe_state = %s, "
                    "probe_expires_at = %s, probe_concluded_at = %s, "
                    "probe_conclusion_json = %s, probe_conclusion_hash = %s, "
                    "reconciliation_ref = %s, reason = %s WHERE lease_token = %s",
                    (
                        sealed.state.value,
                        sealed.expires_at,
                        sealed.concluded_at,
                        conclusion_json,
                        conclusion_hash,
                        reconciliation_ref,
                        reason,
                        lease_token,
                    ),
                )
                self._append_state_journal(connection, lease_token, "PROBE_CONCLUDED", concluded_at)
                return self._required_lease(connection, lease_token)
        except EffectQueueError:
            raise
        except Exception as exc:
            self._raise_database_error("conclude PostgreSQL reconciliation probe", exc)

    def load(self, lease_token: str) -> LeaseRecord | None:
        """Load one fully validated lease and append-only journal."""

        lease_token = text("lease_token", lease_token)
        try:
            with self._read_transaction() as connection:
                row = self._lease_row(connection, lease_token)
                return (
                    None
                    if row is None
                    else self._decode_lease(connection, row, validate_context=True)
                )
        except EffectQueueError:
            raise
        except Exception as exc:
            self._raise_database_error("load PostgreSQL effect lease", exc)

    def latest_for_outbox(self, outbox_id: str) -> LeaseRecord | None:
        """Load the highest validated monotonic epoch for an outbox row."""

        outbox_id = text("outbox_id", outbox_id)
        try:
            with self._read_transaction() as connection:
                row = connection.execute(
                    "SELECT * FROM effect_runtime_leases WHERE outbox_id = %s "
                    "ORDER BY lease_epoch DESC LIMIT 1",
                    (outbox_id,),
                ).fetchone()
                return (
                    None
                    if row is None
                    else self._decode_lease(connection, row, validate_context=True)
                )
        except EffectQueueError:
            raise
        except Exception as exc:
            self._raise_database_error("load latest PostgreSQL effect lease", exc)

    def recoverable(self, *, observed_at: str, heartbeat_before: str) -> tuple[LeaseRecord, ...]:
        """Return expired or stale leases using parsed UTC instants."""

        observed_at = timestamp("observed_at", observed_at)
        heartbeat_before = timestamp("heartbeat_before", heartbeat_before)
        observed = instant(observed_at)
        stale_before = instant(heartbeat_before)
        if stale_before > observed:
            raise EffectQueueError("heartbeat_before cannot be later than observed_at")
        try:
            with self._read_transaction() as connection:
                rows = connection.execute(
                    "SELECT * FROM effect_runtime_leases WHERE status = ANY(%s)",
                    (list(NONTERMINAL_VALUES),),
                ).fetchall()
                records = [
                    self._decode_lease(connection, row, validate_context=True) for row in rows
                ]
                candidates = [
                    record
                    for record in records
                    if instant(record.lease_expiry) <= observed
                    or instant(record.heartbeat_at) <= stale_before
                ]
                return tuple(
                    sorted(
                        candidates,
                        key=lambda record: (
                            min(
                                instant(record.lease_expiry),
                                instant(record.heartbeat_at),
                            ),
                            record.outbox_id,
                            record.lease_epoch,
                        ),
                    )
                )
        except EffectQueueError:
            raise
        except Exception as exc:
            self._raise_database_error("scan recoverable PostgreSQL effect leases", exc)


__all__ = ["PostgresEffectQueue"]
