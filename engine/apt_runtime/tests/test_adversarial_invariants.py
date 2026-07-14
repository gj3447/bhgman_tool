from __future__ import annotations

import pytest

from engine.apt_runtime.domain.events import EventType
from engine.apt_runtime.domain.reducer import (
    InvalidTransitionError,
    SubjectMismatchError,
    reduce_event,
)
from engine.apt_runtime.domain.state import (
    AssuranceStatus,
    RealizationStatus,
    WorkItemKind,
    state_hash,
)
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


def _anchor(state, *, item_id: str):
    return reduce_event(
        state,
        event(
            EventType.ANCHOR_ACCEPTED,
            state.version + 1,
            work_item_id=item_id,
            generation=state.work_item(item_id).current_generation,
            payload=guard_payload(),
        ),
        SPEC,
    )


def _start_decomposition(state, *, item_id: str):
    return reduce_event(
        state,
        event(
            EventType.DECOMPOSITION_STARTED,
            state.version + 1,
            work_item_id=item_id,
            generation=state.work_item(item_id).current_generation,
            payload={},
        ),
        SPEC,
    )


def _open_child(state, *, child_id: str, parent_id: str):
    return reduce_event(
        state,
        event(
            EventType.WORK_ITEM_OPENED,
            state.version + 1,
            work_item_id=child_id,
            generation=1,
            payload={"work_kind": WorkItemKind.LEAF.value, "parent_ids": [parent_id]},
        ),
        SPEC,
    )


def _cycle_snapshot(cycle_id: str):
    return reduce_event(
        None,
        event(
            EventType.CYCLE_CREATED,
            1,
            cycle_id=cycle_id,
            payload={
                "config_snapshot_ref": "config://v1",
                "config_snapshot_hash": "a" * 64,
                "canon_snapshot_ref": "kg://snapshot/1",
                "canon_snapshot_hash": "b" * 64,
            },
        ),
        SPEC,
    )


def test_envelope_identities_are_nfc_normalized_before_state_comparison() -> None:
    nfd = "e\u0301"
    envelope = event(
        EventType.EFFECT_STARTED,
        1,
        cycle_id=nfd,
        work_item_id=nfd,
        effect_id=nfd,
        generation=1,
        payload={"attempt": 1},
    )

    assert envelope.cycle_id == "é"
    assert envelope.stream_id == "é"
    assert envelope.work_item_id == "é"
    assert envelope.effect_id == "é"
    nfd_state = _cycle_snapshot(nfd)
    nfc_state = _cycle_snapshot("é")
    assert nfd_state == nfc_state
    assert state_hash(nfd_state) == state_hash(nfc_state)


def test_semantic_branch_events_must_match_work_item_kind() -> None:
    leaf = _anchor(
        open_work_item(start_cycle(create_cycle()), kind=WorkItemKind.LEAF, item_id="leaf"),
        item_id="leaf",
    )
    with pytest.raises(InvalidTransitionError, match="CONTAINER"):
        _start_decomposition(leaf, item_id="leaf")

    container = _anchor(
        open_work_item(
            start_cycle(create_cycle()), kind=WorkItemKind.CONTAINER, item_id="container"
        ),
        item_id="container",
    )
    with pytest.raises(InvalidTransitionError, match="LEAF"):
        reduce_event(
            container,
            event(
                EventType.ATOMICITY_ACCEPTED,
                container.version + 1,
                work_item_id="container",
                generation=1,
                payload=guard_payload(),
            ),
            SPEC,
        )


def test_child_open_requires_open_decomposing_container_parent() -> None:
    leaf = open_work_item(start_cycle(create_cycle()), kind=WorkItemKind.LEAF, item_id="leaf")
    with pytest.raises(InvalidTransitionError, match="CONTAINER"):
        _open_child(leaf, child_id="child", parent_id="leaf")

    container = _anchor(
        open_work_item(
            start_cycle(create_cycle()), kind=WorkItemKind.CONTAINER, item_id="parent"
        ),
        item_id="parent",
    )
    with pytest.raises(InvalidTransitionError, match="DECOMPOSING"):
        _open_child(container, child_id="too-early", parent_id="parent")

    decomposing = _start_decomposition(container, item_id="parent")
    decomposing = _open_child(decomposing, child_id="child-1", parent_id="parent")
    decomposed = reduce_event(
        decomposing,
        event(
            EventType.CHILDREN_ATTACHED,
            decomposing.version + 1,
            work_item_id="parent",
            generation=1,
            payload=guard_payload(child_ids=["child-1"]),
        ),
        SPEC,
    )
    with pytest.raises(InvalidTransitionError, match="DECOMPOSING"):
        _open_child(decomposed, child_id="child-2", parent_id="parent")


