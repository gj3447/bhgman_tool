from __future__ import annotations

import hashlib
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from engine.apt_runtime.adapters.sqlite_effect_result_store import (
    EffectResultConflict,
    EffectResultStoreCorruption,
    EffectResultStoreError,
    SqliteEffectResultStore,
)
from engine.apt_runtime.adapters.sqlite_effect_queue import SqliteEffectQueue
from engine.apt_runtime.adapters.sqlite_store import SqliteEventStore
from engine.apt_runtime.domain.canonical import canonical_sha256
from engine.apt_runtime.ports.effects import StoredEffectResult


def test_result_is_idempotent_and_verifiable_after_reopen(tmp_path: Path) -> None:
    database = tmp_path / "result-store.sqlite3"
    first = SqliteEffectResultStore(database)
    first.init_schema()
    stored = first.persist("cycle-1", "effect-1", 1, {"artifact": "one"})
    assert first.persist("cycle-1", "effect-1", 1, {"artifact": "one"}) == stored
    first.close()

    reopened = SqliteEffectResultStore(database)
    reopened.init_schema()
    try:
        assert reopened.verify(stored)
        assert reopened.load(stored) == {"artifact": "one"}
    finally:
        reopened.close()


def test_result_identity_cannot_be_rebound(tmp_path: Path) -> None:
    store = SqliteEffectResultStore(tmp_path / "conflict.sqlite3")
    store.init_schema()
    try:
        stored = store.persist("cycle-1", "effect-1", 1, {"artifact": "one"})
        with pytest.raises(EffectResultConflict, match="different result"):
            store.persist("cycle-1", "effect-1", 1, {"artifact": "two"})
        assert store.verify(stored)
        assert store.load(stored) == {"artifact": "one"}
    finally:
        store.close()


def test_blob_tamper_fails_verification(tmp_path: Path) -> None:
    database = tmp_path / "tamper.sqlite3"
    store = SqliteEffectResultStore(database)
    store.init_schema()
    stored = store.persist("cycle-1", "effect-1", 1, {"artifact": "one"})
    store.close()

    connection = sqlite3.connect(database)
    connection.execute(
        "UPDATE effect_result_store_results SET result_json = ? WHERE result_ref = ?",
        (b'{"artifact":"tampered"}', stored.result_ref),
    )
    connection.commit()
    connection.close()

    reopened = SqliteEffectResultStore(database)
    try:
        assert not reopened.verify(stored)
        assert reopened.load(stored) is None
    finally:
        reopened.close()


def test_rehashed_noncanonical_json_still_fails_verification(tmp_path: Path) -> None:
    database = tmp_path / "noncanonical.sqlite3"
    store = SqliteEffectResultStore(database)
    store.init_schema()
    store.persist("cycle-1", "effect-1", 1, {"artifact": "one"})
    store.close()

    noncanonical = b'{ "artifact": "one" }'
    result_hash = hashlib.sha256(noncanonical).hexdigest()
    identity_hash = canonical_sha256({"attempt": 1, "cycle_id": "cycle-1", "effect_id": "effect-1"})
    tampered = StoredEffectResult(
        f"sqlite-effect-result://{identity_hash}/{result_hash}", result_hash
    )
    connection = sqlite3.connect(database)
    connection.execute(
        "UPDATE effect_result_store_results SET result_ref = ?, result_hash = ?, result_json = ?",
        (tampered.result_ref, tampered.result_hash, noncanonical),
    )
    connection.commit()
    connection.close()

    reopened = SqliteEffectResultStore(database)
    try:
        assert not reopened.verify(tampered)
        assert reopened.load(tampered) is None
    finally:
        reopened.close()


def test_persist_rejects_a_corrupt_existing_identity(tmp_path: Path) -> None:
    database = tmp_path / "persist-corrupt.sqlite3"
    store = SqliteEffectResultStore(database)
    store.init_schema()
    store.persist("cycle-1", "effect-1", 1, {"artifact": "one"})
    store.close()

    connection = sqlite3.connect(database)
    connection.execute(
        "UPDATE effect_result_store_results SET result_json = ?",
        (b'{"artifact":"tampered"}',),
    )
    connection.commit()
    connection.close()

    reopened = SqliteEffectResultStore(database)
    try:
        with pytest.raises(EffectResultStoreCorruption, match="result_hash"):
            reopened.persist("cycle-1", "effect-1", 1, {"artifact": "one"})
    finally:
        reopened.close()


def test_schema_init_rejects_an_incompatible_existing_table(tmp_path: Path) -> None:
    database = tmp_path / "wrong-schema.sqlite3"
    connection = sqlite3.connect(database)
    connection.execute("CREATE TABLE effect_result_store_results (result_ref TEXT PRIMARY KEY)")
    connection.commit()
    connection.close()

    store = SqliteEffectResultStore(database)
    try:
        with pytest.raises(EffectResultStoreCorruption, match="schema DDL"):
            store.init_schema()
    finally:
        store.close()


