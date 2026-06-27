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


def test_project_architecture_and_label_tasks_over_http(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n")
    engine_dir = tmp_path / "engine"
    engine_dir.mkdir()
    (engine_dir / "__init__.py").write_text("")
    (engine_dir / "foo_adapter.py").write_text("")
    client = _client()
    target = {"id": "project-1", "root_path": str(tmp_path), "kind": "python_repo"}

    graph = client.post("/projects/architecture", json=target)
    tasks = client.post("/projects/label-tasks", json=target)
    events = client.get("/events/project-1")

    assert graph.status_code == 200
    assert any(node["path"] == "engine/foo_adapter.py" for node in graph.json()["nodes"])
    assert tasks.status_code == 200
    assert any(task["proposed_label"] == "ADAPTER" for task in tasks.json())
    assert [event["event_type"] for event in events.json()][:2] == [
        "project.ingested",
        "architecture.analyzed",
    ]
