"""Durable state-plane vertical slice for Eureka's bounded creative loop.

The slice deliberately stays small:

* immutable filesystem CAS for candidate, context, proposal, and receipt bytes;
* append-only SQLite journal with ``BEGIN IMMEDIATE`` single-writer serialization;
* expected-version fencing and command idempotency;
* a CandidateArchive projection updated atomically with the journal and rebuildable
  from it.

The store records PROPOSE-only facts.  It has no KG writer, acceptance transition,
outbox dispatcher, or Hades materialization authority.

# KG: eureka-canonical-2026-05-26
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import tempfile
from collections.abc import Callable, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from engine.eureka.archive import (
    ARCHIVE_EVENT_SCHEMA,
    ARCHIVE_EVENT_TYPES,
    CANDIDATE_EVALUATED,
    CANDIDATE_OBSERVED,
    CREATIVE_RUN_COMPLETED,
    ArchiveProjectionError,
    ArchiveStatus,
    CandidateArchiveEntry,
    CandidateEvaluated,
    CandidateObserved,
    CreativeRunCompleted,
    EventPosition,
    reduce_candidate_archive,
)


STORE_SCHEMA_VERSION = 1
PROJECTION_NAME = "candidate_archive/v1"
_SHA256_PATTERN = r"^[0-9a-f]{64}$"
_SHA256_RE = re.compile(_SHA256_PATTERN)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _canonical_json(value: Any) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest_json(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _iso_utc(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("durable timestamps must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat()


def default_eureka_state_dir() -> Path:
    """``BHGMAN_EUREKA_STATE_DIR`` or the user-local ``~/.bhgman/eureka``."""

    configured = os.environ.get("BHGMAN_EUREKA_STATE_DIR")
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".bhgman" / "eureka"


class DurableStoreError(RuntimeError):
    """Base class for durable Eureka storage failures."""


class MissingBlobError(DurableStoreError):
    """A journal or caller referenced a CAS object that does not exist."""


class CorruptBlobError(DurableStoreError):
    """CAS bytes no longer match their content address or recorded size."""


class VersionConflict(DurableStoreError):
    """The caller's expected aggregate version is stale or from another run."""


class IdempotencyConflict(DurableStoreError):
    """The same command key was reused for different intent."""


class UnsupportedStoreVersion(DurableStoreError):
    """The SQLite file needs a schema migration this implementation cannot perform."""


class BlobRef(BaseModel):
    """Self-describing reference returned by :class:`FileCAS`."""

    model_config = ConfigDict(frozen=True)

    sha256: str = Field(..., pattern=_SHA256_PATTERN)
    size: int = Field(..., ge=0)
    media_type: str = Field(..., min_length=1)


