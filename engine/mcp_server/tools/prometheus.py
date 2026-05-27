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


def register(mcp: Any) -> None:
    """Attach `prometheus_research` tool to the FastMCP instance."""

    @mcp.tool()
    def prometheus_research(topic: str, n: int = 0) -> dict[str, Any]:
        """Knowledge-first 연구 계획 (프로메테우스, 획득). 행동 전 지식 선행.

        Args:
            topic: 연구 주제
            n: subagent 수 (0=auto_estimate)

        Returns: ResearchPlan dict (n, strategy, matrix, kg_first 지령).
        """
        return prometheus_research_impl(topic, n)
