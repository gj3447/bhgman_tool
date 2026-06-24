"""Tests for the Occam MCP tool."""

from __future__ import annotations

from engine.mcp_server.server import list_registered_tool_names
from engine.mcp_server.tools.occam import occam_dedupe_impl


def test_occam_dedupe_registered():
    assert "occam_dedupe" in list_registered_tool_names()


def test_occam_dedupe_uses_commander_engine_local_dry_run(tmp_path):
    res = occam_dedupe_impl(kg_path=str(tmp_path / "kg.json"))
    assert res["mode"] == "occam"
    assert res["dry_run"] is True
    assert res["applied"] == 0
    assert "occam[" in res["summary"]
