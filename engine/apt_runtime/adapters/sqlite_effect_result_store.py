"""Restart-durable content-addressed SQLite effect-result storage."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from collections.abc import Mapping
from pathlib import Path

from engine.apt_runtime.domain.canonical import (
    CanonicalValue,
    MAX_SIGNED_64,
    as_mapping,
    canonical_json_bytes,
    canonical_sha256,
    deep_freeze,
    normalize_text,
)
from engine.apt_runtime.ports.effects import StoredEffectResult


_RESULT_SCHEMA_VERSION = 1
_RESULT_SCHEMA = """
CREATE TABLE IF NOT EXISTS effect_result_store_schema (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    schema_version INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS effect_result_store_results (
    result_ref TEXT PRIMARY KEY,
    cycle_id TEXT NOT NULL,
    effect_id TEXT NOT NULL,
    attempt INTEGER NOT NULL CHECK (
        attempt >= 1 AND attempt <= 9223372036854775807
    ),
    result_hash TEXT NOT NULL CHECK (
        length(result_hash) = 64 AND result_hash NOT GLOB '*[^0-9a-f]*'
    ),
    result_json BLOB NOT NULL CHECK (typeof(result_json) = 'blob'),
    UNIQUE (cycle_id, effect_id, attempt)
);
"""
_RESULT_TABLES = ("effect_result_store_schema", "effect_result_store_results")
_SELECT_RESULT = (
    "SELECT result_ref, cycle_id, effect_id, attempt, result_hash, result_json "
    "FROM effect_result_store_results "
)


class EffectResultStoreError(RuntimeError):
    """A durable result could not be written or verified safely."""


class EffectResultConflict(EffectResultStoreError):
    """One execution identity was already bound to different result bytes."""


class EffectResultStoreCorruption(EffectResultStoreError):
    """The physical schema or a persisted result violates the store contract."""


def _text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")
    normalized = normalize_text(value)
    if "\x00" in normalized:
        raise ValueError(f"{name} cannot contain U+0000")
    return normalized


def _attempt(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= MAX_SIGNED_64:
        raise ValueError("attempt must be a signed 64-bit positive integer")
    return value


def _ddl_signature(connection: sqlite3.Connection) -> dict[tuple[str, str], str]:
    placeholders = ", ".join("?" for _ in _RESULT_TABLES)
    rows = connection.execute(
        "SELECT type, name, sql FROM sqlite_master "
        f"WHERE (name IN ({placeholders}) OR tbl_name IN ({placeholders})) "
        "AND name NOT LIKE 'sqlite_%' "
        "AND type IN ('table', 'index', 'trigger', 'view')",
        (*_RESULT_TABLES, *_RESULT_TABLES),
    ).fetchall()
    return {(str(row[0]), str(row[1])): "".join(str(row[2] or "").split()).lower() for row in rows}


def _validate_schema_signature(connection: sqlite3.Connection) -> None:
    reference = sqlite3.connect(":memory:")
    try:
        reference.executescript(_RESULT_SCHEMA)
        expected = _ddl_signature(reference)
    finally:
        reference.close()
    if _ddl_signature(connection) != expected:
        raise EffectResultStoreCorruption(
            "SQLite effect-result schema DDL differs from canonical result-store v1"
        )


def _stored_identity(
    cycle_id: str, effect_id: str, attempt: int, result_hash: str
) -> StoredEffectResult:
    identity_hash = canonical_sha256(
        {"attempt": attempt, "cycle_id": cycle_id, "effect_id": effect_id}
    )
    return StoredEffectResult(f"sqlite-effect-result://{identity_hash}/{result_hash}", result_hash)


def _canonical_result_bytes(value: object) -> bytes:
    if not isinstance(value, Mapping):
        raise ValueError("result must be a canonical JSON mapping")
    return canonical_json_bytes(value)


def _decode_canonical_result(result_json: bytes) -> Mapping[str, CanonicalValue]:
    def reject_nonfinite(value: str) -> object:
        raise ValueError(f"non-finite JSON constant {value!r} is not canonical")

    try:
        document = json.loads(
            result_json.decode("utf-8"),
            parse_constant=reject_nonfinite,
        )
        if not isinstance(document, dict):
            raise ValueError("result JSON must decode to a mapping")
        frozen = as_mapping(deep_freeze(document))
        if canonical_json_bytes(frozen) != result_json:
            raise ValueError("result bytes are not apt-canonical-json-v1")
        return frozen
    except (TypeError, UnicodeError, ValueError, RecursionError) as exc:
        raise EffectResultStoreCorruption(f"stored result bytes are not canonical: {exc}") from exc


def _validated_row(row: sqlite3.Row) -> tuple[StoredEffectResult, bytes]:
    try:
        cycle_id = _text("stored cycle_id", row["cycle_id"])
        effect_id = _text("stored effect_id", row["effect_id"])
        attempt = _attempt(row["attempt"])
        result_ref = _text("stored result_ref", row["result_ref"])
        result_hash = _text("stored result_hash", row["result_hash"])
    except (IndexError, ValueError) as exc:
        raise EffectResultStoreCorruption(f"stored result identity is malformed: {exc}") from exc
    if cycle_id != row["cycle_id"] or effect_id != row["effect_id"]:
        raise EffectResultStoreCorruption("stored result identity is not NFC-normalized")
    if len(result_hash) != 64 or any(
        character not in "0123456789abcdef" for character in result_hash
    ):
        raise EffectResultStoreCorruption("stored result_hash is not lowercase SHA-256 hex")
    raw_result = row["result_json"]
    if not isinstance(raw_result, (bytes, memoryview)):
        raise EffectResultStoreCorruption("stored result_json does not have SQLite BLOB type")
    result_json = bytes(raw_result)
    _decode_canonical_result(result_json)
    if hashlib.sha256(result_json).hexdigest() != result_hash:
        raise EffectResultStoreCorruption("stored result_hash does not match result_json")
    expected = _stored_identity(cycle_id, effect_id, attempt, result_hash)
    if result_ref != expected.result_ref:
        raise EffectResultStoreCorruption(
            "stored result_ref does not match execution identity and result hash"
        )
    return expected, result_json


class SqliteEffectResultStore:
    """Persist canonical result bytes before an ``EffectSucceeded`` fact."""

    def __init__(
        self,
        database: str | Path,
        *,
        busy_timeout_ms: int = 5_000,
    ) -> None:
        if (
            isinstance(busy_timeout_ms, bool)
            or not isinstance(busy_timeout_ms, int)
            or busy_timeout_ms < 1
        ):
            raise ValueError("busy_timeout_ms must be a positive integer")
        self._database = str(database)
        self._lock = threading.RLock()
        self._closed = False
        try:
            self._connection = sqlite3.connect(
                self._database,
                isolation_level=None,
                timeout=busy_timeout_ms / 1_000,
                check_same_thread=False,
            )
            self._connection.row_factory = sqlite3.Row
            self._connection.execute(f"PRAGMA busy_timeout = {busy_timeout_ms}")
            if self._database != ":memory:":
                self._connection.execute("PRAGMA journal_mode = WAL")
            self._connection.execute("PRAGMA synchronous = FULL")
        except sqlite3.DatabaseError as exc:
            connection = getattr(self, "_connection", None)
            if connection is not None:
                connection.close()
            self._closed = True
            raise EffectResultStoreError(
                f"failed to open SQLite effect-result store: {exc}"
            ) from exc

    def init_schema(self) -> None:
        """Create result-store v1 atomically and reject incompatible DDL."""

        with self._lock:
            self._require_open()
            try:
                self._connection.executescript(f"BEGIN IMMEDIATE;\n{_RESULT_SCHEMA}")
                _validate_schema_signature(self._connection)
                self._connection.execute(
                    "INSERT OR IGNORE INTO effect_result_store_schema"
                    "(singleton, schema_version) VALUES (1, ?)",
                    (_RESULT_SCHEMA_VERSION,),
                )
                rows = self._connection.execute(
                    "SELECT singleton, schema_version FROM effect_result_store_schema"
                ).fetchall()
                if len(rows) != 1 or tuple(rows[0]) != (1, _RESULT_SCHEMA_VERSION):
                    raise EffectResultStoreCorruption(
                        "SQLite effect-result schema version marker is incompatible"
                    )
                self._connection.execute("COMMIT")
            except EffectResultStoreError:
                self._rollback()
                raise
            except sqlite3.DatabaseError as exc:
                self._rollback()
                raise EffectResultStoreError(
                    f"failed to initialize SQLite effect-result schema: {exc}"
                ) from exc
            except BaseException:
                self._rollback()
                raise

    def persist(
        self,
        cycle_id: str,
        effect_id: str,
        attempt: int,
        result: Mapping[str, CanonicalValue],
    ) -> StoredEffectResult:
        cycle_id = _text("cycle_id", cycle_id)
        effect_id = _text("effect_id", effect_id)
        attempt = _attempt(attempt)
        result_json = _canonical_result_bytes(result)
        result_hash = hashlib.sha256(result_json).hexdigest()
        stored = _stored_identity(cycle_id, effect_id, attempt, result_hash)
        with self._lock:
            self._require_open()
            try:
                self._connection.execute("BEGIN IMMEDIATE")
                row = self._connection.execute(
                    _SELECT_RESULT + "WHERE cycle_id = ? AND effect_id = ? AND attempt = ?",
                    (cycle_id, effect_id, attempt),
                ).fetchone()
                if row is not None:
                    existing, existing_json = _validated_row(row)
                    if existing != stored or existing_json != result_json:
                        raise EffectResultConflict(
                            "execution identity is already bound to a different result"
                        )
                    self._connection.execute("COMMIT")
                    return existing

                ref_row = self._connection.execute(
                    _SELECT_RESULT + "WHERE result_ref = ?",
                    (stored.result_ref,),
                ).fetchone()
                if ref_row is not None:
                    _validated_row(ref_row)
                    raise EffectResultStoreCorruption(
                        "result_ref is already bound to a different execution identity"
                    )

                self._connection.execute(
                    "INSERT INTO effect_result_store_results "
                    "(result_ref, cycle_id, effect_id, attempt, result_hash, result_json) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        stored.result_ref,
                        cycle_id,
                        effect_id,
                        attempt,
                        stored.result_hash,
                        result_json,
                    ),
                )
                persisted_row = self._connection.execute(
                    _SELECT_RESULT + "WHERE result_ref = ?",
                    (stored.result_ref,),
                ).fetchone()
                if persisted_row is None or _validated_row(persisted_row) != (
                    stored,
                    result_json,
                ):
                    raise EffectResultStoreCorruption(
                        "persisted effect result failed its read-after-write audit"
                    )
                self._connection.execute("COMMIT")
            except EffectResultStoreError:
                self._rollback()
                raise
            except sqlite3.DatabaseError as exc:
                self._rollback()
                raise EffectResultStoreError(
                    f"failed to persist SQLite effect result: {exc}"
                ) from exc
            except BaseException:
                self._rollback()
                raise
        return stored

    def verify(self, stored: StoredEffectResult) -> bool:
        if not isinstance(stored, StoredEffectResult):
            return False
        with self._lock:
            self._require_open()
            try:
                row = self._connection.execute(
                    _SELECT_RESULT + "WHERE result_ref = ?",
                    (stored.result_ref,),
                ).fetchone()
            except sqlite3.DatabaseError as exc:
                raise EffectResultStoreError(
                    f"failed to verify SQLite effect result: {exc}"
                ) from exc
        if row is None:
            return False
        try:
            actual, _ = _validated_row(row)
        except EffectResultStoreCorruption:
            return False
        return actual == stored

    def load(self, stored: StoredEffectResult) -> Mapping[str, CanonicalValue] | None:
        """Return a verified immutable canonical result, or ``None`` if absent/tampered."""

        if not isinstance(stored, StoredEffectResult):
            return None
        with self._lock:
            self._require_open()
            try:
                row = self._connection.execute(
                    _SELECT_RESULT + "WHERE result_ref = ?",
                    (stored.result_ref,),
                ).fetchone()
            except sqlite3.DatabaseError as exc:
                raise EffectResultStoreError(f"failed to load SQLite effect result: {exc}") from exc
        if row is None:
            return None
        try:
            actual, result_json = _validated_row(row)
            if actual != stored:
                return None
            return _decode_canonical_result(result_json)
        except EffectResultStoreCorruption:
            return None

    def close(self) -> None:
        """Idempotently close the adapter-owned connection."""

        with self._lock:
            if self._closed:
                return
            try:
                self._connection.close()
            except sqlite3.DatabaseError as exc:
                raise EffectResultStoreError(
                    f"failed to close SQLite effect-result store: {exc}"
                ) from exc
            self._closed = True

    def _require_open(self) -> None:
        if self._closed:
            raise EffectResultStoreError("SQLite effect-result store is closed")

    def _rollback(self) -> None:
        try:
            if not self._closed and self._connection.in_transaction:
                self._connection.execute("ROLLBACK")
        except sqlite3.DatabaseError:
            pass


__all__ = [
    "EffectResultConflict",
    "EffectResultStoreCorruption",
    "EffectResultStoreError",
    "SqliteEffectResultStore",
]
