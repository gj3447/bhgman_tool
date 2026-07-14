from __future__ import annotations

from dataclasses import FrozenInstanceError, replace

import pytest

from engine.apt_runtime.domain.events import (
    EventEnvelope,
    EventSchemaError,
    EventType,
    GuardResult,
    payload_hash,
)
from engine.apt_runtime.domain.fsm_spec import FsmSpec, load_default_spec
from engine.apt_runtime.domain.reducer import (
    GuardRejectedError,
    InvalidTransitionError,
    SpecHashMismatchError,
    StaleGenerationError,
    SubjectMismatchError,
    VersionConflictError,
    reduce_event,
    replay,
)
from engine.apt_runtime.domain.state import (
    AssuranceStatus,
    CycleLifecycle,
    EffectLifecycle,
    RealizationStatus,
    SemanticMaturity,
    WorkItemKind,
    state_hash,
)


SPEC = load_default_spec()
NOW = "2026-07-13T00:00:00Z"


def event(
    event_type: EventType,
    version: int,
    *,
    cycle_id: str = "cycle-1",
    work_item_id: str | None = None,
    effect_id: str | None = None,
    generation: int | None = None,
    payload: dict[str, object] | None = None,
    spec: FsmSpec = SPEC,
) -> EventEnvelope:
    return EventEnvelope.create(
        event_id=f"event-{version}",
        stream_id=cycle_id,
        stream_version=version,
        event_type=event_type,
        schema_version="1.0.0",
        fsm_spec_hash=spec.spec_hash,
        cycle_id=cycle_id,
        work_item_id=work_item_id,
        effect_id=effect_id,
        generation=generation,
        actor="test",
        correlation_id="corr-1",
        causation_id=f"cause-{version}",
        command_id=f"command-{version}",
        config_version="config-v1",
        payload={} if payload is None else payload,
        created_at=NOW,
    )


def guard_payload(**extra: object) -> dict[str, object]:
    return {
        "guard_result": GuardResult.PASS.value,
        "guard_evidence_refs": ["evidence-1"],
        **extra,
    }


def create_cycle(*, spec: FsmSpec = SPEC):
    return reduce_event(
        None,
        event(
            EventType.CYCLE_CREATED,
            1,
            spec=spec,
            payload={
                "config_snapshot_ref": "config://v1",
                "config_snapshot_hash": "a" * 64,
                "canon_snapshot_ref": "kg://snapshot/1",
                "canon_snapshot_hash": "b" * 64,
            },
        ),
        spec,
    )


def start_cycle(state, *, spec: FsmSpec = SPEC):
    return reduce_event(
        state,
        event(EventType.CYCLE_STARTED, state.version + 1, spec=spec, payload=guard_payload()),
        spec,
    )


def open_work_item(state, *, kind: WorkItemKind = WorkItemKind.LEAF, item_id: str = "work-1"):
    return reduce_event(
        state,
        event(
            EventType.WORK_ITEM_OPENED,
            state.version + 1,
            work_item_id=item_id,
            generation=1,
            payload={"work_kind": kind.value, "parent_ids": []},
        ),
        SPEC,
    )


def make_contracted(state, *, item_id: str = "work-1"):
    sequence = [
        (EventType.ANCHOR_ACCEPTED, guard_payload()),
        (EventType.ATOMICITY_ACCEPTED, guard_payload()),
        (EventType.CRYSTALLIZATION_STARTED, {}),
        (
            EventType.CONTRACT_ACCEPTED,
            guard_payload(contract_ref="contract://1", contract_hash="c" * 64),
        ),
    ]
    for event_type, payload in sequence:
        state = reduce_event(
            state,
            event(
                event_type,
                state.version + 1,
                work_item_id=item_id,
                generation=1,
                payload=payload,
            ),
            SPEC,
        )
    return state


def dispatch_work_item(state, *, item_id: str = "work-1"):
    work_item = state.work_item(item_id)
    return reduce_event(
        state,
        event(
            EventType.DISPATCH_PLANNED,
            state.version + 1,
            work_item_id=item_id,
            generation=work_item.current_generation,
            payload=guard_payload(dispatch_ref="dispatch://1"),
        ),
        SPEC,
    )


