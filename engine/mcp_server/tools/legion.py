"""MCP tools — the 7 legion commanders (`legion_roster`, `legion_run`).

The existing MCP surface only exposed the old "5무기" era tools (apt / harness /
longinus / prometheus / taliban / tpa). This module exposes the unified 7-commander
legion (비행기맨#4 결정화) properly:

  획득(prometheus) → 연결(longinus) → 창조(eureka) → 정리(occam) → 검증(naesengmoon)
  → 실현(hades), with 출격(jaebaeman) = the dispatch loop itself.

Both tools honour the legion "infra 0 still works" covenant — they run on the bundled
deterministic LocalKgStore (no live Neo4j, no API key), so they are callable in any
MCP context. `legion_run` is read-mostly: it exercises the closed Contract-bound loop
(requires ⊆ accumulated provides, naesengmoon oracle gate between stages) and reports
which commanders ran, not a destructive KG mutation.

# KG: adr-seven-commander-legion-architecture-2026-05-27, bihaenggiman-legioncommanders-2026-05-26,
#     project-legion-unification-kg-engine-2026-06-01, hades-canonical-2026-05-27
"""

from __future__ import annotations

from typing import Any

# Jaebaeman is not a CommanderStage — 출격(dispatch) is the Legion.run() loop itself
# (CANONICAL_ORDER excludes it). Surfaced in the roster as the 7th for completeness.
_JAEBAEMAN = {
    "name": "jaebaeman",
    "verb": "출격",
    "requires": [],
    "provides": [],
    "role": "dispatch-loop (Legion.run itself, not a stage)",
}


def _stage_roster() -> list[dict[str, Any]]:
    from engine.legion.commanders import default_stages  # noqa: PLC0415

    roster: list[dict[str, Any]] = []
    for s in default_stages():
        roster.append(
            {
                "name": s.name,
                "verb": s.verb,
                "requires": list(s.requires),
                "provides": list(s.provides),
                "role": "active commander (CommanderStage)",
            }
        )
    return roster


def legion_roster_impl() -> dict[str, Any]:
    """The canonical 7-commander roster + Contract handoff chain."""
    stages = _stage_roster()
    return {
        "count": len(stages) + 1,
        "commanders": stages + [_JAEBAEMAN],
        "canonical_order": [s["verb"] for s in stages],
        "note": "획득→연결→창조→정리→검증→실현 (+출격=dispatch loop). naesengmoon "
        "requires all 4 prior provides; hades requires verdict (실현 종착, gate 후).",
    }


