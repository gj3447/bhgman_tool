"""Private PostgreSQL v1 schema for the APT durable event store.

# KG: apt-tpa-legion-engine-canon-2026-06-12
# Design: SYMPOSIUM/THEORY/APT/vnext/APT_ENGINE_FSM_DESIGN_2026-07-13.md §12.1
"""

from __future__ import annotations

from ._postgres_schema_validation import SchemaSignatureError, validate_schema_signature


SCHEMA_VERSION = 1

SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS apt_store_schema (
        singleton INTEGER NOT NULL,
        schema_version INTEGER NOT NULL,
        CONSTRAINT apt_store_schema_pkey PRIMARY KEY (singleton),
        CONSTRAINT apt_store_schema_singleton_check CHECK (singleton = 1)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS apt_stream_heads (
        stream_id TEXT COLLATE "C" NOT NULL,
        current_version BIGINT NOT NULL,
        fsm_spec_hash TEXT COLLATE "C" NOT NULL,
        config_version TEXT COLLATE "C" NOT NULL,
        CONSTRAINT apt_stream_heads_pkey PRIMARY KEY (stream_id),
        CONSTRAINT apt_stream_heads_current_version_check CHECK (current_version >= 0)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS apt_events (
        event_id TEXT COLLATE "C" NOT NULL,
        stream_id TEXT COLLATE "C" NOT NULL,
        stream_version BIGINT NOT NULL,
        event_type TEXT COLLATE "C" NOT NULL,
        schema_version TEXT COLLATE "C" NOT NULL,
        fsm_spec_hash TEXT COLLATE "C" NOT NULL,
        cycle_id TEXT COLLATE "C" NOT NULL,
        work_item_id TEXT COLLATE "C",
        effect_id TEXT COLLATE "C",
        generation BIGINT,
        actor TEXT COLLATE "C" NOT NULL,
        correlation_id TEXT COLLATE "C" NOT NULL,
        causation_id TEXT COLLATE "C" NOT NULL,
        command_id TEXT COLLATE "C" NOT NULL,
        config_version TEXT COLLATE "C" NOT NULL,
        payload_json BYTEA NOT NULL,
        payload_hash TEXT COLLATE "C" NOT NULL,
        created_at TEXT COLLATE "C" NOT NULL,
        CONSTRAINT apt_events_pkey PRIMARY KEY (event_id),
        CONSTRAINT apt_events_stream_version_check CHECK (stream_version >= 1),
        CONSTRAINT apt_events_stream_version_key UNIQUE (stream_id, stream_version),
        CONSTRAINT apt_events_stream_head_fkey FOREIGN KEY (stream_id)
            REFERENCES apt_stream_heads (stream_id)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS apt_events_stream_version_idx
        ON apt_events (stream_id, stream_version)
    """,
    """
    CREATE TABLE IF NOT EXISTS apt_command_receipts (
        command_id TEXT COLLATE "C" NOT NULL,
        stream_id TEXT COLLATE "C" NOT NULL,
        command_hash TEXT COLLATE "C" NOT NULL,
        expected_version BIGINT NOT NULL,
        committed_version BIGINT NOT NULL,
        event_ids_json BYTEA NOT NULL,
        outbox_ids_json BYTEA NOT NULL,
        response_json BYTEA NOT NULL,
        response_hash TEXT COLLATE "C" NOT NULL,
        created_at TEXT COLLATE "C" NOT NULL,
        CONSTRAINT apt_command_receipts_pkey PRIMARY KEY (command_id),
        CONSTRAINT apt_command_receipts_expected_version_check
            CHECK (expected_version >= 0),
        CONSTRAINT apt_command_receipts_committed_version_check
            CHECK (committed_version >= 0)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS apt_outbox (
        outbox_id TEXT COLLATE "C" NOT NULL,
        stream_id TEXT COLLATE "C" NOT NULL,
        effect_id TEXT COLLATE "C" NOT NULL,
        command_id TEXT COLLATE "C" NOT NULL,
        outbox_position INTEGER NOT NULL,
        payload_json BYTEA NOT NULL,
        payload_hash TEXT COLLATE "C" NOT NULL,
        created_at TEXT COLLATE "C" NOT NULL,
        CONSTRAINT apt_outbox_pkey PRIMARY KEY (outbox_id),
        CONSTRAINT apt_outbox_position_check CHECK (outbox_position >= 0),
        CONSTRAINT apt_outbox_stream_effect_key UNIQUE (stream_id, effect_id),
        CONSTRAINT apt_outbox_command_position_key UNIQUE (command_id, outbox_position),
        CONSTRAINT apt_outbox_stream_head_fkey FOREIGN KEY (stream_id)
            REFERENCES apt_stream_heads (stream_id),
        CONSTRAINT apt_outbox_command_receipt_fkey FOREIGN KEY (command_id)
            REFERENCES apt_command_receipts (command_id)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS apt_outbox_stream_idx ON apt_outbox (stream_id)
    """,
    """
    CREATE TABLE IF NOT EXISTS apt_snapshots (
        stream_id TEXT COLLATE "C" NOT NULL,
        stream_version BIGINT NOT NULL,
        fsm_spec_hash TEXT COLLATE "C" NOT NULL,
        codec_version TEXT COLLATE "C" NOT NULL,
        state_hash TEXT COLLATE "C" NOT NULL,
        state_blob BYTEA NOT NULL,
        created_at TEXT COLLATE "C" NOT NULL,
        CONSTRAINT apt_snapshots_pkey PRIMARY KEY (stream_id, stream_version),
        CONSTRAINT apt_snapshots_stream_version_check CHECK (stream_version >= 1),
        CONSTRAINT apt_snapshots_stream_head_fkey FOREIGN KEY (stream_id)
            REFERENCES apt_stream_heads (stream_id)
    )
    """,
)

INSERT_EVENT = (
    "INSERT INTO apt_events"
    "(event_id, stream_id, stream_version, event_type, schema_version, "
    "fsm_spec_hash, cycle_id, work_item_id, effect_id, generation, actor, "
    "correlation_id, causation_id, command_id, config_version, payload_json, "
    "payload_hash, created_at) VALUES "
    "(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
)
INSERT_RECEIPT = (
    "INSERT INTO apt_command_receipts"
    "(command_id, stream_id, command_hash, expected_version, committed_version, event_ids_json, "
    "outbox_ids_json, response_json, response_hash, created_at) "
    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
)
INSERT_OUTBOX = (
    "INSERT INTO apt_outbox"
    "(outbox_id, stream_id, effect_id, command_id, outbox_position, payload_json, "
    "payload_hash, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
)

__all__ = [
    "INSERT_EVENT",
    "INSERT_OUTBOX",
    "INSERT_RECEIPT",
    "SCHEMA_STATEMENTS",
    "SCHEMA_VERSION",
    "SchemaSignatureError",
    "validate_schema_signature",
]
