"""Falsifiers for crash-resumable reconciliation probe generations."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import pytest

from engine.apt_runtime.adapters.sqlite_effect_queue import SqliteEffectQueue
from engine.apt_runtime.adapters.sqlite_store import SqliteEventStore
from engine.apt_runtime.application.effect_runtime_errors import (
    EffectRuntimeStateError,
    ProviderInvocationError,
)
from engine.apt_runtime.application.effect_recovery import EffectRecovery, RecoveryAction
from engine.apt_runtime.application.effect_scheduler import EffectScheduler
from engine.apt_runtime.domain.canonical import CanonicalValue
from engine.apt_runtime.domain.effect_runtime import (
    ExecutionOutcome,
    ReconciliationOutcome,
)
from engine.apt_runtime.domain.state import EffectLifecycle
from engine.apt_runtime.ports.effect_queue import (
    LeaseConflict,
    LeaseStatus,
    ReconciliationProbeConclusion,
    ReconciliationProbeConflict,
    ReconciliationProbePermitState,
)
from engine.apt_runtime.ports.effects import StoredEffectResult
from engine.apt_runtime.tests.test_effect_scheduler import (
    AllowTestGrants,
    InMemoryResultStore,
    ReturningExecutor,
    ReturningReconciler,
    SequentialIds,
    SPEC,
    VerifyTestCancellations,
    _cancel_authorization,
    _lease,
    _open_runtime,
    _state,
)
from engine.apt_runtime.tests.test_sqlite_effect_queue import (
    append_outbox,
    lease_request,
    run_lease,
)


@pytest.fixture
def queue_database(tmp_path: Path):
    database = tmp_path / "probe-fencing.sqlite3"
    store = SqliteEventStore(database)
    store.init_schema()
    store.close()
    queue = SqliteEffectQueue(database)
    queue.init_schema()
    try:
        yield database, queue
    finally:
        queue.close()


def test_expired_probe_takeover_is_generation_fenced_and_not_double_charged(
    queue_database,
) -> None:
    database, queue = queue_database
    outbox = append_outbox(database, "probe-fence")
    token = "lease-probe-fence"
    queue.reserve(lease_request(outbox, token))
    run_lease(queue, token)
    queue.mark_reconciling(
        token,
        observed_at="2026-07-14T00:00:04Z",
        reconciliation_ref="reconciliation://initial",
        reason="unknown provider outcome",
    )

    first = queue.begin_reconciliation_probe(
        token,
        permit_token="permit-nonce",
        acquired_at="2026-07-14T00:00:05Z",
        expires_at="2026-07-14T00:00:10Z",
    )
    assert first.charged
    assert first.usage.reconciliation_probes == 1
    with pytest.raises(ReconciliationProbeConflict, match="unexpired"):
        queue.begin_reconciliation_probe(
            token,
            permit_token="permit-concurrent",
            acquired_at="2026-07-14T00:00:06Z",
            expires_at="2026-07-14T00:00:11Z",
        )

    takeover = queue.begin_reconciliation_probe(
        token,
        permit_token="permit-nonce",
        acquired_at="2026-07-14T00:00:10Z",
        expires_at="2026-07-14T00:00:15Z",
    )
    assert not takeover.charged
    assert takeover.usage.reconciliation_probes == 1
    assert takeover.permit.generation == first.permit.generation + 1

    old_conclusion = ReconciliationProbeConclusion(
        outcome=ReconciliationOutcome.UNKNOWN,
        evidence_refs=("evidence://old",),
        reason="late old observation",
    )
    with pytest.raises(ReconciliationProbeConflict, match="fenced"):
        queue.conclude_reconciliation_probe(
            token,
            permit=first.permit,
            concluded_at="2026-07-14T00:00:09Z",
            expires_at="2026-07-14T00:00:14Z",
            conclusion=old_conclusion,
            reconciliation_ref="evidence://old",
            reason="late old observation",
        )

    conclusion = ReconciliationProbeConclusion(
        outcome=ReconciliationOutcome.UNKNOWN,
        evidence_refs=("evidence://current",),
        reason="still unknown",
    )
    sealed = queue.conclude_reconciliation_probe(
        token,
        permit=takeover.permit,
        concluded_at="2026-07-14T00:00:11Z",
        expires_at="2026-07-14T00:00:16Z",
        conclusion=conclusion,
        reconciliation_ref="evidence://current",
        reason="still unknown",
    )
    assert sealed.probe_permit is not None
    assert sealed.probe_permit.state is ReconciliationProbePermitState.CONCLUDED
    reopened = SqliteEffectQueue(database)
    reopened.init_schema()
    try:
        assert reopened.load(token) == sealed
    finally:
        reopened.close()
    with pytest.raises(ReconciliationProbeConflict, match="awaits durable finalization"):
        queue.begin_reconciliation_probe(
            token,
            permit_token="permit-after-conclusion",
            acquired_at="2026-07-14T00:01:00Z",
            expires_at="2026-07-14T00:01:05Z",
        )
    with pytest.raises(LeaseConflict, match="active or stale"):
        queue.mark_reconciling(
            token,
            observed_at="2026-07-14T00:00:11Z",
            reconciliation_ref="evidence://current",
            reason="still unknown",
        )
    finalized = queue.mark_reconciling(
        token,
        observed_at="2026-07-14T00:00:11Z",
        reconciliation_ref="evidence://current",
        reason="still unknown",
        probe_permit=sealed.probe_permit,
    )
    assert finalized.probe_permit is None


class _FailOnceResultStore(InMemoryResultStore):
    def __init__(self) -> None:
        super().__init__()
        self.failures = 1

    def persist(
        self,
        cycle_id: str,
        effect_id: str,
        attempt: int,
        result: Mapping[str, CanonicalValue],
    ) -> StoredEffectResult:
        if self.failures:
            self.failures -= 1
            raise OSError("transient durable result outage")
        return super().persist(cycle_id, effect_id, attempt, result)


class _CancelDuringPersistStore(InMemoryResultStore):
    def __init__(self) -> None:
        super().__init__()
        self.persist_calls = 0
        self.on_persist = lambda: None

    def persist(
        self,
        cycle_id: str,
        effect_id: str,
        attempt: int,
        result: Mapping[str, CanonicalValue],
    ) -> StoredEffectResult:
        self.persist_calls += 1
        stored = super().persist(cycle_id, effect_id, attempt, result)
        self.on_persist()
        return stored


def _replace_scheduler(runtime, result_store: InMemoryResultStore) -> None:
    runtime.scheduler = EffectScheduler(
        runtime.store,
        runtime.queue,
        SPEC,
        runtime.clock,
        SequentialIds(),
        result_store,
        AllowTestGrants(),
        VerifyTestCancellations(),
        reconciliation_probe_ttl_seconds=60,
    )


def test_applied_persist_failure_takeover_reuses_logical_probe_charge(tmp_path: Path) -> None:
    runtime = _open_runtime(tmp_path / "persist-takeover.sqlite3")
    try:
        store = _FailOnceResultStore()
        _replace_scheduler(runtime, store)
        lease = _lease(runtime)
        runtime.clock.value = "2026-07-14T00:01:00Z"
        runtime.scheduler.execute(
            lease.lease_token,
            input={"artifact": "alpha", "revision": 1},
            executor=ReturningExecutor(ExecutionOutcome.UNKNOWN),
        )
        first = ReturningReconciler(ReconciliationOutcome.APPLIED)
        runtime.clock.value = "2026-07-14T00:02:00Z"
        with pytest.raises(ProviderInvocationError, match="takeover-eligible"):
            runtime.scheduler.reconcile(lease.lease_token, reconciler=first)
        held = runtime.queue.load(lease.lease_token)
        assert held is not None and held.probe_permit is not None
        assert held.probe_permit.state is ReconciliationProbePermitState.ACTIVE
        assert runtime.queue.usage_for_outbox(runtime.outbox.outbox_id).reconciliation_probes == 1

        blocked = ReturningReconciler(ReconciliationOutcome.APPLIED)
        runtime.clock.value = "2026-07-14T00:02:30Z"
        with pytest.raises(EffectRuntimeStateError, match="single-flight"):
            runtime.scheduler.reconcile(lease.lease_token, reconciler=blocked)
        assert blocked.calls == []

        takeover = ReturningReconciler(ReconciliationOutcome.APPLIED)
        runtime.clock.value = "2026-07-14T00:03:00Z"
        observation = runtime.scheduler.reconcile(
            lease.lease_token,
            reconciler=takeover,
        )
        assert observation.lease.status is LeaseStatus.SUCCEEDED
        assert observation.usage.reconciliation_probes == 1
        assert len(first.calls) == len(takeover.calls) == 1
    finally:
        runtime.close()


def test_execution_success_persist_race_with_cancel_keeps_stored_evidence(
    tmp_path: Path,
) -> None:
    runtime = _open_runtime(tmp_path / "success-persist-cancel.sqlite3")
    try:
        store = _CancelDuringPersistStore()
        _replace_scheduler(runtime, store)
        lease = _lease(runtime)
        store.on_persist = lambda: runtime.scheduler.cancel(
            lease.lease_token,
            authorization=_cancel_authorization(),
        )
        runtime.clock.value = "2026-07-14T00:01:00Z"
        observation = runtime.scheduler.execute(
            lease.lease_token,
            input={"artifact": "alpha", "revision": 1},
            executor=ReturningExecutor(ExecutionOutcome.SUCCEEDED),
        )

        assert store.persist_calls == 1
        assert _state(runtime).effect("effect-1").lifecycle is EffectLifecycle.CANCELLED
        assert observation.lease.status is LeaseStatus.RECONCILING
        assert observation.lease.probe_permit is None
        stored_ref = next(iter(store.results))
        assert observation.lease.reconciliation_ref == stored_ref
    finally:
        runtime.close()


def test_concluded_applied_probe_resumes_without_provider_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = _open_runtime(tmp_path / "conclusion-resume.sqlite3")
    try:
        lease = _lease(runtime)
        runtime.clock.value = "2026-07-14T00:01:00Z"
        runtime.scheduler.execute(
            lease.lease_token,
            input={"artifact": "alpha", "revision": 1},
            executor=ReturningExecutor(ExecutionOutcome.UNKNOWN),
        )
        original_finish = runtime.queue.finish

        def crash_before_finish(*args, **kwargs):
            raise RuntimeError("simulated crash after canonical success")

        monkeypatch.setattr(runtime.queue, "finish", crash_before_finish)
        runtime.clock.value = "2026-07-14T00:02:00Z"
        with pytest.raises(RuntimeError, match="simulated crash"):
            runtime.scheduler.reconcile(
                lease.lease_token,
                reconciler=ReturningReconciler(ReconciliationOutcome.APPLIED),
            )
        monkeypatch.setattr(runtime.queue, "finish", original_finish)
        pending = runtime.queue.load(lease.lease_token)
        assert pending is not None and pending.probe_permit is not None
        assert pending.probe_permit.state is ReconciliationProbePermitState.CONCLUDED
        assert _state(runtime).effect("effect-1").lifecycle is EffectLifecycle.SUCCEEDED

        should_not_run = ReturningReconciler(ReconciliationOutcome.UNKNOWN)
        resumed = runtime.scheduler.reconcile(
            lease.lease_token,
            reconciler=should_not_run,
        )
        assert should_not_run.calls == []
        assert resumed.lease.status is LeaseStatus.SUCCEEDED
        assert resumed.lease.probe_permit is None
    finally:
        runtime.close()


def test_concluded_applied_probe_resumes_after_fact_append_crash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = _open_runtime(tmp_path / "conclusion-before-fact.sqlite3")
    try:
        lease = _lease(runtime)
        runtime.clock.value = "2026-07-14T00:01:00Z"
        runtime.scheduler.execute(
            lease.lease_token,
            input={"artifact": "alpha", "revision": 1},
            executor=ReturningExecutor(ExecutionOutcome.UNKNOWN),
        )
        facts = runtime.scheduler._reconciliation._facts
        original_append = facts.append

        def crash_before_fact(**_kwargs):
            raise RuntimeError("simulated crash before canonical success")

        monkeypatch.setattr(facts, "append", crash_before_fact)
        runtime.clock.value = "2026-07-14T00:02:00Z"
        with pytest.raises(RuntimeError, match="before canonical success"):
            runtime.scheduler.reconcile(
                lease.lease_token,
                reconciler=ReturningReconciler(ReconciliationOutcome.APPLIED),
            )
        monkeypatch.setattr(facts, "append", original_append)
        pending = runtime.queue.load(lease.lease_token)
        assert pending is not None and pending.probe_permit is not None
        assert pending.probe_permit.state is ReconciliationProbePermitState.CONCLUDED
        assert _state(runtime).effect("effect-1").lifecycle is EffectLifecycle.TIMED_OUT

        should_not_run = ReturningReconciler(ReconciliationOutcome.UNKNOWN)
        resumed = runtime.scheduler.reconcile(
            lease.lease_token,
            reconciler=should_not_run,
        )
        assert should_not_run.calls == []
        assert resumed.lease.status is LeaseStatus.SUCCEEDED
        assert resumed.lease.probe_permit is None
        assert _state(runtime).effect("effect-1").lifecycle is EffectLifecycle.SUCCEEDED
    finally:
        runtime.close()


def test_cancel_preserves_existing_reconciliation_evidence(tmp_path: Path) -> None:
    runtime = _open_runtime(tmp_path / "cancel-preserves-evidence.sqlite3")
    try:
        lease = _lease(runtime)
        runtime.clock.value = "2026-07-14T00:01:00Z"
        uncertain = runtime.scheduler.execute(
            lease.lease_token,
            input={"artifact": "alpha", "revision": 1},
            executor=ReturningExecutor(ExecutionOutcome.UNKNOWN),
        ).lease
        assert uncertain.status is LeaseStatus.RECONCILING

        runtime.clock.value = "2026-07-14T00:02:00Z"
        cancelled = runtime.scheduler.cancel(
            lease.lease_token,
            authorization=_cancel_authorization(),
        )
        current = runtime.queue.load(lease.lease_token)
        assert current == cancelled
        assert current is not None
        assert current.reconciliation_ref == uncertain.reconciliation_ref
        assert current.reason == uncertain.reason
        assert _state(runtime).effect("effect-1").lifecycle is EffectLifecycle.CANCELLED
    finally:
        runtime.close()


def test_cancelled_started_attempt_waits_for_quiescence_before_probe(tmp_path: Path) -> None:
    runtime = _open_runtime(tmp_path / "cancel-quiescence.sqlite3")
    try:
        lease = _lease(runtime)
        attempted_probe = ReturningReconciler(ReconciliationOutcome.NOT_APPLIED)

        def cancel_while_provider_is_in_flight(_request) -> None:
            runtime.clock.value = "2026-07-14T00:02:00Z"
            cancelled = runtime.scheduler.cancel(
                lease.lease_token,
                authorization=_cancel_authorization(),
            )
            assert cancelled.status is LeaseStatus.RECONCILING
            with pytest.raises(EffectRuntimeStateError, match="before its execution lease expires"):
                runtime.scheduler.reconcile(
                    lease.lease_token,
                    reconciler=attempted_probe,
                )

        runtime.clock.value = "2026-07-14T00:01:00Z"
        late = runtime.scheduler.execute(
            lease.lease_token,
            input={"artifact": "alpha", "revision": 1},
            executor=ReturningExecutor(
                ExecutionOutcome.SUCCEEDED,
                before_return=cancel_while_provider_is_in_flight,
            ),
        )
        assert attempted_probe.calls == []
        assert late.lease.status is LeaseStatus.RECONCILING
        assert _state(runtime).effect("effect-1").lifecycle is EffectLifecycle.CANCELLED
    finally:
        runtime.close()


def test_recovery_distinguishes_live_expired_and_concluded_probe(tmp_path: Path) -> None:
    runtime = _open_runtime(tmp_path / "probe-recovery.sqlite3")
    try:
        lease = _lease(runtime)
        runtime.clock.value = "2026-07-14T00:01:00Z"
        runtime.scheduler.execute(
            lease.lease_token,
            input={"artifact": "alpha", "revision": 1},
            executor=ReturningExecutor(ExecutionOutcome.UNKNOWN),
        )
        first = runtime.queue.begin_reconciliation_probe(
            lease.lease_token,
            permit_token="permit-recovery-1",
            acquired_at="2026-07-14T00:02:00Z",
            expires_at="2026-07-14T00:03:00Z",
        )
        recovery = EffectRecovery(
            runtime.store,
            runtime.queue,
            SPEC,
            runtime.clock,
            heartbeat_stale_after_seconds=1,
        )
        runtime.clock.value = "2026-07-14T00:02:30Z"
        assert recovery.recover()[0].action is RecoveryAction.PROBE_IN_FLIGHT
        runtime.clock.value = "2026-07-14T00:03:00Z"
        assert recovery.recover()[0].action is RecoveryAction.PROBE_TAKEOVER_READY

        takeover = runtime.queue.begin_reconciliation_probe(
            lease.lease_token,
            permit_token="permit-recovery-2",
            acquired_at="2026-07-14T00:03:00Z",
            expires_at="2026-07-14T00:04:00Z",
        )
        sealed = runtime.queue.conclude_reconciliation_probe(
            lease.lease_token,
            permit=takeover.permit,
            concluded_at="2026-07-14T00:03:10Z",
            expires_at="2026-07-14T00:04:10Z",
            conclusion=ReconciliationProbeConclusion(
                outcome=ReconciliationOutcome.UNKNOWN,
                evidence_refs=("evidence://recovery/unknown",),
                reason="provider remains uncertain",
            ),
            reconciliation_ref="evidence://recovery/unknown",
            reason="provider remains uncertain",
        )
        assert sealed.probe_generation == first.permit.generation + 1
        runtime.clock.value = "2026-07-14T00:05:00Z"
        assert recovery.recover()[0].action is RecoveryAction.PROBE_CONCLUSION_PENDING
    finally:
        runtime.close()
