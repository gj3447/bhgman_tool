"""Backend-neutral canonical row codec for durable APT event stores.

# KG: apt-tpa-legion-engine-canon-2026-06-12
# Design: SYMPOSIUM/THEORY/APT/vnext/APT_ENGINE_FSM_DESIGN_2026-07-13.md §12.1
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Protocol, cast

from engine.apt_runtime.domain.canonical import (
    CanonicalEncodingError,
    CanonicalValue,
    as_mapping,
    canonical_json_bytes,
    deep_freeze,
)
from engine.apt_runtime.domain.events import EventEnvelope, EventType
from engine.apt_runtime.ports.event_store import (
    CommandReceipt,
    OutboxRecord,
    PersistenceSchemaError,
    Snapshot,
    StoreCorruption,
)


class RowLike(Protocol):
    """Minimum named-column row surface shared by sqlite3 and psycopg."""

    def __getitem__(self, key: str, /) -> object: ...


def immutable_bytes(value: object, location: str) -> bytes:
    """Return immutable database binary bytes or reject a lossy representation."""

    if isinstance(value, bytes):
        return value
    if isinstance(value, memoryview):
        return value.tobytes()
    raise StoreCorruption(f"{location} must be stored as database binary bytes")


def _canonical_value(blob: object, location: str) -> CanonicalValue:
    raw = immutable_bytes(blob, location)
    try:
        document = json.loads(raw.decode("utf-8"))
        frozen = deep_freeze(document)
        if canonical_json_bytes(frozen) != raw:
            raise StoreCorruption(f"{location} is not canonical apt-canonical-json-v1")
        return frozen
    except StoreCorruption:
        raise
    except (CanonicalEncodingError, UnicodeError, ValueError, TypeError, RecursionError) as exc:
        raise StoreCorruption(f"{location} is not valid canonical JSON: {exc}") from exc


def _canonical_mapping(blob: object, location: str) -> Mapping[str, CanonicalValue]:
    try:
        return as_mapping(_canonical_value(blob, location))
    except CanonicalEncodingError as exc:
        raise StoreCorruption(f"{location} must contain a JSON object") from exc


def _identity_tuple(blob: object, location: str) -> tuple[str, ...]:
    value = _canonical_value(blob, location)
    if not isinstance(value, tuple):
        raise StoreCorruption(f"{location} must contain a JSON array")
    identities = tuple(value)
    if any(not isinstance(item, str) or not item for item in identities):
        raise StoreCorruption(f"{location} must contain non-empty string identities")
    return identities  # type: ignore[return-value]


def encode_event_row(event: EventEnvelope) -> tuple[object, ...]:
    """Encode an event without allowing the database to reserialize JSON."""

    return (
        event.event_id,
        event.stream_id,
        event.stream_version,
        event.event_type.value,
        event.schema_version,
        event.fsm_spec_hash,
        event.cycle_id,
        event.work_item_id,
        event.effect_id,
        event.generation,
        event.actor,
        event.correlation_id,
        event.causation_id,
        event.command_id,
        event.config_version,
        canonical_json_bytes(event.payload),
        event.payload_hash,
        event.created_at,
    )


def encode_receipt_row(receipt: CommandReceipt) -> tuple[object, ...]:
    """Encode a receipt using canonical byte arrays and response bytes."""

    return (
        receipt.command_id,
        receipt.stream_id,
        receipt.command_hash,
        receipt.expected_version,
        receipt.committed_version,
        canonical_json_bytes(receipt.event_ids),
        canonical_json_bytes(receipt.outbox_ids),
        canonical_json_bytes(receipt.response),
        receipt.response_hash,
        receipt.created_at,
    )


def encode_outbox_row(record: OutboxRecord) -> tuple[object, ...]:
    """Encode one executable outbox request as canonical bytes."""

    return (
        record.outbox_id,
        record.stream_id,
        record.effect_id,
        record.command_id,
        canonical_json_bytes(record.payload),
        record.payload_hash,
        record.created_at,
    )


def event_from_row(row: RowLike) -> EventEnvelope:
    """Decode and validate one stored event row."""

    try:
        return EventEnvelope(
            event_id=cast(str, row["event_id"]),
            stream_id=cast(str, row["stream_id"]),
            stream_version=cast(int, row["stream_version"]),
            event_type=EventType(row["event_type"]),
            schema_version=cast(str, row["schema_version"]),
            fsm_spec_hash=cast(str, row["fsm_spec_hash"]),
            cycle_id=cast(str, row["cycle_id"]),
            work_item_id=cast(str | None, row["work_item_id"]),
            effect_id=cast(str | None, row["effect_id"]),
            generation=cast(int | None, row["generation"]),
            actor=cast(str, row["actor"]),
            correlation_id=cast(str, row["correlation_id"]),
            causation_id=cast(str, row["causation_id"]),
            command_id=cast(str, row["command_id"]),
            config_version=cast(str, row["config_version"]),
            payload=_canonical_mapping(row["payload_json"], "event.payload_json"),
            payload_hash=cast(str, row["payload_hash"]),
            created_at=cast(str, row["created_at"]),
        )
    except (TypeError, ValueError) as exc:
        raise StoreCorruption(f"stored event row is invalid: {exc}") from exc


def receipt_from_row(row: RowLike) -> CommandReceipt:
    """Decode and validate one durable command receipt."""

    try:
        return CommandReceipt(
            command_id=cast(str, row["command_id"]),
            stream_id=cast(str, row["stream_id"]),
            command_hash=cast(str, row["command_hash"]),
            expected_version=cast(int, row["expected_version"]),
            committed_version=cast(int, row["committed_version"]),
            event_ids=_identity_tuple(row["event_ids_json"], "receipt.event_ids_json"),
            outbox_ids=_identity_tuple(row["outbox_ids_json"], "receipt.outbox_ids_json"),
            response=_canonical_mapping(row["response_json"], "receipt.response_json"),
            response_hash=cast(str, row["response_hash"]),
            created_at=cast(str, row["created_at"]),
        )
    except (PersistenceSchemaError, TypeError, ValueError) as exc:
        raise StoreCorruption(f"stored command receipt is invalid: {exc}") from exc


def outbox_from_row(row: RowLike) -> OutboxRecord:
    """Decode and validate one executable outbox row."""

    try:
        return OutboxRecord(
            outbox_id=cast(str, row["outbox_id"]),
            stream_id=cast(str, row["stream_id"]),
            effect_id=cast(str, row["effect_id"]),
            command_id=cast(str, row["command_id"]),
            payload=_canonical_mapping(row["payload_json"], "outbox.payload_json"),
            payload_hash=cast(str, row["payload_hash"]),
            created_at=cast(str, row["created_at"]),
        )
    except (PersistenceSchemaError, TypeError, ValueError) as exc:
        raise StoreCorruption(f"stored outbox row is invalid: {exc}") from exc


def snapshot_from_row(row: RowLike) -> Snapshot:
    """Decode and validate one canonical aggregate snapshot."""

    try:
        return Snapshot(
            stream_id=cast(str, row["stream_id"]),
            stream_version=cast(int, row["stream_version"]),
            fsm_spec_hash=cast(str, row["fsm_spec_hash"]),
            codec_version=cast(str, row["codec_version"]),
            state_hash=cast(str, row["state_hash"]),
            state_blob=immutable_bytes(row["state_blob"], "snapshot.state_blob"),
            created_at=cast(str, row["created_at"]),
        )
    except (PersistenceSchemaError, TypeError, ValueError) as exc:
        raise StoreCorruption(f"stored snapshot is invalid: {exc}") from exc


__all__ = [
    "RowLike",
    "encode_event_row",
    "encode_outbox_row",
    "encode_receipt_row",
    "event_from_row",
    "immutable_bytes",
    "outbox_from_row",
    "receipt_from_row",
    "snapshot_from_row",
]
