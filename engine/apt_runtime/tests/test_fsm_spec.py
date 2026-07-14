from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from engine.apt_runtime.domain.fsm_spec import FsmSpec, SpecValidationError, load_default_spec


RUNTIME_SPEC = Path(__file__).parents[1] / "specs" / "apt_engine_fsm.v1.json"


def test_normative_companion_declares_six_regions_and_three_aggregates() -> None:
    spec = load_default_spec()

    assert spec.region_count == 6
    assert spec.aggregate_count == 3
    assert len(spec.machines) == 6
    assert sum(len(machine.states) for machine in spec.machines) == 36
    assert spec.expanded_transition_count == 114
    assert len(spec.spec_hash) == 64


def test_every_declared_state_has_a_witness_path_from_initial_state() -> None:
    spec = load_default_spec()

    for machine in spec.machines:
        witnesses = spec.reachability_witnesses(machine.name)
        assert set(witnesses) == set(machine.states)
        assert witnesses[machine.initial_state] == ()
        for state, path in witnesses.items():
            cursor = machine.initial_state
            for transition in path:
                assert transition.source == cursor
                cursor = transition.target
            assert cursor == state


def test_every_declared_transition_is_selected_by_its_event_and_selector() -> None:
    spec = load_default_spec()

    for transition in spec.expanded_transitions:
        matches = spec.matching_transitions(
            transition.machine_name,
            transition.source,
            transition.event_type,
            transition.event_match,
        )
        assert matches == (transition,)


def test_every_undeclared_region_state_event_contract_combination_is_rejected() -> None:
    spec = load_default_spec()

    for contract in spec.event_contracts:
        if contract.kind != "TRANSITION":
            continue
        for machine in spec.machines:
            if machine.aggregate != contract.subject:
                continue
            for state in machine.states:
                matches = spec.matching_transitions(
                    machine.name,
                    state,
                    contract.event_type,
                    contract.event_match,
                )
                declared = tuple(
                    transition
                    for transition in spec.expanded_transitions
                    if transition.machine_name == machine.name
                    and transition.source == state
                    and transition.event_type == contract.event_type
                    and transition.selector_matches(contract.event_match)
                )
                assert matches == declared


def test_loader_rejects_ambiguous_transition_instead_of_last_write_wins() -> None:
    raw = json.loads(RUNTIME_SPEC.read_text(encoding="utf-8"))
    duplicate = copy.deepcopy(raw["machines"][0]["transitions"][0])
    duplicate["id"] = "cycle.start.ambiguous"
    duplicate["to"] = "WAITING"
    raw["machines"][0]["transitions"].append(duplicate)

    with pytest.raises(SpecValidationError, match="ambiguous"):
        FsmSpec.from_mapping(raw)


def test_loader_rejects_event_contract_missing_a_required_region_transition() -> None:
    raw = json.loads(RUNTIME_SPEC.read_text(encoding="utf-8"))
    realization = next(
        machine for machine in raw["machines"] if machine["name"] == "work_item.realization"
    )
    realization["transitions"] = [
        row for row in realization["transitions"] if row["event_type"] != "ContractAccepted"
    ]

    with pytest.raises(SpecValidationError, match="required region"):
        FsmSpec.from_mapping(raw)


def test_loader_rejects_duplicate_transition_definition_id_within_a_machine() -> None:
    raw = json.loads(RUNTIME_SPEC.read_text(encoding="utf-8"))
    transitions = raw["machines"][0]["transitions"]
    transitions[1]["id"] = transitions[0]["id"]

    with pytest.raises(SpecValidationError, match="transition IDs"):
        FsmSpec.from_mapping(raw)


def test_loader_rejects_unknown_transition_field_instead_of_dropping_guard() -> None:
    raw = json.loads(RUNTIME_SPEC.read_text(encoding="utf-8"))
    transition = next(
        row
        for machine in raw["machines"]
        for row in machine["transitions"]
        if row.get("guard") is not None
    )
    transition["gaurd"] = transition.pop("guard")

    with pytest.raises(SpecValidationError, match="unknown field"):
        FsmSpec.from_mapping(raw)


def test_loader_rejects_unknown_transition_kind() -> None:
    raw = json.loads(RUNTIME_SPEC.read_text(encoding="utf-8"))
    raw["machines"][0]["transitions"][0]["kind"] = "MAGIC"

    with pytest.raises(SpecValidationError, match="transition kind"):
        FsmSpec.from_mapping(raw)