def queue_running_effect(
    state,
    *,
    item_id: str = "work-1",
    effect_id: str = "effect-1",
    capability: str = "artifact.realize",
    provider: str = "Hades",
):
    generation = state.work_item(item_id).current_generation
    state = reduce_event(
        state,
        event(
            EventType.EFFECT_QUEUED,
            state.version + 1,
            work_item_id=item_id,
            effect_id=effect_id,
            generation=generation,
            payload={
                "capability": capability,
                "provider": provider,
                "risk_class": "REVERSIBLE_WRITE",
                "idempotency_key": f"idem-{effect_id}",
                "input_ref": "contract://1",
                "input_hash": "c" * 64,
            },
        ),
        SPEC,
    )
    state = reduce_event(
        state,
        event(
            EventType.EFFECT_LEASED,
            state.version + 1,
            work_item_id=item_id,
            effect_id=effect_id,
            generation=generation,
            payload={"lease_owner": "worker-1", "lease_expiry": NOW},
        ),
        SPEC,
    )
    state = reduce_event(
        state,
        event(
            EventType.EFFECT_STARTED,
            state.version + 1,
            work_item_id=item_id,
            effect_id=effect_id,
            generation=generation,
            payload={"attempt": 1},
        ),
        SPEC,
    )
    return state


def start_bound_effect(state, *, item_id: str = "work-1", effect_id: str = "effect-1"):
    state = dispatch_work_item(state, item_id=item_id)
    state = queue_running_effect(state, item_id=item_id, effect_id=effect_id)
    generation = state.work_item(item_id).current_generation
    return reduce_event(
        state,
        event(
            EventType.REALIZATION_STARTED,
            state.version + 1,
            work_item_id=item_id,
            effect_id=effect_id,
            generation=generation,
            payload={"effect_id": effect_id},
        ),
        SPEC,
    )


def test_event_envelope_is_deeply_immutable_and_payload_hash_is_canonical() -> None:
    left = {"accent": "e\u0301", "nested": {"b": 2, "a": [1, "x"]}}
    right = {"nested": {"a": [1, "x"], "b": 2}, "accent": "é"}
    assert payload_hash(left) == payload_hash(right)

    envelope = event(EventType.CYCLE_RESUMED, 1, payload=left)
    with pytest.raises(TypeError):
        envelope.payload["new"] = "value"  # type: ignore[index]
    with pytest.raises(TypeError):
        envelope.payload["nested"]["a"] = ()  # type: ignore[index]
    with pytest.raises(FrozenInstanceError):
        envelope.stream_version = 2  # type: ignore[misc]


def test_envelope_rejects_payload_hash_mismatch_and_non_integer_number() -> None:
    valid = event(EventType.CYCLE_RESUMED, 1, payload={"x": 1})
    with pytest.raises(EventSchemaError, match="payload_hash"):
        replace(valid, payload_hash="0" * 64)
    with pytest.raises(EventSchemaError, match="integers"):
        event(EventType.CYCLE_RESUMED, 1, payload={"x": 1.5})
    with pytest.raises(EventSchemaError, match="stream_version"):
        replace(valid, stream_version=2.0)  # type: ignore[arg-type]
    with pytest.raises(EventSchemaError, match="generation"):
        replace(valid, generation=2.0)  # type: ignore[arg-type]


def test_contract_acceptance_advances_two_regions_atomically() -> None:
    state = open_work_item(start_cycle(create_cycle()))
    original = state
    state = make_contracted(state)
    work = state.work_item("work-1")

    assert work.semantic_maturity is SemanticMaturity.CONTRACTED
    assert work.realization is RealizationStatus.READY
    assert original.work_item("work-1").semantic_maturity is SemanticMaturity.DRAFT
    assert original.work_item("work-1").realization is RealizationStatus.NOT_READY


