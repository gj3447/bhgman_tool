"""Backend-neutral cross-row invariants for durable APT stores.

# KG: apt-tpa-legion-engine-canon-2026-06-12
# Design: SYMPOSIUM/THEORY/APT/vnext/APT_ENGINE_FSM_DESIGN_2026-07-13.md §12.1
"""

from __future__ import annotations

from typing import cast

from engine.apt_runtime.domain.events import EventEnvelope, EventType
from engine.apt_runtime.ports.event_store import (
    CommandReceipt,
    CommandReceiptDraft,
    OutboxRecord,
    PersistenceSchemaError,
    StoreCorruption,
)

from ._store_codec import RowLike


def validate_append_batch(
    stream_id: str,
    expected_version: int,
    events: tuple[EventEnvelope, ...],
    outbox: tuple[OutboxRecord, ...],
    receipt: CommandReceiptDraft,
) -> None:
    """Validate persistence identities before any backend writes a row."""

    _validate_append_types(events, outbox)
    _validate_receipt_identity(stream_id, expected_version, receipt)
    if not events:
        _validate_empty_append(outbox)
        return
    _validate_append_events(stream_id, expected_version, events, receipt)
    _validate_append_outbox(stream_id, outbox, receipt)
    _validate_effect_bindings(events, outbox)


def _validate_append_types(
    events: tuple[EventEnvelope, ...], outbox: tuple[OutboxRecord, ...]
) -> None:
    if any(not isinstance(event, EventEnvelope) for event in events):
        raise PersistenceSchemaError("events must contain only EventEnvelope values")
    if any(not isinstance(record, OutboxRecord) for record in outbox):
        raise PersistenceSchemaError("outbox_records must contain only OutboxRecord values")


def _validate_receipt_identity(
    stream_id: str, expected_version: int, receipt: CommandReceiptDraft
) -> None:
    if receipt.stream_id != stream_id:
        raise PersistenceSchemaError("receipt stream_id must match append stream_id")
    if receipt.expected_version != expected_version:
        raise PersistenceSchemaError("receipt expected_version must match append expected_version")


def _validate_empty_append(outbox: tuple[OutboxRecord, ...]) -> None:
    if outbox:
        raise PersistenceSchemaError("a no-event command cannot enqueue outbox work")


def _validate_append_events(
    stream_id: str,
    expected_version: int,
    events: tuple[EventEnvelope, ...],
    receipt: CommandReceiptDraft,
) -> None:
    expected_versions = tuple(range(expected_version + 1, expected_version + len(events) + 1))
    if tuple(event.stream_version for event in events) != expected_versions:
        raise PersistenceSchemaError(
            "event versions must be exactly contiguous after expected_version"
        )
    _validate_append_event_identities(stream_id, events, receipt)
    if len({event.event_id for event in events}) != len(events):
        raise PersistenceSchemaError("event IDs must be unique within an append batch")


def _validate_append_event_identities(
    stream_id: str,
    events: tuple[EventEnvelope, ...],
    receipt: CommandReceiptDraft,
) -> None:
    first = events[0]
    for event in events:
        if event.stream_id != stream_id or event.cycle_id != stream_id:
            raise PersistenceSchemaError("every event stream_id and cycle_id must match stream_id")
        if event.command_id != receipt.command_id:
            raise PersistenceSchemaError("every event command_id must match the command receipt")
        if (
            event.fsm_spec_hash != first.fsm_spec_hash
            or event.config_version != first.config_version
        ):
            raise PersistenceSchemaError("event batch must pin one FSM spec and configuration")


def _validate_append_outbox(
    stream_id: str, outbox: tuple[OutboxRecord, ...], receipt: CommandReceiptDraft
) -> None:
    if len({record.outbox_id for record in outbox}) != len(outbox):
        raise PersistenceSchemaError("outbox IDs must be unique within an append batch")
    for record in outbox:
        if record.stream_id != stream_id or record.command_id != receipt.command_id:
            raise PersistenceSchemaError("outbox stream/command identity must match append")


