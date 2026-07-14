"""PostgreSQL compare-and-append store for the APT vNext durable kernel.

Each operation owns a short-lived psycopg connection. Writes take deterministic
transaction advisory locks in command-then-stream order, while multi-query
reads use one repeatable-read snapshot. Canonical JSON remains opaque ``BYTEA``;
PostgreSQL never reparses or reserializes identity bytes.

# KG: apt-tpa-legion-engine-canon-2026-06-12
# Design: SYMPOSIUM/THEORY/APT/vnext/APT_ENGINE_FSM_DESIGN_2026-07-13.md §12.1
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from typing import TYPE_CHECKING, NoReturn

from engine.apt_runtime.domain.canonical import MAX_SIGNED_64, normalize_text
from engine.apt_runtime.domain.events import EventEnvelope
from engine.apt_runtime.domain.state_codec import decode_state
from engine.apt_runtime.ports.event_store import (
    AppendResult,
    CommandReceipt,
    CommandReceiptDraft,
    EventStore,
    OutboxRecord,
    PersistenceSchemaError,
    Snapshot,
    StoreConflict,
    StoreCorruption,
    StoreError,
)

from ._postgres_append import append_locked, load_prior_receipt
from ._postgres_integrity import load_stream_rows, validated_receipt
from ._postgres_schema import (
    SCHEMA_STATEMENTS,
    SCHEMA_VERSION,
    SchemaSignatureError,
    validate_schema_signature,
)
from ._store_codec import (
    event_from_row,
    immutable_bytes,
    outbox_from_row,
    snapshot_from_row,
)
from ._store_integrity import validate_append_batch

if TYPE_CHECKING:
    from psycopg import Connection
    from psycopg.rows import DictRow, RowFactory


def _text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value:
        raise PersistenceSchemaError(f"{name} must be a non-empty string")
    normalized = normalize_text(value)
    if "\x00" in normalized:
        raise PersistenceSchemaError(f"{name} cannot contain U+0000")
    return normalized


def _nonnegative_integer(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > MAX_SIGNED_64:
        raise PersistenceSchemaError(f"{name} must be a signed 64-bit non-negative integer")
    return value


def _lock_key(namespace: str, identity: str) -> int:
    digest = hashlib.sha256(f"{namespace}\x00{identity}".encode()).digest()[:8]
    return int.from_bytes(digest, byteorder="big", signed=True)


class PostgresEventStore(EventStore):
    """Synchronous PostgreSQL implementation of the durable v1 store port.

    # KG: apt-tpa-legion-engine-canon-2026-06-12
    # Design: SYMPOSIUM/THEORY/APT/vnext/APT_ENGINE_FSM_DESIGN_2026-07-13.md §12.1
    """

    def __init__(
        self,
        dsn: str,
        *,
        connect_timeout_seconds: int = 5,
        failpoint: Callable[[str], None] | None = None,
    ) -> None:
        self._dsn = _text("dsn", dsn)
        if (
            isinstance(connect_timeout_seconds, bool)
            or not isinstance(connect_timeout_seconds, int)
            or connect_timeout_seconds < 1
        ):
            raise PersistenceSchemaError("connect_timeout_seconds must be a positive integer")
        if failpoint is not None and not callable(failpoint):
            raise PersistenceSchemaError("failpoint must be callable")
        try:
            import psycopg
            from psycopg import IsolationLevel
            from psycopg.rows import dict_row
        except ImportError as exc:  # pragma: no cover - exercised in minimal installations
            raise ImportError(
                "Install bhgman_tool[apt-postgres] to use PostgresEventStore"
            ) from exc
        self._connect_factory: Callable[..., Connection[DictRow]] = psycopg.connect
        self._row_factory: RowFactory[DictRow] = dict_row
        self._database_error: type[Exception] = psycopg.Error
        self._repeatable_read = IsolationLevel.REPEATABLE_READ
        self._connect_timeout_seconds = connect_timeout_seconds
        self._failpoint = failpoint

    def init_schema(self) -> None:
        """Create v1 atomically, then verify the physical PostgreSQL signature."""

        try:
            with self._connect() as connection:
                with connection.transaction():
                    connection.execute("SET LOCAL synchronous_commit = on")
                    self._advisory_lock(connection, "schema", "apt-event-store-v1")
                    for statement in SCHEMA_STATEMENTS:
                        connection.execute(statement)
                    connection.execute(
                        "INSERT INTO apt_store_schema(singleton, schema_version) "
                        "VALUES (1, %s) ON CONFLICT (singleton) DO NOTHING",
                        (SCHEMA_VERSION,),
                    )
                    row = connection.execute(
                        "SELECT schema_version FROM apt_store_schema WHERE singleton = 1"
                    ).fetchone()
                    if row is None or row["schema_version"] != SCHEMA_VERSION:
                        raise StoreCorruption(
                            "PostgreSQL event-store schema version is incompatible"
                        )
                    try:
                        validate_schema_signature(connection)
                    except SchemaSignatureError as exc:
                        raise StoreCorruption(str(exc)) from exc
        except StoreError:
            raise
        except Exception as exc:
            self._raise_database_error("initialize PostgreSQL event-store schema", exc)

    def close(self) -> None:
        """Release adapter resources; connections are already operation-scoped."""

    def load(self, stream_id: str, after_version: int = 0) -> list[EventEnvelope]:
        """Load one complete validated suffix from a repeatable-read snapshot."""

        stream_id = _text("stream_id", stream_id)
        after_version = _nonnegative_integer("after_version", after_version)
        try:
            with self._read_transaction() as connection:
                head, rows = load_stream_rows(connection, stream_id, after_version)
                if head is None or after_version >= head["current_version"]:
                    return []
                expected_count = head["current_version"] - after_version
                if len(rows) != expected_count:
                    raise StoreCorruption(
                        f"stream {stream_id!r} head is {head['current_version']} but its "
                        f"event suffix contains {len(rows)} of {expected_count} rows"
                    )
                events: list[EventEnvelope] = []
                for offset, row in enumerate(rows, start=after_version + 1):
                    if row["stream_version"] != offset:
                        raise StoreCorruption(
                            f"stream {stream_id!r} contains a version gap at {offset}"
                        )
                    event = event_from_row(row)
                    if (
                        event.fsm_spec_hash != head["fsm_spec_hash"]
                        or event.config_version != head["config_version"]
                    ):
                        raise StoreCorruption(
                            "event specification/configuration differs from stream head"
                        )
                    events.append(event)
                return events
        except StoreError:
            raise
        except Exception as exc:
            self._raise_database_error(f"load event stream {stream_id!r}", exc)

    def append(
        self,
        stream_id: str,
        expected_version: int,
        events: Sequence[EventEnvelope],
        outbox_records: Sequence[OutboxRecord],
        receipt: CommandReceiptDraft,
    ) -> AppendResult:
        """Atomically append, or return the exact receipt of an identical command."""

        stream_id = _text("stream_id", stream_id)
        expected_version = _nonnegative_integer("expected_version", expected_version)
        if not isinstance(receipt, CommandReceiptDraft):
            raise PersistenceSchemaError("receipt must be a CommandReceiptDraft")
        event_batch = tuple(events)
        outbox_batch = tuple(outbox_records)
        committed_new_rows = False
        try:
            with self._connect() as connection:
                with connection.transaction():
                    connection.execute("SET LOCAL synchronous_commit = on")
                    self._advisory_lock(connection, "command", receipt.command_id)
                    prior = load_prior_receipt(connection, stream_id, receipt)
                    if prior is not None:
                        return AppendResult(
                            new_version=prior.committed_version,
                            receipt=prior,
                            deduplicated=True,
                        )

                    validate_append_batch(
                        stream_id, expected_version, event_batch, outbox_batch, receipt
                    )
                    self._advisory_lock(connection, "stream", stream_id)
                    prior = load_prior_receipt(connection, stream_id, receipt)
                    if prior is not None:
                        return AppendResult(
                            new_version=prior.committed_version,
                            receipt=prior,
                            deduplicated=True,
                        )

                    head = connection.execute(
                        "SELECT current_version, fsm_spec_hash, config_version "
                        "FROM apt_stream_heads WHERE stream_id = %s FOR UPDATE",
                        (stream_id,),
                    ).fetchone()
                    actual_version = 0 if head is None else head["current_version"]
                    if actual_version != expected_version:
                        raise StoreConflict(stream_id, expected_version, actual_version)

                    persisted = append_locked(
                        connection,
                        stream_id,
                        expected_version,
                        head,
                        event_batch,
                        outbox_batch,
                        receipt,
                    )
                    committed_new_rows = True
                    if self._failpoint is not None:
                        self._failpoint("before_commit")
                if committed_new_rows and self._failpoint is not None:
                    self._failpoint("after_commit")
                return AppendResult(
                    new_version=persisted.committed_version,
                    receipt=persisted,
                    deduplicated=False,
                )
        except (StoreError, PersistenceSchemaError):
            raise
        except Exception as exc:
            self._raise_database_error("PostgreSQL append transaction", exc)

    def load_command_receipt(self, command_id: str) -> CommandReceipt | None:
        """Load one self-validating command receipt by global identity."""

        command_id = _text("command_id", command_id)
        try:
            with self._read_transaction() as connection:
                row = connection.execute(
                    "SELECT * FROM apt_command_receipts WHERE command_id = %s", (command_id,)
                ).fetchone()
                return None if row is None else validated_receipt(connection, row)
        except StoreError:
            raise
        except Exception as exc:
            self._raise_database_error(f"load command receipt {command_id!r}", exc)

    def load_outbox(self, stream_id: str) -> list[OutboxRecord]:
        """Load executable requests in deterministic stream-version/ordinal order."""

        stream_id = _text("stream_id", stream_id)
        try:
            with self._read_transaction() as connection:
                load_stream_rows(connection, stream_id, MAX_SIGNED_64)
                rows = connection.execute(
                    "SELECT o.* FROM apt_outbox AS o "
                    "JOIN apt_command_receipts AS r USING(command_id) "
                    "WHERE o.stream_id = %s "
                    "ORDER BY r.committed_version, o.outbox_position",
                    (stream_id,),
                ).fetchall()
                for command_id in {row["command_id"] for row in rows}:
                    receipt_row = connection.execute(
                        "SELECT * FROM apt_command_receipts WHERE command_id = %s",
                        (command_id,),
                    ).fetchone()
                    if receipt_row is None:
                        raise StoreCorruption("outbox row has no command receipt")
                    loaded = validated_receipt(connection, receipt_row)
                    if loaded.stream_id != stream_id:
                        raise StoreCorruption("outbox row references another stream's receipt")
                return [outbox_from_row(row) for row in rows]
        except StoreError:
            raise
        except Exception as exc:
            self._raise_database_error(f"load outbox for {stream_id!r}", exc)

    def load_snapshot(self, stream_id: str) -> Snapshot | None:
        """Load the newest self-validating snapshot from one read snapshot."""

        stream_id = _text("stream_id", stream_id)
        try:
            with self._read_transaction() as connection:
                row = connection.execute(
                    "SELECT s.*, h.current_version, h.fsm_spec_hash AS head_spec_hash, "
                    "h.config_version AS head_config_version "
                    "FROM apt_snapshots AS s JOIN apt_stream_heads AS h USING(stream_id) "
                    "WHERE s.stream_id = %s ORDER BY s.stream_version DESC LIMIT 1",
                    (stream_id,),
                ).fetchone()
                if row is None:
                    return None
                if (
                    row["stream_version"] > row["current_version"]
                    or row["fsm_spec_hash"] != row["head_spec_hash"]
                ):
                    raise StoreCorruption(
                        "snapshot version/specification is incompatible with stream head"
                    )
                snapshot = snapshot_from_row(row)
                if decode_state(snapshot.state_blob).config_version != row["head_config_version"]:
                    raise StoreCorruption("snapshot configuration differs from stream head")
                return snapshot
        except StoreError:
            raise
        except Exception as exc:
            self._raise_database_error(f"load snapshot for {stream_id!r}", exc)

    def save_snapshot(self, snapshot: Snapshot) -> None:
        """Save a rebuildable snapshot while serializing against stream appends."""

        if not isinstance(snapshot, Snapshot):
            raise PersistenceSchemaError("snapshot must be a Snapshot")
        try:
            with self._connect() as connection:
                with connection.transaction():
                    connection.execute("SET LOCAL synchronous_commit = on")
                    self._advisory_lock(connection, "stream", snapshot.stream_id)
                    head = connection.execute(
                        "SELECT current_version, fsm_spec_hash, config_version "
                        "FROM apt_stream_heads WHERE stream_id = %s FOR UPDATE",
                        (snapshot.stream_id,),
                    ).fetchone()
                    actual = 0 if head is None else head["current_version"]
                    if head is None or snapshot.stream_version > actual:
                        raise StoreConflict(snapshot.stream_id, snapshot.stream_version, actual)
                    if head["fsm_spec_hash"] != snapshot.fsm_spec_hash:
                        raise StoreError("snapshot specification differs from stream head")
                    if decode_state(snapshot.state_blob).config_version != head["config_version"]:
                        raise StoreError("snapshot configuration differs from stream head")
                    prior = connection.execute(
                        "SELECT fsm_spec_hash, codec_version, state_hash, state_blob "
                        "FROM apt_snapshots WHERE stream_id = %s AND stream_version = %s "
                        "FOR UPDATE",
                        (snapshot.stream_id, snapshot.stream_version),
                    ).fetchone()
                    if prior is not None:
                        same = (
                            prior["fsm_spec_hash"] == snapshot.fsm_spec_hash
                            and prior["codec_version"] == snapshot.codec_version
                            and prior["state_hash"] == snapshot.state_hash
                            and immutable_bytes(prior["state_blob"], "snapshot.state_blob")
                            == snapshot.state_blob
                        )
                        if not same:
                            raise StoreError("snapshot version already exists with different bytes")
                        return
                    connection.execute(
                        "INSERT INTO apt_snapshots"
                        "(stream_id, stream_version, fsm_spec_hash, codec_version, state_hash, "
                        "state_blob, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                        (
                            snapshot.stream_id,
                            snapshot.stream_version,
                            snapshot.fsm_spec_hash,
                            snapshot.codec_version,
                            snapshot.state_hash,
                            snapshot.state_blob,
                            snapshot.created_at,
                        ),
                    )
        except StoreError:
            raise
        except Exception as exc:
            self._raise_database_error("PostgreSQL snapshot transaction", exc)

    def _advisory_lock(
        self, connection: Connection[DictRow], namespace: str, identity: str
    ) -> None:
        connection.execute("SELECT pg_advisory_xact_lock(%s)", (_lock_key(namespace, identity),))

    @contextmanager
    def _read_transaction(self) -> Iterator[Connection[DictRow]]:
        with self._connect(read_only=True) as connection:
            with connection.transaction():
                yield connection

    def _connect(self, *, read_only: bool = False) -> Connection[DictRow]:
        connection = self._connect_factory(
            self._dsn,
            autocommit=True,
            row_factory=self._row_factory,
            connect_timeout=self._connect_timeout_seconds,
        )
        if read_only:
            connection.isolation_level = self._repeatable_read
            connection.read_only = True
        return connection

    def _raise_database_error(self, operation: str, exc: Exception) -> NoReturn:
        if isinstance(exc, self._database_error):
            raise StoreError(f"failed to {operation}: {exc}") from exc
        raise exc


__all__ = ["PostgresEventStore"]
