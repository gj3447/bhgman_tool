"""Process-kill falsifiers for Postgres event/outbox commit atomicity.

# KG: apt-tpa-legion-engine-canon-2026-06-12
# Design: SYMPOSIUM/THEORY/APT/vnext/APT_ENGINE_FSM_DESIGN_2026-07-13.md Slice 1
"""

from __future__ import annotations

import os
import subprocess
import sys

import pytest

from engine.apt_runtime.adapters.postgres_store import PostgresEventStore
from engine.apt_runtime.domain.commands import CanonicalCommandEnvelope
from engine.apt_runtime.domain.events import EventEnvelope, EventType, GuardResult
from engine.apt_runtime.domain.fsm_spec import load_default_spec
from engine.apt_runtime.domain.reducer import replay
from engine.apt_runtime.ports.event_store import CommandReceiptDraft


NOW = "2026-07-14T00:00:00Z"
SPEC = load_default_spec()


def _command(command_id: str, expected_version: int, *, phase: str = "setup"):
    return CanonicalCommandEnvelope(
        command_id=command_id,
        command_type="PostgresCrashBoundaryCommand",
        schema_version="1.0.0",
        cycle_id="cycle-pg-crash",
        expected_version=expected_version,
        actor="crash-test",
        authorization_context={"role": "test"},
        correlation_id="corr-pg-crash",
        causation_id=f"cause-{command_id}",
        input={"phase": phase},
        issued_at=NOW,
    )


def _setup_replayable_prefix(dsn: str) -> None:
    command = _command("command-pg-setup", 0)
    created = EventEnvelope.create(
        event_id="event-pg-created",
        stream_id=command.cycle_id,
        stream_version=1,
        event_type=EventType.CYCLE_CREATED,
        schema_version="1.0.0",
        fsm_spec_hash=SPEC.spec_hash,
        cycle_id=command.cycle_id,
        actor=command.actor,
        correlation_id=command.correlation_id,
        causation_id=command.causation_id,
        command_id=command.command_id,
        config_version="config-v1",
        payload={
            "config_snapshot_ref": "config://v1",
            "config_snapshot_hash": "a" * 64,
            "canon_snapshot_ref": "kg://snapshot/1",
            "canon_snapshot_hash": "b" * 64,
        },
        created_at=NOW,
    )
    started = EventEnvelope.create(
        event_id="event-pg-started",
        stream_id=command.cycle_id,
        stream_version=2,
        event_type=EventType.CYCLE_STARTED,
        schema_version="1.0.0",
        fsm_spec_hash=SPEC.spec_hash,
        cycle_id=command.cycle_id,
        actor=command.actor,
        correlation_id=command.correlation_id,
        causation_id=command.causation_id,
        command_id=command.command_id,
        config_version="config-v1",
        payload={
            "guard_result": GuardResult.PASS.value,
            "guard_evidence_refs": ["evidence-pg-crash"],
        },
        created_at=NOW,
    )
    draft = CommandReceiptDraft.create(
        command=command,
        response={"accepted": True},
        created_at=NOW,
    )
    store = PostgresEventStore(dsn)
    store.init_schema()
    store.append(command.cycle_id, 0, [created, started], [], draft)
    store.close()


CRASH_SCRIPT = r"""
import os

from engine.apt_runtime.adapters.postgres_store import PostgresEventStore
from engine.apt_runtime.domain.commands import CanonicalCommandEnvelope
from engine.apt_runtime.domain.events import EventEnvelope, EventType
from engine.apt_runtime.domain.fsm_spec import load_default_spec
from engine.apt_runtime.ports.event_store import CommandReceiptDraft, OutboxRecord

dsn = os.environ["APT_CRASH_TEST_DSN"]
phase = os.environ["APT_CRASH_TEST_PHASE"]
now = "2026-07-14T00:00:00Z"
spec = load_default_spec()
command = CanonicalCommandEnvelope(
    command_id="command-pg-effect",
    command_type="PostgresCrashBoundaryCommand",
    schema_version="1.0.0",
    cycle_id="cycle-pg-crash",
    expected_version=2,
    actor="crash-test",
    authorization_context={"role": "test"},
    correlation_id="corr-pg-crash",
    causation_id="cause-command-pg-effect",
    input={"phase": phase},
    issued_at=now,
)
payload = {
    "capability": "artifact.realize",
    "provider": "fake-hades",
    "risk_class": "LOCAL_REVERSIBLE",
    "idempotency_key": "idem-pg-crash",
    "input_ref": "artifact://input/crash",
    "input_hash": "c" * 64,
}
event = EventEnvelope.create(
    event_id="event-pg-effect",
    stream_id=command.cycle_id,
    stream_version=3,
    event_type=EventType.EFFECT_QUEUED,
    schema_version="1.0.0",
    fsm_spec_hash=spec.spec_hash,
    cycle_id=command.cycle_id,
    effect_id="effect-pg-crash",
    actor=command.actor,
    correlation_id=command.correlation_id,
    causation_id=command.causation_id,
    command_id=command.command_id,
    config_version="config-v1",
    payload=payload,
    created_at=now,
)
outbox = OutboxRecord.create(
    outbox_id="outbox-pg-crash",
    stream_id=command.cycle_id,
    effect_id="effect-pg-crash",
    command_id=command.command_id,
    payload=payload,
    created_at=now,
)
receipt = CommandReceiptDraft.create(
    command=command,
    response={"accepted": True},
    created_at=now,
)

def crash(name):
    if name == phase:
        os._exit(93 if phase == "before_commit" else 94)

store = PostgresEventStore(dsn, failpoint=crash)
store.init_schema()
store.append(command.cycle_id, 2, [event], [outbox], receipt)
raise AssertionError("configured crash boundary was not reached")
"""


@pytest.mark.parametrize(
    ("phase", "returncode", "expected_version"),
    [("before_commit", 93, 2), ("after_commit", 94, 3)],
)
def test_postgres_process_kill_at_commit_is_all_or_none_and_retry_converges(
    postgres_sandbox,
    phase: str,
    returncode: int,
    expected_version: int,
) -> None:
    _setup_replayable_prefix(postgres_sandbox.dsn)
    environment = os.environ.copy()
    environment["APT_CRASH_TEST_DSN"] = postgres_sandbox.dsn
    environment["APT_CRASH_TEST_PHASE"] = phase

    completed = subprocess.run(
        [sys.executable, "-c", CRASH_SCRIPT],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )
    assert completed.returncode == returncode, completed.stderr

    reopened = PostgresEventStore(postgres_sandbox.dsn)
    reopened.init_schema()
    events = reopened.load("cycle-pg-crash")
    assert replay(events, SPEC).version == expected_version
    queued = reopened.load_outbox("cycle-pg-crash")
    stored_receipt = reopened.load_command_receipt("command-pg-effect")
    if phase == "before_commit":
        assert stored_receipt is None
        assert queued == []
    else:
        assert stored_receipt is not None
        assert [item.outbox_id for item in queued] == ["outbox-pg-crash"]
        command = _command("command-pg-effect", 2, phase=phase)
        draft = CommandReceiptDraft.create(
            command=command,
            response={"accepted": True},
            created_at=NOW,
        )
        retried = reopened.append("cycle-pg-crash", 2, [], [], draft)
        assert retried.deduplicated is True
        assert len(reopened.load("cycle-pg-crash")) == 3
        assert len(reopened.load_outbox("cycle-pg-crash")) == 1
    reopened.close()
