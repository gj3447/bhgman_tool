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


def test_occam_dedupe_default_backend_is_local(tmp_path):
    # 하위호환: backend 미지정 = 기존 local 동작 (regression).
    res = occam_dedupe_impl(kg_path=str(tmp_path / "kg.json"))
    assert res["mode"] == "occam"
    assert res["dry_run"] is True


_DUP_ROWS = [
    {"name": "old", "source_path": "bhgman_tool/x.py", "sha256": "o", "line_count": 10},
    {"name": "new", "source_path": "bhgman_tool/x.py", "sha256": "n", "line_count": 99},
]


def test_occam_dedupe_surfaces_escalations_for_uncertain(monkeypatch):
    # MEDIUM-confidence 후보(디스크 truth 부재)는 payload의 escalations로 노출돼야 한다.
    def fake_read(cypher, params):
        return _DUP_ROWS if "SourceCodeNode" in cypher else []

    monkeypatch.setattr(
        "engine.cli.runtime.make_kg_runners",
        lambda: (fake_read, fake_read, (lambda: None)),
    )
    res = occam_dedupe_impl(backend="neo4j")
    assert res["escalation_count"] >= 1
    assert any(e["target"] == "naesengmoon" for e in res["escalations"])
    assert "escalate" in res["summary"]


def test_occam_dedupe_backend_neo4j_routes_through_kg_runners(monkeypatch):
    # backend="neo4j" → 운영 KG runner(make_kg_runners)를 통해 같은 OccamEngine 표면 실행.
    # CLI/MCP/legion parity: MCP가 더 이상 local-only가 아님.
    calls = {"made": 0, "closed": 0}

    def fake_read(cypher, params):
        return _DUP_ROWS if "SourceCodeNode" in cypher else []

    def fake_make_kg_runners():
        calls["made"] += 1
        return fake_read, fake_read, (lambda: calls.__setitem__("closed", calls["closed"] + 1))

    monkeypatch.setattr("engine.cli.runtime.make_kg_runners", fake_make_kg_runners)
    res = occam_dedupe_impl(backend="neo4j")
    assert res["mode"] == "occam"
    assert res["scanned_nodes"] == 2
    assert res["superseded_candidates"] == 1
    assert res["dry_run"] is True  # apply 기본 False (covenant)
    assert calls["made"] == 1
    assert calls["closed"] == 1  # 러너 close 됨 (driver 누수 방지)


def test_occam_dedupe_backend_neo4j_degrades_when_unavailable(monkeypatch):
    # bolt/MCP 둘 다 없으면 crash가 아니라 정직한 degraded payload.
    monkeypatch.setattr("engine.cli.runtime.make_kg_runners", lambda: None)
    res = occam_dedupe_impl(backend="neo4j")
    assert res["mode"] == "degraded"
    assert "backend" in res["reason"].lower() or "kg" in res["reason"].lower()
