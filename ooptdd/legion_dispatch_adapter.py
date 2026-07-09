"""ooptdd-loop in_process target — dispatch 폐루프(G5-C5 소비자)를 REAL 엔진 체인으로
바인딩 (seed → legion run → 발화 → consume_dispatch → janitor 실행 → KG 처분 실측).

이 어댑터는 trace 를 위조하지 않는다: 모든 이벤트는 (1) 확신-dup 12그룹을 실제 seeding 한
LocalKgStore 위에서 (2) build_default_legion().run() 이 실제로 발화시킨 DispatchDecision 을
(3) consume_dispatch 가 실제로 소비/실행한 결과에서 재도출된다. 카운트는 KG 상태
(consumed_at 보유 :DispatchEvent)와 DispatchConsumeReport 에서만 나오며 손입력 숫자와
입력 echo 는 없다. 자기해소(trigger_cleared)는 두 번째 legion run 의 재발화 부재로 실측.

Longinus binding: 각 must_emit 리터럴은 이 파일의 emit 심볼 본문에 verbatim 상수로 산다 —
engine/legion/ 은 emit-free/리터럴-free 로 유지된다 (하드코어: 이벤트 리터럴은 어댑터에만).

# KG: finding-ooptdd-bhgman-legion-dispatch-adapter-20260710
# KG: LakatosTree_BhgmanDispatchLoop_20260710/dispatch_consumer_keystone
"""

from __future__ import annotations

from engine.kg_local.runner import make_local_runner
from engine.kg_local.store import LocalKgStore
from engine.legion.commanders import build_default_legion
from engine.legion.dispatch_consumer import DispatchConsumeReport, consume_dispatch

_KG_ANCHOR = "finding-ooptdd-bhgman-legion-dispatch-adapter-20260710"
_CYCLE_ID = "legion-dispatch-ooptdd"
N_CONFIDENT = 12  # dead_node_count>10 발화 임계 초과 (판별력: 11개면 발화, 10개면 침묵)


def _ev(cid: str, event: str, **attrs) -> dict:
    """Shape one trace event the way the memory backend keys + counts it (cid + event)."""
    return {
        "cid": cid,
        "correlation_id": cid,
        "cycle_id": cid,
        "service": "bhgman.legion.dispatch",
        "event": event,
        **attrs,
    }


def seed_confident_dups(store: LocalKgStore, n: int = N_CONFIDENT) -> None:
    """abs/rel lineage 쌍(정규화 동일 경로+동일 sha=byte-동일) n그룹 — occam mode-1 이
    그룹핑하고 σ게이트가 확신 처리하는 케이스 → superseded_candidates == n."""
    for i in range(n):
        for prefix in ("/Users/old/bhgman_tool/", "bhgman_tool/"):
            store.nodes.append(
                {
                    "labels": ["SourceCodeNode"],
                    "props": {
                        "name": f"ldc_{i}",
                        "sourcePath": f"{prefix}pkg/ldc_{i}.py",
                        "sha256": f"{i:064x}",
                        "lineCount": 10 + i,
                    },
                }
            )


def _run_real_loop(
    n_groups: int = N_CONFIDENT, apply: bool = True
) -> tuple[LocalKgStore, list, DispatchConsumeReport, list]:
    """REAL 체인 1회: seed → legion run(발화) → consume(실행) → 재run(재발화 실측)."""
    store = LocalKgStore()
    seed_confident_dups(store, n_groups)
    runner = make_local_runner(store, autosave=False)
    ctx = {
        "run_cypher": runner,
        "write_cypher": runner,
        "apply": apply,
        "cycle_id": _CYCLE_ID,
    }
    run = build_default_legion().run(dict(ctx))
    fired = [d for d in run.dispatch_decisions if d.metric_name == "dead_node_count"]
    report = consume_dispatch(run.dispatch_decisions, ctx)
    run2 = build_default_legion().run(dict(ctx))
    refired = [d for d in run2.dispatch_decisions if d.metric_name == "dead_node_count"]
    return store, fired, report, refired


def emit_fired_phase(backend, cid: str, fired: list) -> int:
    """Ship one 'dispatch_decision_fired' per REAL dead_node_count 발화 — 카운트는
    legion run 이 수집한 결정 리스트에서 재도출 (seeding 10개면 발화 0 = RED)."""
    for d in fired:
        backend.ship(
            [_ev(cid, "dispatch_decision_fired", metric=d.metric_name, value=d.metric_value)]
        )
    return len(fired)


def emit_consumed_phase(backend, cid: str, store: LocalKgStore) -> int:
    """Ship one 'dispatch_decision_consumed' per consumed_at 보유 :DispatchEvent —
    카운트는 report echo 가 아니라 KG 상태에서 재도출 (소비자를 no-op 으로 되돌리면
    consumed_at SET 이 사라져 0 = RED)."""
    consumed = [
        e["props"] for e in store.find_nodes("DispatchEvent") if e["props"].get("consumed_at")
    ]
    for e in consumed:
        backend.ship(
            [
                _ev(
                    cid,
                    "dispatch_decision_consumed",
                    status=e.get("consume_status"),
                    depth=e.get("consume_depth"),
                )
            ]
        )
    return len(consumed)


def emit_executed_phase(backend, cid: str, report: DispatchConsumeReport) -> int:
    """Ship one 'dispatch_janitor_executed' per EXECUTED 처분 — allowlist 엣지의 실행이
    실제로 일어났음을 report 처분에서 재도출 (KG 대조는 consumed 축이 담당)."""
    for r in report.executed:
        backend.ship(
            [
                _ev(
                    cid,
                    "dispatch_janitor_executed",
                    edge=f"{r.decision.source_commander}->{r.decision.target_commander}",
                    outcome=r.outcome,
                )
            ]
        )
    return len(report.executed)


def emit_self_heal_phase(backend, cid: str, fired: list, report, refired: list) -> int:
    """Ship 'dispatch_trigger_cleared' iff 발화→실행→재발화0 의 전체 사슬이 실측 성립 —
    janitor 가 자기 발화 조건을 해소했다는 폐루프 기능 증명 (apply=False 면 재발화가
    남아 이 이벤트는 0 = RED)."""
    cleared = 1 if (fired and report.executed and not refired) else 0
    if cleared:
        backend.ship([_ev(cid, "dispatch_trigger_cleared", refired=len(refired))])
    return cleared


def run_legion_dispatch_pipeline(
    backend, cid: str, *, n_groups: int = N_CONFIDENT, apply: bool = True
) -> dict:
    """Loop entry point (called as ``run_legion_dispatch_pipeline(backend, cid)``).
    'dispatch_consume_started'/'dispatch_consume_completed' 리터럴은 이 심볼 본문에 산다."""
    store, fired, report, refired = _run_real_loop(n_groups, apply=apply)

    backend.ship([_ev(cid, "dispatch_consume_started", n_groups=n_groups)])
    n_fired = emit_fired_phase(backend, cid, fired)
    n_consumed = emit_consumed_phase(backend, cid, store)
    n_executed = emit_executed_phase(backend, cid, report)
    n_cleared = emit_self_heal_phase(backend, cid, fired, report, refired)
    backend.ship(
        [
            _ev(
                cid,
                "dispatch_consume_completed",
                dry_run=not apply,
                fired=n_fired,
                consumed=n_consumed,
                executed=n_executed,
                cleared=n_cleared,
            )
        ]
    )
    return {
        "fired": n_fired,
        "consumed": n_consumed,
        "executed": n_executed,
        "cleared": n_cleared,
    }
