"""Exact PostgreSQL schema for the Slice 2 operational effect queue.

The queue is deliberately a separate schema namespace from the immutable
``apt_*`` event store.  Its foreign keys bind every operational lease and
usage row back to a committed outbox request, while canonical BYTEA documents
retain byte identity across SQLite and PostgreSQL.

# KG: apt-tpa-legion-engine-canon-2026-06-12
# Design: ADRs/apt-vnext-slice2-effect-runtime-2026-07-14.md
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ._postgres_effect_queue_index_validation import (
    EffectQueueIndexSignatureError,
    validate_effect_queue_indexes,
)

if TYPE_CHECKING:
    from psycopg import Connection
    from psycopg.rows import DictRow


QUEUE_SCHEMA_VERSION = 2

QUEUE_SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS effect_runtime_schema (
        singleton INTEGER NOT NULL,
        schema_version INTEGER NOT NULL,
        CONSTRAINT effect_runtime_schema_pkey PRIMARY KEY (singleton),
        CONSTRAINT effect_runtime_schema_singleton_check CHECK (singleton = 1)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS effect_runtime_leases (
        lease_token TEXT COLLATE "C" NOT NULL,
        outbox_id TEXT COLLATE "C" NOT NULL,
        stream_id TEXT COLLATE "C" NOT NULL,
        effect_id TEXT COLLATE "C" NOT NULL,
        lease_epoch BIGINT NOT NULL,
        lease_owner TEXT COLLATE "C" NOT NULL,
        status TEXT COLLATE "C" NOT NULL,
        claimed_at TEXT COLLATE "C" NOT NULL,
        activated_at TEXT COLLATE "C",
        heartbeat_at TEXT COLLATE "C" NOT NULL,
        lease_expiry TEXT COLLATE "C" NOT NULL,
        attempt BIGINT NOT NULL,
        claims_json BYTEA NOT NULL,
        claims_hash TEXT COLLATE "C" NOT NULL,
        budget_json BYTEA NOT NULL,
        budget_hash TEXT COLLATE "C" NOT NULL,
        grant_ref TEXT COLLATE "C" NOT NULL,
        grant_hash TEXT COLLATE "C" NOT NULL,
        config_version TEXT COLLATE "C" NOT NULL,
        authorization_ref TEXT COLLATE "C" NOT NULL,
        authorization_hash TEXT COLLATE "C" NOT NULL,
        probe_generation BIGINT NOT NULL,
        probe_token TEXT COLLATE "C",
        probe_state TEXT COLLATE "C",
        probe_acquired_at TEXT COLLATE "C",
        probe_expires_at TEXT COLLATE "C",
        probe_concluded_at TEXT COLLATE "C",
        probe_conclusion_json BYTEA,
        probe_conclusion_hash TEXT COLLATE "C",
        reconciliation_ref TEXT COLLATE "C",
        reason TEXT COLLATE "C",
        completed_at TEXT COLLATE "C",
        CONSTRAINT effect_runtime_leases_pkey PRIMARY KEY (lease_token),
        CONSTRAINT effect_runtime_leases_epoch_check CHECK (lease_epoch >= 1),
        CONSTRAINT effect_runtime_leases_attempt_check CHECK (attempt >= 0),
        CONSTRAINT effect_runtime_leases_probe_generation_check CHECK (
            probe_generation >= 0
        ),
        CONSTRAINT effect_runtime_leases_status_check CHECK (
            status IN (
                'RESERVED', 'ACTIVE', 'RUNNING', 'RECONCILING',
                'SUCCEEDED', 'FAILED', 'CANCELLED', 'ABANDONED'
            )
        ),
        CONSTRAINT effect_runtime_leases_outbox_epoch_key UNIQUE (outbox_id, lease_epoch),
        CONSTRAINT effect_runtime_leases_outbox_fkey FOREIGN KEY (outbox_id)
            REFERENCES apt_outbox (outbox_id)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS effect_runtime_leases_outbox_epoch_idx
        ON effect_runtime_leases (outbox_id, lease_epoch DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS effect_runtime_leases_recovery_idx
        ON effect_runtime_leases (status, lease_expiry, heartbeat_at)
    """,
    """
    CREATE TABLE IF NOT EXISTS effect_runtime_resource_claims (
        lease_token TEXT COLLATE "C" NOT NULL,
        resource_key TEXT COLLATE "C" NOT NULL,
        access TEXT COLLATE "C" NOT NULL,
        CONSTRAINT effect_runtime_resource_claims_pkey
            PRIMARY KEY (lease_token, resource_key),
        CONSTRAINT effect_runtime_resource_claims_access_check CHECK (
            access IN ('SHARED_READ', 'EXCLUSIVE_WRITE')
        ),
        CONSTRAINT effect_runtime_resource_claims_lease_fkey FOREIGN KEY (lease_token)
            REFERENCES effect_runtime_leases (lease_token)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS effect_runtime_resource_claims_resource_idx
        ON effect_runtime_resource_claims (resource_key, access)
    """,
    """
    CREATE TABLE IF NOT EXISTS effect_runtime_usage (
        outbox_id TEXT COLLATE "C" NOT NULL,
        usage_json BYTEA NOT NULL,
        usage_hash TEXT COLLATE "C" NOT NULL,
        updated_at TEXT COLLATE "C" NOT NULL,
        CONSTRAINT effect_runtime_usage_pkey PRIMARY KEY (outbox_id),
        CONSTRAINT effect_runtime_usage_outbox_fkey FOREIGN KEY (outbox_id)
            REFERENCES apt_outbox (outbox_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS effect_runtime_journal (
        lease_token TEXT COLLATE "C" NOT NULL,
        journal_position BIGINT NOT NULL,
        action TEXT COLLATE "C" NOT NULL,
        occurred_at TEXT COLLATE "C" NOT NULL,
        detail_json BYTEA NOT NULL,
        detail_hash TEXT COLLATE "C" NOT NULL,
        CONSTRAINT effect_runtime_journal_pkey PRIMARY KEY (lease_token, journal_position),
        CONSTRAINT effect_runtime_journal_position_check CHECK (journal_position >= 1),
        CONSTRAINT effect_runtime_journal_lease_fkey FOREIGN KEY (lease_token)
            REFERENCES effect_runtime_leases (lease_token)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS effect_runtime_journal_heads (
        lease_token TEXT COLLATE "C" NOT NULL,
        head_position BIGINT NOT NULL,
        head_hash TEXT COLLATE "C" NOT NULL,
        CONSTRAINT effect_runtime_journal_heads_pkey PRIMARY KEY (
            lease_token, head_position
        ),
        CONSTRAINT effect_runtime_journal_heads_position_check CHECK (head_position >= 1),
        CONSTRAINT effect_runtime_journal_heads_lease_fkey FOREIGN KEY (lease_token)
            REFERENCES effect_runtime_leases (lease_token)
    )
    """,
)

