"""Cross-row corruption falsifiers for SQLite receipt and stream integrity.

# KG: apt-tpa-legion-engine-canon-2026-06-12
# KG: APT_SCW_TDAD_canonical
"""

from __future__ import annotations

from pathlib import Path
import sqlite3

import pytest

from engine.apt_runtime.adapters.sqlite_store import SqliteEventStore
from engine.apt_runtime.domain.canonical import canonical_json_bytes, canonical_sha256
from engine.apt_runtime.domain.events import EventType
from engine.apt_runtime.ports.event_store import (
    OutboxRecord,
    PersistenceSchemaError,
    StoreCorruption,
)
from engine.apt_runtime.tests.test_sqlite_store import event, outbox, receipt


def test_receipt_load_and_retry_decode_every_referenced_outbox_row(tmp_path: Path) -> None:
    database = tmp_path / "receipt-payload.sqlite3"
    adapter = SqliteEventStore(database)
    adapter.init_schema()
    command = receipt("command-corrupt-outbox")
    queued = event(
        1,
        command.command_id,
        event_type=EventType.EFFECT_QUEUED,
        effect_id="effect-corrupt-outbox",
    )
    record = outbox(command.command_id, effect_id="effect-corrupt-outbox")
    adapter.append("cycle-1", 0, [queued], [record], command)
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE apt_outbox SET payload_json = ? WHERE outbox_id = ?",
            (b"{}", record.outbox_id),
        )

    with pytest.raises(StoreCorruption, match="payload_hash"):
        adapter.load_command_receipt(command.command_id)
    with pytest.raises(StoreCorruption, match="payload_hash"):
        adapter.append("cycle-1", 0, [], [], command)
    adapter.close()


def test_stream_load_rejects_an_event_whose_command_receipt_was_deleted(
    tmp_path: Path,
) -> None:
    database = tmp_path / "missing-receipt.sqlite3"
    adapter = SqliteEventStore(database)
    adapter.init_schema()
    command = receipt("command-missing-receipt")
    adapter.append("cycle-1", 0, [event(1, command.command_id)], [], command)
    with sqlite3.connect(database) as connection:
        connection.execute(
            "DELETE FROM apt_command_receipts WHERE command_id = ?", (command.command_id,)
        )

    with pytest.raises(StoreCorruption, match="receipt"):
        adapter.load("cycle-1")
    adapter.close()


def test_deeply_nested_json_is_mapped_to_store_corruption(tmp_path: Path) -> None:
    database = tmp_path / "nested-json.sqlite3"
    adapter = SqliteEventStore(database)
    adapter.init_schema()
    command = receipt("command-nested-json")
    queued = event(
        1,
        command.command_id,
        event_type=EventType.EFFECT_QUEUED,
        effect_id="effect-nested-json",
    )
    record = outbox(command.command_id, effect_id="effect-nested-json")
    adapter.append("cycle-1", 0, [queued], [record], command)
    nested = b'{"x":' * 2_000 + b"0" + b"}" * 2_000
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE apt_outbox SET payload_json = ? WHERE outbox_id = ?",
            (nested, record.outbox_id),
        )

    with pytest.raises(StoreCorruption):
        adapter.load_outbox("cycle-1")
    adapter.close()


def test_low_level_append_rejects_divergent_executable_effect_payload(tmp_path: Path) -> None:
    adapter = SqliteEventStore(tmp_path / "divergent-effect.sqlite3")
    adapter.init_schema()
    command = receipt("command-divergent-effect")
    queued = event(
        1,
        command.command_id,
        event_type=EventType.EFFECT_QUEUED,
        effect_id="effect-divergent",
    )
    divergent = OutboxRecord.create(
        outbox_id="outbox-effect-divergent",
        stream_id="cycle-1",
        effect_id="effect-divergent",
        command_id=command.command_id,
        payload={"capability": "different.executable.request"},
        created_at="2026-07-14T00:00:00Z",
    )

    with pytest.raises(PersistenceSchemaError, match="executable payload"):
        adapter.append("cycle-1", 0, [queued], [divergent], command)
    assert adapter.load("cycle-1") == []
    adapter.close()


