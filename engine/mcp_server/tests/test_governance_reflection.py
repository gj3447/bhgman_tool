"""MCP 거버넌스 reflection oracle (T1-4) — 손-목록이 아닌 실등록면이 정본.

drift class (실측 2026-07-15): `prometheus_ingest` 가 `@mcp.tool()` 로 실등록되면서
server.list_registered_tool_names 손-목록 / security.TOOL_CAPABILITIES / registry 카탈로그
세 장부 모두에 없어, boot trifecta 감사와 per-call 미들웨어를 빈 capability 로 통과했다.
기존 parity 테스트(test_registry)는 손목록↔카탈로그만 비교해 이 class 를 구조적으로 못 본다.

고정하는 계약 3개:
  1. 실등록면(registrar introspection) == TOOL_CAPABILITIES == TOOL_CATALOG (3-way).
  2. 미등록 tool 은 fail-closed — 빈 capability 가 아니라 보수적 가정.
  3. kg_query 원격 경로의 비밀번호는 어떤 argv 에도 실리지 않는다 (stdin 전달).

# KG: mcp-security-trifecta-2026-05-25, cycle-bhgman-tier0-loop-wiring-2026-07-15
"""

from __future__ import annotations

import engine.mcp_server.security as security
from engine.mcp_server.registry import TOOL_CATALOG
from engine.mcp_server.security import Capability, audit_tool_call, audit_toolset
from engine.mcp_server.server import list_registered_tool_names
from engine.mcp_server.tools import symposium


def test_three_way_surface_parity():
    """실등록면 == TOOL_CAPABILITIES == 카탈로그. 새 @mcp.tool() 등록이 거버넌스 장부에
    빠지면 여기서 RED — prometheus_ingest 가 그 현행범이었다."""
    registered = set(list_registered_tool_names())
    caps = set(security.TOOL_CAPABILITIES.keys())
    catalogued = set(TOOL_CATALOG.keys())
    assert registered == caps, (
        f"registered-caps drift: only-registered={registered - caps}, only-caps={caps - registered}"
    )
    assert registered == catalogued, (
        f"registered-catalog drift: only-registered={registered - catalogued}, "
        f"only-catalog={catalogued - registered}"
    )


def test_registered_list_is_introspected_not_hand_maintained():
    """prometheus_ingest 는 실등록 tool — 손-목록 시절 누락됐던 이름이 introspection 에 잡힌다."""
    assert "prometheus_ingest" in list_registered_tool_names()


def test_live_fastmcp_surface_agrees_with_introspection():
    """fake-registrar introspection ↔ 실제 FastMCP 인스턴스 표면 일치 (fake 자체의 drift 방지)."""
    import asyncio

    import pytest

    pytest.importorskip("fastmcp")
    from engine.mcp_server.server import build_server

    mcp = build_server()
    lister = getattr(mcp, "get_tools", None) or mcp.list_tools  # fastmcp 2.x / 3.x
    tools = asyncio.run(lister())
    live = set(tools.keys() if isinstance(tools, dict) else [t.name for t in tools])
    assert live == set(list_registered_tool_names())


def test_unknown_tool_fails_closed_in_call_audit():
    """미등록 tool 호출 감사는 빈 capability(최관용)가 아니라 보수적 가정이어야 한다."""
    report = audit_tool_call("nonexistent_tool_xyz", {}, mode=security.SecurityMode.AUDIT)
    assert Capability.READS_PRIVATE_DATA.value in report.capabilities, (
        "unknown tool passed the per-call audit with EMPTY capabilities (fail-open)"
    )
    assert Capability.MUTATES_DATA.value in report.capabilities


def test_unknown_tool_counts_toward_trifecta():
    """toolset 합성 감사에서도 미등록 tool 은 보수적으로 기여한다 (침묵 0-기여 금지)."""
    report = audit_toolset(["nonexistent_tool_xyz"])
    assert Capability.READS_PRIVATE_DATA.value in report.present_capabilities


def test_kg_query_password_never_on_argv(monkeypatch):
    """비밀번호는 ssh/kubectl/cypher-shell 어느 argv 에도 없고 stdin 첫 줄로만 전달된다.

    공유 dgx 호스트에서 `ps` 로 보이는 argv 는 유출면이다 (bhg-f-secrets-on-argv)."""
    import subprocess as sp

    secret = "s3cr3t-argv-canary"
    monkeypatch.setenv("BHGMAN_STATUS_NEO4J_PASSWORD", secret)
    captured: dict = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["input"] = kwargs.get("input")
        return sp.CompletedProcess(cmd, 0, stdout="ok", stderr="")

    monkeypatch.setattr(symposium.subprocess, "run", fake_run)
    out = symposium._ssh_cypher("MATCH (n) RETURN count(n)", {"x": "y"})
    assert out["ok"] is True
    joined = " ".join(captured["cmd"])
    assert secret not in joined, "password leaked into argv"
    assert captured["input"].startswith(secret + "\n"), "password must be stdin line 1"
    assert "MATCH (n) RETURN count(n)" in captured["input"]
    # stdin 이 pod 까지 실제로 도달하려면 kubectl 에 -i 가 필수 (없으면 조용히 버려진다).
    assert "kubectl exec -i" in joined
