"""타입付 오류 분류 (GAP-1) — transient 만 재시도, 그 외는 fail-fast.

양방향: 분류돼야 할 것이 transient 로 분류되고 / 아닌 것은 programming 으로 떨어져
재시도되지 않는다 (조용한 무한 재시도 금지).

# KG: prom16-harness-loop-standard (typed error taxonomy)
"""

from __future__ import annotations

import socket
import urllib.error

import pytest

from engine.legion.errors import (
    ErrorClass,
    RetryPolicy,
    classify_error,
    describe,
    is_transient,
    run_with_retry,
)


def _http_error(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError("http://x", code, "boom", {}, None)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "exc",
    [
        ConnectionError("refused"),
        ConnectionResetError("reset"),  # ConnectionError 하위
        TimeoutError("slow"),
        socket.gaierror("dns"),
        urllib.error.URLError("unreachable"),
        _http_error(500),
        _http_error(503),
    ],
)
def test_transient_family_is_retryable(exc):
    assert classify_error(exc) is ErrorClass.TRANSIENT
    assert is_transient(exc)


@pytest.mark.parametrize(
    "exc",
    [
        AttributeError("'NoneType' has no attribute 'x'"),  # 전형적 결정론 버그
        TypeError("bad arg"),
        KeyError("legion_run"),
        ValueError("nope"),
        RuntimeError("unclassified"),  # 분류 불가 → 보수적으로 programming
        _http_error(404),  # 4xx = 요청/설정 버그, 재시도해도 같은 답
        _http_error(401),
        FileNotFoundError("missing.json"),  # 네트워크 아닌 OSError 는 transient 아님
    ],
)
def test_programming_family_is_not_retryable(exc):
    assert classify_error(exc) is ErrorClass.PROGRAMMING
    assert not is_transient(exc)


def test_repo_llm_http_error_is_transient():
    """repo 자체 래퍼(vLLM non-2xx)는 transient 로 해석돼야 — 122B OOM 500 은 일시장애."""
    from engine.agents.client import LLMHTTPError

    assert classify_error(LLMHTTPError("122B OOM 500")) is ErrorClass.TRANSIENT


def test_retry_recovers_transient_within_budget():
    calls = {"n": 0}
    slept: list[float] = []

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise ConnectionError("flaky")
        return "ok"

    out = run_with_retry(flaky, policy=RetryPolicy(attempts=2, base_delay=0.5), sleep=slept.append)
    assert out == "ok"
    assert calls["n"] == 3
    assert slept == [0.5, 1.0]  # 지수 backoff


def test_retry_gives_up_after_bounded_attempts():
    """유한 재시도 — 무한 재시도 금지 (PROM16 §never an unbounded loop)."""
    calls = {"n": 0}

    def always_down():
        calls["n"] += 1
        raise ConnectionError("down")

    with pytest.raises(ConnectionError):
        run_with_retry(always_down, policy=RetryPolicy(attempts=2), sleep=lambda _s: None)
    assert calls["n"] == 3  # 최초 1 + 재시도 2, 그 이상은 없음


def test_programming_error_fails_fast_without_retry():
    """결정론 버그는 재시도해도 같은 답 — 1회만 시도하고 즉시 raise."""
    calls = {"n": 0}

    def bug():
        calls["n"] += 1
        raise AttributeError("deterministic bug")

    with pytest.raises(AttributeError):
        run_with_retry(bug, policy=RetryPolicy(attempts=5), sleep=lambda _s: None)
    assert calls["n"] == 1


def test_retry_policy_caps_backoff():
    p = RetryPolicy(attempts=10, base_delay=1.0, max_delay=4.0)
    assert [p.delay_for(i) for i in range(5)] == [1.0, 2.0, 4.0, 4.0, 4.0]


def test_describe_keeps_type_name_for_diagnosis():
    assert describe(ValueError("x")) == "ValueError: x"
