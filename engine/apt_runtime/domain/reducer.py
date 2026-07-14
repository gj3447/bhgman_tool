"""Pure APT vNext Slice 0 aggregate reducer.

The reducer consumes already-accepted domain facts.  It does not read clocks,
files, databases, networks, policy engines, or model providers.

KG: apt-tpa-legion-engine-canon-2026-06-12
"""

from __future__ import annotations

from dataclasses import replace
from typing import Iterable, Mapping, TypeVar

from .events import (
    EventEnvelope,
    EventSchemaError,
    EventType,
    GuardResult,
    validate_rfc3339_utc_z,
)
from .fsm_spec import EventContract, FsmSpec, SpecValidationError, Transition
from .state import (
    AptCycleState,
    ArtifactRecord,
    AssuranceStatus,
    CycleLifecycle,
    EffectLifecycle,
    EffectState,
    GenerationHistory,
    RealizationStatus,
    SemanticMaturity,
    WorkItemKind,
    WorkItemLifecycle,
    WorkItemState,
)


class ReducerError(ValueError):
    """Base class for fail-closed reducer rejections."""


class AggregateNotInitializedError(ReducerError):
    """Raised when a non-creation event is applied without an aggregate."""


class InvalidTransitionError(ReducerError):
    """Raised when the current state has no declared transition for an event."""


class VersionConflictError(ReducerError):
    """Raised when the event stream version is not exactly state.version + 1."""


class SubjectMismatchError(ReducerError):
    """Raised when cycle, work-item, effect, or configuration identity drifts."""


class StaleGenerationError(ReducerError):
    """Raised when a work mutation targets a non-current generation."""


class SpecHashMismatchError(ReducerError):
    """Raised when replay is attempted against a different FSM specification."""


class GuardRejectedError(ReducerError):
    """Raised when a guarded transition does not carry a PASS fact."""


_TERMINAL_CYCLE_STATES = {
    CycleLifecycle.SUCCEEDED,
    CycleLifecycle.FAILED,
    CycleLifecycle.CANCELLED,
    CycleLifecycle.SUPERSEDED,
}
_EFFECT_AUDIT_EVENTS = {
    EventType.EFFECT_SUCCEEDED,
    EventType.EFFECT_FAILED,
    EventType.EFFECT_LEASE_EXPIRED,
    EventType.EFFECT_TIMED_OUT,
    EventType.EFFECT_CANCELLED,
}
_WORK_EVENTS_REQUIRING_EFFECT = {
    EventType.REALIZATION_STARTED,
    EventType.ARTIFACT_MATERIALIZED,
    EventType.REALIZATION_FAILED,
}
_CLOSED_WORK_ITEM_EVENTS = {
    EventType.CORRECTION_OPENED,
    EventType.ARTIFACT_INVALIDATED,
    EventType.EVIDENCE_INVALIDATED,
    EventType.WORK_ITEM_SUPERSEDED,
}
_REALIZATION_FAILURE_EFFECT_STATES = frozenset(
    {EffectLifecycle.FAILED, EffectLifecycle.TIMED_OUT, EffectLifecycle.CANCELLED}
)
_CONTAINER_ONLY_EVENTS = {
    EventType.DECOMPOSITION_STARTED,
    EventType.CHILDREN_ATTACHED,
}
_LEAF_ONLY_EVENTS = {
    EventType.ATOMICITY_ACCEPTED,
    EventType.CRYSTALLIZATION_STARTED,
    EventType.CONTRACT_ACCEPTED,
}
_SEQUENCE_PAYLOAD_FIELDS = {
    "parent_ids",
    "child_ids",
    "evidence_refs",
    "guard_evidence_refs",
}

T = TypeVar("T")


def _event_name(event: EventEnvelope) -> str:
    return event.event_type.value


