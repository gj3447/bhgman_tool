"""프로메테우스 결정론 엔진 (경계축 ingest) 검증.

증명: gap-detect → query-derive → fetch(StaticFetcher) → parse → ingest 전 단계 결정론,
PROPOSE 기본, findingId idempotent, 백엔드 미지원 graceful, LLM 불필요.

# KG: project-legion-unification-kg-engine-2026-06-01
"""

from __future__ import annotations

from engine.prometheus import (
    AcquireReport,
    CallableFetcher,
    FetchedDoc,
    StaticFetcher,
    run_acquire,
)
from engine.prometheus.extract import extract_findings, html_to_text
from engine.prometheus.gap_source import scan_gaps
from engine.prometheus.models import Gap
from engine.prometheus.query_template import derive_query


def _gap_rc(rows):
    def rc(_cypher, _params):
        return rows

    return rc


_GAP_ROWS = [
    {"id": "q-koide", "question": "Is the Koide relation numerology", "kind": "OpenQuestion"},
    {"id": "v-eureka", "question": "eureka span maintain 7", "kind": "VerdictPending"},
]


# ── 단계별 결정론 ────────────────────────────────────────────────────────────
def test_scan_gaps_parses_rows():
    gaps = scan_gaps(_gap_rc(_GAP_ROWS))
    assert [g.id for g in gaps] == ["q-koide", "v-eureka"]
    assert gaps[1].kind == "VerdictPending"


def test_scan_gaps_degrades_on_unsupported_backend():
    def rc(_c, _p):
        raise RuntimeError("local KG: unsupported query")

    assert scan_gaps(rc) == []


def test_derive_query_is_deterministic_per_kind():
    q1 = derive_query(Gap("q1", "what is X", "OpenQuestion"))
    q2 = derive_query(Gap("v1", "verdict Y", "VerdictPending"))
    assert q1.text == "what is X"
    assert q2.text == "verdict Y evidence resolution"
    assert derive_query(Gap("q1", "what is X", "OpenQuestion")).text == q1.text  # 재현


def test_html_to_text_strips_tags_and_scripts():
    html = "<html><body><p>Real claim here.</p><script>junk()</script></body></html>"
    assert "Real claim here." in html_to_text(html)
    assert "junk" not in html_to_text(html)


def test_extract_findings_sha_and_citation():
    gap = Gap("q1", "x", "OpenQuestion")
    docs = [
        FetchedDoc("http://src/a", "This is a sufficiently long substantive claim sentence here.")
    ]
    fs = extract_findings(gap, docs, "cyc-1")
    assert len(fs) == 1
    assert fs[0].citation_url == "http://src/a"
    assert fs[0].gap_id == "q1"
    assert len(fs[0].content_sha256) == 64


def test_finding_id_is_idempotent():
    gap = Gap("q1", "x", "OpenQuestion")
    doc = [
        FetchedDoc("http://src/a", "A long enough sentence to pass the min length filter easily.")
    ]
    a = extract_findings(gap, doc, "cyc-1")[0]
    b = extract_findings(gap, doc, "cyc-1")[0]
    assert a.finding_id == b.finding_id  # 재실행 안전


# ── 파이프라인 end-to-end ────────────────────────────────────────────────────
def test_run_acquire_full_pipeline_propose_default():
    corpus = {
        "Is the Koide relation numerology": [
            FetchedDoc(
                "http://phys/koide", "The Koide formula holds to high precision empirically."
            )
        ],
        "eureka span maintain 7 evidence resolution": [
            FetchedDoc("http://kg/eureka", "Seven commanders form the closure of the verb space.")
        ],
    }
    report = run_acquire(_gap_rc(_GAP_ROWS), fetcher=StaticFetcher(corpus), cycle_id="cyc-x")
    assert isinstance(report, AcquireReport)
    assert len(report.gaps) == 2
    assert len(report.findings) == 2
    assert report.dry_run is True  # PROPOSE 기본
    assert report.ingested == 0
    assert len(report.planned_cyphers) == 2
    assert "ResearchFinding" in report.planned_cyphers[0]


def test_run_acquire_without_fetcher_surfaces_queries_only():
    report = run_acquire(_gap_rc(_GAP_ROWS))
    assert len(report.queries) == 2
    assert report.findings == ()


def test_run_acquire_apply_writes_via_write_cypher():
    captured = []

    def write(cypher, params):
        captured.append(params["findingId"])
        return []

    corpus = {
        "Is the Koide relation numerology": [
            FetchedDoc("http://phys/koide", "Koide precision claim long enough to pass the filter.")
        ],
    }
    rows = [_GAP_ROWS[0]]
    report = run_acquire(
        _gap_rc(rows),
        fetcher=StaticFetcher(corpus),
        write_cypher=write,
        apply=True,
        cycle_id="cyc-w",
    )
    assert report.dry_run is False
    assert report.ingested == 1
    assert captured and captured[0].startswith("rf-")


def test_callable_fetcher_wraps_arbitrary_io():
    fetcher = CallableFetcher(
        lambda q: [FetchedDoc("http://x", f"answer for {q.text} padded long enough.")]
    )
    report = run_acquire(_gap_rc([_GAP_ROWS[0]]), fetcher=fetcher)
    assert len(report.findings) == 1
    assert "Koide" in report.findings[0].claim or "answer for" in report.findings[0].claim
