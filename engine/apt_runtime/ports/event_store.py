"""Persistence contract for the APT vNext durable event kernel.

The port owns persistence-level atomicity and optimistic concurrency, not
domain transitions.  Implementations must commit an accepted event batch, its
command receipt, and requested-effect outbox rows in one transaction.

# KG: apt-tpa-legion-engine-canon-2026-06-12
# KG: APT_SCW_TDAD_canonical
"""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from engine.apt_runtime.domain.canonical import (
    CanonicalEncodingError,
    CanonicalValue,
    as_mapping,
    canonical_sha256,
    deep_freeze,
    normalize_text,
)
from engine.apt_runtime.domain.commands import CanonicalCommandEnvelope
from engine.apt_runtime.domain.events import (
    EventEnvelope,
    EventSchemaError,
    validate_rfc3339_utc_z,
)
from engine.apt_runtime.domain.state import state_hash
from engine.apt_runtime.domain.state_codec import (
    STATE_CODEC_VERSION,
    StateCodecError,
    decode_state,
)


class PersistenceSchemaError(ValueError):
    """Raised before I/O when a persistence DTO violates the durable contract."""


class StoreError(RuntimeError):
    """Base class for persistence adapter failures."""


class StoreConflict(StoreError):
    """Optimistic stream-version mismatch with structured conflict evidence."""

    def __init__(self, stream_id: str, expected_version: int, actual_version: int) -> None:
        self.stream_id = stream_id
        self.expected_version = expected_version
        self.actual_version = actual_version
        super().__init__(
            f"stream {stream_id!r} expected version {expected_version}, "
            f"actual version {actual_version}"
        )


class CommandIdConflict(StoreError):
    """A command ID was reused for a different stream or canonical command hash."""


class StreamBindingConflict(StoreError):
    """A non-retryable FSM specification or configuration pin mismatch."""

    def __init__(
        self,
        stream_id: str,
        *,
        stream_fsm_spec_hash: str,
        candidate_fsm_spec_hash: str,
        stream_config_version: str,
        candidate_config_version: str,
    ) -> None:
        self.stream_id = stream_id
        self.stream_fsm_spec_hash = stream_fsm_spec_hash
        self.candidate_fsm_spec_hash = candidate_fsm_spec_hash
        self.stream_config_version = stream_config_version
        self.candidate_config_version = candidate_config_version
        super().__init__(
            f"stream {stream_id!r} is pinned to FSM/config "
            f"{stream_fsm_spec_hash}/{stream_config_version}, not "
            f"{candidate_fsm_spec_hash}/{candidate_config_version}"
        )


class StoreCorruption(StoreError):
    """Stored bytes fail their schema, canonical hash, or envelope validation."""


def _text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value:
        raise PersistenceSchemaError(f"{name} must be a non-empty string")
    return normalize_text(value)


