"""Explicit terminal-durable runner for Eureka's local PROPOSE-only slice.

This adapter is the production seam between the in-memory creative kernel, an
executable evaluator, the pure lifecycle reducer, and the SQLite/CAS archive.  It
returns a proposal only after the evaluator PASS is bound through the lifecycle
and the terminal run is committed and readable from the archive.

It intentionally does *not* claim mid-run checkpoint resume, a transactional
effect outbox, external approval, KG writes, or Hades materialization.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Sequence

from pydantic import BaseModel, ConfigDict, Field, model_validator

from engine.eureka.creative import (
    CreativeLoopConfig,
    CreativeOutcome,
    CreativeProposal,
    CreativeProposer,
    CreativeRunResult,
    CreativeState,
    CreativeTransition,
    ProposalContext,
    ProposalCritic,
    ValidationReceipt,
    contrastive_associations,
    run_creative_loop,
)
from engine.eureka.durable import SqliteEurekaStore
from engine.eureka.evaluation import (
    EvaluationRequest,
    EvaluationVerdict,
    EvaluatorReceipt,
    ExecutableEvaluator,
    execute_evaluation,
)
from engine.eureka.lifecycle import (
    EffectType,
    EvaluationVerdict as LifecycleEvaluationVerdict,
    LifecycleConfiguration,
    LifecycleContext,
    LifecycleEvent,
    LifecycleEventType,
    LifecycleState,
    step,
)


RUNTIME_SCHEMA_VERSION = "bhgman.eureka.terminal-runtime.v1"
LIFECYCLE_RECEIPT_SCHEMA_VERSION = "bhgman.eureka.lifecycle-receipt.v1"
COMMAND_ID = "complete-terminal-run.v1"


def _canonical_json(value: Any) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


class RuntimeIntegrationError(RuntimeError):
    """A supposedly bound evaluator/lifecycle path violated its local contract."""


class LifecycleReceipt(BaseModel):
    """Immutable evidence that one candidate traversed the local lifecycle reducer."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = LIFECYCLE_RECEIPT_SCHEMA_VERSION
    run_id: str = Field(..., min_length=1)
    candidate_digest: str = Field(..., pattern=r"^[0-9a-f]{64}$")
    input_snapshot_hash: str = Field(..., pattern=r"^[0-9a-f]{64}$")
    baseline_snapshot_hash: str = Field(..., pattern=r"^[0-9a-f]{64}$")
    critic_receipt_digest: str = Field(..., pattern=r"^[0-9a-f]{64}$")
    evaluator_receipt_digest: str = Field(..., pattern=r"^[0-9a-f]{64}$")
    final_state: LifecycleState
    transition_ids: tuple[str, ...] = Field(..., min_length=1)
    states: tuple[LifecycleState, ...] = Field(..., min_length=2)
    effect_types: tuple[EffectType, ...] = ()
    source_layer: str = "SECONDARY_AI"

    @model_validator(mode="after")
    def proposed_has_record_effect(self) -> "LifecycleReceipt":
        if self.states[-1] is not self.final_state:
            raise ValueError("last lifecycle state must equal final_state")
        if len(self.states) != len(self.transition_ids) + 1:
            raise ValueError("lifecycle states must bracket every accepted transition")
        if self.final_state is LifecycleState.PROPOSED:
            if self.transition_ids[-2:] != ("evaluation-pass", "return-local-proposal"):
                raise ValueError("PROPOSED lifecycle receipt lacks the bound terminal transitions")
            if EffectType.RECORD_LOCAL_PROPOSAL not in self.effect_types:
                raise ValueError("PROPOSED lifecycle receipt lacks RecordLocalProposal")
        return self

    @property
    def receipt_digest(self) -> str:
        return _digest(self)


def _run_identity(
    context: ProposalContext,
    config: CreativeLoopConfig,
    evaluator: ExecutableEvaluator,
    requested_checks: Sequence[str],
) -> str:
    digest = _digest(
        {
            "schema_version": RUNTIME_SCHEMA_VERSION,
            "cycle_id": context.cycle_id,
            "seed_id": context.seed_id,
            "input_snapshot_hash": context.input_snapshot_hash,
            "baseline_snapshot_hash": context.baseline_snapshot_hash,
            "structural_intent": sorted(context.structural_intent),
            "loop_config": asdict(config),
            "evaluator": {
                "type": str(getattr(evaluator, "evaluator_type", "")),
                "version": str(getattr(evaluator, "evaluator_version", "")),
                "environment_digest": str(getattr(evaluator, "environment_digest", "")),
            },
            "requested_checks": list(requested_checks),
        }
    )
    return f"eureka-{digest}"


