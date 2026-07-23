"""Slice 1A contract tests for canonical state snapshots and persistence DTOs.

# KG: apt-tpa-legion-engine-canon-2026-06-12
# KG: APT_SCW_TDAD_canonical
"""

from __future__ import annotations

import json
from abc import ABC
from dataclasses import FrozenInstanceError, replace

import pytest

from engine.apt_runtime.domain.canonical import as_mapping, canonical_json_bytes
from engine.apt_runtime.domain.commands import CanonicalCommandEnvelope
from engine.apt_runtime.domain.events import EventEnvelope
from engine.apt_runtime.domain.state import (
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
    state_hash,
)
from engine.apt_runtime.domain.state_codec import (
    STATE_CODEC_VERSION,
    StateCodecError,
    decode_state,
    encode_state,
)
from engine.apt_runtime.ports.event_store import (
    AppendResult,
    CommandReceipt,
    CommandReceiptDraft,
    EventStore,
    OutboxRecord,
    PersistenceSchemaError,
    Snapshot,
)


NOW = "2026-07-14T00:00:00Z"
HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_C = "c" * 64


def canonical_command(command_id: str = "command-1") -> CanonicalCommandEnvelope:
    return CanonicalCommandEnvelope(
        command_id=command_id,
        command_type="TestCommand",
        schema_version="1.0.0",
        cycle_id="cycle-1",
        expected_version=1,
        actor="test",
        authorization_context={"role": "test"},
        correlation_id="corr-1",
        causation_id="cause-1",
        input={"intent": "test"},
        issued_at=NOW,
    )


def representative_state() -> AptCycleState:
    generations = (
        GenerationHistory(
            generation=1,
            artifacts=(ArtifactRecord("artifact://old", HASH_A),),
            evidence_refs=("evidence-old",),
            verdict_refs=("verdict-old",),
        ),
        GenerationHistory(
            generation=2,
            artifacts=(ArtifactRecord("artifact://current", HASH_B),),
            evidence_refs=("evidence-current",),
            verdict_refs=("verdict-current",),
        ),
    )
    work_item = WorkItemState(
        work_item_id="work-é",
        kind=WorkItemKind.LEAF,
        lifecycle=WorkItemLifecycle.OPEN,
        semantic_maturity=SemanticMaturity.CONTRACTED,
        realization=RealizationStatus.MATERIALIZED,
        assurance=AssuranceStatus.ACCEPTED,
        realization_effect_id="effect-1",
        current_generation=2,
        parent_ids=("parent-b", "parent-a"),
        child_ids=(),
        generations=generations,
    )
    effect = EffectState(
        effect_id="effect-1",
        lifecycle=EffectLifecycle.SUCCEEDED,
        work_item_id="work-é",
        generation=2,
        capability="artifact.realize",
        provider="Hades",
        risk_class="REVERSIBLE_WRITE",
        idempotency_key="idem-1",
        input_ref="contract://1",
        input_hash=HASH_C,
        result_ref="artifact://current",
        result_hash=HASH_B,
    )
    return AptCycleState(
        cycle_id="cycle-é",
        lifecycle=CycleLifecycle.ACTIVE,
        version=9,
        fsm_spec_hash=HASH_A,
        config_version="config-v1",
        config_snapshot_ref="config://v1",
        config_snapshot_hash=HASH_B,
        canon_snapshot_ref="kg://snapshot/1",
        canon_snapshot_hash=HASH_C,
        work_items=(work_item,),
        effects=(effect,),
    )


def test_state_codec_round_trips_exact_canonical_bytes_and_hash() -> None:
    state = representative_state()

    blob = encode_state(state)
    restored = decode_state(blob)

    assert blob == canonical_json_bytes(state)
    assert restored == state
    assert encode_state(restored) == blob
    assert state_hash(restored) == state_hash(state)


def test_state_codec_normalizes_before_encoding_but_rejects_noncanonical_blob() -> None:
    normalized = representative_state()
    nfd_state = replace(normalized, cycle_id="cycle-e\u0301")
    assert encode_state(nfd_state) == encode_state(normalized)

    pretty = json.dumps(
        json.loads(encode_state(normalized)), ensure_ascii=False, sort_keys=True, indent=2
    ).encode()
    with pytest.raises(StateCodecError, match="canonical"):
        decode_state(pretty)


@pytest.mark.parametrize(
    ("mutate", "match"),
    [
        (lambda doc: doc.update({"unexpected": "field"}), "unexpected"),
        (lambda doc: doc.pop("config_version"), "missing"),
        (lambda doc: doc.update({"version": True}), "version"),
        (lambda doc: doc.update({"lifecycle": "UNKNOWN"}), "lifecycle"),
        (lambda doc: doc.update({"work_items": "not-a-list"}), "work_items"),
    ],
)
def test_state_codec_rejects_structural_schema_drift(mutate, match: str) -> None:
    document = json.loads(encode_state(representative_state()))
    mutate(document)
    blob = canonical_json_bytes(document)

    with pytest.raises(StateCodecError, match=match):
        decode_state(blob)


