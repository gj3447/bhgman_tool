"""Closed runtime compatibility profile for an APT FSM specification.

Graph validation belongs to :mod:`fsm_spec`; this module pins the Python
reducer's finite registry so a syntactically valid but unexecutable spec fails
at load time rather than raising an attribute error during replay.

KG: apt-tpa-legion-engine-canon-2026-06-12
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Protocol, cast

from .canonical import canonical_sha256
from .events import EventType
from .state import (
    AssuranceStatus,
    CycleLifecycle,
    EffectLifecycle,
    RealizationStatus,
    SemanticMaturity,
    WorkItemLifecycle,
)


class ContractProfile(Protocol):
    id: str
    event_type: str
    subject: str
    kind: str
    event_match: Mapping[str, object]
    required_regions: tuple[str, ...]
    optional_regions: tuple[str, ...]
    generation_policy: str
    required_payload: tuple[str, ...]


class TransitionProfile(Protocol):
    id: str
    source: str
    target: str
    event_type: str
    event_match: Mapping[str, object]
    guard: str | None
    kind: str


class MachineProfile(Protocol):
    name: str
    aggregate: str
    state_attribute: str
    initial_state: str
    states: tuple[str, ...]
    terminal_states: tuple[str, ...]
    transitions: Sequence[TransitionProfile]


class RuntimeSpecProfile(Protocol):
    format_version: int
    spec_id: str
    spec_version: str
    status: str
    event_schema_versions: tuple[str, ...]
    transition_authority: str
    canonical_encoding: Mapping[str, object]
    reducer_semantics: Mapping[str, object]
    event_contracts: Sequence[ContractProfile]
    machines: Sequence[MachineProfile]


_MACHINE_REGISTRY = {
    "cycle.lifecycle": (
        "cycle",
        "lifecycle",
        CycleLifecycle.CREATED.value,
        tuple(state.value for state in CycleLifecycle),
        (
            CycleLifecycle.SUCCEEDED.value,
            CycleLifecycle.FAILED.value,
            CycleLifecycle.CANCELLED.value,
            CycleLifecycle.SUPERSEDED.value,
        ),
    ),
    "work_item.lifecycle": (
        "work_item",
        "lifecycle",
        WorkItemLifecycle.OPEN.value,
        tuple(state.value for state in WorkItemLifecycle),
        (WorkItemLifecycle.SUPERSEDED.value,),
    ),
    "work_item.semantic_maturity": (
        "work_item",
        "semantic_maturity",
        SemanticMaturity.DRAFT.value,
        tuple(state.value for state in SemanticMaturity),
        (),
    ),
    "work_item.realization": (
        "work_item",
        "realization",
        RealizationStatus.NOT_READY.value,
        tuple(state.value for state in RealizationStatus),
        (),
    ),
    "work_item.assurance": (
        "work_item",
        "assurance",
        AssuranceStatus.UNASSESSED.value,
        tuple(state.value for state in AssuranceStatus),
        (),
    ),
    "effect.lifecycle": (
        "effect",
        "lifecycle",
        EffectLifecycle.PENDING.value,
        tuple(state.value for state in EffectLifecycle),
        (EffectLifecycle.SUCCEEDED.value, EffectLifecycle.CANCELLED.value),
    ),
}
_GENERATION_POLICIES = {
    "NONE",
    "INITIAL",
    "CURRENT",
    "NEXT",
    "EFFECT_CREATION",
    "EFFECT_BOUND",
}
_CANONICAL_PROFILE = {
    "name": "apt-canonical-json-v1",
    "hash_algorithm": "SHA-256",
    "encoding": "UTF-8",
    "mapping_keys": "LEXICOGRAPHIC",
    "sequence_order": "PRESERVED; state identity collections are sorted before encoding",
    "strings": "UNICODE_NFC",
    "numbers": "INTEGERS_ONLY",
    "separators": "COMMA_AND_COLON_WITHOUT_WHITESPACE",
    "timestamps": "UTC_RFC3339_Z",
    "excluded_state_fields": (),
}
_REDUCER_SEMANTICS = {
    "event_application": "ALL_MATCHING_REGION_TRANSITIONS_ATOMIC",
    "undeclared_transition": "REJECT",
    "guard_advance_result": "PASS_ONLY",
    "maximum_matches_per_region": 1,
    "event_stream_after_cycle_terminal": (
        "ONLY_EXISTING_EFFECT_OUTCOME_OR_CANCELLATION_EVENTS_ALLOWED; "
        "LEASE_START_RETRY_AND_CYCLE_REOPEN_FORBIDDEN"
    ),
    "correction": "NEXT_GENERATION_AND_DOWNSTREAM_RESET_ATOMIC",
    "stale_effect_result": (
        "OUTCOME_OR_CANCELLATION_MAY_ADVANCE_EFFECT_AUDIT; "
        "LEASE_START_RETRY_AND_CURRENT_GENERATION_MATERIALIZATION_FORBIDDEN"
    ),
    "closed_invalidation": (
        "INVALIDATION_ALWAYS_OPENS_NEXT_GENERATION; CLOSED_ALSO_REOPENS_ATOMICALLY"
    ),
    "closed_work_item": (
        "ONLY_CORRECTION_INVALIDATION_OR_SUPERSESSION_WORK_EVENTS; "
        "NEW_EFFECT_AND_EFFECT_LEASE_START_RETRY_FORBIDDEN; "
        "EXISTING_EFFECT_OUTCOME_OR_CANCELLATION_AUDIT_ALLOWED"
    ),
    "work_item_topology": "CHILD_OPEN_REQUIRES_EVERY_PARENT_OPEN_CONTAINER_DECOMPOSING",
    "work_item_kind": "LEAF_ATOMIC_BRANCH_OR_CONTAINER_DECOMPOSITION_BRANCH",
    "realization_effect_binding": (
        "ARTIFACT_REALIZE_CAPABILITY_AND_SAME_EFFECT_FROM_START_THROUGH_"
        "MATERIALIZATION_OR_FAILURE; EVIDENCE_INVALIDATION_RESETS_NONTERMINAL_"
        "BINDING_AND_PRESERVES_MATERIALIZED_PROVENANCE"
    ),
    "invalidation_target": "CURRENT_GENERATION_REFERENCE_REQUIRED",
    "identity_normalization": "ENVELOPE_PAYLOAD_SPEC_AND_STATE_STRINGS_UNICODE_NFC",
}
_EXECUTION_PROFILE_HASH = "57c233766b9f84a95cba9b4be40fba264be9be7ea3639737090366023e2dc55a"
_SELECTOR_PARTITIONS = {
    EventType.WORK_ITEM_CLOSED.value: {
        "event.work.closed.leaf": {"closure_kind": "LEAF"},
        "event.work.closed.container": {"closure_kind": "CONTAINER"},
    },
    EventType.CORRECTION_OPENED.value: {
        "event.correction.anchor": {"scope": "ANCHOR"},
        "event.correction.decomposition": {"scope": "DECOMPOSITION"},
        "event.correction.contract": {"scope": "CONTRACT"},
    },
}
_EVENT_CONTRACT_SHAPES = {
    EventType.CYCLE_CREATED.value: ("cycle", "INITIALIZER", "NONE", (), ()),
    **{
        event_type.value: ("cycle", "TRANSITION", "NONE", ("cycle.lifecycle",), ())
        for event_type in (
            EventType.CYCLE_STARTED,
            EventType.CYCLE_WAITING_ENTERED,
            EventType.CYCLE_RESUMED,
            EventType.CYCLE_RECOVERY_STARTED,
            EventType.CYCLE_RECOVERED,
            EventType.CYCLE_RECOVERY_DEFERRED,
            EventType.CYCLE_COMPLETED,
            EventType.CYCLE_FAILED,
            EventType.CYCLE_CANCELLED,
            EventType.CYCLE_SUPERSEDED,
        )
    },
    EventType.WORK_ITEM_OPENED.value: ("work_item", "INITIALIZER", "INITIAL", (), ()),
    **{
        event_type.value: (
            "work_item",
            "TRANSITION",
            "CURRENT",
            ("work_item.lifecycle",),
            (),
        )
        for event_type in (EventType.WORK_ITEM_CLOSED, EventType.WORK_ITEM_SUPERSEDED)
    },
    **{
        event_type.value: (
            "work_item",
            "TRANSITION",
            "CURRENT",
            ("work_item.semantic_maturity",),
            (),
        )
        for event_type in (
            EventType.ANCHOR_ACCEPTED,
            EventType.ATOMICITY_ACCEPTED,
            EventType.DECOMPOSITION_STARTED,
            EventType.CHILDREN_ATTACHED,
            EventType.CRYSTALLIZATION_STARTED,
        )
    },
    EventType.CONTRACT_ACCEPTED.value: (
        "work_item",
        "TRANSITION",
        "CURRENT",
        ("work_item.semantic_maturity", "work_item.realization"),
        (),
    ),
    EventType.CORRECTION_OPENED.value: (
        "work_item",
        "TRANSITION",
        "NEXT",
        ("work_item.lifecycle", "work_item.semantic_maturity"),
        ("work_item.realization", "work_item.assurance"),
    ),
    **{
        event_type.value: (
            "work_item",
            "TRANSITION",
            "CURRENT",
            ("work_item.realization",),
            (),
        )
        for event_type in (
            EventType.DISPATCH_PLANNED,
            EventType.REALIZATION_STARTED,
            EventType.ARTIFACT_MATERIALIZED,
            EventType.REALIZATION_FAILED,
            EventType.REALIZATION_RETRY_APPROVED,
        )
    },
    EventType.ARTIFACT_INVALIDATED.value: (
        "work_item",
        "TRANSITION",
        "NEXT",
        ("work_item.realization",),
        ("work_item.lifecycle", "work_item.assurance"),
    ),
    **{
        event_type.value: (
            "work_item",
            "TRANSITION",
            "CURRENT",
            ("work_item.assurance",),
            (),
        )
        for event_type in (
            EventType.VERIFICATION_REQUESTED,
            EventType.VERIFICATION_ACCEPTED,
            EventType.VERIFICATION_REFUTED,
            EventType.VERIFICATION_INCONCLUSIVE,
            EventType.NEW_EVIDENCE_SUBMITTED,
        )
    },
    EventType.EVIDENCE_INVALIDATED.value: (
        "work_item",
        "TRANSITION",
        "NEXT",
        ("work_item.assurance",),
        ("work_item.lifecycle", "work_item.realization"),
    ),
    EventType.EFFECT_QUEUED.value: ("effect", "INITIALIZER", "EFFECT_CREATION", (), ()),
    **{
        event_type.value: (
            "effect",
            "TRANSITION",
            "EFFECT_BOUND",
            ("effect.lifecycle",),
            (),
        )
        for event_type in (
            EventType.EFFECT_LEASED,
            EventType.EFFECT_STARTED,
            EventType.EFFECT_SUCCEEDED,
            EventType.EFFECT_FAILED,
            EventType.EFFECT_LEASE_EXPIRED,
            EventType.EFFECT_TIMED_OUT,
            EventType.EFFECT_RETRY_QUEUED,
            EventType.EFFECT_CANCELLED,
        )
    },
}


def validate_runtime_profile(spec_value: object) -> None:
    """Reject specs the current reducer cannot execute exactly."""

    spec = cast(RuntimeSpecProfile, spec_value)
    if spec.format_version != 1:
        raise ValueError(f"unsupported format_version {spec.format_version}; expected 1")
    if spec.spec_id != "apt_engine_fsm":
        raise ValueError(f"unsupported spec_id {spec.spec_id!r}; expected 'apt_engine_fsm'")
    if spec.spec_version != "1.0.0-proposal.6":
        raise ValueError(
            f"unsupported spec_version {spec.spec_version!r}; expected '1.0.0-proposal.6'"
        )
    if spec.status != "DESIGN_PROPOSAL":
        raise ValueError(f"unsupported status {spec.status!r}; expected 'DESIGN_PROPOSAL'")
    if spec.event_schema_versions != ("1.0.0",):
        raise ValueError("event_schema_versions must contain exactly the supported '1.0.0' schema")
    if spec.transition_authority != "DECISION_KERNEL_AND_PURE_REDUCER":
        raise ValueError("unsupported transition_authority")
    if dict(spec.canonical_encoding) != _CANONICAL_PROFILE:
        raise ValueError(
            "canonical_encoding does not match the complete runtime profile: "
            f"{dict(spec.canonical_encoding)!r}"
        )
    if dict(spec.reducer_semantics) != _REDUCER_SEMANTICS:
        raise ValueError(
            "reducer_semantics does not match the complete runtime profile: "
            f"{dict(spec.reducer_semantics)!r}"
        )

    actual_registry = {
        machine.name: (
            machine.aggregate,
            machine.state_attribute,
            machine.initial_state,
            machine.states,
            machine.terminal_states,
        )
        for machine in spec.machines
    }
    if actual_registry != _MACHINE_REGISTRY:
        raise ValueError(
            f"machine registry does not match the reducer registry: {actual_registry!r}"
        )

    declared_event_types = {contract.event_type for contract in spec.event_contracts}
    supported_event_types = {event_type.value for event_type in EventType}
    unknown = declared_event_types - supported_event_types
    missing = supported_event_types - declared_event_types
    if unknown or missing:
        raise ValueError(
            f"event_type registry mismatch; unknown={sorted(unknown)!r}, "
            f"missing={sorted(missing)!r}"
        )

    for contract in spec.event_contracts:
        expected_shape = _EVENT_CONTRACT_SHAPES[contract.event_type]
        actual_shape = (
            contract.subject,
            contract.kind,
            contract.generation_policy,
            contract.required_regions,
            contract.optional_regions,
        )
        if actual_shape != expected_shape:
            raise ValueError(
                f"event contract {contract.id!r} contract shape mismatch "
                "(subject, kind, generation_policy, required regions, optional regions): "
                f"expected {expected_shape!r}, got {actual_shape!r}"
            )

    partitioned_event_types = set(_SELECTOR_PARTITIONS)
    for event_type, expected in _SELECTOR_PARTITIONS.items():
        actual = {
            contract.id: dict(contract.event_match)
            for contract in spec.event_contracts
            if contract.event_type == event_type
        }
        if actual != expected:
            raise ValueError(f"event_type {event_type!r} selector partition mismatch: {actual!r}")
    unexpected_selectors = {
        contract.id: dict(contract.event_match)
        for contract in spec.event_contracts
        if contract.event_type not in partitioned_event_types and contract.event_match
    }
    if unexpected_selectors:
        raise ValueError(
            f"unpartitioned event contracts cannot declare selectors: {unexpected_selectors!r}"
        )

    for contract in spec.event_contracts:
        if contract.subject not in {"cycle", "work_item", "effect"}:
            raise ValueError(
                f"event contract {contract.id!r} has unsupported subject {contract.subject!r}"
            )
        if contract.kind not in {"INITIALIZER", "TRANSITION"}:
            raise ValueError(
                f"event contract {contract.id!r} has unsupported kind {contract.kind!r}"
            )
        if contract.generation_policy not in _GENERATION_POLICIES:
            raise ValueError(
                f"event contract {contract.id!r} has unsupported generation_policy "
                f"{contract.generation_policy!r}"
            )
        missing_selector_fields = set(contract.event_match) - set(contract.required_payload)
        if missing_selector_fields:
            raise ValueError(
                f"event contract {contract.id!r} selector fields must be required payload "
                f"fields: {sorted(missing_selector_fields)!r}"
            )


def validate_execution_profile(spec_value: object) -> None:
    """Pin the exact contracts and transitions after structural diagnostics pass."""

    spec = cast(RuntimeSpecProfile, spec_value)
    execution_profile = {
        "event_contracts": tuple(
            {
                "id": contract.id,
                "event_type": contract.event_type,
                "subject": contract.subject,
                "kind": contract.kind,
                "event_match": contract.event_match,
                "required_regions": contract.required_regions,
                "optional_regions": contract.optional_regions,
                "generation_policy": contract.generation_policy,
                "required_payload": contract.required_payload,
            }
            for contract in spec.event_contracts
        ),
        "machines": tuple(
            {
                "name": machine.name,
                "aggregate": machine.aggregate,
                "state_attribute": machine.state_attribute,
                "initial_state": machine.initial_state,
                "states": machine.states,
                "terminal_states": machine.terminal_states,
                "transitions": tuple(
                    {
                        "id": transition.id,
                        "source": transition.source,
                        "target": transition.target,
                        "event_type": transition.event_type,
                        "event_match": transition.event_match,
                        "guard": transition.guard,
                        "kind": transition.kind,
                    }
                    for transition in machine.transitions
                ),
            }
            for machine in spec.machines
        ),
    }
    actual_execution_profile_hash = canonical_sha256(execution_profile)
    if actual_execution_profile_hash != _EXECUTION_PROFILE_HASH:
        raise ValueError(
            "execution profile mismatch: expected "
            f"{_EXECUTION_PROFILE_HASH}, got {actual_execution_profile_hash}"
        )


__all__ = ["validate_execution_profile", "validate_runtime_profile"]
