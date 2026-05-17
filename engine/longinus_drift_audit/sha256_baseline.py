"""sha256 baseline — Longinus Wave 6 (2026-05-14) absorption.

Absorbed from SYMPOSIUM/SKILLS/bin/longinus_sha256_daemon.py (PoC) into the
bhgman_tool typed module layout. Key differences vs the PoC:
    - KgClient DIP (no curl subprocess; production swaps in Neo4jKgClient).
    - Pydantic models (typed `ReferenceSite` with sha256_status enum).
    - `init_baseline` / `verify_baseline` separated as pure functions for tests.
    - TOCTOU-safe read-once-hash-once via ``daemon.safe_read_hash``.

KG provenance:
    # KG: longinus-sha256-daemon-canonical-2026-05-06
    # KG: lesson-longinus-wave6-full-symposium-binding-2026-05-14
    # KG: ATOM_Skill_longinus (v3.3 absorption)

3 modes ⇔ 3 BX Lens Laws:
    - init   → PutGet seed: KG learns disk hash for the first time
    - verify → GetPut roundtrip: KG hash matches disk hash ⇒ no drift
    - cron   → PutPut: continuous verify, last write wins on drift resolution

Daemon-style wiring (multi-repo loop) already lives in ``daemon.py``. This
module focuses on the KG ↔ disk hash synchronization protocol itself, which
is composable with both the daemon watcher and a one-shot CLI.
"""
from __future__ import annotations

import datetime as dt
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional

from daemon import safe_read_hash
from kg_client import KgClient
from models import (
    ReferenceLayer,
    ReferenceSite,
    Sha256Status,
    SourceCodeDriftEvent,
)

logger = logging.getLogger(__name__)


# ─── Path resolution chain ────────────────────────────────────────────────


DEFAULT_FS_BASE_CHAIN: tuple[str, ...] = (
    "/Users/lagyeongjun/CD/SERVER",
    "/Users/lagyeongjun/CD/SYMPOSIUM",
    "/Users/lagyeongjun/CD/SYMPOSIUM/SKILLS",
    "/Users/lagyeongjun/CD/SYMPOSIUM/METAHUMOTONIC",
    "/Users/lagyeongjun/CD/SYMPOSIUM/THEORY",
    "/Users/lagyeongjun/CD/MIND",
    "/Users/lagyeongjun/CD/bhgman_tool",
    "/Users/lagyeongjun/CD",
)


@dataclass(frozen=True)
class PathResolution:
    """Resolved (status, abs_path) for a sourcePath candidate."""

    status: str          # 'FILE' | 'DIRECTORY' | 'MISSING'
    abs_path: Optional[str] = None


def resolve_path(
    rel_or_abs_path: str,
    *,
    base_chain: Iterable[str] = DEFAULT_FS_BASE_CHAIN,
) -> PathResolution:
    """Resolve a `sourcePath` (possibly relative) to a real disk location.

    Tries: absolute → ~ expansion → each base_chain entry.
    Returns FILE if any candidate is a regular file, DIRECTORY if a directory,
    MISSING otherwise.
    """
    # Strip ":line" suffix if present (sourcePath = "file:line(-end)")
    bare_path = rel_or_abs_path.split(":", 1)[0]
    expanded = os.path.expanduser(bare_path)
    if os.path.isabs(expanded):
        candidates = [expanded]
    else:
        candidates = [os.path.join(b, bare_path) for b in base_chain]
    for path in candidates:
        if os.path.isfile(path):
            return PathResolution(status="FILE", abs_path=path)
    for path in candidates:
        if os.path.isdir(path):
            return PathResolution(status="DIRECTORY", abs_path=path)
    return PathResolution(status="MISSING", abs_path=None)


# ─── init / verify result records ────────────────────────────────────────


@dataclass
class InitResult:
    """Aggregated stats from `init_baseline`."""

    populated: int = 0          # FILE → sha256_baseline written
    directory_skip: int = 0     # DIRECTORY → marked DIRECTORY_SKIP
    missing: int = 0            # MISSING → marked FILE_MISSING
    total_seen: int = 0
    populated_sites: list[ReferenceSite] = field(default_factory=list)


@dataclass
class VerifyResult:
    """Aggregated stats from `verify_baseline`."""

    ok: int = 0                 # current sha256 == baseline
    drift: int = 0              # mismatch — :SourceCodeDriftEvent emitted
    missing: int = 0            # baseline existed but file vanished
    skipped_baseline: int = 0   # no baseline to compare against (call init first)
    skipped_dir: int = 0
    skipped_orphan: int = 0
    drift_events: list[SourceCodeDriftEvent] = field(default_factory=list)


# ─── core operations ─────────────────────────────────────────────────────


def _now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _compute_sha256(abs_path: str) -> str:
    """Compute sha256 of a file's bytes (TOCTOU-safe via daemon.safe_read_hash)."""
    _, sha = safe_read_hash(Path(abs_path))
    return sha


