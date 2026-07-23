"""Cross-row integrity checks for the PostgreSQL durable APT store.

# KG: apt-tpa-legion-engine-canon-2026-06-12
# Design: SYMPOSIUM/THEORY/APT/vnext/APT_ENGINE_FSM_DESIGN_2026-07-13.md §12.1
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from engine.apt_runtime.ports.event_store import CommandReceipt, StoreCorruption

from ._store_codec import RowLike, event_from_row, outbox_from_row, receipt_from_row
from ._store_integrity import (
    validate_receipt_effects,
    validate_receipt_events,
    validate_receipt_head,
    validate_receipt_outbox,
    validate_receipt_outbox_positions,
    validate_stream_prefix,
)

if TYPE_CHECKING:
    from psycopg import Connection
    from psycopg.rows import DictRow


def validated_receipt(connection: Connection[DictRow], row: RowLike) -> CommandReceipt:
    """Decode a receipt and every event/outbox row it claims before trusting it."""

    receipt = receipt_from_row(row)
    event_rows = connection.execute(
        "SELECT * FROM apt_events WHERE stream_id = %s AND command_id = %s ORDER BY stream_version",
        (receipt.stream_id, receipt.command_id),
    ).fetchall()
    events = tuple(event_from_row(item) for item in event_rows)
    validate_receipt_events(receipt, events)
    outbox_rows = connection.execute(
        "SELECT * FROM apt_outbox WHERE stream_id = %s AND command_id = %s "
        "ORDER BY outbox_position",
        (receipt.stream_id, receipt.command_id),
    ).fetchall()
    positions = tuple(item["outbox_position"] for item in outbox_rows)
    validate_receipt_outbox_positions(positions)
    outbox = tuple(outbox_from_row(item) for item in outbox_rows)
    validate_receipt_outbox(receipt, outbox)
    validate_receipt_effects(events, outbox)
    head = connection.execute(
        "SELECT current_version, fsm_spec_hash, config_version "
        "FROM apt_stream_heads WHERE stream_id = %s",
        (receipt.stream_id,),
    ).fetchone()
    validate_receipt_head(receipt, events, head)
    return receipt


def load_stream_rows(
    connection: Connection[DictRow], stream_id: str, after_version: int
) -> tuple[DictRow | None, list[DictRow]]:
    """Read one repeatable-read stream snapshot and audit all receipt links."""

    head = connection.execute(
        "SELECT current_version, fsm_spec_hash, config_version "
        "FROM apt_stream_heads WHERE stream_id = %s",
        (stream_id,),
    ).fetchone()
    counts = connection.execute(
        "SELECT "
        "(SELECT COUNT(*) FROM apt_events WHERE stream_id = %s) AS event_count, "
        "(SELECT MIN(stream_version) FROM apt_events WHERE stream_id = %s) AS min_event, "
        "(SELECT MAX(stream_version) FROM apt_events WHERE stream_id = %s) AS max_event, "
        "(SELECT COUNT(*) FROM apt_outbox WHERE stream_id = %s) AS outbox_count, "
        "(SELECT COUNT(*) FROM apt_snapshots WHERE stream_id = %s) AS snapshot_count",
        (stream_id,) * 5,
    ).fetchone()
    assert counts is not None
    validate_stream_prefix(stream_id, head, counts)

    rows: list[DictRow] = []
    if head is not None and after_version < head["current_version"]:
        rows = connection.execute(
            "SELECT * FROM apt_events WHERE stream_id = %s AND stream_version > %s "
            "ORDER BY stream_version",
            (stream_id, after_version),
        ).fetchall()
    command_rows = connection.execute(
        "SELECT DISTINCT command_id FROM apt_events WHERE stream_id = %s", (stream_id,)
    ).fetchall()
    for command_row in command_rows:
        receipt_row = connection.execute(
            "SELECT * FROM apt_command_receipts WHERE command_id = %s",
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


__all__ = ["load_stream_rows", "validated_receipt"]
