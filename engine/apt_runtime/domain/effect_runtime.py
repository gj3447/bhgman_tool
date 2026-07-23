"""Pure domain contracts for the APT vNext Slice 2 effect runtime.

The module contains no clock, random, storage, or provider dependency.  Budget
and stuck decisions are functions of explicit immutable inputs so they can be
replayed and audited.

# KG: apt-tpa-legion-engine-canon-2026-06-12
# KG: APT_SCW_TDAD_canonical
# Design: SYMPOSIUM/THEORY/APT/vnext/APT_ENGINE_FSM_DESIGN_2026-07-13.md §6.6,
#         §10.4, §12.4, §13, §18 Slice 2
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .canonical import (
    MAX_SIGNED_64,
    canonical_json_bytes,
    canonical_sha256,
    normalize_text,
)


class RuntimeContractError(ValueError):
    """An effect-runtime value violates its replayable domain contract."""


class ExecutionOutcome(str, Enum):
    """Immediate provider observation after one execution attempt."""

    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"


class ReconciliationOutcome(str, Enum):
    """Provider observation made after an execution outcome was uncertain.

    ``NOT_APPLIED`` is a final assertion for the fenced execution identity: no
    matching mutation was committed and no already-dispatched invocation can
    commit it later.  A provider that cannot establish both conditions must
    return ``UNKNOWN``; a point-in-time absence check is not sufficient to open
    retry or release resource claims.
    """

    APPLIED = "APPLIED"
    NOT_APPLIED = "NOT_APPLIED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"


class ResourceAccess(str, Enum):
    """Coordination mode for one canonical resource identity."""

    SHARED_READ = "SHARED_READ"
    EXCLUSIVE_WRITE = "EXCLUSIVE_WRITE"


class BudgetLimit(str, Enum):
    """Stable reason codes emitted by deterministic budget evaluation."""

    ATTEMPTS = "ATTEMPTS"
    RECONCILIATION_PROBES = "RECONCILIATION_PROBES"
    RUNTIME = "RUNTIME"
    COST = "COST"
    NO_PROGRESS = "NO_PROGRESS"


def _text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value:
        raise RuntimeContractError(f"{name} must be a non-empty string")
    normalized = normalize_text(value)
    if "\x00" in normalized:
        raise RuntimeContractError(f"{name} cannot contain U+0000")
    return normalized


def _nonnegative_integer(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= MAX_SIGNED_64:
        raise RuntimeContractError(f"{name} must be a signed 64-bit non-negative integer")
    return value


def _positive_integer(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= MAX_SIGNED_64:
        raise RuntimeContractError(f"{name} must be a signed 64-bit positive integer")
    return value


def _hash(name: str, value: object) -> str:
    text = _text(name, value)
    if len(text) != 64 or any(character not in "0123456789abcdef" for character in text):
        raise RuntimeContractError(f"{name} must be a lowercase SHA-256 hex digest")
    return text


def _resource_key(value: object) -> str:
    text = _text("resource_key", value)
    if "://" in text:
        scheme, path = text.split("://", 1)
        if not scheme or "/" in scheme:
            raise RuntimeContractError("resource_key has an invalid URI scheme")
        prefix = f"{scheme}://"
    else:
        path = text
        prefix = ""
    segments = path.split("/")
    if any(segment in {"", ".", ".."} for segment in segments):
        raise RuntimeContractError(
            "resource_key cannot contain empty, dot, dot-dot, repeated, or trailing segments"
        )
    return prefix + "/".join(segments)


def _resource_segments(value: str) -> tuple[str, ...]:
    if "://" not in value:
        return tuple(value.split("/"))
    scheme, path = value.split("://", 1)
    return (f"{scheme}://", *path.split("/"))


def _checked_add(name: str, left: int, right: int) -> int:
    total = left + right
    if total > MAX_SIGNED_64:
        raise RuntimeContractError(f"{name} exceeds the signed 64-bit range")
    return total


@dataclass(frozen=True, slots=True)
class ResourceClaim:
    """A normalized resource identity and its shared/exclusive access mode."""

    resource_key: str
    access: ResourceAccess

    def __post_init__(self) -> None:
        object.__setattr__(self, "resource_key", _resource_key(self.resource_key))
        try:
            access = ResourceAccess(self.access)
        except ValueError as exc:
            raise RuntimeContractError("access must be SHARED_READ or EXCLUSIVE_WRITE") from exc
        object.__setattr__(self, "access", access)

    def overlaps(self, other: "ResourceClaim") -> bool:
        """Return whether slash-delimited scopes are equal or hierarchical."""

        if not isinstance(other, ResourceClaim):
            return False
        left = _resource_segments(self.resource_key)
        right = _resource_segments(other.resource_key)
        shared = min(len(left), len(right))
        return left[:shared] == right[:shared]

    def conflicts_with(self, other: "ResourceClaim") -> bool:
        """Return whether overlapping claims require serialization."""

        if not self.overlaps(other):
            return False
        return ResourceAccess.EXCLUSIVE_WRITE in (self.access, other.access)


@dataclass(frozen=True, slots=True)
class RuntimeBudget:
    """Immutable upper bounds snapshotted for one effect-runtime cycle."""

    max_attempts: int
    max_runtime_seconds: int
    max_cost_units: int
    max_no_progress: int
    max_reconciliation_probes: int = 3

    def __post_init__(self) -> None:
        for name in (
            "max_attempts",
            "max_runtime_seconds",
            "max_cost_units",
            "max_no_progress",
            "max_reconciliation_probes",
        ):
            object.__setattr__(self, name, _positive_integer(name, getattr(self, name)))


def _grant_claims(value: object) -> tuple[ResourceClaim, ...]:
    if not isinstance(value, tuple) or any(not isinstance(item, ResourceClaim) for item in value):
        raise RuntimeContractError("resource_claims must be a tuple of ResourceClaim values")
    ordered = tuple(sorted(value, key=canonical_json_bytes))
    if not ordered:
        raise RuntimeContractError("resource_claims must contain at least one claim")
    if len({claim.resource_key for claim in ordered}) != len(ordered):
        raise RuntimeContractError("resource_claims must name each resource_key only once")
    return ordered


@dataclass(frozen=True, slots=True)
class EffectExecutionGrant:
    """Immutable authorization/configuration snapshot for one cycle effect."""

    grant_ref: str
    cycle_id: str
    effect_id: str
    capability: str
    provider: str
    risk_class: str
    config_version: str
    resource_claims: tuple[ResourceClaim, ...]
    budget: RuntimeBudget
    authorization_ref: str
    authorization_hash: str
    grant_hash: str = field(init=False)

    def __post_init__(self) -> None:
        for name in (
            "grant_ref",
            "cycle_id",
            "effect_id",
            "capability",
            "provider",
            "risk_class",
            "config_version",
            "authorization_ref",
        ):
            object.__setattr__(self, name, _text(name, getattr(self, name)))
        if not isinstance(self.budget, RuntimeBudget):
            raise RuntimeContractError("budget must be RuntimeBudget")
        claims = _grant_claims(self.resource_claims)
        authorization_hash = _hash("authorization_hash", self.authorization_hash)
        object.__setattr__(self, "resource_claims", claims)
        object.__setattr__(self, "authorization_hash", authorization_hash)
        object.__setattr__(
            self,
            "grant_hash",
            canonical_sha256(
                {
                    "grant_ref": self.grant_ref,
                    "cycle_id": self.cycle_id,
                    "effect_id": self.effect_id,
                    "capability": self.capability,
                    "provider": self.provider,
                    "risk_class": self.risk_class,
                    "config_version": self.config_version,
                    "resource_claims": claims,
                    "budget": self.budget,
                    "authorization_ref": self.authorization_ref,
                    "authorization_hash": authorization_hash,
                }
            ),
        )


@dataclass(frozen=True, slots=True)
class RuntimeUsage:
    """Immutable accumulated usage or one explicitly labelled usage delta."""

    attempts: int = 0
    runtime_seconds: int = 0
    cost_units: int = 0
    no_progress: int = 0
    reconciliation_probes: int = 0
    progress_signature: str | None = None

    def __post_init__(self) -> None:
        for name in (
            "attempts",
            "runtime_seconds",
            "cost_units",
            "no_progress",
            "reconciliation_probes",
        ):
            object.__setattr__(self, name, _nonnegative_integer(name, getattr(self, name)))
        if self.progress_signature is not None:
            object.__setattr__(
                self,
                "progress_signature",
                _hash("progress_signature", self.progress_signature),
            )

    def observe_progress(self, signature: str) -> "RuntimeUsage":
        """Return usage with a deterministic consecutive no-progress observation."""

        current = _hash("progress_signature", signature)
        unchanged = self.progress_signature == current
        no_progress = _checked_add("no_progress", self.no_progress, 1) if unchanged else 0
        return RuntimeUsage(
            attempts=self.attempts,
            runtime_seconds=self.runtime_seconds,
            cost_units=self.cost_units,
            no_progress=no_progress,
            reconciliation_probes=self.reconciliation_probes,
            progress_signature=current,
        )

    def add(self, delta: "RuntimeUsage") -> "RuntimeUsage":
        """Accumulate an explicit usage delta and observe its progress signature."""

        if not isinstance(delta, RuntimeUsage):
            raise RuntimeContractError("delta must be RuntimeUsage")
        combined = RuntimeUsage(
            attempts=_checked_add("attempts", self.attempts, delta.attempts),
            runtime_seconds=_checked_add(
                "runtime_seconds", self.runtime_seconds, delta.runtime_seconds
            ),
            cost_units=_checked_add("cost_units", self.cost_units, delta.cost_units),
            no_progress=_checked_add("no_progress", self.no_progress, delta.no_progress),
            reconciliation_probes=_checked_add(
                "reconciliation_probes",
                self.reconciliation_probes,
                delta.reconciliation_probes,
            ),
            progress_signature=self.progress_signature,
        )
        if delta.progress_signature is None:
            return combined
        return combined.observe_progress(delta.progress_signature)


@dataclass(frozen=True, slots=True)
class BudgetDecision:
    """Deterministic and auditable answer from ``evaluate_budget``."""

    exhausted: bool
    limits: tuple[BudgetLimit, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.exhausted, bool):
            raise RuntimeContractError("exhausted must be a boolean")
        if not isinstance(self.limits, tuple):
            raise RuntimeContractError("limits must be a tuple")
        try:
            supplied = tuple(BudgetLimit(item) for item in self.limits)
        except ValueError as exc:
            raise RuntimeContractError("limits contains an unknown budget limit") from exc
        normalized = tuple(limit for limit in BudgetLimit if limit in supplied)
        if len(normalized) != len(supplied):
            raise RuntimeContractError("limits must be unique")
        if self.exhausted != bool(normalized):
            raise RuntimeContractError("exhausted must agree with limits")
        object.__setattr__(self, "limits", normalized)


def progress_signature(value: object) -> str:
    """Hash explicit replayable progress facts without consulting ambient state."""

    return canonical_sha256(value)


def detect_stuck(budget: RuntimeBudget, usage: RuntimeUsage) -> bool:
    """Return whether the consecutive no-progress limit has been reached."""

    _require_budget_and_usage(budget, usage)
    return usage.no_progress >= budget.max_no_progress


def _require_budget_and_usage(budget: RuntimeBudget, usage: RuntimeUsage) -> None:
    if not isinstance(budget, RuntimeBudget):
        raise RuntimeContractError("budget must be RuntimeBudget")
    if not isinstance(usage, RuntimeUsage):
        raise RuntimeContractError("usage must be RuntimeUsage")


def evaluate_budget(budget: RuntimeBudget, usage: RuntimeUsage) -> BudgetDecision:
    """Return every limit reached at the supplied immutable usage snapshot."""

    _require_budget_and_usage(budget, usage)
    reached = {
        BudgetLimit.ATTEMPTS: usage.attempts >= budget.max_attempts,
        BudgetLimit.RECONCILIATION_PROBES: (
            usage.reconciliation_probes >= budget.max_reconciliation_probes
        ),
        BudgetLimit.RUNTIME: usage.runtime_seconds >= budget.max_runtime_seconds,
        BudgetLimit.COST: usage.cost_units >= budget.max_cost_units,
        BudgetLimit.NO_PROGRESS: detect_stuck(budget, usage),
    }
    limits = tuple(limit for limit in BudgetLimit if reached[limit])
    return BudgetDecision(exhausted=bool(limits), limits=limits)


__all__ = [
    "BudgetDecision",
    "BudgetLimit",
    "EffectExecutionGrant",
    "ExecutionOutcome",
    "ReconciliationOutcome",
    "ResourceAccess",
    "ResourceClaim",
    "RuntimeBudget",
    "RuntimeContractError",
    "RuntimeUsage",
    "detect_stuck",
    "evaluate_budget",
    "progress_signature",
]
