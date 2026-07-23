"""Storage and integrity internals for :class:`PostgresEffectQueue`."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from typing import TYPE_CHECKING, cast

from engine.apt_runtime.domain.canonical import canonical_json_bytes
from engine.apt_runtime.domain.effect_runtime import (
    ResourceAccess,
    ResourceClaim,
    RuntimeUsage,
)
from engine.apt_runtime.ports.effect_queue import (
    EffectQueueCorruption,
    LeaseConflict,
    LeaseNotFound,
    LeaseRecord,
    ResourceClaimConflict,
    TERMINAL_LEASE_STATUSES,
)
from engine.apt_runtime.ports.event_store import OutboxRecord, StoreCorruption

from ._effect_queue_codec import (
    decode_usage,
    encode_usage,
    lease_from_row,
)
from ._postgres_effect_queue_support import (
    NONTERMINAL_VALUES,
    instant,
    timestamp,
)
from ._store_codec import outbox_from_row

if TYPE_CHECKING:
    from psycopg import Connection
    from psycopg.rows import DictRow


_GRANT_FIELDS = (
    "grant_ref",
    "grant_hash",
    "config_version",
    "authorization_ref",
    "authorization_hash",
)


def _authority_context(record: LeaseRecord) -> tuple[object, ...]:
    return (
        record.budget,
        record.resource_claims,
        *(getattr(record, field) for field in _GRANT_FIELDS),
    )


def _validate_epoch_invariants(records: list[LeaseRecord]) -> None:
    contexts = [_authority_context(record) for record in records if record.activated_at is not None]
    if contexts and any(context != contexts[0] for context in contexts[1:]):
        raise EffectQueueCorruption(
            "runtime budget, resource claims, or execution grant changed "
            "across activated lease epochs"
        )
    for previous, current in zip(records, records[1:], strict=False):
        if previous.completed_at is None or instant(current.claimed_at) < instant(
            previous.completed_at
        ):
            raise EffectQueueCorruption("lease epoch chronology overlaps its predecessor")


class PostgresEffectQueueInternalsMixin:
    """Operation-scoped connection, locking, row codec, and journal validation."""

    if TYPE_CHECKING:

        def _connect(self, *, read_only: bool = False) -> Connection[DictRow]: ...
        def _durable_write(self, connection: Connection[DictRow]) -> None: ...
        def _advisory_lock(
            self, connection: Connection[DictRow], namespace: str, identity: str
        ) -> None: ...
        def _validate_journal(
            self, connection: Connection[DictRow], record: LeaseRecord
        ) -> None: ...
        def _validate_usage_journal(
            self,
            connection: Connection[DictRow],
            outbox_id: str,
            usage: RuntimeUsage,
            *,
            updated_at: str,
            first_claimed_at: str,
        ) -> None: ...

    @contextmanager
    def _write_lease(self, lease_token: str) -> Iterator[tuple[Connection[DictRow], LeaseRecord]]:
        with self._connect() as connection:
            with connection.transaction():
                self._durable_write(connection)
                self._advisory_lock(connection, "lease", lease_token)
                row = self._lease_row(connection, lease_token, for_update=True)
                if row is None:
                    raise LeaseNotFound(f"unknown lease token {lease_token!r}")
                yield connection, self._decode_lease(connection, row, validate_context=True)

    def _verify_requested_outbox(
        self, connection: Connection[DictRow], requested: OutboxRecord
    ) -> None:
        row = connection.execute(
            "SELECT * FROM apt_outbox WHERE outbox_id = %s FOR UPDATE",
            (requested.outbox_id,),
        ).fetchone()
        if row is None:
            raise LeaseNotFound(f"outbox {requested.outbox_id!r} does not exist")
        stored = self._decode_outbox(row)
        if stored != requested:
            raise LeaseConflict("requested OutboxRecord differs from the immutable stored row")

    def _assert_resources_available(
        self,
        connection: Connection[DictRow],
        requested: tuple[ResourceClaim, ...],
    ) -> None:
        rows = connection.execute(
            "SELECT * FROM effect_runtime_leases WHERE status = ANY(%s) "
            "ORDER BY outbox_id, lease_epoch FOR UPDATE",
            (list(NONTERMINAL_VALUES),),
        ).fetchall()
        for row in rows:
            held = self._decode_lease(connection, row, validate_context=False)
            if held.status in TERMINAL_LEASE_STATUSES:
                raise EffectQueueCorruption("resource query returned a terminal lease")
            for existing in held.resource_claims:
                if any(claim.conflicts_with(existing) for claim in requested):
                    raise ResourceClaimConflict(
                        f"resource {existing.resource_key!r} is held by lease {held.lease_token!r}"
                    )

    def _ensure_usage_ledger(
        self,
        connection: Connection[DictRow],
        *,
        outbox_id: str,
        initialized_at: str,
        prior_exists: bool,
    ) -> None:
        row = connection.execute(
            "SELECT usage_json, usage_hash, updated_at FROM effect_runtime_usage "
            "WHERE outbox_id = %s FOR UPDATE",
            (outbox_id,),
        ).fetchone()
        if row is not None:
            self._decode_usage_row(row)
            if not prior_exists:
                raise EffectQueueCorruption("usage ledger exists without a lease epoch")
            return
        if prior_exists:
            raise EffectQueueCorruption("existing lease epochs have no usage ledger")
        usage_json, usage_hash = encode_usage(RuntimeUsage())
        connection.execute(
            "INSERT INTO effect_runtime_usage"
            "(outbox_id, usage_json, usage_hash, updated_at) VALUES (%s, %s, %s, %s)",
            (outbox_id, usage_json, usage_hash, initialized_at),
        )

    def _required_lease(self, connection: Connection[DictRow], lease_token: str) -> LeaseRecord:
        row = self._lease_row(connection, lease_token)
        if row is None:  # pragma: no cover - protected by the transaction
            raise EffectQueueCorruption("lease disappeared inside its transaction")
        return self._decode_lease(connection, row, validate_context=True)

    def _lease_row(
        self,
        connection: Connection[DictRow],
        lease_token: str,
        *,
        for_update: bool = False,
    ) -> DictRow | None:
        suffix = " FOR UPDATE" if for_update else ""
        return connection.execute(
            f"SELECT * FROM effect_runtime_leases WHERE lease_token = %s{suffix}",
            (lease_token,),
        ).fetchone()

    def _decode_lease(
        self,
        connection: Connection[DictRow],
        row: Mapping[str, object],
        *,
        validate_context: bool,
    ) -> LeaseRecord:
        token = row.get("lease_token")
        if not isinstance(token, str) or not token:
            raise EffectQueueCorruption("stored lease_token is invalid")
        claim_rows = connection.execute(
            "SELECT resource_key, access FROM effect_runtime_resource_claims "
            "WHERE lease_token = %s ORDER BY resource_key, access",
            (token,),
        ).fetchall()
        claims: list[ResourceClaim] = []
        try:
            for claim_row in claim_rows:
                claims.append(
                    ResourceClaim(
                        resource_key=claim_row["resource_key"],
                        access=ResourceAccess(claim_row["access"]),
                    )
                )
        except (TypeError, ValueError) as exc:
            raise EffectQueueCorruption(f"stored resource claims are invalid: {exc}") from exc
        record = lease_from_row(row, tuple(sorted(claims, key=canonical_json_bytes)))
        if validate_context:
            self._validate_lease_context(connection, record)
        return record

    def _validate_lease_context(self, connection: Connection[DictRow], record: LeaseRecord) -> None:
        outbox_row = connection.execute(
            "SELECT * FROM apt_outbox WHERE outbox_id = %s", (record.outbox_id,)
        ).fetchone()
        if outbox_row is None:
            raise EffectQueueCorruption("lease references a missing outbox row")
        outbox = self._decode_outbox(outbox_row)
        if (record.stream_id, record.effect_id) != (
            outbox.stream_id,
            outbox.effect_id,
        ):
            raise EffectQueueCorruption("lease stream/effect identity differs from its outbox")
        epoch_rows = connection.execute(
            "SELECT * FROM effect_runtime_leases WHERE outbox_id = %s ORDER BY lease_epoch",
            (record.outbox_id,),
        ).fetchall()
        epochs = tuple(row["lease_epoch"] for row in epoch_rows)
        if epochs != tuple(range(1, len(epoch_rows) + 1)):
            raise EffectQueueCorruption("lease epochs are not contiguous from one")
        if len([row for row in epoch_rows if row["status"] in NONTERMINAL_VALUES]) > 1:
            raise EffectQueueCorruption("outbox has multiple nonterminal lease epochs")
        epoch_records = [
            record
            if row["lease_token"] == record.lease_token
            else self._decode_lease(connection, row, validate_context=False)
            for row in epoch_rows
        ]
        _validate_epoch_invariants(epoch_records)
        for candidate in epoch_records:
            self._validate_journal(connection, candidate)
        usage_row = connection.execute(
            "SELECT usage_json, usage_hash, updated_at FROM effect_runtime_usage "
            "WHERE outbox_id = %s",
            (record.outbox_id,),
        ).fetchone()
        if usage_row is None:
            raise EffectQueueCorruption("lease has no runtime usage ledger")
        usage = self._decode_usage_row(usage_row)
        self._validate_usage_journal(
            connection,
            record.outbox_id,
            usage,
            updated_at=cast(str, usage_row["updated_at"]),
            first_claimed_at=epoch_records[0].claimed_at,
        )

    def _decode_usage_row(self, row: Mapping[str, object]) -> RuntimeUsage:
        try:
            timestamp("usage.updated_at", row["updated_at"])
        except (KeyError, TypeError, ValueError) as exc:
            raise EffectQueueCorruption(f"stored usage timestamp is invalid: {exc}") from exc
        return decode_usage(row.get("usage_json"), row.get("usage_hash"))

    @staticmethod
    def _decode_outbox(row: Mapping[str, object]) -> OutboxRecord:
        try:
            return outbox_from_row(row)
        except StoreCorruption as exc:
            raise EffectQueueCorruption(f"stored outbox is corrupt: {exc}") from exc

    @staticmethod
    def _require_live_observation(current: LeaseRecord, observed_at: str, field_name: str) -> None:
        observed = instant(observed_at)
        if observed < instant(current.heartbeat_at):
            raise LeaseConflict(f"{field_name} cannot precede the current heartbeat")
        if observed >= instant(current.lease_expiry):
            raise LeaseConflict(f"{field_name} cannot revive an expired lease")


__all__ = ["PostgresEffectQueueInternalsMixin"]
