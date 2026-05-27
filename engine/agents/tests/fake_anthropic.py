"""FakeAnthropic — 실 API 키 없이 AgentClient를 검증하는 주입용 더블.

responder(system_text, user_text, model) -> str 콜백으로 응답 제어. messages.create의
실 Anthropic 응답 모양(.content[블록].text / .usage / .stop_reason / .model)만 흉내.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass
class _Block:
    text: str
    type: str = "text"


@dataclass
class _Usage:
    input_tokens: int = 10
    output_tokens: int = 5
    cache_read_input_tokens: int = 0


@dataclass
class _Resp:
    content: list
    model: str = "fake-model"
    stop_reason: str = "end_turn"
    usage: _Usage = None  # type: ignore[assignment]


class _FakeMessages:
    def __init__(self, responder: Callable[[str, str, str], str]) -> None:
        self._r = responder
        self.calls: list[dict] = []

    def create(self, *, model, max_tokens, system, messages, **kw):
        self.calls.append({"model": model, "system": system, "messages": messages, **kw})
        sys_text = system[0]["text"] if isinstance(system, list) else str(system)
        user = messages[-1]["content"]
        return _Resp(content=[_Block(self._r(sys_text, user, model))], model=model, usage=_Usage())


class FakeAnthropic:
    """AgentClient(client=FakeAnthropic(responder))로 주입."""

    def __init__(self, responder: Callable[[str, str, str], str]) -> None:
        self.messages = _FakeMessages(responder)
