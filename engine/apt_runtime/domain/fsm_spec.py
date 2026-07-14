"""Immutable loader and query surface for the APT runtime FSM specification.

The JSON companion is the transition authority for Slice 0.  This module deliberately
does not infer missing edges: malformed, incomplete, or ambiguous specifications fail
at load time so the reducer cannot accidentally acquire last-write-wins semantics.

# KG: apt-tpa-legion-engine-canon-2026-06-12
"""

from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from .canonical import canonical_sha256 as canonical_hash
from .canonical import deep_freeze, normalize_text
from .spec_profile import validate_execution_profile, validate_runtime_profile


class SpecValidationError(ValueError):
    """Raised when an FSM specification or lookup is incomplete or ambiguous."""


JsonMapping = Mapping[str, object]
_TRANSITION_FIELDS = frozenset({"id", "event_type", "from", "to", "event_match", "guard", "kind"})
_EVENT_CONTRACT_FIELDS = frozenset(
    {
        "id",
        "event_type",
        "subject",
        "kind",
        "event_match",
        "required_regions",
        "optional_regions",
        "generation_policy",
        "required_payload",
    }
)
_MACHINE_FIELDS = frozenset(
    {
        "name",
        "aggregate",
        "state_attribute",
        "initial_state",
        "states",
        "terminal_states",
        "transitions",
    }
)
_TRANSITION_KINDS = frozenset(
    {"CORRECTION", "FAILURE", "FORWARD", "QUIESCENT", "RECOVERY", "TERMINAL", "WAIT"}
)


def _freeze_json(value: object) -> object:
    return deep_freeze(value)


def _selector_matches(selector: Mapping[str, object], payload: Mapping[str, object]) -> bool:
    return all(
        key in payload and _freeze_json(payload[key]) == expected
        for key, expected in selector.items()
    )


def _selectors_overlap(left: Mapping[str, object], right: Mapping[str, object]) -> bool:
    """Return whether at least one payload can satisfy both partial selectors."""

    shared_keys = left.keys() & right.keys()
    return all(left[key] == right[key] for key in shared_keys)


