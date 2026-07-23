"""Adversarial real-PostgreSQL effect-queue falsifiers.

# KG: apt-tpa-legion-engine-canon-2026-06-12
# Design: ADRs/apt-vnext-slice2-effect-runtime-2026-07-14.md
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
from threading import Barrier

import psycopg
import pytest

from engine.apt_runtime.adapters._effect_queue_codec import encode_usage
from engine.apt_runtime.adapters._effect_queue_journal_chain import (
    replay_journal_checkpoints,
)
from engine.apt_runtime.adapters.postgres_effect_queue import PostgresEffectQueue
from engine.apt_runtime.domain.canonical import canonical_json_bytes, canonical_sha256
from engine.apt_runtime.domain.effect_runtime import (
    ResourceAccess,
    ResourceClaim,
    RuntimeUsage,
    progress_signature,
)
from engine.apt_runtime.ports.effect_queue import (
    EffectQueueCorruption,
    LeaseConflict,
    LeaseRecord,
    LeaseStatus,
    ResourceClaimConflict,
)
from engine.apt_runtime.tests.test_postgres_effect_queue import (
    T1,
    T2,
    T3,
    T4,
    T5,
    lease_request,
    seed_outbox,
)


def _resign_postgres_checkpoints(connection, lease_token: str) -> None:
    """Emulate a schema owner crossing the runtime-DML permission boundary."""

    rows = connection.execute(
        "SELECT journal_position, action, occurred_at, detail_hash "
        "FROM effect_runtime_journal WHERE lease_token = %s ORDER BY journal_position",
        (lease_token,),
    ).fetchall()
    checkpoints = replay_journal_checkpoints(lease_token, tuple(rows))
    connection.execute(
        "ALTER TABLE effect_runtime_journal_heads "
        "DISABLE TRIGGER effect_runtime_journal_heads_append_only"
    )
    connection.execute(
        "DELETE FROM effect_runtime_journal_heads WHERE lease_token = %s",
        (lease_token,),
    )
    for checkpoint in checkpoints:
        connection.execute(
            "INSERT INTO effect_runtime_journal_heads"
            "(lease_token, head_position, head_hash) VALUES (%s, %s, %s)",
            (lease_token, checkpoint.position, checkpoint.digest),
        )
    connection.execute(
        "ALTER TABLE effect_runtime_journal_heads "
        "ENABLE TRIGGER effect_runtime_journal_heads_append_only"
    )


def _active_queue(dsn: str, *, effect_id: str = "effect-adversarial"):
    outbox = seed_outbox(dsn, effect_id=effect_id)
    queue = PostgresEffectQueue(dsn)
    queue.init_schema()
    reserved = queue.reserve(lease_request(outbox, token=f"token-{effect_id}"))
    active = queue.activate(reserved.lease_token, activated_at=T1)
    return queue, outbox, active


def test_postgres_duplicate_concurrent_start_has_exactly_one_winner(
    postgres_sandbox,
) -> None:
    setup, _, active = _active_queue(postgres_sandbox.dsn)
    setup.close()
    queues = [PostgresEffectQueue(postgres_sandbox.dsn) for _ in range(2)]
    barrier = Barrier(2)

    def start(index: int):
        barrier.wait()
        try:
            return queues[index].start(
                active.lease_token,
                lease_owner="worker-a",
                attempt=1,
                started_at=T2,
            )
        except LeaseConflict as exc:
            return exc

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(start, range(2)))
        assert sum(isinstance(item, LeaseRecord) for item in outcomes) == 1
        assert sum(isinstance(item, LeaseConflict) for item in outcomes) == 1
        assert queues[0].load(active.lease_token).status is LeaseStatus.RUNNING  # type: ignore[union-attr]
    finally:
        for queue in queues:
            queue.close()


def test_postgres_concurrent_exclusive_resource_reservations_serialize(
    postgres_sandbox,
) -> None:
    first = seed_outbox(postgres_sandbox.dsn, effect_id="effect-race-a")
    second = seed_outbox(
        postgres_sandbox.dsn,
        stream_id="cycle-race-b",
        effect_id="effect-race-b",
    )
    queues = [PostgresEffectQueue(postgres_sandbox.dsn) for _ in range(2)]
    for queue in queues:
        queue.init_schema()
    requests = [
        lease_request(first, token="token-race-a"),
        lease_request(second, token="token-race-b"),
    ]
    barrier = Barrier(2)

    def reserve(index: int):
        barrier.wait()
        try:
            return queues[index].reserve(requests[index])
        except ResourceClaimConflict as exc:
            return exc

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(reserve, range(2)))
        assert sum(isinstance(item, LeaseRecord) for item in outcomes) == 1
        assert sum(isinstance(item, ResourceClaimConflict) for item in outcomes) == 1
    finally:
        for queue in queues:
            queue.close()


def test_postgres_rejects_journal_hash_and_projection_tamper(postgres_sandbox) -> None:
    queue, _, active = _active_queue(postgres_sandbox.dsn, effect_id="effect-journal-tamper")
    with psycopg.connect(postgres_sandbox.dsn) as connection:
        connection.execute(
            "UPDATE effect_runtime_journal SET detail_hash = %s "
            "WHERE lease_token = %s AND journal_position = 2",
            ("0" * 64, active.lease_token),
        )
    with pytest.raises(EffectQueueCorruption, match="detail_hash"):
        queue.load(active.lease_token)


def test_postgres_rejects_usage_ledger_divergence(postgres_sandbox) -> None:
    queue, outbox, active = _active_queue(postgres_sandbox.dsn, effect_id="effect-usage-tamper")
    queue.start(active.lease_token, lease_owner="worker-a", attempt=1, started_at=T2)
    queue.record_usage(
        active.lease_token,
        delta=RuntimeUsage(
            attempts=1,
            runtime_seconds=1,
            progress_signature=progress_signature("first"),
        ),
        observed_at=T3,
    )
    with psycopg.connect(postgres_sandbox.dsn) as connection:
        connection.execute(
            "UPDATE effect_runtime_usage SET usage_hash = %s WHERE outbox_id = %s",
            ("f" * 64, outbox.outbox_id),
        )
    with pytest.raises(EffectQueueCorruption, match="usage_hash"):
        queue.usage_for_outbox(outbox.outbox_id)


def test_postgres_deleted_usage_tail_and_rewound_ledger_fail_closed(
    postgres_sandbox,
) -> None:
    queue, outbox, active = _active_queue(
        postgres_sandbox.dsn, effect_id="effect-usage-tail-anchor"
    )
    queue.start(active.lease_token, lease_owner="worker-a", attempt=1, started_at=T2)
    queue.record_usage(
        active.lease_token,
        delta=RuntimeUsage(attempts=1, runtime_seconds=7, cost_units=2),
        observed_at=T3,
    )
    zero_blob, zero_hash = encode_usage(RuntimeUsage())
    with psycopg.connect(postgres_sandbox.dsn) as connection:
        connection.execute(
            "DELETE FROM effect_runtime_journal "
            "WHERE lease_token = %s AND action = 'USAGE_RECORDED'",
            (active.lease_token,),
        )
        connection.execute(
            "UPDATE effect_runtime_usage SET usage_json = %s, usage_hash = %s, "
            "updated_at = %s WHERE outbox_id = %s",
            (zero_blob, zero_hash, "2026-07-14T00:00:00Z", outbox.outbox_id),
        )

    with pytest.raises(EffectQueueCorruption, match="durable head checkpoints"):
        queue.usage_for_outbox(outbox.outbox_id)


def test_postgres_deleted_probe_tail_cannot_refund_or_duplicate_probe(
    postgres_sandbox,
) -> None:
    queue, outbox, active = _active_queue(
        postgres_sandbox.dsn, effect_id="effect-probe-tail-anchor"
    )
    queue.start(active.lease_token, lease_owner="worker-a", attempt=1, started_at=T2)
    queue.mark_reconciling(
        active.lease_token,
        observed_at=T3,
        reconciliation_ref="reconcile://pg-tail-anchor/1",
        reason="ambiguous",
    )
    queue.begin_reconciliation_probe(
        active.lease_token,
        permit_token="permit-pg-tail-anchor-1",
        acquired_at=T4,
        expires_at="2026-07-14T00:00:20Z",
    )
    zero_blob, zero_hash = encode_usage(RuntimeUsage())
    with psycopg.connect(postgres_sandbox.dsn) as connection:
        connection.execute(
            "DELETE FROM effect_runtime_journal WHERE lease_token = %s "
            "AND action IN ('PROBE_ACQUIRED', 'USAGE_RECORDED')",
            (active.lease_token,),
        )
        connection.execute(
            "UPDATE effect_runtime_leases SET probe_generation = 0, probe_token = NULL, "
            "probe_state = NULL, probe_acquired_at = NULL, probe_expires_at = NULL, "
            "probe_concluded_at = NULL, probe_conclusion_json = NULL, "
            "probe_conclusion_hash = NULL WHERE lease_token = %s",
            (active.lease_token,),
        )
        connection.execute(
            "UPDATE effect_runtime_usage SET usage_json = %s, usage_hash = %s, "
            "updated_at = %s WHERE outbox_id = %s",
            (zero_blob, zero_hash, "2026-07-14T00:00:00Z", outbox.outbox_id),
        )

    with pytest.raises(EffectQueueCorruption, match="durable head checkpoints"):
        queue.begin_reconciliation_probe(
            active.lease_token,
            permit_token="permit-pg-tail-anchor-2",
            acquired_at=T5,
            expires_at="2026-07-14T00:00:21Z",
        )


@pytest.mark.parametrize("operation", ["UPDATE", "DELETE", "TRUNCATE"])
def test_postgres_journal_checkpoints_reject_mutating_runtime_dml(
    postgres_sandbox, operation: str
) -> None:
    _, _, active = _active_queue(
        postgres_sandbox.dsn,
        effect_id=f"effect-checkpoint-guard-{operation.lower()}",
    )
    statement = {
        "UPDATE": (
            "UPDATE effect_runtime_journal_heads SET head_hash = 'ffffffffffffffffffffffff"
            "ffffffffffffffffffffffffffffffffffffffff' WHERE lease_token = %s"
        ),
        "DELETE": "DELETE FROM effect_runtime_journal_heads WHERE lease_token = %s",
        "TRUNCATE": "TRUNCATE effect_runtime_journal_heads",
    }[operation]
    parameters = () if operation == "TRUNCATE" else (active.lease_token,)

    with psycopg.connect(postgres_sandbox.dsn) as connection:
        with pytest.raises(psycopg.Error, match="append-only"):
            connection.execute(statement, parameters)


@pytest.mark.parametrize("with_usage", [False, True])
def test_postgres_rejects_usage_timestamp_divergence(postgres_sandbox, with_usage: bool) -> None:
    queue, outbox, active = _active_queue(
        postgres_sandbox.dsn, effect_id=f"effect-usage-time-{with_usage}"
    )
    if with_usage:
        queue.start(
            active.lease_token,
            lease_owner="worker-a",
            attempt=1,
            started_at=T2,
        )
        queue.record_usage(
            active.lease_token,
            delta=RuntimeUsage(attempts=1, runtime_seconds=1),
            observed_at=T3,
        )
    with psycopg.connect(postgres_sandbox.dsn) as connection:
        connection.execute(
            "UPDATE effect_runtime_usage SET updated_at = %s WHERE outbox_id = %s",
            ("2026-07-14T00:00:59Z", outbox.outbox_id),
        )
    with pytest.raises(EffectQueueCorruption, match="timestamp"):
        queue.usage_for_outbox(outbox.outbox_id)


def test_postgres_replays_every_legal_journal_step(postgres_sandbox) -> None:
    queue, _, active = _active_queue(postgres_sandbox.dsn, effect_id="effect-journal-step")
    queue.start(
        active.lease_token,
        lease_owner="worker-a",
        attempt=1,
        started_at=T2,
    )
    with psycopg.connect(postgres_sandbox.dsn) as connection:
        connection.execute(
            "DELETE FROM effect_runtime_journal WHERE lease_token = %s AND journal_position = 2",
            (active.lease_token,),
        )
        connection.execute(
            "UPDATE effect_runtime_journal SET journal_position = 2 "
            "WHERE lease_token = %s AND journal_position = 3",
            (active.lease_token,),
        )
    with pytest.raises(EffectQueueCorruption, match="illegal lease journal step"):
        queue.load(active.lease_token)


def test_postgres_typed_replay_rejects_action_specific_carry_forward_rewrite(
    postgres_sandbox,
) -> None:
    queue, _, active = _active_queue(postgres_sandbox.dsn, effect_id="effect-carry-forward-rewrite")
    queue.start(active.lease_token, lease_owner="worker-a", attempt=1, started_at=T2)
    rewritten_expiry = "2026-07-14T00:02:00Z"
    with psycopg.connect(postgres_sandbox.dsn) as connection:
        position, detail_json = connection.execute(
            "SELECT journal_position, detail_json FROM effect_runtime_journal "
            "WHERE lease_token = %s AND action = 'STARTED'",
            (active.lease_token,),
        ).fetchone()
        document = json.loads(bytes(detail_json))
        document["lease"]["lease_expiry"] = rewritten_expiry
        connection.execute(
            "UPDATE effect_runtime_journal SET detail_json = %s, detail_hash = %s "
            "WHERE lease_token = %s AND journal_position = %s",
            (
                canonical_json_bytes(document),
                canonical_sha256(document),
                active.lease_token,
                position,
            ),
        )
        connection.execute(
            "UPDATE effect_runtime_leases SET lease_expiry = %s WHERE lease_token = %s",
            (rewritten_expiry, active.lease_token),
        )
        _resign_postgres_checkpoints(connection, active.lease_token)

    with pytest.raises(EffectQueueCorruption, match=r"rewrites lease\.lease_expiry"):
        queue.load(active.lease_token)


def test_postgres_typed_replay_rejects_nonmonotonic_heartbeat(postgres_sandbox) -> None:
    queue, _, active = _active_queue(postgres_sandbox.dsn, effect_id="effect-heartbeat-rewrite")
    queue.heartbeat(
        active.lease_token,
        lease_owner="worker-a",
        heartbeat_at=T2,
        lease_expiry="2026-07-14T00:02:00Z",
    )
    with psycopg.connect(postgres_sandbox.dsn) as connection:
        position, detail_json = connection.execute(
            "SELECT journal_position, detail_json FROM effect_runtime_journal "
            "WHERE lease_token = %s AND action = 'HEARTBEAT_RECORDED'",
            (active.lease_token,),
        ).fetchone()
        document = json.loads(bytes(detail_json))
        document["lease"]["heartbeat_at"] = T1
        connection.execute(
            "UPDATE effect_runtime_journal SET detail_json = %s, detail_hash = %s "
            "WHERE lease_token = %s AND journal_position = %s",
            (
                canonical_json_bytes(document),
                canonical_sha256(document),
                active.lease_token,
                position,
            ),
        )
        connection.execute(
            "UPDATE effect_runtime_leases SET heartbeat_at = %s WHERE lease_token = %s",
            (T1, active.lease_token),
        )
        _resign_postgres_checkpoints(connection, active.lease_token)

    with pytest.raises(EffectQueueCorruption, match="illegal lease journal step"):
        queue.load(active.lease_token)


def test_postgres_typed_replay_rejects_probe_generation_jump(postgres_sandbox) -> None:
    queue, _, active = _active_queue(
        postgres_sandbox.dsn, effect_id="effect-probe-generation-rewrite"
    )
    queue.start(active.lease_token, lease_owner="worker-a", attempt=1, started_at=T2)
    queue.mark_reconciling(
        active.lease_token,
        observed_at=T3,
        reconciliation_ref="reconcile://pg-generation/1",
        reason="ambiguous",
    )
    queue.begin_reconciliation_probe(
        active.lease_token,
        permit_token="permit-generation-1",
        acquired_at=T4,
        expires_at="2026-07-14T00:00:20Z",
    )
    with psycopg.connect(postgres_sandbox.dsn) as connection:
        position, detail_json = connection.execute(
            "SELECT journal_position, detail_json FROM effect_runtime_journal "
            "WHERE lease_token = %s AND action = 'PROBE_ACQUIRED'",
            (active.lease_token,),
        ).fetchone()
        document = json.loads(bytes(detail_json))
        document["lease"]["probe_generation"] = 2
        document["lease"]["probe_permit"]["generation"] = 2
        connection.execute(
            "UPDATE effect_runtime_journal SET detail_json = %s, detail_hash = %s "
            "WHERE lease_token = %s AND journal_position = %s",
            (
                canonical_json_bytes(document),
                canonical_sha256(document),
                active.lease_token,
                position,
            ),
        )
        connection.execute(
            "UPDATE effect_runtime_leases SET probe_generation = 2 WHERE lease_token = %s",
            (active.lease_token,),
        )
        _resign_postgres_checkpoints(connection, active.lease_token)

    with pytest.raises(EffectQueueCorruption, match="illegal lease journal step"):
        queue.load(active.lease_token)


def test_postgres_retry_claim_cannot_precede_prior_completion(
    postgres_sandbox,
) -> None:
    queue, outbox, active = _active_queue(postgres_sandbox.dsn, effect_id="effect-retry-time")
    queue.finish(
        active.lease_token,
        status=LeaseStatus.FAILED,
        completed_at=T3,
        reason="transient failure",
    )
    with pytest.raises(LeaseConflict, match="prior completion"):
        queue.reserve(
            lease_request(
                outbox,
                token="token-retry-before-completion",
                claimed_at=T2,
            )
        )


def test_postgres_rejects_self_consistent_cross_epoch_chronology_rewrite(
    postgres_sandbox,
) -> None:
    queue, outbox, active = _active_queue(postgres_sandbox.dsn, effect_id="effect-epoch-chronology")
    queue.finish(
        active.lease_token,
        status=LeaseStatus.FAILED,
        completed_at=T3,
        reason="known first attempt failure",
    )
    second = queue.reserve(
        lease_request(
            outbox,
            token="token-epoch-chronology-2",
            claimed_at="2026-07-14T00:00:04Z",
            expiry="2026-07-14T00:02:00Z",
        )
    )
    queue.activate(second.lease_token, activated_at="2026-07-14T00:00:05Z")

    with psycopg.connect(postgres_sandbox.dsn) as connection:
        connection.execute(
            "UPDATE effect_runtime_leases SET claimed_at = %s WHERE lease_token = %s",
            (T2, second.lease_token),
        )
        rows = connection.execute(
            "SELECT journal_position, detail_json FROM effect_runtime_journal "
            "WHERE lease_token = %s ORDER BY journal_position",
            (second.lease_token,),
        ).fetchall()
        for position, detail_json in rows:
            document = json.loads(bytes(detail_json))
            document["lease"]["claimed_at"] = T2
            connection.execute(
                "UPDATE effect_runtime_journal SET detail_json = %s, detail_hash = %s "
                "WHERE lease_token = %s AND journal_position = %s",
                (
                    canonical_json_bytes(document),
                    canonical_sha256(document),
                    second.lease_token,
                    position,
                ),
            )

    with pytest.raises(EffectQueueCorruption, match="chronology overlaps"):
        queue.load(second.lease_token)


def test_postgres_hierarchical_resource_claims_conflict(postgres_sandbox) -> None:
    first = seed_outbox(postgres_sandbox.dsn, effect_id="effect-hierarchy-a")
    second = seed_outbox(
        postgres_sandbox.dsn,
        stream_id="cycle-hierarchy-b",
        effect_id="effect-hierarchy-b",
    )
    queue = PostgresEffectQueue(postgres_sandbox.dsn)
    queue.init_schema()
    queue.reserve(
        lease_request(
            first,
            token="token-hierarchy-a",
            claims=(
                ResourceClaim(
                    resource_key="artifact://tree/root",
                    access=ResourceAccess.EXCLUSIVE_WRITE,
                ),
            ),
        )
    )
    with pytest.raises(ResourceClaimConflict):
        queue.reserve(
            lease_request(
                second,
                token="token-hierarchy-b",
                claims=(
                    ResourceClaim(
                        resource_key="artifact://tree/root/child",
                        access=ResourceAccess.SHARED_READ,
                    ),
                ),
            )
        )


def test_postgres_deleted_held_claim_index_fails_closed(postgres_sandbox) -> None:
    first = seed_outbox(postgres_sandbox.dsn, effect_id="effect-claim-index-a")
    second = seed_outbox(
        postgres_sandbox.dsn,
        stream_id="cycle-claim-index-b",
        effect_id="effect-claim-index-b",
    )
    queue = PostgresEffectQueue(postgres_sandbox.dsn)
    queue.init_schema()
    held = queue.reserve(
        lease_request(
            first,
            token="token-claim-index-a",
            claims=(
                ResourceClaim(
                    resource_key="artifact://tree/root",
                    access=ResourceAccess.EXCLUSIVE_WRITE,
                ),
            ),
        )
    )
    with psycopg.connect(postgres_sandbox.dsn) as connection:
        connection.execute(
            "DELETE FROM effect_runtime_resource_claims WHERE lease_token = %s",
            (held.lease_token,),
        )

    with pytest.raises(EffectQueueCorruption, match="resource rows differ"):
        queue.reserve(
            lease_request(
                second,
                token="token-claim-index-b",
                claims=(
                    ResourceClaim(
                        resource_key="artifact://tree/root/child",
                        access=ResourceAccess.SHARED_READ,
                    ),
                ),
            )
        )
    assert queue.latest_for_outbox(second.outbox_id) is None


def test_postgres_failpoint_rolls_back_state_and_journal(postgres_sandbox) -> None:
    outbox = seed_outbox(postgres_sandbox.dsn, effect_id="effect-failpoint")

    def fail(location: str) -> None:
        if location == "activate_before_commit":
            raise RuntimeError("injected crash")

    queue = PostgresEffectQueue(postgres_sandbox.dsn, failpoint=fail)
    queue.init_schema()
    reserved = queue.reserve(lease_request(outbox, token="token-failpoint"))
    with pytest.raises(RuntimeError, match="injected crash"):
        queue.activate(reserved.lease_token, activated_at=T1)
    reloaded = queue.load(reserved.lease_token)
    assert reloaded is not None
    assert reloaded.status is LeaseStatus.RESERVED
    with psycopg.connect(postgres_sandbox.dsn) as connection:
        count = connection.execute(
            "SELECT count(*) FROM effect_runtime_journal WHERE lease_token = %s",
            (reserved.lease_token,),
        ).fetchone()[0]
    assert count == 1


def test_postgres_init_rejects_extra_queue_relation(postgres_sandbox) -> None:
    seed_outbox(postgres_sandbox.dsn, effect_id="effect-schema-tamper")
    queue = PostgresEffectQueue(postgres_sandbox.dsn)
    queue.init_schema()
    with psycopg.connect(postgres_sandbox.dsn) as connection:
        connection.execute("CREATE TABLE effect_runtime_shadow (value INTEGER)")
    with pytest.raises(EffectQueueCorruption, match="relation signature"):
        queue.init_schema()


def test_postgres_init_rejects_disabled_checkpoint_guard(postgres_sandbox) -> None:
    seed_outbox(postgres_sandbox.dsn, effect_id="effect-trigger-tamper")
    queue = PostgresEffectQueue(postgres_sandbox.dsn)
    queue.init_schema()
    with psycopg.connect(postgres_sandbox.dsn) as connection:
        connection.execute(
            "ALTER TABLE effect_runtime_journal_heads "
            "DISABLE TRIGGER effect_runtime_journal_heads_append_only"
        )

    with pytest.raises(EffectQueueCorruption, match="append-only trigger signature"):
        queue.init_schema()


def test_postgres_init_rejects_unreviewed_rewrite_rule(postgres_sandbox) -> None:
    seed_outbox(postgres_sandbox.dsn, effect_id="effect-rule-tamper")
    queue = PostgresEffectQueue(postgres_sandbox.dsn)
    queue.init_schema()
    with psycopg.connect(postgres_sandbox.dsn) as connection:
        connection.execute(
            "CREATE RULE effect_runtime_usage_intruder AS "
            "ON UPDATE TO effect_runtime_usage DO ALSO NOTHING"
        )

    with pytest.raises(EffectQueueCorruption, match="unexpected rewrite rules"):
        queue.init_schema()


def test_postgres_expired_token_cannot_be_revived_or_started(postgres_sandbox) -> None:
    outbox = seed_outbox(postgres_sandbox.dsn, effect_id="effect-expired")
    queue = PostgresEffectQueue(postgres_sandbox.dsn)
    queue.init_schema()
    reserved = queue.reserve(
        lease_request(
            outbox,
            token="token-expired",
            expiry=T1,
        )
    )
    with pytest.raises(LeaseConflict, match="expired"):
        queue.activate(reserved.lease_token, activated_at=T1)
