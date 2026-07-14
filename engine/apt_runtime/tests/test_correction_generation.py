from __future__ import annotations

import pytest

from engine.apt_runtime.domain.events import EventType
from engine.apt_runtime.domain.reducer import (
    InvalidTransitionError,
    StaleGenerationError,
    SubjectMismatchError,
    reduce_event,
)
from engine.apt_runtime.domain.state import EffectLifecycle, RealizationStatus
from engine.apt_runtime.tests.test_reducer import (
    SPEC,
    create_cycle,
    dispatch_work_item,
    event,
    guard_payload,
    make_contracted,
    open_work_item,
    queue_running_effect,
    start_bound_effect,
    start_cycle,
)


def _materialized_state():
    state = start_bound_effect(make_contracted(open_work_item(start_cycle(create_cycle()))))
    state = reduce_event(
        state,
        event(
            EventType.EFFECT_SUCCEEDED,
            state.version + 1,
            work_item_id="work-1",
            effect_id="effect-1",
            generation=1,
            payload={"result_ref": "result://1", "result_hash": "1" * 64},
        ),
        SPEC,
    )
    return reduce_event(
        state,
        event(
            EventType.ARTIFACT_MATERIALIZED,
            state.version + 1,
            work_item_id="work-1",
            effect_id="effect-1",
            generation=1,
            payload=guard_payload(
                effect_id="effect-1",
                artifact_ref="artifact://1",
                artifact_hash="2" * 64,
            ),
        ),
        SPEC,
    )


def test_effect_retry_waits_for_work_level_realization_retry_approval() -> None:
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
            EventType.REALIZATION_FAILED,
            state.version + 1,
            work_item_id="work-1",
            effect_id="effect-1",
            generation=1,
            payload={"effect_id": "effect-1", "reason": "worker failure"},
        ),
        SPEC,
    )
    retry_event = event(
        EventType.EFFECT_RETRY_QUEUED,
        state.version + 1,
        work_item_id="work-1",
        effect_id="effect-1",
        generation=1,
        payload=guard_payload(reconciliation_ref="reconciliation://1"),
    )
    with pytest.raises(InvalidTransitionError, match="RealizationRetryApproved"):
        reduce_event(state, retry_event, SPEC)

    state = reduce_event(
        state,
        event(
            EventType.REALIZATION_RETRY_APPROVED,
            state.version + 1,
            work_item_id="work-1",
            generation=1,
            payload={"reconciliation_ref": "reconciliation://1"},
        ),
        SPEC,
    )
    state = reduce_event(
        state,
        event(
            EventType.EFFECT_RETRY_QUEUED,
            state.version + 1,
            work_item_id="work-1",
            effect_id="effect-1",
            generation=1,
            payload=guard_payload(reconciliation_ref="reconciliation://1"),
        ),
        SPEC,
    )
    assert state.effect("effect-1").lifecycle is EffectLifecycle.PENDING


def test_each_invalidation_opens_a_generation_and_old_targets_cannot_repeat() -> None:
    state = _materialized_state()
    with pytest.raises(StaleGenerationError):
        reduce_event(
            state,
            event(
                EventType.ARTIFACT_INVALIDATED,
                state.version + 1,
                work_item_id="work-1",
                generation=1,
                payload={"artifact_ref": "artifact://1", "reason": "drift"},
            ),
            SPEC,
        )

    state = reduce_event(
        state,
        event(
            EventType.ARTIFACT_INVALIDATED,
            state.version + 1,
            work_item_id="work-1",
            generation=2,
            payload={"artifact_ref": "artifact://1", "reason": "drift"},
        ),
        SPEC,
    )
    state = dispatch_work_item(state)
    state = queue_running_effect(state, effect_id="effect-2")
    state = reduce_event(
        state,
        event(
            EventType.REALIZATION_STARTED,
            state.version + 1,
            work_item_id="work-1",
            effect_id="effect-2",
            generation=2,
            payload={"effect_id": "effect-2"},
        ),
        SPEC,
    )
    state = reduce_event(
        state,
        event(
            EventType.EFFECT_SUCCEEDED,
            state.version + 1,
            work_item_id="work-1",
            effect_id="effect-2",
            generation=2,
            payload={"result_ref": "result://2", "result_hash": "3" * 64},
        ),
        SPEC,
    )
    state = reduce_event(
        state,
        event(
            EventType.ARTIFACT_MATERIALIZED,
            state.version + 1,
            work_item_id="work-1",
            effect_id="effect-2",
            generation=2,
            payload=guard_payload(
                effect_id="effect-2",
                artifact_ref="artifact://2",
                artifact_hash="4" * 64,
            ),
        ),
        SPEC,
    )
    with pytest.raises(SubjectMismatchError, match="artifact_ref"):
        reduce_event(
            state,
            event(
                EventType.ARTIFACT_INVALIDATED,
                state.version + 1,
                work_item_id="work-1",
                generation=3,
                payload={"artifact_ref": "artifact://1", "reason": "repeat"},
            ),
            SPEC,
        )


def test_invalidated_evidence_is_not_a_current_target_in_the_new_generation() -> None:
    state = make_contracted(open_work_item(start_cycle(create_cycle())))
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
            EventType.EVIDENCE_INVALIDATED,
            state.version + 1,
            work_item_id="work-1",
            generation=2,
            payload={"evidence_ref": "evidence-1", "reason": "stale"},
        ),
        SPEC,
    )
    with pytest.raises(SubjectMismatchError, match="evidence_ref"):
        reduce_event(
            state,
            event(
                EventType.EVIDENCE_INVALIDATED,
                state.version + 1,
                work_item_id="work-1",
                generation=3,
                payload={"evidence_ref": "evidence-1", "reason": "repeat"},
            ),
            SPEC,
        )


def test_evidence_invalidation_resets_nonterminal_realization_binding() -> None:
    state = start_bound_effect(make_contracted(open_work_item(start_cycle(create_cycle()))))
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
            EventType.EVIDENCE_INVALIDATED,
            state.version + 1,
            work_item_id="work-1",
            generation=2,
            payload={"evidence_ref": "evidence-1", "reason": "stale"},
        ),
        SPEC,
    )

    work = state.work_item("work-1")
    assert work.current_generation == 2
    assert work.realization is RealizationStatus.READY
    assert work.realization_effect_id is None
    assert state.effect("effect-1").generation == 1
    assert state.effect("effect-1").lifecycle is EffectLifecycle.RUNNING
