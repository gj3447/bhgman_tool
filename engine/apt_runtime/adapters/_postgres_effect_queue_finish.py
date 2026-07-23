"""Terminal transition policy for the PostgreSQL effect queue."""

from __future__ import annotations

from contextlib import AbstractContextManager
from typing import TYPE_CHECKING, NoReturn

from engine.apt_runtime.ports.effect_queue import (
    EffectQueueError,
    LeaseConflict,
    LeaseRecord,
    LeaseStatus,
    ReconciliationProbePermit,
    TERMINAL_LEASE_STATUSES,
)

from ._postgres_effect_queue_support import (
    FINISH_TRANSITIONS,
    instant,
    require_concluded_permit,
    text,
    timestamp,
)

if TYPE_CHECKING:
    from psycopg import Connection
    from psycopg.rows import DictRow


def _finish_values(
    status: LeaseStatus,
    completed_at: str,
    reconciliation_ref: str | None,
    reason: str | None,
) -> tuple[LeaseStatus, str, str | None, str | None]:
    try:
        terminal = LeaseStatus(status)
    except ValueError as exc:
        raise ValueError("status must be a terminal LeaseStatus") from exc
    if terminal not in TERMINAL_LEASE_STATUSES:
        raise ValueError("status must be terminal")
    completed_at = timestamp("completed_at", completed_at)
    if reconciliation_ref is not None:
        reconciliation_ref = text("reconciliation_ref", reconciliation_ref)
    if reason is not None:
        reason = text("reason", reason)
    if terminal is not LeaseStatus.SUCCEEDED and reason is None:
        raise ValueError(f"{terminal.value} finish requires reason")
    return terminal, completed_at, reconciliation_ref, reason


def _resolve_terminal_retry(
    current: LeaseRecord,
    terminal: LeaseStatus,
    completed_at: str,
    reconciliation_ref: str | None,
    reason: str | None,
) -> LeaseRecord:
    if (
        current.status is terminal
        and current.completed_at == completed_at
        and current.reconciliation_ref == reconciliation_ref
        and current.reason == reason
    ):
        return current
    raise LeaseConflict("terminal finish retry differs from the durable row")


def _require_finish_transition(current: LeaseRecord, terminal: LeaseStatus) -> None:
    if terminal not in FINISH_TRANSITIONS.get(current.status, frozenset()):
        raise LeaseConflict(f"cannot finish {current.status.value} lease as {terminal.value}")


class PostgresEffectQueueFinishMixin:
    """Legal absorbing finish transitions with exact duplicate idempotence."""

    if TYPE_CHECKING:

        def _write_lease(
            self, lease_token: str
        ) -> AbstractContextManager[tuple[Connection[DictRow], LeaseRecord]]: ...
        def _append_state_journal(
            self,
            connection: Connection[DictRow],
            lease_token: str,
            action: str,
            occurred_at: str,
        ) -> None: ...
        def _required_lease(
            self, connection: Connection[DictRow], lease_token: str
        ) -> LeaseRecord: ...
        def _hit_failpoint(self, location: str) -> None: ...
        def _raise_database_error(self, operation: str, exc: Exception) -> NoReturn: ...

    def finish(
        self,
        lease_token: str,
        *,
        status: LeaseStatus,
        completed_at: str,
        reconciliation_ref: str | None = None,
        reason: str | None = None,
        probe_permit: ReconciliationProbePermit | None = None,
    ) -> LeaseRecord:
        """Close a current token once, preserving claims and immutable history."""

        lease_token = text("lease_token", lease_token)
        terminal, completed_at, reconciliation_ref, reason = _finish_values(
            status, completed_at, reconciliation_ref, reason
        )
        try:
            with self._write_lease(lease_token) as (connection, current):
                if current.status in TERMINAL_LEASE_STATUSES:
                    return _resolve_terminal_retry(
                        current,
                        terminal,
                        completed_at,
                        reconciliation_ref,
                        reason,
                    )
                _require_finish_transition(current, terminal)
                if instant(completed_at) < instant(current.heartbeat_at):
                    raise LeaseConflict("completed_at cannot precede the current heartbeat")
                require_concluded_permit(current, probe_permit)
                connection.execute(
                    "UPDATE effect_runtime_leases SET status = %s, probe_token = NULL, "
                    "probe_state = NULL, probe_acquired_at = NULL, probe_expires_at = NULL, "
                    "probe_concluded_at = NULL, probe_conclusion_json = NULL, "
                    "probe_conclusion_hash = NULL, reconciliation_ref = %s, reason = %s, "
                    "completed_at = %s WHERE lease_token = %s",
                    (
                        terminal.value,
                        reconciliation_ref,
                        reason,
                        completed_at,
                        lease_token,
                    ),
                )
                self._append_state_journal(connection, lease_token, "FINISHED", completed_at)
                self._hit_failpoint("finish_before_commit")
                return self._required_lease(connection, lease_token)
        except EffectQueueError:
            raise
        except Exception as exc:
            self._raise_database_error("finish PostgreSQL effect lease", exc)


__all__ = ["PostgresEffectQueueFinishMixin"]
