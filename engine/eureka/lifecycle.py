"""Pure local lifecycle reducer for Eureka's semantic proposal loop.

This module is the executable subset of ``semantic-creative-fsm.v1.json``.
It owns no I/O: model calls, evaluator execution, persistence, clocks, and IDs
remain outside the reducer and return as typed observations.  The supported
slice ends at a local ``PROPOSED`` artifact.  It cannot emit ``ACCEPTED`` or
materialize KG/source changes; those authorities remain outside Eureka.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping


class LifecycleState(str, Enum):
    """States implemented by the local-only FSM profile."""

    INIT = "INIT"
    DETECT = "DETECT"
    ASSOCIATE = "ASSOCIATE"
    DIVERGE = "DIVERGE"
    COMPRESS = "COMPRESS"
    FALSIFY = "FALSIFY"
    REVISE = "REVISE"
    READY_TO_PROPOSE = "READY_TO_PROPOSE"
    PROPOSED = "PROPOSED"
    REJECTED = "REJECTED"
    PLATEAU = "PLATEAU"
    RETRY_EXHAUSTED = "RETRY_EXHAUSTED"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"
    TIMED_OUT = "TIMED_OUT"
    CANCELED = "CANCELED"


class LifecycleEventType(str, Enum):
    """Input events from the semantic creative FSM contract's local path."""

    START = "START"
    PATTERNS_READY = "PATTERNS_READY"
    ASSOCIATIONS_READY = "ASSOCIATIONS_READY"
    CANDIDATES_READY = "CANDIDATES_READY"
    COMPRESSION_COMPLETED = "COMPRESSION_COMPLETED"
    EVALUATION_RECORDED = "EVALUATION_RECORDED"
    REVISION_READY = "REVISION_READY"
    PLATEAU = "PLATEAU"
    RETRIES_EXHAUSTED = "RETRIES_EXHAUSTED"
    RETURN_LOCAL_PROPOSAL = "RETURN_LOCAL_PROPOSAL"
    CANCEL = "CANCEL"
    TIMEOUT = "TIMEOUT"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"


class EffectType(str, Enum):
    """Effect intents; adapters execute them only after the transition is accepted."""

    REQUEST_PATTERN_DETECTION = "RequestPatternDetection"
    REQUEST_ASSOCIATIONS = "RequestAssociations"
    REQUEST_CANDIDATE_GENERATION = "RequestCandidateGeneration"
    REQUEST_INDEPENDENT_EVALUATION = "RequestIndependentEvaluation"
    REQUEST_REVISION = "RequestRevision"
    RECORD_LOCAL_PROPOSAL = "RecordLocalProposal"
    AUDIT_INVALID_TRANSITION = "AuditInvalidTransition"


class RejectionCode(str, Enum):
    TERMINAL_STATE = "TERMINAL_STATE"
    INVALID_EVENT = "INVALID_EVENT"
    INVALID_PAYLOAD = "INVALID_PAYLOAD"
    RUN_ID_MISMATCH = "RUN_ID_MISMATCH"
    GUARD_FALSE = "GUARD_FALSE"
    STEP_BUDGET_EXHAUSTED = "STEP_BUDGET_EXHAUSTED"


class EvaluationVerdict(str, Enum):
    PASS = "PASS"
    REVISE = "REVISE"
    REJECT = "REJECT"


TERMINAL_STATES = frozenset(
    {
        LifecycleState.PROPOSED,
        LifecycleState.REJECTED,
        LifecycleState.PLATEAU,
        LifecycleState.RETRY_EXHAUSTED,
        LifecycleState.BUDGET_EXHAUSTED,
        LifecycleState.TIMED_OUT,
        LifecycleState.CANCELED,
    }
)


def _freeze_payload(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return MappingProxyType(dict(payload))


@dataclass(frozen=True)
class LifecycleEvent:
    type: LifecycleEventType | str
    run_id: str
    actor: str
    event_id: str
    payload: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "payload", _freeze_payload(self.payload))


@dataclass(frozen=True)
class EffectCommand:
    type: EffectType
    payload: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "payload", _freeze_payload(self.payload))


