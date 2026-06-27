"""Legion run 의 durable-ready 래퍼 — fallback-only (새 의존성 0).

오케스트레이션 상태를 내구성 실행 엔진(DBOS Transact, durable-execution 분류 c — Postgres
단일 의존)에 얹어 크래시/재시작 시 비싼 LLM/WebFetch 재지불을 막는 *seam*. **DBOS 미설치 시
in-process 로 graceful degrade** (HAS_DBOS=False → legion.run 그대로, 현행 동작 보존).

원칙(durable-engines-deepdive §6 안티패턴 회피): stage I/O dict 는 write_cypher 등 *비직렬*
객체를 담으므로 그대로 DBOS step 으로 체크포인트할 수 없다. 따라서 진짜 per-stage durability 는
"오케스트레이션 상태(stage 이름·cycle_id·KG-ref)만 durable, 콘텐츠는 KG 가 SoT" 분리(stage 가
raw dict 대신 KG-ref 를 주고받는 리팩터)가 선행조건이다. 그 전까지 durable_run 은 **seam**:
호출부가 지금부터 cycle_id 를 멱등 핸들로 넘기게 해두고, 환경에 DBOS+Postgres 가 생기면
_run_durable_dbos 한 곳만 활성화하면 된다.

지금 당장 실동작하는 durability 보강은 동반 모듈로 제공한다:
  - stuck_detector.StuckDetector — 무진전 정체 halt (깊이캡과 직교)
  - realize_idempotency.RealizationLedger — at-least-once 실현 멱등 (이중 실현 차단)

# KG: durable-legion-fallback-2026-06-27 (durable-engines-deepdive §2 분류c=DBOS Transact)
"""

from __future__ import annotations

from engine.legion.legion import GateFn, Legion
from engine.legion.legion_models import LegionRun

try:  # DBOS 는 선택 의존성 — 없으면 in-process fallback.
    import dbos as _dbos  # noqa: F401

    HAS_DBOS = True
except Exception:  # noqa: BLE001 — 미설치/임포트 실패 전부 fallback 으로
    HAS_DBOS = False


def durable_run(
    legion: Legion,
    context: dict | None = None,
    gate: GateFn | None = None,
    cycle_id: str | None = None,
) -> LegionRun:
    """legion.run 을 durable 하게(가능하면) 실행, 아니면 in-process fallback.

    Args:
        legion: 실행할 Legion (stage 등록 완료).
        context: 초기 KG context dict.
        gate: 나생문 oracle gate (주입식).
        cycle_id: 멱등 실행 핸들 (DBOS SetWorkflowID 후보). None 이면 항상 in-process.

    Returns:
        LegionRun — fallback 경로는 legion.run 과 **동일 결과**.
    """
    if HAS_DBOS and cycle_id is not None:
        return _run_durable_dbos(legion, context, gate, cycle_id)
    return legion.run(context, gate)


def _run_durable_dbos(
    legion: Legion, context: dict | None, gate: GateFn | None, cycle_id: str
) -> LegionRun:  # pragma: no cover — DBOS+Postgres 환경에서만 활성 (현재 미설치 = 미검증, 정직)
    """DBOS 경로. **활성 전 선행조건**: stage I/O 의 KG-ref 직렬화(위 docstring).

    현재는 whole-run 을 그대로 실행하되 cycle_id 를 SetWorkflowID 멱등 핸들로 노출한다.
    per-stage step 메모이제이션(크래시 시 완료 stage 재지불 0)은 직렬화 리팩터 후 이 함수만
    교체하면 된다 — 호출부는 durable_run 시그니처 그대로.
    """
    from dbos import DBOS, SetWorkflowID  # 지연 import (모듈 로드시 DBOS 강제 안 함)

    @DBOS.workflow()
    def _legion_cycle() -> LegionRun:
        # NOTE: 비직렬 콘텐츠는 closure 로 캡처 (cross-restart replay 아닌 in-process retry/
        # 멱등 수준). 진짜 replay 는 KG-ref 직렬화 후 per-stage @DBOS.step 로 격상.
        return legion.run(context, gate)

    with SetWorkflowID(cycle_id):
        return _legion_cycle()


__all__ = ["HAS_DBOS", "durable_run"]
