"""Trusted command/replay boundary above the low-level event-store port.

Only this application service turns a canonical command into durable facts.
The injected decision kernel is trusted domain code; callers cannot submit an
unchecked receipt digest, executable outbox payload, or arbitrary snapshot.

# KG: apt-tpa-legion-engine-canon-2026-06-12
# KG: APT_SCW_TDAD_canonical
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from engine.apt_runtime.domain.canonical import (
    CanonicalEncodingError,
    CanonicalValue,
    as_mapping,
    deep_freeze,
)
from engine.apt_runtime.domain.commands import CanonicalCommandEnvelope
from engine.apt_runtime.domain.events import EventEnvelope, EventType
from engine.apt_runtime.domain.fsm_spec import FsmSpec
from engine.apt_runtime.domain.reducer import replay
from engine.apt_runtime.domain.state import AptCycleState, state_hash
from engine.apt_runtime.domain.state_codec import STATE_CODEC_VERSION, encode_state
from engine.apt_runtime.ports.event_store import (
    AppendResult,
    CommandIdConflict,
    CommandReceiptDraft,
    EventStore,
    OutboxRecord,
    Snapshot,
    StoreConflict,
    StoreCorruption,
)


class DurableKernelError(ValueError):
    """A decision violates the trusted application-boundary contract."""


class DecisionOutcome(str, Enum):
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    NOOP = "NOOP"


@dataclass(frozen=True, slots=True)
class EffectRequest:
    """One value from which the queue event and executable outbox row are bound."""

    queued_event: EventEnvelope
    outbox_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.queued_event, EventEnvelope):
            raise DurableKernelError("queued_event must be an EventEnvelope")
        if self.queued_event.event_type is not EventType.EFFECT_QUEUED:
            raise DurableKernelError("EffectRequest must contain an EffectQueued event")
        if self.queued_event.effect_id is None:
            raise DurableKernelError("EffectQueued must carry an effect_id")
        if not isinstance(self.outbox_id, str) or not self.outbox_id:
            raise DurableKernelError("outbox_id must be a non-empty string")

    def to_outbox(self, command: CanonicalCommandEnvelope) -> OutboxRecord:
        """Derive executable bytes from the exact canonical queued-event payload."""

        return OutboxRecord.create(
            outbox_id=self.outbox_id,
            stream_id=command.cycle_id,
            effect_id=self.queued_event.effect_id or "",
            command_id=command.command_id,
            payload=self.queued_event.payload,
            created_at=self.queued_event.created_at,
        )


@dataclass(frozen=True, slots=True)
class CommandDecision:
    """Typed result emitted by trusted decision code before reducer validation."""

    outcome: DecisionOutcome
    facts: tuple[EventEnvelope, ...]
    effects: tuple[EffectRequest, ...]
    response: Mapping[str, CanonicalValue]

    def __post_init__(self) -> None:
        try:
            outcome = DecisionOutcome(self.outcome)
            response = as_mapping(deep_freeze(self.response))
        except (CanonicalEncodingError, ValueError) as exc:
            raise DurableKernelError(f"invalid command decision: {exc}") from exc
        facts = tuple(self.facts)
        effects = tuple(self.effects)
        if any(not isinstance(event, EventEnvelope) for event in facts):
            raise DurableKernelError("facts must contain only EventEnvelope values")
        if any(event.event_type is EventType.EFFECT_QUEUED for event in facts):
            raise DurableKernelError("EffectQueued must be supplied through EffectRequest")
        if any(not isinstance(effect, EffectRequest) for effect in effects):
            raise DurableKernelError("effects must contain only EffectRequest values")
        if outcome is DecisionOutcome.ACCEPTED and not facts and not effects:
            raise DurableKernelError("an accepted decision must emit at least one event")
        if outcome is not DecisionOutcome.ACCEPTED and (facts or effects):
            raise DurableKernelError("rejected/no-op decisions cannot emit events or effects")
        object.__setattr__(self, "outcome", outcome)
        object.__setattr__(self, "facts", facts)
        object.__setattr__(self, "effects", effects)
        object.__setattr__(self, "response", response)


class DecisionKernel(Protocol):
    """Trusted, deterministic command evaluator injected into ``DurableKernel``."""

    def decide(
        self, state: AptCycleState | None, command: CanonicalCommandEnvelope
    ) -> CommandDecision: ...


class DurableKernel:
    """Sole public mutation and snapshot path for the Slice 1A runtime."""

    def __init__(self, store: EventStore, spec: FsmSpec, decider: DecisionKernel) -> None:
        if not isinstance(store, EventStore):
            raise DurableKernelError("store must implement EventStore")
        if not isinstance(spec, FsmSpec):
            raise DurableKernelError("spec must be an FsmSpec")
        self._store = store
        self._spec = spec
        self._decider = decider

    def execute(self, command: CanonicalCommandEnvelope) -> AppendResult:
        """Deduplicate first, decide from authoritative state, then CAS append."""

        if not isinstance(command, CanonicalCommandEnvelope):
            raise DurableKernelError("command must be a CanonicalCommandEnvelope")
        prior_result = self._prior_result(command)
        if prior_result is not None:
            return prior_result

        history = tuple(self._store.load(command.cycle_id))
        actual_version = 0 if not history else history[-1].stream_version
        if actual_version != command.expected_version:
            prior_result = self._prior_result(command)
            if prior_result is not None:
                return prior_result
            raise StoreConflict(command.cycle_id, command.expected_version, actual_version)
        current_state = None if not history else replay(history, self._spec)
        decision = self._decider.decide(current_state, command)
        if not isinstance(decision, CommandDecision):
            raise DurableKernelError("decision kernel must return CommandDecision")

        events = tuple(
            sorted(
                (*decision.facts, *(effect.queued_event for effect in decision.effects)),
                key=lambda event: event.stream_version,
            )
        )
        self._validate_event_metadata(command, events)
        if events:
            replay((*history, *events), self._spec)
        outbox = tuple(effect.to_outbox(command) for effect in decision.effects)
        response = {
            "outcome": decision.outcome.value,
            "result": decision.response,
        }
        receipt = CommandReceiptDraft.create(
            command=command,
            response=response,
            created_at=command.issued_at,
        )
        try:
            return self._store.append(
                command.cycle_id,
                command.expected_version,
                events,
                outbox,
                receipt,
            )
        except StoreConflict:
            prior_result = self._prior_result(command)
            if prior_result is not None:
                return prior_result
            raise

    def create_snapshot(
        self, stream_id: str, *, created_at: str, version: int | None = None
    ) -> Snapshot:
        """Replay an authoritative prefix and persist only the derived state bytes."""

        history = tuple(self._store.load(stream_id))
        target_version = len(history) if version is None else version
        if (
            isinstance(target_version, bool)
            or not isinstance(target_version, int)
            or target_version < 1
            or target_version > len(history)
        ):
            raise DurableKernelError("snapshot version must identify a durable event prefix")
        state = replay(history[:target_version], self._spec)
        blob = encode_state(state)
        snapshot = Snapshot(
            stream_id=stream_id,
            stream_version=target_version,
            fsm_spec_hash=state.fsm_spec_hash,
            codec_version=STATE_CODEC_VERSION,
            state_hash=state_hash(state),
            state_blob=blob,
            created_at=created_at,
        )
        self._store.save_snapshot(snapshot)
        return snapshot

    def load_snapshot(self, stream_id: str) -> Snapshot | None:
        """Trust a stored snapshot only after replaying its exact event prefix."""

        snapshot = self._store.load_snapshot(stream_id)
        if snapshot is None:
            return None
        history = tuple(self._store.load(stream_id))
        if snapshot.stream_version > len(history):
            raise StoreCorruption("snapshot version exceeds the authoritative event prefix")
        state = replay(history[: snapshot.stream_version], self._spec)
        expected_blob = encode_state(state)
        if snapshot.state_blob != expected_blob or snapshot.state_hash != state_hash(state):
            raise StoreCorruption("snapshot state differs from authoritative event-prefix replay")
        return snapshot

    def _validate_event_metadata(
        self, command: CanonicalCommandEnvelope, events: tuple[EventEnvelope, ...]
    ) -> None:
        expected_versions = tuple(
            range(command.expected_version + 1, command.expected_version + len(events) + 1)
        )
        if tuple(event.stream_version for event in events) != expected_versions:
            raise DurableKernelError("decision events must form the next contiguous version prefix")
        for event in events:
            if event.stream_id != command.cycle_id or event.cycle_id != command.cycle_id:
                raise DurableKernelError("event stream/cycle identity differs from command")
            if event.command_id != command.command_id:
                raise DurableKernelError("event command_id differs from command")
            if event.actor != command.actor:
                raise DurableKernelError("event actor differs from command")
            if event.correlation_id != command.correlation_id:
                raise DurableKernelError("event correlation_id differs from command")
            if event.causation_id != command.causation_id:
                raise DurableKernelError("event causation_id differs from command")
            if event.fsm_spec_hash != self._spec.spec_hash:
                raise DurableKernelError("event FSM specification differs from kernel pin")

    def _prior_result(self, command: CanonicalCommandEnvelope) -> AppendResult | None:
        prior = self._store.load_command_receipt(command.command_id)
        if prior is None:
            return None
        if prior.stream_id != command.cycle_id or prior.command_hash != command.command_hash:
            raise CommandIdConflict(
                f"command_id {command.command_id!r} was reused with different semantics"
            )
        return AppendResult(
            new_version=prior.committed_version,
            receipt=prior,
            deduplicated=True,
        )


__all__ = [
    "CommandDecision",
    "DecisionKernel",
    "DecisionOutcome",
    "DurableKernel",
    "DurableKernelError",
    "EffectRequest",
]
