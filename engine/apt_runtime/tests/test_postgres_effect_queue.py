"""Real-PostgreSQL parity contracts for the Slice 2 effect queue.

# KG: apt-tpa-legion-engine-canon-2026-06-12
# Design: ADRs/apt-vnext-slice2-effect-runtime-2026-07-14.md
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from engine.apt_runtime.adapters.postgres_effect_queue import PostgresEffectQueue
from engine.apt_runtime.adapters.postgres_store import PostgresEventStore
from engine.apt_runtime.domain.effect_runtime import (
    ReconciliationOutcome,
    ResourceAccess,
    ResourceClaim,
    RuntimeBudget,
    RuntimeUsage,
    progress_signature,
)
from engine.apt_runtime.domain.events import EventType
from engine.apt_runtime.ports.effect_queue import (
    LeaseConflict,
    LeaseNotFound,
    LeaseRequest,
    LeaseStatus,
    ReconciliationProbeConclusion,
    ReconciliationProbeConflict,
    ResourceClaimConflict,
)
from engine.apt_runtime.ports.event_store import OutboxRecord
from engine.apt_runtime.tests.test_sqlite_store import event, receipt


T0 = "2026-07-14T00:00:00Z"
T1 = "2026-07-14T00:00:01Z"
T2 = "2026-07-14T00:00:02Z"
T3 = "2026-07-14T00:00:03Z"
T4 = "2026-07-14T00:00:04Z"
T5 = "2026-07-14T00:00:05Z"
EXPIRY = "2026-07-14T00:01:00Z"
EXTENDED_EXPIRY = "2026-07-14T00:02:00Z"
BUDGET = RuntimeBudget(
    max_attempts=4,
    max_runtime_seconds=600,
    max_cost_units=100,
    max_no_progress=3,
)
WRITE_CLAIM = (
    ResourceClaim(resource_key="artifact://shared/output", access=ResourceAccess.EXCLUSIVE_WRITE),
)
GRANT_REF = "grant://effect-runtime/config-v1"
GRANT_HASH = "a" * 64
CONFIG_VERSION = "config-v1"
AUTHORIZATION_REF = "authorization://effect-runtime"
AUTHORIZATION_HASH = "b" * 64


def seed_outbox(
    dsn: str,
    *,
    stream_id: str = "cycle-pg-effect",
    effect_id: str = "effect-pg-runtime",
) -> OutboxRecord:
    """Commit one canonical EffectQueued/outbox pair into an isolated schema."""

    store = PostgresEventStore(dsn)
    store.init_schema()
    command = receipt(
        f"command-{effect_id}",
        stream_id=stream_id,
    )
    queued = event(
        1,
        command.command_id,
        stream_id=stream_id,
        event_id=f"event-{effect_id}",
        event_type=EventType.EFFECT_QUEUED,
        effect_id=effect_id,
    )
    outbox = OutboxRecord.create(
        outbox_id=f"outbox-{effect_id}",
        stream_id=stream_id,
        effect_id=effect_id,
        command_id=command.command_id,
        payload=dict(queued.payload),
        created_at=T0,
    )
    store.append(stream_id, 0, [queued], [outbox], command)
    store.close()
    return outbox


def lease_request(
    outbox: OutboxRecord,
    *,
    token: str = "lease-token-1",
    owner: str = "worker-a",
    claims: tuple[ResourceClaim, ...] = WRITE_CLAIM,
    claimed_at: str = T0,
    expiry: str = EXPIRY,
) -> LeaseRequest:
    return LeaseRequest(
        outbox=outbox,
        lease_token=token,
        lease_owner=owner,
        claimed_at=claimed_at,
        lease_expiry=expiry,
        resource_claims=claims,
        budget=BUDGET,
        grant_ref=GRANT_REF,
        grant_hash=GRANT_HASH,
        config_version=CONFIG_VERSION,
        authorization_ref=AUTHORIZATION_REF,
        authorization_hash=AUTHORIZATION_HASH,
    )


@pytest.fixture
def queue_and_outbox(postgres_sandbox):
    outbox = seed_outbox(postgres_sandbox.dsn)
    queue = PostgresEffectQueue(postgres_sandbox.dsn)
    queue.init_schema()
    try:
        yield queue, outbox
    finally:
        queue.close()


def test_postgres_effect_lifecycle_usage_and_reconnect(queue_and_outbox, postgres_sandbox) -> None:
    queue, outbox = queue_and_outbox
    assert queue.usage_for_outbox(outbox.outbox_id) == RuntimeUsage()

    reserved = queue.reserve(lease_request(outbox))
    assert reserved.status is LeaseStatus.RESERVED
    assert reserved.lease_epoch == 1
    active = queue.activate(reserved.lease_token, activated_at=T1)
    assert active.status is LeaseStatus.ACTIVE
    assert active.heartbeat_at == T1
    renewed = queue.heartbeat(
        reserved.lease_token,
        lease_owner="worker-a",
        heartbeat_at=T2,
        lease_expiry=EXTENDED_EXPIRY,
    )
    assert renewed.lease_expiry == EXTENDED_EXPIRY
    running = queue.start(
        reserved.lease_token,
        lease_owner="worker-a",
        attempt=1,
        started_at=T3,
    )
    assert running.status is LeaseStatus.RUNNING
    signature = progress_signature({"artifact": "v1"})
    usage = queue.record_usage(
        reserved.lease_token,
        delta=RuntimeUsage(
            attempts=1,
            runtime_seconds=7,
            cost_units=2,
            progress_signature=signature,
        ),
        observed_at=T4,
    )
    assert usage == RuntimeUsage(
        attempts=1,
        runtime_seconds=7,
        cost_units=2,
        progress_signature=signature,
    )
    reconciling = queue.mark_reconciling(
        reserved.lease_token,
        observed_at=T4,
        reconciliation_ref="reconcile://attempt/1",
        reason="provider response unknown",
    )
    assert reconciling.status is LeaseStatus.RECONCILING
    revised = queue.mark_reconciling(
        reserved.lease_token,
        observed_at=T5,
        reconciliation_ref="reconcile://attempt/1/poll-2",
        reason="provider still unknown",
    )
    assert revised.reconciliation_ref.endswith("poll-2")
    finished = queue.finish(
        reserved.lease_token,
        status=LeaseStatus.SUCCEEDED,
        completed_at="2026-07-14T00:00:06Z",
        reconciliation_ref="reconcile://attempt/1/poll-2",
    )
    assert finished.status is LeaseStatus.SUCCEEDED

    reopened = PostgresEffectQueue(postgres_sandbox.dsn)
    try:
        reopened.init_schema()
        assert reopened.load(reserved.lease_token) == finished
        assert reopened.latest_for_outbox(outbox.outbox_id) == finished
        assert reopened.usage_for_outbox(outbox.outbox_id) == usage
    finally:
        reopened.close()


def test_postgres_retry_epoch_preserves_claims_budget_and_advances_attempt(
    queue_and_outbox,
) -> None:
    queue, outbox = queue_and_outbox
    first = queue.reserve(lease_request(outbox))
    queue.activate(first.lease_token, activated_at=T1)
    queue.start(first.lease_token, lease_owner="worker-a", attempt=1, started_at=T2)
    queue.finish(
        first.lease_token,
        status=LeaseStatus.FAILED,
        completed_at=T3,
        reason="transient provider failure",
    )

    second = queue.reserve(
        lease_request(outbox, token="lease-token-2", claimed_at=T4, expiry=EXTENDED_EXPIRY)
    )
    assert second.lease_epoch == 2
    assert second.attempt == 0
    assert second.grant_hash == first.grant_hash
    assert second.authorization_hash == first.authorization_hash
    queue.activate(second.lease_token, activated_at=T5)
    with pytest.raises(LeaseConflict, match="not newer"):
        queue.start(
            second.lease_token, lease_owner="worker-a", attempt=1, started_at="2026-07-14T00:00:06Z"
        )
    assert (
        queue.start(
            second.lease_token,
            lease_owner="worker-a",
            attempt=2,
            started_at="2026-07-14T00:00:06Z",
        ).attempt
        == 2
    )


def test_postgres_retry_rejects_every_execution_grant_change(queue_and_outbox) -> None:
    queue, outbox = queue_and_outbox
    first = queue.reserve(lease_request(outbox))
    queue.activate(first.lease_token, activated_at=T1)
    queue.finish(
        first.lease_token,
        status=LeaseStatus.ABANDONED,
        completed_at=T2,
        reason="confirmed not applied",
    )
    base = lease_request(outbox, token="lease-token-2", claimed_at=T3)
    changed_requests = (
        replace(base, grant_ref="grant://effect-runtime/config-v2"),
        replace(base, grant_hash="c" * 64),
        replace(base, config_version="config-v2"),
        replace(base, authorization_ref="authorization://effect-runtime/v2"),
        replace(base, authorization_hash="d" * 64),
    )
    for changed in changed_requests:
        with pytest.raises(LeaseConflict, match="execution grant"):
            queue.reserve(changed)


def test_postgres_pre_event_orphan_does_not_pin_execution_authority(
    queue_and_outbox,
) -> None:
    queue, outbox = queue_and_outbox
    wrong_claim = ResourceClaim(
        resource_key="artifact://wrong/output",
        access=ResourceAccess.EXCLUSIVE_WRITE,
    )
    wrong = replace(
        lease_request(outbox, claims=(wrong_claim,)),
        budget=RuntimeBudget(
            max_attempts=2,
            max_runtime_seconds=30,
            max_cost_units=10,
            max_no_progress=2,
            max_reconciliation_probes=2,
        ),
        grant_ref="grant://wrong/config",
        grant_hash="f" * 64,
        config_version="config-wrong",
        authorization_ref="authorization://wrong",
        authorization_hash="e" * 64,
    )
    orphan = queue.reserve(wrong)
    queue.finish(
        orphan.lease_token,
        status=LeaseStatus.ABANDONED,
        completed_at=T1,
        reason="pre-event reservation was orphaned",
    )

    valid = queue.reserve(
        lease_request(
            outbox,
            token="lease-token-valid",
            claimed_at=T2,
            expiry=EXTENDED_EXPIRY,
        )
    )
    assert valid.lease_epoch == 2
    assert valid.resource_claims == WRITE_CLAIM
    assert valid.config_version == CONFIG_VERSION


def test_postgres_pre_event_orphan_cannot_unpin_activated_authority(
    queue_and_outbox,
) -> None:
    queue, outbox = queue_and_outbox
    first = queue.reserve(lease_request(outbox))
    queue.activate(first.lease_token, activated_at=T1)
    queue.finish(
        first.lease_token,
        status=LeaseStatus.FAILED,
        completed_at=T2,
        reason="known first attempt failure",
    )
    orphan = queue.reserve(
        lease_request(
            outbox,
            token="lease-token-orphan",
            claimed_at=T3,
            expiry=EXTENDED_EXPIRY,
        )
    )
    queue.finish(
        orphan.lease_token,
        status=LeaseStatus.ABANDONED,
        completed_at=T4,
        reason="second reservation orphaned before activation",
    )
    changed = replace(
        lease_request(
            outbox,
            token="lease-token-changed",
            claimed_at=T5,
            expiry=EXTENDED_EXPIRY,
        ),
        config_version="config-attacker",
    )

    with pytest.raises(LeaseConflict, match="execution grant"):
        queue.reserve(changed)


def test_postgres_exact_outbox_and_absorbing_terminal_fences(queue_and_outbox) -> None:
    queue, outbox = queue_and_outbox
    divergent = OutboxRecord.create(
        outbox_id=outbox.outbox_id,
        stream_id=outbox.stream_id,
        effect_id=outbox.effect_id,
        command_id=outbox.command_id,
        payload={**outbox.payload, "provider": "other-provider"},
        created_at=outbox.created_at,
    )
    with pytest.raises(LeaseConflict, match="differs"):
        queue.reserve(replace(lease_request(outbox), outbox=divergent))

    reserved = queue.reserve(lease_request(outbox))
    cancelled = queue.finish(
        reserved.lease_token,
        status=LeaseStatus.CANCELLED,
        completed_at=T1,
        reason="cycle cancelled",
    )
    assert (
        queue.finish(
            reserved.lease_token,
            status=LeaseStatus.CANCELLED,
            completed_at=T1,
            reason="cycle cancelled",
        )
        == cancelled
    )
    with pytest.raises(LeaseConflict, match="absorbing"):
        queue.reserve(lease_request(outbox, token="lease-token-after-cancel"))
    with pytest.raises(LeaseNotFound):
        queue.usage_for_outbox("missing-outbox")


def test_postgres_resource_claims_are_retained_through_reconciliation(
    postgres_sandbox,
) -> None:
    first_outbox = seed_outbox(postgres_sandbox.dsn, effect_id="effect-resource-a")
    second_outbox = seed_outbox(
        postgres_sandbox.dsn,
        stream_id="cycle-pg-effect-b",
        effect_id="effect-resource-b",
    )
    queue = PostgresEffectQueue(postgres_sandbox.dsn)
    queue.init_schema()
    first = queue.reserve(lease_request(first_outbox, token="token-resource-a"))
    queue.activate(first.lease_token, activated_at=T1)
    queue.start(first.lease_token, lease_owner="worker-a", attempt=1, started_at=T2)
    queue.mark_reconciling(
        first.lease_token,
        observed_at=T3,
        reconciliation_ref="reconcile://resource-a",
        reason="unknown write",
    )
    with pytest.raises(ResourceClaimConflict):
        queue.reserve(lease_request(second_outbox, token="token-resource-b"))
    queue.finish(
        first.lease_token,
        status=LeaseStatus.ABANDONED,
        completed_at=T4,
        reconciliation_ref="reconcile://resource-a",
        reason="confirmed not applied",
    )
    assert (
        queue.reserve(lease_request(second_outbox, token="token-resource-b", claimed_at=T5)).status
        is LeaseStatus.RESERVED
    )


def test_postgres_recoverable_uses_expiry_or_stale_heartbeat(queue_and_outbox) -> None:
    queue, outbox = queue_and_outbox
    reserved = queue.reserve(lease_request(outbox))
    assert queue.recoverable(observed_at=T1, heartbeat_before="2026-07-13T23:59:59Z") == ()
    assert queue.recoverable(
        observed_at="2026-07-14T00:01:00Z",
        heartbeat_before="2026-07-13T23:59:59Z",
    ) == (reserved,)
    assert queue.recoverable(observed_at=T1, heartbeat_before=T0) == (reserved,)


def test_postgres_probe_takeover_and_conclusion_match_sqlite_fencing(
    queue_and_outbox,
) -> None:
    queue, outbox = queue_and_outbox
    lease = queue.reserve(lease_request(outbox))
    queue.activate(lease.lease_token, activated_at=T1)
    queue.start(lease.lease_token, lease_owner="worker-a", attempt=1, started_at=T2)
    queue.mark_reconciling(
        lease.lease_token,
        observed_at=T3,
        reconciliation_ref="reconcile://postgres/initial",
        reason="unknown provider outcome",
    )
    first = queue.begin_reconciliation_probe(
        lease.lease_token,
        permit_token="pg-permit",
        acquired_at=T4,
        expires_at=T5,
    )
    assert first.charged and first.usage.reconciliation_probes == 1
    with pytest.raises(ReconciliationProbeConflict, match="unexpired"):
        queue.begin_reconciliation_probe(
            lease.lease_token,
            permit_token="pg-permit-concurrent",
            acquired_at="2026-07-14T00:00:04.5Z",
            expires_at="2026-07-14T00:00:06Z",
        )
    takeover = queue.begin_reconciliation_probe(
        lease.lease_token,
        permit_token="pg-permit",
        acquired_at=T5,
        expires_at="2026-07-14T00:00:07Z",
    )
    assert not takeover.charged
    assert takeover.usage.reconciliation_probes == 1
    assert takeover.permit.generation == first.permit.generation + 1
    with pytest.raises(ReconciliationProbeConflict, match="fenced"):
        queue.conclude_reconciliation_probe(
            lease.lease_token,
            permit=first.permit,
            concluded_at="2026-07-14T00:00:04Z",
            expires_at="2026-07-14T00:00:06Z",
            conclusion=ReconciliationProbeConclusion(
                outcome=ReconciliationOutcome.UNKNOWN,
                evidence_refs=("evidence://postgres/old",),
                reason="late old result",
            ),
            reconciliation_ref="evidence://postgres/old",
            reason="late old result",
        )
    sealed = queue.conclude_reconciliation_probe(
        lease.lease_token,
        permit=takeover.permit,
        concluded_at="2026-07-14T00:00:06Z",
        expires_at="2026-07-14T00:00:08Z",
        conclusion=ReconciliationProbeConclusion(
            outcome=ReconciliationOutcome.UNKNOWN,
            evidence_refs=("evidence://postgres/current",),
            reason="still unknown",
        ),
        reconciliation_ref="evidence://postgres/current",
        reason="still unknown",
    )
    assert sealed.probe_permit is not None
    with pytest.raises(ReconciliationProbeConflict, match="awaits durable finalization"):
        queue.begin_reconciliation_probe(
            lease.lease_token,
            permit_token="pg-after-conclusion",
            acquired_at="2026-07-14T00:00:09Z",
            expires_at="2026-07-14T00:00:10Z",
        )
    finalized = queue.mark_reconciling(
        lease.lease_token,
        observed_at="2026-07-14T00:00:06Z",
        reconciliation_ref="evidence://postgres/current",
        reason="still unknown",
        probe_permit=sealed.probe_permit,
    )
    assert finalized.probe_permit is None