def _receipt_chain_is_bound(
    context: ProposalContext,
    candidate_digest: str,
    critic: ValidationReceipt,
    evaluator: EvaluatorReceipt,
) -> bool:
    return bool(
        critic.candidate_digest == candidate_digest
        and critic.cycle_id == context.cycle_id
        and critic.seed_id == context.seed_id
        and critic.input_snapshot_hash == context.input_snapshot_hash
        and critic.baseline_snapshot_hash == context.baseline_snapshot_hash
        and evaluator.candidate_digest == candidate_digest
        and evaluator.input_snapshot_hash == context.input_snapshot_hash
        and evaluator.baseline_snapshot_hash == context.baseline_snapshot_hash
        and evaluator.critic_receipt_digest == critic.receipt_digest
    )


def _event_id(run_id: str, candidate_digest: str, index: int, event: str) -> str:
    return "evt-" + _digest(
        {
            "run_id": run_id,
            "candidate_digest": candidate_digest,
            "index": index,
            "event": event,
        }
    )


def _drive_lifecycle(
    *,
    run_id: str,
    context: ProposalContext,
    proposal: CreativeProposal,
    proposals: Sequence[CreativeProposal],
    critic_receipt: ValidationReceipt,
    evaluator_receipt: EvaluatorReceipt,
    deadline: datetime,
) -> LifecycleReceipt:
    candidate_digest = proposal.candidate_digest(context)
    producer_id = proposal.producer.independence_key
    producer_family = proposal.producer.provider.strip()
    evaluator_id = (
        f"{evaluator_receipt.evaluator_type}:{evaluator_receipt.evaluator_version}:"
        f"{evaluator_receipt.environment_digest[:16]}"
    )
    evaluator_family = evaluator_receipt.evaluator_type
    configuration = LifecycleConfiguration(
        LifecycleState.INIT,
        LifecycleContext(
            run_id=run_id,
            steps_remaining=8,
            run_deadline=deadline,
            max_correction_rounds=1,
        ),
    )
    states = [configuration.state]
    transitions: list[str] = []
    effects: list[EffectType] = []

    def advance(event_type: LifecycleEventType, payload: dict[str, Any]) -> None:
        nonlocal configuration
        index = len(transitions) + 1
        event = LifecycleEvent(
            type=event_type,
            run_id=run_id,
            actor="eureka-terminal-runtime",
            event_id=_event_id(run_id, candidate_digest, index, event_type.value),
            payload=payload,
        )
        selected = step(configuration, event)
        if not selected.accepted or selected.transition_id is None:
            reason = selected.rejection.reason if selected.rejection is not None else "no transition"
            raise RuntimeIntegrationError(
                f"lifecycle rejected {event_type.value} for {candidate_digest}: {reason}"
            )
        configuration = selected.configuration
        transitions.append(selected.transition_id)
        states.append(configuration.state)
        effects.extend(command.type for command in selected.commands)

    association_hash = _digest(contrastive_associations(context))
    candidate_batch_hash = _digest(
        sorted(item.candidate_digest(context) for item in proposals)
    )
    advance(LifecycleEventType.START, {})
    advance(
        LifecycleEventType.PATTERNS_READY,
        {"evidence_hash": context.input_snapshot_hash},
    )
    advance(
        LifecycleEventType.ASSOCIATIONS_READY,
        {
            "evidence_hash": context.input_snapshot_hash,
            "association_hash": association_hash,
        },
    )
    advance(
        LifecycleEventType.CANDIDATES_READY,
        {
            "candidate_batch_hash": candidate_batch_hash,
            "producer_id": producer_id,
            "producer_family": producer_family,
        },
    )
    advance(
        LifecycleEventType.COMPRESSION_COMPLETED,
        {
            "candidate_hash": candidate_digest,
            "evidence_hash": context.input_snapshot_hash,
            "producer_id": producer_id,
        },
    )
    lifecycle_verdict = (
        LifecycleEvaluationVerdict.PASS.value
        if evaluator_receipt.verdict is EvaluationVerdict.PASS
        else LifecycleEvaluationVerdict.REJECT.value
    )
    advance(
        LifecycleEventType.EVALUATION_RECORDED,
        {
            "candidate_hash": candidate_digest,
            "evidence_hash": context.input_snapshot_hash,
            "producer_id": producer_id,
            "evaluator_id": evaluator_id,
            "evaluator_family": evaluator_family,
            "receipt_hash": evaluator_receipt.receipt_digest,
            "verdict": lifecycle_verdict,
            "receipt_verified": _receipt_chain_is_bound(
                context,
                candidate_digest,
                critic_receipt,
                evaluator_receipt,
            ),
            "deterministic_gates_passed": critic_receipt.accepted,
        },
    )
    if configuration.state is LifecycleState.READY_TO_PROPOSE:
        advance(
            LifecycleEventType.RETURN_LOCAL_PROPOSAL,
            {
                "candidate_hash": candidate_digest,
                "proposal_hash": critic_receipt.receipt_digest,
            },
        )
    return LifecycleReceipt(
        run_id=run_id,
        candidate_digest=candidate_digest,
        input_snapshot_hash=context.input_snapshot_hash,
        baseline_snapshot_hash=context.baseline_snapshot_hash,
        critic_receipt_digest=critic_receipt.receipt_digest,
        evaluator_receipt_digest=evaluator_receipt.receipt_digest,
        final_state=configuration.state,
        transition_ids=tuple(transitions),
        states=tuple(states),
        effect_types=tuple(effects),
    )


