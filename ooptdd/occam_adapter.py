"""ooptdd-loop in_process target — binds occam 정리(KG node dedup / supersede) to the REAL
engine (``engine.occam.run_occam``).

Honest-count contract (verified, STEP-0 baseline):
    run_occam over CLEAN rows (a single SourceCodeNode) yields ``superseded_count=0`` => no
    candidate => RED. To EARN we seed ``_EXACT_DUP_ROWS`` — the abs-lineage and rel-lineage of
    the SAME file (identical sha256 + lineCount, DIFFERING raw sourcePath so it supersedes
    rather than hitting the exact-dup refuse guard). occam detects a confident byte-identical
    SUPERSEDE; with apply=True and a write_cypher that returns the matched supersede row,
    ``apply_result.applied_count == 1``. CRITICALLY ``node.superseded`` is bound to
    ``applied_count`` and emitted ONLY in the non-dry-run branch: a dry-run leaves
    ``applied_count=0`` even though ``apply_result.superseded`` is a non-empty PLANNED list (the
    fake-green trap), a clean KG has zero candidates, and an unmatched write applies nothing.
    Every count is RE-DERIVED from the real ``OccamRunResult`` — never from planned candidates.

Longinus binding (AST-checked): each must_emit literal lives VERBATIM in its ADAPTER symbol
    (``emit_dedup_phase`` / ``emit_apply_phase`` / ``run_occam_pipeline``), NEVER inside
    ``engine/occam/`` (the engine is IO-pure, no ship machinery). Rename => UNBOUND/RED.

# KG: finding-ooptdd-bhgman-occam-adapter-20260625
# KG: occam-kam-canonical-2026-05-26
"""
from __future__ import annotations

from engine.occam.occam_runner import run_occam

_KG_ANCHOR = "finding-ooptdd-bhgman-occam-adapter-20260625"

# abs + rel lineage of the SAME file: identical sha256 + lineCount, DIFFERING raw sourcePath
# (so it supersedes, not exact-dup-refuses). A confident byte-identical SUPERSEDE.
_EXACT_DUP_ROWS = [
    {"name": "a_abs", "source_path": "/abs/bhgman_tool/x.py", "sha256": "same", "line_count": 50},
    {"name": "b_rel", "source_path": "bhgman_tool/x.py", "sha256": "same", "line_count": 50},
]
# A single solo file: no duplicate => zero candidates => the honest RED baseline.
_CLEAN_ROWS = [
    {"name": "solo", "source_path": "bhgman_tool/solo.py", "sha256": "s", "line_count": 50},
]


def _ev(cid: str, event: str, **attrs) -> dict:
    """Shape one trace event the way the memory backend keys + counts it (cid + event)."""
    return {
        "cid": cid,
        "correlation_id": cid,
        "cycle_id": cid,
        "service": "bhgman.occam",
        "event": event,
        **attrs,
    }


def _read_runner(rows):
    """run_cypher read seam returning fixed KG SourceCodeNode rows (boundary I/O injection)."""
    def run_cypher(_cypher, _params):
        return list(rows)

    return run_cypher


def _matched_write_runner():
    """write_cypher seam that returns the matched supersede row (as the engine's RETURN would),
    so apply_result.applied_count reflects a REAL matched write."""
    def write_cypher(_cypher, _params):
        return [{"superseded": "x", "current": "y"}]

    return write_cypher


def _unmatched_write_runner():
    """write_cypher that matched no row (node absent / already superseded) => nothing applied."""
    def write_cypher(_cypher, _params):
        return []

    return write_cypher


def emit_dedup_phase(backend, cid: str, result) -> int:
    """Ship one 'occam.candidate.detected' per real supersession candidate. Count RE-DERIVED
    from report.superseded_count (a clean KG => 0 => RED). The literal lives here."""
    for c in result.report.candidates:
        backend.ship([_ev(cid, "occam.candidate.detected", verdict=c.verdict)])
    return result.report.superseded_count


def emit_apply_phase(backend, cid: str, result) -> int:
    """Ship one 'occam.node.superseded' per node REALLY superseded by a matched write
    (apply_result.applied_count), under the archive-only covenant. Emitted ONLY in the
    non-dry-run branch — a dry-run's planned ``superseded`` list must NOT be shipped (the
    fake-green trap). The literal lives here."""
    ar = result.apply_result
    if ar.dry_run:
        return 0  # PROPOSE/dry-run covenant: no write happened, ship no supersede event
    for ident in ar.superseded:  # in apply mode this is the APPLIED set (len == applied_count)
        backend.ship([_ev(cid, "occam.node.superseded", node=ident, covenant="archive_only")])
    return ar.applied_count


def run_occam_pipeline(backend, cid: str, *, rows=None, apply: bool = True,
                       write_matches: bool = True) -> dict:
    """Loop entry (called as ``run_occam_pipeline(backend, cid)``). Runs the REAL run_occam
    (fetch -> occam_pass -> apply supersede) over the seeded duplicate and ships the lifecycle
    under ``cid``. The 'occam.started' and 'occam.completed' literals live verbatim in THIS
    symbol. ``rows``/``apply``/``write_matches`` default to the green path; the twin test
    overrides them for the dry-run / clean / unmatched-write RED proofs."""
    rows = _EXACT_DUP_ROWS if rows is None else rows
    write = _matched_write_runner() if write_matches else _unmatched_write_runner()
    result = run_occam(_read_runner(rows), write_cypher=write, apply=apply)

    backend.ship([_ev(cid, "occam.started", phase="scan")])
    n_detected = emit_dedup_phase(backend, cid, result)
    n_superseded = emit_apply_phase(backend, cid, result)
    backend.ship([
        _ev(cid, "occam.completed", detected=n_detected, superseded=n_superseded,
            dry_run=result.apply_result.dry_run)
    ])
    return {
        "detected": n_detected,
        "superseded": n_superseded,
        "dry_run": result.apply_result.dry_run,
    }


__all__ = ["emit_apply_phase", "emit_dedup_phase", "run_occam_pipeline"]
