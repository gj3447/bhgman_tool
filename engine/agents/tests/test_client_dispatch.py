"""AgentClient + 재배맨 dispatch TDD (FakeAnthropic, 실 키 불필요).

# KG: bhgman-llm-commander-runtime-2026-05-28
"""

from __future__ import annotations

import pytest
from client import AgentClient, AgentRuntimeUnavailable, runtime_status
from dispatch import SubagentSpec, dispatch_parallel
from fake_anthropic import FakeAnthropic
from agent_models import EFFORT_CAPABLE, HAIKU, OPUS


def test_runtime_status_no_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    ok, reason = runtime_status()
    # SDK 미설치거나 키 부재 — 둘 다 unavailable
    assert ok is False
    assert "ANTHROPIC_API_KEY" in reason or "anthropic SDK" in reason


def test_client_requires_runtime_or_injection(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(AgentRuntimeUnavailable):
        AgentClient()  # 주입 없음 + 키 없음 → degrade


def test_complete_returns_text_and_caches_system():
    fake = FakeAnthropic(lambda s, u, m: f"echo:{u}")
    c = AgentClient(client=fake)
    out = c.complete(system="SYS", user="hello", model=HAIKU)
    assert out.text == "echo:hello"
    # system은 ephemeral 캐시 블록으로 전달
    sent = fake.messages.calls[0]["system"]
    assert sent[0]["cache_control"] == {"type": "ephemeral"}


def test_effort_only_for_capable_model():
    fake = FakeAnthropic(lambda s, u, m: "x")
    c = AgentClient(client=fake)
    c.complete(system="S", user="u", model=OPUS, effort="high")
    assert fake.messages.calls[0].get("output_config") == {"effort": "high"}
    fake2 = FakeAnthropic(lambda s, u, m: "x")
    AgentClient(client=fake2).complete(system="S", user="u", model=HAIKU, effort="high")
    assert "output_config" not in fake2.messages.calls[0]  # Haiku엔 effort 안 붙음(400 방지)
    assert HAIKU not in EFFORT_CAPABLE and OPUS in EFFORT_CAPABLE


def test_dispatch_parallel_preserves_order_and_isolates_failure():
    def responder(s, u, m):
        if "boom" in u:
            raise RuntimeError("kaboom")
        return f"ok:{u}"

    c = AgentClient(client=FakeAnthropic(responder))
    specs = [
        SubagentSpec("a", "S", "u1"),
        SubagentSpec("b", "S", "boom"),
        SubagentSpec("c", "S", "u3"),
    ]
    results = dispatch_parallel(specs, c)
    assert [r.name for r in results] == ["a", "b", "c"]  # 순서 보존
    assert results[0].ok and results[0].text == "ok:u1"
    assert results[1].ok is False and "kaboom" in results[1].error  # 실패 격리
    assert results[2].ok and results[2].text == "ok:u3"


def test_dispatch_empty():
    c = AgentClient(client=FakeAnthropic(lambda s, u, m: "x"))
    assert dispatch_parallel([], c) == []
