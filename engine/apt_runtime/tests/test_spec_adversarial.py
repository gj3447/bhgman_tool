from __future__ import annotations

import json
from pathlib import Path

import pytest

from engine.apt_runtime.domain.canonical import CanonicalEncodingError, canonical_json_bytes
from engine.apt_runtime.domain.fsm_spec import (
    FsmSpec,
    SpecValidationError,
    load_default_spec,
)


RUNTIME_SPEC = Path(__file__).parents[1] / "specs" / "apt_engine_fsm.v1.json"


def test_optional_region_contract_covers_every_active_noninitial_source_state() -> None:
    raw = json.loads(RUNTIME_SPEC.read_text(encoding="utf-8"))
    realization = next(
        machine for machine in raw["machines"] if machine["name"] == "work_item.realization"
    )
    transition = next(
        row for row in realization["transitions"] if row["id"] == "realization.correct.anchor"
    )
    transition["from"].remove("READY")

    with pytest.raises(SpecValidationError, match="optional region.*READY"):
        FsmSpec.from_mapping(raw)


def test_runtime_profile_rejects_missing_selector_partition() -> None:
    raw = json.loads(RUNTIME_SPEC.read_text(encoding="utf-8"))
    raw["event_contracts"] = [
        row for row in raw["event_contracts"] if row["id"] != "event.work.closed.container"
    ]
    lifecycle = next(
        machine for machine in raw["machines"] if machine["name"] == "work_item.lifecycle"
    )
    lifecycle["transitions"] = [
        row for row in lifecycle["transitions"] if row["id"] != "work.close.container"
    ]

    with pytest.raises(SpecValidationError, match="selector partition"):
        FsmSpec.from_mapping(raw)


def test_runtime_profile_rejects_event_contract_region_drift() -> None:
    raw = json.loads(RUNTIME_SPEC.read_text(encoding="utf-8"))
    contract = next(row for row in raw["event_contracts"] if row["id"] == "event.semantic.anchor")
    contract["required_regions"].append("work_item.realization")
    realization = next(
        machine for machine in raw["machines"] if machine["name"] == "work_item.realization"
    )
    realization["transitions"].append(
        {
            "id": "realization.anchor.drift",
            "from": ["NOT_READY"],
            "to": "READY",
            "event_type": "AnchorAccepted",
            "event_match": {},
            "guard": None,
            "kind": "FORWARD",
        }
    )

    with pytest.raises(SpecValidationError, match="contract shape"):
        FsmSpec.from_mapping(raw)


@pytest.mark.parametrize(
    "value",
    ["\ud800", 10**5000],
    ids=("unpaired-surrogate", "oversized-integer"),
)
def test_canonical_encoding_normalizes_host_failures(value: object) -> None:
    with pytest.raises(CanonicalEncodingError, match="canonical JSON encoding failed"):
        canonical_json_bytes(value)


def test_loader_normalizes_invalid_utf8(tmp_path: Path) -> None:
    invalid_spec = tmp_path / "invalid.json"
    invalid_spec.write_bytes(b"\xff")

    with pytest.raises(SpecValidationError, match="invalid FSM JSON"):
        load_default_spec(invalid_spec)


def test_loader_normalizes_json_integer_limit_failure(tmp_path: Path) -> None:
    invalid_spec = tmp_path / "invalid.json"
    invalid_spec.write_text('{"number":' + "9" * 5000 + "}", encoding="utf-8")

    with pytest.raises(SpecValidationError, match="invalid FSM JSON"):
        load_default_spec(invalid_spec)


def test_loader_normalizes_recursive_mapping_failure() -> None:
    raw: dict[str, object] = {}
    raw["recursive"] = raw

    with pytest.raises(SpecValidationError, match="canonically hashed"):
        FsmSpec.from_mapping(raw)
