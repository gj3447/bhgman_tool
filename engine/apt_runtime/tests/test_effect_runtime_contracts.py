"""Pure contract tests for the APT vNext Slice 2 effect runtime.

# KG: apt-tpa-legion-engine-canon-2026-06-12
# Design: SYMPOSIUM/THEORY/APT/vnext/APT_ENGINE_FSM_DESIGN_2026-07-13.md §6.6,
#         §10.4, §12.4, §13, §18 Slice 2
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import FrozenInstanceError, replace

import pytest

from engine.apt_runtime.domain.canonical import (
    CanonicalEncodingError,
    CanonicalValue,
    as_mapping,
    canonical_json_bytes,
    canonical_sha256,
)
from engine.apt_runtime.domain.effect_runtime import (
    BudgetLimit,
    EffectExecutionGrant,
    ExecutionOutcome,
    ReconciliationOutcome,
    ResourceAccess,
    ResourceClaim,
    RuntimeBudget,
    RuntimeContractError,
    RuntimeUsage,
    detect_stuck,
    evaluate_budget,
    progress_signature,
)
from engine.apt_runtime.ports.effects import (
    Clock,
    EffectCancellationAuthorization,
    EffectExecutionRequest,
    EffectExecutionResult,
    EffectExecutor,
    EffectPortSchemaError,
    EffectReconciler,
    EffectReconciliationRequest,
    EffectReconciliationResult,
    EffectResultStore,
    IdGenerator,
    StoredEffectResult,
)


CAPABILITY = "artifact.realize"
PROVIDER = "fake-hades"
RISK_CLASS = "LOCAL_REVERSIBLE"


def _execution_request(**changes: object) -> EffectExecutionRequest:
    payload = changes.pop("input", {"target": "artifact-1"})
    values: dict[str, object] = {
        "cycle_id": "cycle-1",
        "effect_id": "effect-1",
        "capability": CAPABILITY,
        "provider": PROVIDER,
        "risk_class": RISK_CLASS,
        "idempotency_key": "idem-1",
        "input": payload,
        "input_hash": canonical_sha256(payload),
        "lease_token": "lease-1",
        "attempt": 1,
    }
    values.update(changes)
    return EffectExecutionRequest(**values)  # type: ignore[arg-type]


def _execution_result(
    outcome: ExecutionOutcome = ExecutionOutcome.SUCCEEDED,
    **changes: object,
) -> EffectExecutionResult:
    values: dict[str, object] = {
        "cycle_id": "cycle-1",
        "effect_id": "effect-1",
        "capability": CAPABILITY,
        "provider": PROVIDER,
        "risk_class": RISK_CLASS,
        "idempotency_key": "idem-1",
        "input_hash": canonical_sha256({"target": "artifact-1"}),
        "lease_token": "lease-1",
        "attempt": 1,
        "outcome": outcome,
        "result": {"artifact_ref": "artifact-1"} if outcome is ExecutionOutcome.SUCCEEDED else None,
        "evidence_refs": (),
        "reason": None if outcome is ExecutionOutcome.SUCCEEDED else "provider did not confirm",
        "usage_delta": RuntimeUsage(
            attempts=1,
            runtime_seconds=5,
            cost_units=2,
            progress_signature=progress_signature(
                {"execution_outcome": outcome.value, "effect_id": "effect-1"}
            ),
        ),
    }
    values.update(changes)
    return EffectExecutionResult(**values)  # type: ignore[arg-type]


def _reconciliation_request(**changes: object) -> EffectReconciliationRequest:
    values: dict[str, object] = {
        "cycle_id": "cycle-1",
        "effect_id": "effect-1",
        "capability": CAPABILITY,
        "provider": PROVIDER,
        "risk_class": RISK_CLASS,
        "idempotency_key": "idem-1",
        "input_hash": canonical_sha256({"target": "artifact-1"}),
        "lease_token": "lease-1",
        "attempt": 1,
        "evidence_refs": ("evidence-execution-timeout",),
    }
    values.update(changes)
    return EffectReconciliationRequest(**values)  # type: ignore[arg-type]


def _reconciliation_result(
    outcome: ReconciliationOutcome = ReconciliationOutcome.APPLIED,
    **changes: object,
) -> EffectReconciliationResult:
    values: dict[str, object] = {
        "cycle_id": "cycle-1",
        "effect_id": "effect-1",
        "capability": CAPABILITY,
        "provider": PROVIDER,
        "risk_class": RISK_CLASS,
        "idempotency_key": "idem-1",
        "input_hash": canonical_sha256({"target": "artifact-1"}),
        "lease_token": "lease-1",
        "attempt": 1,
        "outcome": outcome,
        "result": {"artifact_ref": "artifact-1"}
        if outcome is ReconciliationOutcome.APPLIED
        else None,
        "evidence_refs": ("evidence-reconciliation-1",),
        "reason": None
        if outcome is ReconciliationOutcome.APPLIED
        else "provider inspection was inconclusive",
    }
    values.update(changes)
    return EffectReconciliationResult(**values)  # type: ignore[arg-type]


def _execution_grant(**changes: object) -> EffectExecutionGrant:
    values: dict[str, object] = {
        "grant_ref": "grant://effect-1/config-v1",
        "cycle_id": "cycle-1",
        "effect_id": "effect-1",
        "capability": CAPABILITY,
        "provider": PROVIDER,
        "risk_class": RISK_CLASS,
        "config_version": "config-v1",
        "resource_claims": (
            ResourceClaim("workspace/repo/docs", ResourceAccess.SHARED_READ),
            ResourceClaim("workspace/repo/engine", ResourceAccess.EXCLUSIVE_WRITE),
        ),
        "budget": RuntimeBudget(3, 1_000, 20, 2),
        "authorization_ref": "authorization://effect-1",
        "authorization_hash": canonical_sha256(
            {"cycle_id": "cycle-1", "effect_id": "effect-1", "role": "operator"}
        ),
    }
    values.update(changes)
    return EffectExecutionGrant(**values)  # type: ignore[arg-type]


def test_execution_and_reconciliation_unknown_are_distinct_from_failure() -> None:
    assert ExecutionOutcome.UNKNOWN is not ExecutionOutcome.FAILED
    assert ReconciliationOutcome.UNKNOWN is not ReconciliationOutcome.FAILED
    assert ReconciliationOutcome.NOT_APPLIED is not ReconciliationOutcome.UNKNOWN
    assert len({item.value for item in ExecutionOutcome}) == 3
    assert len({item.value for item in ReconciliationOutcome}) == 4


def test_execution_request_normalizes_and_deep_freezes_canonical_input() -> None:
    payload = {"cafe\u0301": {"value": "re\u0301sume\u0301"}}
    request = _execution_request(
        cycle_id="cycle-cafe\u0301",
        input=payload,
        input_hash=canonical_sha256(payload),
    )

    assert request.cycle_id == "cycle-café"
    assert as_mapping(request.input["café"])["value"] == "résumé"
    with pytest.raises(TypeError):
        request.input["new"] = "forbidden"  # type: ignore[index]
    with pytest.raises(FrozenInstanceError):
        request.attempt = 2  # type: ignore[misc]


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("cycle_id", "", "non-empty"),
        ("effect_id", "effect-\x00", r"U\+0000"),
        ("capability", "", "non-empty"),
        ("provider", 3, "non-empty"),
        ("risk_class", "risk-\x00", r"U\+0000"),
        ("idempotency_key", 3, "non-empty"),
        ("lease_token", "", "non-empty"),
        ("input_hash", "ABC", "lowercase SHA-256"),
        ("attempt", True, "signed 64-bit"),
        ("attempt", 0, "signed 64-bit"),
        ("attempt", 2**63, "signed 64-bit"),
    ],
)
def test_effect_identity_rejects_malformed_values(field: str, value: object, message: str) -> None:
    with pytest.raises(EffectPortSchemaError, match=message):
        _execution_request(**{field: value})


def test_execution_request_rejects_an_input_hash_mismatch() -> None:
    with pytest.raises(EffectPortSchemaError, match="input_hash does not match"):
        _execution_request(input_hash="0" * 64)


def test_execution_grant_normalizes_claims_and_derives_a_fully_bound_hash() -> None:
    grant = _execution_grant(
        cycle_id="cycle-cafe\u0301",
        effect_id="effect-cafe\u0301",
        resource_claims=(
            ResourceClaim("workspace/repo/engine", ResourceAccess.EXCLUSIVE_WRITE),
            ResourceClaim("workspace/repo/cafe\u0301", ResourceAccess.SHARED_READ),
        ),
    )

    assert grant.cycle_id == "cycle-café"
    assert grant.effect_id == "effect-café"
    assert grant.resource_claims == tuple(sorted(grant.resource_claims, key=canonical_json_bytes))
    expected = canonical_sha256(
        {
            "grant_ref": grant.grant_ref,
            "cycle_id": grant.cycle_id,
            "effect_id": grant.effect_id,
            "capability": grant.capability,
            "provider": grant.provider,
            "risk_class": grant.risk_class,
            "config_version": grant.config_version,
            "resource_claims": grant.resource_claims,
            "budget": grant.budget,
            "authorization_ref": grant.authorization_ref,
            "authorization_hash": grant.authorization_hash,
        }
    )
    assert grant.grant_hash == expected
    assert replace(grant, cycle_id="cycle-other").grant_hash != grant.grant_hash
    assert replace(grant, provider="other-provider").grant_hash != grant.grant_hash
    with pytest.raises(FrozenInstanceError):
        grant.provider = "forbidden"  # type: ignore[misc]


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"resource_claims": ()}, "at least one"),
        ({"resource_claims": []}, "tuple"),
        (
            {
                "resource_claims": (
                    ResourceClaim("workspace/repo", ResourceAccess.SHARED_READ),
                    ResourceClaim("workspace/repo", ResourceAccess.EXCLUSIVE_WRITE),
                )
            },
            "resource_key only once",
        ),
        ({"budget": object()}, "budget must be RuntimeBudget"),
        ({"authorization_hash": "A" * 64}, "lowercase SHA-256"),
        ({"authorization_ref": ""}, "non-empty"),
        ({"cycle_id": ""}, "non-empty"),
    ],
)
def test_execution_grant_rejects_incomplete_or_ambiguous_authority(
    changes: dict[str, object], message: str
) -> None:
    with pytest.raises(RuntimeContractError, match=message):
        _execution_grant(**changes)


def test_cancellation_authority_normalizes_and_requires_cycle_identity() -> None:
    authority = EffectCancellationAuthorization(
        cycle_id="cycle-cafe\u0301",
        effect_id="effect-1",
        actor="operator",
        reason="cancel",
        authorization_ref="authorization://cancel/1",
        authorization_hash="a" * 64,
    )

    assert authority.cycle_id == "cycle-café"
    with pytest.raises(EffectPortSchemaError, match="cycle_id must be a non-empty"):
        replace(authority, cycle_id="")


@pytest.mark.parametrize("outcome", [ExecutionOutcome.FAILED, ExecutionOutcome.UNKNOWN])
def test_non_success_execution_requires_an_auditable_reason(outcome: ExecutionOutcome) -> None:
    with pytest.raises(EffectPortSchemaError, match="reason"):
        _execution_result(outcome, reason=None)


def test_successful_execution_requires_result_and_forbids_failure_reason() -> None:
    with pytest.raises(EffectPortSchemaError, match="result"):
        _execution_result(result=None)
    with pytest.raises(EffectPortSchemaError, match="reason"):
        _execution_result(reason="contradictory")


def test_execution_result_deep_freezes_result_and_normalizes_evidence() -> None:
    result = _execution_result(evidence_refs=("evidence-cafe\u0301",))

    assert result.evidence_refs == ("evidence-café",)
    assert result.result is not None
    with pytest.raises(TypeError):
        result.result["new"] = "forbidden"  # type: ignore[index]


def test_reconciliation_request_requires_tuple_evidence_and_normalizes_it() -> None:
    request = _reconciliation_request(evidence_refs=("evidence-cafe\u0301",))
    assert request.evidence_refs == ("evidence-café",)
    with pytest.raises(EffectPortSchemaError, match="tuple"):
        _reconciliation_request(evidence_refs=["mutable"])  # type: ignore[list-item]


@pytest.mark.parametrize(
    "outcome",
    [
        ReconciliationOutcome.APPLIED,
        ReconciliationOutcome.NOT_APPLIED,
        ReconciliationOutcome.FAILED,
        ReconciliationOutcome.UNKNOWN,
    ],
)
def test_every_reconciliation_result_requires_evidence(
    outcome: ReconciliationOutcome,
) -> None:
    with pytest.raises(EffectPortSchemaError, match="evidence_refs"):
        _reconciliation_result(outcome, evidence_refs=())


def test_applied_reconciliation_requires_result_and_forbids_failure_reason() -> None:
    with pytest.raises(EffectPortSchemaError, match="result"):
        _reconciliation_result(result=None)
    with pytest.raises(EffectPortSchemaError, match="reason"):
        _reconciliation_result(reason="contradictory")


@pytest.mark.parametrize(
    "outcome",
    [
        ReconciliationOutcome.NOT_APPLIED,
        ReconciliationOutcome.FAILED,
        ReconciliationOutcome.UNKNOWN,
    ],
)
def test_non_applied_reconciliation_requires_reason(
    outcome: ReconciliationOutcome,
) -> None:
    with pytest.raises(EffectPortSchemaError, match="reason"):
        _reconciliation_result(outcome, reason=None)


def test_resource_claim_overlap_and_shared_exclusive_conflict_semantics() -> None:
    repository_read = ResourceClaim("workspace/repo", ResourceAccess.SHARED_READ)
    engine_read = ResourceClaim("workspace/repo/engine", ResourceAccess.SHARED_READ)
    second_read = ResourceClaim("workspace/repo/engine", ResourceAccess.SHARED_READ)
    engine_write = ResourceClaim("workspace/repo/engine", ResourceAccess.EXCLUSIVE_WRITE)
    docs_write = ResourceClaim("workspace/repo/docs", ResourceAccess.EXCLUSIVE_WRITE)
    similarly_prefixed = ResourceClaim("workspace/repo2", ResourceAccess.EXCLUSIVE_WRITE)

    assert engine_read.overlaps(second_read)
    assert engine_read.overlaps(engine_write)
    assert repository_read.overlaps(engine_read)
    assert engine_read.overlaps(repository_read)
    assert not engine_read.conflicts_with(second_read)
    assert engine_read.conflicts_with(engine_write)
    assert repository_read.conflicts_with(engine_write)
    assert engine_write.conflicts_with(engine_read)
    assert not engine_write.overlaps(docs_write)
    assert not repository_read.overlaps(similarly_prefixed)
    assert not similarly_prefixed.conflicts_with(repository_read)


def test_resource_claim_validates_resource_identity_and_access() -> None:
    with pytest.raises(RuntimeContractError, match=r"U\+0000"):
        ResourceClaim("workspace:repo-\x00", ResourceAccess.SHARED_READ)
    with pytest.raises(RuntimeContractError, match="non-empty"):
        ResourceClaim("", ResourceAccess.SHARED_READ)
    with pytest.raises(RuntimeContractError, match="access"):
        ResourceClaim("workspace:repo-1", "WRITE")  # type: ignore[arg-type]


def test_budget_exhaustion_is_deterministic_at_exact_boundaries() -> None:
    budget = RuntimeBudget(
        max_attempts=3,
        max_runtime_seconds=1_000,
        max_cost_units=20,
        max_no_progress=2,
        max_reconciliation_probes=4,
    )
    below = RuntimeUsage(
        attempts=2,
        runtime_seconds=999,
        cost_units=19,
        no_progress=1,
        reconciliation_probes=3,
    )
    boundary = RuntimeUsage(
        attempts=3,
        runtime_seconds=1_000,
        cost_units=20,
        no_progress=2,
        reconciliation_probes=4,
    )

    assert not evaluate_budget(budget, below).exhausted
    decision = evaluate_budget(budget, boundary)
    assert decision.exhausted
    assert decision.limits == tuple(BudgetLimit)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("max_attempts", True),
        ("max_runtime_seconds", 0),
        ("max_cost_units", -1),
        ("max_no_progress", 2**63),
        ("max_reconciliation_probes", 0),
    ],
)
def test_runtime_budget_rejects_non_positive_or_non_signed64_limits(
    field: str, value: object
) -> None:
    values: dict[str, object] = {
        "max_attempts": 3,
        "max_runtime_seconds": 1_000,
        "max_cost_units": 20,
        "max_no_progress": 2,
        "max_reconciliation_probes": 3,
    }
    values[field] = value
    with pytest.raises(RuntimeContractError, match="signed 64-bit positive"):
        RuntimeBudget(**values)  # type: ignore[arg-type]


def test_progress_observation_increments_then_resets_no_progress() -> None:
    first = progress_signature({"event_version": 1, "open_needs": ("need-1",)})
    changed = progress_signature({"event_version": 2, "open_needs": ()})
    usage = RuntimeUsage().observe_progress(first)

    assert usage.progress_signature == first
    assert usage.no_progress == 0
    unchanged = usage.observe_progress(first).observe_progress(first)
    assert unchanged.no_progress == 2
    assert evaluate_budget(RuntimeBudget(5, 10_000, 100, 2), unchanged).limits == (
        BudgetLimit.NO_PROGRESS,
    )
    assert detect_stuck(RuntimeBudget(5, 10_000, 100, 2), unchanged)
    reset = unchanged.observe_progress(changed)
    assert reset.no_progress == 0
    assert reset.progress_signature == changed


def test_runtime_budget_reconciliation_probe_default_is_positive_and_bounded() -> None:
    budget = RuntimeBudget(5, 10_000, 100, 2)
    assert budget.max_reconciliation_probes == 3
    below = RuntimeUsage(reconciliation_probes=2)
    boundary = RuntimeUsage(reconciliation_probes=3)
    assert BudgetLimit.RECONCILIATION_PROBES not in evaluate_budget(budget, below).limits
    assert BudgetLimit.RECONCILIATION_PROBES in evaluate_budget(budget, boundary).limits


def test_runtime_usage_adds_execution_delta_without_ambient_time() -> None:
    before = RuntimeUsage(
        attempts=1,
        runtime_seconds=3,
        cost_units=4,
        reconciliation_probes=1,
    )
    delta = RuntimeUsage(
        attempts=1,
        runtime_seconds=5,
        cost_units=2,
        reconciliation_probes=2,
        progress_signature=progress_signature({"event_version": 2}),
    )

    after = before.add(delta)
    assert after.attempts == 2
    assert after.runtime_seconds == 8
    assert after.cost_units == 6
    assert after.reconciliation_probes == 3
    assert after.progress_signature == delta.progress_signature


@pytest.mark.parametrize("value", [True, -1, 2**63])
def test_runtime_usage_rejects_invalid_signed64_counters(value: object) -> None:
    with pytest.raises(RuntimeContractError, match="signed 64-bit non-negative"):
        RuntimeUsage(runtime_seconds=value)  # type: ignore[arg-type]


def test_execution_usage_delta_cannot_charge_reconciliation_probes() -> None:
    with pytest.raises(EffectPortSchemaError, match="reconciliation_probes"):
        _execution_result(
            usage_delta=RuntimeUsage(
                attempts=1,
                reconciliation_probes=1,
                progress_signature=progress_signature({"effect_id": "effect-1"}),
            )
        )


def test_execution_result_requires_exactly_one_attempt_in_usage_delta() -> None:
    with pytest.raises(EffectPortSchemaError, match="usage_delta.attempts"):
        _execution_result(usage_delta=RuntimeUsage())


def test_progress_signature_is_canonical_and_rejects_noncanonical_values() -> None:
    assert progress_signature({"name": "cafe\u0301"}) == progress_signature({"name": "café"})
    with pytest.raises(CanonicalEncodingError):
        progress_signature({"score": 0.5})


class _FakeClock:
    def now_utc(self) -> str:
        return "2026-07-14T12:00:00Z"


class _FakeIds:
    def new_id(self, namespace: str) -> str:
        return f"{namespace}-1"


class _FakeExecutor:
    provider = PROVIDER
    capabilities = frozenset({CAPABILITY})
    risk_classes = frozenset({RISK_CLASS})

    def execute(self, request: EffectExecutionRequest) -> EffectExecutionResult:
        return _execution_result(
            cycle_id=request.cycle_id,
            effect_id=request.effect_id,
            capability=request.capability,
            provider=request.provider,
            risk_class=request.risk_class,
            idempotency_key=request.idempotency_key,
            input_hash=request.input_hash,
            lease_token=request.lease_token,
            attempt=request.attempt,
        )


class _FakeReconciler:
    provider = PROVIDER
    capabilities = frozenset({CAPABILITY})
    risk_classes = frozenset({RISK_CLASS})

    def reconcile(self, request: EffectReconciliationRequest) -> EffectReconciliationResult:
        return _reconciliation_result(
            cycle_id=request.cycle_id,
            effect_id=request.effect_id,
            capability=request.capability,
            provider=request.provider,
            risk_class=request.risk_class,
            idempotency_key=request.idempotency_key,
            input_hash=request.input_hash,
            lease_token=request.lease_token,
            attempt=request.attempt,
        )


class _FakeResultStore:
    def __init__(self) -> None:
        self._results: dict[str, tuple[str, Mapping[str, CanonicalValue]]] = {}

    def persist(
        self,
        cycle_id: str,
        effect_id: str,
        attempt: int,
        result: Mapping[str, CanonicalValue],
    ) -> StoredEffectResult:
        result_hash = canonical_sha256(result)
        result_ref = f"effect-result://{cycle_id}/{effect_id}/{attempt}/{result_hash}"
        self._results[result_ref] = (result_hash, result)
        return StoredEffectResult(result_ref=result_ref, result_hash=result_hash)

    def verify(self, stored: StoredEffectResult) -> bool:
        value = self._results.get(stored.result_ref)
        return value is not None and value[0] == stored.result_hash

    def load(self, stored: StoredEffectResult) -> Mapping[str, CanonicalValue] | None:
        value = self._results.get(stored.result_ref)
        if value is None or value[0] != stored.result_hash:
            return None
        return value[1]


def test_injected_protocol_fakes_satisfy_runtime_ports() -> None:
    clock: Clock = _FakeClock()
    ids: IdGenerator = _FakeIds()
    executor: EffectExecutor = _FakeExecutor()
    reconciler: EffectReconciler = _FakeReconciler()
    result_store: EffectResultStore = _FakeResultStore()

    request = _execution_request()
    reconciliation_request = _reconciliation_request()
    assert clock.now_utc().endswith("Z")
    assert ids.new_id("lease") == "lease-1"
    assert executor.execute(request).outcome is ExecutionOutcome.SUCCEEDED
    assert reconciler.reconcile(reconciliation_request).outcome is ReconciliationOutcome.APPLIED
    stored = result_store.persist(
        request.cycle_id,
        request.effect_id,
        request.attempt,
        {"artifact_ref": "artifact://1"},
    )
    assert result_store.verify(stored)
    assert executor.provider == PROVIDER
    assert CAPABILITY in executor.capabilities
    assert RISK_CLASS in reconciler.risk_classes
    assert isinstance(clock, Clock)
    assert isinstance(ids, IdGenerator)
    assert isinstance(executor, EffectExecutor)
    assert isinstance(reconciler, EffectReconciler)
    assert isinstance(result_store, EffectResultStore)
