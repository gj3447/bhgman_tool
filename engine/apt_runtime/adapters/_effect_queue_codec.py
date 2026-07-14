"""Canonical row codec shared by SQLite/PostgreSQL effect queues.

# KG: apt-tpa-legion-engine-canon-2026-06-12
# Design: ADRs/apt-vnext-slice2-effect-runtime-2026-07-14.md
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import cast

from engine.apt_runtime.domain.canonical import (
    CanonicalEncodingError,
    canonical_json_bytes,
    canonical_sha256,
    deep_freeze,
)
from engine.apt_runtime.domain.effect_runtime import (
    ResourceAccess,
    ResourceClaim,
    RuntimeBudget,
    RuntimeUsage,
)
from engine.apt_runtime.ports.effect_queue import (
    EffectQueueCorruption,
    LeaseRecord,
    LeaseStatus,
    ReconciliationProbeConclusion,
    ReconciliationProbePermit,
    ReconciliationProbePermitState,
)

from ._store_codec import RowLike, immutable_bytes


def _document(blob: object, location: str) -> object:
    raw = immutable_bytes(blob, location)
    try:
        document = json.loads(raw.decode("utf-8"))
        if canonical_json_bytes(document) != raw:
            raise EffectQueueCorruption(f"{location} is not canonical apt-canonical-json-v1")
        return document
    except EffectQueueCorruption:
        raise
    except (CanonicalEncodingError, UnicodeError, ValueError, TypeError, RecursionError) as exc:
        raise EffectQueueCorruption(f"{location} is invalid canonical JSON: {exc}") from exc


def encode_claims(claims: tuple[ResourceClaim, ...]) -> tuple[bytes, str]:
    """Encode normalized resource claims and their canonical digest."""

    blob = canonical_json_bytes(claims)
    return blob, canonical_sha256(claims)


def decode_claims(blob: object, digest: object) -> tuple[ResourceClaim, ...]:
    """Decode exact typed claims and reject row/JSON divergence."""

    document = _document(blob, "lease.claims_json")
    if not isinstance(document, list):
        raise EffectQueueCorruption("lease.claims_json must contain an array")
    claims: list[ResourceClaim] = []
    try:
        for index, raw in enumerate(document):
            if not isinstance(raw, Mapping) or set(raw) != {"resource_key", "access"}:
                raise EffectQueueCorruption(
                    f"lease.claims_json[{index}] must contain resource_key/access"
                )
            claims.append(
                ResourceClaim(
                    resource_key=cast(str, raw["resource_key"]),
                    access=ResourceAccess(raw["access"]),
                )
            )
    except (TypeError, ValueError) as exc:
        raise EffectQueueCorruption(f"lease.claims_json is invalid: {exc}") from exc
    result = tuple(sorted(claims, key=canonical_json_bytes))
    if canonical_json_bytes(result) != immutable_bytes(blob, "lease.claims_json"):
        raise EffectQueueCorruption("lease.claims_json is not normalized")
    if not isinstance(digest, str) or canonical_sha256(result) != digest:
        raise EffectQueueCorruption("lease claims_hash does not match claims_json")
    return result


def encode_budget(budget: RuntimeBudget) -> tuple[bytes, str]:
    """Encode an immutable runtime budget and its digest."""

    blob = canonical_json_bytes(budget)
    return blob, canonical_sha256(budget)


def decode_budget(blob: object, digest: object) -> RuntimeBudget:
    """Decode an exact typed budget and reject row/JSON divergence."""

    document = _document(blob, "lease.budget_json")
    expected = {
        "max_attempts",
        "max_runtime_seconds",
        "max_cost_units",
        "max_no_progress",
        "max_reconciliation_probes",
    }
    if not isinstance(document, Mapping) or set(document) != expected:
        raise EffectQueueCorruption("lease.budget_json has an incompatible field set")
    try:
        budget = RuntimeBudget(**document)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise EffectQueueCorruption(f"lease.budget_json is invalid: {exc}") from exc
    if not isinstance(digest, str) or canonical_sha256(budget) != digest:
        raise EffectQueueCorruption("lease budget_hash does not match budget_json")
    return budget


def encode_usage(usage: RuntimeUsage) -> tuple[bytes, str]:
    """Encode an immutable accumulated runtime usage snapshot and digest."""

    blob = canonical_json_bytes(usage)
    return blob, canonical_sha256(usage)


def encode_probe_conclusion(
    conclusion: ReconciliationProbeConclusion,
) -> tuple[bytes, str]:
    """Encode one crash-resumable reconciliation observation."""

    blob = canonical_json_bytes(conclusion)
    return blob, conclusion.conclusion_hash


def decode_probe_conclusion(blob: object, digest: object) -> ReconciliationProbeConclusion:
    """Decode and hash-check one sealed reconciliation observation."""

    document = _document(blob, "lease.probe_conclusion_json")
    expected = {"outcome", "evidence_refs", "reason", "result_ref", "result_hash"}
    if not isinstance(document, Mapping) or set(document) != expected:
        raise EffectQueueCorruption("probe conclusion has an incompatible field set")
    try:
        evidence = document["evidence_refs"]
        conclusion = ReconciliationProbeConclusion(
            outcome=document["outcome"],  # type: ignore[arg-type]
            evidence_refs=tuple(evidence) if isinstance(evidence, list) else evidence,  # type: ignore[arg-type]
            reason=document["reason"],  # type: ignore[arg-type]
            result_ref=document["result_ref"],  # type: ignore[arg-type]
            result_hash=document["result_hash"],  # type: ignore[arg-type]
        )
    except (TypeError, ValueError) as exc:
        raise EffectQueueCorruption(f"probe conclusion is invalid: {exc}") from exc
    if not isinstance(digest, str) or conclusion.conclusion_hash != digest:
        raise EffectQueueCorruption("probe conclusion hash does not match its document")
    return conclusion


def decode_usage(blob: object, digest: object) -> RuntimeUsage:
    """Decode exact typed usage and reject row/JSON divergence."""

    document = _document(blob, "usage.usage_json")
    expected = {
        "attempts",
        "runtime_seconds",
        "cost_units",
        "no_progress",
        "reconciliation_probes",
        "progress_signature",
    }
    if not isinstance(document, Mapping) or set(document) != expected:
        raise EffectQueueCorruption("usage.usage_json has an incompatible field set")
    try:
        usage = RuntimeUsage(**document)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise EffectQueueCorruption(f"usage.usage_json is invalid: {exc}") from exc
    if not isinstance(digest, str) or canonical_sha256(usage) != digest:
        raise EffectQueueCorruption("usage usage_hash does not match usage_json")
    return usage


def lease_from_row(row: RowLike, claims: tuple[ResourceClaim, ...]) -> LeaseRecord:
    """Decode a lease row and cross-check its normalized claim rows."""

    decoded_claims = decode_claims(row["claims_json"], row["claims_hash"])
    if decoded_claims != claims:
        raise EffectQueueCorruption("lease resource rows differ from claims_json")
    try:
        return LeaseRecord(
            outbox_id=cast(str, row["outbox_id"]),
            stream_id=cast(str, row["stream_id"]),
            effect_id=cast(str, row["effect_id"]),
            lease_token=cast(str, row["lease_token"]),
            lease_epoch=cast(int, row["lease_epoch"]),
            lease_owner=cast(str, row["lease_owner"]),
            status=LeaseStatus(row["status"]),
            claimed_at=cast(str, row["claimed_at"]),
            activated_at=cast(str | None, row["activated_at"]),
            heartbeat_at=cast(str, row["heartbeat_at"]),
            lease_expiry=cast(str, row["lease_expiry"]),
            attempt=cast(int, row["attempt"]),
            resource_claims=decoded_claims,
            budget=decode_budget(row["budget_json"], row["budget_hash"]),
            grant_ref=cast(str, row["grant_ref"]),
            grant_hash=cast(str, row["grant_hash"]),
            config_version=cast(str, row["config_version"]),
            authorization_ref=cast(str, row["authorization_ref"]),
            authorization_hash=cast(str, row["authorization_hash"]),
            probe_generation=cast(int, row["probe_generation"]),
            probe_permit=_probe_permit_from_row(row),
            reconciliation_ref=cast(str | None, row["reconciliation_ref"]),
            reason=cast(str | None, row["reason"]),
            completed_at=cast(str | None, row["completed_at"]),
        )
    except (TypeError, ValueError) as exc:
        raise EffectQueueCorruption(f"stored effect lease is invalid: {exc}") from exc


def _probe_permit_from_row(row: RowLike) -> ReconciliationProbePermit | None:
    values = {
        "permit_token": row["probe_token"],
        "state": row["probe_state"],
        "acquired_at": row["probe_acquired_at"],
        "expires_at": row["probe_expires_at"],
        "concluded_at": row["probe_concluded_at"],
        "conclusion_json": row["probe_conclusion_json"],
        "conclusion_hash": row["probe_conclusion_hash"],
    }
    if all(value is None for value in values.values()):
        return None
    required = ("permit_token", "state", "acquired_at", "expires_at")
    if any(values[name] is None for name in required):
        raise EffectQueueCorruption("stored reconciliation probe permit is incomplete")
    try:
        return ReconciliationProbePermit(
            permit_token=cast(str, values["permit_token"]),
            generation=cast(int, row["probe_generation"]),
            state=ReconciliationProbePermitState(values["state"]),
            acquired_at=cast(str, values["acquired_at"]),
            expires_at=cast(str, values["expires_at"]),
            concluded_at=cast(str | None, values["concluded_at"]),
            conclusion=(
                None
                if values["conclusion_json"] is None and values["conclusion_hash"] is None
                else decode_probe_conclusion(values["conclusion_json"], values["conclusion_hash"])
            ),
        )
    except (TypeError, ValueError) as exc:
        raise EffectQueueCorruption(
            f"stored reconciliation probe permit is invalid: {exc}"
        ) from exc


def journal_detail(value: object) -> tuple[bytes, str]:
    """Return canonical immutable journal detail bytes and digest."""

    frozen = deep_freeze(value)
    return canonical_json_bytes(frozen), canonical_sha256(frozen)


__all__ = [
    "decode_budget",
    "decode_claims",
    "decode_usage",
    "decode_probe_conclusion",
    "encode_budget",
    "encode_claims",
    "encode_usage",
    "encode_probe_conclusion",
    "journal_detail",
    "lease_from_row",
]
