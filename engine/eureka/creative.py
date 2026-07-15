"""Bounded abductive insight loop for Eureka.

The model is deliberately an untrusted source of divergent proposals.  A pure
kernel binds every proposal to its evidence snapshots, rejects prompt/paraphrase
echoes, and accepts a *proposal* only when a separately identified critic returns
an evidence-backed, content-addressed receipt.  Eureka still stops at PROPOSE;
materialization remains Hades' authority.

This module does not claim to manufacture creativity.  It supplies conditions in
which useful novelty can emerge and makes false "Eureka!" outputs cheap to reject.

# KG: eureka-canonical-2026-05-26
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol

from pydantic import BaseModel, Field, field_validator, model_validator

from engine.eureka.induction_models import AbstractClass


SCHEMA_VERSION = "bhgman.eureka.creative.v1"
GATE_VERSION = "bhgman.eureka.gates.v1"
GENERIC_NAMES = frozenset(
    {
        "abstraction",
        "category",
        "concept",
        "framework",
        "good",
        "idea",
        "insight",
        "mechanism",
        "pattern",
        "system",
        "thing",
    }
)
_TOKEN_RE = re.compile(r"[\w가-힣]+", re.UNICODE)
_JSON_ARRAY = re.compile(r"\[.*\]", re.DOTALL)


def _canonical_json(value: Any) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _tokens(text: str) -> set[str]:
    return {token.casefold() for token in _TOKEN_RE.findall(text or "")}


def _jaccard(left: str, right: str) -> float:
    a, b = _tokens(left), _tokens(right)
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


class CreativeOutcome(str, Enum):
    PROPOSED = "PROPOSED"
    NO_DISCOVERY = "NO_DISCOVERY"
    EXHAUSTED = "EXHAUSTED"
    FAILED = "FAILED"


class CreativeState(str, Enum):
    DETECT = "DETECT"
    ASSOCIATE = "ASSOCIATE"
    DIVERGE = "DIVERGE"
    FALSIFY = "FALSIFY"
    REVISE = "REVISE"
    PROPOSED = "PROPOSED"
    NO_DISCOVERY = "NO_DISCOVERY"
    EXHAUSTED = "EXHAUSTED"
    FAILED = "FAILED"


class ReviewVerdict(str, Enum):
    PASS = "PASS"
    REVISE = "REVISE"
    REJECT = "REJECT"


class IndependenceClass(str, Enum):
    PROVIDER_DIVERSE = "PROVIDER_DIVERSE"
    MODEL_DIVERSE_SAME_PROVIDER = "MODEL_DIVERSE_SAME_PROVIDER"
    CORRELATED_SAME_MODEL = "CORRELATED_SAME_MODEL"


class Observation(BaseModel):
    source_id: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)
    content_hash: str = Field(..., pattern=r"^[0-9a-f]{64}$")
    attributes: tuple[str, ...] = ()

    @model_validator(mode="after")
    def content_hash_matches(self) -> "Observation":
        expected = hashlib.sha256(self.content.encode("utf-8")).hexdigest()
        if self.content_hash != expected:
            raise ValueError("content_hash does not match observation content")
        return self

    @classmethod
    def from_text(
        cls, source_id: str, content: str, attributes: Sequence[str] = ()
    ) -> "Observation":
        return cls(
            source_id=source_id,
            content=content,
            content_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
            attributes=tuple(sorted(str(item) for item in attributes)),
        )


class ActorFingerprint(BaseModel):
    provider: str = Field(..., min_length=1)
    model: str = Field(..., min_length=1)
    role: str = Field(..., min_length=1)
    session: str = Field(..., min_length=1)
    prompt_hash: str = Field(..., pattern=r"^[0-9a-f]{64}$")
    seed: int | None = None

    @field_validator("provider", "model", "role", "session")
    @classmethod
    def normalize_identity_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("actor identity fields must not be blank")
        return normalized

    @property
    def independence_key(self) -> str:
        # Role/session separation alone is not independence.  Same provider+model
        # remains correlated and cannot issue an acceptance receipt.
        return f"{self.provider.casefold()}::{self.model.casefold()}"


class ProposalContext(BaseModel):
    schema_version: str = SCHEMA_VERSION
    cycle_id: str = Field(..., min_length=1)
    seed_id: str = Field(..., min_length=1)
    observations: tuple[Observation, ...] = Field(..., min_length=3)
    structural_intent: tuple[str, ...] = Field(..., min_length=1)
    existing_concepts: tuple[str, ...] = ()
    prompt_canary: str = "ZXQ_EUREKA_DO_NOT_COPY_91"

    @model_validator(mode="after")
    def observation_sources_are_unique(self) -> "ProposalContext":
        source_ids = [item.source_id.strip().casefold() for item in self.observations]
        if len(set(source_ids)) != len(source_ids):
            raise ValueError("observation source_ids must be unique")
        return self

    @property
    def input_snapshot_hash(self) -> str:
        rows = sorted(
            (
                {
                    "source_id": item.source_id,
                    "content_hash": item.content_hash,
                    "attributes": sorted(item.attributes),
                }
                for item in self.observations
            ),
            key=lambda row: (row["source_id"], row["content_hash"]),
        )
        return _digest(rows)

    @property
    def baseline_snapshot_hash(self) -> str:
        return _digest(sorted(self.existing_concepts, key=str.casefold))


class CreativeProposal(BaseModel):
    name: str = Field(..., min_length=2, max_length=96)
    definition: str = Field(..., min_length=12, max_length=1200)
    mechanism: str = Field(..., min_length=12, max_length=1200)
    scope: str = Field(..., min_length=4, max_length=600)
    support_ids: tuple[str, ...] = Field(..., min_length=3)
    positive_examples: tuple[str, ...] = Field(..., min_length=3)
    adversarial_near_misses: tuple[str, ...] = Field(..., min_length=2)
    known_failure_scope: str = Field(..., min_length=8, max_length=800)
    falsifier_procedure: str = Field(..., min_length=12, max_length=1000)
    rejection_condition: str = Field(..., min_length=6, max_length=600)
    novelty_claim: str = Field(..., min_length=12, max_length=1000)
    nearest_existing: str = Field(..., min_length=1, max_length=300)
    semantic_delta: str = Field(..., min_length=12, max_length=1000)
    held_out_prediction: str = Field(..., min_length=12, max_length=1000)
    producer: ActorFingerprint
    round: int = Field(..., ge=1)
    parent_candidate_digest: str | None = None

    @model_validator(mode="after")
    def evidence_ids_are_unique(self) -> "CreativeProposal":
        if len(set(self.support_ids)) != len(self.support_ids):
            raise ValueError("support_ids must be unique")
        return self

    def core(self) -> dict[str, Any]:
        payload = self.model_dump(
            mode="json",
            exclude={"producer", "round", "parent_candidate_digest"},
        )
        for key in ("support_ids", "positive_examples", "adversarial_near_misses"):
            payload[key] = sorted(payload[key], key=str.casefold)
        return payload

    def semantic_fingerprint(self) -> str:
        """Order/style-resistant no-progress key (token multiset + evidence boundary)."""
        semantic_text = " ".join((self.name, self.definition, self.mechanism, self.scope))
        return _digest(
            {
                "tokens": sorted(_tokens(semantic_text)),
                "support_ids": sorted(self.support_ids, key=str.casefold),
                "near_miss_tokens": sorted(_tokens(" ".join(self.adversarial_near_misses))),
            }
        )

    def candidate_digest(self, context: ProposalContext) -> str:
        return _digest(
            {
                "schema_version": SCHEMA_VERSION,
                "input_snapshot_hash": context.input_snapshot_hash,
                "baseline_snapshot_hash": context.baseline_snapshot_hash,
                "proposal": self.core(),
            }
        )


class ScoreCard(BaseModel):
    novelty: float = Field(..., ge=0.0, le=1.0)
    compression: float = Field(..., ge=0.0, le=1.0)
    discrimination: float = Field(..., ge=0.0, le=1.0)
    falsifiability: float = Field(..., ge=0.0, le=1.0)

    @property
    def minimum(self) -> float:
        return min(self.novelty, self.compression, self.discrimination, self.falsifiability)


class CriticReview(BaseModel):
    candidate_digest: str = Field(..., pattern=r"^[0-9a-f]{64}$")
    verdict: ReviewVerdict
    cited_evidence_ids: tuple[str, ...] = Field(..., min_length=1)
    strongest_counterargument: str = Field(..., min_length=8, max_length=1000)
    cheapest_falsifier: str = Field(..., min_length=8, max_length=1000)
    scores: ScoreCard
    reviewer: ActorFingerprint


class ValidationReceipt(BaseModel):
    schema_version: str = SCHEMA_VERSION
    cycle_id: str
    seed_id: str
    candidate_digest: str = Field(..., pattern=r"^[0-9a-f]{64}$")
    input_snapshot_hash: str = Field(..., pattern=r"^[0-9a-f]{64}$")
    baseline_snapshot_hash: str = Field(..., pattern=r"^[0-9a-f]{64}$")
    gate_config_hash: str = Field(..., pattern=r"^[0-9a-f]{64}$")
    producer: ActorFingerprint
    reviewer: ActorFingerprint
    independence_class: IndependenceClass
    verdict: ReviewVerdict
    cited_evidence_ids: tuple[str, ...]
    gates: dict[str, bool]
    reasons: tuple[str, ...]
    strongest_counterargument: str
    cheapest_falsifier: str
    scores: ScoreCard

    @property
    def receipt_digest(self) -> str:
        return _digest(self)

    @property
    def accepted(self) -> bool:
        return self.verdict is ReviewVerdict.PASS and bool(self.gates) and all(self.gates.values())


class CreativeProposer(Protocol):
    def propose(
        self,
        context: ProposalContext,
        *,
        round_number: int,
        count: int,
        feedback: Sequence[str],
    ) -> Sequence[CreativeProposal]: ...


class ProposalCritic(Protocol):
    def review(
        self, context: ProposalContext, proposals: Sequence[CreativeProposal]
    ) -> Sequence[CriticReview]: ...


@dataclass(frozen=True)
class CreativeLoopConfig:
    max_rounds: int = 2
    candidates_per_round: int = 5
    max_model_calls: int = 4
    no_progress_limit: int = 2
    max_accepts: int = 1
    score_floor: float = 0.55
    novelty_floor: float = 0.25


@dataclass(frozen=True)
class CreativeTransition:
    source: CreativeState
    target: CreativeState
    reason: str


@dataclass
class CreativeRunResult:
    context: ProposalContext
    outcome: CreativeOutcome
    state: CreativeState
    proposals: list[CreativeProposal] = field(default_factory=list)
    accepted: list[CreativeProposal] = field(default_factory=list)
    receipts: list[ValidationReceipt] = field(default_factory=list)
    rejections: dict[str, tuple[str, ...]] = field(default_factory=dict)
    transitions: list[CreativeTransition] = field(default_factory=list)
    rounds: int = 0
    model_calls: int = 0
    stop_reason: str = ""


@dataclass(frozen=True)
class _RoundStepResult:
    """Private control result carried between bounded creative-loop rounds."""

    terminal: bool
    feedback: list[str]
    no_progress: int


@dataclass
class _CreativeLoopRuntime:
    context: ProposalContext
    proposer: CreativeProposer
    critic: ProposalCritic
    config: CreativeLoopConfig
    result: CreativeRunResult
    seen: set[str] = field(default_factory=set)


@dataclass(frozen=True)
class _ProposalCallResult:
    batch: list[CreativeProposal]
    error: Exception | None


@dataclass(frozen=True)
class _ReviewCallResult:
    reviews: list[CriticReview]
    error: Exception | None


def contrastive_associations(context: ProposalContext, limit: int = 4) -> list[dict[str, Any]]:
    """Select least-overlapping evidence pairs as cheap associative provocations."""
    pairs: list[tuple[float, str, str]] = []
    for i, left in enumerate(context.observations):
        for right in context.observations[i + 1 :]:
            pairs.append((_jaccard(left.content, right.content), left.source_id, right.source_id))
    return [
        {"left": left, "right": right, "lexical_overlap": round(score, 4)}
        for score, left, right in sorted(pairs)[:limit]
    ]


def _proposal_text(proposal: CreativeProposal) -> str:
    return " ".join(str(value) for value in proposal.core().values())


def deterministic_gates(
    context: ProposalContext, proposal: CreativeProposal, novelty_floor: float
) -> tuple[dict[str, bool], list[str]]:
    allowed = {item.source_id for item in context.observations}
    support = set(proposal.support_ids)
    name_tokens = _tokens(proposal.name)
    candidate_text = _proposal_text(proposal)
    sources = [item.content for item in context.observations]
    baselines = list(context.existing_concepts)
    semantic_parts = (proposal.name, proposal.definition, proposal.mechanism)
    nearest_source = max(
        (_jaccard(part, item) for part in semantic_parts for item in sources),
        default=0.0,
    )
    nearest_baseline = max(
        (_jaccard(part, item) for part in semantic_parts for item in baselines),
        default=0.0,
    )
    novelty = 1.0 - max(nearest_source, nearest_baseline)
    gates = {
        "rule_of_three": len(support) >= 3 and support <= allowed,
        "not_prompt_echo": context.prompt_canary not in candidate_text,
        "not_generic": bool(name_tokens) and not (name_tokens <= GENERIC_NAMES),
        "not_single_source_paraphrase": nearest_source < 0.85,
        "not_existing_concept_rename": nearest_baseline < 0.80,
        "novelty_floor": novelty >= novelty_floor,
        "discriminative_boundary": len(proposal.adversarial_near_misses) >= 2,
        "falsifier_present": bool(
            proposal.falsifier_procedure.strip() and proposal.rejection_condition.strip()
        ),
        "held_out_prediction": bool(proposal.held_out_prediction.strip()),
    }
    reasons = [name for name, passed in gates.items() if not passed]
    return gates, reasons


def _make_receipt(
    context: ProposalContext,
    proposal: CreativeProposal,
    review: CriticReview,
    config: CreativeLoopConfig,
) -> ValidationReceipt:
    digest = proposal.candidate_digest(context)
    gates, reasons = deterministic_gates(context, proposal, config.novelty_floor)
    cited = set(review.cited_evidence_ids)
    allowed = {item.source_id for item in context.observations}
    gates["receipt_bound"] = review.candidate_digest == digest
    gates["evidence_cited"] = (
        bool(cited) and set(proposal.support_ids) <= cited and cited <= allowed
    )
    producer_provider = proposal.producer.provider.casefold()
    reviewer_provider = review.reviewer.provider.casefold()
    producer_model = proposal.producer.model.casefold()
    reviewer_model = review.reviewer.model.casefold()
    if producer_model == reviewer_model:
        independence_class = IndependenceClass.CORRELATED_SAME_MODEL
    elif producer_provider != reviewer_provider:
        independence_class = IndependenceClass.PROVIDER_DIVERSE
    elif producer_model != reviewer_model:
        independence_class = IndependenceClass.MODEL_DIVERSE_SAME_PROVIDER
    else:
        independence_class = IndependenceClass.CORRELATED_SAME_MODEL
    gates["reviewer_independent"] = (
        independence_class is not IndependenceClass.CORRELATED_SAME_MODEL
    )
    gates["score_floor"] = review.scores.minimum >= config.score_floor
    gates["goodhart_sane"] = not all(
        score >= 0.99
        for score in (
            review.scores.novelty,
            review.scores.compression,
            review.scores.discrimination,
            review.scores.falsifiability,
        )
    )
    reasons.extend(name for name, passed in gates.items() if not passed and name not in reasons)
    verdict = review.verdict if not reasons else ReviewVerdict.REJECT
    return ValidationReceipt(
        cycle_id=context.cycle_id,
        seed_id=context.seed_id,
        candidate_digest=digest,
        input_snapshot_hash=context.input_snapshot_hash,
        baseline_snapshot_hash=context.baseline_snapshot_hash,
        gate_config_hash=_digest(
            {
                "gate_version": GATE_VERSION,
                "score_floor": config.score_floor,
                "novelty_floor": config.novelty_floor,
            }
        ),
        producer=proposal.producer,
        reviewer=review.reviewer,
        independence_class=independence_class,
        verdict=verdict,
        cited_evidence_ids=review.cited_evidence_ids,
        gates=gates,
        reasons=tuple(reasons),
        strongest_counterargument=review.strongest_counterargument,
        cheapest_falsifier=review.cheapest_falsifier,
        scores=review.scores,
    )


def _move(result: CreativeRunResult, target: CreativeState, reason: str) -> None:
    result.transitions.append(CreativeTransition(result.state, target, reason))
    result.state = target


def _terminal_round(
    result: CreativeRunResult,
    step: _RoundStepResult,
    outcome: CreativeOutcome,
    state: CreativeState,
    reason: str,
    stop_reason: str,
) -> _RoundStepResult:
    result.outcome = outcome
    _move(result, state, reason)
    result.stop_reason = stop_reason
    return _RoundStepResult(True, step.feedback, step.no_progress)


def _initial_runtime(
    context: ProposalContext,
    proposer: CreativeProposer,
    critic: ProposalCritic,
    config: CreativeLoopConfig,
) -> tuple[_CreativeLoopRuntime, _RoundStepResult]:
    result = CreativeRunResult(
        context=context,
        outcome=CreativeOutcome.NO_DISCOVERY,
        state=CreativeState.DETECT,
    )
    _move(result, CreativeState.ASSOCIATE, "contrastive evidence pairs computed")
    associations = contrastive_associations(context)
    feedback = [f"association provocations: {_canonical_json(associations)}"]
    runtime = _CreativeLoopRuntime(context, proposer, critic, config, result)
    return runtime, _RoundStepResult(False, feedback, 0)


def _call_proposer(
    runtime: _CreativeLoopRuntime,
    round_number: int,
    feedback: Sequence[str],
) -> _ProposalCallResult:
    _move(
        runtime.result,
        CreativeState.DIVERGE,
        f"round {round_number}: divergent proposal batch",
    )
    runtime.result.rounds = round_number
    try:
        batch = list(
            runtime.proposer.propose(
                runtime.context,
                round_number=round_number,
                count=runtime.config.candidates_per_round,
                feedback=feedback,
            )
        )
    except Exception as error:  # untrusted runtime boundary, fail closed
        return _ProposalCallResult([], error)
    runtime.result.model_calls += 1
    return _ProposalCallResult(batch, None)


def _screen_proposals(
    runtime: _CreativeLoopRuntime,
    batch: Sequence[CreativeProposal],
) -> list[CreativeProposal]:
    eligible: list[CreativeProposal] = []
    for proposal in batch[: runtime.config.candidates_per_round]:
        digest = proposal.candidate_digest(runtime.context)
        semantic_fingerprint = proposal.semantic_fingerprint()
        runtime.result.proposals.append(proposal)
        _, reasons = deterministic_gates(
            runtime.context,
            proposal,
            runtime.config.novelty_floor,
        )
        if semantic_fingerprint in runtime.seen:
            reasons.append("duplicate_candidate")
        runtime.seen.add(semantic_fingerprint)
        if reasons:
            runtime.result.rejections[digest] = tuple(dict.fromkeys(reasons))
        else:
            eligible.append(proposal)
    return eligible


def _progress_exhausted(
    no_progress: int,
    round_number: int,
    config: CreativeLoopConfig,
) -> bool:
    return no_progress >= config.no_progress_limit or round_number >= config.max_rounds


def _deterministic_rejection_feedback(result: CreativeRunResult) -> list[str]:
    return [reason for reasons in result.rejections.values() for reason in reasons]


def _no_eligible_step(
    runtime: _CreativeLoopRuntime,
    round_number: int,
    previous: _RoundStepResult,
) -> _RoundStepResult:
    step = _RoundStepResult(False, previous.feedback, previous.no_progress + 1)
    if _progress_exhausted(step.no_progress, round_number, runtime.config):
        return _terminal_round(
            runtime.result,
            step,
            CreativeOutcome.EXHAUSTED,
            CreativeState.EXHAUSTED,
            "no novel gate-eligible candidate",
            "no_progress",
        )
    _move(runtime.result, CreativeState.REVISE, "all candidates failed deterministic gates")
    return _RoundStepResult(
        False,
        _deterministic_rejection_feedback(runtime.result),
        step.no_progress,
    )


def _call_critic(
    runtime: _CreativeLoopRuntime,
    round_number: int,
    proposals: Sequence[CreativeProposal],
) -> _ReviewCallResult:
    _move(
        runtime.result,
        CreativeState.FALSIFY,
        f"round {round_number}: independent critic review",
    )
    try:
        reviews = list(runtime.critic.review(runtime.context, proposals))
    except Exception as error:
        return _ReviewCallResult([], error)
    runtime.result.model_calls += 1
    return _ReviewCallResult(reviews, None)


def _bind_round_receipts(
    runtime: _CreativeLoopRuntime,
    proposals: Sequence[CreativeProposal],
    reviews: Sequence[CriticReview],
) -> list[ValidationReceipt]:
    review_by_digest = {item.candidate_digest: item for item in reviews}
    round_receipts: list[ValidationReceipt] = []
    for proposal in proposals:
        digest = proposal.candidate_digest(runtime.context)
        review = review_by_digest.get(digest)
        if review is None:
            runtime.result.rejections[digest] = ("missing_critic_receipt",)
            continue
        receipt = _make_receipt(runtime.context, proposal, review, runtime.config)
        runtime.result.receipts.append(receipt)
        round_receipts.append(receipt)
        if not receipt.accepted:
            runtime.result.rejections[digest] = receipt.reasons or (
                f"critic_{review.verdict.value}",
            )
    return round_receipts


def _accept_passing(
    runtime: _CreativeLoopRuntime,
    previous: _RoundStepResult,
    proposals: Sequence[CreativeProposal],
    passing: list[ValidationReceipt],
) -> _RoundStepResult:
    passing.sort(key=lambda item: (-item.scores.minimum, item.candidate_digest))
    accepted_digests = {
        receipt.candidate_digest for receipt in passing[: max(1, runtime.config.max_accepts)]
    }
    runtime.result.accepted = [
        proposal
        for proposal in proposals
        if proposal.candidate_digest(runtime.context) in accepted_digests
    ]
    return _terminal_round(
        runtime.result,
        previous,
        CreativeOutcome.PROPOSED,
        CreativeState.PROPOSED,
        "content-bound independent receipts passed",
        "proposal_survived",
    )


def _critic_feedback(receipts: Sequence[ValidationReceipt]) -> list[str]:
    return [
        f"{receipt.candidate_digest[:12]}: " + ", ".join(receipt.reasons) for receipt in receipts
    ]


def _receipt_step(
    runtime: _CreativeLoopRuntime,
    round_number: int,
    previous: _RoundStepResult,
    proposals: Sequence[CreativeProposal],
    reviews: Sequence[CriticReview],
) -> _RoundStepResult:
    round_receipts = _bind_round_receipts(runtime, proposals, reviews)
    passing = [receipt for receipt in round_receipts if receipt.accepted]
    if passing:
        return _accept_passing(runtime, previous, proposals, passing)
    step = _RoundStepResult(False, previous.feedback, previous.no_progress + 1)
    if _progress_exhausted(step.no_progress, round_number, runtime.config):
        return _terminal_round(
            runtime.result,
            step,
            CreativeOutcome.EXHAUSTED,
            CreativeState.EXHAUSTED,
            "critic found no surviving proposal",
            "no_progress",
        )
    _move(runtime.result, CreativeState.REVISE, "critic feedback requested one bounded repair")
    return _RoundStepResult(False, _critic_feedback(round_receipts), step.no_progress)


def _run_creative_round(
    runtime: _CreativeLoopRuntime,
    round_number: int,
    previous: _RoundStepResult,
) -> _RoundStepResult:
    if runtime.result.model_calls + 2 > runtime.config.max_model_calls:
        return _terminal_round(
            runtime.result,
            previous,
            CreativeOutcome.EXHAUSTED,
            CreativeState.EXHAUSTED,
            "model-call budget exhausted",
            "model_call_budget",
        )
    proposal_call = _call_proposer(runtime, round_number, previous.feedback)
    if proposal_call.error is not None:
        return _terminal_round(
            runtime.result,
            previous,
            CreativeOutcome.FAILED,
            CreativeState.FAILED,
            f"proposer failed: {proposal_call.error}",
            "proposer_error",
        )
    eligible = _screen_proposals(runtime, proposal_call.batch)
    if not eligible:
        return _no_eligible_step(runtime, round_number, previous)
    review_call = _call_critic(runtime, round_number, eligible)
    if review_call.error is not None:
        return _terminal_round(
            runtime.result,
            previous,
            CreativeOutcome.FAILED,
            CreativeState.FAILED,
            f"critic failed: {review_call.error}",
            "critic_error",
        )
    return _receipt_step(runtime, round_number, previous, eligible, review_call.reviews)


def run_creative_loop(
    context: ProposalContext,
    proposer: CreativeProposer,
    critic: ProposalCritic,
    config: CreativeLoopConfig | None = None,
) -> CreativeRunResult:
    """Run a bounded DIVERGE→FALSIFY→REVISE loop and return PROPOSE-only artifacts."""
    cfg = config or CreativeLoopConfig()
    runtime, step = _initial_runtime(context, proposer, critic, cfg)
    for round_number in range(1, max(1, cfg.max_rounds) + 1):
        step = _run_creative_round(runtime, round_number, step)
        if step.terminal:
            return runtime.result
    _terminal_round(
        runtime.result,
        step,
        CreativeOutcome.NO_DISCOVERY,
        CreativeState.NO_DISCOVERY,
        "no proposal produced",
        "empty",
    )
    return runtime.result


@dataclass
class CreativeEnrichmentResult:
    abstract_classes: list[AbstractClass]
    runs: list[CreativeRunResult]
    receipts: list[ValidationReceipt]


def _slug(name: str, digest: str) -> str:
    base = re.sub(r"[^\w가-힣-]+", "-", name.strip().casefold(), flags=re.UNICODE)
    base = re.sub(r"-+", "-", base).strip("-") or "insight"
    return f"{base[:86]}-{digest[:8]}"


def context_from_abstract_class(
    ac: AbstractClass,
    formal_context: dict[str, frozenset[str]],
    existing_concepts: Sequence[str] = (),
) -> ProposalContext:
    observations = []
    for member in sorted(ac.extent or []):
        attrs = sorted(formal_context.get(member, frozenset()))
        observations.append(Observation.from_text(member, f"{member}: {', '.join(attrs)}", attrs))
    return ProposalContext(
        cycle_id=ac.cycleId,
        seed_id=ac.name,
        observations=tuple(observations),
        structural_intent=tuple(sorted(ac.intent or [])),
        existing_concepts=tuple(existing_concepts),
    )


class CreativeEnricher:
    """Pipeline adapter: enrich the strongest structural concepts, bounded by ``limit``."""

    def __init__(
        self,
        proposer: CreativeProposer,
        critic: ProposalCritic,
        *,
        config: CreativeLoopConfig | None = None,
        limit: int = 3,
    ) -> None:
        self._proposer = proposer
        self._critic = critic
        self._config = config or CreativeLoopConfig()
        self._limit = max(1, limit)

    def enrich(
        self,
        abstract_classes: Sequence[AbstractClass],
        formal_context: dict[str, frozenset[str]],
    ) -> CreativeEnrichmentResult:
        ranked = sorted(
            abstract_classes,
            key=lambda ac: (-(ac.stabilityScore or 0.0), ac.name),
        )[: self._limit]
        existing = tuple(f"{ac.name}: {ac.summary}" for ac in abstract_classes)
        out: list[AbstractClass] = []
        runs: list[CreativeRunResult] = []
        receipts: list[ValidationReceipt] = []
        for ac in ranked:
            if len(ac.extent or []) < 3:
                continue
            context = context_from_abstract_class(ac, formal_context, existing)
            run = run_creative_loop(context, self._proposer, self._critic, self._config)
            runs.append(run)
            receipt_by_candidate = {item.candidate_digest: item for item in run.receipts}
            for proposal in run.accepted:
                digest = proposal.candidate_digest(context)
                receipt = receipt_by_candidate[digest]
                receipts.append(receipt)
                provenance = dict(ac.provenance or {})
                provenance["creative"] = {
                    "schema": SCHEMA_VERSION,
                    "candidate_digest": digest,
                    "receipt_digest": receipt.receipt_digest,
                    "input_snapshot_hash": context.input_snapshot_hash,
                    "baseline_snapshot_hash": context.baseline_snapshot_hash,
                    "producer": proposal.producer.model,
                    "reviewer": receipt.reviewer.model,
                    "source_layer": "SECONDARY_AI",
                }
                out.append(
                    ac.model_copy(
                        update={
                            "name": _slug(proposal.name, digest),
                            "summary": proposal.definition[:240],
                            "semanticName": proposal.name,
                            "mechanism": proposal.mechanism,
                            "scope": proposal.scope,
                            "falsifier": proposal.falsifier_procedure,
                            "candidateDigest": digest,
                            "validationReceiptDigest": receipt.receipt_digest,
                            "noveltyScore": receipt.scores.novelty,
                            "provenance": provenance,
                        }
                    )
                )
        return CreativeEnrichmentResult(out, runs, receipts)


def _parse_json_array(text: str) -> list[dict[str, Any]]:
    match = _JSON_ARRAY.search(text or "")
    if not match:
        raise ValueError("model returned no JSON array")
    value = json.loads(match.group(0))
    if not isinstance(value, list):
        raise ValueError("model output must be a JSON array")
    return [item for item in value if isinstance(item, dict)]


class AgentCreativeProposer:
    """AgentClient adapter. JSON text is parsed and Pydantic-validated fail closed."""

    def __init__(self, client: Any, *, session: str = "eureka-proposer") -> None:
        self._client = client
        self._session = session

    def propose(
        self,
        context: ProposalContext,
        *,
        round_number: int,
        count: int,
        feedback: Sequence[str],
    ) -> Sequence[CreativeProposal]:
        from engine.agents.agent_models import HAIKU, LOCAL_FAST_TIER  # noqa: PLC0415

        system = (
            "You are Eureka's divergent abductive proposer. Create hypotheses, not summaries. "
            "Cross evidence sources, state a mechanism, draw a discriminative boundary, and make "
            "a risky held-out prediction. Never copy the prompt canary. Output one JSON array only."
        )
        schema = {
            key: "string/list as implied"
            for key in (
                "name",
                "definition",
                "mechanism",
                "scope",
                "support_ids",
                "positive_examples",
                "adversarial_near_misses",
                "known_failure_scope",
                "falsifier_procedure",
                "rejection_condition",
                "novelty_claim",
                "nearest_existing",
                "semantic_delta",
                "held_out_prediction",
            )
        }
        user = _canonical_json(
            {
                "task": f"propose at most {count} abstractions",
                "round": round_number,
                "input_snapshot_hash": context.input_snapshot_hash,
                "observations": [item.model_dump(mode="json") for item in context.observations],
                "structural_intent": context.structural_intent,
                "existing_concepts": context.existing_concepts,
                "contrastive_associations": contrastive_associations(context),
                "feedback": list(feedback),
                "required_object_fields": schema,
                "canary_do_not_copy": context.prompt_canary,
            }
        )
        prompt_hash = hashlib.sha256(f"{system}\n{user}".encode("utf-8")).hexdigest()
        seed = int(context.input_snapshot_hash[:8], 16) + round_number
        completion = self._client.complete(
            system=system,
            user=user,
            model=HAIKU,
            max_tokens=4096,
            temperature=0.85,
            seed=seed,
            tier=LOCAL_FAST_TIER,
        )
        provider = "local" if self._client.is_local() else "anthropic"
        actor = ActorFingerprint(
            provider=provider,
            model=completion.model,
            role="proposer",
            session=self._session,
            prompt_hash=prompt_hash,
            seed=seed,
        )
        proposals = []
        for raw in _parse_json_array(completion.text)[:count]:
            proposals.append(
                CreativeProposal.model_validate(
                    {
                        **raw,
                        "producer": actor.model_dump(mode="json"),
                        "round": round_number,
                    }
                )
            )
        return proposals


class AgentProposalCritic:
    """AgentClient adapter for a blinded, lower-temperature proposal critic."""

    def __init__(self, client: Any, *, session: str = "eureka-critic") -> None:
        self._client = client
        self._session = session

    def review(
        self, context: ProposalContext, proposals: Sequence[CreativeProposal]
    ) -> Sequence[CriticReview]:
        from engine.agents.agent_models import LOCAL_BIG_TIER, OPUS  # noqa: PLC0415

        system = (
            "You are Eureka's adversarial critic. Treat every proposal as probably false. "
            "Check whether it explains at least three cited observations, separates near misses, "
            "differs from the baseline, and names a cheap falsifier. Output one JSON array only."
        )
        user = _canonical_json(
            {
                "input_snapshot_hash": context.input_snapshot_hash,
                "observations": [item.model_dump(mode="json") for item in context.observations],
                "baseline": context.existing_concepts,
                "proposals": [
                    {
                        "candidate_digest": item.candidate_digest(context),
                        **item.core(),
                    }
                    for item in proposals
                ],
                "required_fields": [
                    "candidate_digest",
                    "verdict(PASS|REVISE|REJECT)",
                    "cited_evidence_ids",
                    "strongest_counterargument",
                    "cheapest_falsifier",
                    "scores{novelty,compression,discrimination,falsifiability}",
                ],
            }
        )
        prompt_hash = hashlib.sha256(f"{system}\n{user}".encode("utf-8")).hexdigest()
        completion = self._client.complete(
            system=system,
            user=user,
            model=OPUS,
            max_tokens=4096,
            temperature=0.0,
            tier=LOCAL_BIG_TIER,
        )
        provider = "local" if self._client.is_local() else "anthropic"
        actor = ActorFingerprint(
            provider=provider,
            model=completion.model,
            role="critic",
            session=self._session,
            prompt_hash=prompt_hash,
        )
        return [
            CriticReview.model_validate({**raw, "reviewer": actor.model_dump(mode="json")})
            for raw in _parse_json_array(completion.text)
        ]


__all__ = [
    "ActorFingerprint",
    "AgentCreativeProposer",
    "AgentProposalCritic",
    "CreativeEnricher",
    "CreativeEnrichmentResult",
    "CreativeLoopConfig",
    "CreativeOutcome",
    "CreativeProposal",
    "CreativeProposer",
    "CreativeRunResult",
    "CreativeState",
    "CriticReview",
    "IndependenceClass",
    "Observation",
    "ProposalContext",
    "ProposalCritic",
    "ReviewVerdict",
    "ScoreCard",
    "ValidationReceipt",
    "context_from_abstract_class",
    "contrastive_associations",
    "deterministic_gates",
    "run_creative_loop",
]
