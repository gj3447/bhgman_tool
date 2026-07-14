"""Cross-row validation helpers for the SQLite durable event store.

# KG: apt-tpa-legion-engine-canon-2026-06-12
# KG: APT_SCW_TDAD_canonical
"""

from __future__ import annotations

import sqlite3

from engine.apt_runtime.domain.events import EventEnvelope, EventType
from engine.apt_runtime.ports.event_store import (
    CommandReceipt,
    CommandReceiptDraft,
    OutboxRecord,
    PersistenceSchemaError,
    StoreCorruption,
)

from ._sqlite_codec import event_from_row, outbox_from_row, receipt_from_row


def validate_append_batch(
    stream_id: str,
    expected_version: int,
    events: tuple[EventEnvelope, ...],
    outbox: tuple[OutboxRecord, ...],
    receipt: CommandReceiptDraft,
) -> None:
    """Validate persistence identities before any append row is written."""

    if any(not isinstance(event, EventEnvelope) for event in events):
        raise PersistenceSchemaError("events must contain only EventEnvelope values")
    if any(not isinstance(record, OutboxRecord) for record in outbox):
        raise PersistenceSchemaError("outbox_records must contain only OutboxRecord values")
    if not events:
        if outbox:
            raise PersistenceSchemaError("a no-event command cannot enqueue outbox work")
        return
    expected_versions = tuple(range(expected_version + 1, expected_version + len(events) + 1))
    if tuple(event.stream_version for event in events) != expected_versions:
        raise PersistenceSchemaError(
            "event versions must be exactly contiguous after expected_version"
        )
    first = events[0]
    for event in events:
        if event.stream_id != stream_id or event.cycle_id != stream_id:
            raise PersistenceSchemaError("every event stream_id and cycle_id must match stream_id")
        if event.command_id != receipt.command_id:
            raise PersistenceSchemaError("every event command_id must match the command receipt")
        if (
            event.fsm_spec_hash != first.fsm_spec_hash
            or event.config_version != first.config_version
        ):
            raise PersistenceSchemaError("event batch must pin one FSM spec and configuration")
    if len({event.event_id for event in events}) != len(events):
        raise PersistenceSchemaError("event IDs must be unique within an append batch")
    if len({record.outbox_id for record in outbox}) != len(outbox):
        raise PersistenceSchemaError("outbox IDs must be unique within an append batch")
    for record in outbox:
        if record.stream_id != stream_id or record.command_id != receipt.command_id:
            raise PersistenceSchemaError("outbox stream/command identity must match append")
    queued_effects = tuple(
        event.effect_id for event in events if event.event_type is EventType.EFFECT_QUEUED
    )
    if len(set(queued_effects)) != len(queued_effects):
        raise PersistenceSchemaError("EffectQueued identities must be unique within a batch")
    outbox_effects = {record.effect_id for record in outbox}
    if None in queued_effects or set(queued_effects) != outbox_effects:
        raise PersistenceSchemaError(
            "outbox effect IDs must equal the EffectQueued identities in the event batch"
        )
    queued_by_effect = {
        event.effect_id: event for event in events if event.event_type is EventType.EFFECT_QUEUED
    }
    for record in outbox:
        if record.payload != queued_by_effect[record.effect_id].payload:
            raise PersistenceSchemaError(
                "outbox executable payload must equal its EffectQueued request payload"
            )