def test_correction_opens_next_generation_resets_regions_and_preserves_history() -> None:
    state = start_bound_effect(make_contracted(open_work_item(start_cycle(create_cycle()))))
    state = reduce_event(
        state,
        event(
            EventType.EFFECT_SUCCEEDED,
            state.version + 1,
            work_item_id="work-1",
            effect_id="effect-1",
            generation=1,
            payload={"result_ref": "result://1", "result_hash": "d" * 64},
        ),
        SPEC,
    )
    state = reduce_event(
        state,
        event(
            EventType.ARTIFACT_MATERIALIZED,
            state.version + 1,
            work_item_id="work-1",
            effect_id="effect-1",
            generation=1,
            payload=guard_payload(
                effect_id="effect-1", artifact_ref="artifact://1", artifact_hash="e" * 64
            ),
        ),
        SPEC,
    )
    state = reduce_event(
        state,
        event(
            EventType.VERIFICATION_REQUESTED,
            state.version + 1,
            work_item_id="work-1",
            generation=1,
            payload={"oracle_ref": "oracle://1"},
        ),
        SPEC,
    )
    state = reduce_event(
        state,
        event(
            EventType.VERIFICATION_ACCEPTED,
            state.version + 1,
            work_item_id="work-1",
            generation=1,
            payload=guard_payload(verdict_ref="verdict://1"),
        ),
        SPEC,
    )
    before = state

    state = reduce_event(
        state,
        event(
            EventType.CORRECTION_OPENED,
            state.version + 1,
            work_item_id="work-1",
            generation=2,
            payload={
                "scope": "CONTRACT",
                "reason": "oracle drift",
                "evidence_refs": ["evidence://correction"],
            },
        ),
        SPEC,
    )
    work = state.work_item("work-1")

    assert work.current_generation == 2
    assert work.semantic_maturity is SemanticMaturity.CRYSTALLIZING
    assert work.realization is RealizationStatus.NOT_READY
    assert work.assurance is AssuranceStatus.UNASSESSED
    assert len(work.generations) == 2
    assert work.generations[0].artifacts[0].artifact_ref == "artifact://1"
    assert before.work_item("work-1").current_generation == 1


def test_stale_effect_success_is_audited_but_cannot_materialize_current_generation() -> None:
    state = start_bound_effect(make_contracted(open_work_item(start_cycle(create_cycle()))))
    state = reduce_event(
        state,
        event(
            EventType.CORRECTION_OPENED,
            state.version + 1,
            work_item_id="work-1",
            generation=2,
            payload={
                "scope": "CONTRACT",
                "reason": "new contract",
                "evidence_refs": ["evidence://2"],
            },
        ),
        SPEC,
    )
    state = reduce_event(
        state,
        event(
            EventType.EFFECT_SUCCEEDED,
            state.version + 1,
            work_item_id="work-1",
            effect_id="effect-1",
            generation=1,
            payload={"result_ref": "result://late", "result_hash": "f" * 64},
        ),
        SPEC,
    )

    assert state.effect("effect-1").lifecycle is EffectLifecycle.SUCCEEDED
    assert state.work_item("work-1").current_generation == 2
    with pytest.raises(StaleGenerationError):
        reduce_event(
            state,
            event(
                EventType.ARTIFACT_MATERIALIZED,
                state.version + 1,
                work_item_id="work-1",
                effect_id="effect-1",
                generation=1,
                payload=guard_payload(
                    effect_id="effect-1",
                    artifact_ref="artifact://late",
                    artifact_hash="1" * 64,
                ),
            ),
            SPEC,
        )


def test_late_effect_result_after_cycle_cancel_remains_auditable() -> None:
    state = start_bound_effect(make_contracted(open_work_item(start_cycle(create_cycle()))))
    state = reduce_event(
        state,
        event(
            EventType.CYCLE_CANCELLED,
            state.version + 1,
            payload={"reason": "operator request"},
        ),
        SPEC,
    )
    state = reduce_event(
        state,
        event(
            EventType.EFFECT_SUCCEEDED,
            state.version + 1,
            work_item_id="work-1",
            effect_id="effect-1",
            generation=1,
            payload={"result_ref": "result://late", "result_hash": "2" * 64},
        ),
        SPEC,
    )

    assert state.lifecycle is CycleLifecycle.CANCELLED
    assert state.effect("effect-1").lifecycle is EffectLifecycle.SUCCEEDED
    with pytest.raises(InvalidTransitionError):
        reduce_event(
            state,
            event(
                EventType.ARTIFACT_MATERIALIZED,
                state.version + 1,
                work_item_id="work-1",
                effect_id="effect-1",
                generation=1,
                payload=guard_payload(
                    effect_id="effect-1",
                    artifact_ref="artifact://late",
                    artifact_hash="3" * 64,
                ),
            ),
            SPEC,
        )


