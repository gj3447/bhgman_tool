"""재배맨 production 표면 — run-record(KG audit) + OTel attrs + W3C PROV-O export.

Longinus가 두꺼운 이유의 74%는 "감사 증거를 표준포맷·상시감시로 내보내는 production 표면"이었다
(채널 5종/daemon/sha256/SCIP). 재배맨 도메인(계획→씨앗→출격→lifecycle)에 *의미 있는* 표면만
이식한다 — 한 plan/lifecycle 실행을 (1) KG audit 노드 (2) OTel span attrs (3) PROV-O provenance
로 내보낸다. 무의미한 것(sha256 file-hash/SCIP code-index)은 도메인 부재로 N/A.

provexport.serialize 재사용(직렬화 dedup). prov 라이브러리는 optional extra — 없으면 graceful None.
covenant: KG record는 MERGE(멱등), 파괴 토큰 없음.

# KG: lesson-jaebaeman-engine-impl-prom16-2026-06-01, prov-o-nanopub-export-2026-05-30 (provexport 재사용)
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

CypherRunner = Callable[[str, dict], "list[dict]"]


@dataclass(frozen=True)
class RunRecord:
    # KG: 재배맨-v2-subagent-runtime-protocol
    """한 재배맨 실행의 감사 레코드 (plan + 선택적 lifecycle 결과 요약)."""

    run_id: str
    goal: str
    planned_seeds: int
    depth_max: int = 0
    leaf_count: int = 0
    violations: int = 0
    dispatched: int = 0
    collected: int = 0
    failed: int = 0
    created_at: str = ""  # ISO8601; 호출자가 stamp (테스트 결정론 위해 주입식)


def from_results(
    run_id: str, plan_result, lifecycle_result=None, *, created_at: str = ""
) -> RunRecord:
    # KG: 재배맨-v2-subagent-runtime-protocol
    """PlanResult (+ 선택 LifecycleResult) → RunRecord. 두 단계 결과를 한 감사 레코드로."""
    lc = lifecycle_result
    return RunRecord(
        run_id=run_id,
        goal=plan_result.goal,
        planned_seeds=len(plan_result.seeds),
        depth_max=plan_result.depth_max,
        leaf_count=plan_result.leaf_count,
        violations=len(plan_result.violations),
        dispatched=len(lc.outcomes) if lc is not None else 0,
        collected=lc.collected if lc is not None else 0,
        failed=lc.failed if lc is not None else 0,
        created_at=created_at,
    )


# ── (1) KG audit 노드 (covenant: MERGE) ──────────────────────────────────────
_RUN_MERGE = (
    "MERGE (r:JaebaemanRun {name: $run_id}) "
    "SET r.goal = $goal, r.plannedSeeds = $planned, r.depthMax = $depth_max, "
    "r.leafCount = $leaf_count, r.violations = $violations, r.dispatched = $dispatched, "
    "r.collected = $collected, r.failed = $failed, r.createdAt = $created_at "
    "RETURN r.name AS recorded"
)


def build_run_merge(rec: RunRecord) -> tuple[str, dict]:
    # KG: 재배맨-v2-subagent-runtime-protocol
    """run-record MERGE cypher + params (covenant: SET/MERGE만, 파괴 없음)."""
    return _RUN_MERGE, {
        "run_id": rec.run_id,
        "goal": rec.goal,
        "planned": rec.planned_seeds,
        "depth_max": rec.depth_max,
        "leaf_count": rec.leaf_count,
        "violations": rec.violations,
        "dispatched": rec.dispatched,
        "collected": rec.collected,
        "failed": rec.failed,
        "created_at": rec.created_at,
    }


def record_to_kg(rec: RunRecord, write_cypher: CypherRunner) -> str:
    # KG: 재배맨-v2-subagent-runtime-protocol
    """:JaebaemanRun 감사 노드 write. Longinus drift-event 기록의 재배맨 대응."""
    cypher, params = build_run_merge(rec)
    write_cypher(cypher, params)
    return rec.run_id


# ── (2) OTel span attributes (hard dep 없음 — dict만) ────────────────────────
def to_otel_attributes(rec: RunRecord) -> dict:
    # KG: 재배맨-v2-subagent-runtime-protocol
    """OTel span attribute dict (otel SDK 없어도 동작). orchestration 관측 표면."""
    return {
        "jaebaeman.run_id": rec.run_id,
        "jaebaeman.goal": rec.goal,
        "jaebaeman.planned_seeds": rec.planned_seeds,
        "jaebaeman.depth_max": rec.depth_max,
        "jaebaeman.leaf_count": rec.leaf_count,
        "jaebaeman.violations": rec.violations,
        "jaebaeman.dispatched": rec.dispatched,
        "jaebaeman.collected": rec.collected,
        "jaebaeman.failed": rec.failed,
    }


# ── (3) W3C PROV-O export (graceful — prov optional extra) ───────────────────
def to_prov(rec: RunRecord, fmt: str = "turtle") -> str | None:
    # KG: 재배맨-v2-subagent-runtime-protocol
    """plan/lifecycle 실행을 PROV-O로. prov 라이브러리 없으면 None (graceful).

    plan = prov:Activity, 각 씨앗 = prov:Entity wasGeneratedBy plan, lifecycle = prov:Activity used.
    provexport.serialize 재사용.
    """
    try:
        from prov.model import ProvDocument  # noqa: PLC0415

        from engine.provexport.prov_export import serialize  # noqa: PLC0415
    except ImportError:
        return None

    doc = ProvDocument()
    doc.add_namespace("jbm", "https://bhgman.tool/jaebaeman#")
    # prov>=2.2 attribute dicts are invariant-typed — tuple lists satisfy the Iterable overload
    plan_act = doc.activity(f"jbm:plan/{rec.run_id}", other_attributes=[("jbm:goal", rec.goal)])
    seeds_ent = doc.entity(
        f"jbm:seeds/{rec.run_id}",
        [("jbm:plannedSeeds", rec.planned_seeds), ("jbm:depthMax", rec.depth_max)],
    )
    doc.wasGeneratedBy(seeds_ent, plan_act)
    if rec.dispatched:
        disp_act = doc.activity(
            f"jbm:dispatch/{rec.run_id}",
            other_attributes=[("jbm:collected", rec.collected), ("jbm:failed", rec.failed)],
        )
        doc.used(disp_act, seeds_ent)
    return serialize(doc, fmt)


__all__ = [
    "CypherRunner",
    "RunRecord",
    "build_run_merge",
    "from_results",
    "record_to_kg",
    "to_otel_attributes",
    "to_prov",
]