def init_baseline(
    *,
    kg: KgClient,
    sites: Iterable[ReferenceSite],
    base_chain: Iterable[str] = DEFAULT_FS_BASE_CHAIN,
) -> InitResult:
    """Populate `sha256_baseline` for every site that lacks it.

    Idempotent — sites with `sha256_baseline` already set are skipped.
    Status transitions: UNKNOWN → BASELINE / DIRECTORY_SKIP / FILE_MISSING.
    """
    result = InitResult()
    ts = _now_iso()
    chain = tuple(base_chain)
    for site in sites:
        result.total_seen += 1
        if site.sha256_baseline:
            continue  # already initialized
        resolution = resolve_path(site.sourcePath, base_chain=chain)
        if resolution.status == "FILE":
            sha = _compute_sha256(resolution.abs_path)
            updated = site.model_copy(update={
                "sha256": sha,
                "sha256_baseline": sha,
                "sha256_status": Sha256Status.BASELINE,
                "last_validated": ts,
                "pierced_at": site.pierced_at,
            })
            kg.merge_reference_site_state(updated)
            result.populated += 1
            result.populated_sites.append(updated)
        elif resolution.status == "DIRECTORY":
            updated = site.model_copy(update={
                "sha256_status": Sha256Status.DIRECTORY_SKIP,
                "last_validated": ts,
            })
            kg.merge_reference_site_state(updated)
            result.directory_skip += 1
        else:
            updated = site.model_copy(update={
                "sha256_status": Sha256Status.FILE_MISSING,
                "last_validated": ts,
            })
            kg.merge_reference_site_state(updated)
            result.missing += 1
    logger.info(
        "init_baseline: populated=%d directory_skip=%d missing=%d total=%d",
        result.populated, result.directory_skip, result.missing, result.total_seen,
    )
    return result


def _record_drift_event(
    *,
    kg: KgClient,
    result: VerifyResult,
    site: ReferenceSite,
    ts: str,
    kind: str,
    current_sha: str | None,
    new_status: Sha256Status,
    emit_events: bool,
) -> None:
    """Emit :SourceCodeDriftEvent + update site state for FILE_MISSING / SHA256_MISMATCH."""
    event = SourceCodeDriftEvent(
        name=f"drift-{site.sourceId}-{ts}",
        ref_site=site.sourceId,
        path=site.sourcePath,
        baseline_sha256=site.sha256_baseline,
        current_sha256=current_sha,
        kind=kind,
        created_at=ts,
    )
    result.drift_events.append(event)
    if emit_events:
        kg.emit_drift_event(event)
    update_fields: dict[str, object] = {
        "sha256_status": new_status,
        "drift_detected_at": ts,
        "last_validated": ts,
        "drift_score": 1.0,
    }
    if current_sha is not None:
        update_fields["sha256"] = current_sha
    kg.merge_reference_site_state(site.model_copy(update=update_fields))


def verify_baseline(
    *,
    kg: KgClient,
    sites: Iterable[ReferenceSite],
    base_chain: Iterable[str] = DEFAULT_FS_BASE_CHAIN,
    emit_events: bool = True,
) -> VerifyResult:
    """Recompute current sha256 and compare to baseline.

    Emits :SourceCodeDriftEvent for every mismatch (PROV evidence trail).
    Status transitions: BASELINE → VERIFIED | DRIFT | FILE_MISSING.
    """
    result = VerifyResult()
    ts = _now_iso()
    chain = tuple(base_chain)
    for site in sites:
        if site.sha256_status == Sha256Status.DIRECTORY_SKIP:
            result.skipped_dir += 1
            continue
        if not site.sha256_baseline:
            result.skipped_baseline += 1
            continue
        resolution = resolve_path(site.sourcePath, base_chain=chain)
        if resolution.status != "FILE":
            result.missing += 1
            _record_drift_event(
                kg=kg, result=result, site=site, ts=ts,
                kind="FILE_MISSING", current_sha=None,
                new_status=Sha256Status.FILE_MISSING, emit_events=emit_events,
            )
            continue

        current = _compute_sha256(resolution.abs_path)
        if current != site.sha256_baseline:
            result.drift += 1
            _record_drift_event(
                kg=kg, result=result, site=site, ts=ts,
                kind="SHA256_MISMATCH", current_sha=current,
                new_status=Sha256Status.DRIFT, emit_events=emit_events,
            )
        else:
            result.ok += 1
            updated = site.model_copy(update={
                "sha256": current,
                "sha256_status": Sha256Status.VERIFIED,
                "last_validated": ts,
                "drift_detected_at": None,
                "drift_score": 0.0,
            })
            kg.merge_reference_site_state(updated)
    logger.info(
        "verify_baseline: ok=%d drift=%d missing=%d skip_baseline=%d skip_dir=%d",
        result.ok, result.drift, result.missing,
        result.skipped_baseline, result.skipped_dir,
    )
    return result


# ─── Convenience: 7-tuple ReferenceSite factory ──────────────────────────


def make_reference_site_7tuple(
    *,
    sourceId: str,
    sourcePath: str,
    sha256_baseline: str,
    kg_anchor: str,
    layer: ReferenceLayer = ReferenceLayer.L4_SEMIOTIC,
    drift_score: float = 0.0,
) -> ReferenceSite:
    """Build a Wave 6 7-tuple ReferenceSite ready for KG MERGE.

    Schema (LONGINUS_BINDING.md §"7-tuple ReferenceSite"):
        {sourceId, sourcePath, line_range (via sourcePath), sha256,
         semver (kg_anchor surrogate), kg_anchor, drift_metric}.
    """
    return ReferenceSite(
        sourceId=sourceId,
        sourcePath=sourcePath,
        sha256=sha256_baseline,
        sha256_baseline=sha256_baseline,
        sha256_status=Sha256Status.BASELINE,
        kg_anchor=kg_anchor,
        layer=layer,
        drift_score=drift_score,
        last_validated=_now_iso(),
    )


# KG: longinus-sha256-daemon-canonical-2026-05-06
# KG: lesson-longinus-wave6-full-symposium-binding-2026-05-14
# KG: span-bhgman-longinus-wave6-absorb-2026-05-14
