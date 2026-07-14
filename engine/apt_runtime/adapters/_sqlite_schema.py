"""Private SQLite v1 schema for the APT durable event store.

# KG: apt-tpa-legion-engine-canon-2026-06-12
# KG: APT_SCW_TDAD_canonical
"""

from __future__ import annotations

import sqlite3

SCHEMA_VERSION = 1

# ``CREATE TABLE IF NOT EXISTS`` is not a compatibility check.  These
# signatures are verified after initialization so a database cannot claim v1
# while silently exposing different columns, keys, indexes, or foreign keys.
TABLE_SIGNATURES = {
    "apt_store_schema": (
        ("singleton", "INTEGER", 0, 1),
        ("schema_version", "INTEGER", 1, 0),
    ),
    "apt_stream_heads": (
        ("stream_id", "TEXT", 0, 1),
        ("current_version", "INTEGER", 1, 0),
        ("fsm_spec_hash", "TEXT", 1, 0),
        ("config_version", "TEXT", 1, 0),
    ),
    "apt_events": (
        ("event_id", "TEXT", 0, 1),
        ("stream_id", "TEXT", 1, 0),
        ("stream_version", "INTEGER", 1, 0),
        ("event_type", "TEXT", 1, 0),
        ("schema_version", "TEXT", 1, 0),
        ("fsm_spec_hash", "TEXT", 1, 0),
        ("cycle_id", "TEXT", 1, 0),
        ("work_item_id", "TEXT", 0, 0),
        ("effect_id", "TEXT", 0, 0),
        ("generation", "INTEGER", 0, 0),
        ("actor", "TEXT", 1, 0),
        ("correlation_id", "TEXT", 1, 0),
        ("causation_id", "TEXT", 1, 0),
        ("command_id", "TEXT", 1, 0),
        ("config_version", "TEXT", 1, 0),
        ("payload_json", "BLOB", 1, 0),
        ("payload_hash", "TEXT", 1, 0),
        ("created_at", "TEXT", 1, 0),
    ),
    "apt_command_receipts": (
        ("command_id", "TEXT", 0, 1),
        ("stream_id", "TEXT", 1, 0),
        ("command_hash", "TEXT", 1, 0),
        ("committed_version", "INTEGER", 1, 0),
        ("event_ids_json", "BLOB", 1, 0),
        ("outbox_ids_json", "BLOB", 1, 0),
        ("response_json", "BLOB", 1, 0),
        ("response_hash", "TEXT", 1, 0),
        ("created_at", "TEXT", 1, 0),
    ),
    "apt_outbox": (
        ("outbox_id", "TEXT", 0, 1),
        ("stream_id", "TEXT", 1, 0),
        ("effect_id", "TEXT", 1, 0),
        ("command_id", "TEXT", 1, 0),
        ("payload_json", "BLOB", 1, 0),
        ("payload_hash", "TEXT", 1, 0),
        ("created_at", "TEXT", 1, 0),
    ),
    "apt_snapshots": (
        ("stream_id", "TEXT", 1, 1),
        ("stream_version", "INTEGER", 1, 2),
        ("fsm_spec_hash", "TEXT", 1, 0),
        ("codec_version", "TEXT", 1, 0),
        ("state_hash", "TEXT", 1, 0),
        ("state_blob", "BLOB", 1, 0),
        ("created_at", "TEXT", 1, 0),
    ),
}

INDEX_SIGNATURES = {
    "apt_store_schema": (),
    "apt_stream_heads": ((1, "pk", ("stream_id",)),),
    "apt_events": (
        (0, "c", ("stream_id", "stream_version")),
        (1, "pk", ("event_id",)),
        (1, "u", ("stream_id", "stream_version")),
    ),
    "apt_command_receipts": ((1, "pk", ("command_id",)),),
    "apt_outbox": (
        (0, "c", ("stream_id",)),
        (1, "pk", ("outbox_id",)),
        (1, "u", ("stream_id", "effect_id")),
    ),
    "apt_snapshots": ((1, "pk", ("stream_id", "stream_version")),),
}

FOREIGN_KEY_SIGNATURES = {
    "apt_store_schema": (),
    "apt_stream_heads": (),
    "apt_events": (("apt_stream_heads", "stream_id", "stream_id"),),
    "apt_command_receipts": (),
    "apt_outbox": (
        ("apt_command_receipts", "command_id", "command_id"),
        ("apt_stream_heads", "stream_id", "stream_id"),
    ),
    "apt_snapshots": (("apt_stream_heads", "stream_id", "stream_id"),),
}


class SchemaSignatureError(ValueError):
    """The physical SQLite schema does not match the declared schema version."""