@dataclass(frozen=True)
class DurableCreativeRunner:
    """Run, executable-evaluate, lifecycle-bind, and terminally archive one context."""

    store: SqliteEurekaStore
    evaluator: ExecutableEvaluator
    requested_checks: tuple[str, ...]
    clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc)
    lifecycle_deadline_seconds: float = 300.0

    def __post_init__(self) -> None:
        checks = tuple(str(item).strip() for item in self.requested_checks)
        if not checks or any(not item for item in checks) or len(set(checks)) != len(checks):
            raise ValueError("requested_checks must be non-empty, unique, and non-blank")
        if self.lifecycle_deadline_seconds <= 0:
            raise ValueError("lifecycle_deadline_seconds must be positive")
        object.__setattr__(self, "requested_checks", checks)

    def run(
        self,
        context: ProposalContext,
        proposer: CreativeProposer,
        critic: ProposalCritic,
        config: CreativeLoopConfig,
    ) -> CreativeRunResult:
        run_id = _run_identity(context, config, self.evaluator, self.requested_checks)
        # On an exact retry, reproduce the original intent and let command dedup decide.
        # On a new run, archive fingerprints prevent cross-cycle semantic duplicates.
        seen = () if self.store.current_version(run_id) else self.store.semantic_fingerprints()
        result = run_creative_loop(
            context,
            proposer,
            critic,
            config,
            seen_fingerprints=seen,
        )
        critic_by_candidate = {item.candidate_digest: item for item in result.receipts}
        kernel_accepted = list(result.accepted)
        retained: list[CreativeProposal] = []
        now = self.clock()
        if now.tzinfo is None:
            raise ValueError("runtime clock must return a timezone-aware datetime")
        deadline = now + timedelta(seconds=self.lifecycle_deadline_seconds)

        for proposal in kernel_accepted:
            candidate_digest = proposal.candidate_digest(context)
            critic_receipt = critic_by_candidate[candidate_digest]
            request = EvaluationRequest(
                candidate_digest=candidate_digest,
                input_snapshot_hash=context.input_snapshot_hash,
                baseline_snapshot_hash=context.baseline_snapshot_hash,
                critic_receipt_digest=critic_receipt.receipt_digest,
                requested_checks=self.requested_checks,
            )
            evaluator_receipt = execute_evaluation(request, self.evaluator)
            result.evaluator_receipts.append(evaluator_receipt)
            lifecycle_receipt = _drive_lifecycle(
                run_id=run_id,
                context=context,
                proposal=proposal,
                proposals=result.proposals,
                critic_receipt=critic_receipt,
                evaluator_receipt=evaluator_receipt,
                deadline=deadline,
            )
            result.lifecycle_receipts.append(lifecycle_receipt)
            if (
                evaluator_receipt.passed
                and lifecycle_receipt.final_state is LifecycleState.PROPOSED
            ):
                retained.append(proposal)
            else:
                reasons = list(result.rejections.get(candidate_digest, ()))
                reasons.append(f"evaluator_{evaluator_receipt.verdict.value.casefold()}")
                if evaluator_receipt.missing_checks:
                    reasons.extend(
                        f"missing_check:{check}" for check in evaluator_receipt.missing_checks
                    )
                if lifecycle_receipt.final_state is not LifecycleState.PROPOSED:
                    reasons.append(
                        f"lifecycle_{lifecycle_receipt.final_state.value.casefold()}"
                    )
                result.rejections[candidate_digest] = tuple(dict.fromkeys(reasons))

        result.accepted = retained
        if kernel_accepted and not retained:
            previous = result.state
            result.outcome = CreativeOutcome.EXHAUSTED
            result.state = CreativeState.EXHAUSTED
            result.stop_reason = "executable_evaluation_rejected"
            result.transitions.append(
                CreativeTransition(
                    previous,
                    CreativeState.EXHAUSTED,
                    "no critic-approved candidate passed executable lifecycle binding",
                )
            )
        elif retained:
            result.stop_reason = "executable_evaluation_and_lifecycle_passed"

        result.durable_receipt = self.store.record_creative_run(
            result,
            run_id=run_id,
            command_id=COMMAND_ID,
            expected_version=0,
        )
        return result


__all__ = [
    "COMMAND_ID",
    "LIFECYCLE_RECEIPT_SCHEMA_VERSION",
    "RUNTIME_SCHEMA_VERSION",
    "DurableCreativeRunner",
    "LifecycleReceipt",
    "RuntimeIntegrationError",
]
