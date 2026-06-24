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

import http.client
import json
import os
import re
import threading
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urlparse

from engine.agents.agent_models import EFFORT_CAPABLE

DEFAULT_MAX_TOKENS = 4096
WEB_SEARCH_TOOL = {"type": "web_search_20260209", "name": "web_search"}
# openai-compat ReAct: 모델이 검색을 요청하는 한 줄 신호 (server-side tool 없는 로컬 LLM용)
_SEARCH_RE = re.compile(r"(?m)^\s*SEARCH:\s*(.+?)\s*$")


class AgentRuntimeUnavailable(RuntimeError):
    """LLM 런타임 사용 불가 (백엔드 없음). 호출자가 degrade."""


class LLMHTTPError(RuntimeError):
    """openai-compat 백엔드가 non-2xx 반환 (예: 122B OOM 500). dispatch/synth fallback 트리거용.

    urllib.request.urlopen 은 4xx/5xx 에 HTTPError 를 던지지만 http.client(keep-alive 풀드)는
    안 던지므로, 두 transport 의 의미를 일치시켜 dead tier-1 이 graceful degrade 되게 한다.
    """


def _local_base_url() -> str | None:
    return os.environ.get("BHGMAN_LLM_BASE_URL")


@dataclass(frozen=True)
class Endpoint:
    """한 openai-compat 백엔드 (DGX 35B / Ollama 122B 등). tier로 라우팅.

    tier 0 = fast/cheap (35B 브레드스). tier 1 = big/slow (하드 축·synth·verify, 디코릴레이터).
    max_concurrency = 이 백엔드에 동시에 흘릴 수 있는 상한 (Ollama는 OLLAMA_NUM_PARALLEL 얕음 →
    범람시 thrash; dispatch가 per-endpoint 세마포어로 가드).
    """

    name: str
    base_url: str
    model: str
    key: str = "EMPTY"
    tier: int = 0
    max_concurrency: int = 32


def _load_endpoints() -> list[Endpoint] | None:
    """BHGMAN_LLM_ENDPOINTS(JSON list) → [Endpoint]. unset/malformed → None(레거시 단일 경로).

    절대 raise 하지 않는다 — JSON 파싱 실패나 필드 누락은 None 으로 떨어져 레거시
    BHGMAN_LLM_BASE_URL/MODEL 단일 백엔드로 graceful fallback (엔진 죽이지 않음).
    """
    raw = os.environ.get("BHGMAN_LLM_ENDPOINTS")
    if not raw:
        return None
    try:
        items = json.loads(raw)
        if not isinstance(items, list) or not items:
            return None
        eps: list[Endpoint] = []
        for it in items:
            eps.append(
                Endpoint(
                    name=str(it["name"]),
                    base_url=str(it["base_url"]).rstrip("/"),
                    model=str(it["model"]),
                    key=str(it.get("key", "EMPTY")),
                    tier=int(it.get("tier", 0)),
                    max_concurrency=int(it.get("max_concurrency", 32)),
                )
            )
        return eps or None
    except (ValueError, TypeError, KeyError):  # malformed JSON / 필드 누락 → 레거시 fallback
        return None


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
    # L6: openai-compat tool-call (FOLLOWUPS emit_followups 등). [{name, arguments(str)}].
    tool_calls: tuple[dict, ...] = ()


def _urllib_post(url: str, payload: dict, headers: dict, timeout: float) -> dict:
    """무의존 JSON POST (stdlib). openai-compat 백엔드 기본 transport (주입 fallback)."""
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json", **headers}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 — 신뢰된 LLM endpoint
        return json.loads(resp.read().decode())


# 스레드별 keep-alive 연결 풀. http.client.HTTPConnection은 thread-safe 하지 않고
# ThreadPoolExecutor가 worker 스레드를 재사용하므로 threading.local 이 必수다.
# (scheme,host,port)로 키잉 — Layer 4(2번째 백엔드)가 다른 host로 가도 소켓이 안 섞이게.
_POOL = threading.local()


