"""Domain DTOs for the Harness Console.

These models are intentionally framework-free. FastAPI, SQLite, Postgres, and
the future React client adapt to these shapes; they do not own the domain.

# KG: task-harness-console-event-store-2026-06-24
# KG: plan-harness-console-live-verdict-2026-06-24
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TargetKind(str, Enum):
    OCCAM_CANDIDATE = "occam_candidate"
    LONGINUS_AMBIGUOUS = "longinus_ambiguous"
    EUREKA_ABSTRACT_CLASS = "eureka_abstract_class"
    FIX_ATTEMPT = "fix_attempt"
    LAKATOS_SHIFT = "lakatos_shift"
    ARCHITECTURE_NODE = "architecture_node"
    PROJECT_ASSET = "project_asset"
    RESEARCH_CLAIM = "research_claim"


class VerdictValue(str, Enum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    VERIFY = "VERIFY"
    DEFER = "DEFER"
    CANONICAL = "CANONICAL"
    CANONICAL_DELEGATED = "CANONICAL_DELEGATED"
    PROGRESSIVE = "PROGRESSIVE"
    DEGENERATING = "DEGENERATING"


class RequestStatus(str, Enum):
    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    DEFERRED = "DEFERRED"
    APPLIED = "APPLIED"


class LabelTaskStatus(str, Enum):
    PENDING = "PENDING"
    AI_PROPOSED = "AI_PROPOSED"
    HUMAN_APPROVED = "HUMAN_APPROVED"
    HUMAN_REJECTED = "HUMAN_REJECTED"
    DEFERRED = "DEFERRED"


class ProjectKind(str, Enum):
    PYTHON_REPO = "python_repo"
    NODE_VITE = "node_vite"
    THREE_D = "three_d"
    BEAD = "bead"
    GENERIC_FILES = "generic_files"


class HarnessEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    run_id: str
    sequence: int = Field(ge=0)
    event_type: str = Field(min_length=1)
    source: str = Field(min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


class HumanVerdictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    target_ref: str = Field(min_length=1)
    target_kind: TargetKind
    context: dict[str, Any] = Field(default_factory=dict)
    evidence_refs: list[str] = Field(default_factory=list)
    prior_verdicts: list[str] = Field(default_factory=list)
    recommended_action: str | None = None
    allowed_verdicts: list[VerdictValue]
    status: RequestStatus = RequestStatus.PENDING
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("allowed_verdicts")
    @classmethod
    def _require_allowed_verdicts(cls, values: list[VerdictValue]) -> list[VerdictValue]:
        if not values:
            raise ValueError("allowed_verdicts must not be empty")
        return values


class HumanVerdict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    request_id: str = Field(min_length=1)
    verdict: VerdictValue
    rationale: str = Field(min_length=1)
    reviewer_id: str = Field(min_length=1)
    evidence_refs: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)


class LabelTask(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    project_id: str = Field(min_length=1)
    target_ref: str = Field(min_length=1)
    target_kind: str = Field(min_length=1)
    proposed_label: str | None = None
    allowed_labels: list[str]
    ai_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    evidence_refs: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    blocking_questions: list[str] = Field(default_factory=list)
    status: LabelTaskStatus = LabelTaskStatus.PENDING
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("allowed_labels")
    @classmethod
    def _require_allowed_labels(cls, values: list[str]) -> list[str]:
        if not values:
            raise ValueError("allowed_labels must not be empty")
        return values

    @model_validator(mode="after")
    def _proposal_must_be_allowed(self) -> "LabelTask":
        if self.proposed_label is not None and self.proposed_label not in self.allowed_labels:
            raise ValueError("proposed_label must be one of allowed_labels")
        return self


class ProjectTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    root_path: str = Field(min_length=1)
    kind: ProjectKind | None = None
    display_name: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProjectSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    target_id: str = Field(min_length=1)
    root_path: str = Field(min_length=1)
    adapter: str = Field(min_length=1)
    summary: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


__all__ = [
    "HarnessEvent",
    "HumanVerdict",
    "HumanVerdictRequest",
    "LabelTask",
    "LabelTaskStatus",
    "ProjectKind",
    "ProjectSnapshot",
    "ProjectTarget",
    "RequestStatus",
    "TargetKind",
    "VerdictValue",
    "utc_now",
]
