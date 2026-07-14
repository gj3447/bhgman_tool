"""Canonical typed journal replay for the PostgreSQL effect queue."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime
from typing import TYPE_CHECKING, cast

from engine.apt_runtime.domain.canonical import (
    CanonicalEncodingError,
    canonical_json_bytes,
    canonical_sha256,
)
from engine.apt_runtime.domain.effect_runtime import RuntimeUsage
from engine.apt_runtime.ports.effect_queue import (
    EffectQueueCorruption,
    LeaseConflict,
    LeaseRecord,
)

from ._effect_queue_codec import journal_detail
from ._effect_queue_journal_chain import (
    JournalChainEntry,
    JournalHead,
    advance_journal_head,
    replay_journal_checkpoints,
    replay_journal_head,
)
from ._effect_queue_journal_replay import (
    JOURNAL_ACTIONS,
    STATE_ACTIONS,
    replay_state_step,
    validate_usage_detail,
)
from ._postgres_effect_queue_support import LATEST_ACTIONS, instant, timestamp
from ._store_codec import immutable_bytes

if TYPE_CHECKING:
    from psycopg import Connection
    from psycopg.rows import DictRow


def _chain_entries(rows: list[DictRow]) -> tuple[JournalChainEntry, ...]:
    return tuple(
        (
            row["journal_position"],
            row["action"],
            row["occurred_at"],
            row["detail_hash"],
        )
        for row in rows
    )


class PostgresEffectQueueJournalMixin:
    """Append, anchor, replay, and cross-check operational journal rows."""

    if TYPE_CHECKING:

        def _lease_row(
            self,
            connection: Connection[DictRow],
            lease_token: str,
            *,
            for_update: bool = False,
        ) -> DictRow | None: ...
        def _decode_lease(
            self,
            connection: Connection[DictRow],
            row: Mapping[str, object],
            *,
            validate_context: bool,
        ) -> LeaseRecord: ...

    def _journal_projection(
        self, rows: list[DictRow]
    ) -> tuple[list[tuple[str, LeaseRecord]], tuple[datetime, ...]]:
        state_entries: list[tuple[str, LeaseRecord]] = []
        occurred: list[datetime] = []
        previous: LeaseRecord | None = None
        for row in rows:
            action = row["action"]
            if action not in JOURNAL_ACTIONS:
                raise EffectQueueCorruption(f"lease journal action {action!r} is invalid")
            observed = timestamp("journal.occurred_at", row["occurred_at"])
            occurred.append(instant(observed))
            document = self._validate_journal_detail(row["detail_json"], row["detail_hash"])
            if action == "USAGE_RECORDED":
                validate_usage_detail(document)
                continue
            if action not in STATE_ACTIONS:  # pragma: no cover - exact action set above
                raise EffectQueueCorruption("lease journal state action is invalid")
            previous = replay_state_step(action, document, previous, observed)
            state_entries.append((cast(str, action), previous))
        return state_entries, tuple(occurred)

    def _validated_journal_head(
        self,
        connection: Connection[DictRow],
        lease_token: str,
        rows: list[DictRow] | None = None,
    ) -> JournalHead:
        if rows is None:
            rows = connection.execute(
                "SELECT journal_position, action, occurred_at, detail_hash "
                "FROM effect_runtime_journal WHERE lease_token = %s "
                "ORDER BY journal_position",
                (lease_token,),
            ).fetchall()
        try:
            computed = replay_journal_head(lease_token, _chain_entries(rows))
        except (TypeError, ValueError) as exc:
            raise EffectQueueCorruption(f"effect journal chain is invalid: {exc}") from exc
        checkpoints = replay_journal_checkpoints(lease_token, _chain_entries(rows))
        stored = connection.execute(
            "SELECT head_position, head_hash FROM effect_runtime_journal_heads "
            "WHERE lease_token = %s ORDER BY head_position",
            (lease_token,),
        ).fetchall()
        if computed.position == 0:
            if stored:
                raise EffectQueueCorruption("empty effect journal has durable head checkpoints")
            return computed
        actual = tuple((row["head_position"], row["head_hash"]) for row in stored)
        expected = tuple((head.position, head.digest) for head in checkpoints)
        if actual != expected:
            raise EffectQueueCorruption("effect journal differs from durable head checkpoints")
        return computed

    @staticmethod
    def _advance_stored_head(
        connection: Connection[DictRow],
        lease_token: str,
        current: JournalHead,
    ) -> None:
        connection.execute(
            "INSERT INTO effect_runtime_journal_heads"
            "(lease_token, head_position, head_hash) VALUES (%s, %s, %s)",
            (lease_token, current.position, current.digest),
        )

    def _validate_journal(self, connection: Connection[DictRow], record: LeaseRecord) -> None:
        rows = connection.execute(
            "SELECT journal_position, action, occurred_at, detail_json, detail_hash "
            "FROM effect_runtime_journal WHERE lease_token = %s ORDER BY journal_position",
            (record.lease_token,),
        ).fetchall()
        if not rows:
            raise EffectQueueCorruption("lease has no journal")
        positions = tuple(row["journal_position"] for row in rows)
        if positions != tuple(range(1, len(rows) + 1)):
            raise EffectQueueCorruption("lease journal positions are not contiguous from one")
        state_entries, occurred = self._journal_projection(rows)
        if occurred != tuple(sorted(occurred)):
            raise EffectQueueCorruption("lease journal timestamps regress")
        if not state_entries:
            raise EffectQueueCorruption("lease journal has no state projection")
        latest_action, latest_state = state_entries[-1]
        if latest_action not in LATEST_ACTIONS[record.status]:
            raise EffectQueueCorruption("lease status differs from its latest journal action")
        self._validated_journal_head(connection, record.lease_token, rows)
        if latest_state != record:
            raise EffectQueueCorruption(
                "latest journal state projection differs from the lease row"
            )

    @staticmethod
    def _validate_journal_detail(blob: object, digest: object) -> object:
        raw = immutable_bytes(blob, "effect journal detail_json")
        try:
            document = json.loads(raw.decode("utf-8"))
            if canonical_json_bytes(document) != raw:
                raise EffectQueueCorruption(
                    "effect journal detail_json is not canonical apt-canonical-json-v1"
                )
            if not isinstance(digest, str) or canonical_sha256(document) != digest:
                raise EffectQueueCorruption("effect journal detail_hash does not match detail_json")
            return document
        except EffectQueueCorruption:
            raise
        except (
            CanonicalEncodingError,
            UnicodeError,
            ValueError,
            TypeError,
            RecursionError,
        ) as exc:
            raise EffectQueueCorruption(f"effect journal detail_json is invalid: {exc}") from exc

    def _validate_usage_journal(
        self,
        connection: Connection[DictRow],
        outbox_id: str,
        usage: RuntimeUsage,
        *,
        updated_at: str,
        first_claimed_at: str,
    ) -> None:
        rows = connection.execute(
            "SELECT j.occurred_at, j.detail_json, j.detail_hash "
            "FROM effect_runtime_journal AS j "
            "JOIN effect_runtime_leases AS l USING (lease_token) "
            "WHERE l.outbox_id = %s AND j.action = 'USAGE_RECORDED' "
            "ORDER BY l.lease_epoch, j.journal_position",
            (outbox_id,),
        ).fetchall()
        if not rows:
            if usage != RuntimeUsage():
                raise EffectQueueCorruption("nonzero usage has no usage journal entry")
            if updated_at != first_claimed_at:
                raise EffectQueueCorruption(
                    "zero usage timestamp differs from the first reservation"
                )
            return
        document = self._validate_journal_detail(rows[-1]["detail_json"], rows[-1]["detail_hash"])
        validate_usage_detail(document)
        assert isinstance(document, Mapping)
        if canonical_json_bytes(document["usage"]) != canonical_json_bytes(usage):
            raise EffectQueueCorruption("usage ledger differs from its latest usage journal")
        latest_at = timestamp("usage journal occurred_at", rows[-1]["occurred_at"])
        if updated_at != latest_at:
            raise EffectQueueCorruption(
                "usage ledger timestamp differs from its latest usage journal"
            )

    def _append_state_journal(
        self,
        connection: Connection[DictRow],
        lease_token: str,
        action: str,
        occurred_at: str,
    ) -> None:
        row = self._lease_row(connection, lease_token)
        if row is None:  # pragma: no cover - caller just inserted or locked the row
            raise EffectQueueCorruption("cannot journal a missing lease")
        record = self._decode_lease(connection, row, validate_context=False)
        self._append_journal(connection, lease_token, action, occurred_at, {"lease": record})

    def _append_journal(
        self,
        connection: Connection[DictRow],
        lease_token: str,
        action: str,
        occurred_at: str,
        detail: object,
    ) -> None:
        if action not in JOURNAL_ACTIONS:
            raise EffectQueueCorruption(f"unsupported journal action {action!r}")
        rows = connection.execute(
            "SELECT journal_position, action, occurred_at, detail_hash "
            "FROM effect_runtime_journal WHERE lease_token = %s ORDER BY journal_position",
            (lease_token,),
        ).fetchall()
        previous = self._validated_journal_head(connection, lease_token, rows)
        if rows:
            prior_at = timestamp("journal.occurred_at", rows[-1]["occurred_at"])
            if instant(occurred_at) < instant(prior_at):
                raise LeaseConflict("journal occurred_at cannot precede its prior mutation")
        detail_json, detail_hash = journal_detail(detail)
        try:
            current = advance_journal_head(
                previous,
                lease_token=lease_token,
                action=action,
                occurred_at=occurred_at,
                detail_hash=detail_hash,
            )
        except ValueError as exc:
            raise EffectQueueCorruption(str(exc)) from exc
        connection.execute(
            "INSERT INTO effect_runtime_journal"
            "(lease_token, journal_position, action, occurred_at, detail_json, detail_hash) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (
                lease_token,
                current.position,
                action,
                occurred_at,
                detail_json,
                detail_hash,
            ),
        )
        self._advance_stored_head(connection, lease_token, current)


__all__ = ["PostgresEffectQueueJournalMixin"]
