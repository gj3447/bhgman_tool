"""Harness Console domain service.

The service is the stable facade for CLI, MCP, and HTTP adapters. It coordinates
project adapters with the event store, but it does not know about FastAPI,
terminal formatting, or KG write-back.

# KG: task-harness-console-engine-facade-2026-06-26
# KG: plan-harness-console-live-verdict-2026-06-24
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from typing import Any

from engine.harness_console.adapters import ProjectAdapter, select_adapter
from engine.harness_console.models import (
    ArchitectureGraph,
    ArchitectureRole,
    HarnessEvent,
    HumanVerdict,
    HumanVerdictRequest,
    LabelTask,
    ProjectSnapshot,
    ProjectTarget,
    TargetKind,
    VerdictValue,
)
from engine.harness_console.store import EventStore, StoreConflict


DEFAULT_ARCHITECTURE_LABELS = [
    role.value for role in ArchitectureRole if role is not ArchitectureRole.UNKNOWN
]


class HarnessConsoleEngine:
    """Application facade for the Harness Console control room."""

    def __init__(
        self,
        store: EventStore,
        adapters: list[ProjectAdapter] | None = None,
        source: str = "harness-console-engine",
    ) -> None:
        self.store = store
        self.adapters = adapters
        self.source = source

    def ingest_project(self, target: ProjectTarget) -> ProjectSnapshot:
        adapter = select_adapter(target, self.adapters)
        snapshot = adapter.snapshot(target)
        self._append_event(
            run_id=target.id,
            event_type="project.ingested",
            payload={
                "target_id": target.id,
                "root_path": snapshot.root_path,
                "adapter": snapshot.adapter,
                "summary": snapshot.summary,
            },
        )
        return snapshot

    def analyze_architecture(self, snapshot: ProjectSnapshot) -> ArchitectureGraph:
        adapter = self._adapter_by_name(snapshot.adapter)
        graph = adapter.architecture(snapshot)
        self._append_event(
            run_id=snapshot.target_id,
            event_type="architecture.analyzed",
            payload={
                "snapshot_id": snapshot.id,
                "adapter": snapshot.adapter,
                "nodes": len(graph.nodes),
                "edges": len(graph.edges),
                "warnings": graph.warnings,
            },
        )
        return graph

    def create_label_tasks(self, snapshot: ProjectSnapshot) -> list[LabelTask]:
        graph = self.analyze_architecture(snapshot)
        tasks: list[LabelTask] = []
        for node in graph.nodes:
            task = LabelTask(
                id=_stable_id("label-task", graph.project_id, node.id),
                project_id=graph.project_id,
                target_ref=node.path,
                target_kind=TargetKind.ARCHITECTURE_NODE.value,
                proposed_label=None if node.role is ArchitectureRole.UNKNOWN else node.role.value,
                allowed_labels=DEFAULT_ARCHITECTURE_LABELS,
                ai_confidence=None if node.role is ArchitectureRole.UNKNOWN else 0.65,
                evidence_refs=[node.path],
                missing_evidence=[]
                if node.role is not ArchitectureRole.UNKNOWN
                else ["role_signal"],
                blocking_questions=[]
                if node.role is not ArchitectureRole.UNKNOWN
                else ["What architectural role should this node play?"],
            )
            tasks.append(self._create_label_task_idempotent(task))
        self._append_event(
            run_id=snapshot.target_id,
            event_type="label_tasks.created",
            payload={"snapshot_id": snapshot.id, "count": len(tasks)},
        )
        return tasks

    def create_verdict_request(self, request: HumanVerdictRequest) -> HumanVerdictRequest:
        created = self.store.create_verdict_request(request)
        self._append_event(
            run_id=request.id,
            event_type="verdict.requested",
            payload={
                "request_id": request.id,
                "target_ref": request.target_ref,
                "target_kind": request.target_kind.value,
                "allowed_verdicts": [value.value for value in request.allowed_verdicts],
            },
        )
        return created

    def submit_verdict(self, verdict: HumanVerdict) -> HumanVerdict:
        submitted = self.store.submit_human_verdict(verdict)
        self._append_event(
            run_id=verdict.request_id,
            event_type="verdict.submitted",
            payload={
                "verdict_id": verdict.id,
                "request_id": verdict.request_id,
                "verdict": verdict.verdict.value,
                "reviewer_id": verdict.reviewer_id,
            },
        )
        return submitted

    def request_human_verdict_for_node(
        self,
        graph: ArchitectureGraph,
        node_id: str,
        allowed_verdicts: list[VerdictValue] | None = None,
        recommended_action: str | None = None,
    ) -> HumanVerdictRequest:
        node = next((candidate for candidate in graph.nodes if candidate.id == node_id), None)
        if node is None:
            raise ValueError(f"architecture node not found: {node_id}")
        request = HumanVerdictRequest(
            id=_stable_id("verdict-request", graph.project_id, node.id),
            target_ref=node.path,
            target_kind=TargetKind.ARCHITECTURE_NODE,
            context={
                "project_id": graph.project_id,
                "adapter": graph.adapter,
                "node": node.model_dump(mode="json"),
            },
            evidence_refs=[node.path],
            recommended_action=recommended_action,
            allowed_verdicts=allowed_verdicts or [VerdictValue.APPROVE, VerdictValue.REJECT],
        )
        try:
            return self.create_verdict_request(request)
        except StoreConflict:
            existing = [
                item for item in self.store.list_verdict_requests() if item.id == request.id
            ]
            if existing:
                return existing[0]
            raise

    def stream_run(self, run_id: str) -> Iterator[HarnessEvent]:
        yield from self.store.list_events(run_id)

    def _adapter_by_name(self, name: str) -> ProjectAdapter:
        candidates = self.adapters or _default_adapters()
        for adapter in candidates:
            if adapter.name == name:
                return adapter
        raise ValueError(f"project adapter not found: {name}")

    def _append_event(self, run_id: str, event_type: str, payload: dict[str, Any]) -> HarnessEvent:
        for _attempt in range(3):
            sequence = _next_sequence(self.store.list_events(run_id))
            event = HarnessEvent(
                id=_stable_id("event", run_id, str(sequence), event_type),
                run_id=run_id,
                sequence=sequence,
                event_type=event_type,
                source=self.source,
                payload=payload,
            )
            try:
                return self.store.append_event(event)
            except StoreConflict:
                continue
        raise StoreConflict(f"could not append event after sequence retries: {run_id}")

    def _create_label_task_idempotent(self, task: LabelTask) -> LabelTask:
        try:
            created = self.store.create_label_task(task)
        except StoreConflict:
            existing = [
                item
                for item in self.store.list_label_tasks(project_id=task.project_id)
                if item.id == task.id
            ]
            if not existing:
                raise
            return existing[0]
        self._append_event(
            run_id=task.project_id,
            event_type="label_task.created",
            payload={
                "task_id": created.id,
                "target_ref": created.target_ref,
                "proposed_label": created.proposed_label,
                "status": created.status.value,
            },
        )
        return created


def _default_adapters() -> list[ProjectAdapter]:
    from engine.harness_console.adapters import (  # noqa: PLC0415
        BeadProjectAdapter,
        GenericFileAdapter,
        NodeViteAdapter,
        PythonRepoAdapter,
        ThreeDProjectAdapter,
    )

    return [
        PythonRepoAdapter(),
        NodeViteAdapter(),
        ThreeDProjectAdapter(),
        BeadProjectAdapter(),
        GenericFileAdapter(),
    ]


def _next_sequence(events: list[HarnessEvent]) -> int:
    if not events:
        return 0
    return max(event.sequence for event in events) + 1


def _stable_id(*parts: str) -> str:
    raw = "\x1f".join(parts)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"{parts[0]}-{digest}"


__all__ = ["DEFAULT_ARCHITECTURE_LABELS", "HarnessConsoleEngine"]