def validated_receipt(connection: sqlite3.Connection, row: sqlite3.Row) -> CommandReceipt:
    """Decode a receipt and every event/outbox row it claims before trusting it."""

    receipt = receipt_from_row(row)
    event_rows = connection.execute(
        "SELECT * FROM apt_events WHERE stream_id = ? AND command_id = ? ORDER BY stream_version",
        (receipt.stream_id, receipt.command_id),
    ).fetchall()
    events = tuple(event_from_row(item) for item in event_rows)
    if tuple(event.event_id for event in events) != receipt.event_ids:
        raise StoreCorruption("command receipt event references do not match stored rows")
    if events and events[-1].stream_version != receipt.committed_version:
        raise StoreCorruption("command receipt committed version does not match its events")
    outbox_rows = connection.execute(
        "SELECT * FROM apt_outbox WHERE stream_id = ? AND command_id = ? ORDER BY rowid",
        (receipt.stream_id, receipt.command_id),
    ).fetchall()
    outbox = tuple(outbox_from_row(item) for item in outbox_rows)
    if tuple(item.outbox_id for item in outbox) != receipt.outbox_ids:
        raise StoreCorruption("command receipt outbox references do not match stored rows")
    queued = {
        event.effect_id: event.payload
        for event in events
        if event.event_type is EventType.EFFECT_QUEUED
    }
    if set(queued) != {item.effect_id for item in outbox}:
        raise StoreCorruption("command receipt effect events do not match its outbox rows")
    if any(item.payload != queued[item.effect_id] for item in outbox):
        raise StoreCorruption("EffectQueued and outbox executable payloads differ")
    head = connection.execute(
        "SELECT current_version FROM apt_stream_heads WHERE stream_id = ?",
        (receipt.stream_id,),
    ).fetchone()
    if head is None and receipt.committed_version != 0:
        raise StoreCorruption("command receipt committed version has no stream head")
    if head is not None and head["current_version"] < receipt.committed_version:
        raise StoreCorruption("command receipt committed version exceeds the stream head")
    return receipt


def load_stream_rows(
    connection: sqlite3.Connection, stream_id: str, after_version: int
) -> tuple[sqlite3.Row | None, list[sqlite3.Row]]:
    """Read one internally consistent stream snapshot and audit its receipt links."""

    head = connection.execute(
        "SELECT current_version, fsm_spec_hash, config_version "
        "FROM apt_stream_heads WHERE stream_id = ?",
        (stream_id,),
    ).fetchone()
    counts = connection.execute(
        "SELECT "
        "(SELECT COUNT(*) FROM apt_events WHERE stream_id = ?) AS event_count, "
        "(SELECT MIN(stream_version) FROM apt_events WHERE stream_id = ?) AS min_event, "
        "(SELECT MAX(stream_version) FROM apt_events WHERE stream_id = ?) AS max_event, "
        "(SELECT COUNT(*) FROM apt_outbox WHERE stream_id = ?) AS outbox_count, "
        "(SELECT COUNT(*) FROM apt_snapshots WHERE stream_id = ?) AS snapshot_count",
        (stream_id,) * 5,
    ).fetchone()
    assert counts is not None
    if head is None:
        if any(counts[name] for name in ("event_count", "outbox_count", "snapshot_count")):
            raise StoreCorruption(f"stream {stream_id!r} has durable rows without a stream head")
    elif (
        counts["event_count"] != head["current_version"]
        or counts["min_event"] != 1
        or counts["max_event"] != head["current_version"]
    ):
        raise StoreCorruption(f"stream {stream_id!r} head does not match its event prefix")

    rows = []
    if head is not None and after_version < head["current_version"]:
        rows = connection.execute(
            "SELECT * FROM apt_events WHERE stream_id = ? AND stream_version > ? "
            "ORDER BY stream_version",
            (stream_id, after_version),
        ).fetchall()
    command_rows = connection.execute(
        "SELECT DISTINCT command_id FROM apt_events WHERE stream_id = ?", (stream_id,)
    ).fetchall()
    for command_row in command_rows:
        receipt_row = connection.execute(
            "SELECT * FROM apt_command_receipts WHERE command_id = ?",
            (command_row["command_id"],),
        ).fetchone()
        if receipt_row is None:
            raise StoreCorruption(
                f"stream {stream_id!r} contains an event without its command receipt"
            )
        receipt = validated_receipt(connection, receipt_row)
        if receipt.stream_id != stream_id:
            raise StoreCorruption(
                f"stream {stream_id!r} references a receipt owned by {receipt.stream_id!r}"
            )
    return head, rows


__all__ = ["load_stream_rows", "validate_append_batch", "validated_receipt"]