def test_cycle_cancel_forbids_new_effect_execution_but_allows_quiescing() -> None:
    state = make_contracted(open_work_item(start_cycle(create_cycle())))
    state = reduce_event(
        state,
        event(
            EventType.EFFECT_QUEUED,
            state.version + 1,
            work_item_id="work-1",
            effect_id="effect-pending",
            generation=1,
            payload={
                "capability": "artifact.realize",
                "provider": "Hades",
                "risk_class": "REVERSIBLE_WRITE",
                "idempotency_key": "idem-pending",
                "input_ref": "contract://1",
                "input_hash": "c" * 64,
            },
        ),
        SPEC,
    )
    state = reduce_event(
        state,
        event(
            EventType.CYCLE_CANCELLED,
            state.version + 1,
            payload={"reason": "operator request"},
        ),
        SPEC,
    )

    with pytest.raises(InvalidTransitionError, match="terminal cycle"):
        reduce_event(
            state,
            event(
                EventType.EFFECT_LEASED,
                state.version + 1,
                work_item_id="work-1",
                effect_id="effect-pending",
                generation=1,
                payload={"lease_owner": "worker-1", "lease_expiry": NOW},
            ),
            SPEC,
        )

    state = reduce_event(
        state,
        event(
            EventType.EFFECT_CANCELLED,
            state.version + 1,
            work_item_id="work-1",
            effect_id="effect-pending",
            generation=1,
            payload={"reason": "cycle cancelled"},
        ),
        SPEC,
    )
    assert state.effect("effect-pending").lifecycle is EffectLifecycle.CANCELLED


def test_correction_fences_old_effect_from_lease_start_or_retry() -> None:
    state = make_contracted(open_work_item(start_cycle(create_cycle())))
    state = reduce_event(
        state,
        event(
            EventType.EFFECT_QUEUED,
            state.version + 1,
            work_item_id="work-1",
            effect_id="effect-stale",
            generation=1,
            payload={
                "capability": "artifact.realize",
                "provider": "Hades",
                "risk_class": "REVERSIBLE_WRITE",
                "idempotency_key": "idem-stale",
                "input_ref": "contract://1",
                "input_hash": "c" * 64,
            },
        ),
        SPEC,
    )
    state = reduce_event(
        state,
        event(
            EventType.CORRECTION_OPENED,
            state.version + 1,
            work_item_id="work-1",
            generation=2,
            payload={
                "scope": "CONTRACT",
                "reason": "new contract",
                "evidence_refs": ["evidence://2"],
            },
        ),
        SPEC,
    )

    with pytest.raises(StaleGenerationError, match="cannot advance"):
        reduce_event(
            state,
            event(
                EventType.EFFECT_LEASED,
                state.version + 1,
                work_item_id="work-1",
                effect_id="effect-stale",
                generation=1,
                payload={"lease_owner": "worker-1", "lease_expiry": NOW},
            ),
            SPEC,
        )


def test_correction_fences_already_leased_effect_from_start() -> None:
    state = make_contracted(open_work_item(start_cycle(create_cycle())))
    state = reduce_event(
        state,
        event(
            EventType.EFFECT_QUEUED,
            state.version + 1,
            work_item_id="work-1",
            effect_id="effect-leased",
            generation=1,
            payload={
                "capability": "artifact.realize",
                "provider": "Hades",
                "risk_class": "REVERSIBLE_WRITE",
                "idempotency_key": "idem-leased",
                "input_ref": "contract://1",
                "input_hash": "c" * 64,
            },
        ),
        SPEC,
    )
    state = reduce_event(
        state,
        event(
            EventType.EFFECT_LEASED,
            state.version + 1,
            work_item_id="work-1",
            effect_id="effect-leased",
            generation=1,
            payload={"lease_owner": "worker-1", "lease_expiry": NOW},
        ),
        SPEC,
    )
    state = reduce_event(
        state,
        event(
            EventType.CORRECTION_OPENED,
            state.version + 1,
            work_item_id="work-1",
            generation=2,
            payload={
                "scope": "CONTRACT",
                "reason": "new contract",
                "evidence_refs": ["evidence://2"],
            },
        ),
        SPEC,
    )

    with pytest.raises(StaleGenerationError, match="cannot advance"):
        reduce_event(
            state,
            event(
                EventType.EFFECT_STARTED,
                state.version + 1,
                work_item_id="work-1",
                effect_id="effect-leased",
                generation=1,
                payload={"attempt": 1},
            ),
            SPEC,
        )


