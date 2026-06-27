"""EventStore port plus SQLite/Postgres implementations.

The domain depends on EventStore. Storage-specific code is isolated here so the
future FastAPI adapter can stay thin.

# KG: task-harness-console-event-store-2026-06-24
# KG: plan-harness-console-live-verdict-2026-06-24
"""

from __future__ import annotations

import json
import sqlite3
import threading
from abc import ABC, abstractmethod
from collections.abc import Iterable
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from engine.harness_console.models import (
    HarnessEvent,
    HumanVerdict,
    HumanVerdictRequest,
    LabelTask,
    LabelTaskStatus,
    RequestStatus,
)


class StoreError(RuntimeError):
    """Base storage error."""


class StoreConflict(StoreError):
    """Uniqueness or lifecycle conflict."""


class StoreNotFound(StoreError):
    """Requested row does not exist."""


class EventStore(ABC):
    """Persistence port for Harness Console events and review queues."""

    @abstractmethod
    def init_schema(self) -> None: ...

    @abstractmethod
    def append_event(self, event: HarnessEvent) -> HarnessEvent: ...

    @abstractmethod
    def list_events(self, run_id: str) -> list[HarnessEvent]: ...

    @abstractmethod
    def create_verdict_request(self, request: HumanVerdictRequest) -> HumanVerdictRequest: ...

    @abstractmethod
    def list_verdict_requests(
        self, status: RequestStatus | None = None
    ) -> list[HumanVerdictRequest]: ...

    @abstractmethod
    def submit_human_verdict(self, verdict: HumanVerdict) -> HumanVerdict: ...

    @abstractmethod
    def create_label_task(self, task: LabelTask) -> LabelTask: ...

    @abstractmethod
    def list_label_tasks(
        self, project_id: str | None = None, status: LabelTaskStatus | None = None
    ) -> list[LabelTask]: ...

    @abstractmethod
    def update_label_task_status(self, task_id: str, status: LabelTaskStatus) -> LabelTask: ...


_SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS harness_events (
      id TEXT PRIMARY KEY,
      run_id TEXT NOT NULL,
      sequence INTEGER NOT NULL,
      event_type TEXT NOT NULL,
      source TEXT NOT NULL,
      payload_json TEXT NOT NULL,
      created_at TEXT NOT NULL,
      UNIQUE(run_id, sequence)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_harness_events_run_sequence
      ON harness_events (run_id, sequence)
    """,
    """
    CREATE TABLE IF NOT EXISTS verdict_requests (
      id TEXT PRIMARY KEY,
      target_ref TEXT NOT NULL,
      target_kind TEXT NOT NULL,
      context_json TEXT NOT NULL,
      evidence_refs_json TEXT NOT NULL,
      prior_verdicts_json TEXT NOT NULL,
      recommended_action TEXT,
      allowed_verdicts_json TEXT NOT NULL,
      status TEXT NOT NULL,
      created_at TEXT NOT NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_verdict_requests_status_created
      ON verdict_requests (status, created_at)
    """,
    """
    CREATE TABLE IF NOT EXISTS human_verdicts (
      id TEXT PRIMARY KEY,
      request_id TEXT NOT NULL,
      verdict TEXT NOT NULL,
      rationale TEXT NOT NULL,
      reviewer_id TEXT NOT NULL,
      evidence_refs_json TEXT NOT NULL,
      created_at TEXT NOT NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_human_verdicts_request
      ON human_verdicts (request_id, created_at)
    """,
    """
    CREATE TABLE IF NOT EXISTS label_tasks (
      id TEXT PRIMARY KEY,
      project_id TEXT NOT NULL,
      target_ref TEXT NOT NULL,
      target_kind TEXT NOT NULL,
      proposed_label TEXT,
      allowed_labels_json TEXT NOT NULL,
      ai_confidence REAL,
      evidence_refs_json TEXT NOT NULL,
      missing_evidence_json TEXT NOT NULL,
      blocking_questions_json TEXT NOT NULL,
      status TEXT NOT NULL,
      created_at TEXT NOT NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_label_tasks_project_status
      ON label_tasks (project_id, status, created_at)
    """,
)


class SqliteEventStore(EventStore):
    """SQLite implementation for tests and offline development."""

    def __init__(self, path: str | Path = ":memory:") -> None:
        self.path = str(path)
        self._memory_conn: sqlite3.Connection | None = None
        self._lock = threading.RLock()
        if self.path == ":memory:":
            self._memory_conn = self._connect()

    def init_schema(self) -> None:
        with self._session() as conn:
            for statement in _SCHEMA:
                conn.execute(statement)

    def append_event(self, event: HarnessEvent) -> HarnessEvent:
        try:
            with self._session() as conn:
                conn.execute(
                    """
                    INSERT INTO harness_events (
                      id, run_id, sequence, event_type, source, payload_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event.id,
                        event.run_id,
                        event.sequence,
                        event.event_type,
                        event.source,
                        _dump(event.payload),
                        _dt(event.created_at),
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise StoreConflict(f"event already exists or sequence conflict: {event.id}") from exc
        return event

    def list_events(self, run_id: str) -> list[HarnessEvent]:
        with self._session() as conn:
            rows = conn.execute(
                """
                SELECT id, run_id, sequence, event_type, source, payload_json, created_at
                FROM harness_events
                WHERE run_id = ?
                ORDER BY sequence ASC
                """,
                (run_id,),
            ).fetchall()
        return [_event_from_row(row) for row in rows]

    def create_verdict_request(self, request: HumanVerdictRequest) -> HumanVerdictRequest:
        try:
            with self._session() as conn:
                conn.execute(
                    """
                    INSERT INTO verdict_requests (
                      id, target_ref, target_kind, context_json, evidence_refs_json,
                      prior_verdicts_json, recommended_action, allowed_verdicts_json,
                      status, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    _request_params(request),
                )
        except sqlite3.IntegrityError as exc:
            raise StoreConflict(f"verdict request already exists: {request.id}") from exc
        return request

    def list_verdict_requests(
        self, status: RequestStatus | None = None
    ) -> list[HumanVerdictRequest]:
        sql = """
            SELECT id, target_ref, target_kind, context_json, evidence_refs_json,
                   prior_verdicts_json, recommended_action, allowed_verdicts_json,
                   status, created_at
            FROM verdict_requests
        """
        params: tuple[str, ...] = ()
        if status is not None:
            sql += " WHERE status = ?"
            params = (status.value,)
        sql += " ORDER BY created_at ASC, id ASC"
        with self._session() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [_request_from_row(row) for row in rows]

    def submit_human_verdict(self, verdict: HumanVerdict) -> HumanVerdict:
        with self._session() as conn:
            row = conn.execute(
                "SELECT status, allowed_verdicts_json FROM verdict_requests WHERE id = ?",
                (verdict.request_id,),
            ).fetchone()
            if row is None:
                raise StoreNotFound(f"verdict request not found: {verdict.request_id}")
            status = RequestStatus(row["status"])
            allowed = set(_load(row["allowed_verdicts_json"]))
            if status not in {RequestStatus.PENDING, RequestStatus.DEFERRED}:
                raise StoreConflict(f"request is not open for submission: {verdict.request_id}")
            if verdict.verdict.value not in allowed:
                raise StoreConflict(f"verdict {verdict.verdict.value} is not allowed")
            try:
                conn.execute(
                    """
                    INSERT INTO human_verdicts (
                      id, request_id, verdict, rationale, reviewer_id, evidence_refs_json,
                      created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    _verdict_params(verdict),
                )
            except sqlite3.IntegrityError as exc:
                raise StoreConflict(f"human verdict already exists: {verdict.id}") from exc
            conn.execute(
                "UPDATE verdict_requests SET status = ? WHERE id = ?",
                (RequestStatus.SUBMITTED.value, verdict.request_id),
            )
        return verdict

    def create_label_task(self, task: LabelTask) -> LabelTask:
        try:
            with self._session() as conn:
                conn.execute(
                    """
                    INSERT INTO label_tasks (
                      id, project_id, target_ref, target_kind, proposed_label,
                      allowed_labels_json, ai_confidence, evidence_refs_json,
                      missing_evidence_json, blocking_questions_json, status, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    _label_task_params(task),
                )
        except sqlite3.IntegrityError as exc:
            raise StoreConflict(f"label task already exists: {task.id}") from exc
        return task

    def list_label_tasks(
        self, project_id: str | None = None, status: LabelTaskStatus | None = None
    ) -> list[LabelTask]:
        clauses: list[str] = []
        params: list[str] = []
        if project_id is not None:
            clauses.append("project_id = ?")
            params.append(project_id)
        if status is not None:
            clauses.append("status = ?")
            params.append(status.value)
        sql = """
            SELECT id, project_id, target_ref, target_kind, proposed_label,
                   allowed_labels_json, ai_confidence, evidence_refs_json,
                   missing_evidence_json, blocking_questions_json, status, created_at
            FROM label_tasks
        """
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY created_at ASC, id ASC"
        with self._session() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
        return [_label_task_from_row(row) for row in rows]

    def update_label_task_status(self, task_id: str, status: LabelTaskStatus) -> LabelTask:
        with self._session() as conn:
            result = conn.execute(
                "UPDATE label_tasks SET status = ? WHERE id = ?",
                (status.value, task_id),
            )
            if result.rowcount == 0:
                raise StoreNotFound(f"label task not found: {task_id}")
            row = conn.execute(
                """
                SELECT id, project_id, target_ref, target_kind, proposed_label,
                       allowed_labels_json, ai_confidence, evidence_refs_json,
                       missing_evidence_json, blocking_questions_json, status, created_at
                FROM label_tasks
                WHERE id = ?
                """,
                (task_id,),
            ).fetchone()
        if row is None:
            raise StoreNotFound(f"label task not found after update: {task_id}")
        return _label_task_from_row(row)

    @contextmanager
    def _session(self):
        with self._lock:
            if self._memory_conn is not None:
                yield self._memory_conn
                self._memory_conn.commit()
                return
            conn = self._connect()
            try:
                yield conn
                conn.commit()
            finally:
                conn.close()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn


class PostgresEventStore(EventStore):
    """Postgres implementation for the shared deployment.

    psycopg is imported lazily so the default test environment can exercise the
    domain and SQLite adapter without installing Postgres client dependencies.
    """

    def __init__(self, dsn: str) -> None:
        self.dsn = dsn
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:  # pragma: no cover - depends on optional dependency
            raise ImportError("Install psycopg to use PostgresEventStore") from exc
        self._psycopg = psycopg
        self._row_factory = dict_row

    def init_schema(self) -> None:
        with self._session() as conn:
            for statement in _SCHEMA:
                conn.execute(statement)

    def append_event(self, event: HarnessEvent) -> HarnessEvent:
        try:
            with self._session() as conn:
                conn.execute(
                    """
                    INSERT INTO harness_events (
                      id, run_id, sequence, event_type, source, payload_json, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        event.id,
                        event.run_id,
                        event.sequence,
                        event.event_type,
                        event.source,
                        _dump(event.payload),
                        _dt(event.created_at),
                    ),
                )
        except Exception as exc:
            if exc.__class__.__name__ == "UniqueViolation":
                raise StoreConflict(
                    f"event already exists or sequence conflict: {event.id}"
                ) from exc
            raise
        return event

    def list_events(self, run_id: str) -> list[HarnessEvent]:
        with self._session() as conn:
            rows = conn.execute(
                """
                SELECT id, run_id, sequence, event_type, source, payload_json, created_at
                FROM harness_events
                WHERE run_id = %s
                ORDER BY sequence ASC
                """,
                (run_id,),
            ).fetchall()
        return [_event_from_row(row) for row in rows]

    def create_verdict_request(self, request: HumanVerdictRequest) -> HumanVerdictRequest:
        try:
            with self._session() as conn:
                conn.execute(
                    """
                    INSERT INTO verdict_requests (
                      id, target_ref, target_kind, context_json, evidence_refs_json,
                      prior_verdicts_json, recommended_action, allowed_verdicts_json,
                      status, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    _request_params(request),
                )
        except Exception as exc:
            if exc.__class__.__name__ == "UniqueViolation":
                raise StoreConflict(f"verdict request already exists: {request.id}") from exc
            raise
        return request

    def list_verdict_requests(
        self, status: RequestStatus | None = None
    ) -> list[HumanVerdictRequest]:
        sql = """
            SELECT id, target_ref, target_kind, context_json, evidence_refs_json,
                   prior_verdicts_json, recommended_action, allowed_verdicts_json,
                   status, created_at
            FROM verdict_requests
        """
        params: tuple[str, ...] = ()
        if status is not None:
            sql += " WHERE status = %s"
            params = (status.value,)
        sql += " ORDER BY created_at ASC, id ASC"
        with self._session() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [_request_from_row(row) for row in rows]

    def submit_human_verdict(self, verdict: HumanVerdict) -> HumanVerdict:
        with self._session() as conn:
            row = conn.execute(
                "SELECT status, allowed_verdicts_json FROM verdict_requests WHERE id = %s",
                (verdict.request_id,),
            ).fetchone()
            if row is None:
                raise StoreNotFound(f"verdict request not found: {verdict.request_id}")
            status = RequestStatus(row["status"])
            allowed = set(_load(row["allowed_verdicts_json"]))
            if status not in {RequestStatus.PENDING, RequestStatus.DEFERRED}:
                raise StoreConflict(f"request is not open for submission: {verdict.request_id}")
            if verdict.verdict.value not in allowed:
                raise StoreConflict(f"verdict {verdict.verdict.value} is not allowed")
            try:
                conn.execute(
                    """
                    INSERT INTO human_verdicts (
                      id, request_id, verdict, rationale, reviewer_id, evidence_refs_json,
                      created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    _verdict_params(verdict),
                )
            except Exception as exc:
                if exc.__class__.__name__ == "UniqueViolation":
                    raise StoreConflict(f"human verdict already exists: {verdict.id}") from exc
                raise
            conn.execute(
                "UPDATE verdict_requests SET status = %s WHERE id = %s",
                (RequestStatus.SUBMITTED.value, verdict.request_id),
            )
        return verdict

    def create_label_task(self, task: LabelTask) -> LabelTask:
        try:
            with self._session() as conn:
                conn.execute(
                    """
                    INSERT INTO label_tasks (
                      id, project_id, target_ref, target_kind, proposed_label,
                      allowed_labels_json, ai_confidence, evidence_refs_json,
                      missing_evidence_json, blocking_questions_json, status, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    _label_task_params(task),
                )
        except Exception as exc:
            if exc.__class__.__name__ == "UniqueViolation":
                raise StoreConflict(f"label task already exists: {task.id}") from exc
            raise
        return task

    def list_label_tasks(
        self, project_id: str | None = None, status: LabelTaskStatus | None = None
    ) -> list[LabelTask]:
        clauses: list[str] = []
        params: list[str] = []
        if project_id is not None:
            clauses.append("project_id = %s")
            params.append(project_id)
        if status is not None:
            clauses.append("status = %s")
            params.append(status.value)
        sql = """
            SELECT id, project_id, target_ref, target_kind, proposed_label,
                   allowed_labels_json, ai_confidence, evidence_refs_json,
                   missing_evidence_json, blocking_questions_json, status, created_at
            FROM label_tasks
        """
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY created_at ASC, id ASC"
        with self._session() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
        return [_label_task_from_row(row) for row in rows]

    def update_label_task_status(self, task_id: str, status: LabelTaskStatus) -> LabelTask:
        with self._session() as conn:
            result = conn.execute(
                "UPDATE label_tasks SET status = %s WHERE id = %s",
                (status.value, task_id),
            )
            if result.rowcount == 0:
                raise StoreNotFound(f"label task not found: {task_id}")
            row = conn.execute(
                """
                SELECT id, project_id, target_ref, target_kind, proposed_label,
                       allowed_labels_json, ai_confidence, evidence_refs_json,
                       missing_evidence_json, blocking_questions_json, status, created_at
                FROM label_tasks
                WHERE id = %s
                """,
                (task_id,),
            ).fetchone()
        if row is None:
            raise StoreNotFound(f"label task not found after update: {task_id}")
        return _label_task_from_row(row)

    @contextmanager
    def _session(self):
        with self._psycopg.connect(self.dsn, row_factory=self._row_factory) as conn:
            yield conn


def _request_params(request: HumanVerdictRequest) -> tuple[Any, ...]:
    return (
        request.id,
        request.target_ref,
        request.target_kind.value,
        _dump(request.context),
        _dump(request.evidence_refs),
        _dump(request.prior_verdicts),
        request.recommended_action,
        _dump([v.value for v in request.allowed_verdicts]),
        request.status.value,
        _dt(request.created_at),
    )


def _verdict_params(verdict: HumanVerdict) -> tuple[Any, ...]:
    return (
        verdict.id,
        verdict.request_id,
        verdict.verdict.value,
        verdict.rationale,
        verdict.reviewer_id,
        _dump(verdict.evidence_refs),
        _dt(verdict.created_at),
    )


def _label_task_params(task: LabelTask) -> tuple[Any, ...]:
    return (
        task.id,
        task.project_id,
        task.target_ref,
        task.target_kind,
        task.proposed_label,
        _dump(task.allowed_labels),
        task.ai_confidence,
        _dump(task.evidence_refs),
        _dump(task.missing_evidence),
        _dump(task.blocking_questions),
        task.status.value,
        _dt(task.created_at),
    )


def _event_from_row(row: Any) -> HarnessEvent:
    return HarnessEvent(
        id=row["id"],
        run_id=row["run_id"],
        sequence=row["sequence"],
        event_type=row["event_type"],
        source=row["source"],
        payload=_load(row["payload_json"]),
        created_at=row["created_at"],
    )


def _request_from_row(row: Any) -> HumanVerdictRequest:
    return HumanVerdictRequest(
        id=row["id"],
        target_ref=row["target_ref"],
        target_kind=row["target_kind"],
        context=_load(row["context_json"]),
        evidence_refs=_load(row["evidence_refs_json"]),
        prior_verdicts=_load(row["prior_verdicts_json"]),
        recommended_action=row["recommended_action"],
        allowed_verdicts=_load(row["allowed_verdicts_json"]),
        status=row["status"],
        created_at=row["created_at"],
    )


def _label_task_from_row(row: Any) -> LabelTask:
    return LabelTask(
        id=row["id"],
        project_id=row["project_id"],
        target_ref=row["target_ref"],
        target_kind=row["target_kind"],
        proposed_label=row["proposed_label"],
        allowed_labels=_load(row["allowed_labels_json"]),
        ai_confidence=row["ai_confidence"],
        evidence_refs=_load(row["evidence_refs_json"]),
        missing_evidence=_load(row["missing_evidence_json"]),
        blocking_questions=_load(row["blocking_questions_json"]),
        status=row["status"],
        created_at=row["created_at"],
    )


def _dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _load(value: str) -> Any:
    return json.loads(value)


def _dt(value: Any) -> str:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def assert_events(events: Iterable[HarnessEvent]) -> list[HarnessEvent]:
    """Small test helper: materialize and validate event sequence ordering."""
    out = list(events)
    sequences = [event.sequence for event in out]
    if sequences != sorted(sequences):
        raise ValueError("events are not sorted by sequence")
    return out


__all__ = [
    "EventStore",
    "PostgresEventStore",
    "SqliteEventStore",
    "StoreConflict",
    "StoreError",
    "StoreNotFound",
    "assert_events",
]
