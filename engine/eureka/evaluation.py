"""Executable, content-addressed evaluation seam for Eureka proposals.

The creative producer and its LLM critic are untrusted proposal-side actors.  This
module supplies the narrower oracle boundary: an evaluator receives an immutable
request, returns typed check evidence, and cannot retain ``PASS`` unless every
requested check was executed and passed.  Evaluation failures are converted to an
``ERROR`` receipt rather than escaping or being mistaken for success.

The module is deliberately independent of ``creative.py`` so callers can adopt the
seam without creating an import cycle.  It performs no persistence and confers no
canon or materialization authority.

# KG: eureka-canonical-2026-05-26
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import subprocess
from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol, Sequence, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


REQUEST_SCHEMA_VERSION = "bhgman.eureka.evaluation-request.v1"
RECEIPT_SCHEMA_VERSION = "bhgman.eureka.evaluator-receipt.v1"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class _FrozenDict(dict[str, Any]):
    """JSON-serializable dict that cannot drift after content addressing."""

    @staticmethod
    def _immutable(*_args: Any, **_kwargs: Any) -> None:
        raise TypeError("content-addressed evaluation metadata is immutable")

    __setitem__ = _immutable
    __delitem__ = _immutable
    __ior__ = _immutable
    clear = _immutable
    pop = _immutable
    popitem = _immutable
    setdefault = _immutable
    update = _immutable


def _deep_freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return _FrozenDict({str(key): _deep_freeze(child) for key, child in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_deep_freeze(child) for child in value)
    return value


def _canonical_json(value: Any) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _normalized_unique_text(value: Any, *, field_name: str, allow_empty: bool) -> tuple[str, ...]:
    if isinstance(value, str) or value is None:
        raise ValueError(f"{field_name} must be a sequence of strings")
    normalized = tuple(str(item).strip() for item in value)
    if not allow_empty and not normalized:
        raise ValueError(f"{field_name} must not be empty")
    if any(not item for item in normalized):
        raise ValueError(f"{field_name} entries must not be blank")
    if len(set(normalized)) != len(normalized):
        raise ValueError(f"{field_name} entries must be unique")
    return normalized


def _normalized_digests(value: Any, *, field_name: str) -> tuple[str, ...]:
    normalized = _normalized_unique_text(value, field_name=field_name, allow_empty=True)
    if any(_SHA256_RE.fullmatch(item) is None for item in normalized):
        raise ValueError(f"{field_name} entries must be lowercase SHA-256 digests")
    return normalized


class EvaluationVerdict(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    INCONCLUSIVE = "INCONCLUSIVE"
    ERROR = "ERROR"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"


class EvaluationRequest(BaseModel):
    """Exact evidence and critic snapshot an executable evaluation must bind."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = REQUEST_SCHEMA_VERSION
    candidate_digest: str = Field(..., pattern=r"^[0-9a-f]{64}$")
    input_snapshot_hash: str = Field(..., pattern=r"^[0-9a-f]{64}$")
    baseline_snapshot_hash: str = Field(..., pattern=r"^[0-9a-f]{64}$")
    critic_receipt_digest: str = Field(..., pattern=r"^[0-9a-f]{64}$")
    requested_checks: tuple[str, ...] = Field(..., min_length=1)

    @field_validator("schema_version")
    @classmethod
    def schema_is_current(cls, value: str) -> str:
        if value != REQUEST_SCHEMA_VERSION:
            raise ValueError(f"unsupported evaluation request schema: {value!r}")
        return value

    @field_validator("requested_checks", mode="before")
    @classmethod
    def normalize_requested_checks(cls, value: Any) -> tuple[str, ...]:
        return _normalized_unique_text(value, field_name="requested_checks", allow_empty=False)

    @property
    def request_digest(self) -> str:
        return _digest(self)


