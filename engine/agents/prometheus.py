"""프로메테우스(Prometheus) 실엔진 — 지식 선행 리서치.

본질 = 외부 지식을 먼저 훔쳐온다(획득). 실행형: 토픽을 N개 직교 sub-question으로 분해(plan)
→ N개 서브에이전트 병렬 리서치(재배맨 dispatch, web_search 서버툴) → 합성(consensus/
divergence/open-questions). LLM 오케스트레이션이라 결정론 엔진 불가 — Anthropic API 런타임 위.

graceful degrade: AgentClient가 키 부재면 AgentRuntimeUnavailable → CLI가 skill-route fallback.

# KG: prometheus-grounding-2026-05-05, bhgman-llm-commander-runtime-2026-05-28
"""

from __future__ import annotations

from dataclasses import dataclass

from engine.agents.client import AgentClient
from engine.agents.dispatch import SubagentResult, SubagentSpec, dispatch_parallel
from engine.agents.agent_models import SUBAGENT_MODEL, SYNTHESIS_MODEL
from engine.agents.grounding import GroundingSource, build_grounding

_PLAN_SYS = (
    "You are Prometheus, a research planner. Decompose the topic into exactly N distinct, "
    "non-overlapping research sub-questions that together cover it. Output ONLY the sub-questions, "
    "one per line, no numbering, no preamble, no commentary."
)
_RESEARCH_SYS = (
    "You are a Prometheus research subagent. Use web search to gather current, sourced knowledge "
    "on the assigned question. Report concise findings as bullet points; cite a source for each "
    "claim. Explicitly flag uncertainty and gaps. Do not pad."
)
_SYNTH_SYS = (
    "You are Prometheus synthesizing N subagent findings. Produce three sections with these exact "
    "headers:\n## Consensus\n## Divergence\n## Open Questions\n"
    "Under Consensus list claims supported across findings; Divergence lists conflicts; "
    "Open Questions lists what remains unresolved. Be evidence-bound; do not invent agreement."
)


@dataclass(frozen=True)
class ResearchReport:
    topic: str
    n: int
    sub_questions: tuple[str, ...]
    findings: tuple[SubagentResult, ...]
    synthesis: str
    grounded_facts: int = 0  # KG 사전지식으로 접지된 정전·교훈·발견 수 (0 = 접지 없음/미가용)

    @property
    def summary(self) -> str:
        ok = sum(1 for f in self.findings if f.ok)
        g = f" grounded={self.grounded_facts}" if self.grounded_facts else " grounded=0"
        return (
            f"prometheus[{self.topic}]: planned={self.n} "
            f"researched_ok={ok}/{len(self.findings)}{g}"
        )


def plan_axes(topic: str, n: int, client: AgentClient, *, grounding: str = "") -> list[str]:
    """토픽 → N개 sub-question. 실패/부족 시 토픽 자체로 fallback. grounding = KG 사전지식 블록."""
    c = client.complete(
        system=_PLAN_SYS,
        user=f"{grounding}Topic: {topic}\nN = {n}",
        model=SYNTHESIS_MODEL,
        max_tokens=1024,
        effort="low",
    )
    lines = [ln.strip(" -•\t0123456789.") for ln in c.text.splitlines() if ln.strip()]
    return lines[:n] or [topic]


def synthesize(
    topic: str,
    axes: list[str],
    results: list[SubagentResult],
    client: AgentClient,
    *,
    grounding: str = "",
) -> str:
    blocks = []
    for q, r in zip(axes, results):
        body = r.text if r.ok else f"(subagent failed: {r.error})"
        blocks.append(f"### Sub-question: {q}\n{body}")
    user = (
        f"{grounding}Topic: {topic}\n\nFindings from {len(results)} subagents:\n\n"
        + "\n\n".join(blocks)
    )
    c = client.complete(
        system=_SYNTH_SYS, user=user, model=SYNTHESIS_MODEL, max_tokens=4096, effort="high"
    )
    return c.text


def research(
    topic: str,
    n: int,
    client: AgentClient,
    *,
    subagent_model: str = SUBAGENT_MODEL,
    web_search: bool = True,
    max_tokens_per: int = 2048,
    grounding: GroundingSource | None = None,
) -> ResearchReport:
    """plan → N 병렬 리서치 → 합성. PROPOSE only (KG write 없음; /prom 보고 구조 그대로).

    grounding = KG 접지원(LocalGroundingSource/Neo4jGroundingSource). 주면 LLM 호출 *전*
    하계에서 관련 정전·교훈·발견을 읽어 plan/subagent/synthesize prompt에 주입(KG-first Step 0).
    None이면 무접지(graceful) — 단 CLI 기본은 접지 ON.
    """
    ctx, n_facts = build_grounding(
        grounding, topic, header="사전 지식 (이미 아는 것 — 재발견 금지)"
    )
    axes = plan_axes(topic, n, client, grounding=ctx)
    specs = [
        SubagentSpec(
            name=f"axis-{i + 1}",
            system=_RESEARCH_SYS,
            user=f"{ctx}Research question: {q}\n(Parent topic: {topic})",
            model=subagent_model,
            max_tokens=max_tokens_per,
            web_search=web_search,
        )
        for i, q in enumerate(axes)
    ]
    results = dispatch_parallel(specs, client)
    synthesis = synthesize(topic, axes, results, client, grounding=ctx)
    return ResearchReport(
        topic=topic,
        n=len(axes),
        sub_questions=tuple(axes),
        findings=tuple(results),
        synthesis=synthesis,
        grounded_facts=n_facts,
    )


__all__ = ["ResearchReport", "plan_axes", "research", "synthesize"]