QUEUE_SCHEMA_GUARD_STATEMENTS = (
    """
    CREATE FUNCTION effect_runtime_reject_checkpoint_mutation()
    RETURNS trigger
    LANGUAGE plpgsql
    AS $function$
    BEGIN
        RAISE EXCEPTION 'effect-runtime journal checkpoints are append-only'
            USING ERRCODE = '55000';
        RETURN NULL;
    END
    $function$
    """,
    """
    CREATE TRIGGER effect_runtime_journal_heads_append_only
    BEFORE UPDATE OR DELETE OR TRUNCATE ON effect_runtime_journal_heads
    FOR EACH STATEMENT
    EXECUTE FUNCTION effect_runtime_reject_checkpoint_mutation()
    """,
)


class EffectQueueSchemaSignatureError(ValueError):
    """The physical PostgreSQL queue schema differs from canonical queue v2."""


def _columns(specification: str) -> tuple[tuple[str, str, bool, str | None], ...]:
    columns = []
    for token in specification.split():
        name, data_type, required, collation = token.split(":")
        columns.append((name, data_type, required == "1", None if collation == "-" else collation))
    return tuple(columns)


_TABLE_COLUMNS = {
    "effect_runtime_schema": _columns("singleton:integer:1:- schema_version:integer:1:-"),
    "effect_runtime_leases": _columns(
        "lease_token:text:1:pg_catalog.C outbox_id:text:1:pg_catalog.C "
        "stream_id:text:1:pg_catalog.C effect_id:text:1:pg_catalog.C lease_epoch:bigint:1:- "
        "lease_owner:text:1:pg_catalog.C status:text:1:pg_catalog.C "
        "claimed_at:text:1:pg_catalog.C activated_at:text:0:pg_catalog.C "
        "heartbeat_at:text:1:pg_catalog.C lease_expiry:text:1:pg_catalog.C attempt:bigint:1:- "
        "claims_json:bytea:1:- claims_hash:text:1:pg_catalog.C budget_json:bytea:1:- "
        "budget_hash:text:1:pg_catalog.C grant_ref:text:1:pg_catalog.C "
        "grant_hash:text:1:pg_catalog.C config_version:text:1:pg_catalog.C "
        "authorization_ref:text:1:pg_catalog.C authorization_hash:text:1:pg_catalog.C "
        "probe_generation:bigint:1:- probe_token:text:0:pg_catalog.C "
        "probe_state:text:0:pg_catalog.C probe_acquired_at:text:0:pg_catalog.C "
        "probe_expires_at:text:0:pg_catalog.C probe_concluded_at:text:0:pg_catalog.C "
        "probe_conclusion_json:bytea:0:- probe_conclusion_hash:text:0:pg_catalog.C "
        "reconciliation_ref:text:0:pg_catalog.C "
        "reason:text:0:pg_catalog.C completed_at:text:0:pg_catalog.C"
    ),
    "effect_runtime_resource_claims": _columns(
        "lease_token:text:1:pg_catalog.C resource_key:text:1:pg_catalog.C "
        "access:text:1:pg_catalog.C"
    ),
    "effect_runtime_usage": _columns(
        "outbox_id:text:1:pg_catalog.C usage_json:bytea:1:- "
        "usage_hash:text:1:pg_catalog.C updated_at:text:1:pg_catalog.C"
    ),
    "effect_runtime_journal": _columns(
        "lease_token:text:1:pg_catalog.C journal_position:bigint:1:- "
        "action:text:1:pg_catalog.C occurred_at:text:1:pg_catalog.C "
        "detail_json:bytea:1:- detail_hash:text:1:pg_catalog.C"
    ),
    "effect_runtime_journal_heads": _columns(
        "lease_token:text:1:pg_catalog.C head_position:bigint:1:- head_hash:text:1:pg_catalog.C"
    ),
}


