"""Evidence-backed recovery of uncertain Slice 2 effect attempts.

``NOT_APPLIED`` is the only observation that can authorize another attempt.
``UNKNOWN`` and reconciliation failures retain the claim and remain deferred.

# KG: apt-tpa-legion-engine-canon-2026-06-12
# Design: ADRs/apt-vnext-slice2-effect-runtime-2026-07-14.md
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

from engine.apt_runtime.domain.canonical import CanonicalValue, canonical_sha256
from engine.apt_runtime.domain.effect_runtime import (
    BudgetLimit,
    ReconciliationOutcome,
    RuntimeUsage,
    evaluate_budget,
)
from engine.apt_runtime.domain.events import EventType, GuardResult
from engine.apt_runtime.domain.fsm_spec import FsmSpec
from engine.apt_runtime.domain.reducer import replay
from engine.apt_runtime.domain.state import EffectLifecycle, EffectState
from engine.apt_runtime.ports.effect_queue import (
    EffectQueue,
    LeaseRecord,
    LeaseStatus,
    ReconciliationProbeConclusion,
    ReconciliationProbeConflict,
    ReconciliationProbeExhausted,
    ReconciliationProbePermit,
    ReconciliationProbePermitState,
)
from engine.apt_runtime.ports.effects import (
    Clock,
    EffectReconciler,
    EffectReconciliationRequest,
    EffectReconciliationResult,
    EffectResultStore,
    IdGenerator,
    StoredEffectResult,
)
from engine.apt_runtime.ports.event_store import EventStore

from ._effect_runtime_support import (
    _correlation_id,
    _provider_matches,
    _require_canonical_grant_binding,
    _same_identity,
    _with_canonical_attempts,
)
from .effect_facts import EffectFactWriter
from .effect_runtime_errors import (
    BudgetExhaustedError,
    EffectRuntimeStateError,
    EffectSchedulerError,
    ProviderIdentityError,
    ProviderInvocationError,
)


class ReconciliationAction(str, Enum):
    """Canonical consequence of one reconciliation observation."""

    SUCCEEDED = "SUCCEEDED"
    RETRY_QUEUED = "RETRY_QUEUED"
    CANCELLED = "CANCELLED"
    DEFERRED = "DEFERRED"


@dataclass(frozen=True, slots=True)
class EffectReconciliationObservation:
    """Reconciliation evidence and the canonical action it authorized."""

    result: EffectReconciliationResult
    action: ReconciliationAction
    lease: LeaseRecord
    usage: RuntimeUsage


class EffectReconciliationCoordinator:
    """Converge one ``TIMED_OUT`` attempt without guessing provider state."""

    def __init__(
        self,
        store: EventStore,
        queue: EffectQueue,
        spec: FsmSpec,
        clock: Clock,
        facts: EffectFactWriter,
        result_store: EffectResultStore,
        ids: IdGenerator,
        *,
        reconciliation_probe_ttl_seconds: int,
    ) -> None:
        if not isinstance(ids, IdGenerator):
            raise EffectSchedulerError("ids must implement IdGenerator")
        if (
            isinstance(reconciliation_probe_ttl_seconds, bool)
            or not isinstance(reconciliation_probe_ttl_seconds, int)
            or reconciliation_probe_ttl_seconds < 1
        ):
            raise EffectSchedulerError("reconciliation_probe_ttl_seconds must be positive")
        self._store = store
        self._queue = queue
        self._spec = spec
        self._clock = clock
        self._facts = facts
        self._result_store = result_store
        self._ids = ids
        self._probe_ttl_seconds = reconciliation_probe_ttl_seconds

    def reconcile(
        self, lease_token: str, *, reconciler: EffectReconciler
    ) -> EffectReconciliationObservation:
        """Probe provider state and apply only its evidence-backed consequence."""

        if not isinstance(reconciler, EffectReconciler):
            raise EffectSchedulerError("reconciler must implement EffectReconciler")
        record, effect, sealed, cancelled_attempt = self._load_context(lease_token, reconciler)
        if sealed is not None:
            return self._resume_concluded(record, effect, sealed)
        observed_at = self._clock.now_utc()
        self._require_probe_ready(record, cancelled_attempt, observed_at)
        request = self._reconciliation_request(record, effect)
        permit, usage = self._begin_probe(record, effect, observed_at)
        result = self._invoke_probe(record, effect, reconciler, request, permit, usage)
        observed_at = self._clock.now_utc()
        record, effect = self._refresh_after_probe(record, permit, observed_at)
        usage = _with_canonical_attempts(usage, effect.current_attempt)
        stored = self._persist_applied_outcome(record, result)
        return self._conclude_and_apply(
            record,
            effect,
            result,
            usage,
            permit,
            stored,
        )

    def _load_context(
        self,
        lease_token: str,
        reconciler: EffectReconciler,
    ) -> tuple[LeaseRecord, EffectState, ReconciliationProbePermit | None, bool]:
        record = self._queue.load(lease_token)
        if record is None:
            raise EffectRuntimeStateError(f"unknown lease token {lease_token!r}")
        if record.status is not LeaseStatus.RECONCILING:
            raise EffectRuntimeStateError(
                f"lease {lease_token!r} must be RECONCILING, got {record.status.value}"
            )
        history = tuple(self._store.load(record.stream_id))
        if not history:
            raise EffectRuntimeStateError("reconciling lease has no canonical cycle")
        state = replay(history, self._spec)
        effect = state.effect(record.effect_id)
        sealed = _concluded_permit(record)
        cancelled_attempt = _is_cancelled_attempt(effect, record)
        self._require_context_binding(
            record,
            effect,
            state.config_version,
            reconciler,
            sealed,
            cancelled_attempt,
        )
        return record, effect, sealed, cancelled_attempt

    def _require_context_binding(
        self,
        record: LeaseRecord,
        effect: EffectState,
        config_version: str,
        reconciler: EffectReconciler,
        sealed: ReconciliationProbePermit | None,
        cancelled_attempt: bool,
    ) -> None:
        resumable_attempt = sealed is not None and _is_latest_attempt(effect, record)
        if not any((_is_active_uncertain(effect, record), cancelled_attempt, resumable_attempt)):
            raise EffectRuntimeStateError(
                "reconciling lease is stale relative to the canonical uncertain/cancelled effect"
            )
        _require_canonical_grant_binding(effect, record)
        if record.config_version != config_version:
            raise EffectRuntimeStateError("queue config_version differs from the canonical cycle")
        if not _provider_matches(reconciler, effect):
            raise ProviderIdentityError(
                "reconciler provider/capability/risk descriptor does not match the effect grant"
            )
        if not effect.attempts:
            raise EffectRuntimeStateError("timed-out effect has no attempt audit")

    def _require_probe_ready(
        self,
        record: LeaseRecord,
        cancelled_attempt: bool,
        observed_at: str,
    ) -> None:
        if cancelled_attempt and _instant(observed_at) < _instant(record.lease_expiry):
            raise EffectRuntimeStateError(
                "cancelled started attempt cannot be probed before its execution lease expires"
            )

    def _reconciliation_request(
        self,
        record: LeaseRecord,
        effect: EffectState,
    ) -> EffectReconciliationRequest:
        evidence = effect.attempts[-1].reconciliation_refs or effect.reconciliation_refs
        if not evidence and record.reconciliation_ref is not None:
            evidence = (record.reconciliation_ref,)
        if not evidence:
            raise EffectRuntimeStateError("timed-out effect lacks reconciliation evidence")
        return EffectReconciliationRequest(
            cycle_id=record.stream_id,
            effect_id=record.effect_id,
            capability=effect.capability,
            provider=effect.provider,
            risk_class=effect.risk_class,
            idempotency_key=effect.idempotency_key,
            input_hash=effect.input_hash,
            lease_token=record.lease_token,
            attempt=effect.current_attempt,
            evidence_refs=evidence,
        )

    def _begin_probe(
        self,
        record: LeaseRecord,
        effect: EffectState,
        observed_at: str,
    ) -> tuple[ReconciliationProbePermit, RuntimeUsage]:
        permit_token = self._ids.new_id(
            f"effect-reconciliation-probe:{record.stream_id}:{record.effect_id}"
        )
        try:
            acquisition = self._queue.begin_reconciliation_probe(
                record.lease_token,
                permit_token=permit_token,
                acquired_at=observed_at,
                expires_at=self._expires_after(observed_at),
            )
        except ReconciliationProbeExhausted as exc:
            if effect.lifecycle is not EffectLifecycle.CANCELLED:
                self._cancel_uncertain(
                    record,
                    effect,
                    (BudgetLimit.RECONCILIATION_PROBES,),
                    observed_at,
                )
            raise BudgetExhaustedError((BudgetLimit.RECONCILIATION_PROBES,)) from exc
        except ReconciliationProbeConflict as exc:
            raise EffectRuntimeStateError(
                "another reconciliation probe already holds the single-flight permit"
            ) from exc
        return acquisition.permit, acquisition.usage

    def _invoke_probe(
        self,
        record: LeaseRecord,
        effect: EffectState,
        reconciler: EffectReconciler,
        request: EffectReconciliationRequest,
        permit: ReconciliationProbePermit,
        usage: RuntimeUsage,
    ) -> EffectReconciliationResult:
        try:
            result = reconciler.reconcile(request)
        except Exception as exc:
            observed_at = self._clock.now_utc()
            record = self._seal_failed_probe(
                record,
                permit,
                observed_at,
                evidence_ref=_probe_ref(record, type(exc).__name__),
                reason=f"reconciler raised {type(exc).__name__}",
            )
            self._cancel_after_failed_probe(record, effect, usage, observed_at)
            raise ProviderInvocationError(
                "reconciliation probe raised; effect remains fenced and non-retryable"
            ) from exc
        if not isinstance(result, EffectReconciliationResult) or not _same_identity(
            request, result
        ):
            observed_at = self._clock.now_utc()
            record = self._seal_failed_probe(
                record,
                permit,
                observed_at,
                evidence_ref=_probe_ref(record, "identity-mismatch"),
                reason="reconciler returned a mismatched execution identity",
            )
            self._cancel_after_failed_probe(record, effect, usage, observed_at)
            raise ProviderIdentityError(
                "reconciliation result does not match the fenced execution request"
            )
        return result

    def _cancel_after_failed_probe(
        self,
        record: LeaseRecord,
        effect: EffectState,
        usage: RuntimeUsage,
        observed_at: str,
    ) -> None:
        decision = evaluate_budget(record.budget, usage)
        if decision.exhausted and effect.lifecycle is not EffectLifecycle.CANCELLED:
            self._cancel_uncertain(record, effect, decision.limits, observed_at)

    def _refresh_after_probe(
        self,
        record: LeaseRecord,
        permit: ReconciliationProbePermit,
        observed_at: str,
    ) -> tuple[LeaseRecord, EffectState]:
        permitted = self._queue.load(record.lease_token)
        self._require_live_permit(permitted, permit, observed_at)
        assert permitted is not None
        latest_history = tuple(self._store.load(record.stream_id))
        latest_state = replay(latest_history, self._spec)
        effect = latest_state.effect(record.effect_id)
        self._require_current_probe_effect(effect, permitted)
        return permitted, effect

    def _require_live_permit(
        self,
        permitted: LeaseRecord | None,
        permit: ReconciliationProbePermit,
        observed_at: str,
    ) -> None:
        if (
            permitted is None
            or permitted.status is not LeaseStatus.RECONCILING
            or permitted.probe_permit != permit
            or _instant(observed_at) >= _instant(permit.expires_at)
        ):
            raise EffectRuntimeStateError(
                "reconciliation probe lost its durable single-flight permit"
            )

    def _require_current_probe_effect(
        self,
        effect: EffectState,
        record: LeaseRecord,
    ) -> None:
        if effect.lifecycle is EffectLifecycle.CANCELLED:
            if not _is_latest_attempt(effect, record):
                raise EffectRuntimeStateError(
                    "cancelled effect no longer recognizes the probed attempt"
                )
            return
        if (
            effect.lifecycle not in {EffectLifecycle.FAILED, EffectLifecycle.TIMED_OUT}
            or effect.lease_token != record.lease_token
        ):
            raise EffectRuntimeStateError(
                "canonical effect changed before reconciliation conclusion"
            )

    def _persist_applied_outcome(
        self,
        record: LeaseRecord,
        result: EffectReconciliationResult,
    ) -> StoredEffectResult | None:
        if result.outcome is ReconciliationOutcome.APPLIED:
            assert result.result is not None
            try:
                return self._persist_result(record, result.attempt, result.result)
            except Exception as exc:
                raise ProviderInvocationError(
                    "APPLIED reconciliation result could not be persisted; "
                    "the active permit remains takeover-eligible after expiry"
                ) from exc
        return None

    def _conclude_and_apply(
        self,
        record: LeaseRecord,
        effect: EffectState,
        result: EffectReconciliationResult,
        usage: RuntimeUsage,
        permit: ReconciliationProbePermit,
        stored: StoredEffectResult | None,
    ) -> EffectReconciliationObservation:
        concluded_at = self._clock.now_utc()
        conclusion = ReconciliationProbeConclusion(
            outcome=result.outcome,
            evidence_refs=result.evidence_refs,
            reason=result.reason,
            result_ref=None if stored is None else stored.result_ref,
            result_hash=None if stored is None else stored.result_hash,
        )
        record = self._queue.conclude_reconciliation_probe(
            record.lease_token,
            permit=permit,
            concluded_at=concluded_at,
            expires_at=self._expires_after(concluded_at),
            conclusion=conclusion,
            reconciliation_ref=_provider_evidence_ref(result),
            reason=result.reason or f"provider observed {result.outcome.value}",
        )
        assert record.probe_permit is not None
        usage = _with_canonical_attempts(
            self._queue.usage_for_outbox(record.outbox_id),
            effect.current_attempt,
        )
        return self._apply_conclusion(
            record,
            effect,
            result,
            usage,
            concluded_at,
            record.probe_permit,
            stored,
        )

    def _resume_concluded(
        self,
        record: LeaseRecord,
        effect: EffectState,
        permit: ReconciliationProbePermit,
    ) -> EffectReconciliationObservation:
        """Replay a sealed observation without another provider call or budget charge."""

        assert permit.state is ReconciliationProbePermitState.CONCLUDED
        assert permit.concluded_at is not None
        assert permit.conclusion is not None
        conclusion = permit.conclusion
        result_value: Mapping[str, CanonicalValue] | None = None
        stored: StoredEffectResult | None = None
        if conclusion.outcome is ReconciliationOutcome.APPLIED:
            assert conclusion.result_ref is not None
            assert conclusion.result_hash is not None
            stored = StoredEffectResult(
                conclusion.result_ref,
                conclusion.result_hash,
            )
            result_value = self._result_store.load(stored)
            if (
                result_value is None
                or canonical_sha256(result_value) != stored.result_hash
                or not self._result_store.verify(stored)
            ):
                raise EffectRuntimeStateError(
                    "sealed APPLIED conclusion cannot load its verified durable result"
                )
        result = EffectReconciliationResult(
            cycle_id=record.stream_id,
            effect_id=record.effect_id,
            capability=effect.capability,
            provider=effect.provider,
            risk_class=effect.risk_class,
            idempotency_key=effect.idempotency_key,
            input_hash=effect.input_hash,
            lease_token=record.lease_token,
            attempt=effect.attempts[-1].attempt,
            outcome=conclusion.outcome,
            result=result_value,
            evidence_refs=conclusion.evidence_refs,
            reason=conclusion.reason,
        )
        usage = _with_canonical_attempts(
            self._queue.usage_for_outbox(record.outbox_id),
            effect.current_attempt,
        )
        return self._apply_conclusion(
            record,
            effect,
            result,
            usage,
            permit.concluded_at,
            permit,
            stored,
        )

    def _apply_conclusion(
        self,
        record: LeaseRecord,
        effect: EffectState,
        result: EffectReconciliationResult,
        usage: RuntimeUsage,
        observed_at: str,
        permit: ReconciliationProbePermit,
        stored: StoredEffectResult | None,
    ) -> EffectReconciliationObservation:
        """Apply or replay one sealed conclusion, then clear only its exact fence."""

        self._require_conclusion_compatible(effect, result)
        if effect.lifecycle is EffectLifecycle.CANCELLED:
            lease, action = self._apply_cancelled_conclusion(
                record, result, observed_at, permit, stored
            )
        else:
            lease, action = self._apply_uncancelled_conclusion(
                record, effect, result, usage, observed_at, permit, stored
            )
        return EffectReconciliationObservation(result, action, lease, usage)

    def _require_conclusion_compatible(
        self,
        effect: EffectState,
        result: EffectReconciliationResult,
    ) -> None:
        if (
            effect.lifecycle is EffectLifecycle.SUCCEEDED
            and result.outcome is not ReconciliationOutcome.APPLIED
        ):
            raise EffectRuntimeStateError(
                "canonical success conflicts with the sealed reconciliation conclusion"
            )
        if (
            effect.lifecycle is EffectLifecycle.PENDING
            and result.outcome is not ReconciliationOutcome.NOT_APPLIED
        ):
            raise EffectRuntimeStateError(
                "canonical retry conflicts with the sealed reconciliation conclusion"
            )

    def _apply_cancelled_conclusion(
        self,
        record: LeaseRecord,
        result: EffectReconciliationResult,
        observed_at: str,
        permit: ReconciliationProbePermit,
        stored: StoredEffectResult | None,
    ) -> tuple[LeaseRecord, ReconciliationAction]:
        if result.outcome is ReconciliationOutcome.APPLIED:
            assert stored is not None
            lease = self._cancelled_applied(record, result, observed_at, permit, stored)
            return lease, ReconciliationAction.DEFERRED
        if result.outcome is ReconciliationOutcome.NOT_APPLIED:
            lease = self._queue.finish(
                record.lease_token,
                status=LeaseStatus.CANCELLED,
                completed_at=observed_at,
                reconciliation_ref=_provider_evidence_ref(result),
                reason=result.reason or "cancelled execution was not applied",
                probe_permit=permit,
            )
            return lease, ReconciliationAction.CANCELLED
        lease = self._queue.mark_reconciling(
            record.lease_token,
            observed_at=observed_at,
            reconciliation_ref=_provider_evidence_ref(result),
            reason=result.reason or result.outcome.value,
            probe_permit=permit,
        )
        return lease, ReconciliationAction.DEFERRED

    def _apply_uncancelled_conclusion(
        self,
        record: LeaseRecord,
        effect: EffectState,
        result: EffectReconciliationResult,
        usage: RuntimeUsage,
        observed_at: str,
        permit: ReconciliationProbePermit,
        stored: StoredEffectResult | None,
    ) -> tuple[LeaseRecord, ReconciliationAction]:
        if result.outcome is ReconciliationOutcome.APPLIED:
            return self._apply_uncancelled_applied(
                record, effect, result, observed_at, permit, stored
            )
        if result.outcome is ReconciliationOutcome.NOT_APPLIED:
            return self._not_applied(record, result, usage, observed_at, permit)
        return self._defer_uncertain(record, effect, result, usage, observed_at, permit)

    def _apply_uncancelled_applied(
        self,
        record: LeaseRecord,
        effect: EffectState,
        result: EffectReconciliationResult,
        observed_at: str,
        permit: ReconciliationProbePermit,
        stored: StoredEffectResult | None,
    ) -> tuple[LeaseRecord, ReconciliationAction]:
        if effect.lifecycle is EffectLifecycle.FAILED:
            lease = self._queue.mark_reconciling(
                record.lease_token,
                observed_at=observed_at,
                reconciliation_ref=_provider_evidence_ref(result),
                reason="APPLIED contradicts a canonical known failure; manual policy required",
                probe_permit=permit,
            )
            return lease, ReconciliationAction.DEFERRED
        assert stored is not None
        lease = self._applied(record, result, observed_at, permit, stored)
        return lease, ReconciliationAction.SUCCEEDED

    def _defer_uncertain(
        self,
        record: LeaseRecord,
        effect: EffectState,
        result: EffectReconciliationResult,
        usage: RuntimeUsage,
        observed_at: str,
        permit: ReconciliationProbePermit,
    ) -> tuple[LeaseRecord, ReconciliationAction]:
        lease = self._queue.mark_reconciling(
            record.lease_token,
            observed_at=observed_at,
            reconciliation_ref=_provider_evidence_ref(result),
            reason=result.reason or result.outcome.value,
            probe_permit=permit,
        )
        exhausted = evaluate_budget(record.budget, usage)
        if exhausted.exhausted:
            lease = self._cancel_uncertain(
                lease,
                effect,
                exhausted.limits,
                observed_at,
            )
            return lease, ReconciliationAction.CANCELLED
        return lease, ReconciliationAction.DEFERRED

    def _seal_failed_probe(
        self,
        record: LeaseRecord,
        permit: ReconciliationProbePermit,
        observed_at: str,
        *,
        evidence_ref: str,
        reason: str,
    ) -> LeaseRecord:
        conclusion = ReconciliationProbeConclusion(
            outcome=ReconciliationOutcome.FAILED,
            evidence_refs=(evidence_ref,),
            reason=reason,
        )
        sealed = self._queue.conclude_reconciliation_probe(
            record.lease_token,
            permit=permit,
            concluded_at=observed_at,
            expires_at=self._expires_after(observed_at),
            conclusion=conclusion,
            reconciliation_ref=evidence_ref,
            reason=reason,
        )
        assert sealed.probe_permit is not None
        return self._queue.mark_reconciling(
            record.lease_token,
            observed_at=observed_at,
            reconciliation_ref=evidence_ref,
            reason=reason,
            probe_permit=sealed.probe_permit,
        )

    def _expires_after(self, observed_at: str) -> str:
        return _format_instant(_instant(observed_at) + timedelta(seconds=self._probe_ttl_seconds))

    def _applied(
        self,
        record: LeaseRecord,
        result: EffectReconciliationResult,
        observed_at: str,
        permit: ReconciliationProbePermit,
        stored: StoredEffectResult,
    ) -> LeaseRecord:
        self._facts.append(
            cycle_id=record.stream_id,
            effect_id=record.effect_id,
            event_type=EventType.EFFECT_SUCCEEDED,
            payload={
                "attempt": result.attempt,
                "lease_token": result.lease_token,
                "result_ref": stored.result_ref,
                "result_hash": stored.result_hash,
            },
            occurred_at=observed_at,
            actor=record.lease_owner,
            correlation_id=_correlation_id(record),
            causation_id=_provider_evidence_ref(result),
        )
        return self._queue.finish(
            record.lease_token,
            status=LeaseStatus.SUCCEEDED,
            completed_at=observed_at,
            reconciliation_ref=_provider_evidence_ref(result),
            probe_permit=permit,
        )

    def _cancelled_applied(
        self,
        record: LeaseRecord,
        result: EffectReconciliationResult,
        observed_at: str,
        permit: ReconciliationProbePermit,
        stored: StoredEffectResult,
    ) -> LeaseRecord:
        reconciliation_ref = stored.result_ref
        detail = (
            "APPLIED after canonical cancellation; compensation required; "
            f"durable result {stored.result_ref}"
        )
        return self._queue.mark_reconciling(
            record.lease_token,
            observed_at=observed_at,
            reconciliation_ref=reconciliation_ref,
            reason=detail,
            probe_permit=permit,
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
        if (
            not isinstance(stored, StoredEffectResult)
            or stored.result_hash != canonical_sha256(result)
            or not self._result_store.verify(stored)
        ):
            raise EffectRuntimeStateError(
                "result store did not return a verified canonical result identity"
            )
        return stored

    def _cancel_uncertain(
        self,
        record: LeaseRecord,
        effect: EffectState,
        limits: tuple[object, ...],
        observed_at: str,
    ) -> LeaseRecord:
        reason = "runtime budget exhausted with uncertain external outcome: " + ",".join(
            getattr(limit, "value", str(limit)) for limit in limits
        )
        if effect.lifecycle is not EffectLifecycle.CANCELLED:
            self._facts.append(
                cycle_id=record.stream_id,
                effect_id=record.effect_id,
                event_type=EventType.EFFECT_CANCELLED,
                payload={
                    "reason": reason,
                    "authorization_ref": _runtime_authorization_ref(record),
                    "authorization_hash": _runtime_authorization_hash(record),
                },
                occurred_at=observed_at,
                actor=record.lease_owner,
                correlation_id=_correlation_id(record),
                causation_id=record.reconciliation_ref or record.lease_token,
                authorization_context={
                    "authorization_ref": _runtime_authorization_ref(record),
                    "authorization_hash": _runtime_authorization_hash(record),
                },
            )
        return self._queue.mark_reconciling(
            record.lease_token,
            observed_at=observed_at,
            reconciliation_ref=record.reconciliation_ref or _probe_ref(record, "budget-exhausted"),
            reason=reason,
        )

    def _not_applied(
        self,
        record: LeaseRecord,
        result: EffectReconciliationResult,
        usage: RuntimeUsage,
        observed_at: str,
        permit: ReconciliationProbePermit,
    ) -> tuple[LeaseRecord, ReconciliationAction]:
        decision = evaluate_budget(record.budget, usage)
        if decision.exhausted:
            reason = "runtime budget exhausted: " + ",".join(
                limit.value for limit in decision.limits
            )
            self._facts.append(
                cycle_id=record.stream_id,
                effect_id=record.effect_id,
                event_type=EventType.EFFECT_CANCELLED,
                payload={
                    "reason": reason,
                    "authorization_ref": _runtime_authorization_ref(record),
                    "authorization_hash": _runtime_authorization_hash(record),
                },
                occurred_at=observed_at,
                actor=record.lease_owner,
                correlation_id=_correlation_id(record),
                causation_id=_provider_evidence_ref(result),
                authorization_context={
                    "authorization_ref": _runtime_authorization_ref(record),
                    "authorization_hash": _runtime_authorization_hash(record),
                },
            )
            lease = self._queue.finish(
                record.lease_token,
                status=LeaseStatus.CANCELLED,
                completed_at=observed_at,
                reconciliation_ref=_provider_evidence_ref(result),
                reason=reason,
                probe_permit=permit,
            )
            return lease, ReconciliationAction.CANCELLED
        self._facts.append(
            cycle_id=record.stream_id,
            effect_id=record.effect_id,
            event_type=EventType.EFFECT_RETRY_QUEUED,
            payload={
                "guard_result": GuardResult.PASS.value,
                "guard_evidence_refs": result.evidence_refs,
                "lease_token": result.lease_token,
                "reconciliation_ref": _provider_evidence_ref(result),
                "reconciliation_outcome": ReconciliationOutcome.NOT_APPLIED.value,
            },
            occurred_at=observed_at,
            actor=record.lease_owner,
            correlation_id=_correlation_id(record),
            causation_id=_provider_evidence_ref(result),
        )
        lease = self._queue.finish(
            record.lease_token,
            status=LeaseStatus.ABANDONED,
            completed_at=observed_at,
            reconciliation_ref=_provider_evidence_ref(result),
            reason=result.reason,
            probe_permit=permit,
        )
        return lease, ReconciliationAction.RETRY_QUEUED


def _probe_ref(record: LeaseRecord, observation: str) -> str:
    digest = canonical_sha256(
        {
            "effect_id": record.effect_id,
            "lease_token": record.lease_token,
            "observation": observation,
            "stream_id": record.stream_id,
        }
    )
    return f"reconciliation://probe/{digest}"


def _provider_evidence_ref(result: EffectReconciliationResult) -> str:
    return result.evidence_refs[0]


def _concluded_permit(record: LeaseRecord) -> ReconciliationProbePermit | None:
    permit = record.probe_permit
    if permit is None or permit.state is not ReconciliationProbePermitState.CONCLUDED:
        return None
    return permit


def _is_latest_attempt(effect: EffectState, record: LeaseRecord) -> bool:
    return bool(effect.attempts) and effect.attempts[-1].lease_token == record.lease_token


def _is_cancelled_attempt(effect: EffectState, record: LeaseRecord) -> bool:
    return effect.lifecycle is EffectLifecycle.CANCELLED and _is_latest_attempt(effect, record)


def _is_active_uncertain(effect: EffectState, record: LeaseRecord) -> bool:
    return (
        effect.lifecycle in {EffectLifecycle.FAILED, EffectLifecycle.TIMED_OUT}
        and effect.lease_token == record.lease_token
        and effect.lease_owner == record.lease_owner
    )


def _instant(value: str) -> datetime:
    return datetime.fromisoformat(value[:-1] + "+00:00")


def _format_instant(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _runtime_authorization_ref(record: LeaseRecord) -> str:
    return f"policy://effect-runtime/budget/{record.config_version}"


def _runtime_authorization_hash(record: LeaseRecord) -> str:
    return canonical_sha256(
        {
            "action": "cancel-uncertain-effect-on-budget-exhaustion",
            "config_version": record.config_version,
            "grant_hash": record.grant_hash,
        }
    )


__all__ = [
    "EffectReconciliationCoordinator",
    "EffectReconciliationObservation",
    "ReconciliationAction",
]
