"""Adversarial schema and trigger checks for the SQLite durable store.

# KG: apt-tpa-legion-engine-canon-2026-06-12
# KG: APT_SCW_TDAD_canonical
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import sqlite3

import pytest

from engine.apt_runtime.adapters.sqlite_store import SqliteEventStore
from engine.apt_runtime.adapters._sqlite_schema import SCHEMA
from engine.apt_runtime.domain.events import EventType
from engine.apt_runtime.ports.event_store import StoreCorruption, StreamBindingConflict
from engine.apt_runtime.tests.test_sqlite_store import event, outbox, receipt


def _install_ignoring_trigger(database: Path) -> None:
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TRIGGER silently_ignore_outbox BEFORE INSERT ON apt_outbox "
            "BEGIN SELECT RAISE(IGNORE); END"
        )


def test_init_schema_rejects_an_incomplete_table_claiming_v1(tmp_path: Path) -> None:
    database = tmp_path / "incompatible-v1.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.executescript(
            """
            CREATE TABLE apt_store_schema (
                singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                schema_version INTEGER NOT NULL
            );
            INSERT INTO apt_store_schema(singleton, schema_version) VALUES (1, 1);
            CREATE TABLE apt_stream_heads (
                stream_id TEXT PRIMARY KEY,
                current_version INTEGER NOT NULL CHECK (current_version >= 0)
            );
            """
        )

    adapter = SqliteEventStore(database)
    try:
        with pytest.raises(StoreCorruption, match="signature"):
            adapter.init_schema()
    finally:
        adapter.close()


def test_init_schema_rejects_v1_tables_without_required_checks(tmp_path: Path) -> None:
    database = tmp_path / "missing-check.sqlite3"
    weakened_schema = SCHEMA.replace(
        "current_version INTEGER NOT NULL CHECK (current_version >= 0)",
        "current_version INTEGER NOT NULL",
    )
    with sqlite3.connect(database) as connection:
        connection.executescript(weakened_schema)
        connection.execute("INSERT INTO apt_store_schema(singleton, schema_version) VALUES (1, 1)")

    adapter = SqliteEventStore(database)
    try:
        with pytest.raises(StoreCorruption, match="DDL signature"):
            adapter.init_schema()
    finally:
        adapter.close()


def test_init_schema_rejects_a_nonprefixed_trigger_on_an_apt_table(tmp_path: Path) -> None:
    database = tmp_path / "unexpected-trigger.sqlite3"
    adapter = SqliteEventStore(database)
    adapter.init_schema()
    adapter.close()
    _install_ignoring_trigger(database)

    reopened = SqliteEventStore(database)
    try:
        with pytest.raises(StoreCorruption, match="DDL signature"):
            reopened.init_schema()
    finally:
        reopened.close()


def test_ignored_outbox_insert_is_detected_before_commit(tmp_path: Path) -> None:
    database = tmp_path / "ignored-outbox.sqlite3"
    adapter = SqliteEventStore(database)
    adapter.init_schema()
    _install_ignoring_trigger(database)

    command = receipt("command-ignored-outbox")
    queued = event(
        1,
        command.command_id,
        event_type=EventType.EFFECT_QUEUED,
        effect_id="effect-ignored-outbox",
    )
    record = outbox(command.command_id, effect_id="effect-ignored-outbox")
    with pytest.raises(StoreCorruption, match="receipt outbox"):
        adapter.append("cycle-1", 0, [queued], [record], command)

    assert adapter.load("cycle-1") == []
    assert adapter.load_command_receipt(command.command_id) is None
    assert adapter.load_outbox("cycle-1") == []
    adapter.close()


@pytest.mark.parametrize("tamper", ["delete", "rewind"])
def test_load_rejects_a_missing_or_rewound_head_with_hidden_events(
    tmp_path: Path, tamper: str
) -> None:
    database = tmp_path / f"head-{tamper}.sqlite3"
    adapter = SqliteEventStore(database)
    adapter.init_schema()
    command = receipt("command-head-tamper")
    adapter.append("cycle-1", 0, [event(1, command.command_id)], [], command)

    with sqlite3.connect(database) as connection:
        if tamper == "delete":
            connection.execute("DELETE FROM apt_stream_heads WHERE stream_id = 'cycle-1'")
        else:
            connection.execute(
                "UPDATE apt_stream_heads SET current_version = 0 WHERE stream_id = 'cycle-1'"
            )

    with pytest.raises(StoreCorruption, match="head"):
        adapter.load("cycle-1")
    adapter.close()


@pytest.mark.parametrize("binding", ["fsm", "config"])
def test_stream_binding_drift_is_not_reported_as_a_retryable_cas_conflict(
    tmp_path: Path, binding: str
) -> None:
    database = tmp_path / f"binding-{binding}.sqlite3"
    adapter = SqliteEventStore(database)
    adapter.init_schema()
    first = receipt("command-binding-first")
    adapter.append("cycle-1", 0, [event(1, first.command_id)], [], first)
    second = receipt("command-binding-second", expected_version=1)
    candidate = event(2, second.command_id, event_type=EventType.CYCLE_STARTED)
    if binding == "fsm":
        candidate = replace(candidate, fsm_spec_hash="d" * 64)
    else:
        candidate = replace(candidate, config_version="config-v2")

    with pytest.raises(StreamBindingConflict):
        adapter.append("cycle-1", 1, [candidate], [], second)
    assert len(adapter.load("cycle-1")) == 1
    adapter.close()


def test_no_event_receipt_deduplicates_after_the_stream_advances(tmp_path: Path) -> None:
    database = tmp_path / "no-event-receipt.sqlite3"
    adapter = SqliteEventStore(database)
    adapter.init_schema()
    rejected = receipt("command-rejected")

    first = adapter.append("cycle-1", 0, [], [], rejected)
    assert first.new_version == 0
    assert first.receipt.event_ids == ()
    assert adapter.load("cycle-1") == []

    accepted = receipt("command-accepted")
    adapter.append("cycle-1", 0, [event(1, accepted.command_id)], [], accepted)
    retried = adapter.append("cycle-1", 0, [], [], rejected)

    assert retried.deduplicated is True
    assert retried.receipt == first.receipt
    assert len(adapter.load("cycle-1")) == 1
    adapter.close()