_CONSTRAINT_ROWS = (
    ("effect_runtime_schema", "pkey", "p", "primarykey(singleton)"),
    ("effect_runtime_schema", "singleton_check", "c", "check(singleton=1)"),
    ("effect_runtime_leases", "pkey", "p", "primarykey(lease_token)"),
    ("effect_runtime_leases", "epoch_check", "c", "check(lease_epoch>=1)"),
    ("effect_runtime_leases", "attempt_check", "c", "check(attempt>=0)"),
    (
        "effect_runtime_leases",
        "probe_generation_check",
        "c",
        "check(probe_generation>=0)",
    ),
    (
        "effect_runtime_leases",
        "status_check",
        "c",
        "check(status=any(array['reserved'::text,'active'::text,'running'::text,"
        "'reconciling'::text,'succeeded'::text,'failed'::text,'cancelled'::text,"
        "'abandoned'::text]))",
    ),
    (
        "effect_runtime_leases",
        "outbox_epoch_key",
        "u",
        "unique(outbox_id,lease_epoch)",
    ),
    (
        "effect_runtime_leases",
        "outbox_fkey",
        "f",
        "foreignkey(outbox_id)referencesapt_outbox(outbox_id)",
    ),
    (
        "effect_runtime_resource_claims",
        "pkey",
        "p",
        "primarykey(lease_token,resource_key)",
    ),
    (
        "effect_runtime_resource_claims",
        "access_check",
        "c",
        "check(access=any(array['shared_read'::text,'exclusive_write'::text]))",
    ),
    (
        "effect_runtime_resource_claims",
        "lease_fkey",
        "f",
        "foreignkey(lease_token)referenceseffect_runtime_leases(lease_token)",
    ),
    ("effect_runtime_usage", "pkey", "p", "primarykey(outbox_id)"),
    (
        "effect_runtime_usage",
        "outbox_fkey",
        "f",
        "foreignkey(outbox_id)referencesapt_outbox(outbox_id)",
    ),
    (
        "effect_runtime_journal",
        "pkey",
        "p",
        "primarykey(lease_token,journal_position)",
    ),
    (
        "effect_runtime_journal",
        "position_check",
        "c",
        "check(journal_position>=1)",
    ),
    (
        "effect_runtime_journal",
        "lease_fkey",
        "f",
        "foreignkey(lease_token)referenceseffect_runtime_leases(lease_token)",
    ),
    (
        "effect_runtime_journal_heads",
        "pkey",
        "p",
        "primarykey(lease_token,head_position)",
    ),
    (
        "effect_runtime_journal_heads",
        "position_check",
        "c",
        "check(head_position>=1)",
    ),
    (
        "effect_runtime_journal_heads",
        "lease_fkey",
        "f",
        "foreignkey(lease_token)referenceseffect_runtime_leases(lease_token)",
    ),
)
_CONSTRAINTS = {
    (table, f"{table}_{suffix}"): (kind, definition)
    for table, suffix, kind, definition in _CONSTRAINT_ROWS
}