class FileCAS:
    """Immutable SHA-256 object store using same-filesystem atomic publication.

    Objects live at ``<root>/sha256/<first-two>/<remaining-62>``.  A writer fsyncs
    the temporary file, publishes it with a non-overwriting hard link, removes the
    temporary name, then fsyncs the containing directory.  A duplicate put verifies
    existing bytes instead of overwriting them.
    """

    def __init__(
        self,
        root: str | Path,
        *,
        fault_injector: Callable[[str], None] | None = None,
    ) -> None:
        self.root = Path(root).expanduser()
        self._sha_root = self.root / "sha256"
        self._fault_injector = fault_injector

    def put_json(self, value: Any) -> BlobRef:
        data = _canonical_json(value).encode("utf-8")
        return self.put_bytes(data, media_type="application/json")

    def put_bytes(
        self,
        data: bytes,
        *,
        media_type: str = "application/octet-stream",
    ) -> BlobRef:
        if not isinstance(data, bytes):
            raise TypeError("FileCAS.put_bytes requires bytes")
        digest = hashlib.sha256(data).hexdigest()
        target = self._path(digest)
        ref = BlobRef(sha256=digest, size=len(data), media_type=media_type)
        if target.exists():
            self._verify_path(target, ref)
            return ref

        self._mkdir_private(target.parent)
        descriptor, temporary_name = tempfile.mkstemp(
            dir=target.parent,
            prefix=f".{digest}.",
            suffix=".tmp",
        )
        descriptor_open = True
        try:
            try:
                os.fchmod(descriptor, 0o600)
            except OSError:
                pass
            with os.fdopen(descriptor, "wb") as handle:
                descriptor_open = False
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            self._fault("before_publish")
            try:
                # Atomic create-if-absent: unlike replace(), this never overwrites an
                # immutable object installed by another writer between exists() and now.
                os.link(temporary_name, target)
            except FileExistsError:
                pass
            os.unlink(temporary_name)
            self._fsync_directory(target.parent)
            self._verify_path(target, ref)
            self._fault("after_publish")
            return ref
        finally:
            if descriptor_open:
                os.close(descriptor)
            if os.path.exists(temporary_name):
                os.unlink(temporary_name)

    def get_bytes(self, reference: BlobRef | str) -> bytes:
        digest = reference.sha256 if isinstance(reference, BlobRef) else reference
        target = self._path(digest)
        if not target.exists():
            raise MissingBlobError(f"CAS object is missing: {digest}")
        data = target.read_bytes()
        actual = hashlib.sha256(data).hexdigest()
        if actual != digest:
            raise CorruptBlobError(f"CAS digest mismatch: expected {digest}, got {actual}")
        if isinstance(reference, BlobRef) and len(data) != reference.size:
            raise CorruptBlobError(
                f"CAS size mismatch for {digest}: expected {reference.size}, got {len(data)}"
            )
        return data

    def get_json(self, reference: BlobRef | str) -> Any:
        return json.loads(self.get_bytes(reference).decode("utf-8"))

    def exists(self, reference: BlobRef | str) -> bool:
        digest = reference.sha256 if isinstance(reference, BlobRef) else reference
        return self._path(digest).exists()

    def verify(self, reference: BlobRef | str) -> None:
        self.get_bytes(reference)

    def path_for(self, digest: str) -> Path:
        """Expose the deterministic object path for diagnostics and integrity tests."""

        return self._path(digest)

    def _path(self, digest: str) -> Path:
        if not isinstance(digest, str) or _SHA256_RE.fullmatch(digest) is None:
            raise ValueError(f"invalid sha256 digest: {digest!r}")
        return self._sha_root / digest[:2] / digest[2:]

    @staticmethod
    def _mkdir_private(path: Path) -> None:
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
        try:
            os.chmod(path, 0o700)
        except OSError:
            pass

    @staticmethod
    def _fsync_directory(path: Path) -> None:
        descriptor = os.open(path, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    @staticmethod
    def _verify_path(path: Path, reference: BlobRef) -> None:
        data = path.read_bytes()
        actual = hashlib.sha256(data).hexdigest()
        if actual != reference.sha256 or len(data) != reference.size:
            raise CorruptBlobError(
                f"immutable CAS object conflicts with {reference.sha256}: "
                f"actual={actual}, size={len(data)}"
            )

    def _fault(self, stage: str) -> None:
        if self._fault_injector is not None:
            self._fault_injector(stage)


class NewJournalEvent(BaseModel):
    """Unpositioned event accepted by :meth:`SqliteEurekaStore.commit`."""

    event_type: str = Field(..., min_length=1)
    payload: dict[str, Any]
    event_schema: str = Field(default=ARCHIVE_EVENT_SCHEMA, min_length=1)


class StoredJournalEvent(BaseModel):
    """Immutable event envelope read from SQLite."""

    event_id: str
    global_seq: int = Field(..., ge=1)
    run_id: str
    run_seq: int = Field(..., ge=1)
    event_type: str
    event_schema: str
    payload: dict[str, Any]
    occurred_at: str
    command_id: str


class CommitReceipt(BaseModel):
    """Cached response returned identically for a safe command retry."""

    run_id: str
    command_id: str
    intent_hash: str = Field(..., pattern=_SHA256_PATTERN)
    previous_version: int = Field(..., ge=0)
    committed_version: int = Field(..., ge=1)
    first_global_seq: int = Field(..., ge=1)
    last_global_seq: int = Field(..., ge=1)
    event_ids: tuple[str, ...] = Field(..., min_length=1)
    committed_at: str


class ProjectionStats(BaseModel):
    events_scanned: int = Field(..., ge=0)
    candidates: int = Field(..., ge=0)
    last_global_seq: int = Field(..., ge=0)


_SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS run_heads (
      run_id TEXT PRIMARY KEY,
      version INTEGER NOT NULL CHECK (version >= 0),
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS journal_events (
      global_seq INTEGER PRIMARY KEY AUTOINCREMENT,
      event_id TEXT NOT NULL UNIQUE,
      run_id TEXT NOT NULL REFERENCES run_heads(run_id),
      run_seq INTEGER NOT NULL CHECK (run_seq >= 1),
      event_type TEXT NOT NULL,
      event_schema TEXT NOT NULL,
      payload_json TEXT NOT NULL,
      occurred_at TEXT NOT NULL,
      command_id TEXT NOT NULL,
      UNIQUE (run_id, run_seq)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_eureka_journal_run_seq
      ON journal_events (run_id, run_seq)
    """,
    """
    CREATE TRIGGER IF NOT EXISTS trg_eureka_journal_no_update
    BEFORE UPDATE ON journal_events
    BEGIN
      SELECT RAISE(ABORT, 'journal_events is append-only');
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS trg_eureka_journal_no_delete
    BEFORE DELETE ON journal_events
    BEGIN
      SELECT RAISE(ABORT, 'journal_events is append-only');
    END
    """,
    """
    CREATE TABLE IF NOT EXISTS command_dedup (
      run_id TEXT NOT NULL,
      command_id TEXT NOT NULL,
      intent_hash TEXT NOT NULL,
      result_json TEXT NOT NULL,
      committed_at TEXT NOT NULL,
      PRIMARY KEY (run_id, command_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS candidate_archive (
      candidate_digest TEXT PRIMARY KEY,
      semantic_fingerprint TEXT NOT NULL,
      candidate_ref TEXT NOT NULL,
      first_context_ref TEXT NOT NULL,
      last_context_ref TEXT NOT NULL,
      first_proposal_ref TEXT NOT NULL,
      last_proposal_ref TEXT NOT NULL,
      status TEXT NOT NULL CHECK (status IN ('OBSERVED', 'PROPOSED', 'REJECTED')),
      latest_receipt_ref TEXT,
      rejection_reasons_json TEXT NOT NULL,
      score_min REAL,
      gate_config_hash TEXT,
      first_cycle_id TEXT NOT NULL,
      last_cycle_id TEXT NOT NULL,
      first_seed_id TEXT NOT NULL,
      last_seed_id TEXT NOT NULL,
      first_global_seq INTEGER NOT NULL,
      last_global_seq INTEGER NOT NULL,
      seen_count INTEGER NOT NULL CHECK (seen_count >= 1),
      latest_round INTEGER NOT NULL CHECK (latest_round >= 1),
      latest_parent_candidate_digest TEXT,
      source_layer TEXT NOT NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_eureka_archive_fingerprint
      ON candidate_archive (semantic_fingerprint, last_global_seq)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_eureka_archive_status_score
      ON candidate_archive (status, score_min, last_global_seq)
    """,
    """
    CREATE TABLE IF NOT EXISTS projection_heads (
      name TEXT PRIMARY KEY,
      schema_version INTEGER NOT NULL,
      last_global_seq INTEGER NOT NULL CHECK (last_global_seq >= 0)
    )
    """,
)


class SqliteEurekaStore:
    """Single-writer journal plus atomic CandidateArchive projection."""

    def __init__(
        self,
        path: str | Path | None = None,
        *,
        cas: FileCAS | None = None,
        clock: Callable[[], datetime] = _utc_now,
        fault_injector: Callable[[str], None] | None = None,
        busy_timeout_ms: int = 10_000,
    ) -> None:
        state_dir = default_eureka_state_dir()
        self.path = Path(path).expanduser() if path is not None else state_dir / "journal.sqlite3"
        self.cas = cas or FileCAS(self.path.parent / "cas")
        self._clock = clock
        self._fault_injector = fault_injector
        self._busy_timeout_ms = busy_timeout_ms
        self.init_schema()

    def init_schema(self) -> None:
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        try:
            os.chmod(self.path.parent, 0o700)
        except OSError:
            pass
        conn = self._connect()
        try:
            conn.execute("PRAGMA journal_mode = WAL")
            current = int(conn.execute("PRAGMA user_version").fetchone()[0])
            if current not in {0, STORE_SCHEMA_VERSION}:
                raise UnsupportedStoreVersion(
                    f"Eureka store schema {current} is not supported; expected {STORE_SCHEMA_VERSION}"
                )
            conn.execute("BEGIN IMMEDIATE")
            for statement in _SCHEMA_STATEMENTS:
                conn.execute(statement)
            conn.execute(f"PRAGMA user_version = {STORE_SCHEMA_VERSION}")
            conn.commit()
        except BaseException:
            if conn.in_transaction:
                conn.rollback()
            raise
        finally:
            conn.close()
        if self.path.exists():
            try:
                os.chmod(self.path, 0o600)
            except OSError:
                pass

    def commit(
        self,
        *,
        run_id: str,
        command_id: str,
        expected_version: int,
        events: Sequence[NewJournalEvent],
    ) -> CommitReceipt:
        """Atomically append events and advance the CandidateArchive projection.

        A duplicate ``(run_id, command_id)`` is checked before the current version.
        Equal intent returns the cached original receipt; changed intent is a conflict.
        """

        if not run_id or not command_id:
            raise ValueError("run_id and command_id must not be blank")
        if expected_version < 0:
            raise ValueError("expected_version must be non-negative")
        normalized = tuple(NewJournalEvent.model_validate(event) for event in events)
        if not normalized:
            raise ValueError("a durable commit must contain at least one event")
        intent = {
            "run_id": run_id,
            "command_id": command_id,
            "expected_version": expected_version,
            "events": [event.model_dump(mode="json") for event in normalized],
        }
        intent_hash = _digest_json(intent)
        committed_at = _iso_utc(self._clock())
        conn = self._connect()
        created = False
        try:
            conn.execute("BEGIN IMMEDIATE")
            duplicate = conn.execute(
                """
                SELECT intent_hash, result_json
                FROM command_dedup
                WHERE run_id = ? AND command_id = ?
                """,
                (run_id, command_id),
            ).fetchone()
            if duplicate is not None:
                if duplicate["intent_hash"] != intent_hash:
                    raise IdempotencyConflict(
                        f"command {command_id!r} for run {run_id!r} was reused with different intent"
                    )
                receipt = CommitReceipt.model_validate_json(duplicate["result_json"])
                conn.commit()
                return receipt

            head = conn.execute(
                "SELECT version FROM run_heads WHERE run_id = ?", (run_id,)
            ).fetchone()
            current_version = int(head["version"]) if head is not None else 0
            if current_version != expected_version:
                raise VersionConflict(
                    f"run {run_id!r} expected version {expected_version}, current {current_version}"
                )
            if head is None:
                conn.execute(
                    """
                    INSERT INTO run_heads (run_id, version, created_at, updated_at)
                    VALUES (?, 0, ?, ?)
                    """,
                    (run_id, committed_at, committed_at),
                )

            stored: list[StoredJournalEvent] = []
            for offset, event in enumerate(normalized, start=1):
                run_seq = current_version + offset
                event_id = "evt-" + _digest_json(
                    {
                        "run_id": run_id,
                        "command_id": command_id,
                        "offset": offset,
                        "intent_hash": intent_hash,
                    }
                )
                cursor = conn.execute(
                    """
                    INSERT INTO journal_events (
                      event_id, run_id, run_seq, event_type, event_schema,
                      payload_json, occurred_at, command_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event_id,
                        run_id,
                        run_seq,
                        event.event_type,
                        event.event_schema,
                        _canonical_json(event.payload),
                        committed_at,
                        command_id,
                    ),
                )
                global_seq = int(cursor.lastrowid)
                envelope = StoredJournalEvent(
                    event_id=event_id,
                    global_seq=global_seq,
                    run_id=run_id,
                    run_seq=run_seq,
                    event_type=event.event_type,
                    event_schema=event.event_schema,
                    payload=event.payload,
                    occurred_at=committed_at,
                    command_id=command_id,
                )
                stored.append(envelope)
                self._apply_projection_event(conn, envelope)
            self._fault("after_journal_and_projection")

            committed_version = current_version + len(stored)
            conn.execute(
                "UPDATE run_heads SET version = ?, updated_at = ? WHERE run_id = ?",
                (committed_version, committed_at, run_id),
            )
            last_global_seq = stored[-1].global_seq
            conn.execute(
                """
                INSERT INTO projection_heads (name, schema_version, last_global_seq)
                VALUES (?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                  schema_version = excluded.schema_version,
                  last_global_seq = excluded.last_global_seq
                """,
                (PROJECTION_NAME, STORE_SCHEMA_VERSION, last_global_seq),
            )
            receipt = CommitReceipt(
                run_id=run_id,
                command_id=command_id,
                intent_hash=intent_hash,
                previous_version=current_version,
                committed_version=committed_version,
                first_global_seq=stored[0].global_seq,
                last_global_seq=last_global_seq,
                event_ids=tuple(event.event_id for event in stored),
                committed_at=committed_at,
            )
            conn.execute(
                """
                INSERT INTO command_dedup (
                  run_id, command_id, intent_hash, result_json, committed_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (run_id, command_id, intent_hash, _canonical_json(receipt), committed_at),
            )
            self._fault("before_commit")
            conn.commit()
            created = True
        except BaseException:
            if conn.in_transaction:
                conn.rollback()
            raise
        finally:
            conn.close()
        if created:
            self._fault("after_commit")
        return receipt

    def record_creative_run(
        self,
        result: Any,
        *,
        command_id: str,
        expected_version: int = 0,
        run_id: str | None = None,
    ) -> CommitReceipt:
        """Persist every produced candidate, its disposition, and the run summary.

        CAS publication happens before the SQLite transaction.  A crash in between can
        leave an unreferenced immutable blob, but a committed journal event can never
        reference a blob that was not already durable.
        """

        from engine.eureka.creative import SCHEMA_VERSION  # noqa: PLC0415

        context = result.context
        actual_run_id = run_id or context.cycle_id
        context_ref = self.cas.put_json(context.model_dump(mode="json"))

        receipt_by_candidate: dict[str, Any] = {}
        receipt_refs: dict[str, str] = {}
        for receipt in result.receipts:
            reference = self.cas.put_json(receipt.model_dump(mode="json"))
            if reference.sha256 != receipt.receipt_digest:
                raise CorruptBlobError(
                    f"receipt digest drift for candidate {receipt.candidate_digest}"
                )
            receipt_by_candidate[receipt.candidate_digest] = receipt
            receipt_refs[receipt.candidate_digest] = reference.sha256

        evaluator_receipts = tuple(getattr(result, "evaluator_receipts", ()) or ())
        evaluator_by_candidate: dict[str, Any] = {}
        evaluator_refs: dict[str, str] = {}
        for receipt in evaluator_receipts:
            reference = self.cas.put_json(receipt.model_dump(mode="json"))
            if reference.sha256 != receipt.receipt_digest:
                raise CorruptBlobError(
                    f"executable evaluator receipt digest drift for {receipt.candidate_digest}"
                )
            evaluator_by_candidate[receipt.candidate_digest] = receipt
            evaluator_refs[receipt.candidate_digest] = reference.sha256

        accepted_digests = {
            proposal.candidate_digest(context) for proposal in result.accepted
        }
        events: list[NewJournalEvent] = []
        for proposal in result.proposals:
            candidate_digest = proposal.candidate_digest(context)
            identity_blob = {
                "schema_version": SCHEMA_VERSION,
                "input_snapshot_hash": context.input_snapshot_hash,
                "baseline_snapshot_hash": context.baseline_snapshot_hash,
                "proposal": proposal.core(),
            }
            candidate_ref = self.cas.put_json(identity_blob)
            if candidate_ref.sha256 != candidate_digest:
                raise CorruptBlobError(f"candidate identity digest drift: {candidate_digest}")
            proposal_ref = self.cas.put_json(proposal.model_dump(mode="json"))
            observed = CandidateObserved(
                candidate_digest=candidate_digest,
                semantic_fingerprint=proposal.semantic_fingerprint(),
                candidate_ref=candidate_ref.sha256,
                context_ref=context_ref.sha256,
                proposal_ref=proposal_ref.sha256,
                cycle_id=context.cycle_id,
                seed_id=context.seed_id,
                round=proposal.round,
                parent_candidate_digest=proposal.parent_candidate_digest,
                source_layer="SECONDARY_AI",
            )
            events.append(
                NewJournalEvent(
                    event_type=CANDIDATE_OBSERVED,
                    payload=observed.model_dump(mode="json"),
                )
            )

            receipt = receipt_by_candidate.get(candidate_digest)
            evaluator_receipt = evaluator_by_candidate.get(candidate_digest)
            survived = candidate_digest in accepted_digests
            if survived and (receipt is None or not receipt.accepted):
                raise ArchiveProjectionError(
                    f"accepted candidate {candidate_digest} has no accepted validation receipt"
                )
            if survived and evaluator_receipts and (
                evaluator_receipt is None or not evaluator_receipt.passed
            ):
                raise ArchiveProjectionError(
                    f"accepted candidate {candidate_digest} has no passing executable receipt"
                )
            reasons = tuple(result.rejections.get(candidate_digest, ()))
            if not survived and not reasons:
                if evaluator_receipt is not None and not evaluator_receipt.passed:
                    reasons = (f"evaluator_{evaluator_receipt.verdict.value}",)
                elif receipt is None:
                    reasons = ("not_evaluated",)
                elif receipt.accepted:
                    reasons = ("not_selected",)
                elif receipt.reasons:
                    reasons = tuple(receipt.reasons)
                else:
                    reasons = (f"critic_{receipt.verdict.value}",)
            evaluated = CandidateEvaluated(
                candidate_digest=candidate_digest,
                outcome=ArchiveStatus.PROPOSED if survived else ArchiveStatus.REJECTED,
                receipt_ref=evaluator_refs.get(candidate_digest)
                or receipt_refs.get(candidate_digest),
                reasons=reasons,
                score_min=receipt.scores.minimum if receipt is not None else None,
                gate_config_hash=receipt.gate_config_hash if receipt is not None else None,
            )
            events.append(
                NewJournalEvent(
                    event_type=CANDIDATE_EVALUATED,
                    payload=evaluated.model_dump(mode="json"),
                )
            )

        completed = CreativeRunCompleted(
            context_ref=context_ref.sha256,
            outcome=result.outcome.value,
            state=result.state.value,
            rounds=result.rounds,
            model_calls=result.model_calls,
            stop_reason=result.stop_reason,
        )
        events.append(
            NewJournalEvent(
                event_type=CREATIVE_RUN_COMPLETED,
                payload=completed.model_dump(mode="json"),
            )
        )
        return self.commit(
            run_id=actual_run_id,
            command_id=command_id,
            expected_version=expected_version,
            events=events,
        )

    def read_events(
        self,
        run_id: str | None = None,
        *,
        after_global_seq: int = 0,
    ) -> list[StoredJournalEvent]:
        if after_global_seq < 0:
            raise ValueError("after_global_seq must be non-negative")
        sql = """
            SELECT event_id, global_seq, run_id, run_seq, event_type, event_schema,
                   payload_json, occurred_at, command_id
            FROM journal_events
            WHERE global_seq > ?
        """
        params: list[Any] = [after_global_seq]
        if run_id is not None:
            sql += " AND run_id = ?"
            params.append(run_id)
        sql += " ORDER BY global_seq ASC"
        conn = self._connect()
        try:
            rows = conn.execute(sql, tuple(params)).fetchall()
        finally:
            conn.close()
        return [self._event_from_row(row) for row in rows]

    def current_version(self, run_id: str) -> int:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT version FROM run_heads WHERE run_id = ?", (run_id,)
            ).fetchone()
        finally:
            conn.close()
        return int(row["version"]) if row is not None else 0

    def get_candidate(self, candidate_digest: str) -> CandidateArchiveEntry | None:
        conn = self._connect()
        try:
            return self._load_archive_entry(conn, candidate_digest)
        finally:
            conn.close()

    def list_candidates(
        self,
        *,
        status: ArchiveStatus | None = None,
        limit: int = 100,
    ) -> list[CandidateArchiveEntry]:
        if limit < 1:
            raise ValueError("limit must be positive")
        sql = "SELECT * FROM candidate_archive"
        params: list[Any] = []
        if status is not None:
            sql += " WHERE status = ?"
            params.append(status.value)
        sql += " ORDER BY last_global_seq DESC, candidate_digest ASC LIMIT ?"
        params.append(limit)
        conn = self._connect()
        try:
            rows = conn.execute(sql, tuple(params)).fetchall()
        finally:
            conn.close()
        return [self._archive_entry_from_row(row) for row in rows]

    def find_by_fingerprint(
        self,
        semantic_fingerprint: str,
        *,
        limit: int = 100,
    ) -> list[CandidateArchiveEntry]:
        if _SHA256_RE.fullmatch(semantic_fingerprint) is None:
            raise ValueError("semantic_fingerprint must be a lowercase sha256 digest")
        if limit < 1:
            raise ValueError("limit must be positive")
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT * FROM candidate_archive
                WHERE semantic_fingerprint = ?
                ORDER BY last_global_seq DESC, candidate_digest ASC
                LIMIT ?
                """,
                (semantic_fingerprint, limit),
            ).fetchall()
        finally:
            conn.close()
        return [self._archive_entry_from_row(row) for row in rows]

    def rebuild_candidate_archive(self) -> ProjectionStats:
        """Discard and replay the derived view in one rollback-safe transaction."""

        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("DELETE FROM candidate_archive")
            conn.execute("DELETE FROM projection_heads WHERE name = ?", (PROJECTION_NAME,))
            rows = conn.execute(
                """
                SELECT event_id, global_seq, run_id, run_seq, event_type, event_schema,
                       payload_json, occurred_at, command_id
                FROM journal_events
                ORDER BY global_seq ASC
                """
            ).fetchall()
            last_global_seq = 0
            for row in rows:
                event = self._event_from_row(row)
                self._apply_projection_event(conn, event)
                last_global_seq = event.global_seq
            conn.execute(
                """
                INSERT INTO projection_heads (name, schema_version, last_global_seq)
                VALUES (?, ?, ?)
                """,
                (PROJECTION_NAME, STORE_SCHEMA_VERSION, last_global_seq),
            )
            count = int(conn.execute("SELECT COUNT(*) FROM candidate_archive").fetchone()[0])
            conn.commit()
            return ProjectionStats(
                events_scanned=len(rows),
                candidates=count,
                last_global_seq=last_global_seq,
            )
        except BaseException:
            if conn.in_transaction:
                conn.rollback()
            raise
        finally:
            conn.close()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(
            self.path,
            timeout=max(0.001, self._busy_timeout_ms / 1000),
            isolation_level=None,
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute(f"PRAGMA busy_timeout = {int(self._busy_timeout_ms)}")
        conn.execute("PRAGMA synchronous = FULL")
        return conn

    def _apply_projection_event(
        self,
        conn: sqlite3.Connection,
        event: StoredJournalEvent,
    ) -> None:
        if event.event_type not in ARCHIVE_EVENT_TYPES:
            return
        if event.event_schema != ARCHIVE_EVENT_SCHEMA:
            raise ArchiveProjectionError(
                f"unsupported archive event schema {event.event_schema!r} at {event.global_seq}"
            )
        self._verify_event_blobs(event)
        digest = event.payload.get("candidate_digest")
        current = self._load_archive_entry(conn, digest) if isinstance(digest, str) else None
        updated = reduce_candidate_archive(
            current,
            event.event_type,
            event.payload,
            EventPosition(
                global_seq=event.global_seq,
                run_id=event.run_id,
                run_seq=event.run_seq,
            ),
        )
        if updated is not None:
            self._write_archive_entry(conn, updated)

    def _verify_event_blobs(self, event: StoredJournalEvent) -> None:
        payload = event.payload
        if event.event_type == CANDIDATE_OBSERVED:
            observed = CandidateObserved.model_validate(payload)
            for digest in (
                observed.candidate_ref,
                observed.context_ref,
                observed.proposal_ref,
            ):
                self.cas.verify(digest)
        elif event.event_type == CANDIDATE_EVALUATED:
            evaluated = CandidateEvaluated.model_validate(payload)
            if evaluated.receipt_ref is not None:
                self.cas.verify(evaluated.receipt_ref)
        elif event.event_type == CREATIVE_RUN_COMPLETED:
            completed = CreativeRunCompleted.model_validate(payload)
            self.cas.verify(completed.context_ref)

    @staticmethod
    def _event_from_row(row: sqlite3.Row) -> StoredJournalEvent:
        return StoredJournalEvent(
            event_id=row["event_id"],
            global_seq=row["global_seq"],
            run_id=row["run_id"],
            run_seq=row["run_seq"],
            event_type=row["event_type"],
            event_schema=row["event_schema"],
            payload=json.loads(row["payload_json"]),
            occurred_at=row["occurred_at"],
            command_id=row["command_id"],
        )

    @staticmethod
    def _archive_entry_from_row(row: sqlite3.Row) -> CandidateArchiveEntry:
        return CandidateArchiveEntry(
            candidate_digest=row["candidate_digest"],
            semantic_fingerprint=row["semantic_fingerprint"],
            candidate_ref=row["candidate_ref"],
            first_context_ref=row["first_context_ref"],
            last_context_ref=row["last_context_ref"],
            first_proposal_ref=row["first_proposal_ref"],
            last_proposal_ref=row["last_proposal_ref"],
            status=row["status"],
            latest_receipt_ref=row["latest_receipt_ref"],
            rejection_reasons=tuple(json.loads(row["rejection_reasons_json"])),
            score_min=row["score_min"],
            gate_config_hash=row["gate_config_hash"],
            first_cycle_id=row["first_cycle_id"],
            last_cycle_id=row["last_cycle_id"],
            first_seed_id=row["first_seed_id"],
            last_seed_id=row["last_seed_id"],
            first_global_seq=row["first_global_seq"],
            last_global_seq=row["last_global_seq"],
            seen_count=row["seen_count"],
            latest_round=row["latest_round"],
            latest_parent_candidate_digest=row["latest_parent_candidate_digest"],
            source_layer=row["source_layer"],
        )

    def _load_archive_entry(
        self,
        conn: sqlite3.Connection,
        candidate_digest: str,
    ) -> CandidateArchiveEntry | None:
        row = conn.execute(
            "SELECT * FROM candidate_archive WHERE candidate_digest = ?",
            (candidate_digest,),
        ).fetchone()
        return self._archive_entry_from_row(row) if row is not None else None

    @staticmethod
    def _write_archive_entry(
        conn: sqlite3.Connection,
        entry: CandidateArchiveEntry,
    ) -> None:
        conn.execute(
            """
            INSERT INTO candidate_archive (
              candidate_digest, semantic_fingerprint, candidate_ref,
              first_context_ref, last_context_ref, first_proposal_ref, last_proposal_ref,
              status, latest_receipt_ref, rejection_reasons_json, score_min,
              gate_config_hash, first_cycle_id, last_cycle_id, first_seed_id, last_seed_id,
              first_global_seq, last_global_seq, seen_count, latest_round,
              latest_parent_candidate_digest, source_layer
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(candidate_digest) DO UPDATE SET
              semantic_fingerprint = excluded.semantic_fingerprint,
              candidate_ref = excluded.candidate_ref,
              first_context_ref = excluded.first_context_ref,
              last_context_ref = excluded.last_context_ref,
              first_proposal_ref = excluded.first_proposal_ref,
              last_proposal_ref = excluded.last_proposal_ref,
              status = excluded.status,
              latest_receipt_ref = excluded.latest_receipt_ref,
              rejection_reasons_json = excluded.rejection_reasons_json,
              score_min = excluded.score_min,
              gate_config_hash = excluded.gate_config_hash,
              first_cycle_id = excluded.first_cycle_id,
              last_cycle_id = excluded.last_cycle_id,
              first_seed_id = excluded.first_seed_id,
              last_seed_id = excluded.last_seed_id,
              first_global_seq = excluded.first_global_seq,
              last_global_seq = excluded.last_global_seq,
              seen_count = excluded.seen_count,
              latest_round = excluded.latest_round,
              latest_parent_candidate_digest = excluded.latest_parent_candidate_digest,
              source_layer = excluded.source_layer
            """,
            (
                entry.candidate_digest,
                entry.semantic_fingerprint,
                entry.candidate_ref,
                entry.first_context_ref,
                entry.last_context_ref,
                entry.first_proposal_ref,
                entry.last_proposal_ref,
                entry.status.value,
                entry.latest_receipt_ref,
                _canonical_json(list(entry.rejection_reasons)),
                entry.score_min,
                entry.gate_config_hash,
                entry.first_cycle_id,
                entry.last_cycle_id,
                entry.first_seed_id,
                entry.last_seed_id,
                entry.first_global_seq,
                entry.last_global_seq,
                entry.seen_count,
                entry.latest_round,
                entry.latest_parent_candidate_digest,
                entry.source_layer,
            ),
        )

    def _fault(self, stage: str) -> None:
        if self._fault_injector is not None:
            self._fault_injector(stage)


__all__ = [
    "PROJECTION_NAME",
    "STORE_SCHEMA_VERSION",
    "BlobRef",
    "CommitReceipt",
    "CorruptBlobError",
    "DurableStoreError",
    "FileCAS",
    "IdempotencyConflict",
    "MissingBlobError",
    "NewJournalEvent",
    "ProjectionStats",
    "SqliteEurekaStore",
    "StoredJournalEvent",
    "UnsupportedStoreVersion",
    "VersionConflict",
    "default_eureka_state_dir",
]
