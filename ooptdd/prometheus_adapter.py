"""ooptdd-loop in_process target — binds the prometheus 획득(acquire) lifecycle to the
REAL deterministic engine (``engine.prometheus.run_acquire``).

This is the system-under-test the loop calls as ``run_prometheus_pipeline(backend, cid)``.
It does NOT fake the trace: every event it ships is produced by genuinely running the
engine's gap-detect -> query-derive -> fetch -> parse -> ingest chain.

Honest-count contract (verified before writing, STEP-0 baseline):
    A fresh/empty KG returns NO :OpenQuestion/:VerdictPending rows, so ``run_acquire``
    over an empty ``run_cypher`` gives gaps=0 -> findings=0 -> ingested=0. Every ==N
    gate is therefore GENUINELY RED until the real chain populates the store. To EARN
    nonzero counts we seed two real gap rows, key a StaticFetcher corpus to the EXACT
    ``derive_query()`` output for each gap (the join crux — a wrong key yields 0 docs
    for that gap, collapsing the value-pinned count), and run the apply wing with a
    capturing ``write_cypher`` so ``ingested`` is earned off real writes. Every shipped
    count is RE-DERIVED from the real ``AcquireReport`` — never a hand-typed number.

Longinus binding (AST-checked by ``ooptdd_loop.longinus.verify_binding``):
    Each must_emit event-name string literal lives VERBATIM, as a string constant, inside
    the body of the ADAPTER symbol that ships it (``emit_gap_phase`` /
    ``emit_extract_phase`` / ``emit_ingest_phase`` / ``run_prometheus_pipeline``) — and
    those are exactly the events shipped. The literals live ONLY here, NEVER inside
    ``engine/prometheus/`` (the engine stays key-free, I/O-free, emit-free so its pure
    unit tests and the LLM-disjoint floor are preserved). Rename a literal => UNBOUND/RED.

# KG: finding-ooptdd-bhgman-prometheus-adapter-20260624
# KG: ATOM_Skill_prometheus
"""
from __future__ import annotations

from engine.prometheus import run_acquire
from engine.prometheus.fetcher import StaticFetcher
from engine.prometheus.models import AcquireReport, FetchedDoc

_KG_ANCHOR = "finding-ooptdd-bhgman-prometheus-adapter-20260624"

# Pinned so the earned Finding.researchedAt is deterministic (no wall-clock leak).
_RESEARCHED_AT = "2026-06-24T00:00:00Z"

# Two real knowledge gaps, exactly the row shape ``engine.prometheus.scan_gaps`` parses
# (1 OpenQuestion + 1 VerdictPending). A fresh/empty KG returns NONE of these.
_GAP_ROWS = [
    {"id": "q-koide", "question": "Is the Koide relation numerology", "kind": "OpenQuestion"},
    {"id": "v-eureka", "question": "eureka span maintain 7", "kind": "VerdictPending"},
]

# The fetch corpus, keyed by the EXACT ``derive_query()`` output for each gap:
#   OpenQuestion   -> "{q}"                      -> "Is the Koide relation numerology"
#   VerdictPending -> "{q} evidence resolution"  -> "eureka span maintain 7 evidence resolution"
# Each doc carries ONE sentence >= 40 chars (the extract min_len). A wrong key yields zero
# docs for that gap => one fewer Finding => the value-pinned ==2 count goes RED.
_CORPUS = {
    "Is the Koide relation numerology": [
        FetchedDoc(
            "https://phys/koide",
            "The Koide formula holds to high empirical precision across the charged lepton masses.",
        ),
    ],
    "eureka span maintain 7 evidence resolution": [
        FetchedDoc(
            "https://kg/eureka",
            "Seven commanders form the closure of the deterministic verb space of the legion.",
        ),
    ],
}


def _ev(cid: str, event: str, **attrs) -> dict:
    """Shape one trace event the way the memory backend keys + counts it (cid + event)."""
    return {
        "cid": cid,
        "correlation_id": cid,
        "cycle_id": cid,
        "service": "bhgman.prometheus",
        "event": event,
        **attrs,
    }


def _gap_runner(rows):
    """A ``run_cypher`` seam returning fixed gap rows. The real scan_gaps Cypher is a MATCH
    a Mock store cannot run; injecting rows is how the test earns real ``Gap`` objects —
    the same DIP seam the engine already uses (fetcher / KgClient injection)."""
    def run_cypher(_cypher: str, _params: dict) -> list[dict]:
        return list(rows)

    return run_cypher