def _require_mapping(value: object, location: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise SpecValidationError(f"{location} must be a mapping")
    if not all(isinstance(key, str) for key in value):
        raise SpecValidationError(f"{location} keys must be strings")
    return value


def _require_sequence(value: object, location: str) -> Sequence[object]:
    if not isinstance(value, (list, tuple)):
        raise SpecValidationError(f"{location} must be a sequence")
    return value


def _require_string(value: object, location: str) -> str:
    if not isinstance(value, str) or not value:
        raise SpecValidationError(f"{location} must be a non-empty string")
    return normalize_text(value)


def _require_integer(value: object, location: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise SpecValidationError(f"{location} must be an integer")
    return value


def _require_exact_fields(
    value: Mapping[str, object], allowed: frozenset[str], location: str
) -> None:
    unknown = set(value) - allowed
    if unknown:
        raise SpecValidationError(f"{location} has unknown field(s): {sorted(unknown)!r}")
    missing = allowed - set(value)
    if missing:
        raise SpecValidationError(f"{location} has missing field(s): {sorted(missing)!r}")


def _string_tuple(value: object, location: str) -> tuple[str, ...]:
    values = tuple(
        _require_string(item, f"{location}[{index}]")
        for index, item in enumerate(_require_sequence(value, location))
    )
    if len(values) != len(set(values)):
        raise SpecValidationError(f"{location} contains duplicate values")
    return values


def _selector(value: object, location: str) -> Mapping[str, object]:
    selector = _require_mapping(value, location)
    return _freeze_json(selector)  # type: ignore[return-value]


@dataclass(frozen=True, slots=True)
class EventContract:
    """A typed event contract and its partial-payload selector."""

    id: str
    event_type: str
    subject: str
    kind: str
    event_match: Mapping[str, object]
    required_regions: tuple[str, ...]
    optional_regions: tuple[str, ...]
    generation_policy: str
    required_payload: tuple[str, ...]

    def selector_matches(self, payload: Mapping[str, object]) -> bool:
        return _selector_matches(self.event_match, payload)


@dataclass(frozen=True, slots=True)
class Transition:
    """One expanded, single-source transition from the normative table."""

    machine_name: str
    source: str
    target: str
    event_type: str
    event_match: Mapping[str, object]
    guard: str | None
    kind: str
    id: str

    def selector_matches(self, payload: Mapping[str, object]) -> bool:
        return _selector_matches(self.event_match, payload)


@dataclass(frozen=True, slots=True)
class MachineSpec:
    """One orthogonal state-machine region with expanded transitions."""

    name: str
    aggregate: str
    state_attribute: str
    initial_state: str
    states: tuple[str, ...]
    terminal_states: tuple[str, ...]
    transitions: tuple[Transition, ...]


@dataclass(frozen=True, slots=True)
class FsmSpec:
    """Validated, immutable projection of ``apt_engine_fsm.v1.json``."""

    format_version: int
    spec_id: str
    spec_version: str
    event_schema_versions: tuple[str, ...]
    status: str
    source: Mapping[str, object]
    kg_refs: tuple[str, ...]
    aggregate_count: int
    region_count: int
    transition_authority: str
    canonical_encoding: Mapping[str, object]
    reducer_semantics: Mapping[str, object]
    event_contracts: tuple[EventContract, ...]
    machines: tuple[MachineSpec, ...]
    invariants: tuple[str, ...]
    provisional_resolutions: tuple[str, ...]
    spec_hash: str
    metadata: Mapping[str, object]

    @classmethod
    def from_mapping(cls, raw: Mapping[str, object]) -> FsmSpec:
        root = _require_mapping(raw, "spec")
        try:
            spec_hash = canonical_hash(root)
        except (TypeError, ValueError, RecursionError) as exc:
            raise SpecValidationError(f"spec cannot be canonically hashed: {exc}") from exc

        contracts = _parse_event_contracts(root.get("event_contracts"))
        machines = _parse_machines(root.get("machines"))
        metadata = {
            key: value for key, value in root.items() if key not in {"event_contracts", "machines"}
        }

        instance = cls(
            format_version=_require_integer(root.get("format_version"), "format_version"),
            spec_id=_require_string(root.get("spec_id"), "spec_id"),
            spec_version=_require_string(root.get("spec_version"), "spec_version"),
            event_schema_versions=_string_tuple(
                root.get("event_schema_versions"), "event_schema_versions"
            ),
            status=_require_string(root.get("status"), "status"),
            source=_freeze_json(_require_mapping(root.get("source"), "source")),  # type: ignore[arg-type]
            kg_refs=_string_tuple(root.get("kg_refs"), "kg_refs"),
            aggregate_count=_require_integer(root.get("aggregate_count"), "aggregate_count"),
            region_count=_require_integer(root.get("region_count"), "region_count"),
            transition_authority=_require_string(
                root.get("transition_authority"), "transition_authority"
            ),
            canonical_encoding=_freeze_json(
                _require_mapping(root.get("canonical_encoding"), "canonical_encoding")
            ),  # type: ignore[arg-type]
            reducer_semantics=_freeze_json(
                _require_mapping(root.get("reducer_semantics"), "reducer_semantics")
            ),  # type: ignore[arg-type]
            event_contracts=contracts,
            machines=machines,
            invariants=_string_tuple(root.get("invariants"), "invariants"),
            provisional_resolutions=_string_tuple(
                root.get("provisional_resolutions"), "provisional_resolutions"
            ),
            spec_hash=spec_hash,
            metadata=_freeze_json(metadata),  # type: ignore[arg-type]
        )
        instance._validate()
        return instance

    @property
    def expanded_transitions(self) -> tuple[Transition, ...]:
        return tuple(transition for machine in self.machines for transition in machine.transitions)

    @property
    def expanded_transition_count(self) -> int:
        return len(self.expanded_transitions)

    def machine(self, name: str) -> MachineSpec:
        matches = tuple(machine for machine in self.machines if machine.name == name)
        if len(matches) != 1:
            raise SpecValidationError(
                f"machine lookup for {name!r} expected one match, found {len(matches)}"
            )
        return matches[0]

    def matching_event_contract(
        self, event_type: str, payload: Mapping[str, object]
    ) -> EventContract:
        matches = tuple(
            contract
            for contract in self.event_contracts
            if contract.event_type == event_type and contract.selector_matches(payload)
        )
        if len(matches) != 1:
            raise SpecValidationError(
                f"event contract lookup for {event_type!r} is invalid or ambiguous: "
                f"found {len(matches)} matches"
            )
        return matches[0]

    def matching_transitions(
        self,
        machine_name: str,
        state: str,
        event_type: str,
        payload: Mapping[str, object],
    ) -> tuple[Transition, ...]:
        machine = self.machine(machine_name)
        return tuple(
            transition
            for transition in machine.transitions
            if transition.source == state
            and transition.event_type == event_type
            and transition.selector_matches(payload)
        )

    def reachability_witnesses(self, machine_name: str) -> Mapping[str, tuple[Transition, ...]]:
        machine = self.machine(machine_name)
        witnesses: dict[str, tuple[Transition, ...]] = {machine.initial_state: ()}
        pending: deque[str] = deque((machine.initial_state,))

        while pending:
            source = pending.popleft()
            prefix = witnesses[source]
            for transition in machine.transitions:
                if transition.source != source or transition.target in witnesses:
                    continue
                witnesses[transition.target] = (*prefix, transition)
                pending.append(transition.target)

        return MappingProxyType(witnesses)

    def _validate(self) -> None:
        try:
            validate_runtime_profile(self)
        except ValueError as exc:
            raise SpecValidationError(str(exc)) from exc
        machine_names = tuple(machine.name for machine in self.machines)
        if len(machine_names) != len(set(machine_names)):
            raise SpecValidationError("machine names must be globally unique")
        if self.region_count != len(self.machines):
            raise SpecValidationError(
                f"region_count declares {self.region_count}, found {len(self.machines)} machines"
            )

        aggregates = {machine.aggregate for machine in self.machines}
        if self.aggregate_count != len(aggregates):
            raise SpecValidationError(
                f"aggregate_count declares {self.aggregate_count}, found {len(aggregates)}"
            )

        contract_ids = tuple(contract.id for contract in self.event_contracts)
        if len(contract_ids) != len(set(contract_ids)):
            raise SpecValidationError("event-contract IDs must be globally unique")
        transition_ids = _transition_definition_ids(self.machines)
        if len(transition_ids) != len(set(transition_ids)):
            raise SpecValidationError("transition IDs must be globally unique")
        overlap = set(contract_ids) & set(transition_ids)
        if overlap:
            raise SpecValidationError(
                f"transition and event-contract IDs collide: {sorted(overlap)!r}"
            )

        _validate_event_contract_selectors(self.event_contracts)
        # Contract completeness is the cross-region authority boundary.  Check it
        # before local graph reachability so a removed mandatory edge is reported as
        # the contract violation that caused the downstream unreachable states.
        self._validate_contract_region_bindings()
        for machine in self.machines:
            _validate_machine(machine)
        try:
            validate_execution_profile(self)
        except ValueError as exc:
            raise SpecValidationError(str(exc)) from exc

    def _validate_contract_region_bindings(self) -> None:
        machines_by_name = {machine.name: machine for machine in self.machines}

        for contract in self.event_contracts:
            authorized_regions = contract.required_regions + contract.optional_regions
            if len(authorized_regions) != len(set(authorized_regions)):
                raise SpecValidationError(
                    f"event contract {contract.id!r} repeats a region binding"
                )
            for region_name in authorized_regions:
                machine = machines_by_name.get(region_name)
                if machine is None:
                    raise SpecValidationError(
                        f"event contract {contract.id!r} references unknown region {region_name!r}"
                    )
                if machine.aggregate != contract.subject:
                    raise SpecValidationError(
                        f"event contract {contract.id!r} subject {contract.subject!r} "
                        f"does not own region {region_name!r}"
                    )

            if contract.kind == "INITIALIZER":
                if authorized_regions:
                    raise SpecValidationError(
                        f"initializer event contract {contract.id!r} cannot bind transitions"
                    )
                continue
            if contract.kind != "TRANSITION":
                raise SpecValidationError(
                    f"event contract {contract.id!r} has unknown kind {contract.kind!r}"
                )
            if not contract.required_regions:
                raise SpecValidationError(
                    f"transition event contract {contract.id!r} requires at least one "
                    "required region"
                )

            for region_name in contract.required_regions:
                machine = machines_by_name[region_name]
                declared = tuple(
                    transition
                    for transition in machine.transitions
                    if transition.event_type == contract.event_type
                    and transition.selector_matches(contract.event_match)
                )
                if not declared:
                    raise SpecValidationError(
                        f"event contract {contract.id!r} is missing a required region "
                        f"transition for {region_name!r}"
                    )
            for region_name in contract.optional_regions:
                machine = machines_by_name[region_name]
                declared = tuple(
                    transition
                    for transition in machine.transitions
                    if transition.event_type == contract.event_type
                    and transition.selector_matches(contract.event_match)
                )
                if not declared:
                    raise SpecValidationError(
                        f"event contract {contract.id!r} is missing an optional region "
                        f"transition for {region_name!r}"
                    )
                active_sources = (
                    set(machine.states) - {machine.initial_state} - set(machine.terminal_states)
                )
                covered_sources = {transition.source for transition in declared}
                missing_sources = active_sources - covered_sources
                if missing_sources:
                    raise SpecValidationError(
                        f"event contract {contract.id!r} optional region {region_name!r} "
                        f"is missing active source state(s): {sorted(missing_sources)!r}"
                    )

        for machine in self.machines:
            for transition in machine.transitions:
                contracts = tuple(
                    contract
                    for contract in self.event_contracts
                    if contract.kind == "TRANSITION"
                    and contract.subject == machine.aggregate
                    and contract.event_type == transition.event_type
                    and _selectors_overlap(contract.event_match, transition.event_match)
                    and machine.name in contract.required_regions + contract.optional_regions
                )
                if len(contracts) != 1:
                    raise SpecValidationError(
                        f"transition {transition.id!r} in {machine.name!r} must bind "
                        f"exactly one event contract, found {len(contracts)}"
                    )


def _parse_event_contracts(value: object) -> tuple[EventContract, ...]:
    rows = _require_sequence(value, "event_contracts")
    contracts: list[EventContract] = []
    for index, value_row in enumerate(rows):
        location = f"event_contracts[{index}]"
        row = _require_mapping(value_row, location)
        _require_exact_fields(row, _EVENT_CONTRACT_FIELDS, location)
        contracts.append(
            EventContract(
                id=_require_string(row.get("id"), f"{location}.id"),
                event_type=_require_string(row.get("event_type"), f"{location}.event_type"),
                subject=_require_string(row.get("subject"), f"{location}.subject"),
                kind=_require_string(row.get("kind"), f"{location}.kind"),
                event_match=_selector(row.get("event_match"), f"{location}.event_match"),
                required_regions=_string_tuple(
                    row.get("required_regions"), f"{location}.required_regions"
                ),
                optional_regions=_string_tuple(
                    row.get("optional_regions"), f"{location}.optional_regions"
                ),
                generation_policy=_require_string(
                    row.get("generation_policy"), f"{location}.generation_policy"
                ),
                required_payload=_string_tuple(
                    row.get("required_payload"), f"{location}.required_payload"
                ),
            )
        )
    return tuple(contracts)


def _parse_machines(value: object) -> tuple[MachineSpec, ...]:
    rows = _require_sequence(value, "machines")
    machines: list[MachineSpec] = []
    transition_definition_ids: set[str] = set()
    for machine_index, value_row in enumerate(rows):
        location = f"machines[{machine_index}]"
        row = _require_mapping(value_row, location)
        _require_exact_fields(row, _MACHINE_FIELDS, location)
        name = _require_string(row.get("name"), f"{location}.name")
        states = _string_tuple(row.get("states"), f"{location}.states")
        transitions: list[Transition] = []
        for transition_index, value_transition in enumerate(
            _require_sequence(row.get("transitions"), f"{location}.transitions")
        ):
            transition_location = f"{location}.transitions[{transition_index}]"
            transition_row = _require_mapping(value_transition, transition_location)
            _require_exact_fields(transition_row, _TRANSITION_FIELDS, transition_location)
            transition_id = _require_string(transition_row.get("id"), f"{transition_location}.id")
            if transition_id in transition_definition_ids:
                raise SpecValidationError("transition IDs must be globally unique")
            transition_definition_ids.add(transition_id)
            event_type = _require_string(
                transition_row.get("event_type"), f"{transition_location}.event_type"
            )
            target = _require_string(transition_row.get("to"), f"{transition_location}.to")
            event_match = _selector(
                transition_row.get("event_match"),
                f"{transition_location}.event_match",
            )
            guard_value = transition_row.get("guard")
            guard = (
                None
                if guard_value is None
                else _require_string(guard_value, f"{transition_location}.guard")
            )
            kind = _require_string(transition_row.get("kind"), f"{transition_location}.kind")
            if kind not in _TRANSITION_KINDS:
                raise SpecValidationError(
                    f"{transition_location} has unknown transition kind {kind!r}"
                )
            sources = _string_tuple(transition_row.get("from"), f"{transition_location}.from")
            if not sources:
                raise SpecValidationError(
                    f"{transition_location}.from must contain at least one source"
                )
            for source in sources:
                transitions.append(
                    Transition(
                        machine_name=name,
                        source=source,
                        target=target,
                        event_type=event_type,
                        event_match=event_match,
                        guard=guard,
                        kind=kind,
                        id=transition_id,
                    )
                )

        machines.append(
            MachineSpec(
                name=name,
                aggregate=_require_string(row.get("aggregate"), f"{location}.aggregate"),
                state_attribute=_require_string(
                    row.get("state_attribute"), f"{location}.state_attribute"
                ),
                initial_state=_require_string(
                    row.get("initial_state"), f"{location}.initial_state"
                ),
                states=states,
                terminal_states=_string_tuple(
                    row.get("terminal_states"), f"{location}.terminal_states"
                ),
                transitions=tuple(transitions),
            )
        )
    return tuple(machines)


def _transition_definition_ids(machines: tuple[MachineSpec, ...]) -> tuple[str, ...]:
    """Collapse expanded source rows while preserving the raw definition identity."""

    identities: list[tuple[str, str]] = []
    for machine in machines:
        for transition in machine.transitions:
            identity = (machine.name, transition.id)
            if identity not in identities:
                identities.append(identity)
    return tuple(transition_id for _, transition_id in identities)


def _validate_event_contract_selectors(contracts: tuple[EventContract, ...]) -> None:
    for index, left in enumerate(contracts):
        for right in contracts[index + 1 :]:
            if left.event_type != right.event_type:
                continue
            if _selectors_overlap(left.event_match, right.event_match):
                raise SpecValidationError(
                    f"ambiguous event contracts {left.id!r} and {right.id!r} "
                    f"for event {left.event_type!r}"
                )


def _validate_machine(machine: MachineSpec) -> None:
    if machine.initial_state not in machine.states:
        raise SpecValidationError(
            f"machine {machine.name!r} initial state {machine.initial_state!r} is unknown"
        )
    unknown_terminals = set(machine.terminal_states) - set(machine.states)
    if unknown_terminals:
        raise SpecValidationError(
            f"machine {machine.name!r} has unknown terminal states {sorted(unknown_terminals)!r}"
        )

    for transition in machine.transitions:
        if transition.source not in machine.states:
            raise SpecValidationError(
                f"transition {transition.id!r} has unknown source {transition.source!r}"
            )
        if transition.target not in machine.states:
            raise SpecValidationError(
                f"transition {transition.id!r} has unknown target {transition.target!r}"
            )
        if transition.source in machine.terminal_states:
            raise SpecValidationError(
                f"terminal state {transition.source!r} in {machine.name!r} "
                "has an outgoing transition"
            )

    for index, left in enumerate(machine.transitions):
        for right in machine.transitions[index + 1 :]:
            if left.source != right.source or left.event_type != right.event_type:
                continue
            if _selectors_overlap(left.event_match, right.event_match):
                raise SpecValidationError(
                    f"ambiguous transitions {left.id!r} and {right.id!r} in "
                    f"{machine.name!r} from {left.source!r} for {left.event_type!r}"
                )

    witnesses = _reachability_witnesses(machine)
    unreachable = set(machine.states) - witnesses.keys()
    if unreachable:
        raise SpecValidationError(
            f"machine {machine.name!r} has unreachable states {sorted(unreachable)!r}"
        )


def _reachability_witnesses(
    machine: MachineSpec,
) -> dict[str, tuple[Transition, ...]]:
    witnesses: dict[str, tuple[Transition, ...]] = {machine.initial_state: ()}
    pending: deque[str] = deque((machine.initial_state,))
    while pending:
        source = pending.popleft()
        prefix = witnesses[source]
        for transition in machine.transitions:
            if transition.source != source or transition.target in witnesses:
                continue
            witnesses[transition.target] = (*prefix, transition)
            pending.append(transition.target)
    return witnesses


def _reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise SpecValidationError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def _load_spec(path: Path) -> FsmSpec:
    try:
        raw = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_json_keys,
        )
    except OSError as exc:
        raise SpecValidationError(f"cannot read FSM specification {path}: {exc}") from exc
    except SpecValidationError:
        raise
    except (json.JSONDecodeError, UnicodeError, ValueError, RecursionError) as exc:
        raise SpecValidationError(f"invalid FSM JSON in {path}: {exc}") from exc
    return FsmSpec.from_mapping(_require_mapping(raw, "spec"))


@lru_cache(maxsize=1)
def _cached_default_spec() -> FsmSpec:
    path = Path(__file__).parents[1] / "specs" / "apt_engine_fsm.v1.json"
    return _load_spec(path)


def load_default_spec(path: str | Path | None = None) -> FsmSpec:
    """Load the bundled normative companion, or an explicit spec for tooling/tests."""

    if path is None:
        return _cached_default_spec()
    return _load_spec(Path(path))


__all__ = [
    "EventContract",
    "FsmSpec",
    "MachineSpec",
    "SpecValidationError",
    "Transition",
    "load_default_spec",
]
