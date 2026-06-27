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


# ── R6/R7: cycle_id 서버-mint + in-loop 게이트 주입 (키 있으면) ────────────────
def test_legion_run_mints_distinct_default_cycle_ids(tmp_path, monkeypatch):
    monkeypatch.delenv("BHGMAN_VERDICT_HMAC_SECRET", raising=False)
    r1 = legion_run_impl(kg_path=str(tmp_path / "a.json"))
    r2 = legion_run_impl(kg_path=str(tmp_path / "b.json"))
    assert r1["cycle_id"] != r2["cycle_id"] and r1["cycle_id"].startswith("cyc-")


def test_legion_run_preserves_explicit_cycle_id(tmp_path, monkeypatch):
    monkeypatch.delenv("BHGMAN_VERDICT_HMAC_SECRET", raising=False)
    r = legion_run_impl(cycle_id="explicit-1", kg_path=str(tmp_path / "a.json"))
    assert r["cycle_id"] == "explicit-1"


def test_legion_run_gated_transparent_when_key_present(tmp_path, monkeypatch):
    # 키 설정 시 in-loop 게이트가 주입되지만, 정상 verdict 는 통과 → 결과는 ungated 와 동일.
    monkeypatch.delenv("BHGMAN_VERDICT_ED25519_PRIVATE", raising=False)
    monkeypatch.delenv("BHGMAN_VERDICT_ED25519_PUBLIC", raising=False)
    monkeypatch.delenv("BHGMAN_VERDICT_HMAC_SECRET", raising=False)
    base = legion_run_impl(cycle_id="base", kg_path=str(tmp_path / "a.json"))
    monkeypatch.setenv("BHGMAN_VERDICT_HMAC_SECRET", "K" * 40)
    gated = legion_run_impl(cycle_id="gated", kg_path=str(tmp_path / "b.json"))
    assert gated["completed"] == base["completed"]
    assert gated["gate_failure"] == base["gate_failure"]
