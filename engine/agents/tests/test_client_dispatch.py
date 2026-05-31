"""AgentClient + 재배맨 dispatch TDD (FakeAnthropic, 실 키 불필요).

# KG: bhgman-llm-commander-runtime-2026-05-28
"""

from __future__ import annotations

import pytest
from engine.agents.client import AgentClient, AgentRuntimeUnavailable, runtime_status
from engine.agents.dispatch import SubagentSpec, dispatch_parallel
from fake_anthropic import FakeAnthropic
from engine.agents.agent_models import EFFORT_CAPABLE, HAIKU, OPUS


def test_runtime_status_no_backend(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("BHGMAN_LLM_BASE_URL", raising=False)
    ok, reason = runtime_status()
    assert ok is False
    assert "ANTHROPIC_API_KEY" in reason or "백엔드" in reason


def test_runtime_status_local_openai_backend(monkeypatch):
    monkeypatch.setenv("BHGMAN_LLM_BASE_URL", "http://dgx:8000/v1")
    monkeypatch.setenv("BHGMAN_LLM_MODEL", "qwen3.6-27b")
    ok, reason = runtime_status()
    assert ok is True and "openai-compat" in reason  # Anthropic 키 불필요


def test_client_requires_runtime_or_injection(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("BHGMAN_LLM_BASE_URL", raising=False)
    with pytest.raises(AgentRuntimeUnavailable):
        AgentClient()  # 주입 없음 + 백엔드 없음 → degrade


def test_openai_compat_backend_overrides_model_skips_anthropic_features(monkeypatch):
    monkeypatch.setenv("BHGMAN_LLM_MODEL", "qwen3.6-27b")  # DGX vLLM 서빙 모델
    calls = []

    def fake_post(url, payload, headers, timeout):
        calls.append((url, payload, headers))
        return {
            "model": payload["model"],
            "choices": [
                {
                    "message": {"content": "echo:" + payload["messages"][-1]["content"]},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 3, "completion_tokens": 2},
        }

    c = AgentClient(http_post=fake_post)  # openai-compat 모드 (Anthropic 키 불필요)
    out = c.complete(
        system="S", user="hi", model="claude-haiku-4-5", web_search=True, effort="high"
    )
    assert out.text == "echo:hi"
    url, payload, headers = calls[0]
    assert url.endswith("/chat/completions")
    assert payload["model"] == "qwen3.6-27b"  # claude-* 무시, 로컬 모델 override
    assert (
        "tools" not in payload and "output_config" not in payload
    )  # web_search/effort 미지원 무시
    assert headers["Authorization"].startswith("Bearer ")


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
