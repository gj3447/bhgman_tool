"""Exact SQLite schema for the Slice 2 operational effect queue.

# KG: apt-tpa-legion-engine-canon-2026-06-12
# Design: ADRs/apt-vnext-slice2-effect-runtime-2026-07-14.md
"""

from __future__ import annotations

import sqlite3


QUEUE_SCHEMA_VERSION = 2

QUEUE_SCHEMA = """
CREATE TABLE IF NOT EXISTS effect_runtime_schema (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    schema_version INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS effect_runtime_leases (
    lease_token TEXT PRIMARY KEY,
    outbox_id TEXT NOT NULL,
    stream_id TEXT NOT NULL,
    effect_id TEXT NOT NULL,
    lease_epoch INTEGER NOT NULL CHECK (lease_epoch >= 1),
    lease_owner TEXT NOT NULL,
    status TEXT NOT NULL CHECK (
        status IN (
            'RESERVED', 'ACTIVE', 'RUNNING', 'RECONCILING',
            'SUCCEEDED', 'FAILED', 'CANCELLED', 'ABANDONED'
        )
    ),
    claimed_at TEXT NOT NULL,
    activated_at TEXT,
    heartbeat_at TEXT NOT NULL,
    lease_expiry TEXT NOT NULL,
    attempt INTEGER NOT NULL CHECK (attempt >= 0),
    claims_json BLOB NOT NULL,
    claims_hash TEXT NOT NULL,
    budget_json BLOB NOT NULL,
    budget_hash TEXT NOT NULL,
    grant_ref TEXT NOT NULL,
    grant_hash TEXT NOT NULL CHECK (
        length(grant_hash) = 64 AND grant_hash NOT GLOB '*[^0-9a-f]*'
    ),
    config_version TEXT NOT NULL,
    authorization_ref TEXT NOT NULL,
    authorization_hash TEXT NOT NULL CHECK (
        length(authorization_hash) = 64
        AND authorization_hash NOT GLOB '*[^0-9a-f]*'
    ),
    probe_generation INTEGER NOT NULL CHECK (probe_generation >= 0),
    probe_token TEXT,
    probe_state TEXT CHECK (probe_state IN ('ACTIVE', 'CONCLUDED')),
    probe_acquired_at TEXT,
    probe_expires_at TEXT,
    probe_concluded_at TEXT,
    probe_conclusion_json BLOB,
    probe_conclusion_hash TEXT,
    reconciliation_ref TEXT,
    reason TEXT,
    completed_at TEXT,
    UNIQUE (outbox_id, lease_epoch),
    FOREIGN KEY (outbox_id) REFERENCES apt_outbox(outbox_id)
);

CREATE INDEX IF NOT EXISTS effect_runtime_leases_outbox_epoch
ON effect_runtime_leases(outbox_id, lease_epoch DESC);

CREATE INDEX IF NOT EXISTS effect_runtime_leases_recovery
ON effect_runtime_leases(status, lease_expiry, heartbeat_at);

CREATE TABLE IF NOT EXISTS effect_runtime_resource_claims (
    lease_token TEXT NOT NULL,
    resource_key TEXT NOT NULL,
    access TEXT NOT NULL CHECK (access IN ('SHARED_READ', 'EXCLUSIVE_WRITE')),
    PRIMARY KEY (lease_token, resource_key),
    FOREIGN KEY (lease_token) REFERENCES effect_runtime_leases(lease_token)
);

CREATE INDEX IF NOT EXISTS effect_runtime_claims_resource
ON effect_runtime_resource_claims(resource_key, access);

CREATE TABLE IF NOT EXISTS effect_runtime_usage (
    outbox_id TEXT PRIMARY KEY,
    usage_json BLOB NOT NULL,
    usage_hash TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (outbox_id) REFERENCES apt_outbox(outbox_id)
);

CREATE TABLE IF NOT EXISTS effect_runtime_journal (
    journal_id INTEGER PRIMARY KEY AUTOINCREMENT,
    lease_token TEXT NOT NULL,
    journal_position INTEGER NOT NULL CHECK (journal_position >= 1),
    action TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    detail_json BLOB NOT NULL,
    detail_hash TEXT NOT NULL,
    UNIQUE (lease_token, journal_position),
    FOREIGN KEY (lease_token) REFERENCES effect_runtime_leases(lease_token)
);

CREATE INDEX IF NOT EXISTS effect_runtime_journal_lease
ON effect_runtime_journal(lease_token, journal_id);

CREATE TABLE IF NOT EXISTS effect_runtime_journal_heads (
    lease_token TEXT NOT NULL,
    head_position INTEGER NOT NULL CHECK (head_position >= 1),
    head_hash TEXT NOT NULL CHECK (
        length(head_hash) = 64 AND head_hash NOT GLOB '*[^0-9a-f]*'
    ),
    PRIMARY KEY (lease_token, head_position),
    FOREIGN KEY (lease_token) REFERENCES effect_runtime_leases(lease_token)
);

CREATE TRIGGER IF NOT EXISTS effect_runtime_journal_heads_no_update
BEFORE UPDATE ON effect_runtime_journal_heads
BEGIN
    SELECT RAISE(ABORT, 'effect-runtime journal checkpoints are append-only');
END;

CREATE TRIGGER IF NOT EXISTS effect_runtime_journal_heads_no_delete
BEFORE DELETE ON effect_runtime_journal_heads
BEGIN
    SELECT RAISE(ABORT, 'effect-runtime journal checkpoints are append-only');
END;
"""


class EffectQueueSchemaError(ValueError):
    """The physical queue schema differs from its declared version."""


def _ddl_signature(connection: sqlite3.Connection) -> dict[tuple[str, str], str]:
    rows = connection.execute(
        "SELECT type, name, sql FROM sqlite_master "
        "WHERE (name LIKE 'effect_runtime_%' OR tbl_name LIKE 'effect_runtime_%') "
        "AND name NOT LIKE 'sqlite_%' "
        "AND type IN ('table', 'index', 'trigger', 'view')"
    ).fetchall()
    return {(row[0], row[1]): "".join((row[2] or "").split()).lower() for row in rows}


def validate_effect_queue_schema(connection: sqlite3.Connection) -> None:
    """Reject extra, missing, or altered queue tables, indexes, and constraints."""

    reference = sqlite3.connect(":memory:")
    try:
        reference.executescript(QUEUE_SCHEMA)
        expected = _ddl_signature(reference)
    finally:
        reference.close()
    if _ddl_signature(connection) != expected:
        raise EffectQueueSchemaError(
            "SQLite effect-runtime schema DDL differs from canonical queue v2"
        )


__all__ = [
    "EffectQueueSchemaError",
    "QUEUE_SCHEMA",
    "QUEUE_SCHEMA_VERSION",
    "validate_effect_queue_schema",
]