def validate_schema_signature(connection: sqlite3.Connection) -> None:
    """Verify columns, indexes, and foreign keys without trusting the v1 marker."""

    reference = sqlite3.connect(":memory:")
    try:
        reference.executescript(SCHEMA)
        expected_ddl = _ddl_signature(reference)
    finally:
        reference.close()
    if _ddl_signature(connection) != expected_ddl:
        raise SchemaSignatureError("SQLite schema DDL signature differs from canonical v1")

    for table, expected_columns in TABLE_SIGNATURES.items():
        columns = connection.execute(f"PRAGMA table_info({table})").fetchall()
        actual_columns = tuple(
            (item["name"], item["type"].upper(), item["notnull"], item["pk"]) for item in columns
        )
        if actual_columns != expected_columns:
            raise SchemaSignatureError(f"SQLite schema signature differs for table {table!r}")

        actual_indexes: list[tuple[int, str, tuple[str, ...]]] = []
        for index in connection.execute(f"PRAGMA index_list({table})").fetchall():
            index_columns = connection.execute(f"PRAGMA index_info({index['name']})").fetchall()
            actual_indexes.append(
                (
                    index["unique"],
                    index["origin"],
                    tuple(item["name"] for item in index_columns),
                )
            )
        if sorted(actual_indexes) != sorted(INDEX_SIGNATURES[table]):
            raise SchemaSignatureError(f"SQLite index signature differs for table {table!r}")

        foreign_keys = connection.execute(f"PRAGMA foreign_key_list({table})").fetchall()
        actual_foreign_keys = sorted(
            (item["table"], item["from"], item["to"]) for item in foreign_keys
        )
        if actual_foreign_keys != sorted(FOREIGN_KEY_SIGNATURES[table]):
            raise SchemaSignatureError(f"SQLite foreign-key signature differs for table {table!r}")


def _ddl_signature(connection: sqlite3.Connection) -> dict[tuple[str, str], str]:
    rows = connection.execute(
        "SELECT type, name, sql FROM sqlite_master "
        "WHERE (name LIKE 'apt_%' OR tbl_name LIKE 'apt_%') "
        "AND name NOT LIKE 'sqlite_%' "
        "AND type IN ('table', 'index', 'trigger', 'view')"
    ).fetchall()
    return {(row[0], row[1]): "".join((row[2] or "").split()).lower() for row in rows}


SCHEMA = """
CREATE TABLE IF NOT EXISTS apt_store_schema (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    schema_version INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS apt_stream_heads (
    stream_id TEXT PRIMARY KEY,
    current_version INTEGER NOT NULL CHECK (current_version >= 0),
    fsm_spec_hash TEXT NOT NULL,
    config_version TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS apt_events (
    event_id TEXT PRIMARY KEY,
    stream_id TEXT NOT NULL,
    stream_version INTEGER NOT NULL CHECK (stream_version >= 1),
    event_type TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    fsm_spec_hash TEXT NOT NULL,
    cycle_id TEXT NOT NULL,
    work_item_id TEXT,
    effect_id TEXT,
    generation INTEGER,
    actor TEXT NOT NULL,
    correlation_id TEXT NOT NULL,
    causation_id TEXT NOT NULL,
    command_id TEXT NOT NULL,
    config_version TEXT NOT NULL,
    payload_json BLOB NOT NULL,
    payload_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (stream_id, stream_version),
    FOREIGN KEY (stream_id) REFERENCES apt_stream_heads(stream_id)
);

CREATE INDEX IF NOT EXISTS apt_events_stream_version
ON apt_events(stream_id, stream_version);

CREATE TABLE IF NOT EXISTS apt_command_receipts (
    command_id TEXT PRIMARY KEY,
    stream_id TEXT NOT NULL,
    command_hash TEXT NOT NULL,
    committed_version INTEGER NOT NULL CHECK (committed_version >= 0),
    event_ids_json BLOB NOT NULL,
    outbox_ids_json BLOB NOT NULL,
    response_json BLOB NOT NULL,
    response_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS apt_outbox (
    outbox_id TEXT PRIMARY KEY,
    stream_id TEXT NOT NULL,
    effect_id TEXT NOT NULL,
    command_id TEXT NOT NULL,
    payload_json BLOB NOT NULL,
    payload_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (stream_id, effect_id),
    FOREIGN KEY (stream_id) REFERENCES apt_stream_heads(stream_id),
    FOREIGN KEY (command_id) REFERENCES apt_command_receipts(command_id)
);

CREATE INDEX IF NOT EXISTS apt_outbox_stream
ON apt_outbox(stream_id);

CREATE TABLE IF NOT EXISTS apt_snapshots (
    stream_id TEXT NOT NULL,
    stream_version INTEGER NOT NULL CHECK (stream_version >= 1),
    fsm_spec_hash TEXT NOT NULL,
    codec_version TEXT NOT NULL,
    state_hash TEXT NOT NULL,
    state_blob BLOB NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (stream_id, stream_version),
    FOREIGN KEY (stream_id) REFERENCES apt_stream_heads(stream_id)
);
"""

INSERT_EVENT = (
    "INSERT INTO apt_events"
    "(event_id, stream_id, stream_version, event_type, schema_version, "
    "fsm_spec_hash, cycle_id, work_item_id, effect_id, generation, actor, "
    "correlation_id, causation_id, command_id, config_version, payload_json, "
    "payload_hash, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
)
INSERT_RECEIPT = (
    "INSERT INTO apt_command_receipts"
    "(command_id, stream_id, command_hash, committed_version, event_ids_json, "
    "outbox_ids_json, response_json, response_hash, created_at) "
    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
)
INSERT_OUTBOX = (
    "INSERT INTO apt_outbox"
    "(outbox_id, stream_id, effect_id, command_id, payload_json, payload_hash, created_at) "
    "VALUES (?, ?, ?, ?, ?, ?, ?)"
)

__all__ = [
    "FOREIGN_KEY_SIGNATURES",
    "INDEX_SIGNATURES",
    "INSERT_EVENT",
    "INSERT_OUTBOX",
    "INSERT_RECEIPT",
    "SCHEMA",
    "SCHEMA_VERSION",
    "SchemaSignatureError",
    "TABLE_SIGNATURES",
    "validate_schema_signature",
]
