"""데몬 누적 지출/속도 kill-switch (GAP-2) — 에이전트 자기판단과 독립된 정지 권한.

시계는 주입(now) — 실시간 sleep 없이 속도 상한을 검사한다.

# KG: prom16-harness-loop-standard (independent stop / spend kill-switch)
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from engine.legion.spend import SpendLimits, SpendMeter, instrument_agent_client


class _Clock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


def test_no_limits_never_fires():
    """반대 방향: 상한 미지정 = 현행 동작 (아무리 써도 kill 없음)."""
    m = SpendMeter()
    for _ in range(1000):
        m.record(tokens=10_000)
    assert m.exceeded() is None
    assert m.calls == 1000 and m.tokens == 10_000_000


def test_cumulative_call_ceiling_fires():
    m = SpendMeter(SpendLimits(max_llm_calls=3))
    m.record()
    m.record()
    assert m.exceeded() is None
    m.record()
    assert "llm_calls 3 >= max_llm_calls 3" in (m.exceeded() or "")


def test_cumulative_token_ceiling_fires():
    m = SpendMeter(SpendLimits(max_total_tokens=100))
    m.record(tokens=60)
    assert m.exceeded() is None
    m.record(tokens=41)
    assert "max_total_tokens" in (m.exceeded() or "")


def test_velocity_ceiling_fires_then_recovers_as_window_slides():
    """속도 상한은 60초 슬라이딩 윈도우 — 시간이 지나면 다시 통과 (누적 상한과 다른 축)."""
    clock = _Clock()
    m = SpendMeter(SpendLimits(max_calls_per_minute=3), now=clock)
    for _ in range(3):
        m.record()
    assert "calls/min" in (m.exceeded() or "")
    clock.t = 61.0  # 윈도우 밖으로
    assert m.exceeded() is None
    assert m.calls == 3  # 누적은 그대로 (속도만 회복)


def test_token_velocity_ceiling_fires():
    clock = _Clock()
    m = SpendMeter(SpendLimits(max_tokens_per_minute=500), now=clock)
    m.record(tokens=300)
    assert m.exceeded() is None
    m.record(tokens=250)
    assert "tokens/min" in (m.exceeded() or "")


def test_cumulative_ceiling_survives_window_slide():
    """누적 상한은 시간이 지나도 안 풀린다 (속도 상한과 헷갈리면 안 됨)."""
    clock = _Clock()
    m = SpendMeter(SpendLimits(max_total_tokens=100), now=clock)
    m.record(tokens=150)
    clock.t = 10_000.0
    assert "max_total_tokens" in (m.exceeded() or "")


def test_instrumented_client_counts_calls_and_tokens():
    class _Client:
        def complete(self, **_kw):
            return SimpleNamespace(input_tokens=7, output_tokens=3, text="hi")

    m = SpendMeter(SpendLimits(max_total_tokens=15))
    c = instrument_agent_client(_Client(), m)
    assert c.complete(system="s", user="u", model="m").text == "hi"  # 반환값 그대로 통과
    assert m.calls == 1 and m.tokens == 10
    assert m.exceeded() is None
    c.complete(system="s", user="u", model="m")
    assert m.tokens == 20 and "max_total_tokens" in (m.exceeded() or "")


def test_instrumented_client_counts_failed_calls_and_reraises():
    """실패한 호출도 지출 — 재시도 폭주가 상한에 닿아야 한다. 예외는 그대로 전파."""

    class _Client:
        def complete(self, **_kw):
            raise ConnectionError("backend down")

    m = SpendMeter(SpendLimits(max_llm_calls=2))
    c = instrument_agent_client(_Client(), m)
    for _ in range(2):
        with pytest.raises(ConnectionError):
            c.complete(system="s", user="u", model="m")
    assert m.calls == 2 and "max_llm_calls" in (m.exceeded() or "")


def test_instrument_is_idempotent():
    """두 번 감싸도 한 번만 센다 (이중 계측으로 상한이 절반이 되지 않게)."""

    class _Client:
        def complete(self, **_kw):
            return SimpleNamespace(input_tokens=1, output_tokens=1)

    m = SpendMeter()
    c = instrument_agent_client(_Client(), m)
    instrument_agent_client(c, m)
    c.complete(system="s", user="u", model="m")
    assert m.calls == 1


def test_missing_usage_still_counts_calls():
    """usage 를 안 주는 백엔드에서도 호출 수 상한은 유효해야 한다 (토큰=0 fallback)."""

    class _Client:
        def complete(self, **_kw):
            return SimpleNamespace(text="no usage")

    m = SpendMeter(SpendLimits(max_llm_calls=1))
    c = instrument_agent_client(_Client(), m)
    c.complete(system="s", user="u", model="m")
    assert m.tokens == 0 and "max_llm_calls" in (m.exceeded() or "")


def test_probe_is_the_bound_predicate():
    m = SpendMeter(SpendLimits(max_llm_calls=1))
    probe = m.probe()
    assert probe() is None
    m.record()
    assert probe() is not None


def test_any_set_reflects_configured_axes():
    assert not SpendLimits().any_set
    assert SpendLimits(max_llm_calls=1).any_set
    assert SpendLimits(max_tokens_per_minute=1.0).any_set