def test_correction_fences_failed_effect_from_retry() -> None:
    state = start_bound_effect(make_contracted(open_work_item(start_cycle(create_cycle()))))
    state = reduce_event(
        state,
        event(
            EventType.EFFECT_FAILED,
            state.version + 1,
            work_item_id="work-1",
            effect_id="effect-1",
            generation=1,
            payload={"reason": "worker failure"},
        ),
        SPEC,
    )
    state = reduce_event(
        state,
        event(
            EventType.CORRECTION_OPENED,
            state.version + 1,
            work_item_id="work-1",
            generation=2,
            payload={
                "scope": "CONTRACT",
                "reason": "new contract",
                "evidence_refs": ["evidence://2"],
            },
        ),
        SPEC,
    )

    with pytest.raises(StaleGenerationError, match="cannot advance"):
        reduce_event(
            state,
            event(
                EventType.EFFECT_RETRY_QUEUED,
                state.version + 1,
                work_item_id="work-1",
                effect_id="effect-1",
                generation=1,
                payload=guard_payload(reconciliation_ref="reconcile://1"),
            ),
            SPEC,
        )


def test_decomposed_container_can_open_a_decomposition_correction() -> None:
    state = open_work_item(
        start_cycle(create_cycle()), kind=WorkItemKind.CONTAINER, item_id="parent"
    )
    state = reduce_event(
        state,
        event(
            EventType.ANCHOR_ACCEPTED,
            state.version + 1,
            work_item_id="parent",
            generation=1,
            payload=guard_payload(),
        ),
        SPEC,
    )
    state = reduce_event(
        state,
        event(
            EventType.DECOMPOSITION_STARTED,
            state.version + 1,
            work_item_id="parent",
            generation=1,
        ),
        SPEC,
    )
    state = reduce_event(
        state,
        event(
            EventType.WORK_ITEM_OPENED,
            state.version + 1,
            work_item_id="child",
            generation=1,
            payload={"work_kind": "LEAF", "parent_ids": ["parent"]},
        ),
        SPEC,
    )
    state = reduce_event(
        state,
        event(
            EventType.CHILDREN_ATTACHED,
            state.version + 1,
            work_item_id="parent",
            generation=1,
            payload=guard_payload(child_ids=["child"]),
        ),
        SPEC,
    )
    assert state.work_item("parent").semantic_maturity is SemanticMaturity.DECOMPOSED

    state = reduce_event(
        state,
        event(
            EventType.CORRECTION_OPENED,
            state.version + 1,
            work_item_id="parent",
            generation=2,
            payload={
                "scope": "DECOMPOSITION",
                "reason": "missing branch",
                "evidence_refs": ["evidence://decomposition"],
            },
        ),
        SPEC,
    )
    parent = state.work_item("parent")
    assert parent.current_generation == 2
    assert parent.semantic_maturity is SemanticMaturity.DECOMPOSING


