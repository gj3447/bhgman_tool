"""PostgreSQL catalog index validation for the Slice 2 effect queue."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from psycopg import Connection
    from psycopg.rows import DictRow


ColumnContract = tuple[str, str, bool, str | None]
IndexContract = tuple[
    str,
    str,
    bool,
    bool,
    tuple[str, ...],
    tuple[bool, ...],
]


class EffectQueueIndexSignatureError(ValueError):
    """The physical PostgreSQL queue indexes differ from canonical queue v2."""


def _index_type_contract(
    table: str,
    columns: tuple[str, ...],
    table_columns: Mapping[str, Sequence[ColumnContract]],
) -> tuple[tuple[str, ...], tuple[str | None, ...]]:
    definitions = {
        name: (data_type, collation) for name, data_type, _, collation in table_columns[table]
    }
    opclasses = {
        "bigint": "pg_catalog.int8_ops",
        "integer": "pg_catalog.int4_ops",
        "text": "pg_catalog.text_ops",
    }
    return (
        tuple(opclasses[definitions[column][0]] for column in columns),
        tuple(definitions[column][1] for column in columns),
    )


def validate_effect_queue_indexes(
    connection: Connection[DictRow],
    schema: str,
    table_columns: Mapping[str, Sequence[ColumnContract]],
    index_rows: Sequence[IndexContract],
) -> None:
    """Reject altered access methods, sort order, keys, predicates, or extras."""

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
                   SELECT a.attname FROM unnest(ix.indkey) WITH ORDINALITY AS key(attnum, ordinal)
                   JOIN pg_catalog.pg_attribute AS a
                     ON a.attrelid = t.oid AND a.attnum = key.attnum
                   WHERE key.ordinal <= ix.indnkeyatts ORDER BY key.ordinal
               ) AS key_columns,
               ARRAY(
                   SELECT opc_ns.nspname || '.' || opc.opcname
                   FROM unnest(ix.indclass) WITH ORDINALITY AS item(opclass_oid, ordinal)
                   JOIN pg_catalog.pg_opclass AS opc ON opc.oid = item.opclass_oid
                   JOIN pg_catalog.pg_namespace AS opc_ns ON opc_ns.oid = opc.opcnamespace
                   WHERE item.ordinal <= ix.indnkeyatts ORDER BY item.ordinal
               ) AS opclasses,
               ARRAY(
                   SELECT CASE WHEN coll.oid IS NULL THEN NULL
                               ELSE coll_ns.nspname || '.' || coll.collname END
                   FROM unnest(ix.indcollation) WITH ORDINALITY AS item(collation_oid, ordinal)
                   LEFT JOIN pg_catalog.pg_collation AS coll ON coll.oid = item.collation_oid
                   LEFT JOIN pg_catalog.pg_namespace AS coll_ns ON coll_ns.oid = coll.collnamespace
                   WHERE item.ordinal <= ix.indnkeyatts ORDER BY item.ordinal
               ) AS collations,
               ARRAY(
                   SELECT option FROM unnest(ix.indoption) WITH ORDINALITY AS item(option, ordinal)
                   ORDER BY item.ordinal
               ) AS sort_options
        FROM pg_catalog.pg_index AS ix
        JOIN pg_catalog.pg_class AS t ON t.oid = ix.indrelid
        JOIN pg_catalog.pg_class AS i ON i.oid = ix.indexrelid
        JOIN pg_catalog.pg_namespace AS n ON n.oid = t.relnamespace
        JOIN pg_catalog.pg_am AS am ON am.oid = i.relam
        WHERE n.nspname = %s AND t.relname = ANY(%s)
        """,
        (schema, list(table_columns)),
    ).fetchall()
    actual = {
        (str(row["table_name"]), str(row["index_name"])): (
            row["is_unique"],
            row["is_primary"],
            tuple(row["key_columns"]),
            tuple(row["opclasses"]),
            tuple(row["collations"]),
            tuple(bool(int(option) & 1) for option in row["sort_options"]),
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
        )
        for row in rows
    }
    expected = {}
    for table, suffix, unique, primary, columns, descending in index_rows:
        opclasses, collations = _index_type_contract(table, columns, table_columns)
        expected[(table, f"{table}_{suffix}")] = (
            unique,
            primary,
            columns,
            opclasses,
            collations,
            descending,
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
        )
    if actual != expected:
        raise EffectQueueIndexSignatureError(
            "PostgreSQL effect-runtime index signature differs from canonical queue v2"
        )


__all__ = ["EffectQueueIndexSignatureError", "validate_effect_queue_indexes"]
