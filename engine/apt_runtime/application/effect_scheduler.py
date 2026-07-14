"""Lease-gated execution and reconciliation for Slice 2 effects.

External execution is unreachable until ``EffectLeased`` and ``EffectStarted``
are durable.  An uncertain provider observation retains resource claims and can
advance only through evidence-backed reconciliation; it is never blind-retried.

# KG: apt-tpa-legion-engine-canon-2026-06-12
# Design: ADRs/apt-vnext-slice2-effect-runtime-2026-07-14.md
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from engine.apt_runtime.domain.canonical import CanonicalValue, canonical_sha256
from engine.apt_runtime.domain.effect_runtime import (
    EffectExecutionGrant,
    ExecutionOutcome,
    RuntimeBudget,
    RuntimeUsage,
    evaluate_budget,
)
from engine.apt_runtime.domain.events import EventType
from engine.apt_runtime.domain.fsm_spec import FsmSpec
from engine.apt_runtime.domain.reducer import replay
from engine.apt_runtime.domain.state import AptCycleState, EffectLifecycle, EffectState
from engine.apt_runtime.ports.effect_queue import (
    EffectQueue,
    LeaseRecord,
    LeaseRequest,
    LeaseStatus,
)
from engine.apt_runtime.ports.effects import (
    Clock,
    EffectCancellationAuthorization,
    EffectCancellationVerifier,
    EffectExecutionRequest,
    EffectExecutionResult,
    EffectExecutor,
    EffectGrantVerifier,
    EffectReconciler,
    EffectResultStore,
    IdGenerator,
    StoredEffectResult,
)
from engine.apt_runtime.ports.event_store import EventStore, OutboxRecord

from ._effect_runtime_support import (
    _correlation_id,
    _execution_usage_delta,
    _grant_matches,
    _lease_is_expired,
    _reconciliation_ref,
    _require_canonical_lease,
    _require_heartbeat_extension,
    _require_initial_deadline,
    _require_live_lease,
    _require_queue_chronology,
    _provider_matches,
    _same_identity,
    _unknown_usage_delta,
    _verify_outbox_effect,
    _with_canonical_attempts,
)
from .effect_facts import EffectFactWriter
from .effect_reconciliation import (
    EffectReconciliationCoordinator,
    EffectReconciliationObservation,
    ReconciliationAction,
)
from .effect_runtime_errors import (
    BudgetExhaustedError,
    EffectRuntimeStateError,
    EffectSchedulerError,
    ProviderIdentityError,
    ProviderInvocationError,
)


@dataclass(frozen=True, slots=True)
class EffectExecutionObservation:
    """Provider result plus its durable queue projection and accumulated usage."""

    result: EffectExecutionResult
    lease: LeaseRecord
    usage: RuntimeUsage


class EffectScheduler:
    """Coordinate canonical effect facts, operational leases, and providers."""

    def __init__(
        self,
        store: EventStore,
        queue: EffectQueue,
        spec: FsmSpec,
        clock: Clock,
        ids: IdGenerator,
        result_store: EffectResultStore,
        grant_verifier: EffectGrantVerifier,
        cancellation_verifier: EffectCancellationVerifier,
        *,
        reconciliation_probe_ttl_seconds: int,
    ) -> None:
        if not isinstance(store, EventStore):
            raise EffectSchedulerError("store must implement EventStore")
        if not isinstance(queue, EffectQueue):
            raise EffectSchedulerError("queue must implement EffectQueue")
        if not isinstance(spec, FsmSpec):
            raise EffectSchedulerError("spec must be an FsmSpec")
        if not isinstance(clock, Clock):
            raise EffectSchedulerError("clock must implement Clock")
        if not isinstance(ids, IdGenerator):
            raise EffectSchedulerError("ids must implement IdGenerator")
        if not isinstance(result_store, EffectResultStore):
            raise EffectSchedulerError("result_store must implement EffectResultStore")
        if not isinstance(grant_verifier, EffectGrantVerifier):
            raise EffectSchedulerError("grant_verifier must implement EffectGrantVerifier")
        if not isinstance(cancellation_verifier, EffectCancellationVerifier):
            raise EffectSchedulerError(
                "cancellation_verifier must implement EffectCancellationVerifier"
            )
        self._store = store
        self._queue = queue
        self._spec = spec
        self._clock = clock
        self._ids = ids
        self._result_store = result_store
        self._grant_verifier = grant_verifier
        self._cancellation_verifier = cancellation_verifier
        self._facts = EffectFactWriter(store, spec)
        self._reconciliation = EffectReconciliationCoordinator(
            store,
            queue,
            spec,
            clock,
            self._facts,
            result_store,
            ids,
            reconciliation_probe_ttl_seconds=reconciliation_probe_ttl_seconds,
        )

    def lease(
        self,
        outbox: OutboxRecord,
        *,
        lease_owner: str,
        lease_expiry: str,
        grant: EffectExecutionGrant,
    ) -> LeaseRecord:
        """Reserve claims, commit ``EffectLeased``, then open the execution barrier."""

        if not isinstance(outbox, OutboxRecord):
            raise EffectSchedulerError("outbox must be an OutboxRecord")
        state = self._load_state(outbox.stream_id)
        try:
            effect = state.effect(outbox.effect_id)
        except KeyError as exc:
            raise EffectRuntimeStateError(f"unknown effect_id {outbox.effect_id!r}") from exc
        if effect.lifecycle is not EffectLifecycle.PENDING:
            raise EffectRuntimeStateError("only a canonical PENDING effect may be leased")
        _verify_outbox_effect(outbox, effect)
        if not isinstance(grant, EffectExecutionGrant):
            raise EffectSchedulerError("grant must be an EffectExecutionGrant")
        if not self._grant_verifier.verify(grant):
            raise EffectRuntimeStateError(
                "execution grant failed trusted authorization verification"
            )
        if not _grant_matches(effect, state.cycle_id, state.config_version, grant):
            raise EffectRuntimeStateError("execution grant differs from the canonical effect")
        usage = _with_canonical_attempts(
            self._queue.usage_for_outbox(outbox.outbox_id), effect.current_attempt
        )
        self._raise_if_exhausted(grant.budget, usage)
        claimed_at = self._clock.now_utc()
        _require_initial_deadline(claimed_at, lease_expiry, grant.budget)
        token = self._ids.new_id(f"effect-lease:{outbox.stream_id}:{outbox.effect_id}")
        record = self._queue.reserve(
            LeaseRequest(
                outbox=outbox,
                lease_token=token,
                lease_owner=lease_owner,
                claimed_at=claimed_at,
                lease_expiry=lease_expiry,
                resource_claims=grant.resource_claims,
                budget=grant.budget,
                grant_ref=grant.grant_ref,
                grant_hash=grant.grant_hash,
                config_version=grant.config_version,
                authorization_ref=grant.authorization_ref,
                authorization_hash=grant.authorization_hash,
            )
        )
        self._facts.append(
            cycle_id=record.stream_id,
            effect_id=record.effect_id,
            event_type=EventType.EFFECT_LEASED,
            payload={
                "lease_owner": record.lease_owner,
                "lease_token": record.lease_token,
                "lease_expiry": record.lease_expiry,
                "grant_ref": record.grant_ref,
                "grant_hash": record.grant_hash,
                "config_version": record.config_version,
                "authorization_ref": record.authorization_ref,
                "authorization_hash": record.authorization_hash,
            },
            occurred_at=claimed_at,
            actor=record.lease_owner,
            correlation_id=outbox.command_id,
            causation_id=outbox.outbox_id,
        )
        return self._queue.activate(record.lease_token, activated_at=claimed_at)

    def heartbeat(
        self,
        lease_token: str,
        *,
        lease_owner: str,
        lease_expiry: str,
    ) -> LeaseRecord:
        """Commit the canonical heartbeat before renewing the queue projection."""

        record = self._require_lease(lease_token, {LeaseStatus.ACTIVE, LeaseStatus.RUNNING})
        if lease_owner != record.lease_owner:
            raise EffectRuntimeStateError("heartbeat lease_owner does not hold the fenced lease")
        state = self._load_state(record.stream_id)
        effect = state.effect(record.effect_id)
        expected = (
            EffectLifecycle.LEASED
            if record.status is LeaseStatus.ACTIVE
            else EffectLifecycle.RUNNING
        )
        _require_canonical_lease(effect, record, expected)
        if record.config_version != state.config_version:
            raise EffectRuntimeStateError("queue config_version differs from the canonical cycle")
        heartbeat_at = self._clock.now_utc()
        _require_live_lease(record, heartbeat_at, "heartbeat")
        _require_heartbeat_extension(
            record,
            heartbeat_at=heartbeat_at,
            lease_expiry=lease_expiry,
        )
        self._facts.append(
            cycle_id=record.stream_id,
            effect_id=record.effect_id,
            event_type=EventType.EFFECT_HEARTBEAT_RECORDED,
            payload={
                "lease_owner": lease_owner,
                "lease_token": lease_token,
                "heartbeat_at": heartbeat_at,
                "lease_expiry": lease_expiry,
            },
            occurred_at=heartbeat_at,
            actor=lease_owner,
            correlation_id=_correlation_id(record),
            causation_id=lease_token,
        )
        renewed = self._queue.heartbeat(
            lease_token,
            lease_owner=lease_owner,
            heartbeat_at=heartbeat_at,
            lease_expiry=lease_expiry,
        )
        _require_live_lease(renewed, self._clock.now_utc(), "complete heartbeat")
        return renewed

    def execute(
        self,
        lease_token: str,
        *,
        input: Mapping[str, CanonicalValue],
        executor: EffectExecutor,
    ) -> EffectExecutionObservation:
        """Start one fenced attempt and converge its known or uncertain outcome."""

        if not isinstance(executor, EffectExecutor):
            raise EffectSchedulerError("executor must implement EffectExecutor")
        record = self._require_lease(lease_token, {LeaseStatus.ACTIVE})
        state = self._load_state(record.stream_id)
        effect = state.effect(record.effect_id)
        _require_canonical_lease(effect, record, EffectLifecycle.LEASED)
        if record.config_version != state.config_version:
            raise EffectRuntimeStateError("queue config_version differs from the canonical cycle")
        if not _provider_matches(executor, effect):
            raise ProviderIdentityError(
                "executor provider/capability/risk descriptor does not match the effect grant"
            )
        usage = _with_canonical_attempts(
            self._queue.usage_for_outbox(record.outbox_id), effect.current_attempt
        )
        self._raise_if_exhausted(record.budget, usage)
        attempt = effect.current_attempt + 1
        request = EffectExecutionRequest(
            cycle_id=record.stream_id,
            effect_id=record.effect_id,
            capability=effect.capability,
            provider=effect.provider,
            risk_class=effect.risk_class,
            idempotency_key=effect.idempotency_key,
            input_hash=effect.input_hash,
            lease_token=lease_token,
            attempt=attempt,
            input=input,
        )
        started_at = self._clock.now_utc()
        _require_live_lease(record, started_at, "start")
        self._facts.append(
            cycle_id=record.stream_id,
            effect_id=record.effect_id,
            event_type=EventType.EFFECT_STARTED,
            payload={"attempt": attempt, "lease_token": lease_token},
            occurred_at=started_at,
            actor=record.lease_owner,
            correlation_id=_correlation_id(record),
            causation_id=lease_token,
        )
        running = self._queue.start(
            lease_token,
            lease_owner=record.lease_owner,
            attempt=attempt,
            started_at=started_at,
        )
        usage = self._queue.record_usage(
            lease_token,
            delta=RuntimeUsage(attempts=1),
            observed_at=started_at,
        )
        dispatch_at = self._clock.now_utc()
        try:
            _require_live_lease(running, dispatch_at, "invoke provider")
        except EffectRuntimeStateError:
            if _lease_is_expired(running, dispatch_at):
                self._record_unknown(
                    running,
                    attempt=attempt,
                    observed_at=dispatch_at,
                    reason="lease expired after the start barrier and before provider invocation",
                    evidence_refs=(),
                )
            raise
        try:
            result = executor.execute(request)
        except Exception as exc:
            completed_at = self._clock.now_utc()
            delta = _unknown_usage_delta(record, attempt, type(exc).__name__)
            usage = self._queue.record_usage(lease_token, delta=delta, observed_at=completed_at)
            self._record_unknown(
                running,
                attempt=attempt,
                observed_at=completed_at,
                reason=f"provider raised {type(exc).__name__}",
                evidence_refs=(),
            )
            raise ProviderInvocationError(
                "provider invocation raised; outcome retained for reconciliation"
            ) from exc
        if not isinstance(result, EffectExecutionResult) or not _same_identity(request, result):
            completed_at = self._clock.now_utc()
            delta = _unknown_usage_delta(record, attempt, "identity-mismatch")
            self._queue.record_usage(lease_token, delta=delta, observed_at=completed_at)
            self._record_unknown(
                running,
                attempt=attempt,
                observed_at=completed_at,
                reason="provider returned a mismatched execution identity",
                evidence_refs=(),
            )
            raise ProviderIdentityError(
                "provider result does not match the fenced execution request"
            )
        completed_at = self._clock.now_utc()
        usage = self._queue.record_usage(
            lease_token,
            delta=_execution_usage_delta(result.usage_delta),
            observed_at=completed_at,
        )
        latest = self._load_effect(record.stream_id, record.effect_id)
        if latest.lifecycle is EffectLifecycle.CANCELLED:
            lease = self._record_post_cancel_result(running, result, completed_at)
            return EffectExecutionObservation(result=result, lease=lease, usage=usage)
        if latest.lifecycle is not EffectLifecycle.RUNNING or latest.lease_token != lease_token:
            self._queue.mark_reconciling(
                lease_token,
                observed_at=completed_at,
                reconciliation_ref=_reconciliation_ref(
                    running, result.attempt, result.evidence_refs
                ),
                reason="canonical effect changed while the provider was executing",
            )
            raise EffectRuntimeStateError(
                "canonical effect changed while the provider was executing"
            )
        lease = self._record_execution_result(running, result, completed_at)
        return EffectExecutionObservation(result=result, lease=lease, usage=usage)

    def reconcile(
        self, lease_token: str, *, reconciler: EffectReconciler
    ) -> EffectReconciliationObservation:
        """Resolve an uncertain attempt; only ``NOT_APPLIED`` may authorize retry."""

        return self._reconciliation.reconcile(lease_token, reconciler=reconciler)

    def cancel(
        self,
        lease_token: str,
        *,
        authorization: EffectCancellationAuthorization,
    ) -> LeaseRecord:
        """Make effect cancellation canonical before releasing any claims."""

        if not isinstance(authorization, EffectCancellationAuthorization):
            raise EffectSchedulerError("authorization must be an EffectCancellationAuthorization")
        if not self._cancellation_verifier.verify(authorization):
            raise EffectRuntimeStateError("cancellation authorization failed trusted verification")

        record = self._require_lease(
            lease_token,
            {
                LeaseStatus.RESERVED,
                LeaseStatus.ACTIVE,
                LeaseStatus.RUNNING,
                LeaseStatus.RECONCILING,
            },
        )
        if authorization.effect_id != record.effect_id:
            raise EffectRuntimeStateError(
                "cancellation authorization is bound to a different effect"
            )
        if authorization.cycle_id != record.stream_id:
            raise EffectRuntimeStateError(
                "cancellation authorization is bound to a different cycle"
            )
        occurred_at = self._clock.now_utc()
        _require_queue_chronology(record, occurred_at, "cancel")
        self._facts.append(
            cycle_id=record.stream_id,
            effect_id=record.effect_id,
            event_type=EventType.EFFECT_CANCELLED,
            payload={
                "reason": authorization.reason,
                "authorization_ref": authorization.authorization_ref,
                "authorization_hash": authorization.authorization_hash,
            },
            occurred_at=occurred_at,
            actor=authorization.actor,
            correlation_id=_correlation_id(record),
            causation_id=lease_token,
            authorization_context={
                "cycle_id": authorization.cycle_id,
                "effect_id": authorization.effect_id,
                "authorization_ref": authorization.authorization_ref,
                "authorization_hash": authorization.authorization_hash,
            },
        )
        current = self._queue.load(lease_token)
        if current is None:
            raise EffectRuntimeStateError("cancelled lease disappeared from the queue")
        effect = self._load_effect(current.stream_id, current.effect_id)
        current_started = bool(
            effect.attempts and effect.attempts[-1].lease_token == current.lease_token
        )
        if not current_started:
            return self._queue.finish(
                lease_token,
                status=LeaseStatus.CANCELLED,
                completed_at=occurred_at,
                reason=authorization.reason,
            )
        if current.status is LeaseStatus.RECONCILING:
            return current
        return self._queue.mark_reconciling(
            lease_token,
            observed_at=occurred_at,
            reconciliation_ref=_reconciliation_ref(current, max(current.attempt, 1), ()),
            reason=(
                f"canonical cancellation requires outcome reconciliation: {authorization.reason}"
            ),
        )

    def _record_execution_result(
        self,
        record: LeaseRecord,
        result: EffectExecutionResult,
        completed_at: str,
    ) -> LeaseRecord:
        common = {
            "attempt": result.attempt,
            "lease_token": result.lease_token,
        }
        if result.outcome is ExecutionOutcome.SUCCEEDED:
            assert result.result is not None
            try:
                stored = self._persist_result(record, result.attempt, result.result)
            except Exception as exc:
                self._record_unknown(
                    record,
                    attempt=result.attempt,
                    observed_at=completed_at,
                    reason="provider result could not be durably persisted and verified",
                    evidence_refs=result.evidence_refs,
                )
                raise ProviderInvocationError(
                    "provider succeeded but durable result persistence failed"
                ) from exc
            try:
                self._facts.append(
                    cycle_id=record.stream_id,
                    effect_id=record.effect_id,
                    event_type=EventType.EFFECT_SUCCEEDED,
                    payload={
                        **common,
                        "result_ref": stored.result_ref,
                        "result_hash": stored.result_hash,
                    },
                    occurred_at=completed_at,
                    actor=record.lease_owner,
                    correlation_id=_correlation_id(record),
                    causation_id=record.lease_token,
                )
            except Exception:
                latest = self._load_effect(record.stream_id, record.effect_id)
                if latest.lifecycle is EffectLifecycle.CANCELLED:
                    return self._record_post_cancel_result(
                        record,
                        result,
                        completed_at,
                        stored=stored,
                    )
                raise
            return self._queue.finish(
                record.lease_token,
                status=LeaseStatus.SUCCEEDED,
                completed_at=completed_at,
            )
        if result.outcome is ExecutionOutcome.FAILED:
            assert result.reason is not None
            reconciliation_ref = _reconciliation_ref(record, result.attempt, result.evidence_refs)
            self._facts.append(
                cycle_id=record.stream_id,
                effect_id=record.effect_id,
                event_type=EventType.EFFECT_FAILED,
                payload={**common, "reason": result.reason},
                occurred_at=completed_at,
                actor=record.lease_owner,
                correlation_id=_correlation_id(record),
                causation_id=record.lease_token,
            )
            return self._queue.mark_reconciling(
                record.lease_token,
                observed_at=completed_at,
                reconciliation_ref=reconciliation_ref,
                reason=result.reason,
            )
        assert result.reason is not None
        return self._record_unknown(
            record,
            attempt=result.attempt,
            observed_at=completed_at,
            reason=result.reason,
            evidence_refs=result.evidence_refs,
        )

    def _record_unknown(
        self,
        record: LeaseRecord,
        *,
        attempt: int,
        observed_at: str,
        reason: str,
        evidence_refs: tuple[str, ...],
    ) -> LeaseRecord:
        current = self._queue.load(record.lease_token)
        if current is None:
            raise EffectRuntimeStateError("uncertain lease disappeared before timeout commit")
        effect = self._load_effect(current.stream_id, current.effect_id)
        if effect.heartbeat_at is None or effect.lease_expiry is None:
            raise EffectRuntimeStateError("canonical running effect lacks lease chronology")
        reconciliation_ref = _reconciliation_ref(current, attempt, evidence_refs)
        self._facts.append(
            cycle_id=record.stream_id,
            effect_id=record.effect_id,
            event_type=EventType.EFFECT_TIMED_OUT,
            payload={
                "attempt": attempt,
                "lease_token": current.lease_token,
                "reconciliation_ref": reconciliation_ref,
                "expected_heartbeat_at": effect.heartbeat_at,
                "expected_lease_expiry": effect.lease_expiry,
            },
            occurred_at=observed_at,
            actor=current.lease_owner,
            correlation_id=_correlation_id(current),
            causation_id=current.lease_token,
        )
        return self._queue.mark_reconciling(
            current.lease_token,
            observed_at=observed_at,
            reconciliation_ref=reconciliation_ref,
            reason=reason,
        )

    def _record_post_cancel_result(
        self,
        record: LeaseRecord,
        result: EffectExecutionResult,
        observed_at: str,
        *,
        stored: StoredEffectResult | None = None,
    ) -> LeaseRecord:
        current = self._queue.load(record.lease_token)
        if current is None:
            raise EffectRuntimeStateError("cancelled lease disappeared before result evidence")
        if current.probe_permit is not None:
            return current
        reconciliation_ref = _reconciliation_ref(current, result.attempt, result.evidence_refs)
        detail = result.outcome.value
        if result.outcome is ExecutionOutcome.SUCCEEDED:
            assert result.result is not None
            if stored is None:
                try:
                    stored = self._persist_result(current, result.attempt, result.result)
                except Exception:
                    detail += "; durable result persistence failed"
            if stored is not None:
                reconciliation_ref = stored.result_ref
                detail += f"; durable result {stored.result_ref}"
        return self._queue.mark_reconciling(
            current.lease_token,
            observed_at=observed_at,
            reconciliation_ref=reconciliation_ref,
            reason=(
                "provider returned after canonical cancellation: "
                f"{detail}; reconciliation/compensation required"
            ),
        )

    def _persist_result(
        self,
        record: LeaseRecord,
        attempt: int,
        result: Mapping[str, CanonicalValue],
    ) -> StoredEffectResult:
        stored = self._result_store.persist(
            record.stream_id,
            record.effect_id,
            attempt,
            result,
        )
        expected_hash = canonical_sha256(result)
        if (
            not isinstance(stored, StoredEffectResult)
            or stored.result_hash != expected_hash
            or not self._result_store.verify(stored)
        ):
            raise EffectRuntimeStateError(
                "result store did not return a verified canonical result identity"
            )
        return stored

    def _require_lease(self, lease_token: str, allowed: set[LeaseStatus]) -> LeaseRecord:
        record = self._queue.load(lease_token)
        if record is None:
            raise EffectRuntimeStateError(f"unknown lease token {lease_token!r}")
        if record.status not in allowed:
            expected = ", ".join(sorted(status.value for status in allowed))
            raise EffectRuntimeStateError(
                f"lease {lease_token!r} must be one of [{expected}], got {record.status.value}"
            )
        return record

    def _load_effect(self, cycle_id: str, effect_id: str) -> EffectState:
        try:
            return self._load_state(cycle_id).effect(effect_id)
        except KeyError as exc:
            raise EffectRuntimeStateError(f"unknown effect_id {effect_id!r}") from exc

    def _load_state(self, cycle_id: str) -> AptCycleState:
        history = tuple(self._store.load(cycle_id))
        if not history:
            raise EffectRuntimeStateError(f"cycle {cycle_id!r} has no canonical history")
        return replay(history, self._spec)

    @staticmethod
    def _raise_if_exhausted(budget: RuntimeBudget, usage: RuntimeUsage) -> None:
        decision = evaluate_budget(budget, usage)
        if decision.exhausted:
            raise BudgetExhaustedError(decision.limits)


__all__ = [
    "BudgetExhaustedError",
    "EffectExecutionObservation",
    "EffectReconciliationObservation",
    "EffectRuntimeStateError",
    "EffectScheduler",
    "EffectSchedulerError",
    "ProviderIdentityError",
    "ProviderInvocationError",
    "ReconciliationAction",
]
