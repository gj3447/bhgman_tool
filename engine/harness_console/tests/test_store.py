from __future__ import annotations

import os

import pytest

from engine.harness_console.models import (
    HarnessEvent,
    HumanVerdict,
    HumanVerdictRequest,
    LabelTask,
    LabelTaskStatus,
    RequestStatus,
    TargetKind,
    VerdictValue,
)
from engine.harness_console.store import PostgresEventStore, SqliteEventStore, StoreConflict


def _sqlite_store() -> SqliteEventStore:
    store = SqliteEventStore()
    store.init_schema()
    return store


def test_append_and_list_events_in_sequence_order():
    store = _sqlite_store()
    store.append_event(
        HarnessEvent(
            id="evt-2",
            run_id="run-1",
            sequence=2,
            event_type="verdict.requested",
            source="test",
            payload={"target": "b"},
        )
    )
    store.append_event(
        HarnessEvent(
            id="evt-1",
            run_id="run-1",
            sequence=1,
            event_type="run.started",
            source="test",
            payload={"target": "a"},
        )
    )

    events = store.list_events("run-1")

    assert [event.id for event in events] == ["evt-1", "evt-2"]
    assert events[0].payload == {"target": "a"}


def test_duplicate_event_sequence_is_rejected():
    store = _sqlite_store()
    store.append_event(
        HarnessEvent(
            id="evt-1",
            run_id="run-1",
            sequence=1,
            event_type="run.started",
            source="test",
        )
    )

    with pytest.raises(StoreConflict):
        store.append_event(
            HarnessEvent(
                id="evt-2",
                run_id="run-1",
                sequence=1,
                event_type="run.duplicate",
                source="test",
            )
        )


def test_verdict_request_submit_updates_lifecycle():
    store = _sqlite_store()
    request = HumanVerdictRequest(
        id="vr-1",
        target_ref="ref-1",
        target_kind=TargetKind.LONGINUS_AMBIGUOUS,
        context={"path": "engine/x.py"},
        evidence_refs=["evidence-1"],
        allowed_verdicts=[VerdictValue.VERIFY, VerdictValue.REJECT],
    )
    store.create_verdict_request(request)

    pending = store.list_verdict_requests(RequestStatus.PENDING)
    assert [item.id for item in pending] == ["vr-1"]

    store.submit_human_verdict(
        HumanVerdict(
            id="hv-1",
            request_id="vr-1",
            verdict=VerdictValue.VERIFY,
            rationale="ambiguous binding needs review",
            reviewer_id="tester",
            evidence_refs=["evidence-1"],
        )
    )

    assert store.list_verdict_requests(RequestStatus.PENDING) == []
    submitted = store.list_verdict_requests(RequestStatus.SUBMITTED)
    assert [item.id for item in submitted] == ["vr-1"]


def test_disallowed_verdict_is_rejected():
    store = _sqlite_store()
    store.create_verdict_request(
        HumanVerdictRequest(
            id="vr-1",
            target_ref="ref-1",
            target_kind=TargetKind.FIX_ATTEMPT,
            allowed_verdicts=[VerdictValue.REJECT],
        )
    )

    with pytest.raises(StoreConflict):
        store.submit_human_verdict(
            HumanVerdict(
                id="hv-1",
                request_id="vr-1",
                verdict=VerdictValue.APPROVE,
                rationale="not allowed",
                reviewer_id="tester",
            )
        )


def test_label_task_status_update_and_filters():
    store = _sqlite_store()
    store.create_label_task(
        LabelTask(
            id="lt-1",
            project_id="project-1",
            target_ref="engine/foo.py",
            target_kind="architecture_node",
            proposed_label="ENGINE",
            allowed_labels=["ENGINE", "ADAPTER"],
            ai_confidence=0.75,
        )
    )
    store.create_label_task(
        LabelTask(
            id="lt-2",
            project_id="project-2",
            target_ref="asset.glb",
            target_kind="project_asset",
            allowed_labels=["ASSET", "SCENE"],
        )
    )

    updated = store.update_label_task_status("lt-1", LabelTaskStatus.HUMAN_APPROVED)

    assert updated.status is LabelTaskStatus.HUMAN_APPROVED
    assert [task.id for task in store.list_label_tasks(project_id="project-1")] == ["lt-1"]
    assert [
        task.id for task in store.list_label_tasks(status=LabelTaskStatus.HUMAN_APPROVED)
    ] == ["lt-1"]


def test_postgres_store_import_is_lazy():
    dsn = os.environ.get("HARNESS_CONSOLE_DATABASE_URL")
    if not dsn or not dsn.startswith("postgresql://"):
        pytest.skip("HARNESS_CONSOLE_DATABASE_URL with postgresql:// is not configured")

    store = PostgresEventStore(dsn)
    store.init_schema()
