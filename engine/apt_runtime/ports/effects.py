"""Injected effect-provider ports and immutable Slice 2 boundary DTOs.

Adapters receive all nondeterminism through these protocols.  Requests and
results carry the complete effect, lease, idempotency, and attempt identity so
stale or duplicate delivery can be rejected outside provider-specific code.

# KG: apt-tpa-legion-engine-canon-2026-06-12
# KG: APT_SCW_TDAD_canonical
# Design: SYMPOSIUM/THEORY/APT/vnext/APT_ENGINE_FSM_DESIGN_2026-07-13.md §6.6,
#         §12.4, §13, §18 Slice 2
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from engine.apt_runtime.domain.canonical import (
    CanonicalEncodingError,
    CanonicalValue,
    MAX_SIGNED_64,
    as_mapping,
    canonical_sha256,
    deep_freeze,
    normalize_text,
)
from engine.apt_runtime.domain.effect_runtime import (
    EffectExecutionGrant,
    ExecutionOutcome,
    ReconciliationOutcome,
    RuntimeUsage,
)


class EffectPortSchemaError(ValueError):
    """An effect port DTO is incomplete, mutable, or internally inconsistent."""


def _text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value:
        raise EffectPortSchemaError(f"{name} must be a non-empty string")
    normalized = normalize_text(value)
    if "\x00" in normalized:
        raise EffectPortSchemaError(f"{name} cannot contain U+0000")
    return normalized


def _positive_integer(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= MAX_SIGNED_64:
        raise EffectPortSchemaError(f"{name} must be a signed 64-bit positive integer")
    return value


def _hash(name: str, value: object) -> str:
    text = _text(name, value)
    if len(text) != 64 or any(character not in "0123456789abcdef" for character in text):
        raise EffectPortSchemaError(f"{name} must be a lowercase SHA-256 hex digest")
    return text


def _mapping(name: str, value: object) -> Mapping[str, CanonicalValue]:
    try:
        return as_mapping(deep_freeze(value))
    except (CanonicalEncodingError, RecursionError) as exc:
        raise EffectPortSchemaError(f"{name} must be canonical JSON: {exc}") from exc


def _optional_mapping(name: str, value: object | None) -> Mapping[str, CanonicalValue] | None:
    return None if value is None else _mapping(name, value)


def _evidence_refs(value: object, *, nonempty: bool) -> tuple[str, ...]:
    if not isinstance(value, tuple):
        raise EffectPortSchemaError("evidence_refs must be a tuple")
    normalized = tuple(
        _text(f"evidence_refs[{index}]", reference) for index, reference in enumerate(value)
    )
    if nonempty and not normalized:
        raise EffectPortSchemaError("evidence_refs must contain at least one reference")
    if len(set(normalized)) != len(normalized):
        raise EffectPortSchemaError("evidence_refs must be unique")
    return normalized


def _optional_reason(value: object | None) -> str | None:
    return None if value is None else _text("reason", value)


@dataclass(frozen=True, slots=True)
class _EffectIdentity:
    cycle_id: str
    effect_id: str
    capability: str
    provider: str
    risk_class: str
    idempotency_key: str
    input_hash: str
    lease_token: str
    attempt: int

    def __post_init__(self) -> None:
        for name in (
            "cycle_id",
            "effect_id",
            "capability",
            "provider",
            "risk_class",
            "idempotency_key",
            "lease_token",
        ):
            object.__setattr__(self, name, _text(name, getattr(self, name)))
        object.__setattr__(self, "input_hash", _hash("input_hash", self.input_hash))
        object.__setattr__(self, "attempt", _positive_integer("attempt", self.attempt))


@dataclass(frozen=True, slots=True)
class EffectExecutionRequest(_EffectIdentity):
    """Canonical provider input bound to one current lease and attempt."""

    input: Mapping[str, CanonicalValue]

    def __post_init__(self) -> None:
        _EffectIdentity.__post_init__(self)
        frozen = _mapping("input", self.input)
        if canonical_sha256(frozen) != self.input_hash:
            raise EffectPortSchemaError("input_hash does not match canonical input")
        object.__setattr__(self, "input", frozen)


@dataclass(frozen=True, slots=True)
class EffectExecutionResult(_EffectIdentity):
    """Auditable provider observation and explicit resource-usage delta."""

    outcome: ExecutionOutcome
    result: Mapping[str, CanonicalValue] | None
    evidence_refs: tuple[str, ...]
    reason: str | None
    usage_delta: RuntimeUsage

    def __post_init__(self) -> None:
        _EffectIdentity.__post_init__(self)
        try:
            outcome = ExecutionOutcome(self.outcome)
        except ValueError as exc:
            raise EffectPortSchemaError("outcome must be a valid ExecutionOutcome") from exc
        result = _optional_mapping("result", self.result)
        evidence = _evidence_refs(self.evidence_refs, nonempty=False)
        reason = _optional_reason(self.reason)
        _validate_execution_semantics(outcome, result, reason)
        _validate_usage_delta(self.usage_delta)
        object.__setattr__(self, "outcome", outcome)
        object.__setattr__(self, "result", result)
        object.__setattr__(self, "evidence_refs", evidence)
        object.__setattr__(self, "reason", reason)


def _validate_execution_semantics(
    outcome: ExecutionOutcome,
    result: Mapping[str, CanonicalValue] | None,
    reason: str | None,
) -> None:
    if outcome is ExecutionOutcome.SUCCEEDED:
        if result is None:
            raise EffectPortSchemaError("SUCCEEDED execution requires result")
        if reason is not None:
            raise EffectPortSchemaError("SUCCEEDED execution cannot carry reason")
        return
    if result is not None:
        raise EffectPortSchemaError(f"{outcome.value} execution cannot carry result")
    if reason is None:
        raise EffectPortSchemaError(f"{outcome.value} execution requires reason")


def _validate_usage_delta(value: object) -> None:
    if not isinstance(value, RuntimeUsage):
        raise EffectPortSchemaError("usage_delta must be RuntimeUsage")
    if value.attempts != 1:
        raise EffectPortSchemaError("usage_delta.attempts must equal one")
    if value.no_progress != 0:
        raise EffectPortSchemaError("usage_delta.no_progress must be zero before aggregation")
    if value.reconciliation_probes != 0:
        raise EffectPortSchemaError("usage_delta.reconciliation_probes must be zero")
    if value.progress_signature is None:
        raise EffectPortSchemaError("usage_delta.progress_signature is required")


@dataclass(frozen=True, slots=True)
class EffectReconciliationRequest(_EffectIdentity):
    """Read-after-uncertainty probe bound to the original execution identity."""

    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        _EffectIdentity.__post_init__(self)
        object.__setattr__(
            self,
            "evidence_refs",
            _evidence_refs(self.evidence_refs, nonempty=True),
        )


@dataclass(frozen=True, slots=True)
class EffectReconciliationResult(_EffectIdentity):
    """Evidence-backed observation that never collapses unknown into failure."""

    outcome: ReconciliationOutcome
    result: Mapping[str, CanonicalValue] | None
    evidence_refs: tuple[str, ...]
    reason: str | None

    def __post_init__(self) -> None:
        _EffectIdentity.__post_init__(self)
        try:
            outcome = ReconciliationOutcome(self.outcome)
        except ValueError as exc:
            raise EffectPortSchemaError("outcome must be a valid ReconciliationOutcome") from exc
        result = _optional_mapping("result", self.result)
        evidence = _evidence_refs(self.evidence_refs, nonempty=True)
        reason = _optional_reason(self.reason)
        _validate_reconciliation_semantics(outcome, result, reason)
        object.__setattr__(self, "outcome", outcome)
        object.__setattr__(self, "result", result)
        object.__setattr__(self, "evidence_refs", evidence)
        object.__setattr__(self, "reason", reason)


def _validate_reconciliation_semantics(
    outcome: ReconciliationOutcome,
    result: Mapping[str, CanonicalValue] | None,
    reason: str | None,
) -> None:
    if outcome is ReconciliationOutcome.APPLIED:
        if result is None:
            raise EffectPortSchemaError("APPLIED reconciliation requires result")
        if reason is not None:
            raise EffectPortSchemaError("APPLIED reconciliation cannot carry reason")
        return
    if result is not None:
        raise EffectPortSchemaError(f"{outcome.value} reconciliation cannot carry result")
    if reason is None:
        raise EffectPortSchemaError(f"{outcome.value} reconciliation requires reason")


@dataclass(frozen=True, slots=True)
class StoredEffectResult:
    """Durable provider-result identity committed before a success fact."""

    result_ref: str
    result_hash: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "result_ref", _text("result_ref", self.result_ref))
        object.__setattr__(self, "result_hash", _hash("result_hash", self.result_hash))


@dataclass(frozen=True, slots=True)
class EffectCancellationAuthorization:
    """Signed/verifiable authority bound to one exact cycle-effect cancellation."""

    cycle_id: str
    effect_id: str
    actor: str
    reason: str
    authorization_ref: str
    authorization_hash: str

    def __post_init__(self) -> None:
        for name in ("cycle_id", "effect_id", "actor", "reason", "authorization_ref"):
            object.__setattr__(self, name, _text(name, getattr(self, name)))
        object.__setattr__(
            self,
            "authorization_hash",
            _hash("authorization_hash", self.authorization_hash),
        )


@runtime_checkable
class Clock(Protocol):
    """Injected UTC source; consumers validate and persist returned timestamps."""

    def now_utc(self) -> str: ...


@runtime_checkable
class IdGenerator(Protocol):
    """Injected identity source scoped by a stable caller-supplied namespace."""

    def new_id(self, namespace: str) -> str: ...


@runtime_checkable
class EffectExecutor(Protocol):
    """Provider adapter for one leased execution attempt."""

    @property
    def provider(self) -> str: ...

    @property
    def capabilities(self) -> frozenset[str]: ...

    @property
    def risk_classes(self) -> frozenset[str]: ...

    def execute(self, request: EffectExecutionRequest) -> EffectExecutionResult: ...


@runtime_checkable
class EffectReconciler(Protocol):
    """Provider adapter for evidence-based unknown-outcome recovery."""

    @property
    def provider(self) -> str: ...

    @property
    def capabilities(self) -> frozenset[str]: ...

    @property
    def risk_classes(self) -> frozenset[str]: ...

    def reconcile(self, request: EffectReconciliationRequest) -> EffectReconciliationResult: ...


@runtime_checkable
class EffectResultStore(Protocol):
    """Durably persist and later verify one canonical provider result mapping."""

    def persist(
        self,
        cycle_id: str,
        effect_id: str,
        attempt: int,
        result: Mapping[str, CanonicalValue],
    ) -> StoredEffectResult: ...

    def verify(self, stored: StoredEffectResult) -> bool: ...

    def load(self, stored: StoredEffectResult) -> Mapping[str, CanonicalValue] | None: ...


@runtime_checkable
class EffectGrantVerifier(Protocol):
    """Trusted policy boundary for authorization-backed execution grants."""

    def verify(self, grant: EffectExecutionGrant) -> bool: ...


@runtime_checkable
class EffectCancellationVerifier(Protocol):
    """Trusted policy boundary for cancellation authorizations."""

    def verify(self, authorization: EffectCancellationAuthorization) -> bool: ...


__all__ = [
    "Clock",
    "EffectCancellationAuthorization",
    "EffectCancellationVerifier",
    "EffectExecutionRequest",
    "EffectExecutionResult",
    "EffectExecutor",
    "EffectGrantVerifier",
    "EffectPortSchemaError",
    "EffectReconciler",
    "EffectReconciliationRequest",
    "EffectReconciliationResult",
    "EffectResultStore",
    "IdGenerator",
    "StoredEffectResult",
]
