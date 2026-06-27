"""ingest_findings honest count — the Red artifact (written test-first, RED until the dedup).

``written``/``planned`` must equal the number of DISTINCT ``finding_id``s, NOT the number of
write calls. ``finding_id = sha256(gap|url|claim)`` is the idempotent MERGE key, so two findings
that share it are the SAME :ResearchFinding node — counting both inflates ``AcquireReport.ingested``
and the legion ``research_finding_count``, which can spuriously cross the verification dispatch
threshold (a Goodhart hole; PromHonesty hard-core: 영수 없는 green은 거짓말).

# KG: ATOM_Skill_prometheus
"""

from __future__ import annotations

from engine.prometheus.extract import extract_findings
from engine.prometheus.ingest import ingest_findings
from engine.prometheus.models import FetchedDoc, Gap

_GAP = Gap("q1", "x", "OpenQuestion")


def _capture():
    """A faithful fake write_cypher that records the findId actually reaching the store."""
    ids: list[str] = []

    def write(_cypher, params):
        ids.append(params["findingId"])
        return []

    write.ids = ids
    return write


def _findings(*url_claim):
    docs = [FetchedDoc(url, claim) for url, claim in url_claim]
    return tuple(extract_findings(_GAP, docs, "cyc-1"))


def test_identical_claims_collapse_to_one_distinct_node():
    # same url + same claim => one finding_id (sha256(gap|url|claim)) => one :ResearchFinding node.
    findings = _findings(
        ("http://src/a", "This is a sufficiently long substantive claim sentence here now."),
        ("http://src/a", "This is a sufficiently long substantive claim sentence here now."),
    )
    assert len(findings) == 2 and len({f.finding_id for f in findings}) == 1
    w = _capture()
    written, planned = ingest_findings(findings, write_cypher=w, apply=True)
    assert written == 1  # distinct nodes MERGEd, not write calls
    assert len(planned) == 1
    assert len(set(w.ids)) == 1 == len(w.ids)  # the store saw exactly one MERGE


def test_distinct_claims_are_not_collapsed():
    # the discrimination guard: genuinely distinct findings must BOTH ingest (no over-eager dedup).
    findings = _findings(
        ("http://src/a", "Alpha claim long enough to pass the min length filter easily here."),
        ("http://src/b", "Beta claim also long enough to pass the min length filter easily."),
    )
    assert len({f.finding_id for f in findings}) == 2
    w = _capture()
    written, planned = ingest_findings(findings, write_cypher=w, apply=True)
    assert written == 2 and len(planned) == 2 and len(set(w.ids)) == 2


def test_mixed_two_share_one_distinct():
    findings = _findings(
        ("http://src/a", "Shared claim long enough to pass the min length filter easily here."),
        ("http://src/a", "Shared claim long enough to pass the min length filter easily here."),
        ("http://src/b", "Unique claim distinct and long enough to pass the length filter here."),
    )
    assert len({f.finding_id for f in findings}) == 2
    w = _capture()
    written, _planned = ingest_findings(findings, write_cypher=w, apply=True)
    assert written == 2


def test_empty_findings_writes_nothing():
    written, planned = ingest_findings((), write_cypher=_capture(), apply=True)
    assert written == 0 and planned == ()


def test_dry_run_plans_distinct_only_no_write():
    # PROPOSE covenant: apply=False writes nothing, but planned reflects DISTINCT ids only.
    findings = _findings(
        ("http://src/a", "Dup claim long enough to pass the min length filter quite easily."),
        ("http://src/a", "Dup claim long enough to pass the min length filter quite easily."),
    )
    w = _capture()
    written, planned = ingest_findings(findings, write_cypher=w, apply=False)
    assert written == 0
    assert len(planned) == 1  # deduped before planning
    assert w.ids == []  # no write in dry-run
