"""데몬 수준 누적 지출/속도 kill-switch — 에이전트 자기판단과 독립된 정지 권한.

기존 상한은 전부 *1회 run 안*의 것이다 (evolve 의 max_evaluations, LLM 의 budget_tokens).
장수(long-lived) 봇은 tick 마다 그 상한을 새로 받으므로 누적 지출에는 천장이 없다 —
tick 10만 번이면 LLM 비용도 10만 번. PROM16 하네스/루프 표준 §"독립 정지": step 상한 +
무진전 감지 + wall-clock/지출 kill-switch 가 에이전트의 자기판단과 *독립* 이어야 한다.

SpendMeter 는 그 독립 계측기다. AgentClient.complete 를 감싸(instrument_agent_client)
호출 수·토큰을 세고, daemon 이 매 tick 전후로 exceeded() 를 물어 초과 시 타입付
stop_reason='spend_kill' 로 정지한다.

토큰 vs 호출 수: 백엔드가 usage 를 주면(Completion.input_tokens/output_tokens) 토큰으로,
안 주면 호출 수로 센다 — 토큰이 0으로 들어와도 max_llm_calls 는 항상 유효하다.

속도 상한(velocity)은 60초 슬라이딩 윈도우다. 누적 상한이 "총액", 속도 상한이 "분당
지출률" — runaway 재시도 폭주는 총액에 닿기 전에 속도로 먼저 잡힌다.

# KG: prom16-harness-loop-standard (independent stop / spend kill-switch),
#     bhgman-bot-daemon-2026-06-16 (누적 예산 부재의 수정점)
"""

from __future__ import annotations

import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

_WINDOW_SECONDS = 60.0  # 속도 상한 슬라이딩 윈도우 (calls/tokens per minute)


@dataclass(frozen=True)
class SpendLimits:
    """전부 None = 상한 없음 (현행 동작 그대로). 하나라도 주면 그 축만 강제된다."""

    max_llm_calls: int | None = None  # 누적 LLM 호출 수 상한
    max_total_tokens: int | None = None  # 누적 토큰(입력+출력) 상한
    max_calls_per_minute: float | None = None  # 속도 상한 (60s 윈도우)
    max_tokens_per_minute: float | None = None  # 속도 상한 (60s 윈도우)

    @property
    def any_set(self) -> bool:
        return any(
            v is not None
            for v in (
                self.max_llm_calls,
                self.max_total_tokens,
                self.max_calls_per_minute,
                self.max_tokens_per_minute,
            )
        )


class SpendMeter:
    """LLM 호출/토큰 누적 계측 + 상한 판정. now 주입으로 시계 없이 테스트 가능."""

    def __init__(
        self, limits: SpendLimits | None = None, *, now: Callable[[], float] = time.monotonic
    ) -> None:
        self._limits = limits or SpendLimits()
        self._now = now
        self._calls = 0
        self._tokens = 0
        self._window: deque[tuple[float, int]] = deque()  # (timestamp, tokens)

    @property
    def limits(self) -> SpendLimits:
        return self._limits

    @property
    def calls(self) -> int:
        return self._calls

    @property
    def tokens(self) -> int:
        return self._tokens

    def record(self, *, tokens: int = 0) -> None:
        """LLM 호출 1회 계상. tokens=0 이면 호출 수만 (usage 미제공 백엔드)."""
        self._calls += 1
        self._tokens += max(0, int(tokens))
        self._window.append((self._now(), max(0, int(tokens))))
        self._trim()

    def _trim(self) -> None:
        cutoff = self._now() - _WINDOW_SECONDS
        while self._window and self._window[0][0] <= cutoff:
            self._window.popleft()

    def rate(self) -> tuple[int, int]:
        """최근 60초 (호출 수, 토큰 수)."""
        self._trim()
        return len(self._window), sum(t for _, t in self._window)

    def exceeded(self) -> str | None:
        """상한 초과 사유 문자열, 아니면 None. daemon 이 매 tick 물어보는 술어."""
        lim = self._limits
        if lim.max_llm_calls is not None and self._calls >= lim.max_llm_calls:
            return f"llm_calls {self._calls} >= max_llm_calls {lim.max_llm_calls}"
        if lim.max_total_tokens is not None and self._tokens >= lim.max_total_tokens:
            return f"tokens {self._tokens} >= max_total_tokens {lim.max_total_tokens}"
        calls_rate, tokens_rate = self.rate()
        if lim.max_calls_per_minute is not None and calls_rate >= lim.max_calls_per_minute:
            return f"calls/min {calls_rate} >= max_calls_per_minute {lim.max_calls_per_minute}"
        if lim.max_tokens_per_minute is not None and tokens_rate >= lim.max_tokens_per_minute:
            return f"tokens/min {tokens_rate} >= max_tokens_per_minute {lim.max_tokens_per_minute}"
        return None

    def probe(self) -> Callable[[], str | None]:
        """daemon 의 spend_probe 로 넘길 bound 술어."""
        return self.exceeded


def instrument_agent_client(client: Any, meter: SpendMeter) -> Any:
    """client.complete 를 감싸 호출 수/토큰을 meter 에 기록 (in-place, 같은 객체 반환).

    반환값·예외는 그대로 통과시킨다 (관측만, 의미 변경 없음). 실패한 호출도 1 call 로
    계상한다 — 그래야 재시도 폭주가 상한에 닿는다 (실패는 토큰 미상이므로 0 토큰).
    이미 감싼 client 를 다시 감싸지 않는다 (멱등).
    """
    if getattr(client, "_bhgman_spend_metered", False):
        return client
    original = client.complete

    def _metered(*args: Any, **kwargs: Any) -> Any:
        try:
            comp = original(*args, **kwargs)
        except Exception:
            meter.record(tokens=0)  # 실패도 지출 (재시도 폭주 차단)
            raise
        tokens = int(getattr(comp, "input_tokens", 0) or 0) + int(
            getattr(comp, "output_tokens", 0) or 0
        )
        meter.record(tokens=tokens)
        return comp

    client.complete = _metered
    client._bhgman_spend_metered = True
    return client


__all__ = ["SpendLimits", "SpendMeter", "instrument_agent_client"]
