"""Real-Postgres parity contracts for the APT vNext durable event store.

# KG: apt-tpa-legion-engine-canon-2026-06-12
# Design: SYMPOSIUM/THEORY/APT/vnext/APT_ENGINE_FSM_DESIGN_2026-07-13.md §12.1
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Barrier
import time

import psycopg
import pytest

from engine.apt_runtime.adapters.postgres_store import PostgresEventStore
from engine.apt_runtime.domain.events import EventType
from engine.apt_runtime.domain.reducer import replay
from engine.apt_runtime.domain.state import state_hash
from engine.apt_runtime.domain.state_codec import STATE_CODEC_VERSION, encode_state
from engine.apt_runtime.ports.event_store import (
    AppendResult,
    PersistenceSchemaError,
    Snapshot,
    StoreConflict,
    StoreCorruption,
)
from engine.apt_runtime.tests.test_sqlite_store import NOW, SPEC, event, outbox, receipt


@pytest.fixture
def store(postgres_sandbox):
    adapter = PostgresEventStore(postgres_sandbox.dsn)
    adapter.init_schema()
    try:
        yield adapter
    finally:
        adapter.close()


def test_postgres_append_load_dedup_and_atomic_outbox(store: PostgresEventStore) -> None:
    command = receipt("command-pg-effect")
    queued = event(
        1,
        command.command_id,
        event_type=EventType.EFFECT_QUEUED,
        effect_id="effect-pg",
    )
    record = outbox(command.command_id, effect_id="effect-pg")

    first = store.append("cycle-1", 0, [queued], [record], command)

    assert first.deduplicated is False
    assert first.new_version == 1
    assert first.receipt.event_ids == (queued.event_id,)
    assert first.receipt.outbox_ids == (record.outbox_id,)
    assert store.load("cycle-1") == [queued]
    assert store.load_outbox("cycle-1") == [record]
    assert store.load_command_receipt(command.command_id) == first.receipt

    retried = store.append("cycle-1", 0, [], [], command)
    assert retried == replace(first, deduplicated=True)
    assert store.load("cycle-1") == [queued]
    assert store.load_outbox("cycle-1") == [record]


def test_postgres_snapshot_survives_reconnect_and_is_content_idempotent(
    postgres_sandbox,
) -> None:
    first_store = PostgresEventStore(postgres_sandbox.dsn)
    first_store.init_schema()
    command = receipt("command-pg-snapshot")
    created = event(1, command.command_id)
    first_store.append("cycle-1", 0, [created], [], command)
    state = replay([created], SPEC)
    snapshot = Snapshot(
        stream_id="cycle-1",
        stream_version=1,
        fsm_spec_hash=state.fsm_spec_hash,
        codec_version=STATE_CODEC_VERSION,
        state_hash=state_hash(state),
        state_blob=encode_state(state),
        created_at=NOW,
    )
    first_store.save_snapshot(snapshot)
    first_store.save_snapshot(replace(snapshot, created_at="2026-07-14T00:00:01Z"))
    first_store.close()

    reopened = PostgresEventStore(postgres_sandbox.dsn)
    try:
        reopened.init_schema()
        assert reopened.load_snapshot("cycle-1") == snapshot
        assert reopened.load("cycle-1") == [created]
    finally:
        reopened.close()


def test_postgres_no_event_receipt_deduplicates_after_stream_advances(
    store: PostgresEventStore,
) -> None:
    rejected = receipt("command-pg-rejected")
    first = store.append("cycle-1", 0, [], [], rejected)
    assert first.new_version == 0
    assert first.receipt.event_ids == ()
    assert first.receipt.outbox_ids == ()

    accepted = receipt("command-pg-created")
    store.append("cycle-1", 0, [event(1, accepted.command_id)], [], accepted)

    retried = store.append("cycle-1", 0, [], [], rejected)
    assert retried.deduplicated is True
    assert retried.receipt == first.receipt
    assert len(store.load("cycle-1")) == 1


@pytest.mark.parametrize("case", ["gap", "wrong_stream", "unpaired_outbox"])
def test_postgres_invalid_batch_rolls_back_every_surface(
    store: PostgresEventStore,
    case: str,
) -> None:
    command = receipt(f"command-pg-invalid-{case}")
    candidate = event(1, command.command_id)
    records = []
    if case == "gap":
        candidate = replace(candidate, stream_version=2)
    elif case == "wrong_stream":
        candidate = replace(candidate, stream_id="cycle-other", cycle_id="cycle-other")
    else:
        records = [outbox(command.command_id, effect_id="effect-unpaired")]

    with pytest.raises(PersistenceSchemaError):
        store.append("cycle-1", 0, [candidate], records, command)

    assert store.load("cycle-1") == []
    assert store.load_command_receipt(command.command_id) is None
    assert store.load_outbox("cycle-1") == []


def test_postgres_two_commands_racing_one_version_have_one_typed_conflict(
    postgres_sandbox,
) -> None:
    stores = [PostgresEventStore(postgres_sandbox.dsn) for _ in range(2)]
    for adapter in stores:
        adapter.init_schema()
    barrier = Barrier(2)

    def append_one(index: int):
        command = receipt(f"command-pg-race-{index}")
        candidate = event(
            1,
            command.command_id,
            event_id=f"event-pg-race-{index}",
        )
        barrier.wait()
        try:
            return stores[index].append("cycle-1", 0, [candidate], [], command)
        except StoreConflict as exc:
            return exc

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(append_one, range(2)))
        assert sum(isinstance(item, AppendResult) for item in outcomes) == 1
        conflicts = [item for item in outcomes if isinstance(item, StoreConflict)]
        assert len(conflicts) == 1
        assert conflicts[0].expected_version == 0
        assert conflicts[0].actual_version == 1
        assert len(stores[0].load("cycle-1")) == 1
    finally:
        for adapter in stores:
            adapter.close()


def test_postgres_identical_command_race_converges_to_one_receipt(
    postgres_sandbox,
) -> None:
    stores = [PostgresEventStore(postgres_sandbox.dsn) for _ in range(2)]
    for adapter in stores:
        adapter.init_schema()
    command = receipt("command-pg-identical")
    candidate = event(1, command.command_id, event_id="event-pg-identical")
    barrier = Barrier(2)

    def append_same(index: int) -> AppendResult:
        barrier.wait()
        return stores[index].append("cycle-1", 0, [candidate], [], command)

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(append_same, range(2)))
        assert sorted(item.deduplicated for item in results) == [False, True]
        assert results[0].receipt == results[1].receipt
        assert stores[0].load("cycle-1") == [candidate]
    finally:
        for adapter in stores:
            adapter.close()


def _wait_until_session_is_lock_blocked(base_dsn: str, application_name: str) -> None:
    deadline = time.monotonic() + 8
    with psycopg.connect(base_dsn, autocommit=True) as observer:
        while time.monotonic() < deadline:
            row = observer.execute(
                "SELECT wait_event_type FROM pg_stat_activity "
                "WHERE application_name = %s ORDER BY backend_start DESC LIMIT 1",
                (application_name,),
            ).fetchone()
            if row is not None and row[0] == "Lock":
                return
            time.sleep(0.02)
    raise AssertionError(f"Postgres session {application_name!r} did not block on the test lock")


def test_postgres_load_observes_one_snapshot_across_a_concurrent_append(
    postgres_sandbox,
) -> None:
    setup = PostgresEventStore(postgres_sandbox.dsn)
    setup.init_schema()
    first_command = receipt("command-pg-read-first")
    first = event(1, first_command.command_id)
    setup.append("cycle-1", 0, [first], [], first_command)
    setup.close()

    writer_name = f"apt_writer_{postgres_sandbox.schema}"
    reader_name = f"apt_reader_{postgres_sandbox.schema}"
    writer = PostgresEventStore(postgres_sandbox.dsn_for(writer_name))
    reader = PostgresEventStore(postgres_sandbox.dsn_for(reader_name))
    locker = psycopg.connect(postgres_sandbox.dsn)
    locker.execute("LOCK TABLE apt_events IN ACCESS EXCLUSIVE MODE")
    second_command = receipt("command-pg-read-second", expected_version=1)
    second = event(
        2,
        second_command.command_id,
        event_id="event-pg-read-second",
        event_type=EventType.CYCLE_STARTED,
    )
    pool = ThreadPoolExecutor(max_workers=2)
    try:
        written = pool.submit(
            writer.append,
            "cycle-1",
            1,
            [second],
            [],
            second_command,
        )
        _wait_until_session_is_lock_blocked(postgres_sandbox.base_dsn, writer_name)
        loaded = pool.submit(reader.load, "cycle-1")
        _wait_until_session_is_lock_blocked(postgres_sandbox.base_dsn, reader_name)
        locker.commit()
        assert written.result(timeout=8).new_version == 2
        assert loaded.result(timeout=8) == [first]
    finally:
        if not locker.closed:
            locker.rollback()
            locker.close()
        pool.shutdown(wait=False, cancel_futures=True)
        writer.close()
        reader.close()


def test_postgres_init_rejects_an_incomplete_schema_claiming_v1(
    postgres_sandbox,
) -> None:
    with psycopg.connect(postgres_sandbox.dsn, autocommit=True) as connection:
        connection.execute(
            "CREATE TABLE apt_store_schema "
            "(singleton INTEGER PRIMARY KEY, schema_version INTEGER NOT NULL)"
        )
        connection.execute("INSERT INTO apt_store_schema VALUES (1, 1)")
        connection.execute("CREATE TABLE apt_stream_heads (stream_id TEXT PRIMARY KEY)")

    adapter = PostgresEventStore(postgres_sandbox.dsn)
    try:
        with pytest.raises(StoreCorruption, match="schema"):
            adapter.init_schema()
    finally:
        adapter.close()
