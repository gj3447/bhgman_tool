"""MCP tool — `prometheus_research`.

프로메테우스(Prometheus) — 비행기맨 #4 LegionCommander, 획득(acquire). 행동 전 지식 선행.
knowledge-first 연구 진입점: topic → 권장 N + axis×sub-axis 매트릭스 + KG-first 지령.

Legion 아키텍처에서 프로메테우스는 외부/KG ground-truth를 나생문 oracle 렌즈에 공급 →
PROM 16 한계 #5(critic이 KG 진실 못 넘음) 해결 보강. 본 tool은 deterministic skeleton
(실제 web dispatch는 subagent 필요 — MCP tool은 spawn 불가, 그래서 계획+KG-first 진입만).

# KG: prometheus-grounding-2026-05-05, ATOM_Skill_prometheus,
#     adr-seven-commander-legion-architecture-2026-05-27 (step 6),
#     consensus-naesengmoon-limits-prom16-2026-05-27 (#5 ground-truth)
"""

from __future__ import annotations

from typing import Any

# auto_estimate 밴드 (MethodologyConfig_default_v26 prometheus_* 필드 표시값).
_SMALL, _MEDIUM, _LARGE = (3, 5), (6, 11), (12, 20)
_AXES = ("history", "principle", "implementation", "limitations", "connections", "applications")
_SUB_AXES = ("official-docs", "community-cases", "benchmarks", "alternatives", "pitfalls", "trends")


def _auto_estimate(topic: str) -> int:
    """topic 규모로 N 추정. 단어 수 기준 소/중/대 밴드."""
    words = len(topic.split())
    if words <= 4:
        return _SMALL[1]
    if words <= 10:
        return _MEDIUM[1]
    return _LARGE[1]


def prometheus_research_impl(topic: str, n: int = 0) -> dict[str, Any]:
    """Knowledge-first 연구 계획을 반환 (행동 전 지식 선행).

    Args:
        topic: 연구 주제
        n: subagent 수 (0이면 auto_estimate)

    Returns:
        ResearchPlan dict: n, strategy, matrix(axis×sub-axis if n>=12), kg_first 지령.
    """
    topic = topic.strip()
    if not topic:
        return {"error": "empty topic", "n": 0}
    resolved_n = n if n > 0 else _auto_estimate(topic)

    if resolved_n <= _SMALL[1]:
        strategy = "manual-template (원인분석/공식문서/커뮤니티)"
        matrix = None
    elif resolved_n <= _MEDIUM[1]:
        strategy = "preset-domains"
        matrix = None
    else:
        strategy = "axis x sub-axis 교차표"
        matrix = {"axes": list(_AXES), "sub_axes": list(_SUB_AXES)}

    return {
        "topic": topic,
        "n": resolved_n,
        "strategy": strategy,
        "matrix": matrix,
        "principle": "knowledge-first — 행동 전 불(지식)을 먼저 훔쳐온다",
        "kg_first": "Step 2.5 하계 pre-fetch: 기존 ResearchFinding/Lesson 조회 후 중복 회피",
        "grounds_critic": "획득한 ground-truth가 나생문 oracle 렌즈에 공급 (PROM #5 해결)",
    }


def prometheus_ingest_impl(
    topic: str,
    findings: list[dict[str, Any]],
    synthesis: str = "",
    cycle_id: str = "",
    n: int = 0,
) -> dict[str, Any]:
    """PROPOSE the MERGE cyphers that crystallize gathered research findings into the KG.

    The MCP layer can't spawn subagents (the research itself is the parent Claude's job),
    so this closes the *ingest* half of the finding: the parent passes the findings it
    gathered and gets idempotent UNWIND-MERGE cyphers (a Lesson + N ResearchFinding nodes)
    to apply via kg_query(mutate=true). Reuses the engine's ingest_cypher (no drift).

    Args:
        topic: research topic.
        findings: list of {domain|sub_question, text|summary, ok?, agent_id?, confidence?}.
        synthesis: the synthesized report body (stored on the Lesson).
        cycle_id: provenance id (defaults to "manual").
        n: planned subagent count (defaults to len(findings)).
    """
    topic = topic.strip()
    if not topic or not findings:
        return {"error": "topic and findings required", "ingest_cyphers": []}
    try:
        from engine.agents.dispatch import SubagentResult
        from engine.agents.prometheus import ResearchReport, ingest_cypher
    except ImportError as exc:  # agents extra absent — graceful (no anthropic needed to plan)
        return {"error": f"agents runtime unavailable: {exc}", "ingest_cyphers": []}

    cid = (cycle_id or "manual").strip()
    sub_qs = tuple(
        str(f.get("domain") or f.get("sub_question") or f"q{i}") for i, f in enumerate(findings)
    )
    results = tuple(
        SubagentResult(
            name=str(f.get("agent_id") or f"agent-{i}"),
            ok=bool(f.get("ok", True)),
            text=str(f.get("text") or f.get("summary") or ""),
        )
        for i, f in enumerate(findings)
    )
    report = ResearchReport(
        topic=topic,
        n=n or len(findings),
        sub_questions=sub_qs,
        findings=results,
        synthesis=synthesis,
    )
    cyphers = ingest_cypher(report, cid)
    return {
        "topic": topic,
        "cycle_id": cid,
        "finding_count": len(findings),
        "ingest_cyphers": [{"cypher": c, "params": p} for c, p in cyphers],
        "note": "PROPOSE (MERGE-only, idempotent). Apply via kg_query(mutate=true).",
    }


def register(mcp: Any) -> None:
    """Attach the `prometheus_research` + `prometheus_ingest` tools to the FastMCP instance."""

    @mcp.tool()
    def prometheus_research(topic: str, n: int = 0) -> dict[str, Any]:
        """Knowledge-first 연구 계획 (프로메테우스, 획득). 행동 전 지식 선행.

        Args:
            topic: 연구 주제
            n: subagent 수 (0=auto_estimate)

        Returns: ResearchPlan dict (n, strategy, matrix, kg_first 지령).
        """
        return prometheus_research_impl(topic, n)

    @mcp.tool()
    def prometheus_ingest(
        topic: str,
        findings: list[dict[str, Any]],
        synthesis: str = "",
        cycle_id: str = "",
        n: int = 0,
    ) -> dict[str, Any]:
        """Crystallize gathered research findings into the KG (프로메테우스의 KG-write 반쪽).

        Returns idempotent MERGE cyphers (a Lesson + ResearchFinding nodes) to apply via
        kg_query(mutate=true). The MCP layer proposes; the caller applies.
        """
        return prometheus_ingest_impl(topic, findings, synthesis, cycle_id, n)