def _pooled_post(url: str, payload: dict, headers: dict, timeout: float) -> dict:
    """keep-alive 풀드 JSON POST. 느린 192.168.10.x 링크의 TCP 핸드셰이크를 스레드당 1번만 지불.

    stale/half-open 소켓은 재사용 시 예외를 던지므로, 그런 경우 1회 재연결-후-재시도한다.
    """
    u = urlparse(url)
    key = (u.scheme, u.hostname, u.port)
    conns = getattr(_POOL, "conns", None)
    if conns is None:
        conns = _POOL.conns = {}

    def _fresh() -> http.client.HTTPConnection:
        ctor = http.client.HTTPSConnection if u.scheme == "https" else http.client.HTTPConnection
        return ctor(u.hostname, u.port, timeout=timeout)

    path = u.path or "/"
    if u.query:
        path = f"{path}?{u.query}"
    body = json.dumps(payload).encode()
    hdrs = {"Content-Type": "application/json", "Connection": "keep-alive", **headers}
    conn = conns.get(key) or _fresh()
    for attempt in (1, 2):  # reconnect-once on stale/half-open socket
        try:
            conn.request("POST", path, body, hdrs)
            resp = conn.getresponse()
            status = resp.status
            data = resp.read()  # keep-alive 유지하려면 응답 본문을 반드시 다 읽어야 함
            conns[key] = conn
            if status >= 400:  # 4xx/5xx (예: 122B OOM 500) → urllib 처럼 raise → caller fallback
                raise LLMHTTPError(f"HTTP {status}: {data[:200].decode(errors='replace')}")
            return json.loads(data.decode())
        except LLMHTTPError:
            raise  # 상태 에러는 재연결로 안 풀림 — 바로 위로 (소켓은 keep-alive 유지 가능)
        except (
            http.client.RemoteDisconnected,
            http.client.BadStatusLine,
            ConnectionError,
            OSError,
        ):
            try:
                conn.close()
            except Exception:  # noqa: BLE001 — 소켓 정리 best-effort
                pass
            conns.pop(key, None)
            if attempt == 2:
                raise
            conn = _fresh()
    raise AssertionError("unreachable")  # pragma: no cover


