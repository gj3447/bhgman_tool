from __future__ import annotations

from dataclasses import replace

import pytest

from engine.apt_runtime.domain.events import EventSchemaError, EventType
from engine.apt_runtime.domain.reducer import reduce_event
from engine.apt_runtime.tests.test_reducer import (
    SPEC,
    create_cycle,
    event,
    guard_payload,
    start_cycle,
)


def test_work_event_rejects_undeclared_payload_effect_identity() -> None:
    state = start_cycle(create_cycle())
    state = reduce_event(
        state,
        event(
            EventType.WORK_ITEM_OPENED,
            state.version + 1,
            work_item_id="work-1",
            generation=1,
            payload={"work_kind": "LEAF", "parent_ids": []},
        ),
        SPEC,
    )

    with pytest.raises(EventSchemaError, match="unexpected payload"):
        reduce_event(
            state,
            event(
                EventType.ANCHOR_ACCEPTED,
                state.version + 1,
                work_item_id="work-1",
                generation=1,
                payload=guard_payload(effect_id="ghost"),
            ),
            SPEC,
        )


@pytest.mark.parametrize(
    "created_at",
    [
        "2026-07-14T09:00:00+09:00",
        "2026-07-14T00:00:00+00:00",
        "2026-07-14 00:00:00Z",
        "20260714T000000Z",
    ],
)
def test_event_envelope_requires_extended_rfc3339_utc_z(created_at: str) -> None:
    envelope = event(EventType.CYCLE_RESUMED, 1, payload={})

    with pytest.raises(EventSchemaError, match="UTC.*Z"):
        replace(envelope, created_at=created_at)


def test_effect_lease_expiry_requires_extended_rfc3339_utc_z() -> None:
    state = start_cycle(create_cycle())
    state = reduce_event(
        state,
        event(
            EventType.EFFECT_QUEUED,
            state.version + 1,
            effect_id="effect-1",
            payload={
                "capability": "knowledge.acquire",
                "provider": "Prometheus",
                "risk_class": "READ_ONLY",
                "idempotency_key": "idem-1",
                "input_ref": "need://1",
                "input_hash": "a" * 64,
            },
        ),
        SPEC,
    )

    with pytest.raises(EventSchemaError, match="UTC.*Z"):
        reduce_event(
            state,
            event(
                EventType.EFFECT_LEASED,
                state.version + 1,
                effect_id="effect-1",
                payload={
                    "lease_owner": "worker-1",
                    "lease_expiry": "2026-07-14T09:00:00+09:00",
                },
            ),
            SPEC,
        )
