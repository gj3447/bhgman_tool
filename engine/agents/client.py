"""AgentClient — Anthropic API wrapper. LLM 군단장(프로메테우스/나생문)의 실행 기반.

graceful degrade: anthropic SDK 미설치 OR ANTHROPIC_API_KEY 부재 → AgentRuntimeUnavailable
(neo4j 없을 때 cypher print degrade와 같은 정신 — 조용한 실패 금지).

claude-api skill 정본 준수:
  - 모델 ID는 agent_models.py 단일 출처 (날짜 suffix 금지).
  - system prompt는 cache_control(ephemeral) — 반복 prefix 캐싱(claude-api prompt-caching).
  - effort는 Opus/Sonnet만 (Haiku에 주면 400 → EFFORT_CAPABLE 가드).
  - web_search 서버툴 사용 시 pause_turn 서버 루프 재전송 처리.
  - typed exception은 호출자가 anthropic.* 로 잡음 (여기선 SDK 그대로 전파).

테스트: client= 주입(FakeClient) → 실 API 키 없이 검증.

# KG: bhgman-llm-commander-runtime-2026-05-28
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from agent_models import EFFORT_CAPABLE

DEFAULT_MAX_TOKENS = 4096
WEB_SEARCH_TOOL = {"type": "web_search_20260209", "name": "web_search"}


class AgentRuntimeUnavailable(RuntimeError):
    """LLM 런타임 사용 불가 (SDK 미설치 / 키 부재). 호출자가 degrade."""


def runtime_status() -> tuple[bool, str]:
    """(available, reason). CLI가 실행 vs skill-route 분기에 사용."""
    try:
        import anthropic  # noqa: F401,PLC0415
    except ImportError:
        return False, "anthropic SDK 미설치 — pip install 'bhgman_tool[agents]'"
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return False, "ANTHROPIC_API_KEY 미설정"
    return True, "ok"


@dataclass(frozen=True)
class Completion:
    """단일 API 호출 결과 + 사용량(비용 추적)."""

    text: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    stop_reason: str = ""


class AgentClient:
    """messages.create 얇은 래퍼. client= 주입 시 그것을 씀(테스트), 아니면 실 Anthropic()."""

    def __init__(self, client=None, max_continuations: int = 5) -> None:
        if client is None:
            ok, reason = runtime_status()
            if not ok:
                raise AgentRuntimeUnavailable(reason)
            import anthropic  # noqa: PLC0415

            client = anthropic.Anthropic()
        self._c = client
        self._max_cont = max_continuations

    def complete(
        self,
        *,
        system: str,
        user: str,
        model: str,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        effort: str | None = None,
        web_search: bool = False,
    ) -> Completion:
        """1회 호출. system은 캐시(ephemeral). web_search 시 pause_turn 서버루프 처리."""
        system_blocks = [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]
        kwargs: dict = {
            "model": model,
            "max_tokens": max_tokens,
            "system": system_blocks,
        }
        if effort and model in EFFORT_CAPABLE:
            kwargs["output_config"] = {"effort": effort}
        if web_search:
            kwargs["tools"] = [WEB_SEARCH_TOOL]

        messages = [{"role": "user", "content": user}]
        resp = None
        for _ in range(self._max_cont):
            resp = self._c.messages.create(messages=messages, **kwargs)
            if getattr(resp, "stop_reason", None) != "pause_turn":
                break
            # 서버툴(web_search) 미완 — user+assistant 재전송으로 resume (claude-api tool-use).
            messages = [
                {"role": "user", "content": user},
                {"role": "assistant", "content": resp.content},
            ]

        text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
        usage = getattr(resp, "usage", None)
        return Completion(
            text=text,
            model=getattr(resp, "model", model),
            input_tokens=getattr(usage, "input_tokens", 0) or 0,
            output_tokens=getattr(usage, "output_tokens", 0) or 0,
            cache_read_tokens=getattr(usage, "cache_read_input_tokens", 0) or 0,
            stop_reason=getattr(resp, "stop_reason", "") or "",
        )


__all__ = [
    "DEFAULT_MAX_TOKENS",
    "WEB_SEARCH_TOOL",
    "AgentClient",
    "AgentRuntimeUnavailable",
    "Completion",
    "runtime_status",
]