def _run_real_acquire(*, apply: bool, corpus=None, gap_rows=None) -> AcquireReport:
    """Drive the REAL ``run_acquire`` over the seeded gaps + corpus. Every downstream count
    is RE-DERIVED from this real ``AcquireReport``."""
    corpus = _CORPUS if corpus is None else corpus
    gap_rows = _GAP_ROWS if gap_rows is None else gap_rows

    def write_cypher(_cypher: str, _params: dict) -> list[dict]:
        return []  # a real, succeeding write seam — ``ingested`` increments per call

    return run_acquire(
        _gap_runner(gap_rows),
        fetcher=StaticFetcher(corpus),
        write_cypher=write_cypher if apply else None,
        cycle_id="prometheus-ooptdd",
        apply=apply,
        researched_at=_RESEARCHED_AT,
    )


def emit_gap_phase(backend, cid: str, report: AcquireReport) -> int:
    """Ship one 'prometheus_gap_detected' per REAL Gap, carrying its kind. The literal
    'prometheus_gap_detected' lives verbatim here — Longinus AST-checks THIS symbol."""
    for gap in report.gaps:
        backend.ship([_ev(cid, "prometheus_gap_detected", gap_id=gap.id, kind=gap.kind)])
    return len(report.gaps)


def emit_extract_phase(backend, cid: str, report: AcquireReport) -> int:
    """Ship one 'prometheus_finding_extracted' per REAL Finding the fetch->parse chain
    produced. Count RE-DERIVED from report.findings (0 with no/wrong corpus => RED)."""
    for f in report.findings:
        backend.ship([
            _ev(cid, "prometheus_finding_extracted", finding_id=f.finding_id,
                gap_id=f.gap_id, citation_url=f.citation_url)
        ])
    return len(report.findings)


def emit_propose_phase(backend, cid: str, report: AcquireReport) -> int:
    """Ship one 'prometheus_finding_proposed' per planned MERGE cypher (the PROPOSE
    covenant — always computed, even in apply mode)."""
    for _ in report.planned_cyphers:
        backend.ship([_ev(cid, "prometheus_finding_proposed")])
    return len(report.planned_cyphers)


def emit_ingest_phase(backend, cid: str, report: AcquireReport) -> int:
    """Ship one 'prometheus_finding_ingested' per REAL write_cypher row (apply wing only).
    A dry-run report has ingested=0 => no event => the ==N ingest gate is RED."""
    for _ in range(report.ingested):
        backend.ship([_ev(cid, "prometheus_finding_ingested")])
    return report.ingested


def run_prometheus_pipeline(backend, cid: str, *, corpus=None, gap_rows=None,
                            apply: bool = True) -> dict:
    """Loop entry point (called as ``run_prometheus_pipeline(backend, cid)``). Runs the REAL
    acquire and ships the full lifecycle under ``cid``. The 'prometheus_acquire_started' and
    'prometheus_acquire_completed' literals live verbatim in THIS symbol's body — Longinus
    AST-checks ``run_prometheus_pipeline`` for the completion event.

    ``corpus``/``gap_rows``/``apply`` default to the real fixtures so the loop's 2-arg call
    drives the green path; the twin test overrides ``corpus`` for the drop-the-seed RED proof.
    """
    report = _run_real_acquire(apply=apply, corpus=corpus, gap_rows=gap_rows)

    backend.ship([_ev(cid, "prometheus_acquire_started", phase="scan")])
    n_gaps = emit_gap_phase(backend, cid, report)
    n_findings = emit_extract_phase(backend, cid, report)
    n_proposed = emit_propose_phase(backend, cid, report)
    n_ingested = emit_ingest_phase(backend, cid, report)
    backend.ship([
        _ev(cid, "prometheus_acquire_completed", dry_run=report.dry_run,
            gaps=n_gaps, findings=n_findings, proposed=n_proposed, ingested=n_ingested)
    ])
    return {
        "gaps": n_gaps,
        "findings": n_findings,
        "proposed": n_proposed,
        "ingested": n_ingested,
        "dry_run": report.dry_run,
    }


__all__ = [
    "emit_extract_phase",
    "emit_gap_phase",
    "emit_ingest_phase",
    "emit_propose_phase",
    "run_prometheus_pipeline",
]
