"""Portable persistence-identity limits shared by SQLite and PostgreSQL.

# KG: apt-tpa-legion-engine-canon-2026-06-12
# Design: SYMPOSIUM/THEORY/APT/vnext/APT_ENGINE_FSM_DESIGN_2026-07-13.md §12.1
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from engine.apt_runtime.adapters.postgres_store import PostgresEventStore
from engine.apt_runtime.adapters.sqlite_store import SqliteEventStore
from engine.apt_runtime.domain.commands import CommandSchemaError
from engine.apt_runtime.domain.events import EventSchemaError, EventType
from engine.apt_runtime.ports.event_store import PersistenceSchemaError
from engine.apt_runtime.tests.test_sqlite_store import event, outbox, receipt


class _SqliteIoBomb:
    """Fail if an invalid public argument reaches the SQLite connection."""

    in_transaction = False

    def execute(self, *_args: object, **_kwargs: object) -> None:
        raise AssertionError("invalid persistence identity reached SQLite I/O")


def _adapter(backend: str, request: pytest.FixtureRequest, tmp_path: Path):
    if backend == "sqlite":
        adapter = SqliteEventStore(tmp_path / "identity-limits.sqlite3")
    else:
        sandbox = request.getfixturevalue("postgres_sandbox")
        adapter = PostgresEventStore(sandbox.dsn)
    adapter.init_schema()
    return adapter


def _block_io(adapter: object) -> tuple[str, object]:
    if isinstance(adapter, SqliteEventStore):
        attribute = "_connection"
        replacement: object = _SqliteIoBomb()
    else:
        attribute = "_connect_factory"

        def replacement(*_args: object, **_kwargs: object) -> None:
            raise AssertionError("invalid persistence identity reached PostgreSQL I/O")

    original = getattr(adapter, attribute)
    setattr(adapter, attribute, replacement)
    return attribute, original


@pytest.mark.parametrize("backend", ["sqlite", "postgres"])
@pytest.mark.parametrize("operation", ["load_stream", "load_receipt", "append_stream"])
def test_persistence_identities_reject_nul_before_backend_io(
    backend: str,
    operation: str,
    request: pytest.FixtureRequest,
    tmp_path: Path,
) -> None:
    adapter = _adapter(backend, request, tmp_path)
    attribute, original = _block_io(adapter)
    try:
        with pytest.raises(PersistenceSchemaError, match=r"U\+0000"):
            if operation == "load_stream":
                adapter.load("cycle-\x00")
            elif operation == "load_receipt":
                adapter.load_command_receipt("command-\x00")
            else:
                adapter.append("cycle-\x00", 0, [], [], receipt("command-nul"))
    finally:
        setattr(adapter, attribute, original)
        adapter.close()


@pytest.mark.parametrize("backend", ["sqlite", "postgres"])
@pytest.mark.parametrize("operation", ["load_after_version", "append_expected_version"])
def test_persistence_versions_reject_signed_64_bit_overflow_before_backend_io(
    backend: str,
    operation: str,
    request: pytest.FixtureRequest,
    tmp_path: Path,
) -> None:
    adapter = _adapter(backend, request, tmp_path)
    overflow = 2**63
    draft = receipt("command-overflow")
    attribute, original = _block_io(adapter)
    try:
        with pytest.raises(PersistenceSchemaError, match="signed 64-bit"):
            if operation == "load_after_version":
                adapter.load("cycle-1", after_version=overflow)
            else:
                adapter.append("cycle-1", overflow, [], [], draft)
    finally:
        setattr(adapter, attribute, original)
        adapter.close()


@pytest.mark.parametrize("backend", ["sqlite", "postgres"])
@pytest.mark.parametrize("mismatch", ["stream", "expected_version"])
def test_no_event_receipt_identity_must_match_append_arguments(
    backend: str,
    mismatch: str,
    request: pytest.FixtureRequest,
    tmp_path: Path,
) -> None:
    adapter = _adapter(backend, request, tmp_path)
    draft = receipt(
        f"command-{backend}-{mismatch}",
        expected_version=1 if mismatch == "expected_version" else 0,
    )
    stream_id = "cycle-other" if mismatch == "stream" else "cycle-1"
    try:
        with pytest.raises(PersistenceSchemaError, match=mismatch):
            adapter.append(stream_id, 0, [], [], draft)
        assert adapter.load_command_receipt(draft.command_id) is None
    finally:
        adapter.close()


def test_persisted_domain_identities_and_integers_fit_both_backends() -> None:
    overflow = 2**63
    with pytest.raises(CommandSchemaError, match="signed 64-bit"):
        receipt("command-version-overflow", expected_version=overflow)
    with pytest.raises(CommandSchemaError, match=r"U\+0000"):
        receipt("command-\x00")
    with pytest.raises(EventSchemaError, match=r"U\+0000"):
        event(1, "command-\x00")
    queued = event(
        1,
        "command-generation-overflow",
        event_type=EventType.EFFECT_QUEUED,
        effect_id="effect-generation-overflow",
    )
    with pytest.raises(EventSchemaError, match="signed 64-bit"):
        replace(queued, generation=overflow)
    with pytest.raises(PersistenceSchemaError, match=r"U\+0000"):
        outbox("command-\x00")
