"""Adversarial race, schema, and cross-row tests for PostgreSQL parity.

# KG: apt-tpa-legion-engine-canon-2026-06-12
# Design: SYMPOSIUM/THEORY/APT/vnext/APT_ENGINE_FSM_DESIGN_2026-07-13.md §12.1
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Barrier

import psycopg
import pytest
from psycopg.conninfo import make_conninfo

from engine.apt_runtime.adapters.postgres_store import PostgresEventStore
from engine.apt_runtime.domain.canonical import canonical_json_bytes, canonical_sha256
from engine.apt_runtime.domain.commands import CanonicalCommandEnvelope
from engine.apt_runtime.domain.events import EventType
from engine.apt_runtime.domain.reducer import replay
from engine.apt_runtime.domain.state import state_hash
from engine.apt_runtime.domain.state_codec import STATE_CODEC_VERSION, encode_state
from engine.apt_runtime.ports.event_store import (
    AppendResult,
    CommandIdConflict,
    CommandReceiptDraft,
    Snapshot,
    StoreConflict,
    StoreCorruption,
    StoreError,
)
from engine.apt_runtime.tests.test_postgres_store import _wait_until_session_is_lock_blocked
from engine.apt_runtime.tests.test_sqlite_store import NOW, SPEC, event, outbox, receipt


def _draft(
    command_id: str,
    stream_id: str,
    *,
    expected_version: int = 0,
    intent: str = "test",
) -> CommandReceiptDraft:
    command = CanonicalCommandEnvelope(
        command_id=command_id,
        command_type="PostgresAdversarialCommand",
        schema_version="1.0.0",
        cycle_id=stream_id,
        expected_version=expected_version,
        actor="test",
        authorization_context={"role": "test"},
        correlation_id="corr-adversarial",
        causation_id=f"cause-{command_id}-{stream_id}",
        input={"intent": intent},
        issued_at=NOW,
    )
    return CommandReceiptDraft.create(
        command=command,
        response={"accepted": True, "stream_id": stream_id},
        created_at=NOW,
    )


def test_postgres_multi_effect_outbox_order_survives_reconnect(postgres_sandbox) -> None:
    adapter = PostgresEventStore(postgres_sandbox.dsn)
    adapter.init_schema()
    command = receipt("command-pg-ordered-effects")
    effect_ids = ("effect-z", "effect-a", "effect-m")
    events = [
        event(
            version,
            command.command_id,
            event_id=f"event-ordered-{version}",
            event_type=EventType.EFFECT_QUEUED,
            effect_id=effect_id,
        )
        for version, effect_id in enumerate(effect_ids, start=1)
    ]
    records = [outbox(command.command_id, effect_id=effect_id) for effect_id in effect_ids]

    result = adapter.append("cycle-1", 0, events, records, command)
    adapter.close()

    reopened = PostgresEventStore(postgres_sandbox.dsn)
    try:
        assert result.receipt.outbox_ids == tuple(record.outbox_id for record in records)
        assert reopened.load_outbox("cycle-1") == records
        assert reopened.load_command_receipt(command.command_id) == result.receipt
    finally:
        reopened.close()


def test_concurrent_command_id_reuse_across_streams_has_one_clean_loser(
    postgres_sandbox,
) -> None:
    stores = [PostgresEventStore(postgres_sandbox.dsn) for _ in range(2)]
    for adapter in stores:
        adapter.init_schema()
    streams = ("cycle-command-a", "cycle-command-b")
    drafts = tuple(_draft("command-global-race", stream_id) for stream_id in streams)
    candidates = tuple(
        event(
            1,
            draft.command_id,
            stream_id=stream_id,
            event_id=f"event-{stream_id}",
        )
        for stream_id, draft in zip(streams, drafts, strict=True)
    )
    barrier = Barrier(2)

    def append_one(index: int) -> AppendResult | CommandIdConflict:
        barrier.wait()
        try:
            return stores[index].append(streams[index], 0, [candidates[index]], [], drafts[index])
        except CommandIdConflict as exc:
            return exc

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(append_one, range(2)))
        winners = [item for item in outcomes if isinstance(item, AppendResult)]
        losers = [
            index for index, item in enumerate(outcomes) if isinstance(item, CommandIdConflict)
        ]
        assert len(winners) == 1
        assert len(losers) == 1
        loser_stream = streams[losers[0]]
        assert stores[0].load(loser_stream) == []
        assert stores[0].load_outbox(loser_stream) == []
        assert stores[0].load_command_receipt("command-global-race") == winners[0].receipt
    finally:
        for adapter in stores:
            adapter.close()


def test_no_event_append_waits_behind_inflight_stream_creation(postgres_sandbox) -> None:
    creator_name = f"apt_creator_{postgres_sandbox.schema}"
    rejection_name = f"apt_rejection_{postgres_sandbox.schema}"
    creator = PostgresEventStore(postgres_sandbox.dsn_for(creator_name))
    rejection = PostgresEventStore(postgres_sandbox.dsn_for(rejection_name))
    creator.init_schema()
    create_draft = receipt("command-stream-create")
    rejected_draft = receipt("command-stream-rejected")
    created = event(1, create_draft.command_id, event_id="event-stream-create")
    locker = psycopg.connect(postgres_sandbox.dsn)
    locker.execute("LOCK TABLE apt_events IN ACCESS EXCLUSIVE MODE")
    pool = ThreadPoolExecutor(max_workers=2)

    def append_rejection() -> StoreConflict | AppendResult:
        try:
            return rejection.append("cycle-1", 0, [], [], rejected_draft)
        except StoreConflict as exc:
            return exc

    try:
        create_call = pool.submit(
            creator.append,
            "cycle-1",
            0,
            [created],
            [],
            create_draft,
        )
        _wait_until_session_is_lock_blocked(postgres_sandbox.base_dsn, creator_name)
        rejection_call = pool.submit(append_rejection)
        _wait_until_session_is_lock_blocked(postgres_sandbox.base_dsn, rejection_name)
        locker.commit()

        assert create_call.result(timeout=8).new_version == 1
        rejected = rejection_call.result(timeout=8)
        assert isinstance(rejected, StoreConflict)
        assert rejected.expected_version == 0
        assert rejected.actual_version == 1
        assert creator.load_command_receipt(rejected_draft.command_id) is None
        assert creator.load("cycle-1") == [created]
    finally:
        if not locker.closed:
            locker.rollback()
            locker.close()
        pool.shutdown(wait=False, cancel_futures=True)
        creator.close()
        rejection.close()


def test_coherent_outbox_bytea_tamper_is_rejected_on_every_read_path(
    postgres_sandbox,
) -> None:
    adapter = PostgresEventStore(postgres_sandbox.dsn)
    adapter.init_schema()
    command = receipt("command-pg-coherent-tamper")
    queued = event(
        1,
        command.command_id,
        event_type=EventType.EFFECT_QUEUED,
        effect_id="effect-pg-coherent-tamper",
    )
    record = outbox(command.command_id, effect_id="effect-pg-coherent-tamper")
    adapter.append("cycle-1", 0, [queued], [record], command)
    altered = {"capability": "workspace.mutate", "input_ref": "artifact://other"}
    with psycopg.connect(postgres_sandbox.dsn) as connection:
        connection.execute(
            "UPDATE apt_outbox SET payload_json = %s, payload_hash = %s WHERE outbox_id = %s",
            (canonical_json_bytes(altered), canonical_sha256(altered), record.outbox_id),
        )

    try:
        read_paths = (
            lambda: adapter.load_command_receipt(command.command_id),
            lambda: adapter.load("cycle-1"),
            lambda: adapter.load_outbox("cycle-1"),
        )
        for read in read_paths:
            with pytest.raises(StoreCorruption, match="executable payloads differ"):
                read()
    finally:
        adapter.close()


def test_deleted_outbox_is_rejected_by_the_outbox_stream_read(postgres_sandbox) -> None:
    adapter = PostgresEventStore(postgres_sandbox.dsn)
    adapter.init_schema()
    command = receipt("command-pg-deleted-outbox")
    queued = event(
        1,
        command.command_id,
        event_type=EventType.EFFECT_QUEUED,
        effect_id="effect-pg-deleted-outbox",
    )
    record = outbox(command.command_id, effect_id="effect-pg-deleted-outbox")
    adapter.append("cycle-1", 0, [queued], [record], command)
    with psycopg.connect(postgres_sandbox.dsn) as connection:
        connection.execute("DELETE FROM apt_outbox WHERE outbox_id = %s", (record.outbox_id,))

    try:
        with pytest.raises(StoreCorruption, match="receipt outbox"):
            adapter.load_outbox("cycle-1")
    finally:
        adapter.close()


def test_no_event_receipt_rejects_committed_version_tamper(postgres_sandbox) -> None:
    adapter = PostgresEventStore(postgres_sandbox.dsn)
    adapter.init_schema()
    created = receipt("command-pg-before-no-event")
    adapter.append("cycle-1", 0, [event(1, created.command_id)], [], created)
    no_event = receipt("command-pg-no-event-seal", expected_version=1)
    adapter.append("cycle-1", 1, [], [], no_event)
    with psycopg.connect(postgres_sandbox.dsn) as connection:
        connection.execute(
            "UPDATE apt_command_receipts SET committed_version = 0 WHERE command_id = %s",
            (no_event.command_id,),
        )

    try:
        with pytest.raises(StoreCorruption, match="expected_version"):
            adapter.load_command_receipt(no_event.command_id)
    finally:
        adapter.close()


def test_receipt_and_retry_reject_stream_binding_tamper(postgres_sandbox) -> None:
    adapter = PostgresEventStore(postgres_sandbox.dsn)
    adapter.init_schema()
    command = receipt("command-pg-head-binding-tamper")
    adapter.append("cycle-1", 0, [event(1, command.command_id)], [], command)
    with psycopg.connect(postgres_sandbox.dsn) as connection:
        connection.execute(
            "UPDATE apt_stream_heads SET config_version = 'tampered' WHERE stream_id = 'cycle-1'"
        )

    try:
        with pytest.raises(StoreCorruption, match="stream head"):
            adapter.load_command_receipt(command.command_id)
        with pytest.raises(StoreCorruption, match="stream head"):
            adapter.append("cycle-1", 0, [], [], command)
    finally:
        adapter.close()


@pytest.mark.parametrize(
    "tamper",
    [
        "trigger",
        "nullable_head_version",
        "disabled_fk_triggers",
        "noncanonical_index_opclass",
        "shadow_c_collation",
    ],
)
def test_postgres_init_rejects_mutation_hooks_and_weakened_schema(
    postgres_sandbox,
    tamper: str,
) -> None:
    adapter = PostgresEventStore(postgres_sandbox.dsn)
    adapter.init_schema()
    adapter.close()
    with psycopg.connect(postgres_sandbox.dsn, autocommit=True) as connection:
        if tamper == "trigger":
            connection.execute(
                "CREATE FUNCTION unexpected_apt_trigger() RETURNS trigger "
                "LANGUAGE plpgsql AS $$ BEGIN RETURN NEW; END $$"
            )
            connection.execute(
                "CREATE TRIGGER unexpected_apt_trigger BEFORE INSERT ON apt_outbox "
                "FOR EACH ROW EXECUTE FUNCTION unexpected_apt_trigger()"
            )
        elif tamper == "nullable_head_version":
            connection.execute(
                "ALTER TABLE apt_stream_heads ALTER COLUMN current_version DROP NOT NULL"
            )
        elif tamper == "disabled_fk_triggers":
            connection.execute("ALTER TABLE apt_outbox DISABLE TRIGGER ALL")
        elif tamper == "noncanonical_index_opclass":
            connection.execute("DROP INDEX apt_events_stream_version_idx")
            connection.execute(
                "CREATE INDEX apt_events_stream_version_idx ON apt_events "
                "(stream_id text_pattern_ops, stream_version)"
            )
        else:
            schema = psycopg.sql.Identifier(postgres_sandbox.schema)
            connection.execute(
                psycopg.sql.SQL('CREATE COLLATION {}."C" FROM pg_catalog."C"').format(schema)
            )
            connection.execute("DROP INDEX apt_events_stream_version_idx")
            connection.execute(
                psycopg.sql.SQL(
                    "CREATE INDEX apt_events_stream_version_idx ON apt_events "
                    '(stream_id COLLATE {}."C", stream_version)'
                ).format(schema)
            )

    reopened = PostgresEventStore(postgres_sandbox.dsn)
    try:
        with pytest.raises(StoreCorruption, match="schema"):
            reopened.init_schema()
    finally:
        reopened.close()


def test_postgres_init_rejects_replica_session_that_disables_fk_triggers(
    postgres_sandbox,
) -> None:
    replica_dsn = make_conninfo(
        postgres_sandbox.dsn,
        options=(f"-csearch_path={postgres_sandbox.schema} -csession_replication_role=replica"),
    )
    adapter = PostgresEventStore(replica_dsn)
    try:
        with pytest.raises(StoreCorruption, match="schema"):
            adapter.init_schema()
    finally:
        adapter.close()


def test_failed_append_rolls_back_and_same_adapter_remains_reusable(postgres_sandbox) -> None:
    adapter = PostgresEventStore(postgres_sandbox.dsn)
    adapter.init_schema()
    with psycopg.connect(postgres_sandbox.dsn, autocommit=True) as connection:
        connection.execute(
            "CREATE FUNCTION fail_apt_outbox() RETURNS trigger LANGUAGE plpgsql AS $$ "
            "BEGIN RAISE EXCEPTION 'injected outbox failure'; END $$"
        )
        connection.execute(
            "CREATE TRIGGER fail_apt_outbox BEFORE INSERT ON apt_outbox "
            "FOR EACH ROW EXECUTE FUNCTION fail_apt_outbox()"
        )

    failed = receipt("command-pg-failed-append")
    queued = event(
        1,
        failed.command_id,
        event_id="event-pg-failed-append",
        event_type=EventType.EFFECT_QUEUED,
        effect_id="effect-pg-failed-append",
    )
    record = outbox(failed.command_id, effect_id="effect-pg-failed-append")
    with pytest.raises(StoreError, match="injected outbox failure"):
        adapter.append("cycle-1", 0, [queued], [record], failed)

    with psycopg.connect(postgres_sandbox.dsn, autocommit=True) as connection:
        connection.execute("DROP TRIGGER fail_apt_outbox ON apt_outbox")
        connection.execute("DROP FUNCTION fail_apt_outbox()")

    try:
        assert adapter.load("cycle-1") == []
        assert adapter.load_command_receipt(failed.command_id) is None
        succeeding = receipt("command-pg-after-failure")
        created = event(1, succeeding.command_id, event_id="event-pg-after-failure")
        result = adapter.append("cycle-1", 0, [created], [], succeeding)
        assert result.new_version == 1
        assert adapter.load("cycle-1") == [created]
    finally:
        adapter.close()


def test_divergent_same_version_snapshots_race_to_one_winner(postgres_sandbox) -> None:
    stores = [PostgresEventStore(postgres_sandbox.dsn) for _ in range(2)]
    for adapter in stores:
        adapter.init_schema()
    command = receipt("command-pg-snapshot-race")
    created = event(1, command.command_id, event_id="event-pg-snapshot-race")
    stores[0].append("cycle-1", 0, [created], [], command)
    state = replay([created], SPEC)
    divergent_state = replace(state, terminal_receipt_ref="receipt://divergent")
    snapshots = tuple(
        Snapshot(
            stream_id="cycle-1",
            stream_version=1,
            fsm_spec_hash=candidate.fsm_spec_hash,
            codec_version=STATE_CODEC_VERSION,
            state_hash=state_hash(candidate),
            state_blob=encode_state(candidate),
            created_at=NOW,
        )
        for candidate in (state, divergent_state)
    )
    barrier = Barrier(2)

    def save_one(index: int) -> StoreError | None:
        barrier.wait()
        try:
            stores[index].save_snapshot(snapshots[index])
        except StoreError as exc:
            return exc
        return None

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(save_one, range(2)))
        winners = [index for index, outcome in enumerate(outcomes) if outcome is None]
        assert len(winners) == 1
        assert sum(isinstance(outcome, StoreError) for outcome in outcomes) == 1
        assert stores[0].load_snapshot("cycle-1") == snapshots[winners[0]]
    finally:
        for adapter in stores:
            adapter.close()