def test_child_open_rejects_superseded_parent() -> None:
    parent = _start_decomposition(
        _anchor(
            open_work_item(
                start_cycle(create_cycle()), kind=WorkItemKind.CONTAINER, item_id="parent"
            ),
            item_id="parent",
        ),
        item_id="parent",
    )
    parent = reduce_event(
        parent,
        event(
            EventType.WORK_ITEM_SUPERSEDED,
            parent.version + 1,
            work_item_id="parent",
            generation=1,
            payload={"reason": "replaced"},
        ),
        SPEC,
    )

    with pytest.raises(InvalidTransitionError, match="OPEN"):
        _open_child(parent, child_id="child", parent_id="parent")


def test_realization_requires_artifact_realize_capability_but_not_fixed_provider() -> None:
    base = make_contracted(open_work_item(start_cycle(create_cycle())))
    wrong = queue_running_effect(
        dispatch_work_item(base), capability="knowledge.acquire", provider="Prometheus"
    )
    with pytest.raises(InvalidTransitionError, match="artifact.realize"):
        reduce_event(
            wrong,
            event(
                EventType.REALIZATION_STARTED,
                wrong.version + 1,
                work_item_id="work-1",
                effect_id="effect-1",
                generation=1,
                payload={"effect_id": "effect-1"},
            ),
            SPEC,
        )

    alternate = queue_running_effect(
        dispatch_work_item(base), capability="artifact.realize", provider="AlternateProvider"
    )
    alternate = reduce_event(
        alternate,
        event(
            EventType.REALIZATION_STARTED,
            alternate.version + 1,
            work_item_id="work-1",
            effect_id="effect-1",
            generation=1,
            payload={"effect_id": "effect-1"},
        ),
        SPEC,
    )
    assert alternate.work_item("work-1").realization is RealizationStatus.RUNNING


def test_materialization_requires_the_effect_that_started_realization() -> None:
    state = start_bound_effect(make_contracted(open_work_item(start_cycle(create_cycle()))))
    state = queue_running_effect(state, effect_id="effect-2")
    state = reduce_event(
        state,
        event(
            EventType.EFFECT_SUCCEEDED,
            state.version + 1,
            work_item_id="work-1",
            effect_id="effect-2",
            generation=1,
            payload={"result_ref": "result://2", "result_hash": "2" * 64},
        ),
        SPEC,
    )

    with pytest.raises(SubjectMismatchError, match="active realization effect"):
        reduce_event(
            state,
            event(
                EventType.ARTIFACT_MATERIALIZED,
                state.version + 1,
                work_item_id="work-1",
                effect_id="effect-2",
                generation=1,
                payload=guard_payload(
                    effect_id="effect-2",
                    artifact_ref="artifact://2",
                    artifact_hash="3" * 64,
                ),
            ),
            SPEC,
        )


def test_invalidation_requires_a_current_generation_target() -> None:
    state = start_bound_effect(make_contracted(open_work_item(start_cycle(create_cycle()))))
    state = reduce_event(
        state,
        event(
            EventType.EFFECT_SUCCEEDED,
            state.version + 1,
            work_item_id="work-1",
            effect_id="effect-1",
            generation=1,
            payload={"result_ref": "result://1", "result_hash": "4" * 64},
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
                effect_id="effect-1",
                artifact_ref="artifact://real",
                artifact_hash="5" * 64,
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
                generation=2,
                payload={"artifact_ref": "artifact://ghost", "reason": "drift"},
            ),
            SPEC,
        )

    evidence_state = make_contracted(open_work_item(start_cycle(create_cycle())))
    evidence_state = reduce_event(
        evidence_state,
        event(
            EventType.VERIFICATION_REQUESTED,
            evidence_state.version + 1,
            work_item_id="work-1",
            generation=1,
            payload={"oracle_ref": "oracle://1"},
        ),
        SPEC,
    )
    with pytest.raises(SubjectMismatchError, match="evidence_ref"):
        reduce_event(
            evidence_state,
            event(
                EventType.EVIDENCE_INVALIDATED,
                evidence_state.version + 1,
                work_item_id="work-1",
                generation=2,
                payload={"evidence_ref": "evidence://ghost", "reason": "stale"},
            ),
            SPEC,
        )

    evidence_state = reduce_event(
        evidence_state,
        event(
            EventType.EVIDENCE_INVALIDATED,
            evidence_state.version + 1,
            work_item_id="work-1",
            generation=2,
            payload={"evidence_ref": "evidence-1", "reason": "stale"},
        ),
        SPEC,
    )
    assert evidence_state.work_item("work-1").assurance is AssuranceStatus.UNASSESSED
