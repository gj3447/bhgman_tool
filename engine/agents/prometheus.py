"""프로메테우스(Prometheus) 실엔진 — 지식 선행 리서치.

본질 = 외부 지식을 먼저 훔쳐온다(획득). 실행형: 토픽을 N개 직교 sub-question으로 분해(plan)
→ N개 서브에이전트 병렬 리서치(재배맨 dispatch, web_search 서버툴) → 합성(consensus/
divergence/open-questions). LLM 오케스트레이션이라 결정론 엔진 불가 — Anthropic API 런타임 위.

graceful degrade: AgentClient가 키 부재면 AgentRuntimeUnavailable → CLI가 skill-route fallback.

# KG: prometheus-grounding-2026-05-05, bhgman-llm-commander-runtime-2026-05-28
"""

from __future__ import annotations

import os
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
# 자기일관성(self-consistency) 배심원(juror): K개 독립 샘플을 UNION-with-confidence 로 병합.
# 교집합(intersection) 아님 — 리서치는 recall 민감, rare-but-true 발견을 지우면 안 된다.
_JUROR_SYS = (
    "You merge K independent research samples for ONE sub-question into a single finding. "
    "List EVERY distinct claim that appears across the K samples (union, not intersection — "
    "never delete a claim just because only one sample made it). For each claim, tag its support "
    "count as s/K. Demote claims with support 1/K to 'low-confidence' but DO NOT delete them. "
    "Never report K-agreement as independent confirmation — same-model samples share correlated "
    "errors, so high s/K means 'consistent', not 'verified'. Keep sources. Be concise."
)


@dataclass(frozen=True)
class ResearchReport:
    topic: str
    n: int
    sub_questions: tuple[str, ...]
    findings: tuple[SubagentResult, ...]
    synthesis: str
    grounded_facts: int = 0  # KG 사전지식으로 접지된 정전·교훈·발견 수 (0 = 접지 없음/미가용)
    k: int = 1  # 축당 self-consistency 샘플 수 (1 = 오늘의 단일 greedy 경로)

    @property
    def summary(self) -> str:
        ok = sum(1 for f in self.findings if f.ok)
        g = f" grounded={self.grounded_facts}" if self.grounded_facts else " grounded=0"
        kpart = f" k={self.k}" if self.k > 1 else ""
        return (
            f"prometheus[{self.topic}]: planned={self.n} "
            f"researched_ok={ok}/{len(self.findings)}{g}{kpart}"
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


def _merge_axis_samples(
    topic: str,
    axes: list[str],
    grouped: list[list[SubagentResult]],
    client: AgentClient,
    *,
    k: int,
    grounding: str = "",
) -> list[SubagentResult]:
    """축별 K개 샘플 → 축당 1개 병합 결과. 배심원(juror) 출격은 ONE wave (N개 동시).

    UNION-with-confidence(교집합 아님). 배심원 실패 시 그 축의 가장 긴 ok 샘플로 fallback —
    절대 축을 드롭하지 않는다(실패 격리 + recall 보존).
    """
    juror_specs: list[SubagentSpec] = []
    for i, (axis, samples) in enumerate(zip(axes, grouped)):
        blocks = []
        for j, r in enumerate(samples):
            body = r.text if r.ok else f"(sample failed: {r.error})"
            blocks.append(f"### Sample {j + 1}/{k}\n{body}")
        user = (
            f"{grounding}Sub-question: {axis}\n(Parent topic: {topic})\n\n"
            f"{k} independent samples:\n\n" + "\n\n".join(blocks)
        )
        juror_specs.append(
            SubagentSpec(
                name=f"juror-{i + 1}",
                system=_JUROR_SYS,
                user=user,
                model=SYNTHESIS_MODEL,
                max_tokens=2048,
            )
        )
    verdicts = dispatch_parallel(juror_specs, client)
    merged: list[SubagentResult] = []
    for axis, samples, v in zip(axes, grouped, verdicts):
        if v.ok and v.text.strip():
            merged.append(SubagentResult(axis, True, v.text, "", v.completion))
            continue
        # fallback: 가장 긴 ok 샘플 (없으면 첫 샘플) — 축은 절대 드롭 안 함
        ok_samples = [s for s in samples if s.ok and s.text.strip()]
        if ok_samples:
            best = max(ok_samples, key=lambda s: len(s.text))
            merged.append(SubagentResult(axis, True, best.text, "", best.completion))
        else:
            merged.append(samples[0] if samples else SubagentResult(axis, False, "", "no samples"))
    return merged


def research(
    topic: str,
    n: int,
    client: AgentClient,
    *,
    subagent_model: str = SUBAGENT_MODEL,
    web_search: bool = True,
    max_tokens_per: int = 2048,
    grounding: GroundingSource | None = None,
    k: int = int(os.environ.get("BHGMAN_PROM_K", "1")),
    temperature: float = 0.7,
) -> ResearchReport:
    """plan → N 병렬 리서치 → 합성. PROPOSE only (KG write 없음; /prom 보고 구조 그대로).

    grounding = KG 접지원(LocalGroundingSource/Neo4jGroundingSource). 주면 LLM 호출 *전*
    하계에서 관련 정전·교훈·발견을 읽어 plan/subagent/synthesize prompt에 주입(KG-first Step 0).
    None이면 무접지(graceful) — 단 CLI 기본은 접지 ON.

    k = 축당 self-consistency 샘플 수. k=1(기본)은 오늘의 정확한 경로(축당 1 spec, juror 없음).
    k>1 이면 K×N specs 를 ONE dispatch_parallel 로 평탄화(배처가 K×N 동시 디코드를 봄) → 축별 배심원
    병합(UNION-with-confidence) → 병합 텍스트를 기존 synthesize() 에 투입.
    """
    # 로컬 백엔드(vLLM/DGX)면 web_search 강제 OFF — server-side tool 없음 / SearXNG ReAct는 직렬세금.
    web_search = web_search and not client.is_local()
    ctx, n_facts = build_grounding(
        grounding, topic, header="사전 지식 (이미 아는 것 — 재발견 금지)"
    )
    axes = plan_axes(topic, n, client, grounding=ctx)

    if k <= 1:
        # === 오늘의 정확한 경로 (zero regression) ===
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
        results = list(dispatch_parallel(specs, client))
    else:
        # === self-consistency K-샘플링: K×N 평탄화 1-wave ===
        specs = [
            SubagentSpec(
                name=f"axis-{i + 1}-s{j}",
                system=_RESEARCH_SYS,
                user=f"{ctx}Research question: {q}\n(Parent topic: {topic})",
                model=subagent_model,
                max_tokens=max_tokens_per,
                web_search=web_search,
                temperature=temperature,
                seed=j,
            )
            for i, q in enumerate(axes)
            for j in range(k)
        ]
        flat = dispatch_parallel(specs, client)
        # K개씩 축별로 재그룹화 (입력 순서 보존)
        grouped = [flat[i * k : (i + 1) * k] for i in range(len(axes))]
        results = _merge_axis_samples(
            topic, axes, grouped, client, k=k, grounding=ctx
        )

    synthesis = synthesize(topic, axes, results, client, grounding=ctx)
    return ResearchReport(
        topic=topic,
        n=len(axes),
        sub_questions=tuple(axes),
        findings=tuple(results),
        synthesis=synthesis,
        grounded_facts=n_facts,
        k=k,
    )


__all__ = ["ResearchReport", "plan_axes", "research", "synthesize"]