def _positive_integer(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise PersistenceSchemaError(f"{name} must be a positive integer")
    return value


def _nonnegative_integer(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise PersistenceSchemaError(f"{name} must be a non-negative integer")
    return value


def _hash(name: str, value: object) -> str:
    text = _text(name, value)
    if len(text) != 64 or any(character not in "0123456789abcdef" for character in text):
        raise PersistenceSchemaError(f"{name} must be a lowercase SHA-256 hex digest")
    return text


def _timestamp(name: str, value: object) -> str:
    text = _text(name, value)
    try:
        validate_rfc3339_utc_z(name, text)
    except EventSchemaError as exc:
        raise PersistenceSchemaError(str(exc)) from exc
    return text


def _mapping(name: str, value: object) -> Mapping[str, CanonicalValue]:
    try:
        return as_mapping(deep_freeze(value))
    except CanonicalEncodingError as exc:
        raise PersistenceSchemaError(f"{name} is not canonical JSON: {exc}") from exc


def _identity_tuple(name: str, values: tuple[str, ...], *, nonempty: bool) -> tuple[str, ...]:
    if not isinstance(values, tuple):
        raise PersistenceSchemaError(f"{name} must be a tuple")
    normalized = tuple(_text(f"{name}[{index}]", value) for index, value in enumerate(values))
    if nonempty and not normalized:
        raise PersistenceSchemaError(f"{name} must contain at least one identity")
    if len(set(normalized)) != len(normalized):
        raise PersistenceSchemaError(f"{name} identities must be unique")
    return normalized


@dataclass(frozen=True, slots=True)
class OutboxRecord:
    """Immutable requested-effect payload inserted atomically with domain events."""

    outbox_id: str
    stream_id: str
    effect_id: str
    command_id: str
    payload: Mapping[str, CanonicalValue]
    payload_hash: str
    created_at: str

    def __post_init__(self) -> None:
        for name in ("outbox_id", "stream_id", "effect_id", "command_id"):
            object.__setattr__(self, name, _text(name, getattr(self, name)))
        frozen = _mapping("payload", self.payload)
        object.__setattr__(self, "payload", frozen)
        supplied_hash = _hash("payload_hash", self.payload_hash)
        calculated_hash = canonical_sha256(frozen)
        if supplied_hash != calculated_hash:
            raise PersistenceSchemaError("payload_hash does not match canonical outbox payload")
        object.__setattr__(self, "payload_hash", supplied_hash)
        object.__setattr__(self, "created_at", _timestamp("created_at", self.created_at))

    @classmethod
    def create(
        cls,
        *,
        outbox_id: str,
        stream_id: str,
        effect_id: str,
        command_id: str,
        payload: Mapping[str, object],
        created_at: str,
    ) -> "OutboxRecord":
        """Create an outbox row and derive its canonical payload digest."""

        frozen = _mapping("payload", payload)
        return cls(
            outbox_id=outbox_id,
            stream_id=stream_id,
            effect_id=effect_id,
            command_id=command_id,
            payload=frozen,
            payload_hash=canonical_sha256(frozen),
            created_at=created_at,
        )


@dataclass(frozen=True, slots=True, init=False)
class CommandReceiptDraft:
    """Caller-supplied immutable command identity and deterministic response."""

    command_id: str
    command_hash: str
    response: Mapping[str, CanonicalValue]
    response_hash: str
    created_at: str

    def __init__(
        self,
        *,
        command: CanonicalCommandEnvelope,
        response: Mapping[str, object],
        created_at: str,
    ) -> None:
        if not isinstance(command, CanonicalCommandEnvelope):
            raise PersistenceSchemaError("command must be a CanonicalCommandEnvelope")
        frozen = _mapping("response", response)
        object.__setattr__(self, "command_id", command.command_id)
        object.__setattr__(self, "command_hash", command.command_hash)
        object.__setattr__(self, "response", frozen)
        object.__setattr__(self, "response_hash", canonical_sha256(frozen))
        object.__setattr__(self, "created_at", _timestamp("created_at", created_at))

    @classmethod
    def create(
        cls,
        *,
        command: CanonicalCommandEnvelope,
        response: Mapping[str, object],
        created_at: str,
    ) -> "CommandReceiptDraft":
        """Create a draft and derive its canonical response digest."""

        frozen = _mapping("response", response)
        return cls(
            command=command,
            response=frozen,
            created_at=created_at,
        )


@dataclass(frozen=True, slots=True)
class CommandReceipt:
    """Durable idempotency receipt returned for first commit and every retry."""

    command_id: str
    stream_id: str
    command_hash: str
    committed_version: int
    event_ids: tuple[str, ...]
    outbox_ids: tuple[str, ...]
    response: Mapping[str, CanonicalValue]
    response_hash: str
    created_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "command_id", _text("command_id", self.command_id))
        object.__setattr__(self, "stream_id", _text("stream_id", self.stream_id))
        object.__setattr__(self, "command_hash", _hash("command_hash", self.command_hash))
        object.__setattr__(
            self,
            "committed_version",
            _nonnegative_integer("committed_version", self.committed_version),
        )
        object.__setattr__(
            self, "event_ids", _identity_tuple("event_ids", self.event_ids, nonempty=False)
        )
        object.__setattr__(
            self, "outbox_ids", _identity_tuple("outbox_ids", self.outbox_ids, nonempty=False)
        )
        frozen = _mapping("response", self.response)
        object.__setattr__(self, "response", frozen)
        supplied_hash = _hash("response_hash", self.response_hash)
        if supplied_hash != canonical_sha256(frozen):
            raise PersistenceSchemaError("response_hash does not match canonical response")
        object.__setattr__(self, "response_hash", supplied_hash)
        object.__setattr__(self, "created_at", _timestamp("created_at", self.created_at))

    @classmethod
    def from_draft(
        cls,
        draft: CommandReceiptDraft,
        *,
        stream_id: str,
        committed_version: int,
        event_ids: tuple[str, ...],
        outbox_ids: tuple[str, ...] = (),
    ) -> "CommandReceipt":
        """Bind a validated draft to the exact rows committed by the store."""

        if not isinstance(draft, CommandReceiptDraft):
            raise PersistenceSchemaError("draft must be a CommandReceiptDraft")
        return cls(
            command_id=draft.command_id,
            stream_id=stream_id,
            command_hash=draft.command_hash,
            committed_version=committed_version,
            event_ids=event_ids,
            outbox_ids=outbox_ids,
            response=draft.response,
            response_hash=draft.response_hash,
            created_at=draft.created_at,
        )


@dataclass(frozen=True, slots=True)
class Snapshot:
    """A self-validating canonical aggregate snapshot; never the state authority."""

    stream_id: str
    stream_version: int
    fsm_spec_hash: str
    codec_version: str
    state_hash: str
    state_blob: bytes
    created_at: str

    def __post_init__(self) -> None:
        stream_id = _text("stream_id", self.stream_id)
        stream_version = _positive_integer("stream_version", self.stream_version)
        fsm_spec_hash = _hash("fsm_spec_hash", self.fsm_spec_hash)
        codec_version = _text("codec_version", self.codec_version)
        if codec_version != STATE_CODEC_VERSION:
            raise PersistenceSchemaError(
                f"codec_version must be {STATE_CODEC_VERSION!r}, got {codec_version!r}"
            )
        state_digest = _hash("state_hash", self.state_hash)
        if type(self.state_blob) is not bytes:
            raise PersistenceSchemaError("state_blob must be immutable bytes")
        if hashlib.sha256(self.state_blob).hexdigest() != state_digest:
            raise PersistenceSchemaError("state_hash does not match state_blob")
        try:
            state = decode_state(self.state_blob)
        except StateCodecError as exc:
            raise PersistenceSchemaError(
                f"state_blob is not a valid canonical snapshot: {exc}"
            ) from exc
        if state.cycle_id != stream_id:
            raise PersistenceSchemaError("snapshot stream_id does not match encoded cycle_id")
        if state.version != stream_version:
            raise PersistenceSchemaError(
                "snapshot stream_version does not match encoded aggregate version"
            )
        if state.fsm_spec_hash != fsm_spec_hash:
            raise PersistenceSchemaError(
                "snapshot fsm_spec_hash does not match encoded aggregate specification"
            )
        if state_hash(state) != state_digest:
            raise PersistenceSchemaError("snapshot state_hash disagrees with decoded aggregate")
        object.__setattr__(self, "stream_id", stream_id)
        object.__setattr__(self, "stream_version", stream_version)
        object.__setattr__(self, "fsm_spec_hash", fsm_spec_hash)
        object.__setattr__(self, "codec_version", codec_version)
        object.__setattr__(self, "state_hash", state_digest)
        object.__setattr__(self, "created_at", _timestamp("created_at", self.created_at))


@dataclass(frozen=True, slots=True)
class AppendResult:
    """Outcome of a first commit or an idempotent command retry."""

    new_version: int
    receipt: CommandReceipt
    deduplicated: bool

    def __post_init__(self) -> None:
        version = _nonnegative_integer("new_version", self.new_version)
        if not isinstance(self.receipt, CommandReceipt):
            raise PersistenceSchemaError("receipt must be a CommandReceipt")
        if type(self.deduplicated) is not bool:
            raise PersistenceSchemaError("deduplicated must be a bool")
        if self.receipt.committed_version != version:
            raise PersistenceSchemaError("new_version must equal receipt.committed_version")
        object.__setattr__(self, "new_version", version)


class EventStore(ABC):
    """Storage-independent compare-and-append port for one-cycle event streams.

    # KG: apt-tpa-legion-engine-canon-2026-06-12
    # KG: APT_SCW_TDAD_canonical
    """

    @abstractmethod
    def init_schema(self) -> None:
        """Create or validate the adapter's versioned schema."""

    @abstractmethod
    def load(self, stream_id: str, after_version: int = 0) -> list[EventEnvelope]:
        """Load validated envelopes strictly after *after_version*, in version order."""

    @abstractmethod
    def append(
        self,
        stream_id: str,
        expected_version: int,
        events: Sequence[EventEnvelope],
        outbox_records: Sequence[OutboxRecord],
        receipt: CommandReceiptDraft,
    ) -> AppendResult:
        """Trusted low-level CAS append used only after DurableKernel validation."""

    @abstractmethod
    def load_command_receipt(self, command_id: str) -> CommandReceipt | None:
        """Return the durable idempotency receipt for a command, if present."""

    @abstractmethod
    def load_outbox(self, stream_id: str) -> list[OutboxRecord]:
        """Read immutable requested effects; leasing belongs to the effect-runtime slice."""

    @abstractmethod
    def load_snapshot(self, stream_id: str) -> Snapshot | None:
        """Return the latest valid snapshot for the stream, if one exists."""

    @abstractmethod
    def save_snapshot(self, snapshot: Snapshot) -> None:
        """Persist a rebuildable snapshot without changing the event-stream head."""

    @abstractmethod
    def close(self) -> None:
        """Release adapter-owned resources; file adapters may implement a no-op."""


__all__ = [
    "AppendResult",
    "CommandIdConflict",
    "CommandReceipt",
    "CommandReceiptDraft",
    "EventStore",
    "OutboxRecord",
    "PersistenceSchemaError",
    "Snapshot",
    "StreamBindingConflict",
    "StoreConflict",
    "StoreCorruption",
    "StoreError",
]