def test_work_events_reject_ghost_or_disagreeing_effect_identity() -> None:
    state = open_work_item(start_cycle(create_cycle()))
    with pytest.raises(SubjectMismatchError, match="effect_id"):
        reduce_event(
            state,
            event(
                EventType.ANCHOR_ACCEPTED,
                state.version + 1,
                work_item_id="work-1",
                effect_id="ghost-effect",
                generation=1,
                payload=guard_payload(),
            ),
            SPEC,
        )

    running = start_bound_effect(make_contracted(state))
    mismatched = event(
        EventType.REALIZATION_STARTED,
        running.version + 1,
        work_item_id="work-1",
        effect_id="effect-1",
        generation=1,
        payload={"effect_id": "different-effect"},
    )
    with pytest.raises(SubjectMismatchError, match="payload effect_id"):
        reduce_event(running, mismatched, SPEC)

    succeeded = reduce_event(
        running,
        event(
            EventType.EFFECT_SUCCEEDED,
            running.version + 1,
            work_item_id="work-1",
            effect_id="effect-1",
            generation=1,
            payload={"result_ref": "result://1", "result_hash": "d" * 64},
        ),
        SPEC,
    )
    mismatched_materialization = event(
        EventType.ARTIFACT_MATERIALIZED,
        succeeded.version + 1,
        work_item_id="work-1",
        effect_id="effect-1",
        generation=1,
        payload=guard_payload(
            effect_id="different-effect",
            artifact_ref="artifact://1",
            artifact_hash="e" * 64,
        ),
    )
    with pytest.raises(SubjectMismatchError, match="payload effect_id"):
        reduce_event(succeeded, mismatched_materialization, SPEC)


def test_superseded_work_item_rejects_late_artifact_materialization() -> None:
    state = start_bound_effect(make_contracted(open_work_item(start_cycle(create_cycle()))))
    state = reduce_event(
        state,
        event(
            EventType.WORK_ITEM_SUPERSEDED,
            state.version + 1,
            work_item_id="work-1",
            generation=1,
            payload={"reason": "replaced branch"},
        ),
        SPEC,
    )
    state = reduce_event(
        state,
        event(
            EventType.EFFECT_SUCCEEDED,
            state.version + 1,
            work_item_id="work-1",
            effect_id="effect-1",
            generation=1,
            payload={"result_ref": "result://late", "result_hash": "4" * 64},
        ),
        SPEC,
    )

    with pytest.raises(InvalidTransitionError, match="SUPERSEDED"):
        reduce_event(
            state,
            event(
                EventType.ARTIFACT_MATERIALIZED,
                state.version + 1,
                work_item_id="work-1",
                effect_id="effect-1",
                generation=1,
                payload=guard_payload(
                    effect_id="effect-1",
                    artifact_ref="artifact://late",
                    artifact_hash="5" * 64,
                ),
            ),
            SPEC,
        )


def _closed_accepted_materialized_leaf():
    state = start_bound_effect(make_contracted(open_work_item(start_cycle(create_cycle()))))
    state = reduce_event(
        state,
        event(
            EventType.EFFECT_SUCCEEDED,
            state.version + 1,
            work_item_id="work-1",
            effect_id="effect-1",
            generation=1,
            payload={"result_ref": "result://1", "result_hash": "6" * 64},
        ),
        SPEC,
    )
    state = reduce_event(
        state,
        event(
            EventType.ARTIFACT_MATERIALIZED,
            state.version + 1,
            work_item_id="work-1",
            effect_id="effect-1",
            generation=1,
            payload=guard_payload(
                effect_id="effect-1", artifact_ref="artifact://1", artifact_hash="7" * 64
            ),
        ),
        SPEC,
    )
    state = reduce_event(
        state,
        event(
            EventType.VERIFICATION_REQUESTED,
            state.version + 1,
            work_item_id="work-1",
            generation=1,
            payload={"oracle_ref": "oracle://1"},
        ),
        SPEC,
    )
    state = reduce_event(
        state,
        event(
            EventType.VERIFICATION_ACCEPTED,
            state.version + 1,
            work_item_id="work-1",
            generation=1,
            payload=guard_payload(verdict_ref="verdict://1"),
        ),
        SPEC,
    )
    state = reduce_event(
        state,
        event(
            EventType.WORK_ITEM_CLOSED,
            state.version + 1,
            work_item_id="work-1",
            generation=1,
            payload=guard_payload(closure_kind="LEAF"),
        ),
        SPEC,
    )
    return state