@dataclass(frozen=True)
class LifecycleContext:
    run_id: str
    steps_remaining: int
    run_deadline: datetime
    max_correction_rounds: int = 1
    producer_id: str = ""
    producer_family: str = ""
    current_candidate_hash: str = ""
    current_evidence_hash: str = ""
    correction_round: int = 0

    def __post_init__(self) -> None:
        if not self.run_id.strip():
            raise ValueError("run_id must not be blank")
        if self.steps_remaining < 0:
            raise ValueError("steps_remaining must be non-negative")
        if self.max_correction_rounds < 1:
            raise ValueError("max_correction_rounds must be positive")
        if self.correction_round < 0:
            raise ValueError("correction_round must be non-negative")
        if self.correction_round > self.max_correction_rounds:
            raise ValueError("correction_round cannot exceed max_correction_rounds")
        if self.run_deadline.tzinfo is None:
            raise ValueError("run_deadline must be timezone-aware")


@dataclass(frozen=True)
class LifecycleConfiguration:
    state: LifecycleState
    context: LifecycleContext


@dataclass(frozen=True)
class TransitionRejection:
    code: RejectionCode
    reason: str


@dataclass(frozen=True)
class StepResult:
    configuration: LifecycleConfiguration
    commands: tuple[EffectCommand, ...] = ()
    transition_id: str | None = None
    rejection: TransitionRejection | None = None

    @property
    def accepted(self) -> bool:
        return self.rejection is None


_REQUIRED_PAYLOAD: dict[LifecycleEventType, frozenset[str]] = {
    LifecycleEventType.PATTERNS_READY: frozenset({"evidence_hash"}),
    LifecycleEventType.ASSOCIATIONS_READY: frozenset(
        {"evidence_hash", "association_hash"}
    ),
    LifecycleEventType.CANDIDATES_READY: frozenset(
        {"candidate_batch_hash", "producer_id"}
    ),
    LifecycleEventType.COMPRESSION_COMPLETED: frozenset(
        {"candidate_hash", "evidence_hash", "producer_id"}
    ),
    LifecycleEventType.EVALUATION_RECORDED: frozenset(
        {
            "candidate_hash",
            "evidence_hash",
            "producer_id",
            "evaluator_id",
            "evaluator_family",
            "receipt_hash",
            "verdict",
            "receipt_verified",
            "deterministic_gates_passed",
        }
    ),
    LifecycleEventType.REVISION_READY: frozenset(
        {"candidate_hash", "evidence_hash", "producer_id"}
    ),
    LifecycleEventType.PLATEAU: frozenset({"fingerprint", "gain"}),
    LifecycleEventType.RETRIES_EXHAUSTED: frozenset({"failure_class"}),
    LifecycleEventType.RETURN_LOCAL_PROPOSAL: frozenset(
        {"candidate_hash", "proposal_hash"}
    ),
    LifecycleEventType.CANCEL: frozenset({"reason"}),
    LifecycleEventType.TIMEOUT: frozenset({"deadline", "observed_at"}),
    LifecycleEventType.BUDGET_EXHAUSTED: frozenset({"budget_kind"}),
}


_SAFE_INTERRUPT_STATES = frozenset(
    {
        LifecycleState.INIT,
        LifecycleState.DETECT,
        LifecycleState.ASSOCIATE,
        LifecycleState.DIVERGE,
        LifecycleState.COMPRESS,
        LifecycleState.FALSIFY,
        LifecycleState.REVISE,
        LifecycleState.READY_TO_PROPOSE,
    }
)


def _is_sha256(value: Any) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else None
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _effect(effect_type: EffectType, **payload: Any) -> EffectCommand:
    return EffectCommand(effect_type, payload)


def _audit_rejection(
    configuration: LifecycleConfiguration,
    event: LifecycleEvent,
    code: RejectionCode,
    reason: str,
) -> StepResult:
    return StepResult(
        configuration=configuration,
        commands=(
            _effect(
                EffectType.AUDIT_INVALID_TRANSITION,
                state=configuration.state.value,
                event=(
                    event.type.value
                    if isinstance(event.type, LifecycleEventType)
                    else str(event.type)
                ),
                actor=event.actor,
                reason=reason,
                event_id=event.event_id,
            ),
        ),
        rejection=TransitionRejection(code, reason),
    )


def _accepted(
    configuration: LifecycleConfiguration,
    target: LifecycleState,
    transition_id: str,
    *,
    commands: tuple[EffectCommand, ...] = (),
    context: LifecycleContext | None = None,
) -> StepResult:
    current = context or configuration.context
    consumed = replace(current, steps_remaining=max(0, current.steps_remaining - 1))
    return StepResult(
        configuration=LifecycleConfiguration(target, consumed),
        commands=commands,
        transition_id=transition_id,
    )