class CheckResult(BaseModel):
    """One executed, objectively inspectable check."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    check_id: str = Field(..., min_length=1, max_length=160)
    passed: bool
    evidence_digest: str = Field(..., pattern=r"^[0-9a-f]{64}$")
    summary: str = Field(default="", max_length=2000)
    details: dict[str, Any] = Field(default_factory=dict)

    @field_validator("check_id")
    @classmethod
    def normalize_check_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("check_id must not be blank")
        return normalized

    @field_validator("details", mode="after")
    @classmethod
    def freeze_details(cls, value: dict[str, Any]) -> dict[str, Any]:
        return _deep_freeze(value)


class CostMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    wall_time_ms: float = Field(default=0.0, ge=0.0)
    cpu_time_ms: float | None = Field(default=None, ge=0.0)
    tool_calls: int = Field(default=0, ge=0)
    tokens: int = Field(default=0, ge=0)
    monetary_cost_usd: float = Field(default=0.0, ge=0.0)

    @field_validator("wall_time_ms", "cpu_time_ms", "monetary_cost_usd")
    @classmethod
    def finite_costs(cls, value: float | None) -> float | None:
        if value is not None and not math.isfinite(value):
            raise ValueError("cost values must be finite")
        return value


class ContaminationMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    network_accessed: bool = False
    external_state_accessed: bool = False
    benchmark_overlap_detected: bool = False
    notes: tuple[str, ...] = ()

    @field_validator("notes", mode="before")
    @classmethod
    def normalize_notes(cls, value: Any) -> tuple[str, ...]:
        return _normalized_unique_text(value, field_name="contamination.notes", allow_empty=True)


class NondeterminismMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    deterministic: bool = True
    seed: int | None = None
    sources: tuple[str, ...] = ()
    replayable: bool = True

    @field_validator("sources", mode="before")
    @classmethod
    def normalize_sources(cls, value: Any) -> tuple[str, ...]:
        return _normalized_unique_text(value, field_name="nondeterminism.sources", allow_empty=True)


class EvaluationResult(BaseModel):
    """Evaluator-returned observations before request binding is applied."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    verdict: EvaluationVerdict
    checks: tuple[CheckResult, ...] = ()
    objective_vector: dict[str, float] = Field(default_factory=dict)
    counterexamples: tuple[str, ...] = ()
    artifact_digests: tuple[str, ...] = ()
    cost: CostMetadata = Field(default_factory=CostMetadata)
    contamination: ContaminationMetadata = Field(default_factory=ContaminationMetadata)
    nondeterminism: NondeterminismMetadata = Field(default_factory=NondeterminismMetadata)

    @field_validator("counterexamples", mode="before")
    @classmethod
    def normalize_counterexamples(cls, value: Any) -> tuple[str, ...]:
        return _normalized_unique_text(value, field_name="counterexamples", allow_empty=True)

    @field_validator("artifact_digests", mode="before")
    @classmethod
    def normalize_artifact_digests(cls, value: Any) -> tuple[str, ...]:
        return _normalized_digests(value, field_name="artifact_digests")

    @field_validator("objective_vector")
    @classmethod
    def validate_objective_vector(cls, value: dict[str, float]) -> dict[str, float]:
        normalized: dict[str, float] = {}
        for raw_key, raw_score in value.items():
            key = str(raw_key).strip()
            score = float(raw_score)
            if not key:
                raise ValueError("objective_vector keys must not be blank")
            if not math.isfinite(score):
                raise ValueError("objective_vector values must be finite")
            if key in normalized:
                raise ValueError("objective_vector keys must be unique after normalization")
            normalized[key] = score
        return _FrozenDict(normalized)

    @model_validator(mode="after")
    def unique_check_ids(self) -> "EvaluationResult":
        check_ids = [item.check_id for item in self.checks]
        if len(set(check_ids)) != len(check_ids):
            raise ValueError("executed check ids must be unique")
        return self

    @property
    def executed_checks(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks)


