"""Operation-scoped PostgreSQL connections and deterministic queue locks."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING, NoReturn

from engine.apt_runtime.ports.effect_queue import EffectQueueError

from ._postgres_effect_queue_support import lock_key

if TYPE_CHECKING:
    from psycopg import Connection
    from psycopg.rows import DictRow, RowFactory


class PostgresEffectQueueConnectionMixin:
    """Short-lived connection, transaction durability, and advisory locks."""

    if TYPE_CHECKING:
        _connect_factory: Callable[..., Connection[DictRow]]
        _row_factory: RowFactory[DictRow]
        _database_error: type[Exception]
        _repeatable_read: object
        _dsn: str
        _connect_timeout_seconds: int
        _failpoint: Callable[[str], None] | None

    def _advisory_lock(
        self, connection: Connection[DictRow], namespace: str, identity: str
    ) -> None:
        connection.execute("SELECT pg_advisory_xact_lock(%s)", (lock_key(namespace, identity),))

    @staticmethod
    def _durable_write(connection: Connection[DictRow]) -> None:
        connection.execute("SET LOCAL synchronous_commit = on")

    def _hit_failpoint(self, location: str) -> None:
        if self._failpoint is not None:
            self._failpoint(location)

    @contextmanager
    def _read_transaction(self) -> Iterator[Connection[DictRow]]:
        with self._connect(read_only=True) as connection:
            with connection.transaction():
                yield connection

    def _connect(self, *, read_only: bool = False) -> Connection[DictRow]:
        connection = self._connect_factory(
            self._dsn,
            autocommit=True,
            row_factory=self._row_factory,
            connect_timeout=self._connect_timeout_seconds,
        )
        if read_only:
            connection.isolation_level = self._repeatable_read  # type: ignore[assignment]
            connection.read_only = True
        return connection

    def _raise_database_error(self, operation: str, exc: Exception) -> NoReturn:
        if isinstance(exc, self._database_error):
            raise EffectQueueError(f"failed to {operation}: {exc}") from exc
        raise exc


__all__ = ["PostgresEffectQueueConnectionMixin"]
