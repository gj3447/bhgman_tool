"""Immutable aggregate state for the APT vNext Slice 0 reducer.

KG: apt-tpa-legion-engine-canon-2026-06-12
KG: user-verdict-7cmd-need-based-conditional-dispatch-2026-05-30
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .canonical import canonical_sha256, normalize_text


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

    def __post_init__(self) -> None:
        for name in (
            "effect_id",
            "capability",
            "provider",
            "risk_class",
            "idempotency_key",
            "input_ref",
            "input_hash",
        ):
            object.__setattr__(self, name, _normalized_text(name, getattr(self, name)))
        for name in ("work_item_id", "result_ref", "result_hash"):
            object.__setattr__(self, name, _normalized_optional_text(name, getattr(self, name)))
        object.__setattr__(self, "lifecycle", EffectLifecycle(self.lifecycle))
        if self.generation is not None and (
            isinstance(self.generation, bool)
            or not isinstance(self.generation, int)
            or self.generation < 1
        ):
            raise ValueError("effect generation must be a positive integer when present")


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
