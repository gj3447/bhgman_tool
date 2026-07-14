"""Fail-closed PostgreSQL catalog signature validation for APT schema v1.

# KG: apt-tpa-legion-engine-canon-2026-06-12
# Design: SYMPOSIUM/THEORY/APT/vnext/APT_ENGINE_FSM_DESIGN_2026-07-13.md §12.1
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from psycopg import Connection
    from psycopg.rows import DictRow


class SchemaSignatureError(ValueError):
    """The physical PostgreSQL schema does not match canonical APT schema v1."""


def _columns(specification: str) -> tuple[tuple[str, str, bool, str | None], ...]:
    columns = []
    for token in specification.split():
        name, data_type, required, collation = token.split(":")
        columns.append((name, data_type, required == "1", None if collation == "-" else collation))
    return tuple(columns)


_TABLE_COLUMNS = {
    "apt_store_schema": _columns("singleton:integer:1:- schema_version:integer:1:-"),
    "apt_stream_heads": _columns(
        "stream_id:text:1:pg_catalog.C current_version:bigint:1:- "
        "fsm_spec_hash:text:1:pg_catalog.C config_version:text:1:pg_catalog.C"
    ),
    "apt_events": _columns(
        "event_id:text:1:pg_catalog.C stream_id:text:1:pg_catalog.C "
        "stream_version:bigint:1:- event_type:text:1:pg_catalog.C "
        "schema_version:text:1:pg_catalog.C fsm_spec_hash:text:1:pg_catalog.C "
        "cycle_id:text:1:pg_catalog.C work_item_id:text:0:pg_catalog.C "
        "effect_id:text:0:pg_catalog.C generation:bigint:0:- actor:text:1:pg_catalog.C "
        "correlation_id:text:1:pg_catalog.C causation_id:text:1:pg_catalog.C "
        "command_id:text:1:pg_catalog.C config_version:text:1:pg_catalog.C "
        "payload_json:bytea:1:- payload_hash:text:1:pg_catalog.C "
        "created_at:text:1:pg_catalog.C"
    ),
    "apt_command_receipts": _columns(
        "command_id:text:1:pg_catalog.C stream_id:text:1:pg_catalog.C "
        "command_hash:text:1:pg_catalog.C "
        "expected_version:bigint:1:- committed_version:bigint:1:- event_ids_json:bytea:1:- "
        "outbox_ids_json:bytea:1:- response_json:bytea:1:- "
        "response_hash:text:1:pg_catalog.C created_at:text:1:pg_catalog.C"
    ),
    "apt_outbox": _columns(
        "outbox_id:text:1:pg_catalog.C stream_id:text:1:pg_catalog.C "
        "effect_id:text:1:pg_catalog.C command_id:text:1:pg_catalog.C "
        "outbox_position:integer:1:- payload_json:bytea:1:- "
        "payload_hash:text:1:pg_catalog.C created_at:text:1:pg_catalog.C"
    ),
    "apt_snapshots": _columns(
        "stream_id:text:1:pg_catalog.C stream_version:bigint:1:- "
        "fsm_spec_hash:text:1:pg_catalog.C codec_version:text:1:pg_catalog.C "
        "state_hash:text:1:pg_catalog.C state_blob:bytea:1:- "
        "created_at:text:1:pg_catalog.C"
    ),
}


_CONSTRAINT_ROWS = (
    ("apt_store_schema", "pkey", "p", "primarykey(singleton)"),
    ("apt_store_schema", "singleton_check", "c", "check(singleton=1)"),
    ("apt_stream_heads", "pkey", "p", "primarykey(stream_id)"),
    ("apt_stream_heads", "current_version_check", "c", "check(current_version>=0)"),
    ("apt_events", "pkey", "p", "primarykey(event_id)"),
    ("apt_events", "stream_version_check", "c", "check(stream_version>=1)"),
    ("apt_events", "stream_version_key", "u", "unique(stream_id,stream_version)"),
    (
        "apt_events",
        "stream_head_fkey",
        "f",
        "foreignkey(stream_id)referencesapt_stream_heads(stream_id)",
    ),
    ("apt_command_receipts", "pkey", "p", "primarykey(command_id)"),
    ("apt_command_receipts", "expected_version_check", "c", "check(expected_version>=0)"),
    ("apt_command_receipts", "committed_version_check", "c", "check(committed_version>=0)"),
    ("apt_outbox", "pkey", "p", "primarykey(outbox_id)"),
    ("apt_outbox", "position_check", "c", "check(outbox_position>=0)"),
    ("apt_outbox", "stream_effect_key", "u", "unique(stream_id,effect_id)"),
    ("apt_outbox", "command_position_key", "u", "unique(command_id,outbox_position)"),
    (
        "apt_outbox",
        "stream_head_fkey",
        "f",
        "foreignkey(stream_id)referencesapt_stream_heads(stream_id)",
    ),
    (
        "apt_outbox",
        "command_receipt_fkey",
        "f",
        "foreignkey(command_id)referencesapt_command_receipts(command_id)",
    ),
    ("apt_snapshots", "pkey", "p", "primarykey(stream_id,stream_version)"),
    ("apt_snapshots", "stream_version_check", "c", "check(stream_version>=1)"),
    (
        "apt_snapshots",
        "stream_head_fkey",
        "f",
        "foreignkey(stream_id)referencesapt_stream_heads(stream_id)",
    ),
)
_CONSTRAINTS = {
    (table, f"{table}_{suffix}"): (kind, definition)
    for table, suffix, kind, definition in _CONSTRAINT_ROWS
}


_INDEX_ROWS = (
    ("apt_store_schema", "pkey", True, True, ("singleton",)),
    ("apt_stream_heads", "pkey", True, True, ("stream_id",)),
    ("apt_events", "pkey", True, True, ("event_id",)),
    ("apt_events", "stream_version_key", True, False, ("stream_id", "stream_version")),
    ("apt_events", "stream_version_idx", False, False, ("stream_id", "stream_version")),
    ("apt_command_receipts", "pkey", True, True, ("command_id",)),
    ("apt_outbox", "pkey", True, True, ("outbox_id",)),
    ("apt_outbox", "stream_effect_key", True, False, ("stream_id", "effect_id")),
    ("apt_outbox", "command_position_key", True, False, ("command_id", "outbox_position")),
    ("apt_outbox", "stream_idx", False, False, ("stream_id",)),
    ("apt_snapshots", "pkey", True, True, ("stream_id", "stream_version")),
)
_INDEX_OPCLASS_BY_TYPE = {
    "bigint": "pg_catalog.int8_ops",
    "integer": "pg_catalog.int4_ops",
    "text": "pg_catalog.text_ops",
}


def _index_column_contract(
    table: str, columns: tuple[str, ...]
) -> tuple[tuple[str, ...], tuple[str | None, ...]]:
    definitions = {
        name: (data_type, collation) for name, data_type, _, collation in _TABLE_COLUMNS[table]
    }
    return (
        tuple(_INDEX_OPCLASS_BY_TYPE[definitions[column][0]] for column in columns),
        tuple(definitions[column][1] for column in columns),
    )


_INDEXES = {
    (table, f"{table}_{suffix}"): (
        unique,
        primary,
        columns,
        *_index_column_contract(table, columns),
    )
    for table, suffix, unique, primary, columns in _INDEX_ROWS
}


def _normalize_constraint(definition: object) -> str:
    compact = "".join(str(definition).replace('"', "").lower().split())
    if compact.startswith("check((") and compact.endswith("))"):
        return f"check({compact[7:-2]})"
    return compact


def _current_schema(connection: Connection[DictRow]) -> str:
    row = connection.execute("SELECT current_schema() AS schema_name").fetchone()
    schema = None if row is None else row["schema_name"]
    if not isinstance(schema, str) or not schema:
        raise SchemaSignatureError("PostgreSQL connection has no current schema")
    return schema


def _validate_relations(connection: Connection[DictRow], schema: str) -> None:
    rows = connection.execute(
        """
        SELECT c.relname AS relation_name, c.relkind AS relation_kind,
               c.relpersistence AS persistence, c.relrowsecurity AS row_security,
               c.relforcerowsecurity AS force_row_security, c.relispartition AS is_partition
        FROM pg_catalog.pg_class AS c
        JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
        WHERE n.nspname = %s AND left(c.relname, 4) = 'apt_'
        """,
        (schema,),
    ).fetchall()
    actual: dict[str, tuple[object, ...]] = {
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
        **{index: ("i", "p", False, False, False) for _, index in _INDEXES},
    }
    if actual != expected:
        raise SchemaSignatureError(
            "PostgreSQL APT schema relation signature differs from canonical v1"
        )


def _validate_columns(connection: Connection[DictRow], schema: str) -> None:
    rows = connection.execute(
        """
        SELECT c.relname AS table_name, a.attnum AS ordinal, a.attname AS column_name,
               pg_catalog.format_type(a.atttypid, a.atttypmod) AS formatted_type,
               a.attnotnull AS not_null,
               CASE WHEN coll.oid IS NULL THEN NULL
                    ELSE coll_ns.nspname || '.' || coll.collname
               END AS collation_name,
               pg_catalog.pg_get_expr(d.adbin, d.adrelid) AS default_expression,
               a.attidentity AS identity_kind, a.attgenerated AS generated_kind
        FROM pg_catalog.pg_class AS c
        JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
        JOIN pg_catalog.pg_attribute AS a ON a.attrelid = c.oid
        LEFT JOIN pg_catalog.pg_collation AS coll ON coll.oid = a.attcollation
        LEFT JOIN pg_catalog.pg_namespace AS coll_ns ON coll_ns.oid = coll.collnamespace
        LEFT JOIN pg_catalog.pg_attrdef AS d
          ON d.adrelid = c.oid AND d.adnum = a.attnum
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
        raise SchemaSignatureError(
            "PostgreSQL APT schema column signature differs from canonical v1"
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
        raise SchemaSignatureError(
            "PostgreSQL APT schema constraint signature differs from canonical v1"
        )


def _validate_indexes(connection: Connection[DictRow], schema: str) -> None:
    rows = connection.execute(
        """
        SELECT t.relname AS table_name, i.relname AS index_name,
               ix.indisunique AS is_unique, ix.indisprimary AS is_primary,
               am.amname AS access_method, ix.indisvalid AS is_valid,
               ix.indisready AS is_ready, ix.indislive AS is_live,
               ix.indisclustered AS is_clustered, ix.indisexclusion AS is_exclusion,
               ix.indimmediate AS is_immediate,
               ix.indexprs IS NULL AS no_expressions,
               ix.indpred IS NULL AS no_predicate,
               ix.indnkeyatts = ix.indnatts AS no_included_columns,
               ix.indnullsnotdistinct AS nulls_not_distinct,
               ARRAY(
                   SELECT a.attname
                   FROM unnest(ix.indkey) WITH ORDINALITY AS key(attnum, ordinal)
                   JOIN pg_catalog.pg_attribute AS a
                     ON a.attrelid = t.oid AND a.attnum = key.attnum
                   WHERE key.ordinal <= ix.indnkeyatts
                   ORDER BY key.ordinal
               ) AS key_columns,
               ARRAY(
                   SELECT opc_ns.nspname || '.' || opc.opcname
                   FROM unnest(ix.indclass) WITH ORDINALITY AS item(opclass_oid, ordinal)
                   JOIN pg_catalog.pg_opclass AS opc ON opc.oid = item.opclass_oid
                   JOIN pg_catalog.pg_namespace AS opc_ns ON opc_ns.oid = opc.opcnamespace
                   WHERE item.ordinal <= ix.indnkeyatts
                   ORDER BY item.ordinal
               ) AS opclasses,
               ARRAY(
                   SELECT CASE WHEN coll.oid IS NULL THEN NULL
                               ELSE coll_ns.nspname || '.' || coll.collname END
                   FROM unnest(ix.indcollation) WITH ORDINALITY
                     AS item(collation_oid, ordinal)
                   LEFT JOIN pg_catalog.pg_collation AS coll
                     ON coll.oid = item.collation_oid
                   LEFT JOIN pg_catalog.pg_namespace AS coll_ns
                     ON coll_ns.oid = coll.collnamespace
                   WHERE item.ordinal <= ix.indnkeyatts
                   ORDER BY item.ordinal
               ) AS collations,
               ARRAY(
                   SELECT option
                   FROM unnest(ix.indoption) WITH ORDINALITY AS item(option, ordinal)
                   ORDER BY item.ordinal
               ) AS sort_options
        FROM pg_catalog.pg_index AS ix
        JOIN pg_catalog.pg_class AS t ON t.oid = ix.indrelid
        JOIN pg_catalog.pg_class AS i ON i.oid = ix.indexrelid
        JOIN pg_catalog.pg_namespace AS n ON n.oid = t.relnamespace
        JOIN pg_catalog.pg_am AS am ON am.oid = i.relam
        WHERE n.nspname = %s AND t.relname = ANY(%s)
        """,
        (schema, list(_TABLE_COLUMNS)),
    ).fetchall()
    actual: dict[tuple[str, str], tuple[object, ...]] = {
        (str(row["table_name"]), str(row["index_name"])): (
            row["is_unique"],
            row["is_primary"],
            tuple(row["key_columns"]),  # type: ignore[arg-type]
            tuple(row["opclasses"]),  # type: ignore[arg-type]
            tuple(row["collations"]),  # type: ignore[arg-type]
            row["access_method"],
            row["is_valid"],
            row["is_ready"],
            row["is_live"],
            row["is_clustered"],
            row["is_exclusion"],
            row["is_immediate"],
            row["no_expressions"],
            row["no_predicate"],
            row["no_included_columns"],
            row["nulls_not_distinct"],
            tuple(row["sort_options"]),  # type: ignore[arg-type]
        )
        for row in rows
    }
    expected = {
        key: (
            unique,
            primary,
            columns,
            opclasses,
            collations,
            "btree",
            True,
            True,
            True,
            False,
            False,
            True,
            True,
            True,
            True,
            False,
            (0,) * len(columns),
        )
        for key, (unique, primary, columns, opclasses, collations) in _INDEXES.items()
    }
    if actual != expected:
        raise SchemaSignatureError(
            "PostgreSQL APT schema index signature differs from canonical v1"
        )


def _validate_no_unsafe_features(connection: Connection[DictRow], schema: str) -> None:
    row = connection.execute(
        """
        SELECT
          current_setting('session_replication_role') AS replication_role,
          (SELECT count(*)
             FROM pg_catalog.pg_trigger AS tg
             JOIN pg_catalog.pg_class AS c ON c.oid = tg.tgrelid
             JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
            WHERE n.nspname = %s AND c.relname = ANY(%s)
              AND (NOT tg.tgisinternal OR tg.tgenabled <> 'O'))
          +
          (SELECT count(*)
             FROM pg_catalog.pg_rewrite AS rw
             JOIN pg_catalog.pg_class AS c ON c.oid = rw.ev_class
             JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
            WHERE n.nspname = %s AND c.relname = ANY(%s))
          +
          (SELECT count(*)
             FROM pg_catalog.pg_policy AS pol
             JOIN pg_catalog.pg_class AS c ON c.oid = pol.polrelid
             JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
            WHERE n.nspname = %s AND c.relname = ANY(%s))
          +
          (SELECT count(*)
             FROM pg_catalog.pg_inherits AS inh
             JOIN pg_catalog.pg_class AS c ON c.oid = inh.inhrelid
             JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
            WHERE n.nspname = %s AND c.relname = ANY(%s))
          AS unsafe_count
        """,
        (schema, list(_TABLE_COLUMNS)) * 4,
    ).fetchone()
    if row is None or row["replication_role"] != "origin" or row["unsafe_count"] != 0:
        raise SchemaSignatureError(
            "PostgreSQL APT schema/session disables constraints or contains user triggers, "
            "rules, policies, or inheritance"
        )


def validate_schema_signature(connection: Connection[DictRow]) -> None:
    """Fail closed unless the current transaction sees exactly canonical schema v1."""

    schema = _current_schema(connection)
    connection.execute(
        "LOCK TABLE apt_store_schema, apt_stream_heads, apt_events, "
        "apt_command_receipts, apt_outbox, apt_snapshots IN ACCESS SHARE MODE"
    )
    _validate_relations(connection, schema)
    _validate_columns(connection, schema)
    _validate_constraints(connection, schema)
    _validate_indexes(connection, schema)
    _validate_no_unsafe_features(connection, schema)


__all__ = ["SchemaSignatureError", "validate_schema_signature"]