class EvaluatorReceipt(BaseModel):
    """Content-addressed, request-bound executable evidence receipt."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = RECEIPT_SCHEMA_VERSION
    request_digest: str = Field(..., pattern=r"^[0-9a-f]{64}$")
    candidate_digest: str = Field(..., pattern=r"^[0-9a-f]{64}$")
    input_snapshot_hash: str = Field(..., pattern=r"^[0-9a-f]{64}$")
    baseline_snapshot_hash: str = Field(..., pattern=r"^[0-9a-f]{64}$")
    critic_receipt_digest: str = Field(..., pattern=r"^[0-9a-f]{64}$")
    evaluator_type: str = Field(..., min_length=1, max_length=160)
    evaluator_version: str = Field(..., min_length=1, max_length=160)
    environment_digest: str = Field(..., pattern=r"^[0-9a-f]{64}$")
    requested_checks: tuple[str, ...] = Field(..., min_length=1)
    executed_checks: tuple[str, ...] = ()
    checks: tuple[CheckResult, ...] = ()
    verdict: EvaluationVerdict
    objective_vector: dict[str, float] = Field(default_factory=dict)
    counterexamples: tuple[str, ...] = ()
    artifact_digests: tuple[str, ...] = ()
    cost: CostMetadata = Field(default_factory=CostMetadata)
    contamination: ContaminationMetadata = Field(default_factory=ContaminationMetadata)
    nondeterminism: NondeterminismMetadata = Field(default_factory=NondeterminismMetadata)
    error_type: str | None = Field(default=None, max_length=200)
    error_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")

    @field_validator("schema_version")
    @classmethod
    def schema_is_current(cls, value: str) -> str:
        if value != RECEIPT_SCHEMA_VERSION:
            raise ValueError(f"unsupported evaluator receipt schema: {value!r}")
        return value

    @field_validator("evaluator_type", "evaluator_version")
    @classmethod
    def normalize_evaluator_identity(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("evaluator identity fields must not be blank")
        return normalized

    @field_validator("requested_checks", mode="before")
    @classmethod
    def normalize_requested_checks(cls, value: Any) -> tuple[str, ...]:
        return _normalized_unique_text(value, field_name="requested_checks", allow_empty=False)

    @field_validator("executed_checks", mode="before")
    @classmethod
    def normalize_executed_checks(cls, value: Any) -> tuple[str, ...]:
        return _normalized_unique_text(value, field_name="executed_checks", allow_empty=True)

    @field_validator("counterexamples", mode="before")
    @classmethod
    def normalize_counterexamples(cls, value: Any) -> tuple[str, ...]:
        return _normalized_unique_text(value, field_name="counterexamples", allow_empty=True)

    @field_validator("artifact_digests", mode="before")
    @classmethod
    def normalize_artifact_digests(cls, value: Any) -> tuple[str, ...]:
        return _normalized_digests(value, field_name="artifact_digests")

    @field_validator("objective_vector")
    @classmethod
    def validate_objective_vector(cls, value: dict[str, float]) -> dict[str, float]:
        return EvaluationResult(
            verdict=EvaluationVerdict.INCONCLUSIVE,
            objective_vector=value,
        ).objective_vector

    @model_validator(mode="after")
    def exact_binding_and_pass_semantics(self) -> "EvaluatorReceipt":
        request = EvaluationRequest(
            candidate_digest=self.candidate_digest,
            input_snapshot_hash=self.input_snapshot_hash,
            baseline_snapshot_hash=self.baseline_snapshot_hash,
            critic_receipt_digest=self.critic_receipt_digest,
            requested_checks=self.requested_checks,
        )
        if self.request_digest != request.request_digest:
            raise ValueError("request_digest does not match bound evaluation request")
        observed = tuple(item.check_id for item in self.checks)
        if self.executed_checks != observed:
            raise ValueError("executed_checks must exactly match checks in execution order")
        if len(set(observed)) != len(observed):
            raise ValueError("executed check ids must be unique")
        if self.verdict is EvaluationVerdict.PASS:
            by_id = {item.check_id: item for item in self.checks}
            missing = [item for item in self.requested_checks if item not in by_id]
            failed = [
                item for item in self.requested_checks if item in by_id and not by_id[item].passed
            ]
            if missing or failed:
                raise ValueError("PASS requires every requested check to execute and pass")
            if self.error_type is not None or self.error_digest is not None:
                raise ValueError("PASS cannot carry evaluator error metadata")
        if (self.error_type is None) != (self.error_digest is None):
            raise ValueError("error_type and error_digest must be present together")
        return self

    @property
    def missing_checks(self) -> tuple[str, ...]:
        executed = set(self.executed_checks)
        return tuple(item for item in self.requested_checks if item not in executed)

    @property
    def passed(self) -> bool:
        return self.verdict is EvaluationVerdict.PASS

    @property
    def receipt_digest(self) -> str:
        return _digest(self)


@runtime_checkable
class ExecutableEvaluator(Protocol):
    evaluator_type: str
    evaluator_version: str
    environment_digest: str

    def evaluate(self, request: EvaluationRequest) -> EvaluationResult: ...


def _fallback_identity(evaluator: Any) -> tuple[str, str, str]:
    evaluator_type = str(getattr(evaluator, "evaluator_type", "")).strip()
    evaluator_version = str(getattr(evaluator, "evaluator_version", "")).strip()
    type_name = f"{type(evaluator).__module__}.{type(evaluator).__qualname__}"
    evaluator_type = (evaluator_type or type_name)[:160]
    evaluator_version = (evaluator_version or "unknown")[:160]
    raw_environment = str(getattr(evaluator, "environment_digest", "")).strip()
    environment_digest = (
        raw_environment
        if _SHA256_RE.fullmatch(raw_environment)
        else _digest(
            {
                "inferred": True,
                "evaluator_type": evaluator_type,
                "evaluator_version": evaluator_version,
                "python_type": type_name,
            }
        )
    )
    return evaluator_type, evaluator_version, environment_digest


def _validated_identity(evaluator: Any) -> tuple[str, str, str]:
    evaluator_type = str(getattr(evaluator, "evaluator_type", "")).strip()
    evaluator_version = str(getattr(evaluator, "evaluator_version", "")).strip()
    environment_digest = str(getattr(evaluator, "environment_digest", "")).strip()
    if not evaluator_type or not evaluator_version:
        raise ValueError("evaluator_type and evaluator_version are required")
    if _SHA256_RE.fullmatch(environment_digest) is None:
        raise ValueError("environment_digest must be a lowercase SHA-256 digest")
    return evaluator_type, evaluator_version, environment_digest


def _error_receipt(
    request: EvaluationRequest,
    evaluator: Any,
    error: Exception,
) -> EvaluatorReceipt:
    evaluator_type, evaluator_version, environment_digest = _fallback_identity(evaluator)
    error_type = type(error).__name__
    error_digest = _digest({"type": error_type, "message": str(error)})
    return EvaluatorReceipt(
        request_digest=request.request_digest,
        candidate_digest=request.candidate_digest,
        input_snapshot_hash=request.input_snapshot_hash,
        baseline_snapshot_hash=request.baseline_snapshot_hash,
        critic_receipt_digest=request.critic_receipt_digest,
        evaluator_type=evaluator_type,
        evaluator_version=evaluator_version,
        environment_digest=environment_digest,
        requested_checks=request.requested_checks,
        executed_checks=(),
        checks=(),
        verdict=EvaluationVerdict.ERROR,
        nondeterminism=NondeterminismMetadata(
            deterministic=False,
            sources=("evaluator_error",),
            replayable=False,
        ),
        error_type=error_type,
        error_digest=error_digest,
    )


def execute_evaluation(
    request: EvaluationRequest,
    evaluator: ExecutableEvaluator,
) -> EvaluatorReceipt:
    """Execute one evaluator call and return a bound receipt, never a false PASS.

    Evaluator exceptions, malformed results, invalid evaluator identity, and subprocess
    timeouts become ``ERROR`` receipts.  A reported ``PASS`` is downgraded to ``FAIL``
    when a requested check ran and failed, or ``INCONCLUSIVE`` when any requested check
    is absent.
    """

    request = EvaluationRequest.model_validate(request)
    try:
        evaluator_type, evaluator_version, environment_digest = _validated_identity(evaluator)
        raw_result = evaluator.evaluate(request)
        result = EvaluationResult.model_validate(raw_result)
    except Exception as error:  # evaluator is an external/untrusted effect boundary
        return _error_receipt(request, evaluator, error)

    by_id = {item.check_id: item for item in result.checks}
    missing = [item for item in request.requested_checks if item not in by_id]
    failed = [item for item in request.requested_checks if item in by_id and not by_id[item].passed]
    verdict = result.verdict
    if verdict is EvaluationVerdict.PASS:
        if missing:
            verdict = EvaluationVerdict.INCONCLUSIVE
        elif failed:
            verdict = EvaluationVerdict.FAIL

    error_type: str | None = None
    error_digest: str | None = None
    if verdict is EvaluationVerdict.ERROR:
        error_type = "EvaluatorReportedError"
        error_digest = _digest(result)

    try:
        return EvaluatorReceipt(
            request_digest=request.request_digest,
            candidate_digest=request.candidate_digest,
            input_snapshot_hash=request.input_snapshot_hash,
            baseline_snapshot_hash=request.baseline_snapshot_hash,
            critic_receipt_digest=request.critic_receipt_digest,
            evaluator_type=evaluator_type,
            evaluator_version=evaluator_version,
            environment_digest=environment_digest,
            requested_checks=request.requested_checks,
            executed_checks=result.executed_checks,
            checks=result.checks,
            verdict=verdict,
            objective_vector=result.objective_vector,
            counterexamples=result.counterexamples,
            artifact_digests=result.artifact_digests,
            cost=result.cost,
            contamination=result.contamination,
            nondeterminism=result.nondeterminism,
            error_type=error_type,
            error_digest=error_digest,
        )
    except Exception as error:
        return _error_receipt(request, evaluator, error)


class CommandEvaluationError(RuntimeError):
    """A command evaluator failed before producing a valid EvaluationResult."""


@dataclass(frozen=True)
class CommandEvaluator:
    """JSON stdin/stdout subprocess evaluator with no shell interpolation."""

    command: Sequence[str]
    evaluator_version: str
    environment_digest: str
    evaluator_type: str = "command"
    timeout_seconds: float = 30.0
    max_output_bytes: int = 1_000_000

    def __post_init__(self) -> None:
        if isinstance(self.command, (str, bytes)):
            raise ValueError("command must be a sequence of argv elements, not a shell string")
        command = tuple(str(item) for item in self.command)
        if not command or any(not item or "\x00" in item for item in command):
            raise ValueError("command must contain non-empty, NUL-free argv elements")
        if not str(self.evaluator_type).strip() or not str(self.evaluator_version).strip():
            raise ValueError("evaluator_type and evaluator_version must not be blank")
        if _SHA256_RE.fullmatch(str(self.environment_digest).strip()) is None:
            raise ValueError("environment_digest must be a lowercase SHA-256 digest")
        if not math.isfinite(self.timeout_seconds) or self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be finite and positive")
        if self.max_output_bytes < 1:
            raise ValueError("max_output_bytes must be positive")
        object.__setattr__(self, "command", command)
        object.__setattr__(self, "evaluator_type", str(self.evaluator_type).strip())
        object.__setattr__(self, "evaluator_version", str(self.evaluator_version).strip())
        object.__setattr__(self, "environment_digest", str(self.environment_digest).strip())

    def evaluate(self, request: EvaluationRequest) -> EvaluationResult:
        completed = subprocess.run(
            list(self.command),
            input=request.model_dump_json(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            shell=False,
            timeout=self.timeout_seconds,
            check=False,
        )
        stdout_bytes = completed.stdout.encode("utf-8")
        stderr_bytes = completed.stderr.encode("utf-8")
        if len(stdout_bytes) > self.max_output_bytes or len(stderr_bytes) > self.max_output_bytes:
            raise CommandEvaluationError("evaluator output exceeded the configured byte budget")
        if completed.returncode != 0:
            stderr_digest = hashlib.sha256(stderr_bytes).hexdigest()
            raise CommandEvaluationError(
                f"evaluator exited with status {completed.returncode}; "
                f"stderr_sha256={stderr_digest}"
            )
        if not completed.stdout.strip():
            raise CommandEvaluationError("evaluator returned empty stdout")
        return EvaluationResult.model_validate_json(completed.stdout)


__all__ = [
    "CheckResult",
    "CommandEvaluationError",
    "CommandEvaluator",
    "ContaminationMetadata",
    "CostMetadata",
    "EvaluationRequest",
    "EvaluationResult",
    "EvaluationVerdict",
    "EvaluatorReceipt",
    "ExecutableEvaluator",
    "NondeterminismMetadata",
    "execute_evaluation",
]
