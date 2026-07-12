"""Tests for prometheus KG-ingest (the 'write' half of the acquire essence)."""

from engine.agents.dispatch import SubagentResult
from engine.agents.prometheus import (
    ResearchReport,
    _finding_id,
    ingest_cypher,
    ingest_report,
)


def _report() -> ResearchReport:
    return ResearchReport(
        topic="docker vs k8s",
        n=2,
        sub_questions=("networking", "storage"),
        findings=(
            SubagentResult(name="agent-0", ok=True, text="k8s uses CNI plugins [src]"),
            SubagentResult(name="agent-1", ok=True, text="PV/PVC abstraction [src]"),
        ),
        synthesis="## Consensus\nboth containerize\n",
    )


def test_ingest_cypher_is_propose_and_deterministic():
    cyphers = ingest_cypher(_report(), "cyc-1")
    assert len(cyphers) == 2  # lesson + findings

    lesson_c, lesson_p = cyphers[0]
    assert "MERGE (l:Lesson" in lesson_c
    assert lesson_p["topic"] == "docker vs k8s"
    assert lesson_p["synthesis"].startswith("## Consensus")
    assert lesson_p["cycle_id"] == "cyc-1"
    assert lesson_p["researched_ok"] == 2

    findings_c, findings_p = cyphers[1]
    assert "MERGE (rf:ResearchFinding" in findings_c
    assert "UNWIND $findings" in findings_c
    assert len(findings_p["findings"]) == 2
    f0 = findings_p["findings"][0]
    assert f0["domain"] == "networking"
    assert f0["status"] == "RESEARCHED"
    assert f0["name"] == _finding_id("docker vs k8s", "networking", 0)

    # deterministic → idempotent MERGE (re-ingest yields the same ids)
    assert ingest_cypher(_report(), "cyc-1")[1][1]["findings"][0]["name"] == f0["name"]


def test_ingest_cypher_marks_failed_findings():
    report = ResearchReport(
        topic="t",
        n=1,
        sub_questions=("q",),
        findings=(SubagentResult(name="a", ok=False, text="", error="timeout"),),
        synthesis="",
    )
    findings = ingest_cypher(report, "c")[1][1]["findings"]
    assert findings[0]["status"] == "FAILED"


def test_ingest_report_applies_via_runner():
    calls: list[tuple[str, dict]] = []

    def fake_write(cypher: str, params: dict) -> list[dict]:
        calls.append((cypher, params))
        if "ResearchFinding" in cypher:
            return [{"ingested": len(params["findings"])}]
        return [{"lesson": params["lesson"]}]

    count = ingest_report(_report(), fake_write, "cyc-1")
    assert count == 2  # 2 findings ingested
    assert len(calls) == 2  # lesson write + findings write
    assert calls[0][1]["cycle_id"] == "cyc-1"


def test_ingest_report_returns_zero_when_runner_silent():
    def fake_write(cypher: str, params: dict) -> list[dict]:
        return []

    assert ingest_report(_report(), fake_write, "c") == 0