def legion_run_impl(
    cycle_id: str = "mcp-legion",
    kg_path: str | None = None,
    store: Any | None = None,
    consume: bool = False,
) -> dict[str, Any]:
    # KG: LakatosTree_BhgmanJaebaeman_20260702/jbm_s3_mcp_substrate_parity
    # KG: 재배맨-v2-subagent-runtime-protocol
    """Run the closed legion loop via the 재배맨 substrate (deterministic, infra-0).

    jbm-s3 (audit wf_376c327b-8f3 gap G4): this used to call
    ``build_default_legion().run(ctx)`` directly, bypassing
    ``run_legion_via_jaebaeman`` — so the 재배맨 planner/lifecycle/``:JaebaemanRun``
    telemetry existed only on the CLI path and were structurally unreachable from
    MCP. Now MCP and CLI share the one substrate code path: the response carries
    the RunRecord surface (``jaebaeman`` block) and one ``:JaebaemanRun`` audit
    record lands in the LocalKgStore per run (MERGE-only covenant; the bundled
    store is ephemeral unless ``kg_path`` is given, so this stays read-mostly).

    ``store`` is a DIP seam for tests (inject a LocalKgStore and observe the
    telemetry arrival side); it is not exposed over the MCP tool signature.
    Does not require live Neo4j or an API key.
    """
    from engine.kg_local.runner import make_local_runner  # noqa: PLC0415
    from engine.kg_local.store import LocalKgStore  # noqa: PLC0415
    from engine.legion.jaebaeman_substrate import run_legion_via_jaebaeman  # noqa: PLC0415
    from engine.legion.verdict_gate import (  # noqa: PLC0415
        KgVerdictLedger,
        WeakVerdictKeyError,
        build_gate_from_env,
        mint_cycle_id,
    )

    # R6: 서버-mint — 기본 sentinel 이면 run 마다 고유 cycle (ledger false-collision 방지).
    if not cycle_id or cycle_id == "mcp-legion":
        cycle_id = mint_cycle_id()

    if store is None:
        store = LocalKgStore(kg_path) if kg_path else LocalKgStore()
    run_cypher = make_local_runner(store, autosave=False)
    # kg-corroborate 배선 (q-naesengmoon-single-authority): infra-0 MCP 경로에도 별도-소스
    # 정전 대조 oracle leg 를 공급 — LLM 없이도 나생문 verify 가 n_eff≥2 (1.0 퇴화 해소).
    from engine.agents.grounding import LocalGroundingSource  # noqa: PLC0415

    ctx: dict[str, Any] = {
        "run_cypher": run_cypher,
        "cycle_id": cycle_id,
        "grounding": LocalGroundingSource(store),
        "claim": f"legion closed loop completed for {cycle_id}",
    }
    # R7: verdict 키 설정 시 in-loop 게이트 주입 — _run_verify(producer 서명) + _run_realize
    # (consumer 검증). 미설정 → legacy(게이트 없음, 비파괴). artifact_id 는 run-level 바인딩
    # (per-node 바인딩은 OQ1b selection-node 서명 경로).
    try:
        ctx["verdict_gate"] = build_gate_from_env(ledger=KgVerdictLedger(store))
        ctx["artifact_id"] = cycle_id
    except WeakVerdictKeyError:
        pass

    # G4 봉합: CLI cmd_legion 과 동일한 substrate 경로 — legion.run 은 여전히 executor,
    # 재배맨은 그 위 plan(7 seeds)·lifecycle(출격→수확)·audit(:JaebaemanRun) 층.
    result = run_legion_via_jaebaeman(
        ctx, run_id=f"mcp-{cycle_id}", write_cypher=run_cypher, apply=True
    )
    run = result["legion_run"]
    lifecycle = result["lifecycle"]
    record = result["run_record"]

    # G5-C5: post-run 유계 소비 (opt-in). LocalKgStore 전용 경로라 janitor write 도
    # 공유 KG 에 닿을 수 없다 — apply=True 는 substrate 호출과 동일한 ephemeral 범위.
    consumed_block: list[dict[str, Any]] = []
    if consume:
        from engine.legion.dispatch_consumer import consume_dispatch  # noqa: PLC0415

        consume_ctx = {**ctx, "write_cypher": run_cypher, "apply": True}
        report = consume_dispatch(run.dispatch_decisions, consume_ctx)
        consumed_block = [
            {
                "source": r.decision.source_commander,
                "target": r.decision.target_commander,
                "metric": r.decision.metric_name,
                "status": r.status,
                "depth": r.decision.depth,
                "children": r.child_decision_count,
                "outcome": r.outcome,
                "detail": r.detail,
            }
            for r in report.all_records
        ]

    return {
        "cycle_id": cycle_id,
        "completed": bool(run.completed),
        "contract_violation": run.contract_violation,
        "gate_failure": run.gate_failure,
        "ran": [
            {"commander": o.stage, "verb": o.verb, "ok": bool(o.ok), "detail": o.detail}
            for o in run.outcomes
        ],
        "final_context_keys": list(run.final_context_keys),
        # 나생문 최종 verdict 노출 (ensemble/n_eff/oracle_legs) — MCP 표면에서 verify 실체 관측.
        "verdict": dict(run.final_verdict),
        # 측정-주도 dispatch 관측면 (seam-integrity 20260708): 결정이 :DispatchEvent 로만
        # 가라앉으면 오발화(예: 접지 ratio 구조적 0.0 의 매 run self-recurse)가 MCP 표면에서
        # 보이지 않는다 — 어떤 컨트롤이 언제 발화했는지 caller 가 직접 관측한다.
        "dispatch": [
            {
                "source": d.source_commander,
                "target": d.target_commander,
                "metric": d.metric_name,
                "value": d.metric_value,
                "threshold": d.threshold,
                "reason": d.reason,
            }
            for d in run.dispatch_decisions
        ],
        # G5-C5 소비 관측면 (opt-in; 기본 [] — 기존 응답 스키마는 additive 확장만).
        "dispatch_consumed": consumed_block,
        "jaebaeman": {
            "run_id": record.run_id,
            "planned_seeds": record.planned_seeds,
            "dispatched": record.dispatched,
            "collected": record.collected,
            "failed": record.failed,
            "seed_outcomes": [
                {"seed": o.seed_name, "status": o.status.value} for o in lifecycle.outcomes
            ],
        },
        "backend": "local-kg (infra-0; pass NEO4J_* to the engine for live KG)",
    }


def register(mcp: Any) -> None:
    """Attach the 7-commander legion tools to the FastMCP instance."""

    @mcp.tool()
    def legion_roster() -> dict[str, Any]:
        """List the 7 legion commanders (비행기맨#4) with their Contract requires/provides.

        Returns: roster dict {count, commanders[], canonical_order, note}.
        """
        return legion_roster_impl()

    @mcp.tool()
    def legion_run(
        cycle_id: str = "mcp-legion", kg_path: str = "", consume: bool = False
    ) -> dict[str, Any]:
        """Run the closed legion loop (획득→…→실현) on the bundled local KG (no infra).

        Args:
            cycle_id: label for this run.
            kg_path: optional path to a LocalKgStore JSON; empty = default bundle.
            consume: opt-in post-run dispatch consumption (G5-C5 — allowlist·depth-capped;
                the occam janitor edge executes, everything else is provenance-only skip).

        Returns: run summary {completed, ran[], dispatch[], dispatch_consumed[], ...}.
        """
        return legion_run_impl(cycle_id=cycle_id, kg_path=kg_path or None, consume=consume)


__all__ = ["register", "legion_roster_impl", "legion_run_impl"]