def _bindings_match(context: LifecycleContext, event: LifecycleEvent) -> bool:
    payload = event.payload
    return bool(
        payload.get("candidate_hash") == context.current_candidate_hash
        and payload.get("evidence_hash") == context.current_evidence_hash
        and payload.get("producer_id") == context.producer_id
        and _is_sha256(payload.get("receipt_hash"))
        and payload.get("receipt_verified") is True
    )


def evaluation_passes(context: LifecycleContext, event: LifecycleEvent) -> bool:
    """Pure PASS guard; prose or an unbound evaluator receipt cannot satisfy it."""

    payload = event.payload
    producer_family = context.producer_family or context.producer_id
    evaluator_family = str(payload.get("evaluator_family", ""))
    evaluator_id = str(payload.get("evaluator_id", ""))
    return bool(
        context.producer_id.strip()
        and producer_family.strip()
        and _bindings_match(context, event)
        and payload.get("verdict") == EvaluationVerdict.PASS.value
        and payload.get("deterministic_gates_passed") is True
        and evaluator_id
        and evaluator_id.casefold() != context.producer_id.casefold()
        and evaluator_family
        and evaluator_family.casefold() != producer_family.casefold()
        and context.steps_remaining > 0
    )


def evaluation_correctable(context: LifecycleContext, event: LifecycleEvent) -> bool:
    """Pure REVISE guard with bounded correction and fail-closed receipt binding."""

    payload = event.payload
    producer_family = context.producer_family or context.producer_id
    evaluator_family = str(payload.get("evaluator_family", ""))
    evaluator_id = str(payload.get("evaluator_id", ""))
    return bool(
        context.producer_id.strip()
        and producer_family.strip()
        and _bindings_match(context, event)
        and payload.get("verdict") == EvaluationVerdict.REVISE.value
        and payload.get("terminal_falsifier", False) is False
        and payload.get("plateaued", False) is False
        and evaluator_id
        and evaluator_id.casefold() != context.producer_id.casefold()
        and evaluator_family
        and evaluator_family.casefold() != producer_family.casefold()
        and context.correction_round < context.max_correction_rounds
        and context.steps_remaining > 0
    )


def _validate_event(
    configuration: LifecycleConfiguration, event: LifecycleEvent
) -> StepResult | None:
    if configuration.state in TERMINAL_STATES:
        return _audit_rejection(
            configuration,
            event,
            RejectionCode.TERMINAL_STATE,
            f"terminal state {configuration.state.value} accepts no events",
        )
    if not isinstance(event.type, LifecycleEventType):
        return _audit_rejection(
            configuration,
            event,
            RejectionCode.INVALID_EVENT,
            f"unknown event {event.type!r}",
        )
    if event.run_id != configuration.context.run_id:
        return _audit_rejection(
            configuration,
            event,
            RejectionCode.RUN_ID_MISMATCH,
            "event run_id does not match lifecycle aggregate",
        )
    if not event.actor.strip() or not event.event_id.strip():
        return _audit_rejection(
            configuration,
            event,
            RejectionCode.INVALID_PAYLOAD,
            "actor and event_id must not be blank",
        )
    missing = _REQUIRED_PAYLOAD.get(event.type, frozenset()) - event.payload.keys()
    if missing:
        return _audit_rejection(
            configuration,
            event,
            RejectionCode.INVALID_PAYLOAD,
            f"missing payload fields: {', '.join(sorted(missing))}",
        )
    if (
        configuration.context.steps_remaining == 0
        and event.type
        not in {
            LifecycleEventType.CANCEL,
            LifecycleEventType.TIMEOUT,
            LifecycleEventType.BUDGET_EXHAUSTED,
        }
    ):
        return _audit_rejection(
            configuration,
            event,
            RejectionCode.STEP_BUDGET_EXHAUSTED,
            "step budget is exhausted; governor must emit BUDGET_EXHAUSTED",
        )
    return None


