"""하데스 실현(materialize) 멱등 — at-least-once 안전.

MCP 도구 호출·durable step·dispatch 재출격은 모두 at-least-once 라 같은 실현이 두 번 일어날
수 있다(이중 파일 쓰기 / 이중 KG MERGE 의 *call* 재지불 — MERGE 는 write 중복은 막아도 호출
부수효과 재실행은 못 막는다). 콘텐츠-주소 멱등키로 '이미 실현됨' 을 단락한다.

key = sha256(cycle_id | artifact_sha256 | target_path)  (deepdive: Temporal/Golem idempotency key)

영속은 두 갈래(둘 다 이 키를 씀):
  - KG :RealizedVerdict {idempotencyKey} MERGE 후 존재하면 skip
  - DBOS step 의 결과 메모이제이션 키

# KG: hades-realize-idempotency-2026-06-27 (deepdive §6 'at-least-once≠exactly-once' 대응)
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

_SEP = "\x1f"  # unit separator — target_path 안의 문자와 충돌 회피


def realize_idempotency_key(cycle_id: str, artifact_sha256: str, target_path: str) -> str:
    """실현 1건의 멱등키. 같은 (cycle, 산출물 내용, 대상 경로) → 같은 키."""
    raw = f"{cycle_id}{_SEP}{artifact_sha256}{_SEP}{target_path}".encode()
    return "realize-" + hashlib.sha256(raw).hexdigest()[:32]


@dataclass
class RealizationLedger:
    """실현 멱등 원장(in-memory). 영속은 KG :RealizedVerdict 또는 DBOS step 으로 주입 가능."""

    _seen: set[str] = field(default_factory=set, repr=False)

    def seen(self, key: str) -> bool:
        return key in self._seen

    def mark(self, key: str) -> None:
        self._seen.add(key)

    def realize_once(self, key: str, do_realize: Callable[[], Any]) -> tuple[bool, Any]:
        """이미 실현된 키면 (False, None) — do_realize 미호출. 처음이면 실행 후 (True, result).

        at-least-once 로 같은 실현이 두 번 와도 do_realize 는 정확히 1회만 호출된다.
        """
        if key in self._seen:
            return False, None
        result = do_realize()
        self._seen.add(key)
        return True, result


__all__ = ["RealizationLedger", "realize_idempotency_key"]
