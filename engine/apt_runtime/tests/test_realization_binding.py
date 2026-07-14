from __future__ import annotations

import pytest

from engine.apt_runtime.domain.events import EventType
from engine.apt_runtime.domain.reducer import SubjectMismatchError, reduce_event
from engine.apt_runtime.domain.state import RealizationStatus
from engine.apt_runtime.tests.test_reducer import (
    SPEC,
    create_cycle,
    event,
    make_contracted,
    open_work_item,
    queue_running_effect,
    start_bound_effect,
    start_cycle,
)


def test_realization_failure_targets_the_active_effect_and_retry_clears_binding() -> None:
    state = start_bound_effect(make_contracted(open_work_item(start_cycle(create_cycle()))))
    state = queue_running_effect(state, effect_id="effect-2")
    state = reduce_event(
        state,
        event(
            EventType.EFFECT_FAILED,
            state.version + 1,
            work_item_id="work-1",
            effect_id="effect-2",
            generation=1,
            payload={
                "attempt": 1,
                "lease_token": "lease-effect-2",
                "reason": "secondary effect failed",
            },
        ),
        SPEC,
    )
    with pytest.raises(SubjectMismatchError, match="active realization effect"):
        reduce_event(
            state,
            event(
                EventType.REALIZATION_FAILED,
                state.version + 1,
                work_item_id="work-1",
                effect_id="effect-2",
                generation=1,
                payload={"effect_id": "effect-2", "reason": "secondary effect failed"},
            ),
            SPEC,
        )

    state = reduce_event(
        state,
        event(
            EventType.EFFECT_FAILED,
            state.version + 1,
            work_item_id="work-1",
            effect_id="effect-1",
            generation=1,
            payload={
                "attempt": 1,
                "lease_token": "lease-effect-1",
                "reason": "active realization failed",
            },
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
            payload={"effect_id": "effect-1", "reason": "active realization failed"},
        ),
        SPEC,
    )
    failed = state.work_item("work-1")
    assert failed.realization is RealizationStatus.FAILED
    assert failed.realization_effect_id == "effect-1"

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
    retried = state.work_item("work-1")
    assert retried.realization is RealizationStatus.READY
    assert retried.realization_effect_id is None