@pytest.mark.parametrize(
    "blob",
    [
        b"\xff",
        b'{"version":1.5}',
        b'{"cycle_id":"first","cycle_id":"second"}',
        b"[]",
    ],
)
def test_state_codec_rejects_invalid_utf8_numbers_duplicate_keys_and_non_object(
    blob: bytes,
) -> None:
    with pytest.raises(StateCodecError):
        decode_state(blob)


def test_state_codec_rejects_non_bytes_and_non_state_inputs() -> None:
    with pytest.raises(StateCodecError, match="bytes"):
        decode_state("not-bytes")  # type: ignore[arg-type]
    with pytest.raises(StateCodecError, match="AptCycleState"):
        encode_state({"cycle_id": "cycle-1"})  # type: ignore[arg-type]


def test_outbox_record_is_canonical_deeply_immutable_and_hash_checked() -> None:
    record = OutboxRecord.create(
        outbox_id="outbox-e\u0301",
        stream_id="cycle-e\u0301",
        effect_id="effect-1",
        command_id="command-1",
        payload={"nested": {"b": 2, "a": [1, "e\u0301"]}},
        created_at=NOW,
    )

    assert record.outbox_id == "outbox-é"
    assert record.stream_id == "cycle-é"
    assert as_mapping(record.payload["nested"])["a"] == (1, "é")
    with pytest.raises(TypeError):
        record.payload["new"] = "value"  # type: ignore[index]
    with pytest.raises(PersistenceSchemaError, match="payload_hash"):
        replace(record, payload_hash=HASH_A)


def test_receipt_dtos_validate_hashes_identity_order_and_immutability() -> None:
    draft = CommandReceiptDraft.create(
        command=replace(canonical_command(), expected_version=0),
        response={"status": "accepted", "version": 2},
        created_at=NOW,
    )
    receipt = CommandReceipt.from_draft(
        draft,
        stream_id="cycle-1",
        committed_version=2,
        event_ids=("event-1", "event-2"),
        outbox_ids=("outbox-1",),
    )
    result = AppendResult(new_version=2, receipt=receipt, deduplicated=False)

    assert result.receipt.response["status"] == "accepted"
    assert result.receipt.event_ids == ("event-1", "event-2")
    with pytest.raises(FrozenInstanceError):
        result.new_version = 3  # type: ignore[misc]
    with pytest.raises(PersistenceSchemaError, match="unique"):
        replace(receipt, event_ids=("event-1", "event-1"))
    with pytest.raises(PersistenceSchemaError, match="committed_version"):
        AppendResult(new_version=3, receipt=receipt, deduplicated=False)


@pytest.mark.parametrize(
    "factory",
    [
        lambda: OutboxRecord.create(
            outbox_id="outbox-1",
            stream_id="cycle-1",
            effect_id="effect-1",
            command_id="command-1",
            payload={},
            created_at="2026-07-14T09:00:00+09:00",
        ),
        lambda: CommandReceiptDraft.create(
            command="not-a-command",  # type: ignore[arg-type]
            response={},
            created_at=NOW,
        ),
        lambda: CommandReceiptDraft.create(
            command=canonical_command(),
            response={"invalid": 1.5},
            created_at=NOW,
        ),
    ],
)
def test_persistence_dtos_fail_closed_on_invalid_time_hash_and_identity(factory) -> None:
    with pytest.raises(PersistenceSchemaError):
        factory()


def test_snapshot_binds_canonical_blob_hash_version_and_codec() -> None:
    state = representative_state()
    blob = encode_state(state)
    snapshot = Snapshot(
        stream_id=state.cycle_id,
        stream_version=state.version,
        fsm_spec_hash=state.fsm_spec_hash,
        codec_version=STATE_CODEC_VERSION,
        state_hash=state_hash(state),
        state_blob=blob,
        created_at=NOW,
    )

    assert decode_state(snapshot.state_blob) == state
    with pytest.raises(PersistenceSchemaError, match="state_hash"):
        replace(snapshot, state_hash=HASH_B)
    with pytest.raises(PersistenceSchemaError, match="codec_version"):
        replace(snapshot, codec_version="pickle-v1")


def test_event_store_is_an_abstract_port_with_no_default_io() -> None:
    assert issubclass(EventStore, ABC)
    with pytest.raises(TypeError):
        EventStore()  # type: ignore[abstract]

    abstract_methods = {
        "init_schema",
        "load",
        "append",
        "load_command_receipt",
        "load_outbox",
        "load_snapshot",
        "save_snapshot",
        "close",
    }
    assert abstract_methods <= EventStore.__abstractmethods__


def test_event_store_append_contract_mentions_domain_envelopes() -> None:
    annotations = EventStore.append.__annotations__
    assert annotations["events"] != list[dict]
    assert EventEnvelope.__name__ in str(annotations["events"])
