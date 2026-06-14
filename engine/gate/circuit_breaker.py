"""APT v27 A7 — Redis-backed 3-state circuit breaker.

Absorbed from SYMPOSIUM/THEORY/APT/gate_endpoint_prototype/circuit_breaker.py
(Wave 7 P3-H, 2026-05-14).

State FSM:
    CLOSED → (3 consecutive fails) → OPEN
    OPEN → (timeout elapsed) → HALF_OPEN
    HALF_OPEN → (next success) → CLOSED  /  (any fail) → OPEN

Redis key layout:
    circuit:<gate_name>:state          → "CLOSED"|"OPEN"|"HALF_OPEN"
    circuit:<gate_name>:fail_count     → integer
    circuit:<gate_name>:opened_at      → ISO timestamp (OPEN 진입 시간)

KG ref: rfc-apt-v27-A7-gate-hook-fail-closed-4-layer-2026-04-30
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol

import redis


OPEN_DURATION_S = 30.0  # OPEN 상태 유지 시간 (HALF_OPEN 전환 전)
FAIL_THRESHOLD = 3  # consecutive fails to OPEN


class State(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


@dataclass(frozen=True, slots=True)
class CircuitDecision:
    state: State
    allow_request: bool
    reason: str


class RedisLike(Protocol):
    def get(self, key: str): ...
    def set(self, key: str, value, ex: int | None = None): ...
    def incr(self, key: str): ...
    def delete(self, *keys: str): ...


class CircuitBreaker:
    def __init__(self, r: RedisLike, gate_name: str) -> None:
        self._r = r
        self._gate = gate_name

    def _key(self, suffix: str) -> str:
        return f"circuit:{self._gate}:{suffix}"

    # ─── decision ──────────────────────────────────────────────────────

    def check(self) -> CircuitDecision:
        state_raw = self._r.get(self._key("state"))
        if state_raw is None:
            return CircuitDecision(State.CLOSED, True, "fresh circuit, allow")

        state = State(_decode(state_raw))

        if state == State.CLOSED:
            return CircuitDecision(State.CLOSED, True, "circuit closed")

        if state == State.OPEN:
            opened_at_raw = self._r.get(self._key("opened_at"))
            if opened_at_raw is None:
                # corrupt — treat as CLOSED + reset
                self._reset()
                return CircuitDecision(State.CLOSED, True, "corrupt OPEN reset")
            opened_at = float(_decode(opened_at_raw))
            if time.time() - opened_at >= OPEN_DURATION_S:
                # promote OPEN → HALF_OPEN
                self._r.set(self._key("state"), State.HALF_OPEN.value)
                return CircuitDecision(
                    State.HALF_OPEN, True, "OPEN duration elapsed, trial request"
                )
            return CircuitDecision(
                State.OPEN,
                False,
                f"circuit OPEN (opened {time.time() - opened_at:.1f}s ago)",
            )

        # HALF_OPEN
        return CircuitDecision(State.HALF_OPEN, True, "trial request in HALF_OPEN")

    # ─── transition ────────────────────────────────────────────────────

    def record_success(self) -> None:
        self._r.set(self._key("state"), State.CLOSED.value)
        self._r.delete(self._key("fail_count"), self._key("opened_at"))

    def record_failure(self) -> State:
        count = self._r.incr(self._key("fail_count"))
        if count >= FAIL_THRESHOLD:
            # wall clock (time.time), NOT time.monotonic: monotonic resets at boot, so a
            # persisted monotonic opened_at left `time.x() - opened_at` negative after a
            # restart → circuit stuck OPEN forever (W3-G). TTL backstops a leaked OPEN key.
            ttl = int(OPEN_DURATION_S * 4)
            self._r.set(self._key("state"), State.OPEN.value, ex=ttl)
            self._r.set(self._key("opened_at"), str(time.time()), ex=ttl)
            return State.OPEN
        return State.CLOSED

    def _reset(self) -> None:
        self._r.delete(
            self._key("state"),
            self._key("fail_count"),
            self._key("opened_at"),
        )


def _decode(v) -> str:
    if isinstance(v, bytes):
        return v.decode()
    return str(v)


def build_redis_client() -> redis.Redis:
    """Composition Root: Redis 연결 + ping 검증. REDIS_PASSWORD env optional (k8s pod AUTH)."""
    import os

    kwargs: dict[str, Any] = dict(
        host=os.environ.get("REDIS_HOST", "localhost"),
        port=int(os.environ.get("REDIS_PORT", 6379)),
        db=int(os.environ.get("REDIS_DB", 0)),
    )
    pw = os.environ.get("REDIS_PASSWORD")
    if pw:
        kwargs["password"] = pw
    client = redis.Redis(**kwargs)
    if not client.ping():
        raise SystemExit("[BOOT FAIL] Redis unreachable. Gate refuses to start.")
    return client
