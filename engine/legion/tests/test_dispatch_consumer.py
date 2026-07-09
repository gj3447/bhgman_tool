"""dispatch_consumer 가드 배터리 — 폐루프 개시의 revert-proof 이중가드.

RED 실측(2026-07-10, judge_dispatch_consumed.py): 발화는 사는데(fired=1) 소비가 없다
(consumed_at 보유 :DispatchEvent 0, 모듈 ImportError). 이 파일은 GREEN 측 행동 pin +
counter 축(σ 무접촉·depth 유계·apply 비승격·침묵 삼킴 금지)을 기계 고정한다.
측정은 전부 KG 상태 재도출 — in-memory report echo 단독 인정 금지.

# KG: LakatosTree_BhgmanDispatchLoop_20260710/dispatch_consumer_keystone
# KG: adr-legion-runtime-shape-review-2026-06-20 (G5-C5)
"""

from __future__ import annotations

from pathlib import Path

from engine.kg_local.runner import make_local_runner
from engine.kg_local.store import LocalKgStore
from engine.legion.commanders import build_default_legion
from engine.legion.dispatch_consumer import (
    DEPTH_CAPPED,
    EXEC_FAILED,
    EXECUTED,
    SKIPPED_BUDGET,
    SKIPPED_EDGE,
    SKIPPED_UNKNOWN_TARGET,
    consume_dispatch,
)
from engine.legion.legion_models import CommanderStage
from engine.legion.measurement import MAX_DISPATCH_DEPTH, DispatchDecision

N_CONFIDENT = 12  # dead_node_count>10 발화 임계 초과


def _seed_confident(store: LocalKgStore, n: int = N_CONFIDENT, tag: str = "cd") -> None:
    """abs/rel lineage 쌍(정규화 동일 경로 + 동일 sha=byte-동일) — 확신-SUPERSEDE 케이스."""
    for i in range(n):
        for prefix in ("/Users/old/bhgman_tool/", "bhgman_tool/"):
            store.nodes.append(
                {
                    "labels": ["SourceCodeNode"],
                    "props": {
                        "name": f"{tag}_{i}",
                        "sourcePath": f"{prefix}pkg/{tag}_{i}.py",
                        "sha256": f"{i:064x}",
                        "lineCount": 10 + i,
                    },
                }
            )


def _seed_uncertain(store: LocalKgStore, tag: str = "unc") -> list[str]:
    """정규화 동일 경로 + *다른* sha(비동일) + disk-truth 없음 → is_confident_supersede
    False = deferred(불확실셋). 소비자가 몇 번을 돌아도 이 노드들은 SUPERSEDED 되면 안 된다."""
    names = []
    for i in range(2):
        for k, prefix in enumerate(("/Users/old/bhgman_tool/", "bhgman_tool/")):
            nm = f"{tag}_{i}_{k}"
            names.append(nm)
            store.nodes.append(
                {
                    "labels": ["SourceCodeNode"],
                    "props": {
                        "name": nm,
                        "sourcePath": f"{prefix}pkg/{tag}_{i}.py",
                        "sha256": f"{(1000 + i * 10 + k):064x}",  # 쌍 내 sha 상이
                        "lineCount": 10 + k,
                    },
                }
            )
    return names


def _ctx(store: LocalKgStore, *, apply: bool) -> dict:
    runner = make_local_runner(store, autosave=False)
    return {
        "run_cypher": runner,
        "write_cypher": runner,
        "apply": apply,
        "cycle_id": "test-dispatch-consumer",
    }


def _consumed_events(store: LocalKgStore) -> list[dict]:
    return [e["props"] for e in store.find_nodes("DispatchEvent") if e["props"].get("consumed_at")]


def _superseded_names(store: LocalKgStore) -> set[str]:
    return {
        n["props"].get("name")
        for n in store.find_nodes("SourceCodeNode")
        if n["props"].get("status") == "SUPERSEDED"
    }


# ── 폐루프 본선 ───────────────────────────────────────────────────────────────
def test_fired_decision_is_executed_and_kg_records_consumption():
    """keystone: 발화 → 소비 → 실행 → KG consumed_at 실측 (전 처분 provenance 실명)."""
    store = LocalKgStore()
    _seed_confident(store)
    ctx = _ctx(store, apply=True)
    run = build_default_legion().run(dict(ctx))
    fired = [d for d in run.dispatch_decisions if d.metric_name == "dead_node_count"]
    assert fired, "전제: occam self-dispatch 가 발화해야 (seeding 실패면 여기서 죽는다)"

    report = consume_dispatch(run.dispatch_decisions, ctx)

    assert report.executed, "allowlist 엣지(occam→occam)는 실행돼야"
    consumed = _consumed_events(store)
    assert consumed, "소비 처분이 KG :DispatchEvent 에 SET 되어야 (report echo 불인정)"
    assert any(e.get("consume_status") == EXECUTED for e in consumed)
    # 전 처분 실명: report 의 모든 record 가 KG 에 대응 이벤트를 가진다.
    assert len(consumed) >= len(report.all_records) - 0


