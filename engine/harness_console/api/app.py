"""Harness Console FastAPI composition root.

Routes stay thin: they translate HTTP to the EventStore port and return domain
DTOs. Policy belongs in domain services, not in FastAPI.

# KG: task-harness-console-live-gui-2026-06-24
# KG: plan-harness-console-live-verdict-2026-06-24
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from engine.harness_console.models import (
    HarnessEvent,
    HumanVerdict,
    HumanVerdictRequest,
    LabelTask,
    LabelTaskStatus,
    RequestStatus,
)
from engine.harness_console.store import (
    EventStore,
    PostgresEventStore,
    SqliteEventStore,
    StoreConflict,
    StoreNotFound,
)


def create_app(store: EventStore | None = None) -> FastAPI:
    app = FastAPI(title="Harness Console", version="0.1.0")
    app.state.store = store or build_store_from_env()
    app.state.store.init_schema()

    def get_store(request: Request) -> EventStore:
        return request.app.state.store

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/events", response_model=HarnessEvent)
    def append_event(event: HarnessEvent, event_store: EventStore = Depends(get_store)):
        try:
            return event_store.append_event(event)
        except StoreConflict as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/events/{run_id}", response_model=list[HarnessEvent])
    def list_events(run_id: str, event_store: EventStore = Depends(get_store)):
        return event_store.list_events(run_id)

    @app.get("/runs/{run_id}/stream")
    async def stream_run(run_id: str, event_store: EventStore = Depends(get_store)):
        return StreamingResponse(
            _event_stream(run_id, event_store),
            media_type="text/event-stream",
        )

    @app.post("/verdict-requests", response_model=HumanVerdictRequest)
    def create_verdict_request(
        request: HumanVerdictRequest, event_store: EventStore = Depends(get_store)
    ):
        try:
            return event_store.create_verdict_request(request)
        except StoreConflict as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/verdict-requests", response_model=list[HumanVerdictRequest])
    def list_verdict_requests(
        status: RequestStatus | None = None,
        event_store: EventStore = Depends(get_store),
    ):
        return event_store.list_verdict_requests(status)

    @app.post("/verdicts", response_model=HumanVerdict)
    def submit_verdict(verdict: HumanVerdict, event_store: EventStore = Depends(get_store)):
        try:
            return event_store.submit_human_verdict(verdict)
        except StoreNotFound as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except StoreConflict as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/label-tasks", response_model=LabelTask)
    def create_label_task(task: LabelTask, event_store: EventStore = Depends(get_store)):
        try:
            return event_store.create_label_task(task)
        except StoreConflict as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/label-tasks", response_model=list[LabelTask])
    def list_label_tasks(
        project_id: str | None = None,
        status: LabelTaskStatus | None = Query(default=None),
        event_store: EventStore = Depends(get_store),
    ):
        return event_store.list_label_tasks(project_id=project_id, status=status)

    return app


def build_store_from_env() -> EventStore:
    dsn = os.environ.get("HARNESS_CONSOLE_DATABASE_URL")
    if dsn is None or dsn == "":
        if os.environ.get("HARNESS_CONSOLE_DEV_SQLITE", "").lower() == "true":
            return SqliteEventStore()
        raise RuntimeError(
            "HARNESS_CONSOLE_DATABASE_URL is required unless "
            "HARNESS_CONSOLE_DEV_SQLITE=true"
        )
    if dsn.startswith("postgresql://") or dsn.startswith("postgres://"):
        return PostgresEventStore(dsn)
    if dsn.startswith("sqlite:///"):
        return SqliteEventStore(dsn.removeprefix("sqlite:///"))
    raise RuntimeError(f"unsupported HARNESS_CONSOLE_DATABASE_URL scheme: {dsn}")


async def _event_stream(run_id: str, store: EventStore) -> AsyncIterator[str]:
    last_sequence = -1
    while True:
        events = [event for event in store.list_events(run_id) if event.sequence > last_sequence]
        for event in events:
            last_sequence = event.sequence
            yield f"event: {event.event_type}\ndata: {event.model_dump_json()}\n\n"
        await asyncio.sleep(0.25)


__all__ = ["build_store_from_env", "create_app"]