class AgentClient:
    """dual-backend. client=(anthropic 주입) / http_post=(openai-compat 주입)은 테스트용."""

    def __init__(
        self, client=None, http_post: Callable | None = None, max_continuations: int = 5
    ) -> None:
        self._max_cont = max_continuations
        # tier→[Endpoint] 라우팅 테이블. None(레거시/주입)이면 self._base/_model/_key 단일 경로.
        self._endpoints: list[Endpoint] | None = None
        self._by_tier: dict[int, list[Endpoint]] = {}
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
        self._post: Callable | None = None
        base_url = _local_base_url()
        if base_url:  # 실 openai-compat (vLLM/DGX)
            # 기본 keep-alive 풀드 transport(느린 링크서 핸드셰이크 절약); 0 이면 stdlib 단발.
            post = (
                _pooled_post if os.environ.get("BHGMAN_LLM_KEEPALIVE", "1") == "1" else _urllib_post
            )
            self._mode, self._post = "openai", post
            self._base = base_url.rstrip("/")
            self._model = os.environ["BHGMAN_LLM_MODEL"]
            self._key = os.environ.get("BHGMAN_LLM_API_KEY", "EMPTY")
            # L4: 멀티 엔드포인트(tier 라우팅). malformed/unset → None → 위 단일 base 유지.
            eps = _load_endpoints()
            if eps:
                self._endpoints = eps
                for ep in eps:
                    self._by_tier.setdefault(ep.tier, []).append(ep)
        else:  # 실 anthropic
            import anthropic  # noqa: PLC0415

            self._mode, self._c = "anthropic", anthropic.Anthropic()

    def endpoint_for_tier(self, tier: int | None) -> Endpoint | None:
        """tier → Endpoint (없으면 가장 낮은 tier로 fallback). 엔드포인트 미구성이면 None."""
        if not self._endpoints:
            return None
        if tier is not None and self._by_tier.get(tier):
            return self._by_tier[tier][0]
        # 요청 tier 없음/미존재 → 가장 낮은 tier (보통 0=fast breadth)
        lowest = min(self._by_tier)
        return self._by_tier[lowest][0]

    def _resolve_target(self, tier: int | None) -> tuple[str, str, str]:
        """(base_url, model, key) 결정. 엔드포인트 구성됐으면 tier로, 아니면 레거시 단일.

        이게 'complete()가 caller model 을 버리던 死코드 버그'의 수정점 — 물리 모델이
        tier→endpoint 로 선택된다(레거시면 self._model 그대로 → 기존 테스트 불변)."""
        ep = self.endpoint_for_tier(tier)
        if ep is not None:
            return ep.base_url, ep.model, ep.key
        return self._base, self._model, self._key

    def endpoint_concurrency(self) -> dict[str, int]:
        """{base_url: max_concurrency} — dispatch per-endpoint 세마포어 사이징용."""
        if not self._endpoints:
            return {}
        return {ep.base_url: ep.max_concurrency for ep in self._endpoints}

    def is_local(self) -> bool:
        """openai-compat(로컬 vLLM/DGX·주입 transport) 백엔드면 True. anthropic 이면 False.

        web_search 게이팅용 — 로컬 백엔드엔 Anthropic server-side web_search 도구가 없고,
        SearXNG ReAct 경로는 K×N width 에서 라운드당 직렬 round-trip 세금이라 끄는 게 맞다.
        """
        return self._mode == "openai"

    def complete(
        self,
        *,
        system: str,
        user: str,
        model: str,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        effort: str | None = None,
        web_search: bool = False,
        temperature: float = 0.0,
        seed: int | None = None,
        tier: int | None = None,
        tools: list[dict] | None = None,
        tool_choice: str | dict | None = None,
    ) -> Completion:
        """1회 호출. openai-compat면 로컬 모델로(web_search/effort 무시), anthropic이면 full.

        temperature/seed = self-consistency K-샘플링 on-switch (openai-compat만 적용; vLLM이 per-request
        로 sampler 를 켠다). 기본 0.0/None 이면 payload 미주입 = 오늘의 greedy 동작 그대로.
        anthropic 경로는 parity 위해 accept-and-ignore.

        tier(L4): 멀티 엔드포인트 구성시 물리 백엔드/모델을 tier 로 고른다. 미구성이면 무시
        (레거시 단일 base/model). tier=1 = 큰 모델(122B, 디코릴레이터/하드 축/synth).

        tools/tool_choice(L6): openai-compat tool-calling (FOLLOWUPS emit_followups 강제용).
        web_search ReAct 와 배타 — tools 주면 단발 POST 로 tool_calls 를 받는다.
        """
        if self._mode == "openai":
            base, mdl, key = self._resolve_target(tier)
            if tools is not None:  # L6: tool-call 경로 — ReAct 루프 우회, 단발
                return self._openai_post(
                    [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    max_tokens,
                    temperature=temperature,
                    seed=seed,
                    base=base,
                    model=mdl,
                    key=key,
                    tools=tools,
                    tool_choice=tool_choice,
                )
            return self._complete_openai(
                system,
                user,
                max_tokens,
                web_search,
                temperature=temperature,
                seed=seed,
                base=base,
                model=mdl,
                key=key,
            )
        return self._complete_anthropic(system, user, model, max_tokens, effort, web_search)

    def _openai_post(
        self,
        messages: list[dict],
        max_tokens: int,
        *,
        temperature: float = 0.0,
        seed: int | None = None,
        base: str | None = None,
        model: str | None = None,
        key: str | None = None,
        tools: list[dict] | None = None,
        tool_choice: str | dict | None = None,
    ) -> Completion:
        """openai-compat /chat/completions 단발 호출 (멀티턴 messages 그대로 POST).

        base/model/key 미지정이면 레거시 단일 백엔드(self._base/_model/_key) 사용 (기존 동작).
        지정시 그 (tier→endpoint) 물리 백엔드로 POST — caller model 을 버리던 死코드 수정.

        BHGMAN_LLM_NO_THINK 설정 시 Qwen reasoning(think)을 끈다(chat_template_kwargs).
        느린 로컬 GPU(GB10 ~4tok/s)에서 ReAct 멀티라운드의 think 토큰 폭발을 막아 실용 속도 확보.
        """
        base = base if base is not None else self._base
        model = model if model is not None else self._model
        key = key if key is not None else self._key
        payload: dict = {"model": model, "messages": messages, "max_tokens": max_tokens}
        if temperature:  # 0.0 = greedy = 오늘 동작 → 미주입 (back-compat)
            payload["temperature"] = temperature
        if seed is not None:
            payload["seed"] = seed
        if tools is not None:  # L6 tool-calling
            payload["tools"] = tools
            if tool_choice is not None:
                payload["tool_choice"] = tool_choice
        if os.environ.get("BHGMAN_LLM_NO_THINK"):
            payload["chat_template_kwargs"] = {"enable_thinking": False}
        headers = {"Authorization": f"Bearer {key}"}
        timeout = float(
            os.environ.get("BHGMAN_LLM_TIMEOUT", "120")
        )  # reasoning models load+think slowly
        resp = self._post(f"{base}/chat/completions", payload, headers, timeout)
        choice = (resp.get("choices") or [{}])[0]
        msg = choice.get("message") or {}
        text = msg.get("content") or ""
        tcs: tuple[dict, ...] = ()
        if msg.get("tool_calls"):
            tcs = tuple(
                {
                    "name": (tc.get("function") or {}).get("name", ""),
                    "arguments": (tc.get("function") or {}).get("arguments", ""),
                }
                for tc in msg["tool_calls"]
            )
        usage = resp.get("usage") or {}
        return Completion(
            text=text,
            model=resp.get("model", model),
            input_tokens=usage.get("prompt_tokens", 0) or 0,
            output_tokens=usage.get("completion_tokens", 0) or 0,
            stop_reason=choice.get("finish_reason", "") or "",
            tool_calls=tcs,
        )

    def _complete_openai(
        self,
        system: str,
        user: str,
        max_tokens: int,
        web_search: bool = False,
        *,
        temperature: float = 0.0,
        seed: int | None = None,
        base: str | None = None,
        model: str | None = None,
        key: str | None = None,
    ) -> Completion:
        """openai-compat. web_search=True + BHGMAN_SEARXNG_URL 이면 ReAct 검색 루프.

        로컬 LLM 엔 server-side web_search 가 없으므로, 모델이 `SEARCH: <쿼리>` 를 출력하면
        우리(SearXNG self-host)가 검색을 실행해 결과를 다시 주입하는 client-side tool 루프.
        토큰 사용량은 전 라운드 누적해서 반환. temperature/seed 는 모든 라운드에 동일 적용.
        """
        from engine.agents import web_search_local as _ws  # noqa: PLC0415

        # tier→endpoint 가 고른 물리 백엔드를 모든 라운드에 전파(레거시면 None → self._*).
        _t = {"base": base, "model": model, "key": key}

        if not (web_search and _ws.searxng_url()):
            return self._openai_post(
                [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                max_tokens,
                temperature=temperature,
                seed=seed,
                **_t,
            )

        instr = (
            "\n\n[웹검색 도구] 외부·최신 정보가 필요하면, 설명 없이 한 줄에 정확히 "
            "`SEARCH: <검색어>` 한 개만 출력하고 멈춰라. 그러면 검색 결과를 받는다. "
            "결과가 충분하면 최종 답을 작성하고, 검색이 불필요하면 바로 답하라."
        )
        messages: list[dict] = [
            {"role": "system", "content": system + instr},
            {"role": "user", "content": user},
        ]
        rounds = int(os.environ.get("BHGMAN_LLM_SEARCH_ROUNDS", "4"))
        tin = tout = 0
        last = self._openai_post(messages, max_tokens, temperature=temperature, seed=seed, **_t)
        tin, tout = tin + last.input_tokens, tout + last.output_tokens
        for _ in range(rounds):
            m = _SEARCH_RE.search(last.text or "")
            if not m:
                break
            query = m.group(1).strip().strip('"').strip("`").strip()
            try:
                obs = _ws.format_results(_ws.searxng_search(query))
            except Exception as e:  # noqa: BLE001 — 검색 실패해도 모델이 degrade 답
                obs = f"(검색 실패: {e})"
            messages.append({"role": "assistant", "content": last.text})
            messages.append(
                {
                    "role": "user",
                    "content": f"`{query}` 검색 결과:\n{obs}\n\n"
                    "이 결과로 최종 답을 작성하거나, 더 필요하면 다시 SEARCH 하라.",
                }
            )
            last = self._openai_post(messages, max_tokens, temperature=temperature, seed=seed, **_t)
            tin, tout = tin + last.input_tokens, tout + last.output_tokens
        if _SEARCH_RE.search(last.text or ""):  # rounds 소진 후에도 검색 요청 → 강제 종합
            messages.append({"role": "assistant", "content": last.text})
            messages.append(
                {
                    "role": "user",
                    "content": "검색 한도 도달. 더 검색하지 말고 지금까지 결과로 최종 답을 작성하라.",
                }
            )
            last = self._openai_post(messages, max_tokens, temperature=temperature, seed=seed, **_t)
            tin, tout = tin + last.input_tokens, tout + last.output_tokens
        return Completion(
            text=last.text,
            model=last.model,
            input_tokens=tin,
            output_tokens=tout,
            stop_reason=last.stop_reason,
        )

    def _complete_anthropic(
        self, system, user, model, max_tokens, effort, web_search
    ) -> Completion:
        system_blocks = [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]
        kwargs: dict = {"model": model, "max_tokens": max_tokens, "system": system_blocks}
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
    "Endpoint",
    "LLMHTTPError",
    "runtime_status",
]