def test_schema_init_rejects_extra_result_store_ddl(tmp_path: Path) -> None:
    database = tmp_path / "extra-schema.sqlite3"
    store = SqliteEffectResultStore(database)
    store.init_schema()
    store.close()

    connection = sqlite3.connect(database)
    connection.execute(
        "CREATE INDEX unexpected_result_index ON effect_result_store_results(effect_id)"
    )
    connection.commit()
    connection.close()

    reopened = SqliteEffectResultStore(database)
    try:
        with pytest.raises(EffectResultStoreCorruption, match="schema DDL"):
            reopened.init_schema()
    finally:
        reopened.close()


def test_schema_init_rejects_an_incompatible_version_marker(tmp_path: Path) -> None:
    database = tmp_path / "wrong-version.sqlite3"
    store = SqliteEffectResultStore(database)
    store.init_schema()
    store.close()

    connection = sqlite3.connect(database)
    connection.execute(
        "UPDATE effect_result_store_schema SET schema_version = 99 WHERE singleton = 1"
    )
    connection.commit()
    connection.close()

    reopened = SqliteEffectResultStore(database)
    try:
        with pytest.raises(EffectResultStoreCorruption, match="version marker"):
            reopened.init_schema()
    finally:
        reopened.close()


def test_concurrent_connections_idempotently_bind_one_result(tmp_path: Path) -> None:
    database = tmp_path / "concurrent.sqlite3"
    bootstrap = SqliteEffectResultStore(database)
    bootstrap.init_schema()
    bootstrap.close()
    first = SqliteEffectResultStore(database)
    second = SqliteEffectResultStore(database)
    barrier = threading.Barrier(2)

    def persist(store: SqliteEffectResultStore) -> StoredEffectResult:
        barrier.wait()
        return store.persist("cycle-1", "effect-1", 1, {"artifact": "one"})

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = (executor.submit(persist, first), executor.submit(persist, second))
            stored = tuple(future.result() for future in futures)
        assert stored[0] == stored[1]
        assert first.verify(stored[0])
        connection = sqlite3.connect(database)
        try:
            assert connection.execute(
                "SELECT count(*) FROM effect_result_store_results"
            ).fetchone() == (1,)
        finally:
            connection.close()
    finally:
        first.close()
        second.close()


def test_result_schema_can_restart_in_the_shared_runtime_database(tmp_path: Path) -> None:
    database = tmp_path / "shared-runtime.sqlite3"
    event_store = SqliteEventStore(database)
    queue = SqliteEffectQueue(database)
    result_store = SqliteEffectResultStore(database)
    try:
        event_store.init_schema()
        queue.init_schema()
        result_store.init_schema()
        stored = result_store.persist("cycle-1", "effect-1", 1, {"artifact": "one"})
    finally:
        result_store.close()
        queue.close()
        event_store.close()

    reopened_event_store = SqliteEventStore(database)
    reopened_queue = SqliteEffectQueue(database)
    reopened_result_store = SqliteEffectResultStore(database)
    try:
        reopened_event_store.init_schema()
        reopened_queue.init_schema()
        reopened_result_store.init_schema()
        assert reopened_result_store.load(stored) == {"artifact": "one"}
    finally:
        reopened_result_store.close()
        reopened_queue.close()
        reopened_event_store.close()


def test_loaded_result_is_deeply_immutable_and_canonical(tmp_path: Path) -> None:
    store = SqliteEffectResultStore(tmp_path / "load.sqlite3")
    store.init_schema()
    try:
        stored = store.persist(
            "cycle-caf\u00e9",
            "effect-caf\u00e9",
            1,
            {"artifact": "caf\u00e9", "nested": ("one",)},
        )
        assert (
            store.persist(
                "cycle-cafe\u0301",
                "effect-cafe\u0301",
                1,
                {"artifact": "cafe\u0301", "nested": ("one",)},
            )
            == stored
        )
        loaded = store.load(stored)
        assert loaded == {"artifact": "caf\u00e9", "nested": ("one",)}
        assert loaded is not None
        with pytest.raises(TypeError):
            loaded["artifact"] = "changed"  # type: ignore[index]
    finally:
        store.close()


def test_result_must_be_a_canonical_mapping(tmp_path: Path) -> None:
    store = SqliteEffectResultStore(tmp_path / "mapping.sqlite3")
    store.init_schema()
    try:
        with pytest.raises(ValueError, match="mapping"):
            store.persist("cycle-1", "effect-1", 1, ["not-a-mapping"])  # type: ignore[arg-type]
    finally:
        store.close()


def test_close_is_idempotent_and_operations_fail_cleanly(tmp_path: Path) -> None:
    store = SqliteEffectResultStore(tmp_path / "closed.sqlite3")
    store.init_schema()
    stored = store.persist("cycle-1", "effect-1", 1, {"artifact": "one"})
    store.close()
    store.close()

    with pytest.raises(EffectResultStoreError, match="closed"):
        store.init_schema()
    with pytest.raises(EffectResultStoreError, match="closed"):
        store.persist("cycle-2", "effect-2", 1, {"artifact": "two"})
    with pytest.raises(EffectResultStoreError, match="closed"):
        store.verify(stored)
    with pytest.raises(EffectResultStoreError, match="closed"):
        store.load(stored)
