"""Immutable event envelope for the APT vNext Slice 0 reducer.

KG: apt-tpa-legion-engine-canon-2026-06-12
KG: verdict-bihaenggiman-7commander-unify-2026-06-07
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import re

from .canonical import (
    CanonicalEncodingError,
    CanonicalValue,
    as_mapping,
    canonical_sha256,
    deep_freeze,
    normalize_text,
)


class EventSchemaError(ValueError):
    """Raised when an event envelope violates its transport-level schema."""


class GuardResult(str, Enum):
    PASS = "PASS"
    DENY = "DENY"
    INCONCLUSIVE = "INCONCLUSIVE"
    ERROR = "ERROR"


class EventType(str, Enum):
    CYCLE_CREATED = "CycleCreated"
    CYCLE_STARTED = "CycleStarted"
    CYCLE_WAITING_ENTERED = "CycleWaitingEntered"
    CYCLE_RESUMED = "CycleResumed"
    CYCLE_RECOVERY_STARTED = "CycleRecoveryStarted"
    CYCLE_RECOVERED = "CycleRecovered"
    CYCLE_RECOVERY_DEFERRED = "CycleRecoveryDeferred"
    CYCLE_COMPLETED = "CycleCompleted"
    CYCLE_FAILED = "CycleFailed"
    CYCLE_CANCELLED = "CycleCancelled"
    CYCLE_SUPERSEDED = "CycleSuperseded"
    WORK_ITEM_OPENED = "WorkItemOpened"
    WORK_ITEM_CLOSED = "WorkItemClosed"
    WORK_ITEM_SUPERSEDED = "WorkItemSuperseded"
    ANCHOR_ACCEPTED = "AnchorAccepted"
    ATOMICITY_ACCEPTED = "AtomicityAccepted"
    DECOMPOSITION_STARTED = "DecompositionStarted"
    CHILDREN_ATTACHED = "ChildrenAttached"
    CRYSTALLIZATION_STARTED = "CrystallizationStarted"
    CONTRACT_ACCEPTED = "ContractAccepted"
    CORRECTION_OPENED = "CorrectionOpened"
    DISPATCH_PLANNED = "DispatchPlanned"
    REALIZATION_STARTED = "RealizationStarted"
    ARTIFACT_MATERIALIZED = "ArtifactMaterialized"
    REALIZATION_FAILED = "RealizationFailed"
    REALIZATION_RETRY_APPROVED = "RealizationRetryApproved"
    ARTIFACT_INVALIDATED = "ArtifactInvalidated"
    VERIFICATION_REQUESTED = "VerificationRequested"
    VERIFICATION_ACCEPTED = "VerificationAccepted"
    VERIFICATION_REFUTED = "VerificationRefuted"
    VERIFICATION_INCONCLUSIVE = "VerificationInconclusive"
    NEW_EVIDENCE_SUBMITTED = "NewEvidenceSubmitted"
    EVIDENCE_INVALIDATED = "EvidenceInvalidated"
    EFFECT_QUEUED = "EffectQueued"
    EFFECT_LEASED = "EffectLeased"
    EFFECT_STARTED = "EffectStarted"
    EFFECT_SUCCEEDED = "EffectSucceeded"
    EFFECT_FAILED = "EffectFailed"
    EFFECT_LEASE_EXPIRED = "EffectLeaseExpired"
    EFFECT_TIMED_OUT = "EffectTimedOut"
    EFFECT_RETRY_QUEUED = "EffectRetryQueued"
    EFFECT_CANCELLED = "EffectCancelled"


def payload_hash(payload: Mapping[str, object]) -> str:
    """Hash an event payload using apt-canonical-json-v1."""

    try:
        return canonical_sha256(payload)
    except CanonicalEncodingError as exc:
        raise EventSchemaError(str(exc)) from exc


def _require_text(name: str, value: str) -> str:
    if not isinstance(value, str) or not value:
        raise EventSchemaError(f"{name} must be a non-empty string")
    return normalize_text(value)


def _require_positive_integer(name: str, value: object) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise EventSchemaError(f"{name} must be a positive integer")


_RFC3339_UTC_Z = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z\Z"
)


def validate_rfc3339_utc_z(name: str, value: str) -> None:
    """Require the extended RFC3339 UTC ``Z`` form declared by the v1 profile."""

    if _RFC3339_UTC_Z.fullmatch(value) is None:
        raise EventSchemaError(f"{name} must be an extended RFC3339 UTC timestamp ending in Z")
    try:
        datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise EventSchemaError(
            f"{name} must be an extended RFC3339 UTC timestamp ending in Z"
        ) from exc


@dataclass(frozen=True, slots=True)
class EventEnvelope:
    """A replayable event with no ambient clock, random, or I/O dependency."""

    event_id: str
    stream_id: str
    stream_version: int
    event_type: EventType
    schema_version: str
    fsm_spec_hash: str
    cycle_id: str
    work_item_id: str | None
    effect_id: str | None
    generation: int | None
    actor: str
    correlation_id: str
    causation_id: str
    command_id: str
    config_version: str
    payload: Mapping[str, CanonicalValue]
    payload_hash: str
    created_at: str

    def __post_init__(self) -> None:
        for name in (
            "event_id",
            "stream_id",
            "schema_version",
            "fsm_spec_hash",
            "cycle_id",
            "actor",
            "correlation_id",
            "causation_id",
            "command_id",
            "config_version",
            "created_at",
        ):
            object.__setattr__(self, name, _require_text(name, getattr(self, name)))
        _require_positive_integer("stream_version", self.stream_version)
        if self.generation is not None:
            _require_positive_integer("generation", self.generation)
        for name in ("work_item_id", "effect_id"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, _require_text(name, value))
        validate_rfc3339_utc_z("created_at", self.created_at)
        try:
            event_type = EventType(self.event_type)
            frozen_payload = as_mapping(deep_freeze(self.payload))
            calculated_hash = payload_hash(frozen_payload)
        except (CanonicalEncodingError, ValueError) as exc:
            raise EventSchemaError(str(exc)) from exc
        object.__setattr__(self, "event_type", event_type)
        object.__setattr__(self, "payload", frozen_payload)
        if self.payload_hash != calculated_hash:
            raise EventSchemaError(
                "payload_hash does not match the apt-canonical-json-v1 payload digest"
            )

    @classmethod
    def create(
        cls,
        *,
        event_id: str,
        stream_id: str,
        stream_version: int,
        event_type: EventType,
        schema_version: str,
        fsm_spec_hash: str,
        cycle_id: str,
        work_item_id: str | None = None,
        effect_id: str | None = None,
        generation: int | None = None,
        actor: str,
        correlation_id: str,
        causation_id: str,
        command_id: str,
        config_version: str,
        payload: Mapping[str, object],
        created_at: str,
    ) -> "EventEnvelope":
        """Build an envelope and derive its canonical payload digest."""

        try:
            frozen_payload = as_mapping(deep_freeze(payload))
        except CanonicalEncodingError as exc:
            raise EventSchemaError(str(exc)) from exc
        return cls(
            event_id=event_id,
            stream_id=stream_id,
            stream_version=stream_version,
            event_type=event_type,
            schema_version=schema_version,
            fsm_spec_hash=fsm_spec_hash,
            cycle_id=cycle_id,
            work_item_id=work_item_id,
            effect_id=effect_id,
            generation=generation,
            actor=actor,
            correlation_id=correlation_id,
            causation_id=causation_id,
            command_id=command_id,
            config_version=config_version,
            payload=frozen_payload,
            payload_hash=payload_hash(frozen_payload),
            created_at=created_at,
        )
