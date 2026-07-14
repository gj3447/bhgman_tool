"""Compatibility imports for the backend-neutral durable-store row codec.

# KG: apt-tpa-legion-engine-canon-2026-06-12
# Design: SYMPOSIUM/THEORY/APT/vnext/APT_ENGINE_FSM_DESIGN_2026-07-13.md §12.1
"""

from ._store_codec import (
    encode_event_row,
    encode_outbox_row,
    encode_receipt_row,
    event_from_row,
    immutable_bytes,
    outbox_from_row,
    receipt_from_row,
    snapshot_from_row,
)

__all__ = [
    "encode_event_row",
    "encode_outbox_row",
    "encode_receipt_row",
    "event_from_row",
    "immutable_bytes",
    "outbox_from_row",
    "receipt_from_row",
    "snapshot_from_row",
]
