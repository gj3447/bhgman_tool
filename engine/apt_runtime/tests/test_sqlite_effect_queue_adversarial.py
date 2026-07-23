"""Adversarial falsifiers for SQLite effect delivery and recovery.

# KG: apt-tpa-legion-engine-canon-2026-06-12
# Design: ADRs/apt-vnext-slice2-effect-runtime-2026-07-14.md
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sqlite3
from threading import Barrier

import pytest

from engine.apt_runtime.adapters._effect_queue_codec import (
    encode_budget,
    encode_claims,
    encode_usage,
)
from engine.apt_runtime.adapters.sqlite_effect_queue import SqliteEffectQueue
from engine.apt_runtime.domain.canonical import canonical_json_bytes, canonical_sha256
from engine.apt_runtime.domain.effect_runtime import (
    ResourceAccess,
    ResourceClaim,
    RuntimeBudget,
    RuntimeUsage,
)
from engine.apt_runtime.ports.effect_queue import (
    EffectQueueCorruption,
    EffectQueueError,
    LeaseConflict,
    LeaseStatus,
    ResourceClaimConflict,
)
from engine.apt_runtime.tests.test_sqlite_effect_queue import (
    append_outbox,
    lease_request,
    run_lease,
)


@pytest.fixture
def queue_database(tmp_path: Path):
    database = tmp_path / "effect-runtime-adversarial.sqlite3"
    from engine.apt_runtime.adapters.sqlite_store import SqliteEventStore

    store = SqliteEventStore(database)
    store.init_schema()
    store.close()
    queue = SqliteEffectQueue(database)
    queue.init_schema()
    try:
        yield database, queue
    finally:
        queue.close()


def _journal_document(database: Path, token: str, position: int) -> dict[str, object]:
    with sqlite3.connect(database) as connection:
        row = connection.execute(
            "SELECT detail_json FROM effect_runtime_journal "
            "WHERE lease_token = ? AND journal_position = ?",
            (token, position),
        ).fetchone()
    assert row is not None
    document = json.loads(bytes(row[0]).decode("utf-8"))
    assert isinstance(document, dict)
    return document


def _rewrite_journal_document(
    database: Path, token: str, position: int, document: dict[str, object]
) -> None:
    blob = canonical_json_bytes(document)
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE effect_runtime_journal SET detail_json = ?, detail_hash = ? "
            "WHERE lease_token = ? AND journal_position = ?",
            (blob, canonical_sha256(document), token, position),
        )


def test_stale_epoch_token_cannot_mutate_or_complete_a_new_attempt(queue_database) -> None:
    database, queue = queue_database
    outbox = append_outbox(database, "aba")
    queue.reserve(lease_request(outbox, "lease-aba-old"))
    run_lease(queue, "lease-aba-old", attempt=1)
    queue.finish(
        "lease-aba-old",
        status=LeaseStatus.FAILED,
        completed_at="2026-07-14T00:00:04Z",
        reason="known failed first attempt",
    )
    queue.reserve(
        lease_request(
            outbox,
            "lease-aba-new",
            claimed_at="2026-07-14T00:00:05Z",
            expiry="2026-07-14T00:02:00Z",
        )
    )
    queue.activate("lease-aba-new", activated_at="2026-07-14T00:00:06Z")
    expected = queue.start(
        "lease-aba-new",
        lease_owner="worker-a",
        attempt=2,
        started_at="2026-07-14T00:00:07Z",
    )

    with pytest.raises(LeaseConflict):
        queue.heartbeat(
            "lease-aba-old",
            lease_owner="worker-a",
            heartbeat_at="2026-07-14T00:00:08Z",
            lease_expiry="2026-07-14T00:03:00Z",
        )
    with pytest.raises(LeaseConflict):
        queue.record_usage(
            "lease-aba-old",
            delta=RuntimeUsage(attempts=1),
            observed_at="2026-07-14T00:00:08Z",
        )
    with pytest.raises(LeaseConflict, match="absorbing"):
        queue.finish(
            "lease-aba-old",
            status=LeaseStatus.SUCCEEDED,
            completed_at="2026-07-14T00:00:08Z",
        )
    assert queue.load("lease-aba-new") == expected


@pytest.mark.parametrize(
    ("first_scope", "second_scope"),
    [
        ("repo://serialized", "repo://serialized/subtree"),
        ("repo://serialized/subtree", "repo://serialized"),
    ],
)
def test_concurrent_hierarchical_exclusive_reservations_have_exactly_one_winner(
    queue_database, first_scope: str, second_scope: str
) -> None:
    database, first_queue = queue_database
    first = append_outbox(database, "race-a")
    second = append_outbox(database, "race-b")
    other_queue = SqliteEffectQueue(database)
    other_queue.init_schema()
    barrier = Barrier(2)

    def reserve(queue: SqliteEffectQueue, token: str, outbox, scope: str):
        barrier.wait()
        try:
            claim = ResourceClaim(scope, ResourceAccess.EXCLUSIVE_WRITE)
            return queue.reserve(lease_request(outbox, token, claims=(claim,)))
        except EffectQueueError as exc:
            return exc

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = tuple(
                future.result()
                for future in (
                    pool.submit(reserve, first_queue, "lease-race-a", first, first_scope),
                    pool.submit(reserve, other_queue, "lease-race-b", second, second_scope),
                )
            )
    finally:
        other_queue.close()

    winners = [item for item in results if not isinstance(item, BaseException)]
    conflicts = [item for item in results if isinstance(item, ResourceClaimConflict)]
    assert len(winners) == 1
    assert len(conflicts) == 1


def test_concurrent_duplicate_start_has_exactly_one_execution_winner(
    queue_database,
) -> None:
    database, first_queue = queue_database
    outbox = append_outbox(database, "start-race")
    token = "lease-start-race"
    first_queue.reserve(lease_request(outbox, token))
    first_queue.activate(token, activated_at="2026-07-14T00:00:02Z")
    other_queue = SqliteEffectQueue(database)
    other_queue.init_schema()
    barrier = Barrier(2)

    def start(queue: SqliteEffectQueue):
        barrier.wait()
        try:
            return queue.start(
                token,
                lease_owner="worker-a",
                attempt=1,
                started_at="2026-07-14T00:00:03Z",
            )
        except EffectQueueError as exc:
            return exc

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = tuple(
                future.result()
                for future in (
                    pool.submit(start, first_queue),
                    pool.submit(start, other_queue),
                )
            )
    finally:
        other_queue.close()

    winners = [item for item in results if not isinstance(item, BaseException)]
    conflicts = [item for item in results if isinstance(item, LeaseConflict)]
    assert len(winners) == 1
    assert len(conflicts) == 1
    assert first_queue.load(token).status is LeaseStatus.RUNNING


def test_journal_insert_failure_rolls_back_lease_transition(queue_database) -> None:
    database, queue = queue_database
    outbox = append_outbox(database, "journal-rollback")
    reserved = queue.reserve(lease_request(outbox, "lease-journal-rollback"))
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TRIGGER reject_activation_journal "
            "BEFORE INSERT ON effect_runtime_journal "
            "WHEN NEW.action = 'ACTIVATED' "
            "BEGIN SELECT RAISE(ABORT, 'injected activation journal failure'); END"
        )

    with pytest.raises(EffectQueueError, match="journal failure"):
        queue.activate("lease-journal-rollback", activated_at="2026-07-14T00:00:02Z")
    assert queue.load("lease-journal-rollback") == reserved


def test_claim_insert_failure_rolls_back_lease_usage_and_token(queue_database) -> None:
    database, queue = queue_database
    outbox = append_outbox(database, "claim-rollback")
    claim = ResourceClaim("repo://rollback", ResourceAccess.EXCLUSIVE_WRITE)
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TRIGGER reject_claim BEFORE INSERT ON effect_runtime_resource_claims "
            "BEGIN SELECT RAISE(ABORT, 'injected claim failure'); END"
        )

    with pytest.raises(EffectQueueError, match="claim failure"):
        queue.reserve(lease_request(outbox, "lease-claim-rollback", claims=(claim,)))
    assert queue.load("lease-claim-rollback") is None
    assert queue.latest_for_outbox(outbox.outbox_id) is None
    assert queue.usage_for_outbox(outbox.outbox_id) == RuntimeUsage()

    with sqlite3.connect(database) as connection:
        connection.execute("DROP TRIGGER reject_claim")
    assert (
        queue.reserve(lease_request(outbox, "lease-claim-rollback", claims=(claim,))).lease_epoch
        == 1
    )


def test_deleted_held_claim_projection_poison_reservation_closed(queue_database) -> None:
    database, queue = queue_database
    held_outbox = append_outbox(database, "deleted-held-claim")
    next_outbox = append_outbox(database, "deleted-held-claim-next")
    claim = ResourceClaim("repo://protected/tree", ResourceAccess.EXCLUSIVE_WRITE)
    held = queue.reserve(lease_request(held_outbox, "lease-held-claim", claims=(claim,)))
    with sqlite3.connect(database) as connection:
        connection.execute(
            "DELETE FROM effect_runtime_resource_claims WHERE lease_token = ?",
            (held.lease_token,),
        )

    with pytest.raises(EffectQueueCorruption, match="resource rows differ"):
        queue.reserve(
            lease_request(
                next_outbox,
                "lease-after-deleted-claim",
                claims=(ResourceClaim("repo://protected", ResourceAccess.EXCLUSIVE_WRITE),),
            )
        )
    assert queue.latest_for_outbox(next_outbox.outbox_id) is None


@pytest.mark.parametrize(
    "context_field",
    [
        "claims",
        "budget",
        "grant_ref",
        "grant_hash",
        "config_version",
        "authorization_ref",
        "authorization_hash",
    ],
)
def test_cross_epoch_coordination_context_rewrite_fails_closed(
    queue_database, context_field: str
) -> None:
    database, queue = queue_database
    outbox = append_outbox(database, f"epoch-context-{context_field}")
    first_token = f"lease-epoch-context-{context_field}-1"
    second_token = f"lease-epoch-context-{context_field}-2"
    queue.reserve(lease_request(outbox, first_token))
    run_lease(queue, first_token)
    queue.finish(
        first_token,
        status=LeaseStatus.FAILED,
        completed_at="2026-07-14T00:00:04Z",
        reason="known failure",
    )
    queue.reserve(
        lease_request(
            outbox,
            second_token,
            claimed_at="2026-07-14T00:00:05Z",
            expiry="2026-07-14T00:02:00Z",
        )
    )
    queue.activate(second_token, activated_at="2026-07-14T00:00:06Z")

    with sqlite3.connect(database) as connection:
        if context_field == "claims":
            blob, digest = encode_claims(
                (ResourceClaim("repo://rewritten", ResourceAccess.EXCLUSIVE_WRITE),)
            )
            connection.execute(
                "UPDATE effect_runtime_leases SET claims_json = ?, claims_hash = ? "
                "WHERE lease_token = ?",
                (blob, digest, first_token),
            )
        elif context_field == "budget":
            blob, digest = encode_budget(
                RuntimeBudget(
                    max_attempts=9,
                    max_runtime_seconds=999,
                    max_cost_units=999,
                    max_no_progress=9,
                    max_reconciliation_probes=9,
                )
            )
            connection.execute(
                "UPDATE effect_runtime_leases SET budget_json = ?, budget_hash = ? "
                "WHERE lease_token = ?",
                (blob, digest, first_token),
            )
        else:
            replacement = {
                "grant_ref": "grant://rewritten",
                "grant_hash": "f" * 64,
                "config_version": "config-rewritten",
                "authorization_ref": "authorization://rewritten",
                "authorization_hash": "e" * 64,
            }[context_field]
            statement = {
                "grant_ref": (
                    "UPDATE effect_runtime_leases SET grant_ref = ? WHERE lease_token = ?"
                ),
                "grant_hash": (
                    "UPDATE effect_runtime_leases SET grant_hash = ? WHERE lease_token = ?"
                ),
                "config_version": (
                    "UPDATE effect_runtime_leases SET config_version = ? WHERE lease_token = ?"
                ),
                "authorization_ref": (
                    "UPDATE effect_runtime_leases SET authorization_ref = ? WHERE lease_token = ?"
                ),
                "authorization_hash": (
                    "UPDATE effect_runtime_leases SET authorization_hash = ? WHERE lease_token = ?"
                ),
            }[context_field]
            connection.execute(
                statement,
                (replacement, first_token),
            )

    with pytest.raises(EffectQueueCorruption, match="changed across lease epochs"):
        queue.load(second_token)


@pytest.mark.parametrize(
    ("mutation", "operation"),
    [
        (
            "UPDATE effect_runtime_leases SET claims_hash = ? WHERE lease_token = ?",
            "lease",
        ),
        (
            "UPDATE effect_runtime_journal SET detail_hash = ? WHERE lease_token = ?",
            "lease",
        ),
    ],
)
def test_corrupted_lease_or_journal_digest_fails_closed(
    queue_database, mutation: str, operation: str
) -> None:
    database, queue = queue_database
    outbox = append_outbox(database, f"corrupt-{operation}")
    token = f"lease-corrupt-{operation}"
    queue.reserve(lease_request(outbox, token))
    with sqlite3.connect(database) as connection:
        connection.execute(mutation, ("f" * 64, token))

    with pytest.raises(EffectQueueCorruption):
        queue.load(token)


def test_validly_hashed_but_rewound_usage_is_caught_by_journal(queue_database) -> None:
    database, queue = queue_database
    outbox = append_outbox(database, "usage-rewind")
    token = "lease-usage-rewind"
    queue.reserve(lease_request(outbox, token))
    run_lease(queue, token)
    queue.record_usage(
        token,
        delta=RuntimeUsage(attempts=1, runtime_seconds=11, cost_units=4),
        observed_at="2026-07-14T00:00:04Z",
    )
    zero_blob, zero_hash = encode_usage(RuntimeUsage())
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE effect_runtime_usage SET usage_json = ?, usage_hash = ? WHERE outbox_id = ?",
            (zero_blob, zero_hash, outbox.outbox_id),
        )

    with pytest.raises(EffectQueueCorruption, match="journal differs"):
        queue.usage_for_outbox(outbox.outbox_id)


def test_deleted_usage_tail_and_rewound_ledger_fail_against_head_anchor(
    queue_database,
) -> None:
    database, queue = queue_database
    outbox = append_outbox(database, "usage-tail-anchor")
    token = "lease-usage-tail-anchor"
    queue.reserve(lease_request(outbox, token))
    run_lease(queue, token)
    queue.record_usage(
        token,
        delta=RuntimeUsage(attempts=1, runtime_seconds=9, cost_units=2),
        observed_at="2026-07-14T00:00:04Z",
    )
    zero_blob, zero_hash = encode_usage(RuntimeUsage())
    with sqlite3.connect(database) as connection:
        connection.execute(
            "DELETE FROM effect_runtime_journal "
            "WHERE lease_token = ? AND action = 'USAGE_RECORDED'",
            (token,),
        )
        connection.execute(
            "UPDATE effect_runtime_usage SET usage_json = ?, usage_hash = ?, updated_at = ? "
            "WHERE outbox_id = ?",
            (zero_blob, zero_hash, "2026-07-14T00:00:00Z", outbox.outbox_id),
        )

    with pytest.raises(EffectQueueCorruption, match="durable head checkpoints"):
        queue.usage_for_outbox(outbox.outbox_id)


def test_deleted_probe_tail_and_rewound_permit_cannot_refund_probe(
    queue_database,
) -> None:
    database, queue = queue_database
    outbox = append_outbox(database, "probe-tail-anchor")
    token = "lease-probe-tail-anchor"
    queue.reserve(lease_request(outbox, token))
    run_lease(queue, token)
    queue.mark_reconciling(
        token,
        observed_at="2026-07-14T00:00:04Z",
        reconciliation_ref="reconcile://tail-anchor/1",
        reason="ambiguous",
    )
    queue.begin_reconciliation_probe(
        token,
        permit_token="permit-tail-anchor-1",
        acquired_at="2026-07-14T00:00:05Z",
        expires_at="2026-07-14T00:00:20Z",
    )
    zero_blob, zero_hash = encode_usage(RuntimeUsage())
    with sqlite3.connect(database) as connection:
        connection.execute(
            "DELETE FROM effect_runtime_journal WHERE lease_token = ? "
            "AND action IN ('PROBE_ACQUIRED', 'USAGE_RECORDED')",
            (token,),
        )
        connection.execute(
            "UPDATE effect_runtime_leases SET probe_generation = 0, probe_token = NULL, "
            "probe_state = NULL, probe_acquired_at = NULL, probe_expires_at = NULL, "
            "probe_concluded_at = NULL, probe_conclusion_json = NULL, "
            "probe_conclusion_hash = NULL WHERE lease_token = ?",
            (token,),
        )
        connection.execute(
            "UPDATE effect_runtime_usage SET usage_json = ?, usage_hash = ?, updated_at = ? "
            "WHERE outbox_id = ?",
            (zero_blob, zero_hash, "2026-07-14T00:00:00Z", outbox.outbox_id),
        )

    with pytest.raises(EffectQueueCorruption, match="durable head checkpoints"):
        queue.begin_reconciliation_probe(
            token,
            permit_token="permit-tail-anchor-2",
            acquired_at="2026-07-14T00:00:06Z",
            expires_at="2026-07-14T00:00:21Z",
        )


@pytest.mark.parametrize("operation", ["UPDATE", "DELETE"])
def test_journal_head_checkpoints_reject_mutating_runtime_dml(
    queue_database, operation: str
) -> None:
    database, queue = queue_database
    outbox = append_outbox(database, f"checkpoint-guard-{operation.lower()}")
    token = f"lease-checkpoint-guard-{operation.lower()}"
    queue.reserve(lease_request(outbox, token))
    statement = {
        "UPDATE": ("UPDATE effect_runtime_journal_heads SET head_hash = ? WHERE lease_token = ?"),
        "DELETE": "DELETE FROM effect_runtime_journal_heads WHERE lease_token = ?",
    }[operation]
    parameters = ("f" * 64, token) if operation == "UPDATE" else (token,)

    with sqlite3.connect(database) as connection:
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute(statement, parameters)


@pytest.mark.parametrize(
    ("mutation", "value"),
    [
        ("UPDATE effect_runtime_leases SET lease_owner = ? WHERE lease_token = ?", "attacker"),
        (
            "UPDATE effect_runtime_leases SET grant_hash = ? WHERE lease_token = ?",
            "f" * 64,
        ),
        (
            "UPDATE effect_runtime_leases SET config_version = ? WHERE lease_token = ?",
            "config-v2",
        ),
        (
            "UPDATE effect_runtime_leases SET authorization_ref = ? WHERE lease_token = ?",
            "authorization://attacker",
        ),
    ],
)
def test_lease_row_rewrite_is_caught_by_latest_journal_projection(
    queue_database, mutation: str, value: str
) -> None:
    database, queue = queue_database
    outbox = append_outbox(database, "row-rewrite")
    token = "lease-row-rewrite"
    queue.reserve(lease_request(outbox, token))
    with sqlite3.connect(database) as connection:
        connection.execute(mutation, (value, token))

    with pytest.raises(EffectQueueCorruption, match="projection differs"):
        queue.load(token)


def test_historic_journal_lease_requires_exact_field_set(queue_database) -> None:
    database, queue = queue_database
    outbox = append_outbox(database, "journal-exact-fields")
    token = "lease-journal-exact-fields"
    queue.reserve(lease_request(outbox, token))
    document = _journal_document(database, token, 1)
    lease = document["lease"]
    assert isinstance(lease, dict)
    lease["unreviewed_field"] = "injected"
    _rewrite_journal_document(database, token, 1, document)

    with pytest.raises(EffectQueueCorruption, match="incompatible field set"):
        queue.load(token)


def test_historic_journal_cannot_rewrite_immutable_grant_binding(queue_database) -> None:
    database, queue = queue_database
    outbox = append_outbox(database, "journal-grant-carry")
    token = "lease-journal-grant-carry"
    queue.reserve(lease_request(outbox, token))
    queue.activate(token, activated_at="2026-07-14T00:00:02Z")
    document = _journal_document(database, token, 2)
    lease = document["lease"]
    assert isinstance(lease, dict)
    lease["grant_ref"] = "grant://attacker"
    _rewrite_journal_document(database, token, 2, document)
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE effect_runtime_leases SET grant_ref = ? WHERE lease_token = ?",
            ("grant://attacker", token),
        )

    with pytest.raises(EffectQueueCorruption, match=r"rewrites lease\.grant_ref"):
        queue.load(token)


def test_middle_journal_deletion_is_detected_by_per_lease_position(queue_database) -> None:
    database, queue = queue_database
    outbox = append_outbox(database, "journal-position-gap")
    token = "lease-journal-position-gap"
    queue.reserve(lease_request(outbox, token))
    run_lease(queue, token)
    queue.record_usage(
        token,
        delta=RuntimeUsage(attempts=1),
        observed_at="2026-07-14T00:00:04Z",
    )
    queue.heartbeat(
        token,
        lease_owner="worker-a",
        heartbeat_at="2026-07-14T00:00:05Z",
        lease_expiry="2026-07-14T00:02:00Z",
    )
    with sqlite3.connect(database) as connection:
        connection.execute(
            "DELETE FROM effect_runtime_journal WHERE lease_token = ? AND journal_position = 4",
            (token,),
        )

    with pytest.raises(EffectQueueCorruption, match="positions are not contiguous"):
        queue.load(token)


def test_journal_action_rewrite_is_caught_even_when_detail_hash_still_matches(
    queue_database,
) -> None:
    database, queue = queue_database
    outbox = append_outbox(database, "action-rewrite")
    token = "lease-action-rewrite"
    queue.reserve(lease_request(outbox, token))
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE effect_runtime_journal SET action = 'FINISHED' WHERE lease_token = ?",
            (token,),
        )

    with pytest.raises(EffectQueueCorruption, match="journal"):
        queue.load(token)


def test_corrupted_immutable_outbox_is_rejected_before_reservation(queue_database) -> None:
    database, queue = queue_database
    outbox = append_outbox(database, "outbox-corrupt")
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE apt_outbox SET payload_hash = ? WHERE outbox_id = ?",
            ("f" * 64, outbox.outbox_id),
        )

    with pytest.raises(EffectQueueCorruption):
        queue.reserve(lease_request(outbox, "lease-outbox-corrupt"))
    assert queue.load("lease-outbox-corrupt") is None


def test_outbox_corruption_after_reservation_poison_loads_closed(queue_database) -> None:
    database, queue = queue_database
    outbox = append_outbox(database, "outbox-corrupt-after")
    token = "lease-outbox-corrupt-after"
    queue.reserve(lease_request(outbox, token))
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE apt_outbox SET payload_hash = ? WHERE outbox_id = ?",
            ("f" * 64, outbox.outbox_id),
        )

    with pytest.raises(EffectQueueCorruption):
        queue.load(token)


def test_schema_drift_is_rejected_on_reopen(queue_database) -> None:
    database, queue = queue_database
    queue.close()
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE effect_runtime_intruder(unreviewed_column TEXT NOT NULL)")

    reopened = SqliteEffectQueue(database)
    try:
        with pytest.raises(EffectQueueCorruption, match="DDL differs"):
            reopened.init_schema()
    finally:
        reopened.close()


def test_orphan_operational_row_is_rejected_by_foreign_key_audit(queue_database) -> None:
    database, queue = queue_database
    queue.close()
    with sqlite3.connect(database) as connection:
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute(
            "INSERT INTO effect_runtime_usage"
            "(outbox_id, usage_json, usage_hash, updated_at) VALUES (?, ?, ?, ?)",
            (
                "missing-outbox",
                *encode_usage(RuntimeUsage()),
                "2026-07-14T00:00:00Z",
            ),
        )

    reopened = SqliteEffectQueue(database)
    try:
        with pytest.raises(EffectQueueCorruption, match="foreign-key corruption"):
            reopened.init_schema()
    finally:
        reopened.close()


def test_queue_schema_creation_without_event_store_rolls_back(tmp_path: Path) -> None:
    database = tmp_path / "missing-event-store.sqlite3"
    queue = SqliteEffectQueue(database)
    try:
        with pytest.raises(EffectQueueCorruption, match="apt_outbox"):
            queue.init_schema()
    finally:
        queue.close()
    with sqlite3.connect(database) as connection:
        names = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE name LIKE 'effect_runtime_%'"
            )
        }
    assert names == set()
