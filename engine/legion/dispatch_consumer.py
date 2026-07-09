"""Post-run dispatch consumer — DispatchDecision의 최초 소비자 (폐루프 개시).

2026-07-09 딥패스가 코드로 증명한 사실: 발화된 DispatchDecision의 종착은 아무도 읽지
않는 in-memory 리스트(legion.py sink.extend)와 아무도 되-쿼리하지 않는 :DispatchEvent
노드뿐이었다 — `commander_by_name` 리졸버는 테스트만 호출했고, MAX_DISPATCH_DEPTH=3인데
depth+1 재귀 호출 코드가 없었으며, record_outcome 프로덕션 호출부는 0이었다. 이 모듈이
그 셋을 한꺼번에 갚는다: 리졸버의 최초 프로덕션 호출, depth의 최초 실전파,
record_outcome의 최초 배선.

경계 (ADR legion-runtime-shape-review-2026-06-20 §G5-C5 — oracle이 라이브로 고정):
  * post-run ONLY — legion.run 완료 후 진입점(CLI/MCP)이 명시 opt-in으로 호출.
    Legion.run 내부에 소비를 심지 않는다(G5-C1 in-run executor 유일성 + stage 간
    oracle gate 의미론 보존).
  * allowlist ONLY — 실행 가능 엣지는 EXECUTABLE_EDGES 뿐(v1: occam→occam
    self-supersede janitor). 그 외 결정은 실행 없이 provenance-only skip.
    무음 확장 금지: 이 집합을 넓히려면 ADR G5-C5 개정 + dispatch-identity oracle
    개정이 함께 필요하다.
  * depth-capped — 재실행이 낳은 새 결정은 depth+1로 decide_dispatch에 전파되어
    MAX_DISPATCH_DEPTH에서 기계 종결(MaxDispatchDepthExceeded), 별도로
    max_executions 총예산이 이중 유계를 만든다.
  * σ게이트 상속 — 소비자의 유일한 write 경로는 stage.run(=OccamEngine.run →
    apply_supersessions(should_apply=is_confident_supersede)). deferred/불확실셋을
    읽는 코드 경로 자체가 없고, ctx의 apply 값을 절대 승격하지 않는다.
  * 침묵 삼킴 금지 — 모든 처분(executed/skipped/depth_capped/failed)이
    DispatchConsumeReport와 KG provenance(SET-only)에 실명 기록된다. legion.py의
    blanket-except 침묵 패턴을 복제하지 않는다.

# KG: LakatosTree_BhgmanDispatchLoop_20260710/dispatch_consumer_keystone
# KG: adr-legion-runtime-shape-review-2026-06-20 (G5-C5)
# KG: 7cmd-measurement-driven-conditional-dispatch-2026-05-30
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from engine.legion.legion_models import CommanderStage
from engine.legion.measurement import (
    COMMANDER_REGISTRY,
    DispatchDecision,
    MaxDispatchDepthExceeded,
    commander_by_name,
)

# v1 allowlist — occam self-supersede janitor 단일 엣지. 확장 = ADR G5-C5 개정 + oracle
# 개정 동반 (무음 확장은 test_dispatch_identity 가 ADR 라이브 리드로 차단).
EXECUTABLE_EDGES: frozenset[tuple[str, str]] = frozenset({("occam", "occam")})

# 처분 상태 (report + KG provenance 공용 어휘)
EXECUTED = "executed"
SKIPPED_EDGE = "skipped_edge_not_allowlisted"
SKIPPED_UNKNOWN_TARGET = "skipped_unknown_target"
SKIPPED_NO_STAGE = "skipped_no_stage_registered"
SKIPPED_BUDGET = "skipped_budget_exhausted"
DEPTH_CAPPED = "depth_capped"
EXEC_FAILED = "exec_failed"

_CONSUMED_BY = "dispatch_consumer.v1"

# 기존 :DispatchEvent(legion.py _DISPATCH_EVENT_MERGE 와 동일 identity 키)에 소비 처분을
# SET-only 로 병합 — 신규 라벨/노드 0, DELETE 0 (kg_harness DestructiveWriteRule 통과 형태).
# 소비자가 낳은 child 결정(depth>0)은 같은 MERGE 가 이벤트 자체를 생성한다.
_DISPATCH_CONSUME_MERGE = (
    "MERGE (e:DispatchEvent {source_commander:$source_commander, "
    "target_commander:$target_commander, metric_name:$metric_name, epoch:$epoch, "
    "decided_at:$decided_at}) "
    "SET e.metric_value=$metric_value, e.threshold=$threshold, e.reason=$reason, "
    "e.depth=$depth, e.cycle_id=$cycle_id, e.hmac_signature=$hmac_signature, "
    "e.consumed_at=$consumed_at, e.consume_status=$consume_status, "
    "e.consumed_by=$consumed_by, e.consume_depth=$consume_depth, e.outcome=$outcome "
    "RETURN e.source_commander AS src"
)


@dataclass(frozen=True)
class ConsumedRecord:
    """한 결정의 처분 — decision 원본 + 상태 + 실측치 (실패도 실명 기록)."""

    decision: DispatchDecision
    status: str
    child_decision_count: int = 0
    outcome: int | None = None
    detail: str = ""


@dataclass(frozen=True)
class DispatchConsumeReport:
    """소비 패스 1회의 전체 처분 — 카운트는 소비자가 아니라 독자가 재도출한다."""

    executed: tuple[ConsumedRecord, ...] = ()
    skipped: tuple[ConsumedRecord, ...] = ()
    depth_capped: tuple[ConsumedRecord, ...] = ()
    failed: tuple[ConsumedRecord, ...] = ()

    @property
    def all_records(self) -> tuple[ConsumedRecord, ...]:
        return self.executed + self.skipped + self.depth_capped + self.failed


def _default_stage_registry() -> dict[str, CommanderStage]:
    from engine.legion.commanders import default_stages  # noqa: PLC0415 — 순환 회피(commanders→legion)

    return {s.name: s for s in default_stages()}


def _write_provenance(ctx: dict, record: ConsumedRecord, cycle_id: str | None) -> None:
    """처분을 :DispatchEvent 에 SET-only 병합 (write_cypher 부재 시 skip — legion.py 와
    동형의 best-effort provenance, 단 실행 자체의 실패는 report 에 이미 실명이다)."""
    wc = ctx.get("write_cypher")
    if wc is None:
        return
    params = record.decision.to_kg_event(cycle_id=cycle_id)
    params.update(
        consumed_at=datetime.now(timezone.utc).isoformat(),
        consume_status=record.status,
        consumed_by=_CONSUMED_BY,
        consume_depth=record.decision.depth,
        outcome=record.outcome,
    )
    try:
        wc(_DISPATCH_CONSUME_MERGE, params)
    except Exception:  # noqa: BLE001 — provenance 는 best-effort; 처분은 report 가 정본
        pass


def _judge_outcome(decision: DispatchDecision, children: list[DispatchDecision]) -> int:
    """dispatch 효능의 최소 정의: 실행 후 재측정에서 같은 metric 이 재발화하지 않으면 1.

    (재발화 = 발화 조건이 해소되지 않음 = 이번 dispatch 는 조건을 못 닫음 → 0.)"""
    refired = any(c.metric_name == decision.metric_name for c in children)
    return 0 if refired else 1


def consume_dispatch(
    decisions: tuple[DispatchDecision, ...] | list[DispatchDecision],
    ctx: dict,
    *,
    stages: dict[str, CommanderStage] | None = None,
    instrument_log: Any | None = None,
    max_executions: int = 8,
) -> DispatchConsumeReport:
    """legion.run 이 수집한 DispatchDecision 을 post-run 소비한다 (G5-C5 경로).

    ctx 는 진입점이 run 에 준 초기 context 그대로 — occam janitor 는 run_cypher 만
    필수로 요구하며, write 는 write_cypher + apply(ctx 값 그대로, 승격 없음)에만 발생.
    반환된 report 의 모든 카운트는 KG provenance 와 대조 가능하다(fake-green 차단).
    """
    registry = stages if stages is not None else _default_stage_registry()
    cycle_id = ctx.get("cycle_id")
    apply_mode = bool(ctx.get("apply", False))

    executed: list[ConsumedRecord] = []
    skipped: list[ConsumedRecord] = []
    depth_capped: list[ConsumedRecord] = []
    failed: list[ConsumedRecord] = []
    budget = max_executions

    frontier: deque[DispatchDecision] = deque(decisions)
    while frontier:
        d = frontier.popleft()

        # 타깃 유효성 — 리졸버의 최초 프로덕션 호출 (미지 타깃 = fail-closed skip).
        try:
            commander_by_name(d.target_commander)
        except KeyError:
            rec = ConsumedRecord(
                d, SKIPPED_UNKNOWN_TARGET, detail=f"unknown: {d.target_commander!r}"
            )
            skipped.append(rec)
            _write_provenance(ctx, rec, cycle_id)
            continue

        edge = (d.source_commander, d.target_commander)
        if edge not in EXECUTABLE_EDGES:
            rec = ConsumedRecord(d, SKIPPED_EDGE, detail=f"edge {edge} not in allowlist")
            skipped.append(rec)
            _write_provenance(ctx, rec, cycle_id)
            continue

        stage = registry.get(d.target_commander)
        if stage is None:
            rec = ConsumedRecord(d, SKIPPED_NO_STAGE, detail=f"no stage: {d.target_commander!r}")
            skipped.append(rec)
            _write_provenance(ctx, rec, cycle_id)
            continue

        if budget <= 0:
            rec = ConsumedRecord(d, SKIPPED_BUDGET, detail=f"max_executions={max_executions}")
            skipped.append(rec)
            _write_provenance(ctx, rec, cycle_id)
            continue

        # ── 실행 (janitor: occam 재실행 — write 는 σ게이트 상속 경로뿐) ────────────
        budget -= 1
        try:
            output = stage.run(dict(ctx))
        except Exception as e:  # noqa: BLE001 — 침묵 삼킴 금지: EXEC_FAILED 실명 기록
            rec = ConsumedRecord(d, EXEC_FAILED, outcome=0 if apply_mode else None, detail=repr(e))
            failed.append(rec)
            _write_provenance(ctx, rec, cycle_id)
            continue

        # 재측정 — 매 반복 fresh measurement(epoch-cache stale 방지), depth 는 d.depth+1
        # 로 전파 (MAX_DISPATCH_DEPTH 도달 시 기계 종결 = depth_capped).
        merged = {**ctx, **output}
        children: list[DispatchDecision] = []
        status = EXECUTED
        detail = ""
        measurement = stage.measure(merged) if stage.measure is not None else None
        if measurement is not None:
            try:
                children = measurement.decide_dispatch(cycle_id=cycle_id, depth=d.depth + 1)
            except MaxDispatchDepthExceeded as e:
                status = DEPTH_CAPPED
                detail = str(e)

        outcome: int | None = None
        if apply_mode and status in (EXECUTED, DEPTH_CAPPED):
            outcome = _judge_outcome(d, children)
            if measurement is not None and instrument_log is not None:
                measurement.set_instrument_log(instrument_log)
                measurement.record_outcome(
                    d,
                    outcome,
                    cycle_id=cycle_id,
                    dispatch_id=d.to_kg_event(cycle_id=cycle_id)["hmac_signature"],
                )

        rec = ConsumedRecord(
            d, status, child_decision_count=len(children), outcome=outcome, detail=detail
        )
        (depth_capped if status == DEPTH_CAPPED else executed).append(rec)
        _write_provenance(ctx, rec, cycle_id)

        # child 결정 중 allowlist 대상만 frontier 에 — 그 외는 provenance-only skip 으로
        # 다음 반복에서 처분된다 (전 결정 실명 원칙).
        frontier.extend(children)

    return DispatchConsumeReport(
        executed=tuple(executed),
        skipped=tuple(skipped),
        depth_capped=tuple(depth_capped),
        failed=tuple(failed),
    )


__all__ = [
    "COMMANDER_REGISTRY",
    "ConsumedRecord",
    "DispatchConsumeReport",
    "EXECUTABLE_EDGES",
    "consume_dispatch",
]
