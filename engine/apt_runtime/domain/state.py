"""Immutable aggregate state for the APT vNext Slice 0 reducer.

KG: apt-tpa-legion-engine-canon-2026-06-12
KG: user-verdict-7cmd-need-based-conditional-dispatch-2026-05-30
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .canonical import MAX_SIGNED_64, canonical_sha256, normalize_text


class CycleLifecycle(str, Enum):
    CREATED = "CREATED"
    ACTIVE = "ACTIVE"
    WAITING = "WAITING"
    RECOVERING = "RECOVERING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    SUPERSEDED = "SUPERSEDED"


class WorkItemLifecycle(str, Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    SUPERSEDED = "SUPERSEDED"


class SemanticMaturity(str, Enum):
    DRAFT = "DRAFT"
    ANCHORED = "ANCHORED"
    DECOMPOSING = "DECOMPOSING"
    DECOMPOSED = "DECOMPOSED"
    ATOMIC = "ATOMIC"
    CRYSTALLIZING = "CRYSTALLIZING"
    CONTRACTED = "CONTRACTED"


class RealizationStatus(str, Enum):
    NOT_READY = "NOT_READY"
    READY = "READY"
    DISPATCHED = "DISPATCHED"
    RUNNING = "RUNNING"
    MATERIALIZED = "MATERIALIZED"
    FAILED = "FAILED"


class AssuranceStatus(str, Enum):
    UNASSESSED = "UNASSESSED"
    VERIFYING = "VERIFYING"
    ACCEPTED = "ACCEPTED"
    REFUTED = "REFUTED"
    INCONCLUSIVE = "INCONCLUSIVE"


class EffectLifecycle(str, Enum):
    PENDING = "PENDING"
    LEASED = "LEASED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    TIMED_OUT = "TIMED_OUT"
    CANCELLED = "CANCELLED"


class EffectAttemptOutcome(str, Enum):
    """Auditable outcome history for one fenced external execution attempt."""

    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    TIMED_OUT = "TIMED_OUT"
    CANCELLED = "CANCELLED"


class WorkItemKind(str, Enum):
    LEAF = "LEAF"
    CONTAINER = "CONTAINER"


def _sorted_unique(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(sorted({_normalized_text("identity collection value", value) for value in values}))


def _normalized_text(name: str, value: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")
    return normalize_text(value)


def _normalized_optional_text(name: str, value: str | None) -> str | None:
    return None if value is None else _normalized_text(name, value)


def _normalized_hash(name: str, value: str) -> str:
    normalized = _normalized_text(name, value)
    if len(normalized) != 64 or any(
        character not in "0123456789abcdef" for character in normalized
    ):
        raise ValueError(f"{name} must be a lowercase SHA-256 hex digest")
    return normalized


def _normalized_optional_hash(name: str, value: str | None) -> str | None:
    return None if value is None else _normalized_hash(name, value)


def _normalized_history(name: str, values: tuple[str, ...]) -> tuple[str, ...]:
    if not isinstance(values, tuple):
        raise ValueError(f"{name} must be a tuple")
    return tuple(_normalized_text(f"{name}[{index}]", value) for index, value in enumerate(values))


_ALLOWED_ATTEMPT_HISTORIES = frozenset(
    {
        (EffectAttemptOutcome.RUNNING,),
        (EffectAttemptOutcome.RUNNING, EffectAttemptOutcome.SUCCEEDED),
        (EffectAttemptOutcome.RUNNING, EffectAttemptOutcome.FAILED),
        (EffectAttemptOutcome.RUNNING, EffectAttemptOutcome.TIMED_OUT),
        (
            EffectAttemptOutcome.RUNNING,
            EffectAttemptOutcome.TIMED_OUT,
            EffectAttemptOutcome.SUCCEEDED,
        ),
        (EffectAttemptOutcome.RUNNING, EffectAttemptOutcome.CANCELLED),
    }
)


def _effect_attempt_number(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= MAX_SIGNED_64:
        raise ValueError("effect attempt must be a signed 64-bit positive integer")
    return value


def _effect_attempt_history(
    values: tuple[EffectAttemptOutcome, ...],
) -> tuple[EffectAttemptOutcome, ...]:
    history = tuple(EffectAttemptOutcome(item) for item in values)
    if not history or history[0] is not EffectAttemptOutcome.RUNNING:
        raise ValueError("effect attempt outcome history must begin with RUNNING")
    if history not in _ALLOWED_ATTEMPT_HISTORIES:
        raise ValueError("effect attempt outcome history is not a legal recovery path")
    return history


def _validate_completed_attempt(record: EffectAttemptRecord) -> None:
    if record.completed_at is None:
        raise ValueError("completed effect attempt requires completed_at")
    if (record.result_ref is None) != (record.result_hash is None):
        raise ValueError("effect attempt result_ref and result_hash must appear together")
    if record.outcome is EffectAttemptOutcome.SUCCEEDED:
        if record.result_ref is None or record.reasons:
            raise ValueError("succeeded effect attempt requires only a result")
    elif record.result_ref is not None:
        raise ValueError("non-succeeded effect attempt cannot carry a result")
    if record.outcome in {EffectAttemptOutcome.FAILED, EffectAttemptOutcome.CANCELLED}:
        if not record.reasons:
            raise ValueError("failed/cancelled effect attempt requires a reason")
    if EffectAttemptOutcome.TIMED_OUT in record.outcome_history and not record.reconciliation_refs:
        raise ValueError("timed-out effect attempt requires reconciliation evidence")


def _validate_attempt_audit(record: EffectAttemptRecord) -> None:
    if record.outcome is not EffectAttemptOutcome.RUNNING:
        _validate_completed_attempt(record)
        return
    completion_audit = (record.completed_at, record.result_ref, record.result_hash)
    if (
        any(value is not None for value in completion_audit)
        or record.reasons
        or record.reconciliation_refs
    ):
        raise ValueError("running effect attempt cannot carry completion audit")


def _effect_generation(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError("effect generation must be a positive integer when present")
    return value


def _validate_complete_binding(name: str, values: tuple[str | None, ...]) -> None:
    if any(value is None for value in values) and any(value is not None for value in values):
        raise ValueError(f"{name} fields must appear or clear together")


def _validate_lease_grant_binding(record: EffectState) -> None:
    active_lease = (
        record.lease_owner,
        record.lease_token,
        record.lease_expiry,
        record.heartbeat_at,
    )
    grant_binding = (
        record.grant_ref,
        record.grant_hash,
        record.authorization_ref,
        record.authorization_hash,
    )
    _validate_complete_binding("active effect lease", active_lease)
    _validate_complete_binding("effect grant binding", grant_binding)
    if record.lease_token is not None and record.grant_ref is None:
        raise ValueError("active effect lease requires a durable grant binding")


def _effect_lease_history(record: EffectState) -> tuple[str, ...]:
    history = _normalized_history("lease_token_history", record.lease_token_history)
    if len(set(history)) != len(history):
        raise ValueError("lease_token_history values must be unique")
    if record.lease_token is not None and record.lease_token not in history:
        raise ValueError("active lease token must appear in lease_token_history")
    return history


def _current_attempt(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= MAX_SIGNED_64:
        raise ValueError("current_attempt must be a non-negative integer")
    return value


def _effect_attempts(
    values: tuple[EffectAttemptRecord, ...],
    *,
    current_attempt: int,
    lease_history: tuple[str, ...],
) -> tuple[EffectAttemptRecord, ...]:
    attempts = tuple(values)
    if any(not isinstance(item, EffectAttemptRecord) for item in attempts):
        raise ValueError("attempts must contain only EffectAttemptRecord values")
    if tuple(item.attempt for item in attempts) != tuple(range(1, len(attempts) + 1)):
        raise ValueError("effect attempts must be contiguous and monotonically numbered")
    if current_attempt != len(attempts):
        raise ValueError("current_attempt must equal the immutable attempt record count")
    if any(item.lease_token not in lease_history for item in attempts):
        raise ValueError("every attempt lease token must appear in lease_token_history")
    return attempts


def _validate_effect_lease_lifecycle(record: EffectState) -> None:
    lease_required = {
        EffectLifecycle.LEASED,
        EffectLifecycle.RUNNING,
        EffectLifecycle.FAILED,
        EffectLifecycle.TIMED_OUT,
    }
    lease_forbidden = {
        EffectLifecycle.PENDING,
        EffectLifecycle.SUCCEEDED,
        EffectLifecycle.CANCELLED,
    }
    if record.lifecycle in lease_required and record.lease_token is None:
        raise ValueError(f"{record.lifecycle.value} effect requires a retained active lease")
    if record.lifecycle in lease_forbidden and record.lease_token is not None:
        raise ValueError(f"{record.lifecycle.value} effect cannot retain an active lease")


def _validate_effect_attempt_lifecycle(
    record: EffectState, attempts: tuple[EffectAttemptRecord, ...]
) -> None:
    expected = {
        EffectLifecycle.RUNNING: EffectAttemptOutcome.RUNNING,
        EffectLifecycle.FAILED: EffectAttemptOutcome.FAILED,
        EffectLifecycle.SUCCEEDED: EffectAttemptOutcome.SUCCEEDED,
    }
    outcome = expected.get(record.lifecycle)
    if outcome is not None and (not attempts or attempts[-1].outcome is not outcome):
        raise ValueError(
            f"{record.lifecycle.value.lower()} effect requires a "
            f"{outcome.value.lower()} current attempt audit"
        )
    if record.lifecycle is EffectLifecycle.SUCCEEDED and (
        record.result_ref != attempts[-1].result_ref
        or record.result_hash != attempts[-1].result_hash
    ):
        raise ValueError("effect result must equal its succeeded attempt audit")


def _validate_effect_result(record: EffectState) -> None:
    if (record.result_ref is None) != (record.result_hash is None):
        raise ValueError("effect result_ref and result_hash must appear together")


@dataclass(frozen=True, slots=True)
class ArtifactRecord:
    artifact_ref: str
    artifact_hash: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "artifact_ref", _normalized_text("artifact_ref", self.artifact_ref)
        )
        object.__setattr__(
            self, "artifact_hash", _normalized_text("artifact_hash", self.artifact_hash)
        )


@dataclass(frozen=True, slots=True)
class GenerationHistory:
    generation: int
    artifacts: tuple[ArtifactRecord, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    verdict_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if (
            isinstance(self.generation, bool)
            or not isinstance(self.generation, int)
            or self.generation < 1
        ):
            raise ValueError("generation must be a positive integer")
        object.__setattr__(
            self,
            "artifacts",
            tuple(sorted(self.artifacts, key=lambda item: (item.artifact_ref, item.artifact_hash))),
        )
        object.__setattr__(self, "evidence_refs", _sorted_unique(self.evidence_refs))
        object.__setattr__(self, "verdict_refs", _sorted_unique(self.verdict_refs))


@dataclass(frozen=True, slots=True)
class WorkItemState:
    work_item_id: str
    kind: WorkItemKind
    lifecycle: WorkItemLifecycle = WorkItemLifecycle.OPEN
    semantic_maturity: SemanticMaturity = SemanticMaturity.DRAFT
    realization: RealizationStatus = RealizationStatus.NOT_READY
    assurance: AssuranceStatus = AssuranceStatus.UNASSESSED
    realization_effect_id: str | None = None
    current_generation: int = 1
    parent_ids: tuple[str, ...] = ()
    child_ids: tuple[str, ...] = ()
    generations: tuple[GenerationHistory, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "work_item_id", _normalized_text("work_item_id", self.work_item_id)
        )
        if (
            isinstance(self.current_generation, bool)
            or not isinstance(self.current_generation, int)
            or self.current_generation < 1
        ):
            raise ValueError("current_generation must be a positive integer")
        object.__setattr__(self, "kind", WorkItemKind(self.kind))
        object.__setattr__(self, "lifecycle", WorkItemLifecycle(self.lifecycle))
        object.__setattr__(self, "semantic_maturity", SemanticMaturity(self.semantic_maturity))
        object.__setattr__(self, "realization", RealizationStatus(self.realization))
        object.__setattr__(self, "assurance", AssuranceStatus(self.assurance))
        object.__setattr__(
            self,
            "realization_effect_id",
            _normalized_optional_text("realization_effect_id", self.realization_effect_id),
        )
        effect_bound_states = {
            RealizationStatus.RUNNING,
            RealizationStatus.MATERIALIZED,
            RealizationStatus.FAILED,
        }
        if self.realization in effect_bound_states and self.realization_effect_id is None:
            raise ValueError(f"{self.realization.value} realization requires an effect binding")
        if self.realization not in effect_bound_states and self.realization_effect_id is not None:
            raise ValueError(
                f"{self.realization.value} realization cannot retain an effect binding"
            )
        object.__setattr__(self, "parent_ids", _sorted_unique(self.parent_ids))
        object.__setattr__(self, "child_ids", _sorted_unique(self.child_ids))
        generations = tuple(sorted(self.generations, key=lambda item: item.generation))
        if len({item.generation for item in generations}) != len(generations):
            raise ValueError("generation history numbers must be unique")
        if generations and generations[-1].generation != self.current_generation:
            raise ValueError("current_generation must name the latest generation history")
        object.__setattr__(self, "generations", generations)

    def generation_history(self, generation: int | None = None) -> GenerationHistory:
        target = self.current_generation if generation is None else generation
        for history in self.generations:
            if history.generation == target:
                return history
        raise KeyError(target)


@dataclass(frozen=True, slots=True)
class EffectAttemptRecord:
    """Immutable replay-derived audit for one monotonically numbered attempt.

    ``outcome_history`` retains recovery facts such as ``TIMED_OUT -> SUCCEEDED``
    instead of overwriting the uncertainty that preceded reconciliation.
    """

    attempt: int
    lease_token: str
    lease_owner: str
    started_at: str
    outcome_history: tuple[EffectAttemptOutcome, ...] = (EffectAttemptOutcome.RUNNING,)
    completed_at: str | None = None
    result_ref: str | None = None
    result_hash: str | None = None
    reasons: tuple[str, ...] = ()
    reconciliation_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _effect_attempt_number(self.attempt)
        for name in ("lease_token", "lease_owner", "started_at"):
            object.__setattr__(self, name, _normalized_text(name, getattr(self, name)))
        history = _effect_attempt_history(self.outcome_history)
        object.__setattr__(self, "outcome_history", history)
        for name in ("completed_at", "result_ref"):
            object.__setattr__(self, name, _normalized_optional_text(name, getattr(self, name)))
        object.__setattr__(
            self,
            "result_hash",
            _normalized_optional_hash("result_hash", self.result_hash),
        )
        object.__setattr__(self, "reasons", _normalized_history("reasons", self.reasons))
        object.__setattr__(
            self,
            "reconciliation_refs",
            _normalized_history("reconciliation_refs", self.reconciliation_refs),
        )
        _validate_attempt_audit(self)

    @property
    def outcome(self) -> EffectAttemptOutcome:
        return self.outcome_history[-1]

    @property
    def reason(self) -> str | None:
        return None if not self.reasons else self.reasons[-1]


@dataclass(frozen=True, slots=True)
class EffectState:
    effect_id: str
    lifecycle: EffectLifecycle
    work_item_id: str | None
    generation: int | None
    capability: str
    provider: str
    risk_class: str
    idempotency_key: str
    input_ref: str
    input_hash: str
    result_ref: str | None = None
    result_hash: str | None = None
    lease_owner: str | None = None
    lease_token: str | None = None
    lease_expiry: str | None = None
    heartbeat_at: str | None = None
    grant_ref: str | None = None
    grant_hash: str | None = None
    authorization_ref: str | None = None
    authorization_hash: str | None = None
    lease_token_history: tuple[str, ...] = ()
    current_attempt: int = 0
    attempts: tuple[EffectAttemptRecord, ...] = ()
    reconciliation_refs: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in (
            "effect_id",
            "capability",
            "provider",
            "risk_class",
            "idempotency_key",
            "input_ref",
        ):
            object.__setattr__(self, name, _normalized_text(name, getattr(self, name)))
        object.__setattr__(self, "input_hash", _normalized_hash("input_hash", self.input_hash))
        for name in (
            "work_item_id",
            "result_ref",
            "lease_owner",
            "lease_token",
            "lease_expiry",
            "heartbeat_at",
            "grant_ref",
            "authorization_ref",
        ):
            object.__setattr__(self, name, _normalized_optional_text(name, getattr(self, name)))
        object.__setattr__(
            self,
            "result_hash",
            _normalized_optional_hash("result_hash", self.result_hash),
        )
        for name in ("grant_hash", "authorization_hash"):
            object.__setattr__(
                self,
                name,
                _normalized_optional_hash(name, getattr(self, name)),
            )
        object.__setattr__(self, "lifecycle", EffectLifecycle(self.lifecycle))
        object.__setattr__(self, "generation", _effect_generation(self.generation))
        _validate_lease_grant_binding(self)
        lease_history = _effect_lease_history(self)
        object.__setattr__(self, "lease_token_history", lease_history)
        current_attempt = _current_attempt(self.current_attempt)
        attempts = _effect_attempts(
            self.attempts,
            current_attempt=current_attempt,
            lease_history=lease_history,
        )
        object.__setattr__(self, "attempts", attempts)
        object.__setattr__(
            self,
            "reconciliation_refs",
            _normalized_history("reconciliation_refs", self.reconciliation_refs),
        )
        object.__setattr__(self, "reasons", _normalized_history("reasons", self.reasons))
        _validate_effect_result(self)
        _validate_effect_lease_lifecycle(self)
        _validate_effect_attempt_lifecycle(self, attempts)


@dataclass(frozen=True, slots=True)
class AptCycleState:
    cycle_id: str
    lifecycle: CycleLifecycle
    version: int
    fsm_spec_hash: str
    config_version: str
    config_snapshot_ref: str
    config_snapshot_hash: str
    canon_snapshot_ref: str
    canon_snapshot_hash: str
    work_items: tuple[WorkItemState, ...] = ()
    effects: tuple[EffectState, ...] = ()
    terminal_receipt_ref: str | None = None

    def __post_init__(self) -> None:
        for name in (
            "cycle_id",
            "fsm_spec_hash",
            "config_version",
            "config_snapshot_ref",
            "config_snapshot_hash",
            "canon_snapshot_ref",
            "canon_snapshot_hash",
        ):
            object.__setattr__(self, name, _normalized_text(name, getattr(self, name)))
        object.__setattr__(
            self,
            "terminal_receipt_ref",
            _normalized_optional_text("terminal_receipt_ref", self.terminal_receipt_ref),
        )
        if isinstance(self.version, bool) or not isinstance(self.version, int) or self.version < 1:
            raise ValueError("version must be a positive integer")
        object.__setattr__(self, "lifecycle", CycleLifecycle(self.lifecycle))
        work_items = tuple(sorted(self.work_items, key=lambda item: item.work_item_id))
        effects = tuple(sorted(self.effects, key=lambda item: item.effect_id))
        if len({item.work_item_id for item in work_items}) != len(work_items):
            raise ValueError("work_item_id values must be unique within a cycle")
        if len({item.effect_id for item in effects}) != len(effects):
            raise ValueError("effect_id values must be unique within a cycle")
        object.__setattr__(self, "work_items", work_items)
        object.__setattr__(self, "effects", effects)

    def work_item(self, work_item_id: str) -> WorkItemState:
        for item in self.work_items:
            if item.work_item_id == work_item_id:
                return item
        raise KeyError(work_item_id)

    def effect(self, effect_id: str) -> EffectState:
        for item in self.effects:
            if item.effect_id == effect_id:
                return item
        raise KeyError(effect_id)


def state_hash(state: AptCycleState) -> str:
    """Return a stable SHA-256 identity for a fully reduced aggregate state."""

    return canonical_sha256(state)