def test_stream_load_rejects_an_event_rebound_to_another_streams_receipt(
    tmp_path: Path,
) -> None:
    database = tmp_path / "cross-stream-receipt.sqlite3"
    adapter = SqliteEventStore(database)
    adapter.init_schema()
    command_a = receipt("command-a", stream_id="cycle-a")
    command_b = receipt("command-b", stream_id="cycle-b")
    adapter.append(
        "cycle-a",
        0,
        [event(1, command_a.command_id, stream_id="cycle-a", event_id="event-a")],
        [],
        command_a,
    )
    adapter.append(
        "cycle-b",
        0,
        [event(1, command_b.command_id, stream_id="cycle-b", event_id="event-b")],
        [],
        command_b,
    )
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE apt_events SET command_id = ? WHERE event_id = 'event-b'",
            (command_a.command_id,),
        )

    with pytest.raises(StoreCorruption, match="receipt owned"):
        adapter.load("cycle-b")
    adapter.close()


def test_read_paths_rebind_effect_event_to_outbox_payload_after_coherent_tamper(
    tmp_path: Path,
) -> None:
    database = tmp_path / "coherent-outbox-tamper.sqlite3"
    adapter = SqliteEventStore(database)
    adapter.init_schema()
    command = receipt("command-coherent-tamper")
    queued = event(
        1,
        command.command_id,
        event_type=EventType.EFFECT_QUEUED,
        effect_id="effect-coherent-tamper",
    )
    record = outbox(command.command_id, effect_id="effect-coherent-tamper")
    adapter.append("cycle-1", 0, [queued], [record], command)
    altered = {"capability": "workspace.mutate", "input_ref": "artifact://other"}
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE apt_outbox SET payload_json = ?, payload_hash = ? WHERE outbox_id = ?",
            (canonical_json_bytes(altered), canonical_sha256(altered), record.outbox_id),
        )

    with pytest.raises(StoreCorruption, match="executable payloads differ"):
        adapter.load_command_receipt(command.command_id)
    with pytest.raises(StoreCorruption, match="executable payloads differ"):
        adapter.load("cycle-1")
    with pytest.raises(StoreCorruption, match="executable payloads differ"):
        adapter.load_outbox("cycle-1")
    adapter.close()


def test_deleted_outbox_is_rejected_by_the_outbox_stream_read(tmp_path: Path) -> None:
    database = tmp_path / "deleted-outbox-stream-read.sqlite3"
    adapter = SqliteEventStore(database)
    adapter.init_schema()
    command = receipt("command-deleted-outbox-stream-read")
    queued = event(
        1,
        command.command_id,
        event_type=EventType.EFFECT_QUEUED,
        effect_id="effect-deleted-outbox-stream-read",
    )
    record = outbox(command.command_id, effect_id="effect-deleted-outbox-stream-read")
    adapter.append("cycle-1", 0, [queued], [record], command)
    with sqlite3.connect(database) as connection:
        connection.execute("DELETE FROM apt_outbox WHERE outbox_id = ?", (record.outbox_id,))

    with pytest.raises(StoreCorruption, match="receipt outbox"):
        adapter.load_outbox("cycle-1")
    adapter.close()


def test_no_event_receipt_rejects_committed_version_tamper(tmp_path: Path) -> None:
    database = tmp_path / "no-event-receipt-version-tamper.sqlite3"
    adapter = SqliteEventStore(database)
    adapter.init_schema()
    created = receipt("command-before-no-event")
    adapter.append("cycle-1", 0, [event(1, created.command_id)], [], created)
    no_event = receipt("command-no-event-seal", expected_version=1)
    adapter.append("cycle-1", 1, [], [], no_event)
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE apt_command_receipts SET committed_version = 0 WHERE command_id = ?",
            (no_event.command_id,),
        )

    with pytest.raises(StoreCorruption, match="expected_version"):
        adapter.load_command_receipt(no_event.command_id)
    adapter.close()


def test_receipt_and_retry_reject_stream_binding_tamper(tmp_path: Path) -> None:
    database = tmp_path / "receipt-stream-binding-tamper.sqlite3"
    adapter = SqliteEventStore(database)
    adapter.init_schema()
    command = receipt("command-head-binding-tamper")
    adapter.append("cycle-1", 0, [event(1, command.command_id)], [], command)
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE apt_stream_heads SET config_version = 'tampered' WHERE stream_id = 'cycle-1'"
        )

    with pytest.raises(StoreCorruption, match="stream head"):
        adapter.load_command_receipt(command.command_id)
    with pytest.raises(StoreCorruption, match="stream head"):
        adapter.append("cycle-1", 0, [], [], command)
    adapter.close()
