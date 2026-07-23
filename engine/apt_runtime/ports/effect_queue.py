"""Durable operational queue contract for the APT Slice 2 effect runtime.

The event log remains authoritative for effect lifecycle.  This port owns the
short pre-event reservation, fencing token, heartbeat, and resource exclusion
needed to get a worker to the next canonical effect fact safely.

# KG: apt-tpa-legion-engine-canon-2026-06-12
# Design: ADRs/apt-vnext-slice2-effect-runtime-2026-07-14.md
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from engine.apt_runtime.domain.canonical import (
    MAX_SIGNED_64,
    canonical_sha256,
    canonical_json_bytes,
    normalize_text,
)
from engine.apt_runtime.domain.effect_runtime import (
    ReconciliationOutcome,
    ResourceClaim,
    RuntimeBudget,
    RuntimeUsage,
)
from engine.apt_runtime.domain.events import validate_rfc3339_utc_z
from engine.apt_runtime.ports.event_store import OutboxRecord


class EffectQueueError(RuntimeError):
    """Base class for durable effect-delivery coordination failures."""


class LeaseConflict(EffectQueueError):
    """The outbox row already has a nonterminal lease or token mismatch."""


class LeaseNotFound(EffectQueueError):
    """No durable lease exists for the requested fencing token."""


class ReconciliationProbeConflict(LeaseConflict):
    """Another reconciliation probe already holds the single-flight permit."""


class ReconciliationProbeExhausted(LeaseConflict):
    """The immutable reconciliation-probe budget has been consumed."""


class ResourceClaimConflict(EffectQueueError):
    """A nonterminal lease holds an overlapping incompatible resource claim."""


class EffectQueueCorruption(EffectQueueError):
    """Durable operational rows fail their declared schema or invariants."""


class LeaseStatus(str, Enum):
    """Operational delivery state; canonical effect lifecycle lives in events."""

    RESERVED = "RESERVED"
    ACTIVE = "ACTIVE"
    RUNNING = "RUNNING"
    RECONCILING = "RECONCILING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    ABANDONED = "ABANDONED"


class ReconciliationProbePermitState(str, Enum):
    """Durable lifecycle of one fenced provider-probe generation."""

    ACTIVE = "ACTIVE"
    CONCLUDED = "CONCLUDED"


TERMINAL_LEASE_STATUSES = frozenset(
    {
        LeaseStatus.SUCCEEDED,
        LeaseStatus.FAILED,
        LeaseStatus.CANCELLED,
        LeaseStatus.ABANDONED,
    }
)


def _text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")
    normalized = normalize_text(value)
    if "\x00" in normalized:
        raise ValueError(f"{name} cannot contain U+0000")
    return normalized


def _timestamp(name: str, value: object) -> str:
    text = _text(name, value)
    validate_rfc3339_utc_z(name, text)
    return text


def _sha256(name: str, value: object) -> str:
    text = _text(name, value)
    if len(text) != 64 or any(character not in "0123456789abcdef" for character in text):
        raise ValueError(f"{name} must be a lowercase SHA-256 hex digest")
    return text


def _instant(value: str) -> datetime:
    return datetime.fromisoformat(value[:-1] + "+00:00")


def _nonnegative(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > MAX_SIGNED_64:
        raise ValueError(f"{name} must be a signed 64-bit non-negative integer")
    return value


def _positive(name: str, value: object) -> int:
    number = _nonnegative(name, value)
    if number < 1:
        raise ValueError(f"{name} must be a signed 64-bit positive integer")
    return number


def _optional_text(name: str, value: object) -> str | None:
    return None if value is None else _text(name, value)


def _optional_timestamp(name: str, value: object) -> str | None:
    return None if value is None else _timestamp(name, value)


def _optional_sha256(name: str, value: object) -> str | None:
    return None if value is None else _sha256(name, value)


def _reconciliation_outcome(value: object) -> ReconciliationOutcome:
    try:
        return ReconciliationOutcome(value)
    except ValueError as exc:
        raise ValueError("outcome must be a known reconciliation outcome") from exc


def _evidence_refs(values: object) -> tuple[str, ...]:
    if not isinstance(values, tuple) or not values:
        raise ValueError("evidence_refs must be a non-empty tuple")
    normalized = tuple(
        _text(f"evidence_refs[{index}]", value) for index, value in enumerate(values)
    )
    if len(set(normalized)) != len(normalized):
        raise ValueError("evidence_refs must be unique")
    return normalized


def _validate_conclusion_shape(
    outcome: ReconciliationOutcome,
    *,
    reason: str | None,
    result_ref: str | None,
    result_hash: str | None,
) -> None:
    if outcome is ReconciliationOutcome.APPLIED:
        if result_ref is None or result_hash is None:
            raise ValueError("APPLIED conclusion requires a durable result identity")
        if reason is not None:
            raise ValueError("APPLIED conclusion cannot carry a reason")
        return
    if result_ref is not None or result_hash is not None:
        raise ValueError(f"{outcome.value} conclusion cannot carry a result identity")
    if reason is None:
        raise ValueError(f"{outcome.value} conclusion requires a reason")


def _permit_state(value: object) -> ReconciliationProbePermitState:
    try:
        return ReconciliationProbePermitState(value)
    except ValueError as exc:
        raise ValueError("state must be a known reconciliation permit state") from exc


def _validate_permit_interval(acquired_at: str, expires_at: str) -> None:
    if _instant(expires_at) <= _instant(acquired_at):
        raise ValueError("expires_at must be later than acquired_at")


def _validate_permit_shape(
    state: ReconciliationProbePermitState,
    *,
    acquired_at: str,
    expires_at: str,
    concluded_at: str | None,
    conclusion: object,
) -> None:
    if state is ReconciliationProbePermitState.ACTIVE:
        if concluded_at is not None or conclusion is not None:
            raise ValueError("ACTIVE permit cannot carry a conclusion")
        return
    if concluded_at is None or not isinstance(conclusion, ReconciliationProbeConclusion):
        raise ValueError("CONCLUDED permit requires concluded_at and conclusion")
    if _instant(concluded_at) < _instant(acquired_at):
        raise ValueError("concluded_at cannot precede acquired_at")
    if _instant(concluded_at) >= _instant(expires_at):
        raise ValueError("concluded_at must precede expires_at")


@dataclass(frozen=True, slots=True)
class ReconciliationProbeConclusion:
    """Crash-resumable provider observation sealed under one permit generation."""

    outcome: ReconciliationOutcome
    evidence_refs: tuple[str, ...]
    reason: str | None
    result_ref: str | None = None
    result_hash: str | None = None

    def __post_init__(self) -> None:
        outcome = _reconciliation_outcome(self.outcome)
        evidence_refs = _evidence_refs(self.evidence_refs)
        reason = _optional_text("reason", self.reason)
        result_ref = _optional_text("result_ref", self.result_ref)
        result_hash = _optional_sha256("result_hash", self.result_hash)
        _validate_conclusion_shape(
            outcome,
            reason=reason,
            result_ref=result_ref,
            result_hash=result_hash,
        )
        object.__setattr__(self, "outcome", outcome)
        object.__setattr__(self, "evidence_refs", evidence_refs)
        object.__setattr__(self, "reason", reason)
        object.__setattr__(self, "result_ref", result_ref)
        object.__setattr__(self, "result_hash", result_hash)

    @property
    def conclusion_hash(self) -> str:
        """Canonical digest persisted beside the conclusion document."""

        return canonical_sha256(self)


@dataclass(frozen=True, slots=True)
class ReconciliationProbePermit:
    """A time-bounded generation fence for one reconciliation provider call."""

    permit_token: str
    generation: int
    state: ReconciliationProbePermitState
    acquired_at: str
    expires_at: str
    concluded_at: str | None = None
    conclusion: ReconciliationProbeConclusion | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "permit_token", _text("permit_token", self.permit_token))
        generation = _positive("generation", self.generation)
        state = _permit_state(self.state)
        acquired_at = _timestamp("acquired_at", self.acquired_at)
        expires_at = _timestamp("expires_at", self.expires_at)
        _validate_permit_interval(acquired_at, expires_at)
        concluded_at = _optional_timestamp("concluded_at", self.concluded_at)
        _validate_permit_shape(
            state,
            acquired_at=acquired_at,
            expires_at=expires_at,
            concluded_at=concluded_at,
            conclusion=self.conclusion,
        )
        object.__setattr__(self, "generation", generation)
        object.__setattr__(self, "state", state)
        object.__setattr__(self, "acquired_at", acquired_at)
        object.__setattr__(self, "expires_at", expires_at)
        object.__setattr__(self, "concluded_at", concluded_at)


@dataclass(frozen=True, slots=True)
class ReconciliationProbeAcquisition:
    """Atomic permit acquisition result and its budget-accounting decision."""

    permit: ReconciliationProbePermit
    usage: RuntimeUsage
    charged: bool

    def __post_init__(self) -> None:
        if not isinstance(self.permit, ReconciliationProbePermit):
            raise ValueError("permit must be a ReconciliationProbePermit")
        if not isinstance(self.usage, RuntimeUsage):
            raise ValueError("usage must be RuntimeUsage")
        if not isinstance(self.charged, bool):
            raise ValueError("charged must be bool")


def _claims(values: tuple[ResourceClaim, ...]) -> tuple[ResourceClaim, ...]:
    if not isinstance(values, tuple) or any(not isinstance(item, ResourceClaim) for item in values):
        raise ValueError("resource_claims must be a tuple of ResourceClaim values")
    ordered = tuple(sorted(values, key=canonical_json_bytes))
    encoded = tuple(canonical_json_bytes(item) for item in ordered)
    if len(set(encoded)) != len(encoded):
        raise ValueError("resource_claims must be unique")
    if len({item.resource_key for item in ordered}) != len(ordered):
        raise ValueError("resource_claims must name each resource_key only once")
    return ordered


@dataclass(frozen=True, slots=True)
class LeaseRequest:
    """One deterministic reservation request for an immutable outbox row."""

    outbox: OutboxRecord
    lease_token: str
    lease_owner: str
    claimed_at: str
    lease_expiry: str
    resource_claims: tuple[ResourceClaim, ...]
    budget: RuntimeBudget
    grant_ref: str
    grant_hash: str
    config_version: str
    authorization_ref: str
    authorization_hash: str

    def __post_init__(self) -> None:
        if not isinstance(self.outbox, OutboxRecord):
            raise ValueError("outbox must be an OutboxRecord")
        object.__setattr__(self, "lease_token", _text("lease_token", self.lease_token))
        object.__setattr__(self, "lease_owner", _text("lease_owner", self.lease_owner))
        claimed_at = _timestamp("claimed_at", self.claimed_at)
        lease_expiry = _timestamp("lease_expiry", self.lease_expiry)
        if _instant(lease_expiry) <= _instant(claimed_at):
            raise ValueError("lease_expiry must be later than claimed_at")
        if not isinstance(self.budget, RuntimeBudget):
            raise ValueError("budget must be a RuntimeBudget")
        for name in ("grant_ref", "config_version", "authorization_ref"):
            object.__setattr__(self, name, _text(name, getattr(self, name)))
        for name in ("grant_hash", "authorization_hash"):
            object.__setattr__(self, name, _sha256(name, getattr(self, name)))
        object.__setattr__(self, "claimed_at", claimed_at)
        object.__setattr__(self, "lease_expiry", lease_expiry)
        object.__setattr__(self, "resource_claims", _claims(self.resource_claims))


def _validate_lease_clock(claimed_at: str, heartbeat_at: str, lease_expiry: str) -> None:
    if _instant(heartbeat_at) < _instant(claimed_at):
        raise ValueError("heartbeat_at cannot precede claimed_at")
    if _instant(lease_expiry) <= _instant(heartbeat_at):
        raise ValueError("lease_expiry must be later than heartbeat_at")


def _validate_activation(status: LeaseStatus, *, claimed_at: str, activated_at: str | None) -> None:
    activation_required = {
        LeaseStatus.ACTIVE,
        LeaseStatus.RUNNING,
        LeaseStatus.RECONCILING,
        LeaseStatus.SUCCEEDED,
        LeaseStatus.FAILED,
    }
    if status is LeaseStatus.RESERVED and activated_at is not None:
        raise ValueError("RESERVED lease cannot have activated_at")
    if status in activation_required and activated_at is None:
        raise ValueError(f"{status.value} lease requires activated_at")
    if activated_at is not None and _instant(activated_at) < _instant(claimed_at):
        raise ValueError("activated_at cannot precede claimed_at")


def _validate_completion(status: LeaseStatus, *, claimed_at: str, completed_at: str | None) -> None:
    if status in TERMINAL_LEASE_STATUSES and completed_at is None:
        raise ValueError(f"{status.value} lease requires completed_at")
    if status not in TERMINAL_LEASE_STATUSES and completed_at is not None:
        raise ValueError(f"{status.value} lease cannot have completed_at")
    if completed_at is not None and _instant(completed_at) < _instant(claimed_at):
        raise ValueError("completed_at cannot precede claimed_at")


def _validate_probe_binding(
    status: LeaseStatus,
    *,
    probe_generation: int,
    probe_permit: object,
) -> None:
    if probe_permit is None:
        return
    if not isinstance(probe_permit, ReconciliationProbePermit):
        raise ValueError("probe_permit must be a ReconciliationProbePermit")
    if status is not LeaseStatus.RECONCILING:
        raise ValueError("only a RECONCILING lease may hold a probe permit")
    if probe_permit.generation != probe_generation:
        raise ValueError("probe permit generation must match lease probe_generation")


def _validate_lease_status_fields(
    status: LeaseStatus,
    *,
    attempt: int,
    reconciliation_ref: str | None,
    reason: str | None,
) -> None:
    if status is LeaseStatus.RUNNING and attempt < 1:
        raise ValueError("RUNNING lease requires a positive attempt")
    if status is LeaseStatus.RECONCILING and (reconciliation_ref is None or reason is None):
        raise ValueError("RECONCILING lease requires reconciliation_ref and reason")
    reason_required = {
        LeaseStatus.FAILED,
        LeaseStatus.CANCELLED,
        LeaseStatus.ABANDONED,
    }
    if status in reason_required and reason is None:
        raise ValueError(f"{status.value} lease requires reason")


@dataclass(frozen=True, slots=True)
class LeaseRecord:
    """Self-validating latest operational projection of one lease epoch."""

    outbox_id: str
    stream_id: str
    effect_id: str
    lease_token: str
    lease_epoch: int
    lease_owner: str
    status: LeaseStatus
    claimed_at: str
    activated_at: str | None
    heartbeat_at: str
    lease_expiry: str
    attempt: int
    resource_claims: tuple[ResourceClaim, ...]
    budget: RuntimeBudget
    grant_ref: str
    grant_hash: str
    config_version: str
    authorization_ref: str
    authorization_hash: str
    probe_generation: int = 0
    probe_permit: ReconciliationProbePermit | None = None
    reconciliation_ref: str | None = None
    reason: str | None = None
    completed_at: str | None = None

    def __post_init__(self) -> None:
        for name in (
            "outbox_id",
            "stream_id",
            "effect_id",
            "lease_token",
            "lease_owner",
            "grant_ref",
            "config_version",
            "authorization_ref",
        ):
            object.__setattr__(self, name, _text(name, getattr(self, name)))
        for name in ("grant_hash", "authorization_hash"):
            object.__setattr__(self, name, _sha256(name, getattr(self, name)))
        _positive("lease_epoch", self.lease_epoch)
        status = LeaseStatus(self.status)
        claimed_at = _timestamp("claimed_at", self.claimed_at)
        heartbeat_at = _timestamp("heartbeat_at", self.heartbeat_at)
        lease_expiry = _timestamp("lease_expiry", self.lease_expiry)
        _validate_lease_clock(claimed_at, heartbeat_at, lease_expiry)
        activated_at = _optional_timestamp("activated_at", self.activated_at)
        completed_at = _optional_timestamp("completed_at", self.completed_at)
        attempt = _nonnegative("attempt", self.attempt)
        probe_generation = _nonnegative("probe_generation", self.probe_generation)
        _validate_activation(status, claimed_at=claimed_at, activated_at=activated_at)
        _validate_completion(status, claimed_at=claimed_at, completed_at=completed_at)
        for name in ("reconciliation_ref", "reason"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, _text(name, value))
        _validate_lease_status_fields(
            status,
            attempt=attempt,
            reconciliation_ref=self.reconciliation_ref,
            reason=self.reason,
        )
        _validate_probe_binding(
            status,
            probe_generation=probe_generation,
            probe_permit=self.probe_permit,
        )
        if not isinstance(self.budget, RuntimeBudget):
            raise ValueError("budget must be a RuntimeBudget")
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "claimed_at", claimed_at)
        object.__setattr__(self, "activated_at", activated_at)
        object.__setattr__(self, "heartbeat_at", heartbeat_at)
        object.__setattr__(self, "lease_expiry", lease_expiry)
        object.__setattr__(self, "attempt", attempt)
        object.__setattr__(self, "probe_generation", probe_generation)
        object.__setattr__(self, "resource_claims", _claims(self.resource_claims))
        object.__setattr__(self, "completed_at", completed_at)


class EffectQueue(ABC):
    """Persistence-independent lease journal and resource-claim coordinator."""

    @abstractmethod
    def init_schema(self) -> None:
        """Create or validate the adapter's operational schema."""

    @abstractmethod
    def reserve(self, request: LeaseRequest) -> LeaseRecord:
        """Reserve one outbox row and its resource claims using a fencing token."""

    @abstractmethod
    def activate(self, lease_token: str, *, activated_at: str) -> LeaseRecord:
        """Mark the reservation executable only after EffectLeased is durable."""

    @abstractmethod
    def heartbeat(
        self,
        lease_token: str,
        *,
        lease_owner: str,
        heartbeat_at: str,
        lease_expiry: str,
    ) -> LeaseRecord:
        """Renew an ACTIVE/RUNNING lease using the current fencing token."""

    @abstractmethod
    def start(
        self, lease_token: str, *, lease_owner: str, attempt: int, started_at: str
    ) -> LeaseRecord:
        """Win ACTIVE→RUNNING once after EffectStarted; duplicate starts must conflict."""

    @abstractmethod
    def mark_reconciling(
        self,
        lease_token: str,
        *,
        observed_at: str,
        reconciliation_ref: str,
        reason: str,
        probe_permit: ReconciliationProbePermit | None = None,
    ) -> LeaseRecord:
        """Fence retry while an unknown/expired outcome is reconciled."""

    @abstractmethod
    def finish(
        self,
        lease_token: str,
        *,
        status: LeaseStatus,
        completed_at: str,
        reconciliation_ref: str | None = None,
        reason: str | None = None,
        probe_permit: ReconciliationProbePermit | None = None,
    ) -> LeaseRecord:
        """Close a lease only after the corresponding canonical fact is durable."""

    @abstractmethod
    def usage_for_outbox(self, outbox_id: str) -> RuntimeUsage:
        """Load the canonical accumulated usage for every epoch of one effect request."""

    @abstractmethod
    def record_usage(
        self,
        lease_token: str,
        *,
        delta: RuntimeUsage,
        observed_at: str,
    ) -> RuntimeUsage:
        """Atomically add an explicit execution delta to the outbox usage ledger."""

    @abstractmethod
    def begin_reconciliation_probe(
        self,
        lease_token: str,
        *,
        permit_token: str,
        acquired_at: str,
        expires_at: str,
    ) -> ReconciliationProbeAcquisition:
        """Acquire one generation; expired takeover inherits the logical probe charge."""

    @abstractmethod
    def conclude_reconciliation_probe(
        self,
        lease_token: str,
        *,
        permit: ReconciliationProbePermit,
        concluded_at: str,
        expires_at: str,
        conclusion: ReconciliationProbeConclusion,
        reconciliation_ref: str,
        reason: str,
    ) -> LeaseRecord:
        """Seal an exact active generation before any canonical conclusion mutation."""

    @abstractmethod
    def load(self, lease_token: str) -> LeaseRecord | None:
        """Load one validated lease by fencing token."""

    @abstractmethod
    def latest_for_outbox(self, outbox_id: str) -> LeaseRecord | None:
        """Load the newest lease epoch for an outbox request."""

    @abstractmethod
    def recoverable(self, *, observed_at: str, heartbeat_before: str) -> tuple[LeaseRecord, ...]:
        """Return nonterminal reservations with expired TTL or stale heartbeat."""

    @abstractmethod
    def close(self) -> None:
        """Release adapter-owned resources."""


__all__ = [
    "EffectQueue",
    "EffectQueueCorruption",
    "EffectQueueError",
    "LeaseConflict",
    "LeaseNotFound",
    "LeaseRecord",
    "LeaseRequest",
    "LeaseStatus",
    "ReconciliationProbeAcquisition",
    "ReconciliationProbeConclusion",
    "ResourceClaimConflict",
    "ReconciliationProbeConflict",
    "ReconciliationProbeExhausted",
    "ReconciliationProbePermit",
    "ReconciliationProbePermitState",
    "TERMINAL_LEASE_STATUSES",
]