def test_janitor_clears_own_trigger_with_apply():
    """폐루프의 기능 증명 — *인과 분리* 버전(적대검증 2026-07-10): run1 의 in-run apply 가
    원 백로그를 닦으므로, janitor 몫의 백로그를 소비 직전 재주입해 '닫은 것이 janitor'임을
    분리 증명한다. (no-op counter 는 아래 test_do_nothing_janitor_does_not_clear.)"""
    store = LocalKgStore()
    _seed_confident(store)
    ctx = _ctx(store, apply=True)
    run = build_default_legion().run(dict(ctx))
    _seed_confident(store, tag="regen")  # janitor 몫 재주입 — run1 은 이미 지나갔다

    consume_dispatch(run.dispatch_decisions, ctx)

    run2 = build_default_legion().run(dict(ctx))
    refired = [d for d in run2.dispatch_decisions if d.metric_name == "dead_node_count"]
    assert not refired, "janitor 가 재주입 백로그를 닫았으면 dead_node_count 재발화는 없어야"


def test_do_nothing_janitor_does_not_clear():
    """인과 counter: 유효한 hygiene 모양만 반환하고 아무 일도 안 하는 janitor 면 재주입
    백로그가 남아 재발화한다 — 자기해소 green 이 run1 의 in-run apply 공로가 아니라
    janitor 실행의 인과임을 판별 (적대검증 2026-07-10 high 의 봉합)."""
    store = LocalKgStore()
    _seed_confident(store)
    ctx = _ctx(store, apply=True)
    run = build_default_legion().run(dict(ctx))
    fired = [d for d in run.dispatch_decisions if d.metric_name == "dead_node_count"]
    assert fired
    _seed_confident(store, tag="regen")

    noop = CommanderStage(
        "occam",
        "정리",
        ("run_cypher",),
        ("hygiene",),
        lambda _ctx: {"hygiene": {"mode": "occam", "candidates": [], "superseded_candidates": 0}},
        measure=None,
    )
    report = consume_dispatch(run.dispatch_decisions, ctx, stages={"occam": noop})
    assert report.executed, "no-op 도 실행 자체는 된다 (실행≠효능의 분리)"

    run2 = build_default_legion().run(dict(ctx))
    refired = [d for d in run2.dispatch_decisions if d.metric_name == "dead_node_count"]
    assert refired, "no-op janitor 면 백로그가 남아 재발화해야 — 아니면 배터리가 인과를 못 가름"


def test_depth_capped_outcome_is_not_vacuous_success():
    """outcome 정직성(적대검증 2026-07-10 high): 전량 deferred(σ게이트가 막는) 백로그는
    apply=True 여도 janitor 가 못 닫는다 — 체인은 depth-cap 종결되고, 그 지점의 outcome 은
    재측정값 대조로 0 이어야 한다 (children=[] 공허 판정이면 1 로 날조된다)."""

    class _Log:
        def __init__(self):
            self.rows = []

        def record(self, **kw):
            self.rows.append(kw)

    store = LocalKgStore()
    # 12그룹 전부 불확실(동일 정규화경로+상이 sha) → 후보는 잡히되 전량 deferred.
    for i in range(12):
        for k, prefix in enumerate(("/Users/old/bhgman_tool/", "bhgman_tool/")):
            store.nodes.append(
                {
                    "labels": ["SourceCodeNode"],
                    "props": {
                        "name": f"dfr_{i}_{k}",
                        "sourcePath": f"{prefix}pkg/dfr_{i}.py",
                        "sha256": f"{(2000 + i * 10 + k):064x}",
                        "lineCount": 10 + k,
                    },
                }
            )
    ctx = _ctx(store, apply=True)
    run = build_default_legion().run(dict(ctx))
    fired = [d for d in run.dispatch_decisions if d.metric_name == "dead_node_count"]
    assert fired, "deferred 후보도 dead_node_count 로 계수되어 발화해야 (전제)"

    log = _Log()
    report = consume_dispatch(run.dispatch_decisions, ctx, instrument_log=log)

    assert report.depth_capped, "σ게이트가 막는 백로그는 depth-cap 으로 종결돼야"
    for rec in report.executed + report.depth_capped:
        assert rec.outcome == 0, (
            f"조건이 명백히 잔존하는데 outcome={rec.outcome} — 재측정 대조가 아니라 "
            "공허 판정이면 여기서 1 이 나온다"
        )
    assert log.rows and all(r["outcome"] == 0 for r in log.rows), (
        "instrument ground-truth 도 전부 0 이어야 (성공 날조 금지)"
    )
    # 불확실셋은 여전히 무접촉 (σ counter 재확인).
    assert not _superseded_names(store)


