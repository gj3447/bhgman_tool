"""Canonical fact writer used by the Slice 2 operational effect runtime.

The effect queue is an operational projection, never a second state authority.
Every lifecycle mutation therefore passes through ``DurableKernel`` and the
pure reducer before the queue projection is advanced.

# KG: apt-tpa-legion-engine-canon-2026-06-12
# Design: ADRs/apt-vnext-slice2-effect-runtime-2026-07-14.md
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from engine.apt_runtime.domain.canonical import (
    CanonicalValue,
    as_mapping,
    canonical_sha256,
    deep_freeze,
)
from engine.apt_runtime.domain.commands import CanonicalCommandEnvelope
from engine.apt_runtime.domain.events import EventEnvelope, EventType
from engine.apt_runtime.domain.fsm_spec import FsmSpec
from engine.apt_runtime.domain.reducer import replay
from engine.apt_runtime.domain.state import AptCycleState
from engine.apt_runtime.ports.event_store import EventStore, StoreConflict

from .durable_kernel import (
    CommandDecision,
    DecisionKernel,
    DecisionOutcome,
    DurableKernel,
    DurableKernelError,
)


class EffectFactError(DurableKernelError):
    """A canonical effect fact could not be constructed or committed."""


@dataclass(frozen=True, slots=True)
class EffectFactCommit:
    """Stable identity of a first or deduplicated canonical fact commit."""

    event_id: str
    stream_version: int
    event_type: EventType
    deduplicated: bool


@dataclass(frozen=True, slots=True)
class _FactDefinition:
    cycle_id: str
    effect_id: str
    event_type: EventType
    payload: Mapping[str, CanonicalValue]
    occurred_at: str
    actor: str
    correlation_id: str
    causation_id: str
    authorization_context: Mapping[str, CanonicalValue]


class _SingleFactDecider(DecisionKernel):
    def __init__(self, spec: FsmSpec, definition: _FactDefinition, event_id: str) -> None:
        self._spec = spec
        self._definition = definition
        self._event_id = event_id

    def decide(
        self, state: AptCycleState | None, command: CanonicalCommandEnvelope
    ) -> CommandDecision:
        if state is None:
            raise EffectFactError("effect facts require an initialized cycle")
        try:
            effect = state.effect(self._definition.effect_id)
        except KeyError as exc:
            raise EffectFactError(f"unknown effect_id {self._definition.effect_id!r}") from exc
        event = EventEnvelope.create(
            event_id=self._event_id,
            stream_id=state.cycle_id,
            stream_version=state.version + 1,
            event_type=self._definition.event_type,
            schema_version=self._spec.event_schema_versions[0],
            fsm_spec_hash=self._spec.spec_hash,
            cycle_id=state.cycle_id,
            work_item_id=effect.work_item_id,
            effect_id=effect.effect_id,
            generation=effect.generation,
            actor=command.actor,
            correlation_id=command.correlation_id,
            causation_id=command.causation_id,
            command_id=command.command_id,
            config_version=state.config_version,
            payload=self._definition.payload,
            created_at=self._definition.occurred_at,
        )
        return CommandDecision(
            outcome=DecisionOutcome.ACCEPTED,
            facts=(event,),
            effects=(),
            response={"event_id": event.event_id, "event_type": event.event_type.value},
        )


class EffectFactWriter:
    """Append one reducer-validated effect fact with bounded CAS retries."""

    def __init__(self, store: EventStore, spec: FsmSpec, *, max_conflict_retries: int = 8) -> None:
        if not isinstance(store, EventStore):
            raise EffectFactError("store must implement EventStore")
        if not isinstance(spec, FsmSpec):
            raise EffectFactError("spec must be an FsmSpec")
        if (
            isinstance(max_conflict_retries, bool)
            or not isinstance(max_conflict_retries, int)
            or max_conflict_retries < 1
        ):
            raise EffectFactError("max_conflict_retries must be a positive integer")
        self._store = store
        self._spec = spec
        self._max_conflict_retries = max_conflict_retries

    def append(
        self,
        *,
        cycle_id: str,
        effect_id: str,
        event_type: EventType,
        payload: Mapping[str, object],
        occurred_at: str,
        actor: str,
        correlation_id: str,
        causation_id: str,
        authorization_context: Mapping[str, object] | None = None,
    ) -> EffectFactCommit:
        """Commit one exact fact, deduplicating an identical concurrent attempt."""

        frozen_payload = as_mapping(deep_freeze(payload))
        frozen_authorization = as_mapping(
            deep_freeze(
                {
                    "authority": "EFFECT_RUNTIME",
                    "effect_id": effect_id,
                }
                if authorization_context is None
                else authorization_context
            )
        )
        definition = _FactDefinition(
            cycle_id=cycle_id,
            effect_id=effect_id,
            event_type=EventType(event_type),
            payload=frozen_payload,
            occurred_at=occurred_at,
            actor=actor,
            correlation_id=correlation_id,
            causation_id=causation_id,
            authorization_context=frozen_authorization,
        )
        for _ in range(self._max_conflict_retries):
            history = tuple(self._store.load(cycle_id))
            if not history:
                raise EffectFactError("effect facts require an initialized cycle")
            duplicate = _find_exact_fact(history, definition)
            if duplicate is not None:
                return EffectFactCommit(
                    event_id=duplicate.event_id,
                    stream_version=duplicate.stream_version,
                    event_type=duplicate.event_type,
                    deduplicated=True,
                )
            state = replay(history, self._spec)
            command_id, event_id = _fact_ids(definition, state.version)
            command = CanonicalCommandEnvelope(
                command_id=command_id,
                command_type=f"Record{definition.event_type.value}",
                schema_version=self._spec.event_schema_versions[0],
                cycle_id=cycle_id,
                expected_version=state.version,
                actor=actor,
                authorization_context=definition.authorization_context,
                correlation_id=correlation_id,
                causation_id=causation_id,
                input={
                    "effect_id": effect_id,
                    "event_type": definition.event_type.value,
                    "occurred_at": occurred_at,
                    "payload": frozen_payload,
                },
                issued_at=occurred_at,
            )
            kernel = DurableKernel(
                self._store,
                self._spec,
                _SingleFactDecider(self._spec, definition, event_id),
            )
            try:
                result = kernel.execute(command)
            except StoreConflict:
                continue
            return EffectFactCommit(
                event_id=event_id,
                stream_version=result.new_version,
                event_type=definition.event_type,
                deduplicated=result.deduplicated,
            )
        raise EffectFactError("effect fact CAS retry budget was exhausted")


def _find_exact_fact(
    history: tuple[EventEnvelope, ...], definition: _FactDefinition
) -> EventEnvelope | None:
    payload_hash = canonical_sha256(definition.payload)
    for event in history:
        if (
            event.effect_id == definition.effect_id
            and event.event_type is definition.event_type
            and event.payload_hash == payload_hash
            and event.created_at == definition.occurred_at
            and event.actor == definition.actor
            and event.correlation_id == definition.correlation_id
            and event.causation_id == definition.causation_id
        ):
            return event
    return None


def _fact_ids(definition: _FactDefinition, expected_version: int) -> tuple[str, str]:
    digest = canonical_sha256(
        {
            "actor": definition.actor,
            "authorization_context": definition.authorization_context,
            "causation_id": definition.causation_id,
            "correlation_id": definition.correlation_id,
            "cycle_id": definition.cycle_id,
            "effect_id": definition.effect_id,
            "event_type": definition.event_type.value,
            "expected_version": expected_version,
            "occurred_at": definition.occurred_at,
            "payload": definition.payload,
        }
    )
    return f"effect-fact-command-{digest}", f"effect-fact-event-{digest}"


__all__ = [
    "EffectFactCommit",
    "EffectFactError",
    "EffectFactWriter",
]