_INDEX_ROWS = (
    ("effect_runtime_schema", "pkey", True, True, ("singleton",), (False,)),
    ("effect_runtime_leases", "pkey", True, True, ("lease_token",), (False,)),
    (
        "effect_runtime_leases",
        "outbox_epoch_key",
        True,
        False,
        ("outbox_id", "lease_epoch"),
        (False, False),
    ),
    (
        "effect_runtime_leases",
        "outbox_epoch_idx",
        False,
        False,
        ("outbox_id", "lease_epoch"),
        (False, True),
    ),
    (
        "effect_runtime_leases",
        "recovery_idx",
        False,
        False,
        ("status", "lease_expiry", "heartbeat_at"),
        (False, False, False),
    ),
    (
        "effect_runtime_resource_claims",
        "pkey",
        True,
        True,
        ("lease_token", "resource_key"),
        (False, False),
    ),
    (
        "effect_runtime_resource_claims",
        "resource_idx",
        False,
        False,
        ("resource_key", "access"),
        (False, False),
    ),
    ("effect_runtime_usage", "pkey", True, True, ("outbox_id",), (False,)),
    (
        "effect_runtime_journal",
        "pkey",
        True,
        True,
        ("lease_token", "journal_position"),
        (False, False),
    ),
    (
        "effect_runtime_journal_heads",
        "pkey",
        True,
        True,
        ("lease_token", "head_position"),
        (False, False),
    ),
)


def _normalize_constraint(definition: object) -> str:
    compact = "".join(str(definition).replace('"', "").lower().split())
    if compact.startswith("check((") and compact.endswith("))"):
        return f"check({compact[7:-2]})"
    return compact


def _current_schema(connection: Connection[DictRow]) -> str:
    row = connection.execute("SELECT current_schema() AS schema_name").fetchone()
    schema = None if row is None else row["schema_name"]
    if not isinstance(schema, str) or not schema:
        raise EffectQueueSchemaSignatureError("PostgreSQL connection has no current schema")
    return schema