def _required_string(payload: Mapping[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise EventSchemaError(f"payload field {key!r} must be a non-empty string")
    return value


def _string_tuple(payload: Mapping[str, object], key: str) -> tuple[str, ...]:
    value = payload.get(key, ())
    if not isinstance(value, (tuple, list)):
        raise EventSchemaError(f"payload field {key!r} must be a sequence of strings")
    result = tuple(value)
    if any(not isinstance(item, str) or not item for item in result):
        raise EventSchemaError(f"payload field {key!r} must contain non-empty strings")
    return result


def _validate_required_payload(contract: EventContract, payload: Mapping[str, object]) -> None:
    unexpected = sorted(set(payload) - set(contract.required_payload))
    if unexpected:
        raise EventSchemaError(f"unexpected payload fields: {', '.join(unexpected)}")
    missing = [key for key in contract.required_payload if key not in payload]
    if missing:
        raise EventSchemaError(f"missing required payload fields: {', '.join(missing)}")
    for key in contract.required_payload:
        if key in _SEQUENCE_PAYLOAD_FIELDS:
            values = _string_tuple(payload, key)
            if key in {"evidence_refs", "guard_evidence_refs"} and not values:
                raise EventSchemaError(f"payload field {key!r} must contain at least one reference")
            continue
        if key == "attempt":
            value = payload[key]
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise EventSchemaError("payload field 'attempt' must be a positive integer")
            continue
        value = _required_string(payload, key)
        if key.endswith("_hash") and (
            len(value) != 64
            or any(character not in "0123456789abcdefABCDEF" for character in value)
        ):
            raise EventSchemaError(f"payload field {key!r} must be a 64-character SHA-256 hex")
        if key == "lease_expiry":
            validate_rfc3339_utc_z("lease_expiry", value)


def _unique(existing: tuple[T, ...], additions: Iterable[T]) -> tuple[T, ...]:
    result = list(existing)
    for item in additions:
        if item not in result:
            result.append(item)
    return tuple(result)


def _contract_for(spec: FsmSpec, event: EventEnvelope) -> EventContract:
    try:
        return spec.matching_event_contract(_event_name(event), event.payload)
    except SpecValidationError as exc:
        raise InvalidTransitionError(str(exc)) from exc


def _validate_envelope(
    state: AptCycleState | None,
    event: EventEnvelope,
    spec: FsmSpec,
) -> EventContract:
    if event.fsm_spec_hash != spec.spec_hash:
        raise SpecHashMismatchError(
            f"event FSM hash {event.fsm_spec_hash} does not match {spec.spec_hash}"
        )
    if event.schema_version not in spec.event_schema_versions:
        raise EventSchemaError(f"unsupported schema_version {event.schema_version!r}")
    if event.stream_id != event.cycle_id:
        raise SubjectMismatchError("stream_id must equal cycle_id for the v1 aggregate")

    contract = _contract_for(spec, event)
    _validate_required_payload(contract, event.payload)

    if contract.subject == "cycle" and (
        event.work_item_id is not None
        or event.effect_id is not None
        or event.generation is not None
    ):
        raise SubjectMismatchError("cycle event cannot name work-item/effect subjects")
    if contract.subject == "work_item":
        if event.work_item_id is None:
            raise SubjectMismatchError("work-item event requires work_item_id")
        if event.event_type in _WORK_EVENTS_REQUIRING_EFFECT:
            if event.effect_id is None:
                raise SubjectMismatchError(f"{event.event_type.value} requires an effect_id")
        elif event.effect_id is not None:
            raise SubjectMismatchError(
                f"{event.event_type.value} cannot carry an auxiliary effect_id"
            )
    if contract.subject == "effect" and event.effect_id is None:
        raise SubjectMismatchError("effect event requires effect_id")

    if state is None:
        if event.stream_version != 1:
            raise VersionConflictError("CycleCreated must have stream_version 1")
        return contract

    if event.cycle_id != state.cycle_id or event.stream_id != state.cycle_id:
        raise SubjectMismatchError("event does not belong to the loaded cycle")
    if event.config_version != state.config_version:
        raise SubjectMismatchError("event config_version differs from the cycle snapshot")
    expected_version = state.version + 1
    if event.stream_version != expected_version:
        raise VersionConflictError(
            f"expected stream_version {expected_version}, got {event.stream_version}"
        )
    if event.fsm_spec_hash != state.fsm_spec_hash:
        raise SpecHashMismatchError("event FSM hash differs from the cycle-pinned hash")

    if state.lifecycle in _TERMINAL_CYCLE_STATES:
        if event.event_type not in _EFFECT_AUDIT_EVENTS:
            raise InvalidTransitionError(
                "terminal cycle permits only late outcome/cancellation events for "
                "already-recorded effects"
            )

    return contract


def _matching_region_transitions(
    spec: FsmSpec,
    aggregate: str,
    subject: object,
    event: EventEnvelope,
    contract: EventContract,
) -> dict[str, Transition]:
    matches: dict[str, Transition] = {}
    for machine in spec.machines:
        if machine.aggregate != aggregate:
            continue
        current = getattr(subject, machine.state_attribute)
        current_value = current.value if hasattr(current, "value") else str(current)
        selected = spec.matching_transitions(
            machine.name,
            current_value,
            _event_name(event),
            event.payload,
        )
        if len(selected) > 1:
            raise InvalidTransitionError(
                f"ambiguous runtime transition for {machine.name}/{current_value}/{_event_name(event)}"
            )
        if selected:
            matches[machine.name] = selected[0]

    missing_regions = set(contract.required_regions) - set(matches)
    if missing_regions:
        missing = ", ".join(sorted(missing_regions))
        raise InvalidTransitionError(
            f"event {_event_name(event)} has no declared transition in required region(s): {missing}"
        )
    unexpected = set(matches) - set(contract.required_regions) - set(contract.optional_regions)
    if unexpected:
        raise InvalidTransitionError(
            f"event {_event_name(event)} unexpectedly matched region(s): {sorted(unexpected)}"
        )
    _validate_guards(matches.values(), event.payload)
    return matches


def _validate_guards(transitions: Iterable[Transition], payload: Mapping[str, object]) -> None:
    guarded = tuple(transition for transition in transitions if transition.guard is not None)
    if not guarded:
        return
    if payload.get("guard_result") != GuardResult.PASS.value:
        names = ", ".join(transition.guard or "" for transition in guarded)
        raise GuardRejectedError(f"guarded transition requires PASS: {names}")
    evidence_refs = _string_tuple(payload, "guard_evidence_refs")
    if not evidence_refs:
        raise GuardRejectedError("guarded transition requires at least one evidence reference")


def _replace_work_item(state: AptCycleState, work_item: WorkItemState) -> AptCycleState:
    items = tuple(
        sorted(
            (
                work_item if current.work_item_id == work_item.work_item_id else current
                for current in state.work_items
            ),
            key=lambda item: item.work_item_id,
        )
    )
    return replace(state, work_items=items)


def _replace_effect(state: AptCycleState, effect: EffectState) -> AptCycleState:
    effects = tuple(
        sorted(
            (
                effect if current.effect_id == effect.effect_id else current
                for current in state.effects
            ),
            key=lambda item: item.effect_id,
        )
    )
    return replace(state, effects=effects)


def _create_cycle(event: EventEnvelope, spec: FsmSpec) -> AptCycleState:
    return AptCycleState(
        cycle_id=event.cycle_id,
        lifecycle=CycleLifecycle.CREATED,
        version=event.stream_version,
        fsm_spec_hash=spec.spec_hash,
        config_version=event.config_version,
        config_snapshot_ref=_required_string(event.payload, "config_snapshot_ref"),
        config_snapshot_hash=_required_string(event.payload, "config_snapshot_hash"),
        canon_snapshot_ref=_required_string(event.payload, "canon_snapshot_ref"),
        canon_snapshot_hash=_required_string(event.payload, "canon_snapshot_hash"),
        work_items=(),
        effects=(),
        terminal_receipt_ref=None,
    )


def _reduce_cycle(
    state: AptCycleState,
    event: EventEnvelope,
    contract: EventContract,
    spec: FsmSpec,
) -> AptCycleState:
    matches = _matching_region_transitions(spec, "cycle", state, event, contract)
    transition = matches["cycle.lifecycle"]
    receipt = state.terminal_receipt_ref
    if event.event_type is EventType.CYCLE_COMPLETED:
        receipt = _required_string(event.payload, "terminal_receipt_ref")
    return replace(
        state,
        lifecycle=CycleLifecycle(transition.target),
        terminal_receipt_ref=receipt,
        version=event.stream_version,
    )


def _create_work_item(state: AptCycleState, event: EventEnvelope) -> AptCycleState:
    if state.lifecycle is not CycleLifecycle.ACTIVE:
        raise InvalidTransitionError("work items may be opened only while the cycle is ACTIVE")
    assert event.work_item_id is not None
    if any(item.work_item_id == event.work_item_id for item in state.work_items):
        raise InvalidTransitionError(f"work item {event.work_item_id!r} already exists")
    if event.generation != 1:
        raise StaleGenerationError("WorkItemOpened must initialize generation 1")
    try:
        kind = WorkItemKind(_required_string(event.payload, "work_kind"))
    except ValueError as exc:
        raise EventSchemaError("work_kind must be LEAF or CONTAINER") from exc
    parent_ids = tuple(sorted(set(_string_tuple(event.payload, "parent_ids"))))
    known_ids = {item.work_item_id for item in state.work_items}
    missing = set(parent_ids) - known_ids
    if missing:
        raise SubjectMismatchError(f"unknown parent work item(s): {sorted(missing)}")
    parents = tuple(state.work_item(parent_id) for parent_id in parent_ids)
    for parent in parents:
        if parent.kind is not WorkItemKind.CONTAINER:
            raise InvalidTransitionError(
                f"parent work item {parent.work_item_id!r} must be a CONTAINER"
            )
        if parent.lifecycle is not WorkItemLifecycle.OPEN:
            raise InvalidTransitionError(f"parent work item {parent.work_item_id!r} must be OPEN")
        if parent.semantic_maturity is not SemanticMaturity.DECOMPOSING:
            raise InvalidTransitionError(
                f"parent work item {parent.work_item_id!r} must be DECOMPOSING"
            )

    work_item = WorkItemState(
        work_item_id=event.work_item_id,
        kind=kind,
        lifecycle=WorkItemLifecycle.OPEN,
        semantic_maturity=SemanticMaturity.DRAFT,
        realization=RealizationStatus.NOT_READY,
        assurance=AssuranceStatus.UNASSESSED,
        current_generation=1,
        parent_ids=parent_ids,
        child_ids=(),
        generations=(GenerationHistory(generation=1),),
    )
    items = list(state.work_items)
    for index, parent in enumerate(items):
        if parent.work_item_id in parent_ids:
            items[index] = replace(
                parent,
                child_ids=tuple(sorted((*parent.child_ids, event.work_item_id))),
            )
    items.append(work_item)
    return replace(
        state,
        work_items=tuple(sorted(items, key=lambda item: item.work_item_id)),
        version=event.stream_version,
    )


def _validate_work_generation(
    work_item: WorkItemState,
    event: EventEnvelope,
    contract: EventContract,
) -> None:
    if contract.generation_policy == "CURRENT":
        expected = work_item.current_generation
    elif contract.generation_policy == "NEXT":
        expected = work_item.current_generation + 1
    else:
        raise InvalidTransitionError(
            f"unsupported work generation policy {contract.generation_policy!r}"
        )
    if event.generation != expected:
        raise StaleGenerationError(
            f"expected generation {expected} for {event.event_type.value}, got {event.generation}"
        )


def _validate_effect_for_realization(
    state: AptCycleState,
    work_item: WorkItemState,
    event: EventEnvelope,
    *,
    required_lifecycles: frozenset[EffectLifecycle],
) -> EffectState:
    assert event.effect_id is not None
    payload_effect_id = _required_string(event.payload, "effect_id")
    if payload_effect_id != event.effect_id:
        raise SubjectMismatchError("payload effect_id must equal envelope effect_id")
    try:
        effect = state.effect(event.effect_id)
    except KeyError as exc:
        raise SubjectMismatchError(f"unknown effect_id {event.effect_id!r}") from exc
    if effect.lifecycle not in required_lifecycles:
        expected = ", ".join(sorted(lifecycle.value for lifecycle in required_lifecycles))
        raise InvalidTransitionError(
            f"effect {event.effect_id!r} must be one of [{expected}], got {effect.lifecycle.value}"
        )
    if effect.capability != "artifact.realize":
        raise InvalidTransitionError(
            f"realization requires capability 'artifact.realize', got {effect.capability!r}"
        )
    if (
        effect.work_item_id != work_item.work_item_id
        or effect.generation != work_item.current_generation
    ):
        raise StaleGenerationError("effect is not bound to the current work-item generation")
    if (
        event.event_type in {EventType.ARTIFACT_MATERIALIZED, EventType.REALIZATION_FAILED}
        and work_item.realization_effect_id != event.effect_id
    ):
        raise SubjectMismatchError(
            f"{event.event_type.value} effect_id must equal the active realization effect"
        )
    return effect


def _updated_generation_history(
    history: GenerationHistory,
    event: EventEnvelope,
) -> GenerationHistory:
    evidence = _unique(
        history.evidence_refs,
        (
            *_string_tuple(event.payload, "guard_evidence_refs"),
            *_string_tuple(event.payload, "evidence_refs"),
        ),
    )
    verdicts = history.verdict_refs
    verdict_ref = event.payload.get("verdict_ref")
    if isinstance(verdict_ref, str) and verdict_ref:
        verdicts = _unique(verdicts, (verdict_ref,))
    artifacts = history.artifacts
    if event.event_type is EventType.ARTIFACT_MATERIALIZED:
        artifact = ArtifactRecord(
            artifact_ref=_required_string(event.payload, "artifact_ref"),
            artifact_hash=_required_string(event.payload, "artifact_hash"),
        )
        artifacts = _unique(artifacts, (artifact,))
    return replace(
        history,
        artifacts=artifacts,
        evidence_refs=evidence,
        verdict_refs=verdicts,
    )


def _reduce_work_item(
    state: AptCycleState,
    event: EventEnvelope,
    contract: EventContract,
    spec: FsmSpec,
) -> AptCycleState:
    assert event.work_item_id is not None
    try:
        work_item = state.work_item(event.work_item_id)
    except KeyError as exc:
        raise SubjectMismatchError(f"unknown work_item_id {event.work_item_id!r}") from exc
    if work_item.lifecycle is WorkItemLifecycle.SUPERSEDED:
        raise InvalidTransitionError("SUPERSEDED work item cannot accept new work events")
    if (
        work_item.lifecycle is WorkItemLifecycle.CLOSED
        and event.event_type not in _CLOSED_WORK_ITEM_EVENTS
    ):
        raise InvalidTransitionError(
            "CLOSED work item accepts only correction, invalidation, or supersession events"
        )
    _validate_work_generation(work_item, event, contract)

    if event.event_type in _CONTAINER_ONLY_EVENTS and work_item.kind is not WorkItemKind.CONTAINER:
        raise InvalidTransitionError(f"{event.event_type.value} requires a CONTAINER work item")
    if event.event_type in _LEAF_ONLY_EVENTS and work_item.kind is not WorkItemKind.LEAF:
        raise InvalidTransitionError(f"{event.event_type.value} requires a LEAF work item")

    if event.event_type is EventType.WORK_ITEM_CLOSED:
        closure_kind = _required_string(event.payload, "closure_kind")
        if closure_kind != work_item.kind.value:
            raise SubjectMismatchError(
                f"closure_kind {closure_kind!r} does not match {work_item.kind.value}"
            )
    if event.event_type is EventType.CHILDREN_ATTACHED:
        declared_children = set(_string_tuple(event.payload, "child_ids"))
        if declared_children != set(work_item.child_ids):
            raise SubjectMismatchError("ChildrenAttached must name exactly the attached children")
    if event.event_type is EventType.ARTIFACT_INVALIDATED:
        artifact_ref = _required_string(event.payload, "artifact_ref")
        if artifact_ref not in {
            artifact.artifact_ref for artifact in work_item.generation_history().artifacts
        }:
            raise SubjectMismatchError(
                f"artifact_ref {artifact_ref!r} is not in the current generation"
            )
    if event.event_type is EventType.EVIDENCE_INVALIDATED:
        evidence_ref = _required_string(event.payload, "evidence_ref")
        if evidence_ref not in work_item.generation_history().evidence_refs:
            raise SubjectMismatchError(
                f"evidence_ref {evidence_ref!r} is not in the current generation"
            )
    if event.event_type is EventType.REALIZATION_STARTED:
        _validate_effect_for_realization(
            state,
            work_item,
            event,
            required_lifecycles=frozenset({EffectLifecycle.RUNNING}),
        )
    if event.event_type is EventType.ARTIFACT_MATERIALIZED:
        _validate_effect_for_realization(
            state,
            work_item,
            event,
            required_lifecycles=frozenset({EffectLifecycle.SUCCEEDED}),
        )
    if event.event_type is EventType.REALIZATION_FAILED:
        _validate_effect_for_realization(
            state,
            work_item,
            event,
            required_lifecycles=_REALIZATION_FAILURE_EFFECT_STATES,
        )

    matches = _matching_region_transitions(spec, "work_item", work_item, event, contract)
    updated = work_item
    for region_name, transition in matches.items():
        if region_name == "work_item.lifecycle":
            updated = replace(updated, lifecycle=WorkItemLifecycle(transition.target))
        elif region_name == "work_item.semantic_maturity":
            updated = replace(updated, semantic_maturity=SemanticMaturity(transition.target))
        elif region_name == "work_item.realization":
            realization = RealizationStatus(transition.target)
            if event.event_type is EventType.REALIZATION_STARTED:
                realization_effect_id = event.effect_id
            elif realization in {
                RealizationStatus.NOT_READY,
                RealizationStatus.READY,
                RealizationStatus.DISPATCHED,
            }:
                realization_effect_id = None
            else:
                realization_effect_id = updated.realization_effect_id
            updated = replace(
                updated,
                realization=realization,
                realization_effect_id=realization_effect_id,
            )
        elif region_name == "work_item.assurance":
            updated = replace(updated, assurance=AssuranceStatus(transition.target))
        else:  # pragma: no cover - validated specs cannot introduce an unknown work region
            raise InvalidTransitionError(f"unsupported work-item region {region_name!r}")

    opens_generation = contract.generation_policy == "NEXT"
    if opens_generation:
        assert event.generation is not None
        artifacts = (
            work_item.generations[-1].artifacts
            if event.event_type is EventType.EVIDENCE_INVALIDATED
            else ()
        )
        new_history = GenerationHistory(
            generation=event.generation,
            artifacts=artifacts,
            evidence_refs=_string_tuple(event.payload, "evidence_refs"),
        )
        updated = replace(
            updated,
            current_generation=event.generation,
            generations=(*work_item.generations, new_history),
        )
    else:
        current = updated.generations[-1]
        next_history = _updated_generation_history(current, event)
        updated = replace(updated, generations=(*updated.generations[:-1], next_history))

    state = _replace_work_item(state, updated)
    return replace(state, version=event.stream_version)


def _create_effect(state: AptCycleState, event: EventEnvelope) -> AptCycleState:
    if state.lifecycle is not CycleLifecycle.ACTIVE:
        raise InvalidTransitionError("effects may be queued only while the cycle is ACTIVE")
    assert event.effect_id is not None
    if any(effect.effect_id == event.effect_id for effect in state.effects):
        raise InvalidTransitionError(f"effect {event.effect_id!r} already exists")

    if event.work_item_id is None:
        if event.generation is not None:
            raise SubjectMismatchError("cycle-scoped effect cannot carry a generation")
    else:
        try:
            work_item = state.work_item(event.work_item_id)
        except KeyError as exc:
            raise SubjectMismatchError(f"unknown work_item_id {event.work_item_id!r}") from exc
        if work_item.lifecycle is not WorkItemLifecycle.OPEN:
            raise InvalidTransitionError(
                f"cannot queue an effect for a {work_item.lifecycle.value} work item"
            )
        if event.generation != work_item.current_generation:
            raise StaleGenerationError("new effect must bind to the current work generation")

    effect = EffectState(
        effect_id=event.effect_id,
        lifecycle=EffectLifecycle.PENDING,
        work_item_id=event.work_item_id,
        generation=event.generation,
        capability=_required_string(event.payload, "capability"),
        provider=_required_string(event.payload, "provider"),
        risk_class=_required_string(event.payload, "risk_class"),
        idempotency_key=_required_string(event.payload, "idempotency_key"),
        input_ref=_required_string(event.payload, "input_ref"),
        input_hash=_required_string(event.payload, "input_hash"),
        result_ref=None,
        result_hash=None,
    )
    effects = tuple(sorted((*state.effects, effect), key=lambda item: item.effect_id))
    return replace(state, effects=effects, version=event.stream_version)


def _reduce_effect(
    state: AptCycleState,
    event: EventEnvelope,
    contract: EventContract,
    spec: FsmSpec,
) -> AptCycleState:
    assert event.effect_id is not None
    try:
        effect = state.effect(event.effect_id)
    except KeyError as exc:
        raise SubjectMismatchError(f"unknown effect_id {event.effect_id!r}") from exc
    if event.work_item_id != effect.work_item_id or event.generation != effect.generation:
        raise SubjectMismatchError("effect event subject/generation differs from queued binding")
    if effect.work_item_id is not None:
        work_item = state.work_item(effect.work_item_id)
        if (
            work_item.lifecycle is WorkItemLifecycle.CLOSED
            and event.event_type not in _EFFECT_AUDIT_EVENTS
        ):
            raise InvalidTransitionError(
                "CLOSED work item permits only late effect outcome/cancellation audit"
            )
        obsolete = (
            effect.generation != work_item.current_generation
            or work_item.lifecycle is WorkItemLifecycle.SUPERSEDED
        )
        if obsolete and event.event_type not in _EFFECT_AUDIT_EVENTS:
            raise StaleGenerationError(
                "obsolete work-item effect cannot advance lease/start/retry execution"
            )
        if (
            work_item.realization is RealizationStatus.FAILED
            and work_item.realization_effect_id == effect.effect_id
            and event.event_type
            in {
                EventType.EFFECT_RETRY_QUEUED,
                EventType.EFFECT_LEASED,
                EventType.EFFECT_STARTED,
            }
        ):
            raise InvalidTransitionError(
                "failed realization requires RealizationRetryApproved before effect retry, "
                "lease, or start"
            )
    matches = _matching_region_transitions(spec, "effect", effect, event, contract)
    transition = matches["effect.lifecycle"]
    lifecycle = EffectLifecycle(transition.target)
    if event.event_type is EventType.EFFECT_SUCCEEDED:
        updated = replace(
            effect,
            lifecycle=lifecycle,
            result_ref=_required_string(event.payload, "result_ref"),
            result_hash=_required_string(event.payload, "result_hash"),
        )
    else:
        updated = replace(effect, lifecycle=lifecycle)
    state = _replace_effect(state, updated)
    return replace(state, version=event.stream_version)


def reduce_event(
    state: AptCycleState | None,
    event: EventEnvelope,
    spec: FsmSpec,
) -> AptCycleState:
    """Apply one immutable fact and return a new aggregate or reject atomically."""

    contract = _validate_envelope(state, event, spec)
    if state is None:
        if event.event_type is not EventType.CYCLE_CREATED or contract.kind != "INITIALIZER":
            raise AggregateNotInitializedError("the first event must be CycleCreated")
        return _create_cycle(event, spec)

    if contract.kind == "INITIALIZER":
        if event.event_type is EventType.WORK_ITEM_OPENED:
            return _create_work_item(state, event)
        if event.event_type is EventType.EFFECT_QUEUED:
            return _create_effect(state, event)
        raise InvalidTransitionError(f"initializer {_event_name(event)} is invalid after creation")
    if contract.subject == "cycle":
        return _reduce_cycle(state, event, contract, spec)
    if contract.subject == "work_item":
        return _reduce_work_item(state, event, contract, spec)
    if contract.subject == "effect":
        return _reduce_effect(state, event, contract, spec)
    raise InvalidTransitionError(f"unknown aggregate subject {contract.subject!r}")


def replay(events: Iterable[EventEnvelope], spec: FsmSpec) -> AptCycleState:
    """Replay an ordered stream using one immutable, hash-pinned specification."""

    state: AptCycleState | None = None
    for event in events:
        state = reduce_event(state, event, spec)
    if state is None:
        raise AggregateNotInitializedError("cannot replay an empty event stream")
    return state
