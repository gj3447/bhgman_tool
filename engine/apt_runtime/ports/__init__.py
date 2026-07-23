"""Ports for the APT vNext durable runtime.

# KG: apt-tpa-legion-engine-canon-2026-06-12
# KG: APT_SCW_TDAD_canonical
"""

from .event_store import (
    AppendResult,
    CommandIdConflict,
    CommandReceipt,
    CommandReceiptDraft,
    EventStore,
    OutboxRecord,
    PersistenceSchemaError,
    Snapshot,
    StreamBindingConflict,
    StoreConflict,
    StoreCorruption,
    StoreError,
)

__all__ = [
    "AppendResult",
    "CommandIdConflict",
    "CommandReceipt",
    "CommandReceiptDraft",
    "EventStore",
    "OutboxRecord",
    "PersistenceSchemaError",
    "Snapshot",
    "StreamBindingConflict",
    "StoreConflict",
    "StoreCorruption",
    "StoreError",
]
