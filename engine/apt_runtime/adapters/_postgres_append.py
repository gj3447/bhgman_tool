"""Locked PostgreSQL append mechanics separated from connection policy.

# KG: apt-tpa-legion-engine-canon-2026-06-12
# Design: SYMPOSIUM/THEORY/APT/vnext/APT_ENGINE_FSM_DESIGN_2026-07-13.md §12.1
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from engine.apt_runtime.domain.events import EventEnvelope
from engine.apt_runtime.ports.event_store import (
    CommandIdConflict,
    CommandReceipt,
    CommandReceiptDraft,
    OutboxRecord,
    StoreConflict,
    StoreCorruption,
    StreamBindingConflict,
)

from ._postgres_integrity import validated_receipt
from ._postgres_schema import INSERT_EVENT, INSERT_OUTBOX, INSERT_RECEIPT
from ._store_codec import encode_event_row, encode_outbox_row, encode_receipt_row

if TYPE_CHECKING:
    from psycopg import Connection
    from psycopg.rows import DictRow


def load_prior_receipt(
    connection: Connection[DictRow],
    stream_id: str,
    draft: CommandReceiptDraft,
) -> CommandReceipt | None:
    """Load an identical prior command or reject command-ID reuse."""

    row = connection.execute(
        "SELECT * FROM apt_command_receipts WHERE command_id = %s",
        (draft.command_id,),
    ).fetchone()
    if row is None:
        return None
    prior = validated_receipt(connection, row)
    if prior.stream_id != stream_id or prior.command_hash != draft.command_hash:
        raise CommandIdConflict(
            f"command_id {draft.command_id!r} was already used for a "
            "different stream or command hash"
        )
    return prior


def append_locked(
    connection: Connection[DictRow],
    stream_id: str,
    expected_version: int,
    head: DictRow | None,
    events: tuple[EventEnvelope, ...],
    outbox: tuple[OutboxRecord, ...],
    draft: CommandReceiptDraft,
) -> CommandReceipt:
    """Write one already-validated batch while the stream lock is held."""

    actual_version = 0 if head is None else head["current_version"]
    if not events:
        persisted = CommandReceipt.from_draft(
            draft,
            stream_id=stream_id,
            committed_version=actual_version,
            event_ids=(),
        )
        connection.execute(INSERT_RECEIPT, encode_receipt_row(persisted))
        _assert_persisted_receipt(connection, persisted, "no-event command")
        return persisted

    first = events[0]
    if head is None:
        connection.execute(
            "INSERT INTO apt_stream_heads"
            "(stream_id, current_version, fsm_spec_hash, config_version) "
            "VALUES (%s, 0, %s, %s)",
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

    for event in events:
        connection.execute(INSERT_EVENT, encode_event_row(event))
    persisted = CommandReceipt.from_draft(
        draft,
        stream_id=stream_id,
        committed_version=events[-1].stream_version,
        event_ids=tuple(event.event_id for event in events),
        outbox_ids=tuple(record.outbox_id for record in outbox),
    )
    connection.execute(INSERT_RECEIPT, encode_receipt_row(persisted))
    for position, record in enumerate(outbox):
        encoded = encode_outbox_row(record)
        connection.execute(INSERT_OUTBOX, (*encoded[:4], position, *encoded[4:]))
    cursor = connection.execute(
        "UPDATE apt_stream_heads SET current_version = %s "
        "WHERE stream_id = %s AND current_version = %s",
        (events[-1].stream_version, stream_id, expected_version),
    )
    if cursor.rowcount != 1:
        raise StoreConflict(stream_id, expected_version, _head_version(connection, stream_id))
    _assert_persisted_receipt(connection, persisted, "committed command")
    return persisted


def _assert_persisted_receipt(
    connection: Connection[DictRow],
    expected: CommandReceipt,
    description: str,
) -> None:
    row = connection.execute(
        "SELECT * FROM apt_command_receipts WHERE command_id = %s",
        (expected.command_id,),
    ).fetchone()
    if row is None or validated_receipt(connection, row) != expected:
        raise StoreCorruption(f"{description} receipt failed cross-row validation")


def _head_version(connection: Connection[DictRow], stream_id: str) -> int:
    row = connection.execute(
        "SELECT current_version FROM apt_stream_heads WHERE stream_id = %s", (stream_id,)
    ).fetchone()
    return 0 if row is None else row["current_version"]


__all__ = ["append_locked", "load_prior_receipt"]
