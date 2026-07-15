"""Legion 루프의 타입付 오류 분류 — transient 는 재시도, 그 외는 fail-fast/격리.

daemon/legion 루프는 `except Exception` 으로 *전부* 격리했다. 그 결과 결정론 버그
(AttributeError/TypeError 류)가 매 tick 조용히 같은 자리에서 죽어도 봇은 영원히 계속
돈다 — 무한 루프 + 0 진전 + 진단 불가. PROM16 하네스/루프 표준 §"타입付 오류 분류":
transient(네트워크/타임아웃/5xx)만 유한 재시도+backoff, 나머지는 programming_error 로
*타입付 기록* 후 해당 work item 격리 (재시도 금지), K회 연속이면 루프 정지.

분류 경계 (정직):
  transient  = ConnectionError / TimeoutError / socket.gaierror / urllib URLError /
               HTTPError 5xx / repo 의 transient 래퍼(LLMHTTPError, TransientGateError,
               neo4j ServiceUnavailable·TransientError·SessionExpired).
  programming = 그 외 전부. HTTPError 4xx 포함 (400/401/404 는 재시도해도 같은 답 =
               설정·코드 버그). 네트워크가 아닌 OSError(FileNotFoundError, PermissionError
               등)도 포함 — "OSError 면 무조건 transient" 는 재시도해봐야 소용없는
               디스크·경로 버그를 무한 재시도로 감추므로 채택하지 않는다.

repo 래퍼는 *지연 해석* 한다 — neo4j/fastapi 는 선택 extra 라 import 가능성이 환경마다
다르다. import 실패한 타입은 그냥 목록에서 빠질 뿐 분류는 계속 동작한다 (fail-open 이
아니라 degrade: 못 찾은 타입은 보수적으로 programming 으로 떨어져 재시도되지 않는다).

# KG: prom16-harness-loop-standard (typed error taxonomy),
#     bhgman-bot-daemon-2026-06-16 (except Exception 격리 루프의 수정점)
"""

from __future__ import annotations

import importlib
import socket
import time
import urllib.error
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
from typing import TypeVar

T = TypeVar("T")


class ErrorClass(str, Enum):
    """오류의 처리 정책 분류. str 상속 = TickResult/JSON 직렬화에 그대로 실린다."""

    TRANSIENT = "transient"  # 유한 재시도 + backoff
    PROGRAMMING = "programming_error"  # fail-fast / 격리, 재시도 금지


# 항상 존재하는 stdlib transient. ConnectionError/TimeoutError/gaierror 는 OSError 하위,
# URLError 도 3.x 에선 OSError 하위 — 그래도 OSError 전체를 넣지 않는 이유는 docstring 참조.
_STDLIB_TRANSIENT: tuple[type[BaseException], ...] = (
    ConnectionError,
    TimeoutError,
    socket.gaierror,
    urllib.error.URLError,
)

# (module, attr) — 선택 의존성이라 import 가능성이 환경마다 다르다. 지연 해석 + 캐시.
# 주의: LLMHTTPError 는 여기 없다. status 코드에 따라 5xx=transient / 4xx=programming 으로
# 갈리므로 무조건-transient 목록에 넣으면 401/404 를 영원히 재시도하게 된다(urllib.HTTPError 와
# 의미가 어긋남). classify_error 가 LLMHTTPError.status 를 보고 별도 분기한다.
_REPO_TRANSIENT_REFS: tuple[tuple[str, str], ...] = (
    ("engine.gate.gate_endpoint", "TransientGateError"),  # APT gate retry 대상
    ("neo4j.exceptions", "ServiceUnavailable"),
    ("neo4j.exceptions", "TransientError"),
    ("neo4j.exceptions", "SessionExpired"),
)


@lru_cache(maxsize=1)
def _llm_http_error_type() -> type[BaseException] | None:
    """engine.agents.client.LLMHTTPError (import 가능하면). status 기반 분류 전용."""
    try:
        from engine.agents.client import LLMHTTPError
    except Exception:  # noqa: BLE001 — 선택 extra 미설치/부작용 import 실패
        return None
    return LLMHTTPError


