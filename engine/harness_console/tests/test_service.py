from __future__ import annotations

from engine.harness_console.models import (
    HumanVerdict,
    HumanVerdictRequest,
    ProjectKind,
    ProjectTarget,
    TargetKind,
    VerdictValue,
)
from engine.harness_console.service import HarnessConsoleEngine
from engine.harness_console.store import SqliteEventStore


def _engine() -> HarnessConsoleEngine:
    store = SqliteEventStore()
    store.init_schema()
    return HarnessConsoleEngine(store)


def test_engine_ingests_analyzes_and_creates_label_tasks(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n")
    engine_dir = tmp_path / "engine"
    engine_dir.mkdir()
    (engine_dir / "__init__.py").write_text("")
    (engine_dir / "commander_engine.py").write_text("class CommanderEngine: ...\n")

    engine = _engine()
    target = ProjectTarget(id="project-1", root_path=str(tmp_path), kind=ProjectKind.PYTHON_REPO)

    snapshot = engine.ingest_project(target)
    graph = engine.analyze_architecture(snapshot)
    tasks = engine.create_label_tasks(snapshot)

    assert snapshot.summary == {"python_files": 2}
    assert any(node.path == "engine/commander_engine.py" for node in graph.nodes)
    assert any(task.target_ref == "engine/commander_engine.py" for task in tasks)
    assert [event.event_type for event in engine.stream_run("project-1")] == [
        "project.ingested",
        "architecture.analyzed",
        "architecture.analyzed",
        "label_task.created",
        "label_task.created",
        "label_tasks.created",
    ]


def test_create_label_tasks_is_idempotent_for_same_snapshot(tmp_path):
    (tmp_path / "README.md").write_text("# Docs\n")
    engine = _engine()
    target = ProjectTarget(id="docs", root_path=str(tmp_path))
    snapshot = engine.ingest_project(target)

    first = engine.create_label_tasks(snapshot)
    second = engine.create_label_tasks(snapshot)

    assert [task.id for task in first] == [task.id for task in second]
    assert len(engine.store.list_label_tasks(project_id="docs")) == 1


def test_verdict_request_and_submission_emit_audit_events():
    engine = _engine()
    request = HumanVerdictRequest(
        id="vr-1",
        target_ref="engine/foo.py",
        target_kind=TargetKind.ARCHITECTURE_NODE,
        allowed_verdicts=[VerdictValue.APPROVE, VerdictValue.REJECT],
    )

    engine.create_verdict_request(request)
    engine.submit_verdict(
        HumanVerdict(
            id="hv-1",
            request_id="vr-1",
            verdict=VerdictValue.APPROVE,
            rationale="role is correct",
            reviewer_id="tester",
        )
    )

    assert [event.event_type for event in engine.stream_run("vr-1")] == [
        "verdict.requested",
        "verdict.submitted",
    ]