def _validate_effect_bindings(
    events: tuple[EventEnvelope, ...], outbox: tuple[OutboxRecord, ...]
) -> None:
    queued_events = _queued_effect_events(events)
    queued_effects = tuple(event.effect_id for event in queued_events)
    if len(set(queued_effects)) != len(queued_effects):
        raise PersistenceSchemaError("EffectQueued identities must be unique within a batch")
    outbox_effects = {record.effect_id for record in outbox}
    if None in queued_effects or set(queued_effects) != outbox_effects:
        raise PersistenceSchemaError(
            "outbox effect IDs must equal the EffectQueued identities in the event batch"
        )
    queued_by_effect = {event.effect_id: event for event in queued_events}
    for record in outbox:
        if record.payload != queued_by_effect[record.effect_id].payload:
            raise PersistenceSchemaError(
                "outbox executable payload must equal its EffectQueued request payload"
            )


def _queued_effect_events(events: tuple[EventEnvelope, ...]) -> tuple[EventEnvelope, ...]:
    return tuple(event for event in events if event.event_type is EventType.EFFECT_QUEUED)


def validate_receipt_events(receipt: CommandReceipt, events: tuple[EventEnvelope, ...]) -> None:
    """Validate a receipt's event identities and version interval."""

    if tuple(event.event_id for event in events) != receipt.event_ids:
        raise StoreCorruption("command receipt event references do not match stored rows")
    expected_versions = tuple(range(receipt.expected_version + 1, receipt.committed_version + 1))
    if (
        receipt.committed_version != receipt.expected_version + len(events)
        or tuple(event.stream_version for event in events) != expected_versions
    ):
        raise StoreCorruption(
            "command receipt expected_version/committed_version do not match its events"
        )


def validate_receipt_outbox_positions(positions: tuple[int, ...]) -> None:
    """Validate the PostgreSQL adapter's explicit outbox ordinals."""

    if positions != tuple(range(len(positions))):
        raise StoreCorruption("command receipt outbox positions are not contiguous")


def validate_receipt_outbox(receipt: CommandReceipt, outbox: tuple[OutboxRecord, ...]) -> None:
    """Validate a receipt's outbox identities."""

    if tuple(item.outbox_id for item in outbox) != receipt.outbox_ids:
        raise StoreCorruption("command receipt outbox references do not match stored rows")


def validate_receipt_effects(
    events: tuple[EventEnvelope, ...], outbox: tuple[OutboxRecord, ...]
) -> None:
    """Validate event-to-outbox effect identities and executable payloads."""

    queued = {
        event.effect_id: event.payload
        for event in events
        if event.event_type is EventType.EFFECT_QUEUED
    }
    if set(queued) != {item.effect_id for item in outbox}:
        raise StoreCorruption("command receipt effect events do not match its outbox rows")
    if any(item.payload != queued[item.effect_id] for item in outbox):
        raise StoreCorruption("EffectQueued and outbox executable payloads differ")


def validate_receipt_head(
    receipt: CommandReceipt,
    events: tuple[EventEnvelope, ...],
    head: RowLike | None,
) -> None:
    """Validate the receipt's committed interval against its stream head."""

    if head is None:
        if receipt.committed_version != 0:
            raise StoreCorruption("command receipt committed version has no stream head")
        return
    current_version = cast(int, head["current_version"])
    if current_version < receipt.committed_version:
        raise StoreCorruption("command receipt committed version exceeds the stream head")
    if events:
        _validate_receipt_head_binding(events, head)


def _validate_receipt_head_binding(events: tuple[EventEnvelope, ...], head: RowLike) -> None:
    fsm_spec_hash = head["fsm_spec_hash"]
    config_version = head["config_version"]
    if any(event.fsm_spec_hash != fsm_spec_hash for event in events) or any(
        event.config_version != config_version for event in events
    ):
        raise StoreCorruption("command receipt events differ from the stream head binding")


def validate_stream_prefix(stream_id: str, head: RowLike | None, counts: RowLike) -> None:
    """Validate a stream head against its durable event prefix and side rows."""

    if head is None:
        if any(counts[name] for name in ("event_count", "outbox_count", "snapshot_count")):
            raise StoreCorruption(f"stream {stream_id!r} has durable rows without a stream head")
        return
    current_version = cast(int, head["current_version"])
    if (
        counts["event_count"] != current_version
        or counts["min_event"] != 1
        or counts["max_event"] != current_version
    ):
        raise StoreCorruption(f"stream {stream_id!r} head does not match its event prefix")


__all__ = [
    "validate_append_batch",
    "validate_receipt_effects",
    "validate_receipt_events",
    "validate_receipt_head",
    "validate_receipt_outbox",
    "validate_receipt_outbox_positions",
    "validate_stream_prefix",
]
