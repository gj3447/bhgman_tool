"""Tests for the prometheus_ingest MCP tool (findings → idempotent MERGE cyphers)."""

import pytest

from engine.mcp_server.tools.prometheus import (
    prometheus_ingest_impl,
    prometheus_research_impl,
)


def test_prometheus_ingest_returns_merge_cyphers():
    out = prometheus_ingest_impl(
        topic="docker vs k8s",
        findings=[
            {"domain": "networking", "summary": "CNI plugins", "ok": True},
            {"sub_question": "storage", "text": "PV/PVC", "ok": True},
        ],
        synthesis="## Consensus",
        cycle_id="cyc-9",
    )
    if "error" in out and "agents runtime unavailable" in out["error"]:
        pytest.skip("agents extra not installed in this environment")

    assert out["finding_count"] == 2
    assert out["cycle_id"] == "cyc-9"
    cyphers = out["ingest_cyphers"]
    assert len(cyphers) == 2
    assert any("ResearchFinding" in c["cypher"] for c in cyphers)
    findings_params = next(c["params"] for c in cyphers if "ResearchFinding" in c["cypher"])
    domains = {f["domain"] for f in findings_params["findings"]}
    assert domains == {"networking", "storage"}


def test_prometheus_ingest_rejects_empty():
    assert "error" in prometheus_ingest_impl("", [])
    assert "error" in prometheus_ingest_impl("topic", [])


def test_prometheus_research_planner_unchanged():
    out = prometheus_research_impl("docker networking storage security auth monitoring", 16)
    assert out["n"] == 16
    assert out["matrix"] is not None
    assert "kg_first" in out