def test_degraded_output_is_exec_failed():
    """fail-soft 봉합(적대검증 2026-07-10 high): occam 류 엔진은 내부 예외를 삼키고
    degraded stub 을 반환한다 — 소비자는 그것을 EXECUTED 성공이 아니라 EXEC_FAILED 로
    실명 처분해야 한다."""

    def _degraded_run(_ctx: dict) -> dict:
        return {"hygiene": {"mode": "degraded", "reason": "kg unreachable", "summary": "x"}}

    broken = CommanderStage(
        "occam", "정리", ("run_cypher",), ("hygiene",), _degraded_run, measure=None
    )
    store = LocalKgStore()
    ctx = _ctx(store, apply=True)
    report = consume_dispatch([_decision("occam", "occam")], ctx, stages={"occam": broken})
    assert not report.executed
    assert [r.status for r in report.failed] == [EXEC_FAILED]
    assert "degraded" in report.failed[0].detail
    assert report.failed[0].outcome == 0


def test_outcome_recorded_only_on_apply():
    """record_outcome 최초 배선: apply=True + instrument 주입 시에만 ground-truth 기록."""

    class _Log:
        def __init__(self):
            self.rows = []

        def record(self, **kw):
            self.rows.append(kw)

    store = LocalKgStore()
    _seed_confident(store)
    ctx = _ctx(store, apply=True)
    run = build_default_legion().run(dict(ctx))
    log = _Log()
    report = consume_dispatch(run.dispatch_decisions, ctx, instrument_log=log)
    assert log.rows, "apply=True + instrument → outcome 이 기록돼야"
    assert all(r["outcome"] in (0, 1) for r in log.rows)
    assert all(rec.outcome is not None for rec in report.executed)

    # 대조: apply=False 면 기록 없음 (dry-run 은 효능 판정 불가 — outcome 날조 금지).
    store2 = LocalKgStore()
    _seed_confident(store2)
    ctx2 = _ctx(store2, apply=False)
    run2 = build_default_legion().run(dict(ctx2))
    log2 = _Log()
    report2 = consume_dispatch(run2.dispatch_decisions, ctx2, instrument_log=log2)
    assert not log2.rows
    assert all(rec.outcome is None for rec in report2.executed + report2.depth_capped)


# ── counter 축: σ게이트 무접촉 ────────────────────────────────────────────────
def test_deferred_uncertain_set_never_touched():
    """σ counter: 불확실(deferred) 후보는 소비자가 몇 번을 실행해도 SUPERSEDED 금지 —
    write 경로가 occam σ게이트(is_confident_supersede)를 상속하는 단일 경로임의 실측."""
    store = LocalKgStore()
    _seed_confident(store)
    uncertain = _seed_uncertain(store)
    ctx = _ctx(store, apply=True)
    run = build_default_legion().run(dict(ctx))
    consume_dispatch(run.dispatch_decisions, ctx)

    superseded = _superseded_names(store)
    touched = superseded & set(uncertain)
    assert not touched, f"deferred/불확실셋이 소비자 경유로 SUPERSEDED 됨: {touched}"
    # sanity: 확신셋은 실제로 정리됐다 (테스트가 vacuous 하지 않음을 증명).
    assert any(nm.startswith("cd_") for nm in superseded)


def test_apply_is_never_escalated():
    """apply 비승격: ctx.apply=False 면 소비자 경유 실행도 write 0 (dry-run 유지)."""
    store = LocalKgStore()
    _seed_confident(store)
    ctx = _ctx(store, apply=False)
    run = build_default_legion().run(dict(ctx))
    consume_dispatch(run.dispatch_decisions, ctx)
    assert not _superseded_names(store), "apply=False 소비에서 SUPERSEDED write 는 금지"