def test_loader_rejects_transition_missing_required_guard_field() -> None:
    raw = json.loads(RUNTIME_SPEC.read_text(encoding="utf-8"))
    raw["machines"][0]["transitions"][0].pop("guard")

    with pytest.raises(SpecValidationError, match="missing field"):
        FsmSpec.from_mapping(raw)


def test_loader_rejects_transition_contract_without_a_required_region() -> None:
    raw = json.loads(RUNTIME_SPEC.read_text(encoding="utf-8"))
    contract = next(
        row for row in raw["event_contracts"] if row["event_type"] == "CycleResumed"
    )
    contract["required_regions"] = []
    cycle = next(machine for machine in raw["machines"] if machine["name"] == "cycle.lifecycle")
    cycle["transitions"] = [
        row for row in cycle["transitions"] if row["event_type"] != "CycleResumed"
    ]

    with pytest.raises(SpecValidationError, match="required region"):
        FsmSpec.from_mapping(raw)


def test_loader_rejects_missing_optional_region_transition() -> None:
    raw = json.loads(RUNTIME_SPEC.read_text(encoding="utf-8"))
    realization = next(
        machine for machine in raw["machines"] if machine["name"] == "work_item.realization"
    )
    realization["transitions"] = [
        row for row in realization["transitions"] if row["id"] != "realization.correct.anchor"
    ]

    with pytest.raises(SpecValidationError, match="optional region"):
        FsmSpec.from_mapping(raw)


def test_loader_rejects_runtime_machine_state_registry_drift() -> None:
    raw = json.loads(RUNTIME_SPEC.read_text(encoding="utf-8"))
    cycle = next(machine for machine in raw["machines"] if machine["name"] == "cycle.lifecycle")
    cycle["states"] = ["ACTIVE_X" if state == "ACTIVE" else state for state in cycle["states"]]
    for transition in cycle["transitions"]:
        transition["from"] = [
            "ACTIVE_X" if state == "ACTIVE" else state for state in transition["from"]
        ]
        if transition["to"] == "ACTIVE":
            transition["to"] = "ACTIVE_X"

    with pytest.raises(SpecValidationError, match="machine registry"):
        FsmSpec.from_mapping(raw)


def test_runtime_spec_strings_are_nfc_normalized_consistently_with_spec_hash() -> None:
    nfd_raw = json.loads(RUNTIME_SPEC.read_text(encoding="utf-8"))
    nfc_raw = copy.deepcopy(nfd_raw)
    nfd_raw["source"]["path"] = "e\u0301"
    nfc_raw["source"]["path"] = "é"

    nfd_spec = FsmSpec.from_mapping(nfd_raw)
    nfc_spec = FsmSpec.from_mapping(nfc_raw)

    assert nfd_spec.spec_hash == nfc_spec.spec_hash
    assert nfd_spec.source["path"] == "é"


def test_terminal_states_have_no_outgoing_transition() -> None:
    spec = load_default_spec()

    for machine in spec.machines:
        outgoing_sources = {transition.source for transition in machine.transitions}
        assert not (set(machine.terminal_states) & outgoing_sources)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda raw: raw.__setitem__("format_version", 999), "format_version"),
        (lambda raw: raw.__setitem__("spec_id", "other_fsm"), "spec_id"),
        (
            lambda raw: raw["canonical_encoding"].__setitem__("hash_algorithm", "MD5"),
            "canonical_encoding",
        ),
        (
            lambda raw: raw["machines"][0].__setitem__("state_attribute", "missing"),
            "machine registry",
        ),
        (
            lambda raw: raw["event_contracts"][0].__setitem__("generation_policy", "MAGIC"),
            "generation_policy",
        ),
        (
            lambda raw: raw["event_contracts"][0].__setitem__("event_type", "UnknownFact"),
            "event_type",
        ),
    ],
)
def test_loader_rejects_runtime_incompatible_profiles(mutation, message: str) -> None:
    raw = json.loads(RUNTIME_SPEC.read_text(encoding="utf-8"))
    mutation(raw)

    with pytest.raises(SpecValidationError, match=message):
        FsmSpec.from_mapping(raw)
