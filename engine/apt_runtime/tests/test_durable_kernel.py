"""Trust-boundary and replay falsifiers for the Slice 1A DurableKernel.

# KG: apt-tpa-legion-engine-canon-2026-06-12
# KG: APT_SCW_TDAD_canonical
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from threading import Barrier, Event as ThreadEvent

import pytest

from engine.apt_runtime.application import (
    CommandDecision,
    DecisionOutcome,
    DurableKernel,
    DurableKernelError,
    EffectRequest,
)
from engine.apt_runtime.adapters.sqlite_store import SqliteEventStore
from engine.apt_runtime.domain.commands import CanonicalCommandEnvelope, CommandSchemaError
from engine.apt_runtime.domain.events import EventEnvelope, EventType, GuardResult
from engine.apt_runtime.domain.fsm_spec import load_default_spec
from engine.apt_runtime.domain.reducer import AggregateNotInitializedError, replay
from engine.apt_runtime.domain.state import state_hash
from engine.apt_runtime.domain.state_codec import STATE_CODEC_VERSION, encode_state
from engine.apt_runtime.ports.event_store import (
    AppendResult,
    CommandIdConflict,
    EventStore,
    Snapshot,
    StoreConflict,
    StoreCorruption,
)


SPEC = load_default_spec()
NOW = "2026-07-14T00:00:00Z"


def command(
    command_id: str,
    mode: str,
    expected_version: int,
    *,
    actor: str = "tester",
) -> CanonicalCommandEnvelope:
    return CanonicalCommandEnvelope(
        command_id=command_id,
        command_type="TestCommand",
        schema_version="1.0.0",
        cycle_id="cycle-kernel",
        expected_version=expected_version,
        actor=actor,
        authorization_context={"role": "test", "scope": ["cycle:write"]},
        correlation_id="corr-kernel",
        causation_id=f"cause-{command_id}",
        input={"mode": mode},
        issued_at=NOW,
    )


def envelope(command_value: CanonicalCommandEnvelope, event_type: EventType) -> EventEnvelope:
    if event_type is EventType.CYCLE_CREATED:
        payload = {
            "config_snapshot_ref": "config://v1",
            "config_snapshot_hash": "a" * 64,
            "canon_snapshot_ref": "kg://snapshot/1",
            "canon_snapshot_hash": "b" * 64,
        }
        effect_id = None
    elif event_type is EventType.CYCLE_STARTED:
        payload = {
            "guard_result": GuardResult.PASS.value,
            "guard_evidence_refs": ["evidence-1"],
        }
        effect_id = None
    elif event_type is EventType.EFFECT_QUEUED:
        payload = {
            "capability": "artifact.realize",
            "provider": "fake-hades",
            "risk_class": "LOCAL_REVERSIBLE",
            "idempotency_key": f"idem-{command_value.command_id}",
            "input_ref": "artifact://input/1",
            "input_hash": "c" * 64,
        }
        effect_id = f"effect-{command_value.command_id}"
    else:  # pragma: no cover - closed helper
        raise AssertionError(event_type)
    return EventEnvelope.create(
        event_id=f"event-{command_value.command_id}",
        stream_id=command_value.cycle_id,
        stream_version=command_value.expected_version + 1,
        event_type=event_type,
        schema_version="1.0.0",
        fsm_spec_hash=SPEC.spec_hash,
        cycle_id=command_value.cycle_id,
        effect_id=effect_id,
        actor=command_value.actor,
        correlation_id=command_value.correlation_id,
        causation_id=command_value.causation_id,
        command_id=command_value.command_id,
        config_version="config-v1",
        payload=payload,
        created_at=NOW,
    )


class TestDecider:
    def decide(self, state, command_value: CanonicalCommandEnvelope) -> CommandDecision:
        mode = command_value.input["mode"]
        if mode == "reject":
            return CommandDecision(DecisionOutcome.REJECTED, (), (), {"reason": "denied"})
        event_type = {
            "create": EventType.CYCLE_CREATED,
            "start": EventType.CYCLE_STARTED,
            "effect": EventType.EFFECT_QUEUED,
        }[mode]
        event = envelope(command_value, event_type)
        if event_type is EventType.EFFECT_QUEUED:
            request = EffectRequest(event, f"outbox-{command_value.command_id}")
            return CommandDecision(DecisionOutcome.ACCEPTED, (), (request,), {"queued": True})
        return CommandDecision(DecisionOutcome.ACCEPTED, (event,), (), {"accepted": True})


def open_kernel(database: Path) -> tuple[SqliteEventStore, DurableKernel]:
    store = SqliteEventStore(database)
    store.init_schema()
    return store, DurableKernel(store, SPEC, TestDecider())


def test_command_hash_is_derived_from_every_semantic_identity_field() -> None:
    base = command("command-hash", "create", 0)
    variants = (
        replace(base, cycle_id="cycle-other"),
        replace(base, expected_version=1),
        replace(base, actor="other"),
        replace(base, authorization_context={"role": "other"}),
        replace(base, correlation_id="corr-other"),
        replace(base, causation_id="cause-other"),
        replace(base, command_type="OtherCommand"),
        replace(base, schema_version="2.0.0"),
        replace(base, input={"mode": "reject"}),
        replace(base, issued_at="2026-07-14T00:00:01Z"),
    )

    assert len(base.command_hash) == 64
    assert all(candidate.command_hash != base.command_hash for candidate in variants)
    assert variants[8].input_hash != base.input_hash


def test_command_boundary_maps_recursive_input_to_typed_schema_error() -> None:
    recursive: dict[str, object] = {}
    recursive["self"] = recursive

    with pytest.raises(CommandSchemaError, match="canonical JSON"):
        replace(command("command-recursive", "create", 0), input=recursive)


def test_illegal_first_effect_is_rejected_before_any_durable_row(tmp_path: Path) -> None:
    store, kernel = open_kernel(tmp_path / "illegal.sqlite3")
    candidate = command("command-illegal", "effect", 0)

    with pytest.raises(AggregateNotInitializedError):
        kernel.execute(candidate)

    assert store.load(candidate.cycle_id) == []
    assert store.load_command_receipt(candidate.command_id) is None
    assert store.load_outbox(candidate.cycle_id) == []
    store.close()


def test_restart_and_stale_retry_return_the_exact_prior_receipt(tmp_path: Path) -> None:
    database = tmp_path / "restart.sqlite3"
    store, kernel = open_kernel(database)
    create = command("command-create", "create", 0)
    first = kernel.execute(create)
    store.close()

    reopened, resumed = open_kernel(database)
    retried = resumed.execute(create)
    assert retried.deduplicated is True
    assert retried.receipt == first.receipt
    assert replay(reopened.load(create.cycle_id), SPEC).version == 1
    with pytest.raises(CommandIdConflict):
        resumed.execute(replace(create, actor="intruder"))
    reopened.close()


def test_rejection_receipt_survives_later_state_change(tmp_path: Path) -> None:
    store, kernel = open_kernel(tmp_path / "rejection.sqlite3")
    rejected = command("command-reject", "reject", 0)
    first = kernel.execute(rejected)
    assert first.new_version == 0
    assert first.receipt.event_ids == ()

    kernel.execute(command("command-create-after-reject", "create", 0))
    retried = kernel.execute(rejected)
    assert retried.deduplicated is True
    assert retried.receipt == first.receipt
    assert len(store.load(rejected.cycle_id)) == 1
    store.close()


def test_effect_request_derives_the_exact_executable_outbox_payload(tmp_path: Path) -> None:
    store, kernel = open_kernel(tmp_path / "effect.sqlite3")
    kernel.execute(command("command-create", "create", 0))
    kernel.execute(command("command-start", "start", 1))
    kernel.execute(command("command-effect", "effect", 2))

    queued = store.load("cycle-kernel")[-1]
    outbox = store.load_outbox("cycle-kernel")
    assert len(outbox) == 1
    assert outbox[0].payload == queued.payload
    with pytest.raises(DurableKernelError, match="EffectQueued"):
        CommandDecision(DecisionOutcome.ACCEPTED, (queued,), (), {})
    store.close()


def test_kernel_rejects_a_self_validating_but_prefix_divergent_snapshot(
    tmp_path: Path,
) -> None:
    store, kernel = open_kernel(tmp_path / "snapshot-prefix.sqlite3")
    kernel.execute(command("command-create", "create", 0))
    state = replay(store.load("cycle-kernel"), SPEC)
    fabricated = replace(state, config_snapshot_hash="d" * 64)
    blob = encode_state(fabricated)
    store.save_snapshot(
        Snapshot(
            stream_id=fabricated.cycle_id,
            stream_version=fabricated.version,
            fsm_spec_hash=fabricated.fsm_spec_hash,
            codec_version=STATE_CODEC_VERSION,
            state_hash=state_hash(fabricated),
            state_blob=blob,
            created_at=NOW,
        )
    )

    with pytest.raises(StoreCorruption, match="event-prefix replay"):
        kernel.load_snapshot("cycle-kernel")
    store.close()


def test_kernel_creates_and_reloads_only_replayed_snapshot_bytes(tmp_path: Path) -> None:
    database = tmp_path / "snapshot-valid.sqlite3"
    store, kernel = open_kernel(database)
    kernel.execute(command("command-create", "create", 0))
    snapshot = kernel.create_snapshot("cycle-kernel", created_at=NOW)
    store.close()

    reopened, resumed = open_kernel(database)
    assert resumed.load_snapshot("cycle-kernel") == snapshot
    reopened.close()


def test_concurrent_kernel_commands_leave_one_clean_cas_conflict(tmp_path: Path) -> None:
    database = tmp_path / "kernel-race.sqlite3"
    barrier = Barrier(2)

    class BarrierDecider(TestDecider):
        def decide(self, state, command_value: CanonicalCommandEnvelope) -> CommandDecision:
            barrier.wait()
            return super().decide(state, command_value)

    stores = [SqliteEventStore(database), SqliteEventStore(database)]
    for store in stores:
        store.init_schema()
    kernels = [DurableKernel(store, SPEC, BarrierDecider()) for store in stores]
    commands = [command(f"command-race-{index}", "create", 0) for index in range(2)]

    def execute(index: int) -> AppendResult | StoreConflict:
        try:
            return kernels[index].execute(commands[index])
        except StoreConflict as exc:
            return exc

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(execute, range(2)))

    assert sum(isinstance(outcome, AppendResult) for outcome in outcomes) == 1
    assert sum(isinstance(outcome, StoreConflict) for outcome in outcomes) == 1
    assert len(stores[0].load("cycle-kernel")) == 1
    for store in stores:
        store.close()


def test_identical_command_race_rechecks_receipt_after_preflight_version_drift(
    tmp_path: Path,
) -> None:
    database = tmp_path / "same-command-race.sqlite3"
    winner_store = SqliteEventStore(database)
    loser_delegate = SqliteEventStore(database)
    winner_store.init_schema()
    loser_delegate.init_schema()
    first_lookup_done = ThreadEvent()
    winner_done = ThreadEvent()

    class PausingStore(EventStore):
        def __init__(self, delegate: EventStore) -> None:
            self._delegate = delegate
            self._first_lookup = True

        def init_schema(self) -> None:
            self._delegate.init_schema()

        def load(self, stream_id: str, after_version: int = 0):
            return self._delegate.load(stream_id, after_version)

        def append(self, stream_id, expected_version, events, outbox_records, receipt):
            return self._delegate.append(
                stream_id, expected_version, events, outbox_records, receipt
            )

        def load_command_receipt(self, command_id: str):
            result = self._delegate.load_command_receipt(command_id)
            if self._first_lookup:
                self._first_lookup = False
                first_lookup_done.set()
                assert winner_done.wait(timeout=5)
            return result

        def load_outbox(self, stream_id: str):
            return self._delegate.load_outbox(stream_id)

        def load_snapshot(self, stream_id: str):
            return self._delegate.load_snapshot(stream_id)

        def save_snapshot(self, snapshot: Snapshot) -> None:
            self._delegate.save_snapshot(snapshot)

        def close(self) -> None:
            self._delegate.close()

    candidate = command("command-same-race", "create", 0)
    winner = DurableKernel(winner_store, SPEC, TestDecider())
    loser = DurableKernel(PausingStore(loser_delegate), SPEC, TestDecider())

    with ThreadPoolExecutor(max_workers=1) as pool:
        losing_call = pool.submit(loser.execute, candidate)
        assert first_lookup_done.wait(timeout=5)
        first = winner.execute(candidate)
        winner_done.set()
        retried = losing_call.result(timeout=5)

    assert retried.deduplicated is True
    assert retried.receipt == first.receipt
    assert len(winner_store.load(candidate.cycle_id)) == 1
    winner_store.close()
    loser_delegate.close()
