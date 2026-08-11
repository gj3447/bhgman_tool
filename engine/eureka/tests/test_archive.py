"""Pure CandidateArchive reducer tests."""

from __future__ import annotations

import hashlib

import pytest
from pydantic import ValidationError

from engine.eureka.archive import (
    CANDIDATE_EVALUATED,
    CANDIDATE_OBSERVED,
    CREATIVE_RUN_COMPLETED,
    ArchiveProjectionError,
    ArchiveStatus,
    CandidateEvaluated,
    CandidateObserved,
    CreativeRunCompleted,
    EventPosition,
    reduce_candidate_archive,
)


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _observed(*, cycle: str = "cycle-1", proposal: str = "proposal-1") -> CandidateObserved:
    candidate = _sha("candidate")
    return CandidateObserved(
        candidate_digest=candidate,
        semantic_fingerprint=_sha("fingerprint"),
        candidate_ref=candidate,
        context_ref=_sha(f"context:{cycle}"),
        proposal_ref=_sha(proposal),
        cycle_id=cycle,
        seed_id="seed",
        round=1,
    )


def _position(seq: int, run_id: str = "run-1") -> EventPosition:
    return EventPosition(global_seq=seq, run_id=run_id, run_seq=seq)


def test_observe_then_propose_builds_content_bound_projection() -> None:
    observed = _observed()
    entry = reduce_candidate_archive(
        None,
        CANDIDATE_OBSERVED,
        observed.model_dump(mode="json"),
        _position(1),
    )
    assert entry is not None
    assert entry.status is ArchiveStatus.OBSERVED
    assert entry.candidate_ref == observed.candidate_digest

    evaluated = CandidateEvaluated(
        candidate_digest=observed.candidate_digest,
        outcome=ArchiveStatus.PROPOSED,
        receipt_ref=_sha("receipt"),
        score_min=0.72,
    )
    proposed = reduce_candidate_archive(
        entry,
        CANDIDATE_EVALUATED,
        evaluated.model_dump(mode="json"),
        _position(2),
    )

    assert proposed is not None
    assert proposed.status is ArchiveStatus.PROPOSED
    assert proposed.latest_receipt_ref == evaluated.receipt_ref
    assert proposed.rejection_reasons == ()
    assert proposed.last_global_seq == 2


def test_repeated_observation_preserves_first_and_updates_last_occurrence() -> None:
    first = _observed(cycle="cycle-1", proposal="proposal-1")
    entry = reduce_candidate_archive(
        None,
        CANDIDATE_OBSERVED,
        first.model_dump(mode="json"),
        _position(1, "run-1"),
    )
    second = _observed(cycle="cycle-2", proposal="proposal-2")
    repeated = reduce_candidate_archive(
        entry,
        CANDIDATE_OBSERVED,
        second.model_dump(mode="json"),
        _position(5, "run-2"),
    )

    assert repeated is not None
    assert repeated.seen_count == 2
    assert repeated.first_cycle_id == "cycle-1"
    assert repeated.last_cycle_id == "cycle-2"
    assert repeated.first_proposal_ref == first.proposal_ref
    assert repeated.last_proposal_ref == second.proposal_ref


def test_rejection_deduplicates_reasons() -> None:
    observed = _observed()
    entry = reduce_candidate_archive(
        None,
        CANDIDATE_OBSERVED,
        observed.model_dump(mode="json"),
        _position(1),
    )
    rejected = CandidateEvaluated(
        candidate_digest=observed.candidate_digest,
        outcome=ArchiveStatus.REJECTED,
        reasons=("novelty_floor", "novelty_floor", ""),
    )
    result = reduce_candidate_archive(
        entry,
        CANDIDATE_EVALUATED,
        rejected.model_dump(mode="json"),
        _position(2),
    )

    assert result is not None
    assert result.status is ArchiveStatus.REJECTED
    assert result.rejection_reasons == ("novelty_floor",)


def test_evaluation_before_observation_fails_closed() -> None:
    event = CandidateEvaluated(
        candidate_digest=_sha("unknown"),
        outcome=ArchiveStatus.REJECTED,
        reasons=("not_observed",),
    )
    with pytest.raises(ArchiveProjectionError, match="evaluated before"):
        reduce_candidate_archive(
            None,
            CANDIDATE_EVALUATED,
            event.model_dump(mode="json"),
            _position(1),
        )


def test_candidate_reference_must_equal_candidate_digest() -> None:
    with pytest.raises(ValidationError, match="candidate_ref"):
        CandidateObserved(
            candidate_digest=_sha("candidate"),
            semantic_fingerprint=_sha("fingerprint"),
            candidate_ref=_sha("different"),
            context_ref=_sha("context"),
            proposal_ref=_sha("proposal"),
            cycle_id="cycle",
            seed_id="seed",
            round=1,
        )


def test_proposed_requires_receipt() -> None:
    with pytest.raises(ValidationError, match="PROPOSED requires"):
        CandidateEvaluated(
            candidate_digest=_sha("candidate"),
            outcome=ArchiveStatus.PROPOSED,
        )


def test_run_completed_is_validated_but_does_not_change_candidate() -> None:
    observed = _observed()
    entry = reduce_candidate_archive(
        None,
        CANDIDATE_OBSERVED,
        observed.model_dump(mode="json"),
        _position(1),
    )
    completed = CreativeRunCompleted(
        context_ref=observed.context_ref,
        outcome="PROPOSED",
        state="PROPOSED",
        rounds=1,
        model_calls=2,
        stop_reason="proposal_survived",
    )

    unchanged = reduce_candidate_archive(
        entry,
        CREATIVE_RUN_COMPLETED,
        completed.model_dump(mode="json"),
        _position(2),
    )
    assert unchanged == entry


def test_unknown_journal_event_is_ignored() -> None:
    assert reduce_candidate_archive(None, "BudgetConsumed.v1", {}, _position(1)) is None
