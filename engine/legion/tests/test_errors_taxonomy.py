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


def test_repo_llm_http_error_5xx_is_transient():
    """repo 래퍼의 5xx(예: 122B OOM 500)는 일시장애 → transient. status 기반(urllib.HTTPError 규칙)."""
    from engine.agents.client import LLMHTTPError

    assert classify_error(LLMHTTPError("122B OOM 500", status=500)) is ErrorClass.TRANSIENT
    assert classify_error(LLMHTTPError("bad gateway", status=503)) is ErrorClass.TRANSIENT


def test_repo_llm_http_error_4xx_is_programming():
    """repo 래퍼의 4xx(401/404 등)는 요청·인증 버그 → programming. 무한 재시도 금지(이 분기의 핵심)."""
    from engine.agents.client import LLMHTTPError

    assert classify_error(LLMHTTPError("401 unauthorized", status=401)) is ErrorClass.PROGRAMMING
    assert classify_error(LLMHTTPError("404 no model", status=404)) is ErrorClass.PROGRAMMING


def test_repo_llm_http_error_missing_status_is_programming():
    """status 파싱 불가 시 보수적으로 programming — 조용한 무한 재시도보다 fail-fast."""
    from engine.agents.client import LLMHTTPError

    assert classify_error(LLMHTTPError("no status field")) is ErrorClass.PROGRAMMING


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