@lru_cache(maxsize=1)
def repo_transient_types() -> tuple[type[BaseException], ...]:
    """이 환경에서 실제로 import 되는 repo/드라이버 transient 래퍼들 (캐시)."""
    found: list[type[BaseException]] = []
    for mod_name, attr in _REPO_TRANSIENT_REFS:
        try:
            mod = importlib.import_module(mod_name)
        except Exception:  # noqa: BLE001 — 선택 extra 미설치/부작용 import 실패 → 목록에서 제외
            continue
        t = getattr(mod, attr, None)
        if isinstance(t, type) and issubclass(t, BaseException):
            found.append(t)
    return tuple(found)


def classify_error(exc: BaseException) -> ErrorClass:
    """예외 → 처리 정책. 모르는 예외는 PROGRAMMING (보수적: 조용히 재시도하지 않는다)."""
    if isinstance(exc, urllib.error.HTTPError):
        # HTTPError ⊂ URLError 이므로 반드시 먼저 본다. 5xx=서버측 일시장애 / 4xx=요청 버그.
        return ErrorClass.TRANSIENT if int(exc.code) >= 500 else ErrorClass.PROGRAMMING
    llm_http = _llm_http_error_type()
    if llm_http is not None and isinstance(exc, llm_http):
        # openai-compat 백엔드 non-2xx. urllib.HTTPError 와 같은 규칙으로 status 를 본다:
        # 5xx=일시장애(재시도 유효) / 4xx=요청·인증 버그(재시도 무의미). status 파싱 불가면
        # 보수적으로 programming(조용한 무한 재시도보다 fail-fast 가 안전).
        status = getattr(exc, "status", None)
        if isinstance(status, int):
            return ErrorClass.TRANSIENT if status >= 500 else ErrorClass.PROGRAMMING
        return ErrorClass.PROGRAMMING
    if isinstance(exc, _STDLIB_TRANSIENT) or isinstance(exc, repo_transient_types()):
        return ErrorClass.TRANSIENT
    return ErrorClass.PROGRAMMING


def is_transient(exc: BaseException) -> bool:
    return classify_error(exc) is ErrorClass.TRANSIENT


@dataclass(frozen=True)
class RetryPolicy:
    """유한 재시도 + 지수 backoff. attempts=0 이면 재시도 없음 (첫 실패가 곧 종료)."""

    attempts: int = 2
    base_delay: float = 0.5
    max_delay: float = 30.0

    def delay_for(self, attempt: int) -> float:
        """attempt(0-based) 번째 재시도 전 대기 초. base*2^attempt, max_delay 로 캡."""
        return min(self.base_delay * (2.0**attempt), self.max_delay)


def run_with_retry(
    fn: Callable[[], T],
    *,
    policy: RetryPolicy,
    sleep: Callable[[float], None] = time.sleep,
    on_retry: Callable[[int, BaseException, float], None] | None = None,
) -> T:
    """fn() 을 실행하되 transient 실패만 policy.attempts 회까지 backoff 재시도.

    programming 오류는 첫 실패에 즉시 raise (fail-fast — 재시도해도 같은 답). transient 도
    재시도 소진 시 raise 한다 — 호출자(daemon)가 타입付 결과로 기록한다.
    """
    attempt = 0
    while True:
        try:
            return fn()
        except Exception as e:
            if not is_transient(e) or attempt >= policy.attempts:
                raise
            delay = policy.delay_for(attempt)
            if on_retry is not None:
                on_retry(attempt + 1, e, delay)
            sleep(delay)
            attempt += 1


class StopReason(str, Enum):
    """루프의 *타입付* 종료 상태. bare exception 을 terminal 로 쓰지 않는다 (PROM16)."""

    MAX_TICKS = "max_ticks"  # 설정된 tick 상한 도달 (정상)
    SIGNAL = "signal"  # SIGTERM/SIGINT graceful stop
    ERROR_STORM = "error_storm"  # K회 연속 programming_error → 정지
    SPEND_KILL = "spend_kill"  # 누적 예산/속도 상한 초과 → 정지
    ALL_QUARANTINED = "all_quarantined"  # rotation 큐의 모든 topic 이 격리됨 → 할 일 없음


def describe(exc: BaseException) -> str:
    """로그/TickResult.detail 용 짧은 표현 — 타입名을 반드시 남긴다 (진단 가능성)."""
    return f"{type(exc).__name__}: {exc}"


__all__ = [
    "ErrorClass",
    "RetryPolicy",
    "StopReason",
    "classify_error",
    "describe",
    "is_transient",
    "repo_transient_types",
    "run_with_retry",
]
