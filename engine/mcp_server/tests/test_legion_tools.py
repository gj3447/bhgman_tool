"""Tests for the 7-commander legion MCP tools."""

from __future__ import annotations

from engine.mcp_server.tools.legion import legion_roster_impl, legion_run_impl
from engine.mcp_server.server import list_registered_tool_names


def test_roster_lists_all_seven_commanders():
    r = legion_roster_impl()
    names = [c["name"] for c in r["commanders"]]
    assert r["count"] == 7
    assert names == [
        "prometheus",
        "longinus",
        "eureka",
        "occam",
        "naesengmoon",
        "hades",
        "jaebaeman",
    ]
    assert r["canonical_order"] == ["획득", "연결", "창조", "정리", "검증", "실현"]


def test_roster_contracts_chain():
    r = legion_roster_impl()
    by = {c["name"]: c for c in r["commanders"]}
    # naesengmoon(검증) requires all 4 prior provides
    assert set(by["naesengmoon"]["requires"]) == {"acquired", "bindings", "abstractions", "hygiene"}
    # hades(실현) requires the verdict (gate 후 실현)
    assert by["hades"]["requires"] == ["verdict"]
    # jaebaeman is the dispatch loop, not a stage
    assert "dispatch" in by["jaebaeman"]["role"]


def test_legion_run_infra0_completes():
    run = legion_run_impl(cycle_id="test-legion")
    assert run["completed"] is True
    assert run["contract_violation"] is None
    assert run["gate_failure"] is None
    ran = {o["commander"]: o["ok"] for o in run["ran"]}
    assert set(ran) == {"prometheus", "longinus", "eureka", "occam", "naesengmoon", "hades"}
    assert all(ran.values())


def test_legion_tools_registered():
    names = list_registered_tool_names()
    assert "legion_roster" in names
    assert "legion_run" in names
