"""Strict canonical snapshot codec for the APT vNext cycle aggregate.

Snapshots are a rebuildable acceleration layer over the event log.  This codec
therefore accepts only the exact ``apt-canonical-json-v1`` representation of an
``AptCycleState``.  It never uses pickle, permissive coercion, or ambient schema
defaults that could make the same bytes mean different states after restart.

# KG: apt-tpa-legion-engine-canon-2026-06-12
# KG: APT_SCW_TDAD_canonical
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from enum import Enum
from typing import NoReturn, TypeVar, cast

from .canonical import CanonicalEncodingError, canonical_json_bytes
from .state import (
    AptCycleState,
    ArtifactRecord,
    AssuranceStatus,
    CycleLifecycle,
    EffectAttemptOutcome,
    EffectAttemptRecord,
    EffectLifecycle,
    EffectState,
    GenerationHistory,
    RealizationStatus,
    SemanticMaturity,
    WorkItemKind,
    WorkItemLifecycle,
    WorkItemState,
)


STATE_CODEC_VERSION = "apt-cycle-state-v3"


class StateCodecError(ValueError):
    """Raised when snapshot bytes are not the exact supported canonical state schema."""


E = TypeVar("E", bound=Enum)


def encode_state(state: AptCycleState) -> bytes:
    """Encode one aggregate using the same bytes used by ``state_hash``.

    # KG: apt-tpa-legion-engine-canon-2026-06-12
    # KG: APT_SCW_TDAD_canonical
    """

    if not isinstance(state, AptCycleState):
        raise StateCodecError("encode_state requires an AptCycleState")
    try:
        return canonical_json_bytes(state)
    except CanonicalEncodingError as exc:  # defensive: state constructors already constrain data
        raise StateCodecError(f"state is not canonically encodable: {exc}") from exc


def _reject_float(token: str) -> NoReturn:
    raise StateCodecError(
        f"snapshot contains non-integer JSON number {token!r}; canonical v1 forbids floats"
    )


def _reject_constant(token: str) -> NoReturn:
    raise StateCodecError(f"snapshot contains invalid JSON constant {token!r}")


def _object_without_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise StateCodecError(f"snapshot contains duplicate JSON key {key!r}")
        result[key] = value
    return result


def _mapping(value: object, path: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise StateCodecError(f"{path} must be an object")
    if any(not isinstance(key, str) for key in value):
        raise StateCodecError(f"{path} keys must be strings")
    return cast(Mapping[str, object], value)


def _sequence(value: object, path: str) -> list[object]:
    if not isinstance(value, list):
        raise StateCodecError(f"{path} must be an array")
    return value


def _keys(value: Mapping[str, object], expected: frozenset[str], path: str) -> None:
    actual = set(value)
    missing = sorted(expected - actual)
    unexpected = sorted(actual - expected)
    if missing:
        raise StateCodecError(f"{path} missing field(s): {', '.join(missing)}")
    if unexpected:
        raise StateCodecError(f"{path} unexpected field(s): {', '.join(unexpected)}")


def _text(value: object, path: str) -> str:
    if not isinstance(value, str) or not value:
        raise StateCodecError(f"{path} must be a non-empty string")
    return value


def _optional_text(value: object, path: str) -> str | None:
    return None if value is None else _text(value, path)


def _integer(value: object, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise StateCodecError(f"{path} must be an integer")
    return value


def _optional_integer(value: object, path: str) -> int | None:
    return None if value is None else _integer(value, path)


def _enum(enum_type: type[E], value: object, path: str) -> E:
    raw = _text(value, path)
    try:
        return enum_type(raw)
    except ValueError as exc:
        raise StateCodecError(f"{path} has unknown value {raw!r}") from exc


_ARTIFACT_KEYS = frozenset({"artifact_ref", "artifact_hash"})
_GENERATION_KEYS = frozenset({"generation", "artifacts", "evidence_refs", "verdict_refs"})
_WORK_ITEM_KEYS = frozenset(
    {
        "work_item_id",
        "kind",
        "lifecycle",
        "semantic_maturity",
        "realization",
        "assurance",
        "realization_effect_id",
        "current_generation",
        "parent_ids",
        "child_ids",
        "generations",
    }
)
_EFFECT_ATTEMPT_KEYS = frozenset(
    {
        "attempt",
        "lease_token",
        "lease_owner",
        "started_at",
        "outcome_history",
        "completed_at",
        "result_ref",
        "result_hash",
        "reasons",
        "reconciliation_refs",
    }
)
_EFFECT_KEYS = frozenset(
    {
        "effect_id",
        "lifecycle",
        "work_item_id",
        "generation",
        "capability",
        "provider",
        "risk_class",
        "idempotency_key",
        "input_ref",
        "input_hash",
        "result_ref",
        "result_hash",
        "lease_owner",
        "lease_token",
        "lease_expiry",
        "heartbeat_at",
        "grant_ref",
        "grant_hash",
        "authorization_ref",
        "authorization_hash",
        "lease_token_history",
        "current_attempt",
        "attempts",
        "reconciliation_refs",
        "reasons",
    }
)
_CYCLE_KEYS = frozenset(
    {
        "cycle_id",
        "lifecycle",
        "version",
        "fsm_spec_hash",
        "config_version",
        "config_snapshot_ref",
        "config_snapshot_hash",
        "canon_snapshot_ref",
        "canon_snapshot_hash",
        "work_items",
        "effects",
        "terminal_receipt_ref",
    }
)


def _text_tuple(value: object, path: str) -> tuple[str, ...]:
    return tuple(
        _text(item, f"{path}[{index}]") for index, item in enumerate(_sequence(value, path))
    )


def _artifact(value: object, path: str) -> ArtifactRecord:
    item = _mapping(value, path)
    _keys(item, _ARTIFACT_KEYS, path)
    return ArtifactRecord(
        artifact_ref=_text(item["artifact_ref"], f"{path}.artifact_ref"),
        artifact_hash=_text(item["artifact_hash"], f"{path}.artifact_hash"),
    )


def _generation(value: object, path: str) -> GenerationHistory:
    item = _mapping(value, path)
    _keys(item, _GENERATION_KEYS, path)
    return GenerationHistory(
        generation=_integer(item["generation"], f"{path}.generation"),
        artifacts=tuple(
            _artifact(artifact, f"{path}.artifacts[{index}]")
            for index, artifact in enumerate(_sequence(item["artifacts"], f"{path}.artifacts"))
        ),
        evidence_refs=_text_tuple(item["evidence_refs"], f"{path}.evidence_refs"),
        verdict_refs=_text_tuple(item["verdict_refs"], f"{path}.verdict_refs"),
    )


def _work_item(value: object, path: str) -> WorkItemState:
    item = _mapping(value, path)
    _keys(item, _WORK_ITEM_KEYS, path)
    return WorkItemState(
        work_item_id=_text(item["work_item_id"], f"{path}.work_item_id"),
        kind=_enum(WorkItemKind, item["kind"], f"{path}.kind"),
        lifecycle=_enum(WorkItemLifecycle, item["lifecycle"], f"{path}.lifecycle"),
        semantic_maturity=_enum(
            SemanticMaturity, item["semantic_maturity"], f"{path}.semantic_maturity"
        ),
        realization=_enum(RealizationStatus, item["realization"], f"{path}.realization"),
        assurance=_enum(AssuranceStatus, item["assurance"], f"{path}.assurance"),
        realization_effect_id=_optional_text(
            item["realization_effect_id"], f"{path}.realization_effect_id"
        ),
        current_generation=_integer(item["current_generation"], f"{path}.current_generation"),
        parent_ids=_text_tuple(item["parent_ids"], f"{path}.parent_ids"),
        child_ids=_text_tuple(item["child_ids"], f"{path}.child_ids"),
        generations=tuple(
            _generation(generation, f"{path}.generations[{index}]")
            for index, generation in enumerate(
                _sequence(item["generations"], f"{path}.generations")
            )
        ),
    )


def _attempt(value: object, path: str) -> EffectAttemptRecord:
    item = _mapping(value, path)
    _keys(item, _EFFECT_ATTEMPT_KEYS, path)
    return EffectAttemptRecord(
        attempt=_integer(item["attempt"], f"{path}.attempt"),
        lease_token=_text(item["lease_token"], f"{path}.lease_token"),
        lease_owner=_text(item["lease_owner"], f"{path}.lease_owner"),
        started_at=_text(item["started_at"], f"{path}.started_at"),
        outcome_history=tuple(
            _enum(EffectAttemptOutcome, outcome, f"{path}.outcome_history[{index}]")
            for index, outcome in enumerate(
                _sequence(item["outcome_history"], f"{path}.outcome_history")
            )
        ),
        completed_at=_optional_text(item["completed_at"], f"{path}.completed_at"),
        result_ref=_optional_text(item["result_ref"], f"{path}.result_ref"),
        result_hash=_optional_text(item["result_hash"], f"{path}.result_hash"),
        reasons=_text_tuple(item["reasons"], f"{path}.reasons"),
        reconciliation_refs=_text_tuple(item["reconciliation_refs"], f"{path}.reconciliation_refs"),
    )


def _effect(value: object, path: str) -> EffectState:
    item = _mapping(value, path)
    _keys(item, _EFFECT_KEYS, path)
    return EffectState(
        effect_id=_text(item["effect_id"], f"{path}.effect_id"),
        lifecycle=_enum(EffectLifecycle, item["lifecycle"], f"{path}.lifecycle"),
        work_item_id=_optional_text(item["work_item_id"], f"{path}.work_item_id"),
        generation=_optional_integer(item["generation"], f"{path}.generation"),
        capability=_text(item["capability"], f"{path}.capability"),
        provider=_text(item["provider"], f"{path}.provider"),
        risk_class=_text(item["risk_class"], f"{path}.risk_class"),
        idempotency_key=_text(item["idempotency_key"], f"{path}.idempotency_key"),
        input_ref=_text(item["input_ref"], f"{path}.input_ref"),
        input_hash=_text(item["input_hash"], f"{path}.input_hash"),
        result_ref=_optional_text(item["result_ref"], f"{path}.result_ref"),
        result_hash=_optional_text(item["result_hash"], f"{path}.result_hash"),
        lease_owner=_optional_text(item["lease_owner"], f"{path}.lease_owner"),
        lease_token=_optional_text(item["lease_token"], f"{path}.lease_token"),
        lease_expiry=_optional_text(item["lease_expiry"], f"{path}.lease_expiry"),
        heartbeat_at=_optional_text(item["heartbeat_at"], f"{path}.heartbeat_at"),
        grant_ref=_optional_text(item["grant_ref"], f"{path}.grant_ref"),
        grant_hash=_optional_text(item["grant_hash"], f"{path}.grant_hash"),
        authorization_ref=_optional_text(item["authorization_ref"], f"{path}.authorization_ref"),
        authorization_hash=_optional_text(item["authorization_hash"], f"{path}.authorization_hash"),
        lease_token_history=_text_tuple(item["lease_token_history"], f"{path}.lease_token_history"),
        current_attempt=_integer(item["current_attempt"], f"{path}.current_attempt"),
        attempts=tuple(
            _attempt(attempt, f"{path}.attempts[{index}]")
            for index, attempt in enumerate(_sequence(item["attempts"], f"{path}.attempts"))
        ),
        reconciliation_refs=_text_tuple(item["reconciliation_refs"], f"{path}.reconciliation_refs"),
        reasons=_text_tuple(item["reasons"], f"{path}.reasons"),
    )


def _cycle(value: object) -> AptCycleState:
    item = _mapping(value, "state")
    _keys(item, _CYCLE_KEYS, "state")
    return AptCycleState(
        cycle_id=_text(item["cycle_id"], "state.cycle_id"),
        lifecycle=_enum(CycleLifecycle, item["lifecycle"], "state.lifecycle"),
        version=_integer(item["version"], "state.version"),
        fsm_spec_hash=_text(item["fsm_spec_hash"], "state.fsm_spec_hash"),
        config_version=_text(item["config_version"], "state.config_version"),
        config_snapshot_ref=_text(item["config_snapshot_ref"], "state.config_snapshot_ref"),
        config_snapshot_hash=_text(item["config_snapshot_hash"], "state.config_snapshot_hash"),
        canon_snapshot_ref=_text(item["canon_snapshot_ref"], "state.canon_snapshot_ref"),
        canon_snapshot_hash=_text(item["canon_snapshot_hash"], "state.canon_snapshot_hash"),
        work_items=tuple(
            _work_item(work_item, f"state.work_items[{index}]")
            for index, work_item in enumerate(_sequence(item["work_items"], "state.work_items"))
        ),
        effects=tuple(
            _effect(effect, f"state.effects[{index}]")
            for index, effect in enumerate(_sequence(item["effects"], "state.effects"))
        ),
        terminal_receipt_ref=_optional_text(
            item["terminal_receipt_ref"], "state.terminal_receipt_ref"
        ),
    )


def decode_state(blob: bytes) -> AptCycleState:
    """Decode only byte-exact canonical v1 state and reject all schema drift.

    # KG: apt-tpa-legion-engine-canon-2026-06-12
    # KG: APT_SCW_TDAD_canonical
    """

    if type(blob) is not bytes:
        raise StateCodecError("decode_state requires immutable bytes")
    try:
        text = blob.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise StateCodecError("snapshot is not valid UTF-8") from exc
    try:
        document = json.loads(
            text,
            parse_float=_reject_float,
            parse_constant=_reject_constant,
            object_pairs_hook=_object_without_duplicates,
        )
    except StateCodecError:
        raise
    except (json.JSONDecodeError, RecursionError) as exc:
        raise StateCodecError(f"snapshot is not valid JSON: {exc}") from exc

    try:
        if canonical_json_bytes(document) != blob:
            raise StateCodecError("snapshot bytes are not canonical apt-canonical-json-v1")
        state = _cycle(document)
        if encode_state(state) != blob:
            raise StateCodecError(
                "snapshot is canonical JSON but not the canonical AptCycleState representation"
            )
        return state
    except StateCodecError:
        raise
    except (CanonicalEncodingError, TypeError, ValueError) as exc:
        raise StateCodecError(f"snapshot does not encode a valid AptCycleState: {exc}") from exc


__all__ = ["STATE_CODEC_VERSION", "StateCodecError", "decode_state", "encode_state"]