def _interrupt_transition(
    configuration: LifecycleConfiguration, event: LifecycleEvent
) -> StepResult | None:
    if configuration.state not in _SAFE_INTERRUPT_STATES:
        return None
    state_suffix = (
        "ready"
        if configuration.state is LifecycleState.READY_TO_PROPOSE
        else configuration.state.value.casefold()
    )
    if event.type is LifecycleEventType.CANCEL:
        return _accepted(
            configuration,
            LifecycleState.CANCELED,
            f"cancel-{state_suffix}",
        )
    if event.type is LifecycleEventType.BUDGET_EXHAUSTED:
        return _accepted(
            configuration,
            LifecycleState.BUDGET_EXHAUSTED,
            f"budget-{state_suffix}",
        )
    if event.type is LifecycleEventType.TIMEOUT:
        deadline = _parse_datetime(event.payload.get("deadline"))
        observed_at = _parse_datetime(event.payload.get("observed_at"))
        due = bool(
            deadline == configuration.context.run_deadline
            and observed_at is not None
            and observed_at >= configuration.context.run_deadline
        )
        if due:
            return _accepted(
                configuration,
                LifecycleState.TIMED_OUT,
                f"timeout-{state_suffix}",
            )
        return _audit_rejection(
            configuration,
            event,
            RejectionCode.GUARD_FALSE,
            "TIMEOUT observed before or against a different run deadline",
        )
    return None