def _validate_relations(connection: Connection[DictRow], schema: str) -> None:
    rows = connection.execute(
        """
        SELECT c.relname AS relation_name, c.relkind AS relation_kind,
               c.relpersistence AS persistence, c.relrowsecurity AS row_security,
               c.relforcerowsecurity AS force_row_security, c.relispartition AS is_partition
        FROM pg_catalog.pg_class AS c
        JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
        WHERE n.nspname = %s AND left(c.relname, 15) = 'effect_runtime_'
        """,
        (schema,),
    ).fetchall()
    actual = {
        str(row["relation_name"]): (
            row["relation_kind"],
            row["persistence"],
            row["row_security"],
            row["force_row_security"],
            row["is_partition"],
        )
        for row in rows
    }
    expected = {
        **{table: ("r", "p", False, False, False) for table in _TABLE_COLUMNS},
        **{
            f"{table}_{suffix}": ("i", "p", False, False, False)
            for table, suffix, *_ in _INDEX_ROWS
        },
    }
    if actual != expected:
        raise EffectQueueSchemaSignatureError(
            "PostgreSQL effect-runtime relation signature differs from canonical queue v2"
        )


def _validate_columns(connection: Connection[DictRow], schema: str) -> None:
    rows = connection.execute(
        """
        SELECT c.relname AS table_name, a.attnum AS ordinal, a.attname AS column_name,
               pg_catalog.format_type(a.atttypid, a.atttypmod) AS formatted_type,
               a.attnotnull AS not_null,
               CASE WHEN coll.oid IS NULL THEN NULL
                    ELSE coll_ns.nspname || '.' || coll.collname END AS collation_name,
               pg_catalog.pg_get_expr(d.adbin, d.adrelid) AS default_expression,
               a.attidentity AS identity_kind, a.attgenerated AS generated_kind
        FROM pg_catalog.pg_class AS c
        JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
        JOIN pg_catalog.pg_attribute AS a ON a.attrelid = c.oid
        LEFT JOIN pg_catalog.pg_collation AS coll ON coll.oid = a.attcollation
        LEFT JOIN pg_catalog.pg_namespace AS coll_ns ON coll_ns.oid = coll.collnamespace
        LEFT JOIN pg_catalog.pg_attrdef AS d ON d.adrelid = c.oid AND d.adnum = a.attnum
        WHERE n.nspname = %s AND c.relname = ANY(%s)
          AND a.attnum > 0 AND NOT a.attisdropped
        ORDER BY c.relname, a.attnum
        """,
        (schema, list(_TABLE_COLUMNS)),
    ).fetchall()
    actual: dict[str, list[tuple[object, ...]]] = {table: [] for table in _TABLE_COLUMNS}
    for row in rows:
        actual[str(row["table_name"])].append(
            (
                row["column_name"],
                row["formatted_type"],
                row["not_null"],
                row["collation_name"],
                row["default_expression"],
                row["identity_kind"],
                row["generated_kind"],
            )
        )
    expected = {
        table: [(*column, None, "", "") for column in columns]
        for table, columns in _TABLE_COLUMNS.items()
    }
    if actual != expected:
        raise EffectQueueSchemaSignatureError(
            "PostgreSQL effect-runtime column signature differs from canonical queue v2"
        )


def _validate_constraints(connection: Connection[DictRow], schema: str) -> None:
    rows = connection.execute(
        """
        SELECT c.relname AS table_name, con.conname AS constraint_name,
               con.contype AS constraint_type,
               pg_catalog.pg_get_constraintdef(con.oid, false) AS definition,
               con.convalidated AS validated, con.condeferrable AS deferrable,
               con.condeferred AS deferred, con.connoinherit AS no_inherit,
               con.conislocal AS is_local, con.coninhcount AS inherited_count
        FROM pg_catalog.pg_constraint AS con
        JOIN pg_catalog.pg_class AS c ON c.oid = con.conrelid
        JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
        WHERE n.nspname = %s AND c.relname = ANY(%s)
        """,
        (schema, list(_TABLE_COLUMNS)),
    ).fetchall()
    actual = {
        (str(row["table_name"]), str(row["constraint_name"])): (
            row["constraint_type"],
            _normalize_constraint(row["definition"]),
            row["validated"],
            row["deferrable"],
            row["deferred"],
            row["no_inherit"],
            row["is_local"],
            row["inherited_count"],
        )
        for row in rows
    }
    expected = {
        key: (kind, definition, True, False, False, kind != "c", True, 0)
        for key, (kind, definition) in _CONSTRAINTS.items()
    }
    if actual != expected:
        raise EffectQueueSchemaSignatureError(
            "PostgreSQL effect-runtime constraint signature differs from canonical queue v2"
        )


