"""Eureka semantic creative loop: divergence is free, acceptance is fail-closed."""

from __future__ import annotations

import hashlib
import json

import pytest

from engine.agents.client import Completion
from engine.eureka.creative import (
    ActorFingerprint,
    AgentCreativeProposer,
    AgentProposalCritic,
    CreativeEnricher,
    CreativeLoopConfig,
    CreativeOutcome,
    CreativeProposal,
    CriticReview,
    Observation,
    ProposalContext,
    ReviewVerdict,
    ScoreCard,
    deterministic_gates,
    run_creative_loop,
)
from engine.eureka.pipeline import PipelineConfig, run


def _actor(model: str, role: str) -> ActorFingerprint:
    return ActorFingerprint(
        provider="test",
        model=model,
        role=role,
        session=f"session-{role}",
        prompt_hash=hashlib.sha256(f"prompt-{role}".encode()).hexdigest(),
        seed=7 if role == "proposer" else None,
    )


def _context(*, baseline: tuple[str, ...] = ()) -> ProposalContext:
    rows = (
        ("lease", "A lease transfers ownership while rejecting stale effects."),
        ("schema", "A schema epoch advances monotonically and rejects older writers."),
        ("token", "A fencing token orders ownership transfer and invalidates stale actors."),
    )
    return ProposalContext(
        cycle_id="creative-test",
        seed_id="structural-seed",
        observations=tuple(Observation.from_text(key, text, (key,)) for key, text in rows),
        structural_intent=("monotonic_version", "stale_effect_rejection"),
        existing_concepts=baseline,
    )


def _proposal(
    *,
    producer_model: str = "model-a",
    name: str = "temporal authority membrane",
    definition: str = (
        "A boundary that turns ownership change into a monotone authority epoch across domains."
    ),
) -> CreativeProposal:
    return CreativeProposal(
        name=name,
        definition=definition,
        mechanism=(
            "Each transfer emits a higher epoch; any effect carrying an older epoch is refused "
            "before it can mutate shared state."
        ),
        scope="Concurrent systems with transferable single-writer authority.",
        support_ids=("lease", "schema", "token"),
        positive_examples=(
            "database leader handoff",
            "schema migration writer fencing",
            "distributed lock lease replacement",
        ),
        adversarial_near_misses=(
            "a timestamp used only for logging",
            "a mutex with no ownership transfer",
        ),
        known_failure_scope="It does not solve Byzantine actors that can forge authority epochs.",
        falsifier_procedure=(
            "Replay an effect from the previous owner after transfer and observe whether it mutates state."
        ),
        rejection_condition="Reject the concept if any stale effect is accepted.",
        novelty_claim=(
            "It unifies lease fencing, schema epochs, and ownership transfer as one causal boundary."
        ),
        nearest_existing="fencing token",
        semantic_delta=(
            "The abstraction covers the transfer protocol and stale-effect veto, not merely token order."
        ),
        held_out_prediction=(
            "A cache-primary handoff using the same boundary will reject delayed writes without locks."
        ),
        producer=_actor(producer_model, "proposer"),
        round=1,
    )


class _OneProposer:
    def __init__(self, proposal: CreativeProposal) -> None:
        self.proposal = proposal
        self.calls = 0

    def propose(self, context, *, round_number, count, feedback):
        self.calls += 1
        return [self.proposal.model_copy(update={"round": round_number})]


class _PassCritic:
    def __init__(self, reviewer_model: str = "model-b") -> None:
        self.reviewer_model = reviewer_model

    def review(self, context, proposals):
        return [
            CriticReview(
                candidate_digest=proposal.candidate_digest(context),
                verdict=ReviewVerdict.PASS,
                cited_evidence_ids=("lease", "schema", "token"),
                strongest_counterargument="The three mechanisms may share vocabulary but not causality.",
                cheapest_falsifier="Inject one stale write after each ownership transfer.",
                scores=ScoreCard(
                    novelty=0.78,
                    compression=0.74,
                    discrimination=0.81,
                    falsifiability=0.86,
                ),
                reviewer=_actor(self.reviewer_model, "critic"),
            )
            for proposal in proposals
        ]