def test_consumer_has_no_direct_kg_adapter_import():
    """구조 가드: 소비자는 occam 의 write 표면(kg_adapter/semantic_dedup/occam_runner)을
    직접 import 하지 않는다 — write 는 stage.run(σ게이트 내장) 경유가 유일해야 한다.
    (AST import 검사 — docstring 의 설명 언급은 죄가 아니다)"""
    import ast

    src = (Path(__file__).resolve().parents[1] / "dispatch_consumer.py").read_text(encoding="utf-8")
    forbidden = ("kg_adapter", "semantic_dedup", "occam_runner", "occam_engine")
    hits: list[str] = []
    for node in ast.walk(ast.parse(src)):
        mods: list[str] = []
        if isinstance(node, ast.Import):
            mods = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            mods = [node.module or ""] + [a.name for a in node.names]
        hits.extend(m for m in mods if any(f in m for f in forbidden))
    assert not hits, f"dispatch_consumer 가 occam write 표면을 직접 import: {hits}"


# ── counter 축: 유계 (depth + budget) ────────────────────────────────────────
def test_depth_cap_terminates_dry_run_chain():
    """depth counter: apply=False 면 KG 불변 → 매 재측정 재발화 — 그래도 체인은
    MAX_DISPATCH_DEPTH 에서 기계 종결(실행 수 == cap, 마지막 처분 = depth_capped)."""
    store = LocalKgStore()
    _seed_confident(store)
    ctx = _ctx(store, apply=False)
    run = build_default_legion().run(dict(ctx))
    fired = [d for d in run.dispatch_decisions if d.metric_name == "dead_node_count"]
    assert fired

    report = consume_dispatch(run.dispatch_decisions, ctx)

    n_exec = len(report.executed) + len(report.depth_capped)
    assert n_exec == MAX_DISPATCH_DEPTH, f"체인 실행 수는 정확히 cap: {n_exec}"
    assert report.depth_capped, "종결 처분이 depth_capped 로 실명 기록돼야"
    assert any(e.get("consume_status") == DEPTH_CAPPED for e in _consumed_events(store))


def test_budget_exhaustion_is_recorded_not_silent():
    """budget counter: max_executions 소진 시 잔여는 SKIPPED_BUDGET 실명 처분."""
    store = LocalKgStore()
    _seed_confident(store)
    ctx = _ctx(store, apply=False)
    run = build_default_legion().run(dict(ctx))
    report = consume_dispatch(run.dispatch_decisions, ctx, max_executions=1)
    assert len(report.executed) + len(report.depth_capped) == 1
    assert any(r.status == SKIPPED_BUDGET for r in report.skipped)


# ── fail-closed 처분 ─────────────────────────────────────────────────────────
def _decision(source: str, target: str, metric: str = "dead_node_count") -> DispatchDecision:
    return DispatchDecision(
        source_commander=source,
        target_commander=target,
        metric_name=metric,
        metric_value=99.0,
        threshold=10.0,
        reason="test",
    )


def test_unknown_target_is_skipped_fail_closed():
    store = LocalKgStore()
    ctx = _ctx(store, apply=False)
    report = consume_dispatch([_decision("occam", "not_a_commander")], ctx)
    assert not report.executed
    assert [r.status for r in report.skipped] == [SKIPPED_UNKNOWN_TARGET]
    assert any(e.get("consume_status") == SKIPPED_UNKNOWN_TARGET for e in _consumed_events(store))


def test_non_allowlist_edge_is_skipped_with_provenance():
    """occam→naesengmoon(supersession_confidence) 등 allowlist 밖 엣지는 실행 없이
    provenance-only skip — 무음 확장 금지(G5-C5)의 런타임 절반."""
    store = LocalKgStore()
    ctx = _ctx(store, apply=False)
    report = consume_dispatch([_decision("occam", "naesengmoon", "supersession_confidence")], ctx)
    assert not report.executed
    assert [r.status for r in report.skipped] == [SKIPPED_EDGE]
    assert any(e.get("consume_status") == SKIPPED_EDGE for e in _consumed_events(store))


def test_stage_failure_is_named_not_swallowed():
    """침묵 삼킴 금지: stage.run 예외 → EXEC_FAILED 실명 기록(+KG), crash 없음."""

    def _boom(_ctx: dict) -> dict:
        raise RuntimeError("janitor blew up")

    broken = CommanderStage("occam", "정리", ("run_cypher",), ("hygiene",), _boom, measure=None)
    store = LocalKgStore()
    ctx = _ctx(store, apply=True)
    report = consume_dispatch([_decision("occam", "occam")], ctx, stages={"occam": broken})
    assert [r.status for r in report.failed] == [EXEC_FAILED]
    assert "janitor blew up" in report.failed[0].detail
    assert report.failed[0].outcome == 0, "apply 모드의 실패는 효능 0 으로 기록"
    assert any(e.get("consume_status") == EXEC_FAILED for e in _consumed_events(store))
