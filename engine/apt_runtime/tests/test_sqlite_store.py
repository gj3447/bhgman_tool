"""Contract and falsifier tests for the SQLite durable event store.

# KG: apt-tpa-legion-engine-canon-2026-06-12
# KG: APT_SCW_TDAD_canonical
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
import sqlite3
from threading import Barrier, Event as ThreadEvent

import pytest

from engine.apt_runtime.adapters.sqlite_store import SqliteEventStore
from engine.apt_runtime.domain.commands import CanonicalCommandEnvelope
from engine.apt_runtime.domain.events import EventEnvelope, EventType, GuardResult
from engine.apt_runtime.domain.fsm_spec import load_default_spec
from engine.apt_runtime.domain.reducer import replay
from engine.apt_runtime.domain.state import state_hash
from engine.apt_runtime.domain.state_codec import STATE_CODEC_VERSION, decode_state, encode_state
from engine.apt_runtime.ports.event_store import (
    AppendResult,
    CommandIdConflict,
    CommandReceiptDraft,
    OutboxRecord,
    PersistenceSchemaError,
    Snapshot,
    StoreConflict,
    StoreCorruption,
    StoreError,
)


SPEC = load_default_spec()
NOW = "2026-07-14T00:00:00Z"


def event(
    version: int,
    command_id: str,
    *,
    stream_id: str = "cycle-1",
    event_id: str | None = None,
    event_type: EventType = EventType.CYCLE_CREATED,
    effect_id: str | None = None,
    fsm_spec_hash: str | None = None,
) -> EventEnvelope:
    payload: dict[str, object]
    if event_type is EventType.CYCLE_CREATED:
        payload = {
            "config_snapshot_ref": "config://v1",
            "config_snapshot_hash": "a" * 64,
            "canon_snapshot_ref": "kg://snapshot/1",
            "canon_snapshot_hash": "b" * 64,
        }
    elif event_type is EventType.CYCLE_STARTED:
        payload = {
            "guard_result": GuardResult.PASS.value,
            "guard_evidence_refs": ["evidence-1"],
        }
    elif event_type is EventType.EFFECT_QUEUED:
        payload = {
            "capability": "artifact.realize",
            "provider": "fake-hades",
            "risk_class": "LOCAL_REVERSIBLE",
            "idempotency_key": f"idem-{effect_id}",
            "input_ref": "artifact://input/1",
            "input_hash": "c" * 64,
        }
    else:  # pragma: no cover - helper is intentionally closed over used cases
        raise AssertionError(event_type)
    return EventEnvelope.create(
        event_id=event_id or f"event-{version}",
        stream_id=stream_id,
        stream_version=version,
        event_type=event_type,
        schema_version="1.0.0",
        fsm_spec_hash=fsm_spec_hash or SPEC.spec_hash,
        cycle_id=stream_id,
        work_item_id="work-1" if effect_id is not None else None,
        effect_id=effect_id,
        generation=1 if effect_id is not None else None,
        actor="test",
        correlation_id="corr-1",
        causation_id=f"cause-{version}",
        command_id=command_id,
        config_version="config-v1",
        payload=payload,
        created_at=NOW,
    )


def receipt(
    command_id: str, *, intent: str = "test", expected_version: int = 0
) -> CommandReceiptDraft:
    command = CanonicalCommandEnvelope(
        command_id=command_id,
        command_type="TestCommand",
        schema_version="1.0.0",
        cycle_id="cycle-1",
        expected_version=expected_version,
        actor="test",
        authorization_context={"role": "test"},
        correlation_id="corr-1",
        causation_id=f"cause-{command_id}",
        input={"intent": intent},
        issued_at=NOW,
    )
    return CommandReceiptDraft.create(
        command=command,
        response={"accepted": True, "command_id": command_id},
        created_at=NOW,
    )


def outbox(command_id: str, *, effect_id: str = "effect-1") -> OutboxRecord:
    return OutboxRecord.create(
        outbox_id=f"outbox-{effect_id}",
        stream_id="cycle-1",
        effect_id=effect_id,
        command_id=command_id,
        payload={
            "capability": "artifact.realize",
            "provider": "fake-hades",
            "risk_class": "LOCAL_REVERSIBLE",
            "idempotency_key": f"idem-{effect_id}",
            "input_ref": "artifact://input/1",
            "input_hash": "c" * 64,
        },
        created_at=NOW,
    )


@pytest.fixture
def store(tmp_path: Path):
    adapter = SqliteEventStore(tmp_path / "apt.sqlite3")
    adapter.init_schema()
    try:
        yield adapter
    finally:
        adapter.close()


def test_append_load_receipt_and_same_command_retry_are_atomic(store: SqliteEventStore) -> None:
    command = receipt("command-1")
    first = store.append("cycle-1", 0, [event(1, command.command_id)], [], command)

    assert first == AppendResult(new_version=1, receipt=first.receipt, deduplicated=False)
    assert store.load("cycle-1") == [event(1, command.command_id)]
    assert store.load_command_receipt(command.command_id) == first.receipt
    assert store.load_outbox("cycle-1") == []

    retried = store.append("cycle-1", 0, [], [], command)
    assert retried.deduplicated is True
    assert retried.receipt == first.receipt
    assert store.load("cycle-1") == [event(1, command.command_id)]

    with pytest.raises(CommandIdConflict):
        store.append("cycle-1", 1, [], [], receipt("command-1", intent="different"))


def test_batch_versions_and_after_version_boundary_roundtrip(store: SqliteEventStore) -> None:
    command = receipt("command-batch")
    events = [
        event(1, command.command_id),
        event(2, command.command_id, event_type=EventType.CYCLE_STARTED),
    ]

    result = store.append("cycle-1", 0, events, [], command)

    assert result.new_version == 2
    assert result.receipt.event_ids == ("event-1", "event-2")
    assert store.load("cycle-1", after_version=1) == [events[1]]
    assert store.load("cycle-1", after_version=2) == []
    assert state_hash(replay(store.load("cycle-1"), SPEC)) == state_hash(replay(events, SPEC))


@pytest.mark.parametrize("case", ["gap", "stream", "command", "spec", "outbox"])
def test_invalid_batch_rolls_back_every_persistence_surface(tmp_path: Path, case: str) -> None:
    adapter = SqliteEventStore(tmp_path / f"{case}.sqlite3")
    adapter.init_schema()
    command = receipt("command-invalid")
    candidate = event(1, command.command_id)
    candidates = [candidate]
    records: list[OutboxRecord] = []
    if case == "gap":
        candidate = replace(candidate, stream_version=2)
    elif case == "stream":
        candidate = replace(candidate, stream_id="other-cycle")
    elif case == "command":
        candidate = replace(candidate, command_id="other-command")
    elif case == "spec":
        candidates = [
            candidate,
            event(
                2,
                command.command_id,
                event_type=EventType.CYCLE_STARTED,
                fsm_spec_hash="d" * 64,
            ),
        ]
    elif case == "outbox":
        records = [outbox(command.command_id)]
    if case != "spec":
        candidates = [candidate]

    with pytest.raises(PersistenceSchemaError):
        adapter.append("cycle-1", 0, candidates, records, command)

    assert adapter.load("cycle-1") == []
    assert adapter.load_command_receipt(command.command_id) is None
    assert adapter.load_outbox("cycle-1") == []
    adapter.close()


def test_outbox_constraint_failure_rolls_back_head_event_and_receipt(tmp_path: Path) -> None:
    database = tmp_path / "rollback.sqlite3"
    adapter = SqliteEventStore(database)
    adapter.init_schema()
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TRIGGER reject_outbox BEFORE INSERT ON apt_outbox "
            "BEGIN SELECT RAISE(ABORT, 'injected outbox failure'); END"
        )

    command = receipt("command-effect")
    queued = event(
        1,
        command.command_id,
        event_type=EventType.EFFECT_QUEUED,
        effect_id="effect-1",
    )
    with pytest.raises(StoreError, match="outbox failure"):
        adapter.append("cycle-1", 0, [queued], [outbox(command.command_id)], command)

    assert adapter.load("cycle-1") == []
    assert adapter.load_command_receipt(command.command_id) is None
    assert adapter.load_outbox("cycle-1") == []
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT count(*) FROM apt_stream_heads").fetchone() == (0,)
        assert connection.execute("SELECT count(*) FROM apt_events").fetchone() == (0,)
    adapter.close()


def test_duplicate_queued_effect_identity_is_rejected_before_io(
    store: SqliteEventStore,
) -> None:
    command = receipt("command-duplicate-effect")
    queued = [
        event(
            version,
            command.command_id,
            event_type=EventType.EFFECT_QUEUED,
            effect_id="effect-duplicate",
        )
        for version in (1, 2)
    ]
    record = outbox(command.command_id, effect_id="effect-duplicate")

    with pytest.raises(PersistenceSchemaError, match="EffectQueued identities must be unique"):
        store.append("cycle-1", 0, queued, [record], command)

    assert store.load("cycle-1") == []
    assert store.load_command_receipt(command.command_id) is None


@pytest.mark.parametrize("missing", ["event", "outbox"])
def test_receipt_detects_missing_rows_after_direct_tamper(tmp_path: Path, missing: str) -> None:
    database = tmp_path / f"missing-{missing}.sqlite3"
    adapter = SqliteEventStore(database)
    adapter.init_schema()
    command = receipt("command-receipt-tamper")
    queued = event(
        1,
        command.command_id,
        event_type=EventType.EFFECT_QUEUED,
        effect_id="effect-receipt-tamper",
    )
    record = outbox(command.command_id, effect_id="effect-receipt-tamper")
    adapter.append("cycle-1", 0, [queued], [record], command)

    table = "apt_events" if missing == "event" else "apt_outbox"
    with sqlite3.connect(database) as connection:
        connection.execute(f"DELETE FROM {table}")

    with pytest.raises(StoreCorruption, match="receipt"):
        adapter.load_command_receipt(command.command_id)
    with pytest.raises(StoreCorruption, match="receipt"):
        adapter.append("cycle-1", 0, [], [], command)
    adapter.close()


def test_two_connections_racing_same_expected_version_have_one_clean_conflict(
    tmp_path: Path,
) -> None:
    database = tmp_path / "race.sqlite3"
    stores = [SqliteEventStore(database), SqliteEventStore(database)]
    for adapter in stores:
        adapter.init_schema()
    barrier = Barrier(2)

    def append_one(index: int) -> AppendResult | StoreConflict:
        command = receipt(f"command-race-{index}")
        candidate = event(
            1,
            command.command_id,
            event_id=f"event-race-{index}",
        )
        barrier.wait()
        try:
            return stores[index].append("cycle-1", 0, [candidate], [], command)
        except StoreConflict as exc:
            return exc

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(append_one, range(2)))

    assert sum(isinstance(item, AppendResult) for item in outcomes) == 1
    conflicts = [item for item in outcomes if isinstance(item, StoreConflict)]
    assert len(conflicts) == 1
    assert conflicts[0].expected_version == 0
    assert conflicts[0].actual_version == 1
    assert len(stores[0].load("cycle-1")) == 1
    for adapter in stores:
        adapter.close()


def test_load_uses_one_read_snapshot_during_a_concurrent_append(tmp_path: Path) -> None:
    database = tmp_path / "read-snapshot.sqlite3"
    reader = SqliteEventStore(database)
    writer = SqliteEventStore(database)
    reader.init_schema()
    writer.init_schema()
    first_command = receipt("command-read-first")
    reader.append("cycle-1", 0, [event(1, first_command.command_id)], [], first_command)

    head_read = ThreadEvent()
    writer_done = ThreadEvent()
    connection = reader._connection

    class BlockingHeadCursor:
        def __init__(self, cursor: sqlite3.Cursor) -> None:
            self._cursor = cursor

        def fetchone(self):
            row = self._cursor.fetchone()
            head_read.set()
            assert writer_done.wait(timeout=5), "writer did not finish while reader was paused"
            return row

        def __getattr__(self, name: str):
            return getattr(self._cursor, name)

    class InterleavingConnection:
        intercepted = False

        def execute(self, sql: str, parameters=()):
            cursor = connection.execute(sql, parameters)
            if not self.intercepted and sql.startswith(
                "SELECT current_version, fsm_spec_hash, config_version"
            ):
                self.intercepted = True
                return BlockingHeadCursor(cursor)
            return cursor

        def __getattr__(self, name: str):
            return getattr(connection, name)

    reader._connection = InterleavingConnection()  # type: ignore[assignment]
    with ThreadPoolExecutor(max_workers=1) as pool:
        loaded = pool.submit(reader.load, "cycle-1")
        assert head_read.wait(timeout=5), "reader did not pause after reading the head"
        second_command = receipt("command-read-second", expected_version=1)
        try:
            writer.append(
                "cycle-1",
                1,
                [event(2, second_command.command_id, event_type=EventType.CYCLE_STARTED)],
                [],
                second_command,
            )
        finally:
            writer_done.set()
        assert loaded.result(timeout=5) == [event(1, first_command.command_id)]

    reader.close()
    writer.close()


def test_direct_payload_tamper_is_reported_as_store_corruption(
    tmp_path: Path,
) -> None:
    database = tmp_path / "tamper.sqlite3"
    adapter = SqliteEventStore(database)
    adapter.init_schema()
    command = receipt("command-tamper")
    adapter.append("cycle-1", 0, [event(1, command.command_id)], [], command)

    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE apt_events SET payload_json = ? WHERE event_id = 'event-1'", (b"{}",)
        )

    with pytest.raises(StoreCorruption, match="payload_hash"):
        adapter.load("cycle-1")
    adapter.close()


def test_snapshot_survives_reopen_and_preserves_canonical_state_hash(tmp_path: Path) -> None:
    database = tmp_path / "snapshot.sqlite3"
    adapter = SqliteEventStore(database)
    adapter.init_schema()
    command = receipt("command-snapshot")
    events = [event(1, command.command_id)]
    adapter.append("cycle-1", 0, events, [], command)
    state = replay(events, SPEC)
    blob = encode_state(state)
    snapshot = Snapshot(
        stream_id="cycle-1",
        stream_version=state.version,
        fsm_spec_hash=state.fsm_spec_hash,
        codec_version=STATE_CODEC_VERSION,
        state_hash=state_hash(state),
        state_blob=blob,
        created_at=NOW,
    )
    adapter.save_snapshot(snapshot)
    adapter.save_snapshot(snapshot)
    adapter.save_snapshot(replace(snapshot, created_at="2026-07-14T00:00:01Z"))
    adapter.close()

    reopened = SqliteEventStore(database)
    reopened.init_schema()
    loaded = reopened.load_snapshot("cycle-1")
    assert loaded == snapshot
    assert loaded is not None
    assert state_hash(decode_state(loaded.state_blob)) == state_hash(
        replay(reopened.load("cycle-1"), SPEC)
    )
    reopened.close()


def test_snapshot_configuration_must_match_the_stream_head(store: SqliteEventStore) -> None:
    command = receipt("command-snapshot-config")
    events = [event(1, command.command_id)]
    store.append("cycle-1", 0, events, [], command)
    drifted_state = replace(replay(events, SPEC), config_version="config-v2")
    blob = encode_state(drifted_state)
    snapshot = Snapshot(
        stream_id="cycle-1",
        stream_version=drifted_state.version,
        fsm_spec_hash=drifted_state.fsm_spec_hash,
        codec_version=STATE_CODEC_VERSION,
        state_hash=state_hash(drifted_state),
        state_blob=blob,
        created_at=NOW,
    )

    with pytest.raises(StoreError, match="configuration differs"):
        store.save_snapshot(snapshot)
    assert store.load_snapshot("cycle-1") is None