def test_cross_source_abstraction_gets_content_bound_receipt():
    context = _context()
    result = run_creative_loop(context, _OneProposer(_proposal()), _PassCritic())

    assert result.outcome is CreativeOutcome.PROPOSED
    assert len(result.accepted) == 1
    receipt = result.receipts[0]
    assert receipt.accepted is True
    assert receipt.candidate_digest == result.accepted[0].candidate_digest(context)
    assert receipt.input_snapshot_hash == context.input_snapshot_hash
    assert len(receipt.receipt_digest) == 64


def test_correlated_producer_reviewer_cannot_self_accept():
    context = _context()
    result = run_creative_loop(
        context,
        _OneProposer(_proposal(producer_model="same-model")),
        _PassCritic(reviewer_model="same-model"),
        CreativeLoopConfig(max_rounds=1),
    )

    assert result.outcome is CreativeOutcome.EXHAUSTED
    receipt = result.receipts[0]
    assert receipt.gates["reviewer_independent"] is False
    assert receipt.accepted is False


def test_same_model_cannot_bypass_independence_with_whitespace_or_provider_change():
    context = _context()

    class _DisguisedSameModelCritic(_PassCritic):
        def review(self, context, proposals):
            reviews = list(super().review(context, proposals))
            disguised = _actor("same-model ", "critic").model_copy(
                update={"provider": "another-provider"}
            )
            return [reviews[0].model_copy(update={"reviewer": disguised})]

    result = run_creative_loop(
        context,
        _OneProposer(_proposal(producer_model="same-model")),
        _DisguisedSameModelCritic(),
        CreativeLoopConfig(max_rounds=1),
    )

    assert result.outcome is CreativeOutcome.EXHAUSTED
    assert result.receipts[0].gates["reviewer_independent"] is False


def test_critic_must_cite_every_claimed_support_source():
    context = _context()

    class _PartialEvidenceCritic(_PassCritic):
        def review(self, context, proposals):
            reviews = list(super().review(context, proposals))
            return [reviews[0].model_copy(update={"cited_evidence_ids": ("lease",)})]

    result = run_creative_loop(
        context,
        _OneProposer(_proposal()),
        _PartialEvidenceCritic(),
        CreativeLoopConfig(max_rounds=1),
    )

    assert result.outcome is CreativeOutcome.EXHAUSTED
    assert result.receipts[0].gates["evidence_cited"] is False


def test_duplicate_observation_source_ids_are_rejected():
    observation = Observation.from_text("same", "one source")
    with pytest.raises(ValueError, match="source_ids must be unique"):
        ProposalContext(
            cycle_id="duplicate-source",
            seed_id="seed",
            observations=(observation, observation, observation),
            structural_intent=("x",),
        )


def test_tampered_candidate_digest_cannot_issue_receipt():
    class _TamperedCritic(_PassCritic):
        def review(self, context, proposals):
            reviews = list(super().review(context, proposals))
            return [reviews[0].model_copy(update={"candidate_digest": "0" * 64})]

    result = run_creative_loop(
        _context(),
        _OneProposer(_proposal()),
        _TamperedCritic(),
        CreativeLoopConfig(max_rounds=1),
    )

    assert result.outcome is CreativeOutcome.EXHAUSTED
    assert result.receipts == []
    assert "missing_critic_receipt" in next(iter(result.rejections.values()))


def test_snapshot_and_candidate_hash_ignore_observation_order():
    one = _context()
    two = one.model_copy(update={"observations": tuple(reversed(one.observations))})
    proposal = _proposal()

    assert one.input_snapshot_hash == two.input_snapshot_hash
    assert proposal.candidate_digest(one) == proposal.candidate_digest(two)


def test_prompt_canary_echo_is_rejected_before_critic():
    context = _context()
    proposal = _proposal(
        definition=("A boundary that transfers authority while copying ZXQ_EUREKA_DO_NOT_COPY_91.")
    )
    gates, reasons = deterministic_gates(context, proposal, 0.25)

    assert gates["not_prompt_echo"] is False
    assert "not_prompt_echo" in reasons


