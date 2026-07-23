"""Persistence adapters for the APT vNext durable runtime.

# KG: apt-tpa-legion-engine-canon-2026-06-12
# KG: APT_SCW_TDAD_canonical
"""

from .postgres_store import PostgresEventStore
from .sqlite_store import SqliteEventStore

__all__ = ["PostgresEventStore", "SqliteEventStore"]
