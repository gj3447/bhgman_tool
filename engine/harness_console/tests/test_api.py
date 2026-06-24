from __future__ import annotations

from fastapi.testclient import TestClient

from engine.harness_console.api import create_app
from engine.harness_console.store import SqliteEventStore


def _client() -> TestClient:
    store = SqliteEventStore()
    return TestClient(create_app(store))


def test_health():
    client = _client()

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_event_roundtrip_over_http():
    client = _client()
    payload = {
        "id": "evt-1",
        "run_id": "run-1",
        "sequence": 1,
        "event_type": "run.started",
        "source": "api-test",
        "payload": {"ok": True},
    }

    created = client.post("/events", json=payload)
    listed = client.get("/events/run-1")

    assert created.status_code == 200
    assert listed.status_code == 200
    assert [event["id"] for event in listed.json()] == ["evt-1"]
    assert listed.json()[0]["payload"] == {"ok": True}


def test_verdict_request_and_submit_over_http():
    client = _client()
    request = {
        "id": "vr-1",
        "target_ref": "ref-1",
        "target_kind": "longinus_ambiguous",
        "allowed_verdicts": ["VERIFY", "REJECT"],
    }
    verdict = {
        "id": "hv-1",
        "request_id": "vr-1",
        "verdict": "VERIFY",
        "rationale": "needs human confirmation",
        "reviewer_id": "tester",
    }

    assert client.post("/verdict-requests", json=request).status_code == 200
    assert client.post("/verdicts", json=verdict).status_code == 200
    submitted = client.get("/verdict-requests", params={"status": "SUBMITTED"})

    assert submitted.status_code == 200
    assert [item["id"] for item in submitted.json()] == ["vr-1"]


def test_label_task_filters_over_http():
    client = _client()
    task = {
        "id": "lt-1",
        "project_id": "project-1",
        "target_ref": "engine/foo.py",
        "target_kind": "architecture_node",
        "allowed_labels": ["ENGINE", "ADAPTER"],
        "proposed_label": "ENGINE",
    }

    assert client.post("/label-tasks", json=task).status_code == 200
    listed = client.get("/label-tasks", params={"project_id": "project-1"})

    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == ["lt-1"]