def test_closed_artifact_invalidation_reopens_into_next_generation() -> None:
    state = _closed_accepted_materialized_leaf()
    prior_generation = state.work_item("work-1").generation_history(1)

    state = reduce_event(
        state,
        event(
            EventType.ARTIFACT_INVALIDATED,
            state.version + 1,
            work_item_id="work-1",
            generation=2,
            payload={"artifact_ref": "artifact://1", "reason": "hash drift"},
        ),
        SPEC,
    )
    work = state.work_item("work-1")
    assert work.lifecycle.value == "OPEN"
    assert work.current_generation == 2
    assert work.realization is RealizationStatus.READY
    assert work.assurance is AssuranceStatus.UNASSESSED
    assert work.generation_history(1) == prior_generation
    assert work.generation_history(2).artifacts == ()


def test_closed_evidence_invalidation_reopens_and_preserves_artifact_provenance() -> None:
    state = _closed_accepted_materialized_leaf()
    prior_generation = state.work_item("work-1").generation_history(1)

    state = reduce_event(
        state,
        event(
            EventType.EVIDENCE_INVALIDATED,
            state.version + 1,
            work_item_id="work-1",
            generation=2,
            payload={"evidence_ref": "evidence-1", "reason": "oracle drift"},
        ),
        SPEC,
    )
    work = state.work_item("work-1")
    assert work.lifecycle.value == "OPEN"
    assert work.current_generation == 2
    assert work.realization is RealizationStatus.MATERIALIZED
    assert work.realization_effect_id == "effect-1"
    assert work.assurance is AssuranceStatus.UNASSESSED
    assert work.generation_history(1) == prior_generation
    assert work.generation_history(2).artifacts == prior_generation.artifacts
    assert work.generation_history(2).evidence_refs == ()


def test_closed_correction_reopens_and_resets_downstream_regions() -> None:
    state = _closed_accepted_materialized_leaf()

    state = reduce_event(
        state,
        event(
            EventType.CORRECTION_OPENED,
            state.version + 1,
            work_item_id="work-1",
            generation=2,
            payload={
                "scope": "CONTRACT",
                "reason": "contract drift",
                "evidence_refs": ["evidence://correction"],
            },
        ),
        SPEC,
    )
    work = state.work_item("work-1")
    assert work.lifecycle.value == "OPEN"
    assert work.current_generation == 2
    assert work.semantic_maturity is SemanticMaturity.CRYSTALLIZING
    assert work.realization is RealizationStatus.NOT_READY
    assert work.realization_effect_id is None
    assert work.assurance is AssuranceStatus.UNASSESSED


def test_closed_work_item_fences_ordinary_work_and_new_effects() -> None:
    state = make_contracted(open_work_item(start_cycle(create_cycle())))
    state = reduce_event(
        state,
        event(
            EventType.WORK_ITEM_CLOSED,
            state.version + 1,
            work_item_id="work-1",
            generation=1,
            payload=guard_payload(closure_kind="LEAF"),
        ),
        SPEC,
    )

    with pytest.raises(InvalidTransitionError, match="CLOSED"):
        dispatch_work_item(state)
    with pytest.raises(InvalidTransitionError, match="CLOSED"):
        reduce_event(
            state,
            event(
                EventType.EFFECT_QUEUED,
                state.version + 1,
                work_item_id="work-1",
                effect_id="effect-1",
                generation=1,
                payload={
                    "capability": "artifact.realize",
                    "provider": "Hades",
                    "risk_class": "REVERSIBLE_WRITE",
                    "idempotency_key": "idem-effect-1",
                    "input_ref": "contract://1",
                    "input_hash": "8" * 64,
                },
            ),
            SPEC,
        )


