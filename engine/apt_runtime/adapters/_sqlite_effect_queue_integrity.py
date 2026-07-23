"""Cross-row integrity checks for the SQLite effect-runtime queue.

These checks make the mutable operational projection fail closed against its
canonical append-only journal.  They deliberately contain no lifecycle policy.

# KG: apt-tpa-legion-engine-canon-2026-06-12
# Design: ADRs/apt-vnext-slice2-effect-runtime-2026-07-14.md
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
import sqlite3
from typing import cast

from engine.apt_runtime.domain.canonical import (
    CanonicalEncodingError,
    canonical_json_bytes,
)
from engine.apt_runtime.domain.effect_runtime import RuntimeUsage
from engine.apt_runtime.domain.events import EventSchemaError, validate_rfc3339_utc_z
from engine.apt_runtime.ports.effect_queue import (
    EffectQueueCorruption,
    LeaseConflict,
    LeaseRecord,
    LeaseStatus,
    TERMINAL_LEASE_STATUSES,
)
from engine.apt_runtime.ports.event_store import StoreCorruption

from ._effect_queue_codec import (
    decode_budget,
    decode_claims,
    decode_usage,
    journal_detail,
)
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


def _timestamp(name: str, value: object) -> str:
    if not isinstance(value, str) or not value or "\x00" in value:
        raise EffectQueueCorruption(f"{name} must be a non-empty timestamp string")
    try:
        validate_rfc3339_utc_z(name, value)
    except EventSchemaError as exc:
        raise EffectQueueCorruption(str(exc)) from exc
    return value


def _instant(value: str) -> datetime:
    return datetime.fromisoformat(value[:-1] + "+00:00")


def validated_detail(row: sqlite3.Row) -> object:
    """Decode one canonical journal detail and verify its action and digest."""

    raw_value = row["detail_json"]
    if not isinstance(raw_value, bytes):
        raise EffectQueueCorruption("journal.detail_json must be database binary bytes")
    try:
        document = json.loads(raw_value.decode("utf-8"))
        if canonical_json_bytes(document) != raw_value:
            raise EffectQueueCorruption(
                "journal.detail_json is not canonical apt-canonical-json-v1"
            )
    except EffectQueueCorruption:
        raise
    except (CanonicalEncodingError, UnicodeError, ValueError, TypeError, RecursionError) as exc:
        raise EffectQueueCorruption(f"journal.detail_json is invalid: {exc}") from exc
    digest = row["detail_hash"]
    if not isinstance(digest, str) or hashlib.sha256(raw_value).hexdigest() != digest:
        raise EffectQueueCorruption("journal.detail_hash does not match detail_json")
    action = row["action"]
    if not isinstance(action, str) or action not in JOURNAL_ACTIONS:
        raise EffectQueueCorruption("journal.action is unknown")
    _timestamp("journal.occurred_at", row["occurred_at"])
    return document


def assert_journal_forward(
    connection: sqlite3.Connection, lease_token: str, occurred_at: str
) -> None:
    """Reject a mutation whose audit time would move one lease journal backwards."""

    row = connection.execute(
        "SELECT occurred_at FROM effect_runtime_journal "
        "WHERE lease_token = ? ORDER BY journal_position DESC LIMIT 1",
        (lease_token,),
    ).fetchone()
    if row is None:
        return
    latest = _timestamp("journal.occurred_at", row["occurred_at"])
    if _instant(occurred_at) < _instant(latest):
        raise LeaseConflict(f"journal occurred_at cannot precede {latest!r}")


def _chain_entries(rows: list[sqlite3.Row]) -> tuple[JournalChainEntry, ...]:
    return tuple(
        (
            row["journal_position"],
            row["action"],
            row["occurred_at"],
            row["detail_hash"],
        )
        for row in rows
    )


def _validated_journal_head(
    connection: sqlite3.Connection,
    lease_token: str,
    rows: list[sqlite3.Row] | None = None,
) -> JournalHead:
    if rows is None:
        rows = connection.execute(
            "SELECT journal_position, action, occurred_at, detail_hash "
            "FROM effect_runtime_journal WHERE lease_token = ? ORDER BY journal_position",
            (lease_token,),
        ).fetchall()
    try:
        computed = replay_journal_head(lease_token, _chain_entries(rows))
    except (TypeError, ValueError) as exc:
        raise EffectQueueCorruption(f"effect journal chain is invalid: {exc}") from exc
    checkpoints = replay_journal_checkpoints(lease_token, _chain_entries(rows))
    stored = connection.execute(
        "SELECT head_position, head_hash FROM effect_runtime_journal_heads "
        "WHERE lease_token = ? ORDER BY head_position",
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


def _advance_stored_head(
    connection: sqlite3.Connection,
    lease_token: str,
    current: JournalHead,
) -> None:
    connection.execute(
        "INSERT INTO effect_runtime_journal_heads"
        "(lease_token, head_position, head_hash) VALUES (?, ?, ?)",
        (lease_token, current.position, current.digest),
    )


def append_journal(
    connection: sqlite3.Connection,
    *,
    lease_token: str,
    action: str,
    occurred_at: str,
    detail: object,
) -> None:
    """Append one gap-detectable per-lease journal entry."""

    if action not in JOURNAL_ACTIONS:
        raise EffectQueueCorruption(f"cannot append unknown journal action {action!r}")
    assert_journal_forward(connection, lease_token, occurred_at)
    previous = _validated_journal_head(connection, lease_token)
    detail_blob, detail_hash = journal_detail(detail)
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
        "VALUES (?, ?, ?, ?, ?, ?)",
        (lease_token, current.position, action, occurred_at, detail_blob, detail_hash),
    )
    _advance_stored_head(connection, lease_token, current)


def validate_lease_journal(connection: sqlite3.Connection, record: LeaseRecord) -> None:
    """Verify journal chronology and its latest lease projection against the row."""

    rows = connection.execute(
        "SELECT journal_id, journal_position, action, occurred_at, detail_json, detail_hash "
        "FROM effect_runtime_journal WHERE lease_token = ? ORDER BY journal_position",
        (record.lease_token,),
    ).fetchall()
    if not rows:
        raise EffectQueueCorruption("effect lease has no reservation journal entry")
    if rows[0]["action"] != "RESERVED":
        raise EffectQueueCorruption("effect lease journal must begin with RESERVED")
    state_details: list[bytes] = []
    previous_at: str | None = None
    previous_state: LeaseRecord | None = None
    positions: list[int] = []
    for row in rows:
        position = row["journal_position"]
        if isinstance(position, bool) or not isinstance(position, int):
            raise EffectQueueCorruption("journal_position must be an integer")
        positions.append(position)
        document = validated_detail(row)
        occurred_at = cast(str, row["occurred_at"])
        if previous_at is not None and _instant(occurred_at) < _instant(previous_at):
            raise EffectQueueCorruption("effect lease journal chronology moves backwards")
        previous_at = occurred_at
        if row["action"] in STATE_ACTIONS:
            previous_state = replay_state_step(row["action"], document, previous_state, occurred_at)
            state_details.append(canonical_json_bytes(document))
        else:
            validate_usage_detail(document)
    if not state_details:
        raise EffectQueueCorruption("effect lease journal has no state projection")
    if tuple(positions) != tuple(range(1, len(rows) + 1)):
        raise EffectQueueCorruption("effect lease journal positions are not contiguous from one")
    _validated_journal_head(connection, record.lease_token, rows)
    if state_details[-1] != canonical_json_bytes({"lease": record}):
        raise EffectQueueCorruption("latest lease journal projection differs from lease row")


def _binding_text(name: str, value: object, *, digest: bool = False) -> str:
    if not isinstance(value, str) or not value or "\x00" in value:
        raise EffectQueueCorruption(f"lease.{name} must be a non-empty string")
    if digest and (
        len(value) != 64 or any(character not in "0123456789abcdef" for character in value)
    ):
        raise EffectQueueCorruption(f"lease.{name} must be a lowercase SHA-256 digest")
    return value


def validate_epoch_sequence(connection: sqlite3.Connection, outbox_id: str) -> None:
    """Validate contiguous epochs and their immutable coordination context."""

    rows = connection.execute(
        "SELECT lease_epoch, status, claimed_at, activated_at, completed_at, "
        "claims_json, claims_hash, budget_json, budget_hash, grant_ref, grant_hash, config_version, "
        "authorization_ref, authorization_hash FROM effect_runtime_leases "
        "WHERE outbox_id = ? ORDER BY lease_epoch",
        (outbox_id,),
    ).fetchall()
    actual = tuple(cast(int, row["lease_epoch"]) for row in rows)
    if actual != tuple(range(1, len(rows) + 1)):
        raise EffectQueueCorruption("outbox lease epochs are not contiguous from one")
    try:
        statuses = tuple(LeaseStatus(row["status"]) for row in rows)
    except ValueError as exc:
        raise EffectQueueCorruption("outbox lease epoch has an unknown status") from exc
    if any(status not in TERMINAL_LEASE_STATUSES for status in statuses[:-1]):
        raise EffectQueueCorruption("outbox has multiple nonterminal lease epochs")

    contexts: list[object] = []
    for row in rows:
        context = (
            decode_claims(row["claims_json"], row["claims_hash"]),
            decode_budget(row["budget_json"], row["budget_hash"]),
            _binding_text("grant_ref", row["grant_ref"]),
            _binding_text("grant_hash", row["grant_hash"], digest=True),
            _binding_text("config_version", row["config_version"]),
            _binding_text("authorization_ref", row["authorization_ref"]),
            _binding_text("authorization_hash", row["authorization_hash"], digest=True),
        )
        if row["activated_at"] is not None:
            contexts.append(context)
    if contexts and any(context != contexts[0] for context in contexts[1:]):
        raise EffectQueueCorruption(
            "runtime budget, claims, or execution grant changed across lease epochs"
        )
    for previous, current in zip(rows, rows[1:], strict=False):
        completed_at = previous["completed_at"]
        if completed_at is None or _instant(
            _timestamp("lease.claimed_at", current["claimed_at"])
        ) < _instant(_timestamp("lease.completed_at", completed_at)):
            raise EffectQueueCorruption("lease epoch chronology overlaps its predecessor")


def assert_usage_shape(connection: sqlite3.Connection, outbox_id: str, *, has_prior: bool) -> None:
    """Require exactly one canonical usage ledger after a first lease epoch."""

    row = connection.execute(
        "SELECT usage_json, usage_hash FROM effect_runtime_usage WHERE outbox_id = ?",
        (outbox_id,),
    ).fetchone()
    if has_prior and row is None:
        raise EffectQueueCorruption("leased outbox is missing its usage ledger")
    if not has_prior and row is not None:
        raise EffectQueueCorruption("unleased outbox unexpectedly has a usage ledger")
    if row is not None:
        try:
            decode_usage(row["usage_json"], row["usage_hash"])
        except StoreCorruption as exc:
            raise EffectQueueCorruption(str(exc)) from exc


def _validate_zero_usage_anchor(
    connection: sqlite3.Connection,
    outbox_id: str,
    usage: RuntimeUsage,
    updated_at: str,
) -> RuntimeUsage:
    if usage != RuntimeUsage():
        raise EffectQueueCorruption("nonzero usage has no canonical journal entry")
    first_lease = connection.execute(
        "SELECT claimed_at FROM effect_runtime_leases "
        "WHERE outbox_id = ? ORDER BY lease_epoch LIMIT 1",
        (outbox_id,),
    ).fetchone()
    if first_lease is None or updated_at != first_lease["claimed_at"]:
        raise EffectQueueCorruption("zero usage ledger is not anchored to its first lease")
    return usage


def load_usage(connection: sqlite3.Connection, outbox_id: str) -> RuntimeUsage:
    """Load and cross-check the canonical ledger with its latest usage journal."""

    row = connection.execute(
        "SELECT usage_json, usage_hash, updated_at FROM effect_runtime_usage WHERE outbox_id = ?",
        (outbox_id,),
    ).fetchone()
    lease_count = cast(
        int,
        connection.execute(
            "SELECT count(*) FROM effect_runtime_leases WHERE outbox_id = ?",
            (outbox_id,),
        ).fetchone()[0],
    )
    if row is None:
        if lease_count:
            raise EffectQueueCorruption("leased outbox is missing its usage ledger")
        return RuntimeUsage()
    if not lease_count:
        raise EffectQueueCorruption("unleased outbox unexpectedly has a usage ledger")
    try:
        usage = decode_usage(row["usage_json"], row["usage_hash"])
    except StoreCorruption as exc:
        raise EffectQueueCorruption(str(exc)) from exc
    updated_at = _timestamp("usage.updated_at", row["updated_at"])

    journal = connection.execute(
        "SELECT j.action, j.occurred_at, j.detail_json, j.detail_hash "
        "FROM effect_runtime_journal AS j "
        "JOIN effect_runtime_leases AS l ON l.lease_token = j.lease_token "
        "WHERE l.outbox_id = ? AND j.action = 'USAGE_RECORDED' "
        "ORDER BY j.journal_id DESC LIMIT 1",
        (outbox_id,),
    ).fetchone()
    if journal is None:
        return _validate_zero_usage_anchor(connection, outbox_id, usage, updated_at)
    document = validated_detail(journal)
    if not isinstance(document, dict) or set(document) != {"delta", "usage"}:
        raise EffectQueueCorruption("latest usage journal detail has an invalid shape")
    validate_usage_detail(document)
    if updated_at != journal["occurred_at"]:
        raise EffectQueueCorruption("usage updated_at differs from its latest journal entry")
    if canonical_json_bytes(document["usage"]) != canonical_json_bytes(usage):
        raise EffectQueueCorruption("latest usage journal differs from usage ledger")
    return usage


__all__ = [
    "assert_journal_forward",
    "assert_usage_shape",
    "load_usage",
    "validate_lease_journal",
    "validated_detail",
]
