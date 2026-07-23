"""Application-level falsifiers for the Slice 2 effect scheduler.

# KG: apt-tpa-legion-engine-canon-2026-06-12
# Design: ADRs/apt-vnext-slice2-effect-runtime-2026-07-14.md
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, cast

import pytest

from engine.apt_runtime.adapters.sqlite_effect_queue import SqliteEffectQueue
from engine.apt_runtime.adapters.sqlite_store import SqliteEventStore
from engine.apt_runtime.application.effect_reconciliation import ReconciliationAction
from engine.apt_runtime.application.effect_runtime_errors import (
    EffectRuntimeStateError,
    ProviderIdentityError,
    ProviderInvocationError,
)
from engine.apt_runtime.application.effect_scheduler import EffectScheduler
from engine.apt_runtime.domain.canonical import CanonicalValue, canonical_sha256
from engine.apt_runtime.domain.commands import CanonicalCommandEnvelope
from engine.apt_runtime.domain.effect_runtime import (
    ExecutionOutcome,
    EffectExecutionGrant,
    ReconciliationOutcome,
    ResourceAccess,
    ResourceClaim,
    RuntimeBudget,
    RuntimeUsage,
    progress_signature,
)
from engine.apt_runtime.domain.events import EventEnvelope, EventType, GuardResult
from engine.apt_runtime.domain.fsm_spec import load_default_spec
from engine.apt_runtime.domain.reducer import replay
from engine.apt_runtime.domain.state import EffectLifecycle
from engine.apt_runtime.ports.effect_queue import LeaseStatus
from engine.apt_runtime.ports.effects import (
    EffectCancellationAuthorization,
    EffectExecutionRequest,
    EffectExecutionResult,
    EffectReconciliationRequest,
    EffectReconciliationResult,
    StoredEffectResult,
)
from engine.apt_runtime.ports.event_store import CommandReceiptDraft, OutboxRecord


SPEC = load_default_spec()
NOW = "2026-07-14T00:00:00Z"
CYCLE_ID = "cycle-effect-runtime"
INPUT: dict[str, CanonicalValue] = {"artifact": "alpha", "revision": 1}
INPUT_HASH = canonical_sha256(INPUT)
CLAIMS = (ResourceClaim("workspace://repo/artifact", ResourceAccess.EXCLUSIVE_WRITE),)
DEFAULT_BUDGET = RuntimeBudget(5, 3_600, 100, 3)
CANCELLATION_REF = "authorization://effect-1/cancel/operator"


def _grant(
    budget: RuntimeBudget = DEFAULT_BUDGET,
    *,
    cycle_id: str = CYCLE_ID,
) -> EffectExecutionGrant:
    return EffectExecutionGrant(
        grant_ref="grant://effect-1/config-v1",
        cycle_id=cycle_id,
        effect_id="effect-1",
        capability="artifact.realize",
        provider="fake-provider",
        risk_class="REVERSIBLE_WRITE",
        config_version="config-v1",
        resource_claims=CLAIMS,
        budget=budget,
        authorization_ref="authorization://effect-1/operator",
        authorization_hash=_execution_authorization_hash(cycle_id),
    )


def _execution_authorization_hash(cycle_id: str) -> str:
    return canonical_sha256({"cycle_id": cycle_id, "effect_id": "effect-1", "role": "operator"})


def _cancel_authorization(
    *,
    cycle_id: str = CYCLE_ID,
    effect_id: str = "effect-1",
    actor: str = "operator",
    reason: str = "operator cancelled",
) -> EffectCancellationAuthorization:
    authorization_hash = canonical_sha256(
        {
            "cycle_id": cycle_id,
            "effect_id": effect_id,
            "actor": actor,
            "reason": reason,
            "authorization_ref": CANCELLATION_REF,
        }
    )
    return EffectCancellationAuthorization(
        cycle_id=cycle_id,
        effect_id=effect_id,
        actor=actor,
        reason=reason,
        authorization_ref=CANCELLATION_REF,
        authorization_hash=authorization_hash,
    )


class MutableClock:
    def __init__(self, value: str = NOW) -> None:
        self.value = value

    def now_utc(self) -> str:
        return self.value


class SequentialIds:
    def __init__(self) -> None:
        self.counter = 0

    def new_id(self, namespace: str) -> str:
        self.counter += 1
        return f"lease-{self.counter}"


class InMemoryResultStore:
    def __init__(self) -> None:
        self.results: dict[str, tuple[str, Mapping[str, CanonicalValue]]] = {}

    def persist(
        self,
        cycle_id: str,
        effect_id: str,
        attempt: int,
        result: Mapping[str, CanonicalValue],
    ) -> StoredEffectResult:
        result_hash = canonical_sha256(result)
        result_ref = f"memory-result://{cycle_id}/{effect_id}/{attempt}/{result_hash}"
        self.results[result_ref] = (result_hash, result)
        return StoredEffectResult(result_ref, result_hash)

    def verify(self, stored: StoredEffectResult) -> bool:
        value = self.results.get(stored.result_ref)
        return value is not None and value[0] == stored.result_hash

    def load(self, stored: StoredEffectResult) -> Mapping[str, CanonicalValue] | None:
        value = self.results.get(stored.result_ref)
        if value is None or value[0] != stored.result_hash:
            return None
        return value[1]


class AllowTestGrants:
    def verify(self, grant: EffectExecutionGrant) -> bool:
        return grant.authorization_hash == _execution_authorization_hash(grant.cycle_id)


class VerifyTestCancellations:
    def verify(self, authorization: EffectCancellationAuthorization) -> bool:
        expected = canonical_sha256(
            {
                "cycle_id": authorization.cycle_id,
                "effect_id": authorization.effect_id,
                "actor": authorization.actor,
                "reason": authorization.reason,
                "authorization_ref": authorization.authorization_ref,
            }
        )
        return authorization.authorization_hash == expected


@dataclass(slots=True)
class RuntimeHarness:
    store: SqliteEventStore
    queue: SqliteEffectQueue
    scheduler: EffectScheduler
    outbox: OutboxRecord
    clock: MutableClock

    def close(self) -> None:
        self.queue.close()
        self.store.close()


def _event(version: int, event_type: EventType, payload: dict[str, object]) -> EventEnvelope:
    effect = event_type is EventType.EFFECT_QUEUED
    return EventEnvelope.create(
        event_id=f"seed-event-{version}",
        stream_id=CYCLE_ID,
        stream_version=version,
        event_type=event_type,
        schema_version=SPEC.event_schema_versions[0],
        fsm_spec_hash=SPEC.spec_hash,
        cycle_id=CYCLE_ID,
        effect_id="effect-1" if effect else None,
        actor="seed",
        correlation_id="seed-correlation",
        causation_id=f"seed-cause-{version}",
        command_id="seed-command",
        config_version="config-v1",
        payload=payload,
        created_at=NOW,
    )


def _open_runtime(database: Path) -> RuntimeHarness:
    store = SqliteEventStore(database)
    store.init_schema()
    queued_payload: dict[str, object] = {
        "capability": "artifact.realize",
        "provider": "fake-provider",
        "risk_class": "REVERSIBLE_WRITE",
        "idempotency_key": "idem-effect-1",
        "input_ref": "artifact://input/1",
        "input_hash": INPUT_HASH,
    }
    events = (
        _event(
            1,
            EventType.CYCLE_CREATED,
            {
                "config_snapshot_ref": "config://v1",
                "config_snapshot_hash": "a" * 64,
                "canon_snapshot_ref": "kg://snapshot/1",
                "canon_snapshot_hash": "b" * 64,
            },
        ),
        _event(
            2,
            EventType.CYCLE_STARTED,
            {
                "guard_result": GuardResult.PASS.value,
                "guard_evidence_refs": ["evidence://seed/start"],
            },
        ),
        _event(3, EventType.EFFECT_QUEUED, queued_payload),
    )
    outbox = OutboxRecord.create(
        outbox_id="outbox-effect-1",
        stream_id=CYCLE_ID,
        effect_id="effect-1",
        command_id="seed-command",
        payload=queued_payload,
        created_at=NOW,
    )
    command = CanonicalCommandEnvelope(
        command_id="seed-command",
        command_type="SeedActiveEffect",
        schema_version=SPEC.event_schema_versions[0],
        cycle_id=CYCLE_ID,
        expected_version=0,
        actor="seed",
        authorization_context={"authority": "TEST_FIXTURE"},
        correlation_id="seed-correlation",
        causation_id="seed-root",
        input={"effect_id": "effect-1"},
        issued_at=NOW,
    )
    store.append(
        outbox.stream_id,
        0,
        events,
        (outbox,),
        CommandReceiptDraft.create(command=command, response={"seeded": True}, created_at=NOW),
    )
    queue = SqliteEffectQueue(database)
    queue.init_schema()
    clock = MutableClock()
    return RuntimeHarness(
        store,
        queue,
        EffectScheduler(
            store,
            queue,
            SPEC,
            clock,
            SequentialIds(),
            InMemoryResultStore(),
            AllowTestGrants(),
            VerifyTestCancellations(),
            reconciliation_probe_ttl_seconds=60,
        ),
        outbox,
        clock,
    )


@pytest.fixture
def runtime_factory(tmp_path: Path):
    opened: list[RuntimeHarness] = []

    def create(name: str = "runtime.sqlite3") -> RuntimeHarness:
        runtime = _open_runtime(tmp_path / name)
        opened.append(runtime)
        return runtime

    yield create
    for runtime in reversed(opened):
        runtime.close()


def _lease(runtime: RuntimeHarness, budget: RuntimeBudget = DEFAULT_BUDGET):
    return runtime.scheduler.lease(
        runtime.outbox,
        lease_owner="worker-1",
        lease_expiry="2026-07-14T01:00:00Z",
        grant=_grant(budget),
    )


def _usage(signature: str = "provider-progress") -> RuntimeUsage:
    return RuntimeUsage(
        attempts=1,
        runtime_seconds=2,
        cost_units=1,
        progress_signature=progress_signature({"signature": signature}),
    )


class ReturningExecutor:
    def __init__(
        self,
        outcome: ExecutionOutcome,
        *,
        signature: str = "provider-progress",
        before_return: Callable[[EffectExecutionRequest], None] | None = None,
        identity_cycle: str | None = None,
    ) -> None:
        self.outcome = outcome
        self.signature = signature
        self.before_return = before_return
        self.identity_cycle = identity_cycle
        self.calls: list[EffectExecutionRequest] = []

    @property
    def provider(self) -> str:
        return "fake-provider"

    @property
    def capabilities(self) -> frozenset[str]:
        return frozenset({"artifact.realize"})

    @property
    def risk_classes(self) -> frozenset[str]:
        return frozenset({"REVERSIBLE_WRITE"})

    def execute(self, request: EffectExecutionRequest) -> EffectExecutionResult:
        self.calls.append(request)
        if self.before_return is not None:
            self.before_return(request)
        succeeded = self.outcome is ExecutionOutcome.SUCCEEDED
        return EffectExecutionResult(
            cycle_id=self.identity_cycle or request.cycle_id,
            effect_id=request.effect_id,
            capability=request.capability,
            provider=request.provider,
            risk_class=request.risk_class,
            idempotency_key=request.idempotency_key,
            input_hash=request.input_hash,
            lease_token=request.lease_token,
            attempt=request.attempt,
            outcome=self.outcome,
            result={"artifact_ref": "artifact://result/1"} if succeeded else None,
            evidence_refs=(f"evidence://execute/{request.attempt}",),
            reason=None if succeeded else f"provider observed {self.outcome.value}",
            usage_delta=_usage(self.signature),
        )


class RaisingExecutor:
    def __init__(self) -> None:
        self.calls = 0

    provider = "fake-provider"
    capabilities = frozenset({"artifact.realize"})
    risk_classes = frozenset({"REVERSIBLE_WRITE"})

    def execute(self, request: EffectExecutionRequest) -> EffectExecutionResult:
        self.calls += 1
        raise TimeoutError("response lost")


class ReturningReconciler:
    def __init__(self, outcome: ReconciliationOutcome) -> None:
        self.outcome = outcome
        self.calls: list[EffectReconciliationRequest] = []

    provider = "fake-provider"
    capabilities = frozenset({"artifact.realize"})
    risk_classes = frozenset({"REVERSIBLE_WRITE"})

    def reconcile(self, request: EffectReconciliationRequest) -> EffectReconciliationResult:
        self.calls.append(request)
        applied = self.outcome is ReconciliationOutcome.APPLIED
        return EffectReconciliationResult(
            cycle_id=request.cycle_id,
            effect_id=request.effect_id,
            capability=request.capability,
            provider=request.provider,
            risk_class=request.risk_class,
            idempotency_key=request.idempotency_key,
            input_hash=request.input_hash,
            lease_token=request.lease_token,
            attempt=request.attempt,
            outcome=self.outcome,
            result={"artifact_ref": "artifact://reconciled/1"} if applied else None,
            evidence_refs=(f"evidence://reconcile/{self.outcome.value}/{request.attempt}",),
            reason=None if applied else f"reconciliation observed {self.outcome.value}",
        )


def _state(runtime: RuntimeHarness):
    return replay(runtime.store.load(runtime.outbox.stream_id), SPEC)


def test_commit_barrier_precedes_provider_and_success_is_durable(runtime_factory) -> None:
    runtime = runtime_factory()
    lease = _lease(runtime)
    observed: dict[str, object] = {}

    def inspect_barrier(request: EffectExecutionRequest) -> None:
        observed["events"] = tuple(
            event.event_type for event in runtime.store.load(request.cycle_id)
        )
        observed["queue_status"] = runtime.queue.load(request.lease_token).status

    executor = ReturningExecutor(ExecutionOutcome.SUCCEEDED, before_return=inspect_barrier)
    runtime.clock.value = "2026-07-14T00:01:00Z"
    result = runtime.scheduler.execute(lease.lease_token, input=INPUT, executor=executor)

    events = cast(tuple[EventType, ...], observed["events"])
    assert events[-2:] == (EventType.EFFECT_LEASED, EventType.EFFECT_STARTED)
    assert observed["queue_status"] is LeaseStatus.RUNNING
    assert result.lease.status is LeaseStatus.SUCCEEDED
    assert _state(runtime).effect("effect-1").lifecycle is EffectLifecycle.SUCCEEDED


def test_lease_rejects_verified_grant_bound_to_another_cycle(runtime_factory) -> None:
    runtime = runtime_factory()
    other_cycle_grant = _grant(cycle_id="cycle-other")

    assert AllowTestGrants().verify(other_cycle_grant)
    with pytest.raises(EffectRuntimeStateError, match="canonical effect"):
        runtime.scheduler.lease(
            runtime.outbox,
            lease_owner="worker-1",
            lease_expiry="2026-07-14T01:00:00Z",
            grant=other_cycle_grant,
        )


def test_cancellation_requires_verified_effect_bound_authority(runtime_factory) -> None:
    runtime = runtime_factory()
    lease = _lease(runtime)
    valid = _cancel_authorization()
    forged = EffectCancellationAuthorization(
        cycle_id=valid.cycle_id,
        effect_id=valid.effect_id,
        actor=valid.actor,
        reason=valid.reason,
        authorization_ref=valid.authorization_ref,
        authorization_hash="0" * 64,
    )

    with pytest.raises(EffectRuntimeStateError, match="failed trusted verification"):
        runtime.scheduler.cancel(lease.lease_token, authorization=forged)
    with pytest.raises(EffectRuntimeStateError, match="different effect"):
        runtime.scheduler.cancel(
            lease.lease_token,
            authorization=_cancel_authorization(effect_id="effect-other"),
        )
    other_cycle = _cancel_authorization(cycle_id="cycle-other")
    assert VerifyTestCancellations().verify(other_cycle)
    with pytest.raises(EffectRuntimeStateError, match="different cycle"):
        runtime.scheduler.cancel(lease.lease_token, authorization=other_cycle)

    cancelled = runtime.scheduler.cancel(lease.lease_token, authorization=valid)

    assert cancelled.status is LeaseStatus.CANCELLED
    effect = _state(runtime).effect("effect-1")
    assert effect.lifecycle is EffectLifecycle.CANCELLED
    assert effect.reasons[-1] == valid.reason
    event = runtime.store.load(CYCLE_ID)[-1]
    assert event.cycle_id == valid.cycle_id
    assert event.effect_id == valid.effect_id
    assert event.payload["authorization_hash"] == valid.authorization_hash


def test_known_failure_is_reconciled_and_contradictory_applied_is_deferred(
    runtime_factory,
) -> None:
    runtime = runtime_factory()
    lease = _lease(runtime)
    runtime.clock.value = "2026-07-14T00:01:00Z"

    observation = runtime.scheduler.execute(
        lease.lease_token,
        input=INPUT,
        executor=ReturningExecutor(ExecutionOutcome.FAILED),
    )

    assert observation.lease.status is LeaseStatus.RECONCILING
    effect = _state(runtime).effect("effect-1")
    assert effect.lifecycle is EffectLifecycle.FAILED
    assert effect.attempts[-1].outcome.value == "FAILED"
    runtime.clock.value = "2026-07-14T00:02:00Z"
    contradictory = runtime.scheduler.reconcile(
        lease.lease_token,
        reconciler=ReturningReconciler(ReconciliationOutcome.APPLIED),
    )
    assert contradictory.action is ReconciliationAction.DEFERRED
    assert contradictory.lease.status is LeaseStatus.RECONCILING
    assert _state(runtime).effect("effect-1").lifecycle is EffectLifecycle.FAILED
    runtime.clock.value = "2026-07-14T00:03:00Z"
    not_applied = runtime.scheduler.reconcile(
        lease.lease_token,
        reconciler=ReturningReconciler(ReconciliationOutcome.NOT_APPLIED),
    )
    assert not_applied.action is ReconciliationAction.RETRY_QUEUED
    assert _state(runtime).effect("effect-1").lifecycle is EffectLifecycle.PENDING


@pytest.mark.parametrize(
    ("executor_factory", "error"),
    [
        (RaisingExecutor, ProviderInvocationError),
        (
            lambda: ReturningExecutor(ExecutionOutcome.SUCCEEDED, identity_cycle="cycle-wrong"),
            ProviderIdentityError,
        ),
    ],
)
def test_provider_exception_or_identity_mismatch_is_retained_for_reconciliation(
    runtime_factory, executor_factory, error
) -> None:
    runtime = runtime_factory()
    lease = _lease(runtime)
    runtime.clock.value = "2026-07-14T00:01:00Z"

    with pytest.raises(error):
        runtime.scheduler.execute(lease.lease_token, input=INPUT, executor=executor_factory())

    assert runtime.queue.load(lease.lease_token).status is LeaseStatus.RECONCILING
    assert _state(runtime).effect("effect-1").lifecycle is EffectLifecycle.TIMED_OUT
    assert EventType.EFFECT_RETRY_QUEUED not in {
        event.event_type for event in runtime.store.load(runtime.outbox.stream_id)
    }


def test_applied_reconciliation_converges_unknown_execution_to_success(runtime_factory) -> None:
    runtime = runtime_factory()
    lease = _lease(runtime)
    runtime.clock.value = "2026-07-14T00:01:00Z"
    runtime.scheduler.execute(
        lease.lease_token,
        input=INPUT,
        executor=ReturningExecutor(ExecutionOutcome.UNKNOWN),
    )
    runtime.clock.value = "2026-07-14T00:02:00Z"

    observation = runtime.scheduler.reconcile(
        lease.lease_token,
        reconciler=ReturningReconciler(ReconciliationOutcome.APPLIED),
    )

    assert observation.action is ReconciliationAction.SUCCEEDED
    assert observation.lease.status is LeaseStatus.SUCCEEDED
    assert _state(runtime).effect("effect-1").lifecycle is EffectLifecycle.SUCCEEDED


def test_unknown_reconciliation_is_deferred_without_retry(runtime_factory) -> None:
    runtime = runtime_factory()
    lease = _lease(runtime)
    runtime.clock.value = "2026-07-14T00:01:00Z"
    runtime.scheduler.execute(
        lease.lease_token,
        input=INPUT,
        executor=ReturningExecutor(ExecutionOutcome.UNKNOWN),
    )
    runtime.clock.value = "2026-07-14T00:02:00Z"

    observation = runtime.scheduler.reconcile(
        lease.lease_token,
        reconciler=ReturningReconciler(ReconciliationOutcome.UNKNOWN),
    )

    assert observation.action is ReconciliationAction.DEFERRED
    assert observation.lease.status is LeaseStatus.RECONCILING
    assert _state(runtime).effect("effect-1").lifecycle is EffectLifecycle.TIMED_OUT
    assert EventType.EFFECT_RETRY_QUEUED not in {
        event.event_type for event in runtime.store.load(runtime.outbox.stream_id)
    }


def test_only_not_applied_opens_retry_and_old_token_cannot_execute(runtime_factory) -> None:
    runtime = runtime_factory()
    first = _lease(runtime)
    runtime.clock.value = "2026-07-14T00:01:00Z"
    runtime.scheduler.execute(
        first.lease_token,
        input=INPUT,
        executor=ReturningExecutor(ExecutionOutcome.UNKNOWN),
    )
    runtime.clock.value = "2026-07-14T00:02:00Z"
    reconciled = runtime.scheduler.reconcile(
        first.lease_token,
        reconciler=ReturningReconciler(ReconciliationOutcome.NOT_APPLIED),
    )
    assert reconciled.action is ReconciliationAction.RETRY_QUEUED
    assert _state(runtime).effect("effect-1").lifecycle is EffectLifecycle.PENDING

    runtime.clock.value = "2026-07-14T00:03:00Z"
    second = runtime.scheduler.lease(
        runtime.outbox,
        lease_owner="worker-1",
        lease_expiry="2026-07-14T01:00:00Z",
        grant=_grant(),
    )
    stale_executor = ReturningExecutor(ExecutionOutcome.SUCCEEDED)
    with pytest.raises(EffectRuntimeStateError, match="ABANDONED"):
        runtime.scheduler.execute(first.lease_token, input=INPUT, executor=stale_executor)
    assert stale_executor.calls == []
    assert second.lease_epoch == 2
    assert second.lease_token != first.lease_token


def test_repeated_no_progress_cancels_instead_of_opening_another_retry(runtime_factory) -> None:
    runtime = runtime_factory()
    budget = RuntimeBudget(5, 3_600, 100, 1)
    first = _lease(runtime, budget)
    token = first.lease_token
    moments = (
        ("2026-07-14T00:01:00Z", "2026-07-14T00:03:00Z"),
        ("2026-07-14T00:05:00Z", "2026-07-14T00:06:00Z"),
    )
    for index, (executed_at, reconciled_at) in enumerate(moments, start=1):
        runtime.clock.value = executed_at
        runtime.scheduler.execute(
            token,
            input=INPUT,
            executor=ReturningExecutor(ExecutionOutcome.UNKNOWN, signature="no-progress"),
        )
        runtime.clock.value = reconciled_at
        observation = runtime.scheduler.reconcile(
            token,
            reconciler=ReturningReconciler(ReconciliationOutcome.NOT_APPLIED),
        )
        if index == 1:
            assert observation.action is ReconciliationAction.RETRY_QUEUED
            runtime.clock.value = "2026-07-14T00:04:00Z"
            token = runtime.scheduler.lease(
                runtime.outbox,
                lease_owner="worker-1",
                lease_expiry="2026-07-14T01:00:00Z",
                grant=_grant(budget),
            ).lease_token

    assert observation.action is ReconciliationAction.CANCELLED
    assert observation.lease.status is LeaseStatus.CANCELLED
    assert _state(runtime).effect("effect-1").lifecycle is EffectLifecycle.CANCELLED