def test_closed_work_item_fences_effect_execution_but_allows_late_audit() -> None:
    state = dispatch_work_item(make_contracted(open_work_item(start_cycle(create_cycle()))))
    state = reduce_event(
        state,
        event(
            EventType.EFFECT_QUEUED,
            state.version + 1,
            work_item_id="work-1",
            effect_id="effect-1",
            generation=1,
            payload={
                "capability": "artifact.realize",
                "provider": "Hades",
                "risk_class": "REVERSIBLE_WRITE",
                "idempotency_key": "idem-effect-1",
                "input_ref": "contract://1",
                "input_hash": "9" * 64,
            },
        ),
        SPEC,
    )
    state = reduce_event(
        state,
        event(
            EventType.WORK_ITEM_CLOSED,
            state.version + 1,
            work_item_id="work-1",
            generation=1,
            payload=guard_payload(closure_kind="LEAF"),
        ),
        SPEC,
    )

    with pytest.raises(InvalidTransitionError, match="CLOSED"):
        reduce_event(
            state,
            event(
                EventType.EFFECT_LEASED,
                state.version + 1,
                work_item_id="work-1",
                effect_id="effect-1",
                generation=1,
                payload={"lease_owner": "worker-1", "lease_expiry": NOW},
            ),
            SPEC,
        )

    state = reduce_event(
        state,
        event(
            EventType.EFFECT_CANCELLED,
            state.version + 1,
            work_item_id="work-1",
            effect_id="effect-1",
            generation=1,
            payload={"reason": "closed"},
        ),
        SPEC,
    )
    assert state.effect("effect-1").lifecycle is EffectLifecycle.CANCELLED


def test_required_payload_fields_are_typed_not_presence_only() -> None:
    state = start_cycle(create_cycle())
    with pytest.raises(EventSchemaError, match="reason"):
        reduce_event(
            state,
            event(EventType.CYCLE_CANCELLED, state.version + 1, payload={"reason": None}),
            SPEC,
        )


def test_replay_and_state_hash_are_deterministic() -> None:
    events = (
        event(
            EventType.CYCLE_CREATED,
            1,
            payload={
                "canon_snapshot_hash": "b" * 64,
                "canon_snapshot_ref": "kg://snapshot/1",
                "config_snapshot_hash": "a" * 64,
                "config_snapshot_ref": "config://v1",
            },
        ),
        event(EventType.CYCLE_STARTED, 2, payload=guard_payload()),
        event(
            EventType.CYCLE_WAITING_ENTERED,
            3,
            payload={"need_ref": "need://dependency"},
        ),
    )

    first = replay(events, SPEC)
    second = replay(tuple(events), SPEC)
    assert first == second
    assert state_hash(first) == state_hash(second)
    assert first.lifecycle is CycleLifecycle.WAITING


def test_fail_closed_on_guard_version_subject_spec_and_generation_errors() -> None:
    created = create_cycle()
    with pytest.raises(GuardRejectedError):
        reduce_event(
            created,
            event(
                EventType.CYCLE_STARTED,
                2,
                payload={"guard_result": "DENY", "guard_evidence_refs": ["evidence-1"]},
            ),
            SPEC,
        )
    with pytest.raises(VersionConflictError):
        reduce_event(
            created,
            event(EventType.CYCLE_STARTED, 3, payload=guard_payload()),
            SPEC,
        )
    with pytest.raises(SubjectMismatchError):
        reduce_event(
            created,
            event(
                EventType.CYCLE_STARTED,
                2,
                cycle_id="different-cycle",
                payload=guard_payload(),
            ),
            SPEC,
        )
    wrong_hash = replace(
        event(EventType.CYCLE_STARTED, 2, payload=guard_payload()),
        fsm_spec_hash="9" * 64,
    )
    with pytest.raises(SpecHashMismatchError):
        reduce_event(created, wrong_hash, SPEC)

    opened = open_work_item(start_cycle(created))
    with pytest.raises(StaleGenerationError):
        reduce_event(
            opened,
            event(
                EventType.ANCHOR_ACCEPTED,
                opened.version + 1,
                work_item_id="work-1",
                generation=2,
                payload=guard_payload(),
            ),
            SPEC,
        )


def test_terminal_cycle_rejects_lifecycle_reopen() -> None:
    state = start_cycle(create_cycle())
    state = reduce_event(
        state,
        event(EventType.CYCLE_CANCELLED, 3, payload={"reason": "stop"}),
        SPEC,
    )

    with pytest.raises(InvalidTransitionError):
        reduce_event(
            state,
            event(EventType.CYCLE_RESUMED, 4),
            SPEC,
        )


def test_unknown_event_schema_version_is_rejected() -> None:
    created = create_cycle()
    unsupported = replace(
        event(EventType.CYCLE_STARTED, 2, payload=guard_payload()),
        schema_version="2.0.0",
    )
    with pytest.raises(EventSchemaError, match="schema_version"):
        reduce_event(created, unsupported, SPEC)