def test_existing_concept_rename_is_rejected():
    proposal = _proposal(
        name="epoch authority seal",
        definition=("An epoch authority seal rejects stale effects after an ownership transfer."),
    )
    context = _context(
        baseline=("epoch authority seal rejects stale effects after an ownership transfer",)
    )
    gates, reasons = deterministic_gates(context, proposal, 0.0)

    assert gates["not_existing_concept_rename"] is False
    assert "not_existing_concept_rename" in reasons


def test_duplicate_no_progress_loop_is_bounded():
    context = _context()
    proposal = _proposal(name="concept")  # generic: deterministic rejection, repeated
    proposer = _OneProposer(proposal)
    result = run_creative_loop(
        context,
        proposer,
        _PassCritic(),
        CreativeLoopConfig(max_rounds=9, max_model_calls=10, no_progress_limit=2),
    )

    assert result.outcome is CreativeOutcome.EXHAUSTED
    assert result.rounds == 2
    assert proposer.calls == 2
    assert result.model_calls == 2  # critic was never called


def test_pipeline_enrichment_replaces_generic_ac_and_binds_receipt():
    context = {
        "lease": frozenset({"monotonic_version", "stale_effect_rejection"}),
        "schema": frozenset({"monotonic_version", "stale_effect_rejection"}),
        "token": frozenset({"monotonic_version", "stale_effect_rejection"}),
    }
    enricher = CreativeEnricher(_OneProposer(_proposal()), _PassCritic(), limit=1)
    result = run(
        reference_sites=[],
        formal_context=context,
        config=PipelineConfig(cycle_id="creative-pipeline", creative_enricher=enricher),
    )

    stage = next(item for item in result.stages if item.stage == "4.9-semantic-creative-loop")
    assert stage.ok is True
    assert len(result.proposals) == 1
    ac = result.proposals[0]
    assert ac.semanticName == "temporal authority membrane"
    assert ac.candidateDigest and ac.validationReceiptDigest
    assert result.creative_artifacts[0]["source_layer"] == "SECONDARY_AI"


def test_pipeline_acceptance_receipt_requirement_fails_closed():
    context = {
        "a": frozenset({"x", "y"}),
        "b": frozenset({"x", "y"}),
        "c": frozenset({"x", "y"}),
    }
    writes = []
    result = run(
        reference_sites=[],
        formal_context=context,
        config=PipelineConfig(
            cycle_id="no-receipt",
            fidelity_runner=lambda query, params: [
                {"witness": "independent-a", "top_shared": 3, "extent": 3},
                {"witness": "independent-b", "top_shared": 3, "extent": 3},
            ],
            persist_cypher=lambda query, params: writes.append((query, params)) or [],
            persist_accept=True,
            require_acceptance_receipt=True,
        ),
    )

    persist = next(item for item in result.stages if item.stage == "6-persist")
    assert persist.ok is False
    assert "validation receipt" in persist.error
    assert writes == []


class _JsonAgentClient:
    """Cross-backend contract fake: JSON text in, Completion out, two distinct models."""

    def is_local(self):
        return False

    def complete(self, *, system, user, model, **kwargs):
        if "divergent abductive proposer" in system:
            payload = _proposal().core()
            return Completion(text=json.dumps([payload]), model="model-a")
        request = json.loads(user)
        digest = request["proposals"][0]["candidate_digest"]
        review = {
            "candidate_digest": digest,
            "verdict": "PASS",
            "cited_evidence_ids": ["lease", "schema", "token"],
            "strongest_counterargument": "The apparent mechanism may be only lexical analogy.",
            "cheapest_falsifier": "Replay a stale effect after an ownership transfer.",
            "scores": {
                "novelty": 0.76,
                "compression": 0.75,
                "discrimination": 0.82,
                "falsifiability": 0.88,
            },
        }
        return Completion(text=json.dumps([review]), model="model-b")


def test_agentclient_json_adapters_run_end_to_end():
    context = _context()
    client = _JsonAgentClient()
    result = run_creative_loop(
        context,
        AgentCreativeProposer(client),
        AgentProposalCritic(client),
        CreativeLoopConfig(max_rounds=1),
    )

    assert result.outcome is CreativeOutcome.PROPOSED
    assert result.receipts[0].producer.model == "model-a"
    assert result.receipts[0].reviewer.model == "model-b"
