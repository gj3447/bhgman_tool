"""Pure CandidateArchive projection for durable Eureka creative runs.

The journal is authoritative.  This module contains only versioned event payloads
and a deterministic reducer, so the SQLite projection can be discarded and rebuilt
without model, clock, filesystem, or network calls.

Archive states remain inside Eureka's PROPOSE-only covenant.  ``PROPOSED`` means a
candidate survived the bounded creative loop; it never means canonically accepted or
materialized.

# KG: eureka-canonical-2026-05-26
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from pydantic import BaseModel, Field, model_validator


ARCHIVE_EVENT_SCHEMA = "bhgman.eureka.archive.v1"
CANDIDATE_OBSERVED = "CandidateObserved.v1"
CANDIDATE_EVALUATED = "CandidateEvaluated.v1"
CREATIVE_RUN_COMPLETED = "CreativeRunCompleted.v1"
ARCHIVE_EVENT_TYPES = frozenset(
    {CANDIDATE_OBSERVED, CANDIDATE_EVALUATED, CREATIVE_RUN_COMPLETED}
)

_SHA256_PATTERN = r"^[0-9a-f]{64}$"


class ArchiveProjectionError(RuntimeError):
    """A journal event cannot be applied to the CandidateArchive projection."""


class ArchiveStatus(str, Enum):
    """Latest bounded-loop disposition; no value grants canon or Hades authority."""

    OBSERVED = "OBSERVED"
    PROPOSED = "PROPOSED"
    REJECTED = "REJECTED"


class CandidateObserved(BaseModel):
    """One producer occurrence of a content-addressed candidate."""

    candidate_digest: str = Field(..., pattern=_SHA256_PATTERN)
    occurrence_id: str = Field(..., pattern=_SHA256_PATTERN)
    semantic_fingerprint: str = Field(..., pattern=_SHA256_PATTERN)
    candidate_ref: str = Field(..., pattern=_SHA256_PATTERN)
    context_ref: str = Field(..., pattern=_SHA256_PATTERN)
    proposal_ref: str = Field(..., pattern=_SHA256_PATTERN)
    input_snapshot_hash: str = Field(..., pattern=_SHA256_PATTERN)
    baseline_snapshot_hash: str = Field(..., pattern=_SHA256_PATTERN)
    cycle_id: str = Field(..., min_length=1)
    seed_id: str = Field(..., min_length=1)
    round: int = Field(..., ge=1)
    parent_candidate_digest: str | None = Field(None, pattern=_SHA256_PATTERN)
    source_layer: str = Field(default="SECONDARY_AI", min_length=1)

    @model_validator(mode="after")
    def candidate_blob_is_identity_blob(self) -> "CandidateObserved":
        if self.candidate_ref != self.candidate_digest:
            raise ValueError("candidate_ref must equal the content-addressed candidate_digest")
        return self


class CandidateEvaluated(BaseModel):
    """Bounded-loop disposition for a previously observed candidate."""

    candidate_digest: str = Field(..., pattern=_SHA256_PATTERN)
    occurrence_id: str = Field(..., pattern=_SHA256_PATTERN)
    input_snapshot_hash: str = Field(..., pattern=_SHA256_PATTERN)
    baseline_snapshot_hash: str = Field(..., pattern=_SHA256_PATTERN)
    cycle_id: str = Field(..., min_length=1)
    seed_id: str = Field(..., min_length=1)
    outcome: ArchiveStatus
    critic_receipt_ref: str | None = Field(None, pattern=_SHA256_PATTERN)
    evaluator_receipt_ref: str | None = Field(None, pattern=_SHA256_PATTERN)
    lifecycle_receipt_ref: str | None = Field(None, pattern=_SHA256_PATTERN)
    reasons: tuple[str, ...] = ()
    score_min: float | None = Field(None, ge=0.0, le=1.0)
    gate_config_hash: str | None = Field(None, pattern=_SHA256_PATTERN)

    @model_validator(mode="after")
    def outcome_is_terminal_for_this_evaluation(self) -> "CandidateEvaluated":
        if self.outcome is ArchiveStatus.OBSERVED:
            raise ValueError("CandidateEvaluated outcome cannot be OBSERVED")
        if self.outcome is ArchiveStatus.PROPOSED and not all(
            (
                self.critic_receipt_ref,
                self.evaluator_receipt_ref,
                self.lifecycle_receipt_ref,
            )
        ):
            raise ValueError(
                "PROPOSED requires critic, executable evaluator, and lifecycle receipts"
            )
        return self


class CreativeRunCompleted(BaseModel):
    """Terminal summary retained in the journal; it does not alter candidate rows."""

    context_ref: str = Field(..., pattern=_SHA256_PATTERN)
    outcome: str = Field(..., min_length=1)
    state: str = Field(..., min_length=1)
    rounds: int = Field(..., ge=0)
    model_calls: int = Field(..., ge=0)
    stop_reason: str = ""


@dataclass(frozen=True)
class EventPosition:
    """Journal coordinates supplied by the durable adapter, not by event producers."""

    global_seq: int
    run_id: str
    run_seq: int

    def __post_init__(self) -> None:
        if self.global_seq < 1 or self.run_seq < 1:
            raise ValueError("journal sequences must be positive")
        if not self.run_id:
            raise ValueError("run_id must not be blank")


class CandidateArchiveEntry(BaseModel):
    """Rebuildable summary view over all occurrences of one candidate digest."""

    candidate_digest: str = Field(..., pattern=_SHA256_PATTERN)
    semantic_fingerprint: str = Field(..., pattern=_SHA256_PATTERN)
    candidate_ref: str = Field(..., pattern=_SHA256_PATTERN)
    first_context_ref: str = Field(..., pattern=_SHA256_PATTERN)
    last_context_ref: str = Field(..., pattern=_SHA256_PATTERN)
    latest_input_snapshot_hash: str = Field(..., pattern=_SHA256_PATTERN)
    latest_baseline_snapshot_hash: str = Field(..., pattern=_SHA256_PATTERN)
    first_proposal_ref: str = Field(..., pattern=_SHA256_PATTERN)
    last_proposal_ref: str = Field(..., pattern=_SHA256_PATTERN)
    status: ArchiveStatus
    latest_critic_receipt_ref: str | None = Field(None, pattern=_SHA256_PATTERN)
    latest_evaluator_receipt_ref: str | None = Field(None, pattern=_SHA256_PATTERN)
    latest_lifecycle_receipt_ref: str | None = Field(None, pattern=_SHA256_PATTERN)
    rejection_reasons: tuple[str, ...] = ()
    score_min: float | None = Field(None, ge=0.0, le=1.0)
    gate_config_hash: str | None = Field(None, pattern=_SHA256_PATTERN)
    first_cycle_id: str = Field(..., min_length=1)
    last_cycle_id: str = Field(..., min_length=1)
    first_seed_id: str = Field(..., min_length=1)
    last_seed_id: str = Field(..., min_length=1)
    first_global_seq: int = Field(..., ge=1)
    last_global_seq: int = Field(..., ge=1)
    seen_count: int = Field(..., ge=1)
    latest_round: int = Field(..., ge=1)
    latest_parent_candidate_digest: str | None = Field(None, pattern=_SHA256_PATTERN)
    latest_occurrence_id: str = Field(..., pattern=_SHA256_PATTERN)
    source_layer: str = Field(..., min_length=1)


def payload_candidate_digest(event_type: str, payload: dict) -> str | None:
    """Return the candidate identity after validating a projection event payload."""

    if event_type == CANDIDATE_OBSERVED:
        return CandidateObserved.model_validate(payload).candidate_digest
    if event_type == CANDIDATE_EVALUATED:
        return CandidateEvaluated.model_validate(payload).candidate_digest
    if event_type == CREATIVE_RUN_COMPLETED:
        CreativeRunCompleted.model_validate(payload)
        return None
    return None


def reduce_candidate_archive(
    current: CandidateArchiveEntry | None,
    event_type: str,
    payload: dict,
    position: EventPosition,
) -> CandidateArchiveEntry | None:
    """Apply one event to one candidate row.

    Unknown event types are intentionally ignored so other Eureka journal facts can
    share the store.  Known events are fail-closed: malformed payloads, evaluation
    before observation, or identity drift raise :class:`ArchiveProjectionError`.
    """

    try:
        if current is not None and position.global_seq < current.last_global_seq:
            raise ArchiveProjectionError(
                f"stale archive event {position.global_seq} < {current.last_global_seq}"
            )
        if current is not None and position.global_seq == current.last_global_seq:
            return current
        if event_type == CANDIDATE_OBSERVED:
            observed = CandidateObserved.model_validate(payload)
            return _observe(current, observed, position)
        if event_type == CANDIDATE_EVALUATED:
            evaluated = CandidateEvaluated.model_validate(payload)
            return _evaluate(current, evaluated, position)
        if event_type == CREATIVE_RUN_COMPLETED:
            CreativeRunCompleted.model_validate(payload)
            return current
        return current
    except ArchiveProjectionError:
        raise
    except Exception as error:
        raise ArchiveProjectionError(
            f"invalid {event_type} payload at global_seq={position.global_seq}: {error}"
        ) from error


def _observe(
    current: CandidateArchiveEntry | None,
    observed: CandidateObserved,
    position: EventPosition,
) -> CandidateArchiveEntry:
    if current is None:
        return CandidateArchiveEntry(
            candidate_digest=observed.candidate_digest,
            semantic_fingerprint=observed.semantic_fingerprint,
            candidate_ref=observed.candidate_ref,
            first_context_ref=observed.context_ref,
            last_context_ref=observed.context_ref,
            latest_input_snapshot_hash=observed.input_snapshot_hash,
            latest_baseline_snapshot_hash=observed.baseline_snapshot_hash,
            first_proposal_ref=observed.proposal_ref,
            last_proposal_ref=observed.proposal_ref,
            status=ArchiveStatus.OBSERVED,
            first_cycle_id=observed.cycle_id,
            last_cycle_id=observed.cycle_id,
            first_seed_id=observed.seed_id,
            last_seed_id=observed.seed_id,
            first_global_seq=position.global_seq,
            last_global_seq=position.global_seq,
            seen_count=1,
            latest_round=observed.round,
            latest_parent_candidate_digest=observed.parent_candidate_digest,
            latest_occurrence_id=observed.occurrence_id,
            source_layer=observed.source_layer,
        )

    if current.candidate_digest != observed.candidate_digest:
        raise ArchiveProjectionError("candidate lookup returned a different digest")
    if current.candidate_ref != observed.candidate_ref:
        raise ArchiveProjectionError(
            f"candidate content drift for {observed.candidate_digest}: candidate_ref changed"
        )
    if current.semantic_fingerprint != observed.semantic_fingerprint:
        raise ArchiveProjectionError(
            f"candidate identity drift for {observed.candidate_digest}: fingerprint changed"
        )
    return current.model_copy(
        update={
            "last_context_ref": observed.context_ref,
            "latest_input_snapshot_hash": observed.input_snapshot_hash,
            "latest_baseline_snapshot_hash": observed.baseline_snapshot_hash,
            "last_proposal_ref": observed.proposal_ref,
            "last_cycle_id": observed.cycle_id,
            "last_seed_id": observed.seed_id,
            "last_global_seq": position.global_seq,
            "seen_count": current.seen_count + 1,
            "latest_round": observed.round,
            "latest_parent_candidate_digest": observed.parent_candidate_digest,
            "latest_occurrence_id": observed.occurrence_id,
            "status": ArchiveStatus.OBSERVED,
            "latest_critic_receipt_ref": None,
            "latest_evaluator_receipt_ref": None,
            "latest_lifecycle_receipt_ref": None,
            "rejection_reasons": (),
            "score_min": None,
            "gate_config_hash": None,
            "source_layer": observed.source_layer,
        }
    )


def _evaluate(
    current: CandidateArchiveEntry | None,
    evaluated: CandidateEvaluated,
    position: EventPosition,
) -> CandidateArchiveEntry:
    if current is None:
        raise ArchiveProjectionError(
            f"candidate {evaluated.candidate_digest} evaluated before CandidateObserved"
        )
    if current.candidate_digest != evaluated.candidate_digest:
        raise ArchiveProjectionError("candidate lookup returned a different digest")
    if current.latest_occurrence_id != evaluated.occurrence_id:
        raise ArchiveProjectionError("evaluation is not bound to the latest observed occurrence")
    if (
        current.last_cycle_id != evaluated.cycle_id
        or current.last_seed_id != evaluated.seed_id
        or current.latest_input_snapshot_hash != evaluated.input_snapshot_hash
        or current.latest_baseline_snapshot_hash != evaluated.baseline_snapshot_hash
    ):
        raise ArchiveProjectionError(
            "evaluation context snapshots do not match observed occurrence"
        )
    reasons = tuple(dict.fromkeys(reason for reason in evaluated.reasons if reason))
    return current.model_copy(
        update={
            "status": evaluated.outcome,
            "latest_critic_receipt_ref": evaluated.critic_receipt_ref,
            "latest_evaluator_receipt_ref": evaluated.evaluator_receipt_ref,
            "latest_lifecycle_receipt_ref": evaluated.lifecycle_receipt_ref,
            "rejection_reasons": reasons if evaluated.outcome is ArchiveStatus.REJECTED else (),
            "score_min": evaluated.score_min,
            "gate_config_hash": evaluated.gate_config_hash,
            "last_global_seq": position.global_seq,
        }
    )


__all__ = [
    "ARCHIVE_EVENT_SCHEMA",
    "ARCHIVE_EVENT_TYPES",
    "CANDIDATE_EVALUATED",
    "CANDIDATE_OBSERVED",
    "CREATIVE_RUN_COMPLETED",
    "ArchiveProjectionError",
    "ArchiveStatus",
    "CandidateArchiveEntry",
    "CandidateEvaluated",
    "CandidateObserved",
    "CreativeRunCompleted",
    "EventPosition",
    "payload_candidate_digest",
    "reduce_candidate_archive",
]