def step(configuration: LifecycleConfiguration, event: LifecycleEvent) -> StepResult:
    """Select one deterministic transition and emit effect intents without I/O."""

    invalid = _validate_event(configuration, event)
    if invalid is not None:
        return invalid
    interrupt = _interrupt_transition(configuration, event)
    if interrupt is not None:
        return interrupt

    state = configuration.state
    payload = event.payload
    if state is LifecycleState.INIT and event.type is LifecycleEventType.START:
        return _accepted(
            configuration,
            LifecycleState.DETECT,
            "start-detection",
            commands=(
                _effect(
                    EffectType.REQUEST_PATTERN_DETECTION,
                    run_id=event.run_id,
                    event_id=event.event_id,
                ),
            ),
        )
    if state is LifecycleState.DETECT and event.type is LifecycleEventType.PATTERNS_READY:
        if not _is_sha256(payload["evidence_hash"]):
            return _audit_rejection(
                configuration,
                event,
                RejectionCode.INVALID_PAYLOAD,
                "evidence_hash must be a SHA-256 digest",
            )
        context = replace(
            configuration.context,
            current_evidence_hash=str(payload["evidence_hash"]),
        )
        return _accepted(
            configuration,
            LifecycleState.ASSOCIATE,
            "patterns-to-association",
            context=context,
            commands=(
                _effect(
                    EffectType.REQUEST_ASSOCIATIONS,
                    run_id=event.run_id,
                    evidence_hash=payload["evidence_hash"],
                ),
            ),
        )
    if (
        state is LifecycleState.ASSOCIATE
        and event.type is LifecycleEventType.ASSOCIATIONS_READY
    ):
        if (
            payload["evidence_hash"] != configuration.context.current_evidence_hash
            or not _is_sha256(payload["association_hash"])
        ):
            return _audit_rejection(
                configuration,
                event,
                RejectionCode.GUARD_FALSE,
                "association receipt is not bound to current evidence",
            )
        return _accepted(
            configuration,
            LifecycleState.DIVERGE,
            "associations-to-divergence",
            commands=(
                _effect(
                    EffectType.REQUEST_CANDIDATE_GENERATION,
                    run_id=event.run_id,
                    association_hash=payload["association_hash"],
                ),
            ),
        )
    if state is LifecycleState.DIVERGE and event.type is LifecycleEventType.CANDIDATES_READY:
        producer_id = str(payload["producer_id"]).strip()
        producer_family = str(payload.get("producer_family") or producer_id).strip()
        if (
            not _is_sha256(payload["candidate_batch_hash"])
            or not producer_id
            or not producer_family
        ):
            return _audit_rejection(
                configuration,
                event,
                RejectionCode.INVALID_PAYLOAD,
                "candidate batch hash and producer identity must be valid",
            )
        context = replace(
            configuration.context,
            producer_id=producer_id,
            producer_family=producer_family,
        )
        return _accepted(
            configuration,
            LifecycleState.COMPRESS,
            "divergence-to-compression",
            context=context,
        )
    if (
        state is LifecycleState.COMPRESS
        and event.type is LifecycleEventType.COMPRESSION_COMPLETED
    ):
        candidate_hash = payload["candidate_hash"]
        evidence_hash = payload["evidence_hash"]
        if (
            not _is_sha256(candidate_hash)
            or evidence_hash != configuration.context.current_evidence_hash
            or payload["producer_id"] != configuration.context.producer_id
        ):
            return _audit_rejection(
                configuration,
                event,
                RejectionCode.GUARD_FALSE,
                "compressed candidate is not bound to producer and evidence",
            )
        context = replace(
            configuration.context,
            current_candidate_hash=str(candidate_hash),
        )
        return _accepted(
            configuration,
            LifecycleState.FALSIFY,
            "compression-to-falsification",
            context=context,
            commands=(
                _effect(
                    EffectType.REQUEST_INDEPENDENT_EVALUATION,
                    run_id=event.run_id,
                    candidate_hash=candidate_hash,
                    evidence_hash=evidence_hash,
                ),
            ),
        )
    if (
        state is LifecycleState.FALSIFY
        and event.type is LifecycleEventType.EVALUATION_RECORDED
    ):
        if evaluation_passes(configuration.context, event):
            return _accepted(
                configuration,
                LifecycleState.READY_TO_PROPOSE,
                "evaluation-pass",
            )
        if evaluation_correctable(configuration.context, event):
            return _accepted(
                configuration,
                LifecycleState.REVISE,
                "evaluation-revise",
                commands=(
                    _effect(
                        EffectType.REQUEST_REVISION,
                        run_id=event.run_id,
                        candidate_hash=payload["candidate_hash"],
                        receipt_hash=payload["receipt_hash"],
                    ),
                ),
            )
        return _accepted(
            configuration,
            LifecycleState.REJECTED,
            "evaluation-reject-default",
        )
    if state is LifecycleState.REVISE and event.type is LifecycleEventType.REVISION_READY:
        if (
            not _is_sha256(payload["candidate_hash"])
            or payload["evidence_hash"] != configuration.context.current_evidence_hash
            or payload["producer_id"] != configuration.context.producer_id
        ):
            return _audit_rejection(
                configuration,
                event,
                RejectionCode.GUARD_FALSE,
                "revision is not bound to producer and evidence",
            )
        context = replace(
            configuration.context,
            current_candidate_hash=str(payload["candidate_hash"]),
            correction_round=configuration.context.correction_round + 1,
        )
        return _accepted(
            configuration,
            LifecycleState.FALSIFY,
            "revision-to-falsification",
            context=context,
            commands=(
                _effect(
                    EffectType.REQUEST_INDEPENDENT_EVALUATION,
                    run_id=event.run_id,
                    candidate_hash=payload["candidate_hash"],
                    evidence_hash=payload["evidence_hash"],
                ),
            ),
        )
    if state is LifecycleState.REVISE and event.type is LifecycleEventType.PLATEAU:
        return _accepted(
            configuration,
            LifecycleState.PLATEAU,
            "revision-plateau",
        )
    if (
        state is LifecycleState.REVISE
        and event.type is LifecycleEventType.RETRIES_EXHAUSTED
    ):
        return _accepted(
            configuration,
            LifecycleState.RETRY_EXHAUSTED,
            "revision-retries-exhausted",
        )
    if (
        state is LifecycleState.READY_TO_PROPOSE
        and event.type is LifecycleEventType.RETURN_LOCAL_PROPOSAL
    ):
        if (
            payload["candidate_hash"] != configuration.context.current_candidate_hash
            or not _is_sha256(payload["proposal_hash"])
        ):
            return _audit_rejection(
                configuration,
                event,
                RejectionCode.GUARD_FALSE,
                "local proposal is not bound to the validated candidate",
            )
        return _accepted(
            configuration,
            LifecycleState.PROPOSED,
            "return-local-proposal",
            commands=(
                _effect(
                    EffectType.RECORD_LOCAL_PROPOSAL,
                    run_id=event.run_id,
                    candidate_hash=payload["candidate_hash"],
                    proposal_hash=payload["proposal_hash"],
                ),
            ),
        )
    event_name = (
        event.type.value if isinstance(event.type, LifecycleEventType) else str(event.type)
    )
    return _audit_rejection(
        configuration,
        event,
        RejectionCode.INVALID_EVENT,
        f"event {event_name} is not enabled in state {state.value}",
    )


__all__ = [
    "EffectCommand",
    "EffectType",
    "EvaluationVerdict",
    "LifecycleConfiguration",
    "LifecycleContext",
    "LifecycleEvent",
    "LifecycleEventType",
    "LifecycleState",
    "RejectionCode",
    "StepResult",
    "TERMINAL_STATES",
    "TransitionRejection",
    "evaluation_correctable",
    "evaluation_passes",
    "step",
]
