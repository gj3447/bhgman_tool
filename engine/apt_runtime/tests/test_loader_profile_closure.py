from __future__ import annotations

import json
from pathlib import Path

import pytest

from engine.apt_runtime.domain.fsm_spec import FsmSpec, SpecValidationError


RUNTIME_SPEC = Path(__file__).parents[1] / "specs" / "apt_engine_fsm.v1.json"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("mapping_keys", "INSERTION_ORDER"),
        ("sequence_order", "ARBITRARY"),
        ("separators", "PRETTY_PRINT"),
        ("timestamps", "LOCAL_TIME"),
        ("excluded_state_fields", ["effects"]),
    ],
)
def test_loader_pins_the_complete_canonical_profile(field: str, value: object) -> None:
    raw = json.loads(RUNTIME_SPEC.read_text(encoding="utf-8"))
    raw["canonical_encoding"][field] = value

    with pytest.raises(SpecValidationError, match="canonical_encoding"):
        FsmSpec.from_mapping(raw)


def test_loader_pins_declared_reducer_semantics() -> None:
    raw = json.loads(RUNTIME_SPEC.read_text(encoding="utf-8"))
    raw["reducer_semantics"]["undeclared_transition"] = "ALLOW"

    with pytest.raises(SpecValidationError, match="reducer_semantics"):
        FsmSpec.from_mapping(raw)


def test_loader_rejects_empty_transition_sources() -> None:
    raw = json.loads(RUNTIME_SPEC.read_text(encoding="utf-8"))
    raw["machines"][0]["transitions"].append(
        {
            "id": "event.cycle.started",
            "from": [],
            "to": "ACTIVE",
            "event_type": "CycleStarted",
            "event_match": {},
            "guard": "cycle_startable",
            "kind": "FORWARD",
        }
    )

    with pytest.raises(SpecValidationError, match="from.*at least one"):
        FsmSpec.from_mapping(raw)


def test_loader_pins_required_payload_contracts() -> None:
    raw = json.loads(RUNTIME_SPEC.read_text(encoding="utf-8"))
    contract = next(row for row in raw["event_contracts"] if row["id"] == "event.cycle.failed")
    contract["required_payload"] = []

    with pytest.raises(SpecValidationError, match="execution profile"):
        FsmSpec.from_mapping(raw)


def test_loader_rejects_reducer_incompatible_transition_target() -> None:
    raw = json.loads(RUNTIME_SPEC.read_text(encoding="utf-8"))
    realization = next(
        machine for machine in raw["machines"] if machine["name"] == "work_item.realization"
    )
    transition = next(row for row in realization["transitions"] if row["id"] == "realization.ready")
    transition["to"] = "RUNNING"

    with pytest.raises(SpecValidationError, match="execution profile"):
        FsmSpec.from_mapping(raw)


@pytest.mark.parametrize(
    ("section", "field"),
    [("event_contracts", "authorization_policy"), ("machines", "entry_guard")],
)
def test_loader_rejects_unknown_structural_fields(section: str, field: str) -> None:
    raw = json.loads(RUNTIME_SPEC.read_text(encoding="utf-8"))
    raw[section][0][field] = "MUST_PASS"

    with pytest.raises(SpecValidationError, match="unknown field"):
        FsmSpec.from_mapping(raw)