def _compact_source(value: object) -> str:
    return "".join(str(value).lower().split())


def _validate_append_only_guard(connection: Connection[DictRow], schema: str) -> None:
    rows = connection.execute(
        """
        SELECT t.tgname AS trigger_name, t.tgtype AS trigger_type,
               t.tgenabled AS enabled, t.tgisinternal AS internal,
               p.proname AS function_name, p.prosecdef AS security_definer,
               p.proleakproof AS leakproof, p.proisstrict AS strict,
               p.provolatile AS volatility, p.proparallel AS parallel_safety,
               l.lanname AS language_name,
               pg_catalog.pg_get_function_identity_arguments(p.oid) AS identity_args,
               pg_catalog.pg_get_function_result(p.oid) AS result_type,
               p.prosrc AS function_source
        FROM pg_catalog.pg_trigger AS t
        JOIN pg_catalog.pg_class AS c ON c.oid = t.tgrelid
        JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
        JOIN pg_catalog.pg_proc AS p ON p.oid = t.tgfoid
        JOIN pg_catalog.pg_language AS l ON l.oid = p.prolang
        WHERE n.nspname = %s AND left(c.relname, 15) = 'effect_runtime_'
          AND NOT t.tgisinternal
        """,
        (schema,),
    ).fetchall()
    actual = tuple(
        (
            row["trigger_name"],
            row["trigger_type"],
            row["enabled"],
            row["internal"],
            row["function_name"],
            row["security_definer"],
            row["leakproof"],
            row["strict"],
            row["volatility"],
            row["parallel_safety"],
            row["language_name"],
            row["identity_args"],
            row["result_type"],
            _compact_source(row["function_source"]),
        )
        for row in rows
    )
    expected_source = _compact_source(
        """
        BEGIN
            RAISE EXCEPTION 'effect-runtime journal checkpoints are append-only'
                USING ERRCODE = '55000';
            RETURN NULL;
        END
        """
    )
    expected = (
        (
            "effect_runtime_journal_heads_append_only",
            58,
            "O",
            False,
            "effect_runtime_reject_checkpoint_mutation",
            False,
            False,
            False,
            "v",
            "u",
            "plpgsql",
            "",
            "trigger",
            expected_source,
        ),
    )
    if actual != expected:
        raise EffectQueueSchemaSignatureError(
            "PostgreSQL effect-runtime append-only trigger signature differs from queue v2"
        )
    rules = connection.execute(
        "SELECT rulename FROM pg_catalog.pg_rules "
        "WHERE schemaname = %s AND left(tablename, 15) = 'effect_runtime_'",
        (schema,),
    ).fetchall()
    if rules:
        raise EffectQueueSchemaSignatureError(
            "PostgreSQL effect-runtime tables contain unexpected rewrite rules"
        )


def validate_effect_queue_schema_signature(connection: Connection[DictRow]) -> None:
    """Reject extra, missing, or altered queue relations and constraints."""

    schema = _current_schema(connection)
    _validate_relations(connection, schema)
    _validate_columns(connection, schema)
    _validate_constraints(connection, schema)
    _validate_append_only_guard(connection, schema)
    try:
        validate_effect_queue_indexes(connection, schema, _TABLE_COLUMNS, _INDEX_ROWS)
    except EffectQueueIndexSignatureError as exc:
        raise EffectQueueSchemaSignatureError(str(exc)) from exc


__all__ = [
    "EffectQueueSchemaSignatureError",
    "QUEUE_SCHEMA_GUARD_STATEMENTS",
    "QUEUE_SCHEMA_STATEMENTS",
    "QUEUE_SCHEMA_VERSION",
    "validate_effect_queue_schema_signature",
]
