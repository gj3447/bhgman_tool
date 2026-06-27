"""ooptdd-loop in_process target — binds two trace gates to the REAL Longinus drift
audit engine (``engine.longinus_drift_audit``).

This is the system-under-test the loop calls as ``run_audit_pipeline(backend, cid)``.
It does NOT fake the trace: every event it ships is produced by genuinely running the
engine code.

Honest-count contract (verified before writing):
    ``MockKgClient()`` starts with ZERO ReferenceSite states, so a naive sha256
    baseline count over a fresh Mock KG is 0 — a ``>=1`` gate would (correctly) be RED.
    To EARN a nonzero count we seed one *real* :ReferenceSite whose ``sourcePath`` is an
    actual engine file, then run the engine's real
    ``sha256_baseline.init_baseline`` (which content-hashes the file off disk via
    ``daemon.safe_read_hash``). Only after that does the baseline count become a real,
    nonzero value — and ``LonginusAudit.run_full`` re-derives the same count from the KG.

Longinus binding (AST-checked by ooptdd_loop.longinus.verify_binding):
    The event-name string literals 'sha256_baseline_checked' and
    'longinus_audit_complete' appear verbatim, as string constants, inside the bodies
    of the two bound symbols below (``emit_sha256_phase`` / ``run_audit_pipeline``) —
    and they are exactly the events shipped to the backend. The binding stays honest:
    rename a literal and the gate goes UNBOUND (proven via the RED-proof run).

# KG: finding-ooptdd-bhgman-longinus-adapter-20260624
# KG: lesson-longinus-wave6-full-symposium-binding-2026-05-14
"""
from __future__ import annotations

from engine.longinus_drift_audit import sha256_baseline
from engine.longinus_drift_audit.audit_runner import LonginusAudit
from engine.longinus_drift_audit.kg_client import MockKgClient
from engine.longinus_drift_audit.models import ReferenceLayer, ReferenceSite

# A real engine file on disk. Its bytes are what ``init_baseline`` content-hashes, so the
# earned baseline is a genuine sha256 of real source — not a placeholder. Relative to the
# repo root, which the engine's DEFAULT_FS_BASE_CHAIN (git-toplevel) resolves to FILE.
_REAL_ENGINE_FILE = "engine/longinus_drift_audit/sha256_baseline.py"

# Audit scope: the engine package dir. Small + fast to scan, and a real code root (not a stub).
_CODE_ROOT = "engine/longinus_drift_audit"

_KG_ANCHOR = "finding-ooptdd-bhgman-longinus-adapter-20260624"


def _ev(cid: str, event: str, **attrs) -> dict:
    """Shape one trace event the way the memory backend keys + counts it (cid + event)."""
    return {
        "cid": cid,
        "correlation_id": cid,
        "cycle_id": cid,
        "service": "bhgman-longinus-audit",
        "event": event,
        **attrs,
    }


def _seed_real_reference_site(kg: MockKgClient) -> ReferenceSite:
    """Insert ONE real :ReferenceSite (UNKNOWN, no baseline yet) pointing at a real engine
    file, so the subsequent ``init_baseline`` has genuine on-disk content to hash.

    Without this seed the Mock KG is empty and the baseline count is honestly 0.
    """
    site = ReferenceSite(
        sourceId=_KG_ANCHOR,
        sourcePath=_REAL_ENGINE_FILE,
        kg_anchor=_KG_ANCHOR,
        layer=ReferenceLayer.L4_SEMIOTIC,
    )
    kg.merge_reference_site_state(site)
    return site


def emit_sha256_phase(backend, cid: str, kg: MockKgClient) -> int:
    """Run the REAL ``sha256_baseline.init_baseline`` over the seeded site, then ship a
    'sha256_baseline_checked' event carrying the EARNED, nonzero baseline count.

    The literal 'sha256_baseline_checked' below is the event we ship AND the string
    Longinus AST-checks against this symbol's body — they are the same string on purpose.
    Returns the earned baseline count (real number, reported by the caller).
    """
    site = _seed_real_reference_site(kg)
    # REAL engine call: content-hashes the real file off disk and writes BASELINE state.
    init = sha256_baseline.init_baseline(kg=kg, sites=[site])
    # The earned count: how many KG sites now actually carry a sha256 baseline. On a fresh
    # Mock KG this is 0 until init_baseline genuinely populates it — here it is >= 1.
    baseline_count = sum(1 for s in kg.list_reference_site_states() if s.sha256_baseline)
    backend.ship([
        _ev(
            cid,
            "sha256_baseline_checked",
            baseline_count=baseline_count,
            populated=init.populated,
            sourcePath=site.sourcePath,
            sha256=(site.sha256_baseline or kg.sites[site.sourceId].sha256_baseline),
        )
    ])
    return baseline_count


def run_audit_pipeline(backend, cid: str) -> dict:
    """Loop entry point: run the REAL Longinus drift audit under ``cid`` and ship its
    completion event.

    Steps (all real engine code):
      1. fresh empty Mock KG (baseline count starts at 0 — nothing earned yet),
      2. ``emit_sha256_phase`` seeds + runs ``init_baseline`` -> earns the baseline count
         and ships 'sha256_baseline_checked',
      3. ``LonginusAudit.run_full`` runs the full audit (scan + drift + sha256 verify + GED),
      4. ship exactly ONE 'longinus_audit_complete' event with the real audit_id +
         the engine-derived ``sha256_baseline_count``.

    The literal 'longinus_audit_complete' below is the event we ship AND the string
    Longinus AST-checks against this symbol's body.
    """
    kg = MockKgClient()
    baseline_count = emit_sha256_phase(backend, cid, kg)
    # REAL audit over a real code root — the engine's own orchestrator.
    audit = LonginusAudit(kg=kg, code_root=_CODE_ROOT)
    report = audit.run_full(verify_sha256=True)
    backend.ship([
        _ev(
            cid,
            "longinus_audit_complete",
            audit_id=report.audit_id,
            sha256_baseline_count=report.sha256_baseline_count,
            sha256_drift_events=len(report.sha256_drift_events),
            reverse_orphans=len(report.reverse_orphans),
        )
    ])
    return {
        "audit_id": report.audit_id,
        "sha256_baseline_count": report.sha256_baseline_count,
        "earned_baseline_count": baseline_count,
    }
