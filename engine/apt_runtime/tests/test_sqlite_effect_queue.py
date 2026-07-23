"""Contract tests for the SQLite Slice 2 effect queue.

# KG: apt-tpa-legion-engine-canon-2026-06-12
# Design: ADRs/apt-vnext-slice2-effect-runtime-2026-07-14.md
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from engine.apt_runtime.adapters.sqlite_effect_queue import SqliteEffectQueue
from engine.apt_runtime.adapters.sqlite_store import SqliteEventStore
from engine.apt_runtime.domain.canonical import canonical_sha256
from engine.apt_runtime.domain.commands import CanonicalCommandEnvelope
from engine.apt_runtime.domain.effect_runtime import (
    ResourceAccess,
    ResourceClaim,
    RuntimeBudget,
    RuntimeUsage,
    progress_signature,
)
from engine.apt_runtime.domain.events import EventEnvelope, EventType
from engine.apt_runtime.domain.fsm_spec import load_default_spec
from engine.apt_runtime.ports.effect_queue import (
    LeaseConflict,
    LeaseNotFound,
    LeaseRequest,
    LeaseStatus,
    ResourceClaimConflict,
)
from engine.apt_runtime.ports.event_store import CommandReceiptDraft, OutboxRecord


NOW = "2026-07-14T00:00:00Z"
SPEC = load_default_spec()
BUDGET = RuntimeBudget(
    max_attempts=4,
    max_runtime_seconds=120,
    max_cost_units=100,
    max_no_progress=3,
)


@pytest.fixture
def queue_database(tmp_path: Path):
    database = tmp_path / "effect-runtime.sqlite3"
    store = SqliteEventStore(database)
    store.init_schema()
    store.close()
    queue = SqliteEffectQueue(database)
    queue.init_schema()
    try:
        yield database, queue
    finally:
        queue.close()


def append_outbox(database: Path, suffix: str) -> OutboxRecord:
    """Append one real immutable EffectQueued/outbox pair on its own stream."""

    stream_id = f"cycle-{suffix}"
    effect_id = f"effect-{suffix}"
    command_id = f"command-{suffix}"
    payload = {
        "capability": "artifact.realize",
        "provider": "fake-hades",
        "risk_class": "LOCAL_REVERSIBLE",
        "idempotency_key": f"idem-{suffix}",
        "input_ref": f"artifact://input/{suffix}",
        "input_hash": canonical_sha256({"input": suffix}),
    }
    command = CanonicalCommandEnvelope(
        command_id=command_id,
        command_type="QueueEffect",
        schema_version="1.0.0",
        cycle_id=stream_id,
        expected_version=0,
        actor="test",
        authorization_context={"role": "test"},
        correlation_id=f"correlation-{suffix}",
        causation_id=f"causation-{suffix}",
        input={"effect_id": effect_id},
        issued_at=NOW,
    )
    receipt = CommandReceiptDraft.create(
        command=command,
        response={"accepted": True},
        created_at=NOW,
    )
    event = EventEnvelope.create(
        event_id=f"event-{suffix}",
        stream_id=stream_id,
        stream_version=1,
        event_type=EventType.EFFECT_QUEUED,
        schema_version="1.0.0",
        fsm_spec_hash=SPEC.spec_hash,
        cycle_id=stream_id,
        work_item_id=f"work-{suffix}",
        effect_id=effect_id,
        generation=1,
        actor="test",
        correlation_id=f"correlation-{suffix}",
        causation_id=f"causation-{suffix}",
        command_id=command_id,
        config_version="config-v1",
        payload=payload,
        created_at=NOW,
    )
    outbox = OutboxRecord.create(
        outbox_id=f"outbox-{suffix}",
        stream_id=stream_id,
        effect_id=effect_id,
        command_id=command_id,
        payload=payload,
        created_at=NOW,
    )
    store = SqliteEventStore(database)
    store.init_schema()
    store.append(stream_id, 0, [event], [outbox], receipt)
    store.close()
    return outbox


def lease_request(
    outbox: OutboxRecord,
    token: str,
    *,
    owner: str = "worker-a",
    claimed_at: str = "2026-07-14T00:00:01Z",
    expiry: str = "2026-07-14T00:01:00Z",
    claims: tuple[ResourceClaim, ...] = (),
    budget: RuntimeBudget = BUDGET,
) -> LeaseRequest:
    authorization_ref = f"authorization://{outbox.effect_id}"
    authorization_hash = canonical_sha256(
        {"effect_id": outbox.effect_id, "authorization_ref": authorization_ref}
    )
    grant_ref = f"grant://{outbox.effect_id}/config-v1"
    return LeaseRequest(
        outbox=outbox,
        lease_token=token,
        lease_owner=owner,
        claimed_at=claimed_at,
        lease_expiry=expiry,
        resource_claims=claims,
        budget=budget,
        grant_ref=grant_ref,
        grant_hash=canonical_sha256(
            {
                "effect_id": outbox.effect_id,
                "grant_ref": grant_ref,
                "authorization_hash": authorization_hash,
            }
        ),
        config_version="config-v1",
        authorization_ref=authorization_ref,
        authorization_hash=authorization_hash,
    )


def run_lease(queue: SqliteEffectQueue, token: str, *, attempt: int = 1) -> None:
    queue.activate(token, activated_at="2026-07-14T00:00:02Z")
    queue.start(
        token,
        lease_owner="worker-a",
        attempt=attempt,
        started_at="2026-07-14T00:00:03Z",
    )


def test_reserve_activate_heartbeat_start_finish_and_reopen_roundtrip(
    queue_database,
) -> None:
    database, queue = queue_database
    outbox = append_outbox(database, "roundtrip")
    claim = ResourceClaim("artifact://output/roundtrip", ResourceAccess.EXCLUSIVE_WRITE)

    reserved = queue.reserve(lease_request(outbox, "lease-roundtrip", claims=(claim,)))
    assert reserved.status is LeaseStatus.RESERVED
    assert reserved.lease_epoch == 1
    assert reserved.grant_ref == "grant://effect-roundtrip/config-v1"
    assert len(reserved.grant_hash) == 64
    assert reserved.config_version == "config-v1"
    assert reserved.authorization_ref == "authorization://effect-roundtrip"
    assert len(reserved.authorization_hash) == 64
    assert reserved.budget.max_reconciliation_probes == 3
    assert queue.latest_for_outbox(outbox.outbox_id) == reserved

    active = queue.activate("lease-roundtrip", activated_at="2026-07-14T00:00:02Z")
    assert active.status is LeaseStatus.ACTIVE
    renewed = queue.heartbeat(
        "lease-roundtrip",
        lease_owner="worker-a",
        heartbeat_at="2026-07-14T00:00:10Z",
        lease_expiry="2026-07-14T00:02:00Z",
    )
    assert renewed.heartbeat_at == "2026-07-14T00:00:10Z"
    running = queue.start(
        "lease-roundtrip",
        lease_owner="worker-a",
        attempt=1,
        started_at="2026-07-14T00:00:11Z",
    )
    assert running.status is LeaseStatus.RUNNING
    done = queue.finish(
        "lease-roundtrip",
        status=LeaseStatus.SUCCEEDED,
        completed_at="2026-07-14T00:00:12Z",
    )
    assert done.status is LeaseStatus.SUCCEEDED

    queue.close()
    reopened = SqliteEffectQueue(database)
    reopened.init_schema()
    try:
        assert reopened.load("lease-roundtrip") == done
        assert reopened.latest_for_outbox(outbox.outbox_id) == done
    finally:
        reopened.close()


def test_duplicate_delivery_is_fenced_and_terminal_success_is_absorbing(
    queue_database,
) -> None:
    database, queue = queue_database
    outbox = append_outbox(database, "duplicate")
    request = lease_request(outbox, "lease-duplicate")
    assert queue.reserve(request) == queue.load("lease-duplicate")
    with pytest.raises(LeaseConflict, match="already has RESERVED"):
        queue.reserve(replace(request, lease_token="lease-other"))

    run_lease(queue, "lease-duplicate")
    succeeded = queue.finish(
        "lease-duplicate",
        status=LeaseStatus.SUCCEEDED,
        completed_at="2026-07-14T00:00:04Z",
    )
    assert (
        queue.finish(
            "lease-duplicate",
            status=LeaseStatus.SUCCEEDED,
            completed_at="2026-07-14T00:00:04Z",
        )
        == succeeded
    )
    with pytest.raises(LeaseConflict, match="SUCCEEDED"):
        queue.reserve(replace(request, lease_token="lease-after-success"))


def test_failed_retry_increments_epoch_and_requires_newer_attempt(queue_database) -> None:
    database, queue = queue_database
    outbox = append_outbox(database, "retry")
    queue.reserve(lease_request(outbox, "lease-retry-1"))
    run_lease(queue, "lease-retry-1", attempt=1)
    queue.finish(
        "lease-retry-1",
        status=LeaseStatus.FAILED,
        completed_at="2026-07-14T00:00:04Z",
        reason="provider rejected request",
    )

    with pytest.raises(LeaseConflict, match="claimed_at cannot precede"):
        queue.reserve(
            lease_request(
                outbox,
                "lease-retry-stale-clock",
                claimed_at="2026-07-14T00:00:03Z",
                expiry="2026-07-14T00:02:00Z",
            )
        )

    changed_grant = replace(
        lease_request(
            outbox,
            "lease-retry-changed-grant",
            claimed_at="2026-07-14T00:00:05Z",
            expiry="2026-07-14T00:02:00Z",
        ),
        config_version="config-v2",
    )
    with pytest.raises(LeaseConflict, match="execution grant cannot change"):
        queue.reserve(changed_grant)

    second = queue.reserve(
        lease_request(
            outbox,
            "lease-retry-2",
            claimed_at="2026-07-14T00:00:05Z",
            expiry="2026-07-14T00:02:00Z",
        )
    )
    assert second.lease_epoch == 2
    queue.activate("lease-retry-2", activated_at="2026-07-14T00:00:06Z")
    with pytest.raises(LeaseConflict, match="not newer"):
        queue.start(
            "lease-retry-2",
            lease_owner="worker-a",
            attempt=1,
            started_at="2026-07-14T00:00:07Z",
        )
    assert (
        queue.start(
            "lease-retry-2",
            lease_owner="worker-a",
            attempt=2,
            started_at="2026-07-14T00:00:07Z",
        ).attempt
        == 2
    )


def test_pre_event_abandoned_reservation_does_not_pin_execution_grant(
    queue_database,
) -> None:
    database, queue = queue_database
    outbox = append_outbox(database, "orphan-grant")
    wrong_claim = ResourceClaim("repo://wrong", ResourceAccess.EXCLUSIVE_WRITE)
    wrong = replace(
        lease_request(outbox, "lease-orphan-wrong", claims=(wrong_claim,)),
        budget=RuntimeBudget(
            max_attempts=2,
            max_runtime_seconds=30,
            max_cost_units=10,
            max_no_progress=2,
            max_reconciliation_probes=2,
        ),
        grant_ref="grant://wrong",
        grant_hash="f" * 64,
        config_version="config-wrong",
        authorization_ref="authorization://wrong",
        authorization_hash="e" * 64,
    )
    queue.reserve(wrong)
    queue.finish(
        wrong.lease_token,
        status=LeaseStatus.ABANDONED,
        completed_at="2026-07-14T00:00:02Z",
        reason="pre-event reservation was orphaned",
    )
    valid_claim = ResourceClaim("repo://valid", ResourceAccess.EXCLUSIVE_WRITE)

    valid = queue.reserve(
        lease_request(
            outbox,
            "lease-orphan-valid",
            claimed_at="2026-07-14T00:00:03Z",
            expiry="2026-07-14T00:02:00Z",
            claims=(valid_claim,),
        )
    )

    assert valid.lease_epoch == 2
    assert valid.resource_claims == (valid_claim,)
    assert valid.config_version == "config-v1"


def test_pre_event_orphan_cannot_unpin_an_activated_epoch_grant(queue_database) -> None:
    database, queue = queue_database
    outbox = append_outbox(database, "activated-grant-baseline")
    queue.reserve(lease_request(outbox, "lease-activated-baseline-1"))
    run_lease(queue, "lease-activated-baseline-1")
    queue.finish(
        "lease-activated-baseline-1",
        status=LeaseStatus.FAILED,
        completed_at="2026-07-14T00:00:04Z",
        reason="known first attempt failure",
    )
    queue.reserve(
        lease_request(
            outbox,
            "lease-activated-baseline-orphan",
            claimed_at="2026-07-14T00:00:05Z",
            expiry="2026-07-14T00:02:00Z",
        )
    )
    queue.finish(
        "lease-activated-baseline-orphan",
        status=LeaseStatus.ABANDONED,
        completed_at="2026-07-14T00:00:06Z",
        reason="second reservation orphaned before activation",
    )
    changed = replace(
        lease_request(
            outbox,
            "lease-activated-baseline-changed",
            claimed_at="2026-07-14T00:00:07Z",
            expiry="2026-07-14T00:02:00Z",
        ),
        config_version="config-attacker",
    )

    with pytest.raises(LeaseConflict, match="execution grant cannot change"):
        queue.reserve(changed)


def test_shared_claims_coexist_but_exclusive_claims_serialize_globally(
    queue_database,
) -> None:
    database, queue = queue_database
    first = append_outbox(database, "shared-a")
    second = append_outbox(database, "shared-b")
    writer = append_outbox(database, "writer")
    shared = ResourceClaim("repo://shared", ResourceAccess.SHARED_READ)
    exclusive = ResourceClaim("repo://shared", ResourceAccess.EXCLUSIVE_WRITE)

    queue.reserve(lease_request(first, "lease-shared-a", claims=(shared,)))
    queue.reserve(lease_request(second, "lease-shared-b", claims=(shared,)))
    with pytest.raises(ResourceClaimConflict, match="repo://shared"):
        queue.reserve(lease_request(writer, "lease-writer", claims=(exclusive,)))

    queue.finish(
        "lease-shared-a",
        status=LeaseStatus.ABANDONED,
        completed_at="2026-07-14T00:00:02Z",
        reason="unused reservation",
    )
    queue.finish(
        "lease-shared-b",
        status=LeaseStatus.ABANDONED,
        completed_at="2026-07-14T00:00:02Z",
        reason="unused reservation",
    )
    assert queue.reserve(
        lease_request(writer, "lease-writer", claims=(exclusive,))
    ).resource_claims == (exclusive,)


def test_reconciling_unknown_retains_exclusive_claim_until_settled(queue_database) -> None:
    database, queue = queue_database
    uncertain = append_outbox(database, "unknown")
    next_write = append_outbox(database, "next-write")
    exclusive = ResourceClaim("provider://account/7", ResourceAccess.EXCLUSIVE_WRITE)
    queue.reserve(lease_request(uncertain, "lease-unknown", claims=(exclusive,)))
    run_lease(queue, "lease-unknown")
    reconciling = queue.mark_reconciling(
        "lease-unknown",
        observed_at="2026-07-14T00:02:00Z",
        reconciliation_ref="reconcile://unknown/1",
        reason="provider response was lost",
    )
    assert reconciling.status is LeaseStatus.RECONCILING
    deferred_again = queue.mark_reconciling(
        "lease-unknown",
        observed_at="2026-07-14T00:02:01Z",
        reconciliation_ref="reconcile://unknown/2",
        reason="reconciliation remained unknown",
    )
    assert deferred_again.reconciliation_ref == "reconcile://unknown/2"
    assert deferred_again.reason == "reconciliation remained unknown"
    with pytest.raises(LeaseConflict, match="journal occurred_at cannot precede"):
        queue.mark_reconciling(
            "lease-unknown",
            observed_at="2026-07-14T00:02:00.500Z",
            reconciliation_ref="reconcile://unknown/stale",
            reason="stale reconciliation observation",
        )
    assert queue.load("lease-unknown") == deferred_again
    with pytest.raises(ResourceClaimConflict):
        queue.reserve(lease_request(next_write, "lease-next", claims=(exclusive,)))

    queue.finish(
        "lease-unknown",
        status=LeaseStatus.ABANDONED,
        completed_at="2026-07-14T00:02:02Z",
        reconciliation_ref="reconcile://unknown/2",
        reason="confirmed not applied",
    )
    assert (
        queue.reserve(lease_request(next_write, "lease-next", claims=(exclusive,))).status
        is LeaseStatus.RESERVED
    )


def test_usage_accumulates_across_retry_epochs_and_is_journaled(queue_database) -> None:
    database, queue = queue_database
    outbox = append_outbox(database, "usage")
    assert queue.usage_for_outbox(outbox.outbox_id) == RuntimeUsage()
    queue.reserve(lease_request(outbox, "lease-usage-1"))
    run_lease(queue, "lease-usage-1")
    signature = progress_signature({"step": "same"})
    first = queue.record_usage(
        "lease-usage-1",
        delta=RuntimeUsage(
            attempts=1,
            runtime_seconds=7,
            cost_units=2,
            progress_signature=signature,
        ),
        observed_at="2026-07-14T00:00:04Z",
    )
    assert first == RuntimeUsage(
        attempts=1,
        runtime_seconds=7,
        cost_units=2,
        no_progress=0,
        progress_signature=signature,
    )
    queue.finish(
        "lease-usage-1",
        status=LeaseStatus.FAILED,
        completed_at="2026-07-14T00:00:05Z",
        reason="retryable provider failure",
    )
    queue.reserve(
        lease_request(
            outbox,
            "lease-usage-2",
            claimed_at="2026-07-14T00:00:06Z",
            expiry="2026-07-14T00:02:00Z",
        )
    )
    queue.activate("lease-usage-2", activated_at="2026-07-14T00:00:07Z")
    queue.start(
        "lease-usage-2",
        lease_owner="worker-a",
        attempt=2,
        started_at="2026-07-14T00:00:08Z",
    )
    accumulated = queue.record_usage(
        "lease-usage-2",
        delta=RuntimeUsage(
            attempts=1,
            runtime_seconds=5,
            cost_units=3,
            progress_signature=signature,
        ),
        observed_at="2026-07-14T00:00:09Z",
    )
    assert accumulated == RuntimeUsage(
        attempts=2,
        runtime_seconds=12,
        cost_units=5,
        no_progress=1,
        progress_signature=signature,
    )
    assert queue.usage_for_outbox(outbox.outbox_id) == accumulated


def test_reconciliation_probe_usage_is_durable_and_hashed(queue_database) -> None:
    database, queue = queue_database
    outbox = append_outbox(database, "probe-usage")
    token = "lease-probe-usage"
    queue.reserve(lease_request(outbox, token))
    run_lease(queue, token)
    queue.mark_reconciling(
        token,
        observed_at="2026-07-14T00:00:04Z",
        reconciliation_ref="reconcile://probe/1",
        reason="external result unknown",
    )

    usage = queue.record_usage(
        token,
        delta=RuntimeUsage(reconciliation_probes=1),
        observed_at="2026-07-14T00:00:05Z",
    )

    assert usage.reconciliation_probes == 1
    assert queue.usage_for_outbox(outbox.outbox_id) == usage


def test_recoverable_includes_expired_or_stale_nonterminal_only(queue_database) -> None:
    database, queue = queue_database
    expired = append_outbox(database, "expired")
    stale = append_outbox(database, "stale")
    healthy = append_outbox(database, "healthy")
    terminal = append_outbox(database, "terminal")
    queue.reserve(lease_request(expired, "lease-expired", expiry="2026-07-14T00:00:05Z"))
    queue.reserve(lease_request(stale, "lease-stale", expiry="2026-07-14T00:03:00Z"))
    queue.reserve(
        lease_request(
            healthy,
            "lease-healthy",
            claimed_at="2026-07-14T00:01:30Z",
            expiry="2026-07-14T00:03:00Z",
        )
    )
    queue.reserve(lease_request(terminal, "lease-terminal"))
    queue.finish(
        "lease-terminal",
        status=LeaseStatus.ABANDONED,
        completed_at="2026-07-14T00:00:02Z",
        reason="recovery abandoned orphan reservation",
    )

    recoverable = queue.recoverable(
        observed_at="2026-07-14T00:01:00Z",
        heartbeat_before="2026-07-14T00:00:30Z",
    )
    assert {item.lease_token for item in recoverable} == {
        "lease-expired",
        "lease-stale",
    }


def test_recoverable_compares_fractional_timestamps_chronologically(queue_database) -> None:
    database, queue = queue_database
    outbox = append_outbox(database, "fractional-expiry")
    queue.reserve(
        lease_request(
            outbox,
            "lease-fractional-expiry",
            claimed_at="2026-07-14T00:00:00Z",
            expiry="2026-07-14T00:00:01.500Z",
        )
    )
    assert (
        queue.recoverable(
            observed_at="2026-07-14T00:00:01Z",
            heartbeat_before="2026-07-13T23:59:59Z",
        )
        == ()
    )
    assert (
        queue.recoverable(
            observed_at="2026-07-14T00:00:01.500Z",
            heartbeat_before="2026-07-13T23:59:59Z",
        )[0].lease_token
        == "lease-fractional-expiry"
    )


def test_exact_outbox_request_and_known_outbox_are_required(queue_database) -> None:
    database, queue = queue_database
    outbox = append_outbox(database, "exact")
    mismatched = OutboxRecord.create(
        outbox_id=outbox.outbox_id,
        stream_id=outbox.stream_id,
        effect_id=outbox.effect_id,
        command_id=outbox.command_id,
        payload={**outbox.payload, "provider": "different-provider"},
        created_at=outbox.created_at,
    )
    with pytest.raises(LeaseConflict, match="exactly match"):
        queue.reserve(lease_request(mismatched, "lease-mismatch"))
    with pytest.raises(LeaseNotFound):
        queue.usage_for_outbox("missing-outbox")


def test_owner_fencing_expiry_and_legal_transition_guards(queue_database) -> None:
    database, queue = queue_database
    outbox = append_outbox(database, "guards")
    queue.reserve(lease_request(outbox, "lease-guards", expiry="2026-07-14T00:00:10Z"))
    with pytest.raises(LeaseConflict, match="cannot start RESERVED"):
        queue.start(
            "lease-guards",
            lease_owner="worker-a",
            attempt=1,
            started_at="2026-07-14T00:00:02Z",
        )
    queue.activate("lease-guards", activated_at="2026-07-14T00:00:02Z")
    with pytest.raises(LeaseConflict, match="does not hold"):
        queue.heartbeat(
            "lease-guards",
            lease_owner="worker-b",
            heartbeat_at="2026-07-14T00:00:03Z",
            lease_expiry="2026-07-14T00:00:20Z",
        )
    with pytest.raises(LeaseConflict, match="expired"):
        queue.start(
            "lease-guards",
            lease_owner="worker-a",
            attempt=1,
            started_at="2026-07-14T00:00:10Z",
        )
    with pytest.raises(LeaseConflict, match="cannot finish ACTIVE.*SUCCEEDED"):
        queue.finish(
            "lease-guards",
            status=LeaseStatus.SUCCEEDED,
            completed_at="2026-07-14T00:00:11Z",
        )
