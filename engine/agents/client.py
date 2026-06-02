"""AgentClient — dual-backend LLM 래퍼. LLM 군단장(프로메테우스/나생문/재배맨)의 실행 기반.

두 백엔드 (Anthropic 키 *불필요* 경로 포함):
  ① **openai-compat** (vLLM/Ollama/LM Studio/any OpenAI-compatible) — BHGMAN_LLM_BASE_URL 설정 시.
     무의존 stdlib urllib POST /chat/completions. DGX vLLM(Qwen 등) 로컬 LLM에 그대로 붙음.
     model은 BHGMAN_LLM_MODEL로 *override* (군단장이 넘긴 claude-* 무시 — 로컬 서빙 모델명 사용).
     web_search/effort/cache 미지원(silently 무시) — 로컬 LLM엔 server-side tool 없음.
  ② **anthropic** — ANTHROPIC_API_KEY + anthropic SDK. system 캐시, effort 가드, web_search pause_turn.

graceful degrade: 둘 다 불가면 AgentRuntimeUnavailable → CLI가 skill-route fallback.
backend 우선순위: 주입(client=/http_post=) > BHGMAN_LLM_BASE_URL(local) > ANTHROPIC_API_KEY.

# KG: bhgman-llm-commander-runtime-2026-05-28, bhgman-llm-openai-compat-backend-2026-05-28
"""

from __future__ import annotations

import json
import os
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass

from engine.agents.agent_models import EFFORT_CAPABLE

DEFAULT_MAX_TOKENS = 4096
WEB_SEARCH_TOOL = {"type": "web_search_20260209", "name": "web_search"}


class AgentRuntimeUnavailable(RuntimeError):
    """LLM 런타임 사용 불가 (백엔드 없음). 호출자가 degrade."""


def _local_base_url() -> str | None:
    return os.environ.get("BHGMAN_LLM_BASE_URL")


def runtime_status() -> tuple[bool, str]:
    """(available, reason). local(OpenAI-compat) 먼저, 없으면 anthropic. CLI 분기용."""
    if _local_base_url():
        if not os.environ.get("BHGMAN_LLM_MODEL"):
            return False, "BHGMAN_LLM_BASE_URL 있으나 BHGMAN_LLM_MODEL 미설정"
        return True, f"openai-compat @ {_local_base_url()}"
    try:
        import anthropic  # noqa: F401,PLC0415
    except ImportError:
        return (
            False,
            "백엔드 없음 — BHGMAN_LLM_BASE_URL(로컬 LLM) 또는 anthropic SDK+ANTHROPIC_API_KEY",
        )
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return False, "ANTHROPIC_API_KEY 미설정 (또는 BHGMAN_LLM_BASE_URL로 로컬 LLM 지정)"
    return True, "anthropic"


@dataclass(frozen=True)
class Completion:
    """단일 호출 결과 + 사용량."""

    text: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    stop_reason: str = ""


def _urllib_post(url: str, payload: dict, headers: dict, timeout: float) -> dict:
    """무의존 JSON POST (stdlib). openai-compat 백엔드 기본 transport."""
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json", **headers}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 — 신뢰된 LLM endpoint
        return json.loads(resp.read().decode())


class AgentClient:
    """dual-backend. client=(anthropic 주입) / http_post=(openai-compat 주입)은 테스트용."""

    def __init__(
        self, client=None, http_post: Callable | None = None, max_continuations: int = 5
    ) -> None:
        self._max_cont = max_continuations
        if client is not None:  # 주입된 anthropic-like (테스트)
            self._mode, self._c = "anthropic", client
            return
        if http_post is not None:  # 주입된 openai-compat transport (테스트)
            self._mode, self._post = "openai", http_post
            self._base = _local_base_url() or "http://injected/v1"
            self._model = os.environ.get("BHGMAN_LLM_MODEL", "local-model")
            self._key = os.environ.get("BHGMAN_LLM_API_KEY", "EMPTY")
            return
        ok, reason = runtime_status()
        if not ok:
            raise AgentRuntimeUnavailable(reason)
        base_url = _local_base_url()
        if base_url:  # 실 openai-compat (vLLM/DGX)
            self._mode, self._post = "openai", _urllib_post
            self._base = base_url.rstrip("/")
            self._model = os.environ["BHGMAN_LLM_MODEL"]
            self._key = os.environ.get("BHGMAN_LLM_API_KEY", "EMPTY")
        else:  # 실 anthropic
            import anthropic  # noqa: PLC0415

            self._mode, self._c = "anthropic", anthropic.Anthropic()

    def complete(
        self,
        *,
        system: str,
        user: str,
        model: str,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        effort: str | None = None,
        web_search: bool = False,
        temperature: float | None = None,
    ) -> Completion:
        """1회 호출. openai-compat면 로컬 모델로(web_search/effort 무시), anthropic이면 full.

        temperature: best-of-N sampling diversity용 (None=백엔드 기본). 양 백엔드 plumb."""
        if self._mode == "openai":
            return self._complete_openai(system, user, max_tokens, temperature)
        return self._complete_anthropic(
            system, user, model, max_tokens, effort, web_search, temperature
        )

    def _complete_openai(
        self, system: str, user: str, max_tokens: int, temperature: float | None = None
    ) -> Completion:
        payload = {
            "model": self._model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "max_tokens": max_tokens,
        }
        if temperature is not None:
            payload["temperature"] = temperature
        headers = {"Authorization": f"Bearer {self._key}"}
        resp = self._post(f"{self._base}/chat/completions", payload, headers, 120.0)
        choice = (resp.get("choices") or [{}])[0]
        text = (choice.get("message") or {}).get("content") or ""
        usage = resp.get("usage") or {}
        return Completion(
            text=text,
            model=resp.get("model", self._model),
            input_tokens=usage.get("prompt_tokens", 0) or 0,
            output_tokens=usage.get("completion_tokens", 0) or 0,
            stop_reason=choice.get("finish_reason", "") or "",
        )

    def _complete_anthropic(
        self, system, user, model, max_tokens, effort, web_search, temperature=None
    ) -> Completion:
        system_blocks = [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]
        kwargs: dict = {"model": model, "max_tokens": max_tokens, "system": system_blocks}
        if temperature is not None:
            kwargs["temperature"] = temperature
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
            messages = [
                {"role": "user", "content": user},
                {"role": "assistant", "content": resp.content},
            ]
        assert resp is not None  # loop body runs at least once (max_cont >= 1)
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
