"""Process-kill falsifiers around the SQLite append commit boundary.

# KG: apt-tpa-legion-engine-canon-2026-06-12
# KG: APT_SCW_TDAD_canonical
"""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys

import pytest

from engine.apt_runtime.adapters.sqlite_store import SqliteEventStore
from engine.apt_runtime.domain.commands import CanonicalCommandEnvelope
from engine.apt_runtime.domain.events import EventEnvelope, EventType, GuardResult
from engine.apt_runtime.domain.fsm_spec import load_default_spec
from engine.apt_runtime.domain.reducer import replay
from engine.apt_runtime.ports.event_store import CommandReceiptDraft


NOW = "2026-07-14T00:00:00Z"
SPEC = load_default_spec()


def _command(command_id: str, expected_version: int) -> CanonicalCommandEnvelope:
    return CanonicalCommandEnvelope(
        command_id=command_id,
        command_type="CrashBoundaryCommand",
        schema_version="1.0.0",
        cycle_id="cycle-crash",
        expected_version=expected_version,
        actor="crash-test",
        authorization_context={"role": "test"},
        correlation_id="corr-crash",
        causation_id=f"cause-{command_id}",
        input={"phase": "setup"},
        issued_at=NOW,
    )


def _setup_replayable_prefix(database: Path) -> None:
    command = _command("command-setup", 0)
    created = EventEnvelope.create(
        event_id="event-created",
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
        event_id="event-started",
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
            "guard_evidence_refs": ["evidence-crash"],
        },
        created_at=NOW,
    )
    receipt = CommandReceiptDraft.create(
        command=command,
        response={"accepted": True},
        created_at=NOW,
    )
    store = SqliteEventStore(database)
    store.init_schema()
    store.append(command.cycle_id, 0, [created, started], [], receipt)
    store.close()


CRASH_SCRIPT = r"""
import os
import sys

from engine.apt_runtime.adapters.sqlite_store import SqliteEventStore
from engine.apt_runtime.domain.commands import CanonicalCommandEnvelope
from engine.apt_runtime.domain.events import EventEnvelope, EventType
from engine.apt_runtime.domain.fsm_spec import load_default_spec
from engine.apt_runtime.ports.event_store import CommandReceiptDraft, OutboxRecord

database, phase = sys.argv[1:]
now = "2026-07-14T00:00:00Z"
spec = load_default_spec()
command = CanonicalCommandEnvelope(
    command_id="command-effect",
    command_type="CrashBoundaryCommand",
    schema_version="1.0.0",
    cycle_id="cycle-crash",
    expected_version=2,
    actor="crash-test",
    authorization_context={"role": "test"},
    correlation_id="corr-crash",
    causation_id="cause-command-effect",
    input={"phase": phase},
    issued_at=now,
)
payload = {
    "capability": "artifact.realize",
    "provider": "fake-hades",
    "risk_class": "LOCAL_REVERSIBLE",
    "idempotency_key": "idem-crash",
    "input_ref": "artifact://input/crash",
    "input_hash": "c" * 64,
}
event = EventEnvelope.create(
    event_id="event-effect",
    stream_id=command.cycle_id,
    stream_version=3,
    event_type=EventType.EFFECT_QUEUED,
    schema_version="1.0.0",
    fsm_spec_hash=spec.spec_hash,
    cycle_id=command.cycle_id,
    effect_id="effect-crash",
    actor=command.actor,
    correlation_id=command.correlation_id,
    causation_id=command.causation_id,
    command_id=command.command_id,
    config_version="config-v1",
    payload=payload,
    created_at=now,
)
outbox = OutboxRecord.create(
    outbox_id="outbox-crash",
    stream_id=command.cycle_id,
    effect_id="effect-crash",
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
        os._exit(91 if phase == "before_commit" else 92)

store = SqliteEventStore(database, failpoint=crash)
store.init_schema()
store.append(command.cycle_id, 2, [event], [outbox], receipt)
raise AssertionError("configured crash boundary was not reached")
"""


@pytest.mark.parametrize(
    ("phase", "returncode", "expected_version"),
    [("before_commit", 91, 2), ("after_commit", 92, 3)],
)
def test_process_kill_at_append_commit_boundary_is_all_or_none_and_replayable(
    tmp_path: Path,
    phase: str,
    returncode: int,
    expected_version: int,
) -> None:
    database = tmp_path / f"crash-{phase}.sqlite3"
    _setup_replayable_prefix(database)

    completed = subprocess.run(
        [sys.executable, "-c", CRASH_SCRIPT, str(database), phase],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == returncode, completed.stderr

    reopened = SqliteEventStore(database)
    reopened.init_schema()
    events = reopened.load("cycle-crash")
    assert replay(events, SPEC).version == expected_version
    outbox = reopened.load_outbox("cycle-crash")
    receipt = reopened.load_command_receipt("command-effect")
    if phase == "before_commit":
        assert receipt is None
        assert outbox == []
    else:
        assert receipt is not None
        assert [item.outbox_id for item in outbox] == ["outbox-crash"]
        retry_command = replace_input_phase(_command("command-effect", 2), phase)
        draft = CommandReceiptDraft.create(
            command=retry_command,
            response={"accepted": True},
            created_at=NOW,
        )
        retried = reopened.append("cycle-crash", 2, [], [], draft)
        assert retried.deduplicated is True
        assert len(reopened.load("cycle-crash")) == 3
        assert len(reopened.load_outbox("cycle-crash")) == 1
    reopened.close()


def replace_input_phase(command: CanonicalCommandEnvelope, phase: str) -> CanonicalCommandEnvelope:
    return CanonicalCommandEnvelope(
        command_id=command.command_id,
        command_type=command.command_type,
        schema_version=command.schema_version,
        cycle_id=command.cycle_id,
        expected_version=command.expected_version,
        actor=command.actor,
        authorization_context=command.authorization_context,
        correlation_id=command.correlation_id,
        causation_id=command.causation_id,
        input={"phase": phase},
        issued_at=command.issued_at,
    )
