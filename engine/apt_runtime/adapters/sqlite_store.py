"""SQLite compare-and-append store for the APT vNext durable kernel.

The adapter persists an event batch, its command receipt, requested-effect
outbox rows, and the stream-head CAS update in one ``BEGIN IMMEDIATE``
transaction.  It deliberately contains no domain transition logic and is a
trusted low-level port; application mutations must route through
``engine.apt_runtime.DurableKernel``.

# KG: apt-tpa-legion-engine-canon-2026-06-12
# KG: APT_SCW_TDAD_canonical
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
import sqlite3
from threading import RLock

from engine.apt_runtime.domain.canonical import normalize_text
from engine.apt_runtime.domain.events import EventEnvelope
from engine.apt_runtime.domain.state_codec import decode_state
from engine.apt_runtime.ports.event_store import (
    AppendResult,
    CommandIdConflict,
    CommandReceipt,
    CommandReceiptDraft,
    EventStore,
    OutboxRecord,
    PersistenceSchemaError,
    Snapshot,
    StoreConflict,
    StoreCorruption,
    StoreError,
    StreamBindingConflict,
)

from ._sqlite_codec import (
    encode_event_row,
    encode_outbox_row,
    encode_receipt_row,
    event_from_row,
    immutable_bytes,
    outbox_from_row,
    snapshot_from_row,
)
from ._sqlite_integrity import load_stream_rows, validate_append_batch, validated_receipt
from ._sqlite_schema import (
    INSERT_EVENT,
    INSERT_OUTBOX,
    INSERT_RECEIPT,
    SCHEMA,
    SCHEMA_VERSION,
    SchemaSignatureError,
    validate_schema_signature,
)


def _text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value:
        raise PersistenceSchemaError(f"{name} must be a non-empty string")
    return normalize_text(value)


def _nonnegative_integer(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise PersistenceSchemaError(f"{name} must be a non-negative integer")
    return value


class SqliteEventStore(EventStore):
    """SQLite implementation of the v1 durable event-store contract.

    # KG: apt-tpa-legion-engine-canon-2026-06-12
    # KG: APT_SCW_TDAD_canonical
    """

    def __init__(
        self,
        database: str | Path,
        *,
        busy_timeout_ms: int = 5_000,
        failpoint: Callable[[str], None] | None = None,
    ) -> None:
        if (
            isinstance(busy_timeout_ms, bool)
            or not isinstance(busy_timeout_ms, int)
            or busy_timeout_ms < 1
        ):
            raise PersistenceSchemaError("busy_timeout_ms must be a positive integer")
        self._database = str(database)
        if failpoint is not None and not callable(failpoint):
            raise PersistenceSchemaError("failpoint must be callable")
        self._failpoint = failpoint
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
            raise StoreError(f"failed to open SQLite event store: {exc}") from exc

    def init_schema(self) -> None:
        """Create v1 atomically and reject an incompatible schema signature."""

        with self._lock:
            try:
                self._connection.executescript(f"BEGIN IMMEDIATE;\n{SCHEMA}")
                self._connection.execute(
                    "INSERT OR IGNORE INTO apt_store_schema(singleton, schema_version) "
                    "VALUES (1, ?)",
                    (SCHEMA_VERSION,),
                )
                row = self._connection.execute(
                    "SELECT schema_version FROM apt_store_schema WHERE singleton = 1"
                ).fetchone()
                if row is None or row["schema_version"] != SCHEMA_VERSION:
                    raise StoreCorruption("SQLite event-store schema version is incompatible")
                try:
                    validate_schema_signature(self._connection)
                except SchemaSignatureError as exc:
                    raise StoreCorruption(str(exc)) from exc
                self._connection.execute("COMMIT")
            except StoreError:
                self._rollback()
                raise
            except sqlite3.DatabaseError as exc:
                self._rollback()
                raise StoreError(f"failed to initialize SQLite event-store schema: {exc}") from exc
            except BaseException:
                self._rollback()
                raise

    def close(self) -> None:
        """Close the adapter-owned connection."""

        with self._lock:
            self._connection.close()

    def load(self, stream_id: str, after_version: int = 0) -> list[EventEnvelope]:
        """Load one complete validated event suffix in ascending version order."""

        stream_id = _text("stream_id", stream_id)
        after_version = _nonnegative_integer("after_version", after_version)
        with self._lock:
            try:
                self._connection.execute("BEGIN")
                head, rows = load_stream_rows(self._connection, stream_id, after_version)
                self._connection.execute("COMMIT")
            except sqlite3.DatabaseError as exc:
                self._rollback()
                raise StoreError(f"failed to load event stream {stream_id!r}: {exc}") from exc
            except BaseException:
                self._rollback()
                raise

        if head is None or after_version >= head["current_version"]:
            return []

        expected_count = head["current_version"] - after_version
        if len(rows) != expected_count:
            raise StoreCorruption(
                f"stream {stream_id!r} head is {head['current_version']} but its event suffix "
                f"contains {len(rows)} of {expected_count} rows"
            )
        events: list[EventEnvelope] = []
        for offset, row in enumerate(rows, start=after_version + 1):
            if row["stream_version"] != offset:
                raise StoreCorruption(f"stream {stream_id!r} contains a version gap at {offset}")
            event = event_from_row(row)
            if (
                event.fsm_spec_hash != head["fsm_spec_hash"]
                or event.config_version != head["config_version"]
            ):
                raise StoreCorruption("event specification/configuration differs from stream head")
            events.append(event)
        return events

    def append(
        self,
        stream_id: str,
        expected_version: int,
        events: Sequence[EventEnvelope],
        outbox_records: Sequence[OutboxRecord],
        receipt: CommandReceiptDraft,
    ) -> AppendResult:
        """Atomically append or return the receipt of an identical prior command."""

        stream_id = _text("stream_id", stream_id)
        expected_version = _nonnegative_integer("expected_version", expected_version)
        if not isinstance(receipt, CommandReceiptDraft):
            raise PersistenceSchemaError("receipt must be a CommandReceiptDraft")
        event_batch = tuple(events)
        outbox_batch = tuple(outbox_records)

        with self._lock:
            try:
                self._connection.execute("BEGIN IMMEDIATE")
                prior_row = self._connection.execute(
                    "SELECT * FROM apt_command_receipts WHERE command_id = ?",
                    (receipt.command_id,),
                ).fetchone()
                if prior_row is not None:
                    prior = validated_receipt(self._connection, prior_row)
                    if prior.stream_id != stream_id or prior.command_hash != receipt.command_hash:
                        raise CommandIdConflict(
                            f"command_id {receipt.command_id!r} was already used for a "
                            "different stream or command hash"
                        )
                    self._connection.execute("COMMIT")
                    return AppendResult(
                        new_version=prior.committed_version,
                        receipt=prior,
                        deduplicated=True,
                    )

                validate_append_batch(
                    stream_id, expected_version, event_batch, outbox_batch, receipt
                )
                head = self._connection.execute(
                    "SELECT current_version, fsm_spec_hash, config_version "
                    "FROM apt_stream_heads WHERE stream_id = ?",
                    (stream_id,),
                ).fetchone()
                actual_version = 0 if head is None else head["current_version"]
                if actual_version != expected_version:
                    raise StoreConflict(stream_id, expected_version, actual_version)

                if not event_batch:
                    persisted_receipt = CommandReceipt.from_draft(
                        receipt,
                        stream_id=stream_id,
                        committed_version=actual_version,
                        event_ids=(),
                    )
                    self._connection.execute(INSERT_RECEIPT, encode_receipt_row(persisted_receipt))
                    receipt_row = self._connection.execute(
                        "SELECT * FROM apt_command_receipts WHERE command_id = ?",
                        (receipt.command_id,),
                    ).fetchone()
                    if (
                        receipt_row is None
                        or validated_receipt(self._connection, receipt_row) != persisted_receipt
                    ):
                        raise StoreCorruption("no-event command receipt failed validation")
                    self._commit_append()
                    return AppendResult(
                        new_version=actual_version,
                        receipt=persisted_receipt,
                        deduplicated=False,
                    )

                first = event_batch[0]
                if head is None:
                    self._connection.execute(
                        "INSERT INTO apt_stream_heads"
                        "(stream_id, current_version, fsm_spec_hash, config_version) "
                        "VALUES (?, 0, ?, ?)",
                        (stream_id, first.fsm_spec_hash, first.config_version),
                    )
                elif (
                    head["fsm_spec_hash"] != first.fsm_spec_hash
                    or head["config_version"] != first.config_version
                ):
                    raise StreamBindingConflict(
                        stream_id,
                        stream_fsm_spec_hash=head["fsm_spec_hash"],
                        candidate_fsm_spec_hash=first.fsm_spec_hash,
                        stream_config_version=head["config_version"],
                        candidate_config_version=first.config_version,
                    )

                self._connection.executemany(
                    INSERT_EVENT, [encode_event_row(event) for event in event_batch]
                )
                persisted_receipt = CommandReceipt.from_draft(
                    receipt,
                    stream_id=stream_id,
                    committed_version=event_batch[-1].stream_version,
                    event_ids=tuple(event.event_id for event in event_batch),
                    outbox_ids=tuple(record.outbox_id for record in outbox_batch),
                )
                self._connection.execute(INSERT_RECEIPT, encode_receipt_row(persisted_receipt))
                self._connection.executemany(
                    INSERT_OUTBOX, [encode_outbox_row(record) for record in outbox_batch]
                )
                cursor = self._connection.execute(
                    "UPDATE apt_stream_heads SET current_version = ? "
                    "WHERE stream_id = ? AND current_version = ?",
                    (event_batch[-1].stream_version, stream_id, expected_version),
                )
                if cursor.rowcount != 1:
                    current = self._head_version(stream_id)
                    raise StoreConflict(stream_id, expected_version, current)
                receipt_row = self._connection.execute(
                    "SELECT * FROM apt_command_receipts WHERE command_id = ?",
                    (receipt.command_id,),
                ).fetchone()
                if (
                    receipt_row is None
                    or validated_receipt(self._connection, receipt_row) != persisted_receipt
                ):
                    raise StoreCorruption(
                        "committed command receipt does not match its event/outbox rows"
                    )
                self._commit_append()
                return AppendResult(
                    new_version=persisted_receipt.committed_version,
                    receipt=persisted_receipt,
                    deduplicated=False,
                )
            except (StoreError, PersistenceSchemaError):
                self._rollback()
                raise
            except sqlite3.DatabaseError as exc:
                self._rollback()
                raise StoreError(f"SQLite append transaction failed: {exc}") from exc
            except BaseException:
                self._rollback()
                raise

    def load_command_receipt(self, command_id: str) -> CommandReceipt | None:
        """Load one self-validating command receipt by global command identity."""

        command_id = _text("command_id", command_id)
        with self._lock:
            try:
                row = self._connection.execute(
                    "SELECT * FROM apt_command_receipts WHERE command_id = ?", (command_id,)
                ).fetchone()
                return None if row is None else validated_receipt(self._connection, row)
            except sqlite3.DatabaseError as exc:
                raise StoreError(f"failed to load command receipt {command_id!r}: {exc}") from exc

    def load_outbox(self, stream_id: str) -> list[OutboxRecord]:
        """Load immutable requested-effect rows in insertion order."""

        stream_id = _text("stream_id", stream_id)
        with self._lock:
            try:
                rows = self._connection.execute(
                    "SELECT * FROM apt_outbox WHERE stream_id = ? ORDER BY rowid", (stream_id,)
                ).fetchall()
                for command_id in {row["command_id"] for row in rows}:
                    receipt_row = self._connection.execute(
                        "SELECT * FROM apt_command_receipts WHERE command_id = ?", (command_id,)
                    ).fetchone()
                    if receipt_row is None:
                        raise StoreCorruption("outbox row has no command receipt")
                    receipt = validated_receipt(self._connection, receipt_row)
                    if receipt.stream_id != stream_id:
                        raise StoreCorruption("outbox row references another stream's receipt")
            except sqlite3.DatabaseError as exc:
                raise StoreError(f"failed to load outbox for {stream_id!r}: {exc}") from exc
        return [outbox_from_row(row) for row in rows]

    def load_snapshot(self, stream_id: str) -> Snapshot | None:
        """Load the newest self-validating snapshot that cannot exceed the stream head."""

        stream_id = _text("stream_id", stream_id)
        with self._lock:
            try:
                row = self._connection.execute(
                    "SELECT s.*, h.current_version, h.fsm_spec_hash AS head_spec_hash, "
                    "h.config_version AS head_config_version "
                    "FROM apt_snapshots AS s JOIN apt_stream_heads AS h USING(stream_id) "
                    "WHERE s.stream_id = ? ORDER BY s.stream_version DESC LIMIT 1",
                    (stream_id,),
                ).fetchone()
            except sqlite3.DatabaseError as exc:
                raise StoreError(f"failed to load snapshot for {stream_id!r}: {exc}") from exc
        if row is None:
            return None
        if (
            row["stream_version"] > row["current_version"]
            or row["fsm_spec_hash"] != row["head_spec_hash"]
        ):
            raise StoreCorruption("snapshot version/specification is incompatible with stream head")
        snapshot = snapshot_from_row(row)
        if decode_state(snapshot.state_blob).config_version != row["head_config_version"]:
            raise StoreCorruption("snapshot configuration differs from stream head")
        return snapshot

    def save_snapshot(self, snapshot: Snapshot) -> None:
        """Persist a historical snapshot without advancing or replacing event history."""

        if not isinstance(snapshot, Snapshot):
            raise PersistenceSchemaError("snapshot must be a Snapshot")
        with self._lock:
            try:
                self._connection.execute("BEGIN IMMEDIATE")
                head = self._connection.execute(
                    "SELECT current_version, fsm_spec_hash, config_version "
                    "FROM apt_stream_heads "
                    "WHERE stream_id = ?",
                    (snapshot.stream_id,),
                ).fetchone()
                actual = 0 if head is None else head["current_version"]
                if head is None or snapshot.stream_version > actual:
                    raise StoreConflict(snapshot.stream_id, snapshot.stream_version, actual)
                if head["fsm_spec_hash"] != snapshot.fsm_spec_hash:
                    raise StoreError("snapshot specification differs from stream head")
                if decode_state(snapshot.state_blob).config_version != head["config_version"]:
                    raise StoreError("snapshot configuration differs from stream head")
                prior = self._connection.execute(
                    "SELECT fsm_spec_hash, codec_version, state_hash, state_blob "
                    "FROM apt_snapshots WHERE stream_id = ? AND stream_version = ?",
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
                    self._connection.execute("COMMIT")
                    return
                self._connection.execute(
                    "INSERT INTO apt_snapshots"
                    "(stream_id, stream_version, fsm_spec_hash, codec_version, state_hash, "
                    "state_blob, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
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
                self._connection.execute("COMMIT")
            except (StoreError, PersistenceSchemaError):
                self._rollback()
                raise
            except sqlite3.DatabaseError as exc:
                self._rollback()
                raise StoreError(f"SQLite snapshot transaction failed: {exc}") from exc
            except BaseException:
                self._rollback()
                raise

    def _head_version(self, stream_id: str) -> int:
        row = self._connection.execute(
            "SELECT current_version FROM apt_stream_heads WHERE stream_id = ?", (stream_id,)
        ).fetchone()
        return 0 if row is None else row["current_version"]

    def _commit_append(self) -> None:
        if self._failpoint is not None:
            self._failpoint("before_commit")
        self._connection.execute("COMMIT")
        if self._failpoint is not None:
            self._failpoint("after_commit")

    def _rollback(self) -> None:
        if self._connection.in_transaction:
            self._connection.execute("ROLLBACK")


__all__ = ["SqliteEventStore"]
