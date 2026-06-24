"""프로메테우스(Prometheus) 실엔진 — 지식 선행 리서치.

본질 = 외부 지식을 먼저 훔쳐온다(획득). 실행형: 토픽을 N개 직교 sub-question으로 분해(plan)
→ N개 서브에이전트 병렬 리서치(재배맨 dispatch, web_search 서버툴) → 합성(consensus/
divergence/open-questions). LLM 오케스트레이션이라 결정론 엔진 불가 — Anthropic API 런타임 위.

graceful degrade: AgentClient가 키 부재면 AgentRuntimeUnavailable → CLI가 skill-route fallback.

# KG: prometheus-grounding-2026-05-05, bhgman-llm-commander-runtime-2026-05-28
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

from engine.agents import naesengmoon
from engine.agents.client import AgentClient
from engine.agents.dispatch import SubagentResult, SubagentSpec, dispatch_parallel
from engine.agents.agent_models import (
    LOCAL_BIG_TIER,
    LOCAL_FAST_TIER,
    SUBAGENT_MODEL,
    SYNTHESIS_MODEL,
)
from engine.agents.grounding import GroundingSource, build_grounding

# 하드 축 휴리스틱 — 추론/비교/증명류 키워드. tier-1(122B 디코릴레이터)로 라우팅.
_HARD_AXIS_RE = re.compile(r"\b(compare|prove|why|tradeoff|trade-off|derive)\b", re.IGNORECASE)

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
# L6: 재귀 트리 리서치. 답 + FOLLOWUPS(서버 tool-call parser qwen3_coder 로 강제, regex 아님).
_RESEARCH_TREE_SYS = (
    "You are a Prometheus research subagent in a recursive research tree. (1) Answer the assigned "
    "question concisely with sourced bullet points; cite a source per claim; flag uncertainty. "
    "(2) THEN decide whether your answer revealed deeper sub-questions that still need research. "
    "You MUST call the `emit_followups` tool exactly once: pass the list of follow-up sub-questions "
    "(at most {branch}, each a distinct, non-overlapping drill-down) your answer revealed are still "
    "needed, OR an EMPTY list if the question is fully resolved (a true leaf). Do not pad."
)
_FOLLOWUPS_TOOL = {
    "type": "function",
    "function": {
        "name": "emit_followups",
        "description": "Emit follow-up sub-questions revealed by your answer (empty list = leaf).",
        "parameters": {
            "type": "object",
            "properties": {
                "followups": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Follow-up sub-questions, or [] if fully resolved.",
                }
            },
            "required": ["followups"],
        },
    },
}
# 텍스트 fallback 파서 — 모델이 tool-call 대신 평문 `FOLLOWUPS:` 블록을 내면 관용 파싱.
_FOLLOWUPS_RE = re.compile(r"(?ims)^\s*FOLLOWUPS?\s*:\s*(.*?)\s*$")
_NODE_CTX_BUDGET = int(
    os.environ.get("BHGMAN_PROM_NODE_CTX", "6000")
)  # reduce 노드 children char 상한


@dataclass(frozen=True)
class ResearchReport:
    topic: str
    n: int
    sub_questions: tuple[str, ...]
    findings: tuple[SubagentResult, ...]
    synthesis: str
    grounded_facts: int = 0  # KG 사전지식으로 접지된 정전·교훈·발견 수 (0 = 접지 없음/미가용)
    k: int = 1  # 축당 self-consistency 샘플 수 (1 = 오늘의 단일 greedy 경로)
    verify_verdict: str = ""  # L5: naesengmoon critique 판정 (PASS/CONDITIONAL/FAIL; "" = 미실행)
    depth: int = 1  # L6: 재귀 트리 깊이 (1 = 오늘의 flat 경로)
    nodes: int = 0  # L6: 트리 노드 총수 (0 = flat)
    parse_ratio: str = ""  # L6: 레벨별 FOLLOWUPS 파싱 성공률 (silent depth-collapse 가시화)

    @property
    def summary(self) -> str:
        ok = sum(1 for f in self.findings if f.ok)
        g = f" grounded={self.grounded_facts}" if self.grounded_facts else " grounded=0"
        kpart = f" k={self.k}" if self.k > 1 else ""
        vpart = f" verify={self.verify_verdict}" if self.verify_verdict else ""
        dpart = f" depth={self.depth} nodes={self.nodes}" if self.depth > 1 else ""
        ppart = f" parse=[{self.parse_ratio}]" if self.parse_ratio else ""
        return (
            f"prometheus[{self.topic}]: planned={self.n} "
            f"researched_ok={ok}/{len(self.findings)}{g}{kpart}{vpart}{dpart}{ppart}"
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


def _complete_with_fallback(
    client: AgentClient,
    *,
    system: str,
    user: str,
    model: str,
    max_tokens: int,
    effort: str | None = None,
    tier: int | None = None,
):
    """tier 지정 호출 — 실패시 tier-0 로 재시도 (dead tier-1 은 degrade, never fail).

    synthesize/verify 처럼 single-point 호출의 fault-tolerance. tier=None(또는 0)이면
    그냥 단발 (오늘 동작). dispatch 와 달리 이 호출들은 격리망이 없어 명시적 try/fallback 필요.
    """
    try:
        return client.complete(
            system=system, user=user, model=model, max_tokens=max_tokens, effort=effort, tier=tier
        )
    except Exception:  # noqa: BLE001 — tier-1(122B) 죽으면 35B 로 graceful degrade
        if tier in (None, LOCAL_FAST_TIER):
            raise
        return client.complete(
            system=system,
            user=user,
            model=model,
            max_tokens=max_tokens,
            effort=effort,
            tier=LOCAL_FAST_TIER,
        )


def synthesize(
    topic: str,
    axes: list[str],
    results: list[SubagentResult],
    client: AgentClient,
    *,
    grounding: str = "",
    tier: int | None = None,
) -> str:
    blocks = []
    for q, r in zip(axes, results):
        body = r.text if r.ok else f"(subagent failed: {r.error})"
        blocks.append(f"### Sub-question: {q}\n{body}")
    user = (
        f"{grounding}Topic: {topic}\n\nFindings from {len(results)} subagents:\n\n"
        + "\n\n".join(blocks)
    )
    c = _complete_with_fallback(
        client,
        system=_SYNTH_SYS,
        user=user,
        model=SYNTHESIS_MODEL,
        max_tokens=4096,
        effort="high",
        tier=tier,
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


# ───────────────────────────── L6: 재귀 트리 리서치 ─────────────────────────────


@dataclass
class TreeNode:
    """리서치 트리 한 노드. depth>1 일 때만 쓰임 (depth=1 은 flat 경로, 트리 미사용)."""

    nid: str
    question: str
    answer: SubagentResult | None = None
    synthesis: str = ""  # reduce_tree 가 채움 (internal node 의 partial synthesis)
    children: list[TreeNode] | None = None

    def __post_init__(self) -> None:
        if self.children is None:
            self.children = []


def _parse_followups(comp, branch: int) -> tuple[list[str], bool]:
    """Completion → (followups, parsed_ok). tool-call 우선, 평문 FOLLOWUPS: fallback.

    parsed_ok=False = 구조 파싱 실패 → 'treat as leaf'(조용히 flat 으로 붕괴하지만 가시화됨).
    빈 followups 라도 명시적 leaf 선언(tool-call 성공)이면 parsed_ok=True.
    """
    import json as _json  # noqa: PLC0415

    if comp is None:
        return [], False
    # 1) tool-call (서버 --tool-call-parser qwen3_coder 가 emit_followups 를 구조화)
    for tc in getattr(comp, "tool_calls", ()) or ():
        if tc.get("name") == "emit_followups":
            try:
                args = _json.loads(tc.get("arguments") or "{}")
                fu = [str(x).strip() for x in (args.get("followups") or []) if str(x).strip()]
                return fu[:branch], True
            except (ValueError, TypeError):
                continue
    # 2) 평문 FOLLOWUPS: 블록 fallback (관용 — 모델이 tool-call 안 내고 텍스트로 낸 경우)
    text = getattr(comp, "text", "") or ""
    m = _FOLLOWUPS_RE.search(text)
    if m:
        tail = text[m.start() :]
        # 선행 리스트 마커(-, •, 1., 2)) 만 제거 — 끝의 숫자(q1, q2)는 보존
        lines = [
            re.sub(r"^[\s\-•*]*\d*[.)]?\s*", "", ln).strip()
            for ln in tail.splitlines()[1:]
            if ln.strip() and ln.strip().lower() not in ("none", "n/a")
        ]
        lines = [ln for ln in lines if ln]
        # 'FOLLOWUPS: none' 한 줄이면 leaf 선언으로 친다
        head = m.group(1).strip().lower()
        if head in ("none", "", "n/a"):
            return [], True
        return lines[:branch], True
    return [], False  # 구조 못 찾음 → leaf 취급 (parse miss)


def expand_tree(
    topic: str,
    root_questions: list[str],
    client: AgentClient,
    *,
    depth: int,
    branch: int,
    max_tokens_per: int,
    web_search: bool,
    ctx: str,
    parse_log: list[str],
) -> list[TreeNode]:
    """BFS 트리 확장. 레벨당 ONE dispatch_parallel. FOLLOWUPS = tool-call(qwen3_coder).

    parse_log 에 레벨별 'parsed/total' 비율을 적어 silent depth-collapse 를 가시화한다.
    각 노드 답변은 SubagentResult 로 보관, followups 가 다음 레벨 frontier 가 된다.
    """
    roots = [TreeNode(nid=f"n{i}", question=q) for i, q in enumerate(root_questions)]
    frontier = roots
    for d in range(depth):
        specs = [
            SubagentSpec(
                name=node.nid,
                system=_RESEARCH_TREE_SYS.format(branch=branch),
                user=f"{ctx}Research question: {node.question}\n(Parent topic: {topic})",
                model=SUBAGENT_MODEL,
                max_tokens=max_tokens_per,
                web_search=web_search,
                tools=(_FOLLOWUPS_TOOL,),
                tool_choice="auto",
            )
            for node in frontier
        ]
        results = dispatch_parallel(specs, client)
        next_frontier: list[TreeNode] = []
        parsed = 0
        for node, r in zip(frontier, results):
            node.answer = r
            if d == depth - 1:  # 마지막 레벨 = leaf, followups 무시
                continue
            fu, ok = _parse_followups(r.completion, branch)
            if ok:
                parsed += 1
            for j, q in enumerate(fu):
                child = TreeNode(nid=f"{node.nid}.{j}", question=q)
                node.children.append(child)
                next_frontier.append(child)
        if d < depth - 1:
            parse_log.append(f"L{d + 1}:{parsed}/{len(frontier)}")
        frontier = next_frontier
        if not frontier:  # 전 노드가 leaf → 조기 종료
            break
    return roots


def _truncate_children(text: str) -> str:
    """reduce 노드 children 컨텍스트 char 상한 — 넓은 레벨이 KV headroom 넘기지 않게."""
    if len(text) <= _NODE_CTX_BUDGET:
        return text
    return text[:_NODE_CTX_BUDGET] + "\n…(truncated for KV budget)"


def reduce_tree(
    topic: str,
    roots: list[TreeNode],
    client: AgentClient,
    *,
    ctx: str,
    root_tier: int | None = None,
) -> str:
    """bottom-up map-reduce 합성. 내부 노드 한 레벨 = ONE dispatch_parallel.

    leaf 답변 → 부모 reduce, 부모 partial → 조부모 reduce, … → 루트 합성(전체 forest).
    노드별 children char-budget 로 truncate. 루트 단일 합성은 root_tier(보통 122B)로.
    """
    # 노드를 depth 별로 모음 (가장 깊은 internal node 부터 reduce)
    levels: dict[int, list[TreeNode]] = {}

    def _walk(node: TreeNode, d: int) -> None:
        levels.setdefault(d, []).append(node)
        for c in node.children or []:
            _walk(c, d + 1)

    forest_root = TreeNode(nid="root", question=topic, children=list(roots))
    _walk(forest_root, 0)

    def _child_block(c: TreeNode) -> str:
        if c.synthesis:
            body = c.synthesis
        elif c.answer is not None and c.answer.ok:
            body = c.answer.text
        elif c.answer is not None:
            body = f"(failed: {c.answer.error})"
        else:
            body = "(no answer)"
        return f"### {c.question}\n{_truncate_children(body)}"

    # 깊은 internal level 부터 위로 (root level 0 은 마지막)
    for d in sorted(
        (dd for dd, nodes in levels.items() if any(n.children for n in nodes)), reverse=True
    ):
        internal = [n for n in levels[d] if n.children]
        if not internal:
            continue
        if d == 0:  # 루트 단일 합성 — root_tier(122B)로, fault-tolerant
            node = internal[0]
            user = (
                f"{ctx}Topic: {topic}\n\nPartial syntheses from {len(node.children)} clusters:\n\n"
                + "\n\n".join(_child_block(c) for c in node.children)
            )
            node.synthesis = _complete_with_fallback(
                client,
                system=_SYNTH_SYS,
                user=user,
                model=SYNTHESIS_MODEL,
                max_tokens=4096,
                effort="high",
                tier=root_tier,
            ).text
            continue
        specs = [
            SubagentSpec(
                name=node.nid,
                system=_SYNTH_SYS,
                user=(
                    f"{ctx}Sub-question: {node.question}\n(Parent topic: {topic})\n\n"
                    f"Findings from {len(node.children)} children:\n\n"
                    + "\n\n".join(_child_block(c) for c in node.children)
                ),
                model=SYNTHESIS_MODEL,
                max_tokens=2048,
            )
            for node in internal
        ]
        partials = dispatch_parallel(specs, client)
        for node, p in zip(internal, partials):
            node.synthesis = p.text if p.ok else f"(reduce failed: {p.error})"
    return forest_root.synthesis


def _tree_leaf_results(roots: list[TreeNode]) -> list[SubagentResult]:
    """트리의 모든 노드 답변을 flatten → ResearchReport.findings (summary 호환)."""
    out: list[SubagentResult] = []

    def _walk(node: TreeNode) -> None:
        if node.answer is not None:
            out.append(node.answer)
        for c in node.children or []:
            _walk(c)

    for r in roots:
        _walk(r)
    return out


def _all_questions(roots: list[TreeNode]) -> list[str]:
    qs: list[str] = []

    def _walk(node: TreeNode) -> None:
        qs.append(node.question)
        for c in node.children or []:
            _walk(c)

    for r in roots:
        _walk(r)
    return qs


def _axis_tier(axis: str, hard_axes: int, ranked_hard: set[str]) -> int:
    """축 → tier. hard_axes>0 이고 이 축이 hard 셋에 들면 tier-1(122B), 아니면 tier-0(35B)."""
    if hard_axes > 0 and axis in ranked_hard:
        return LOCAL_BIG_TIER
    return LOCAL_FAST_TIER


def _pick_hard_axes(axes: list[str], hard_axes: int) -> set[str]:
    """compare|prove|why|tradeoff|derive 키워드 가진 축 우선 → 상위 hard_axes 개."""
    if hard_axes <= 0:
        return set()
    scored = sorted(axes, key=lambda a: (bool(_HARD_AXIS_RE.search(a)), len(a)), reverse=True)
    return set(scored[:hard_axes])


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
    hard_axes: int = int(os.environ.get("BHGMAN_HARD_AXES", "0")),
    verify: bool = bool(os.environ.get("BHGMAN_PROM_VERIFY")),
    depth: int = int(os.environ.get("BHGMAN_PROM_DEPTH", "1")),
    branch: int = int(os.environ.get("BHGMAN_PROM_BRANCH", "3")),
) -> ResearchReport:
    """plan → 리서치 → 합성. PROPOSE only (KG write 없음; /prom 보고 구조 그대로).

    grounding = KG 접지원. None이면 무접지(graceful) — 단 CLI 기본은 접지 ON.

    k(L3) = 축당 self-consistency 샘플 수. k=1(기본)은 오늘의 정확한 경로.
    hard_axes(L4) = compare/prove/why/tradeoff/derive 휴리스틱으로 고른 상위 N개 축의 샘플을
        tier-1(122B 디코릴레이터)로 라우팅. 0(기본)이면 전부 tier-0(35B).
    verify(L5) = synth 후 naesengmoon.critique → FAIL/CONDITIONAL이면 ONE repair synth.
    depth(L6) = 재귀 트리 깊이. depth=1(기본)은 flat 경로(아래 가드). depth>1 이면 expand_tree +
        reduce_tree map-reduce 합성. 기본 상한 2.
    """
    # 로컬 백엔드(vLLM/DGX)면 web_search 강제 OFF — server-side tool 없음 / SearXNG ReAct는 직렬세금.
    web_search = web_search and not client.is_local()
    # tier-1(122B) 헬시 모델 구성됐는지 (없으면 verify/synth = same-model, 약한 디코릴레이션 솔직고지).
    tier1_ok = client.endpoint_for_tier(LOCAL_BIG_TIER) is not None
    synth_tier = LOCAL_BIG_TIER if tier1_ok else None
    depth = max(1, min(depth, 2))  # 기본 상한 2 (wall-time = 깊이에 선형)

    ctx, n_facts = build_grounding(
        grounding, topic, header="사전 지식 (이미 아는 것 — 재발견 금지)"
    )
    axes = plan_axes(topic, n, client, grounding=ctx)

    # ─── L6: 재귀 트리 경로 (depth>1) ───
    if depth > 1:
        parse_log: list[str] = []
        roots = expand_tree(
            topic,
            axes,
            client,
            depth=depth,
            branch=max(1, branch),
            max_tokens_per=max_tokens_per,
            web_search=web_search,
            ctx=ctx,
            parse_log=parse_log,
        )
        synthesis = reduce_tree(topic, roots, client, ctx=ctx, root_tier=synth_tier)
        flat_results = _tree_leaf_results(roots)
        all_qs = _all_questions(roots)
        verdict = ""
        if verify:
            synthesis, verdict = _verify_repair(
                topic, synthesis, axes, flat_results, client, ctx=ctx, synth_tier=synth_tier
            )
        return ResearchReport(
            topic=topic,
            n=len(axes),
            sub_questions=tuple(all_qs),
            findings=tuple(flat_results),
            synthesis=synthesis,
            grounded_facts=n_facts,
            k=k,
            verify_verdict=verdict,
            depth=depth,
            nodes=len(flat_results),
            parse_ratio=" ".join(parse_log),
        )

    # ─── flat 경로 (depth=1) ───
    ranked_hard = _pick_hard_axes(axes, hard_axes) if tier1_ok else set()

    if k <= 1:
        # === 오늘의 정확한 경로 (hard_axes=0 이면 tier 전부 0 → zero regression) ===
        specs = [
            SubagentSpec(
                name=f"axis-{i + 1}",
                system=_RESEARCH_SYS,
                user=f"{ctx}Research question: {q}\n(Parent topic: {topic})",
                model=subagent_model,
                max_tokens=max_tokens_per,
                web_search=web_search,
                tier=_axis_tier(q, hard_axes, ranked_hard),
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
                tier=_axis_tier(q, hard_axes, ranked_hard),
            )
            for i, q in enumerate(axes)
            for j in range(k)
        ]
        flat = dispatch_parallel(specs, client)
        # K개씩 축별로 재그룹화 (입력 순서 보존)
        grouped = [flat[i * k : (i + 1) * k] for i in range(len(axes))]
        results = _merge_axis_samples(topic, axes, grouped, client, k=k, grounding=ctx)

    synthesis = synthesize(topic, axes, results, client, grounding=ctx, tier=synth_tier)

    verdict = ""
    if verify:
        synthesis, verdict = _verify_repair(
            topic, synthesis, axes, results, client, ctx=ctx, synth_tier=synth_tier
        )

    return ResearchReport(
        topic=topic,
        n=len(axes),
        sub_questions=tuple(axes),
        findings=tuple(results),
        synthesis=synthesis,
        grounded_facts=n_facts,
        k=k,
        verify_verdict=verdict,
    )


def _verify_repair(
    topic: str,
    synthesis: str,
    axes: list[str],
    results: list[SubagentResult],
    client: AgentClient,
    *,
    ctx: str,
    synth_tier: int | None,
) -> tuple[str, str]:
    """L5: naesengmoon.critique → FAIL/CONDITIONAL이면 ONE repair synth (비평 첨부). (synthesis, verdict).

    critic 을 tier-1(122B)로 라우팅하면 cross-family = 진짜 디코릴레이션. tier-1 미구성이면
    same-model critic (약한 디코릴레이션) — naesengmoon 의 n_eff 가 이미 그걸 솔직히 보고함.
    """
    try:
        ev = naesengmoon.critique(topic, synthesis, client, model=SYNTHESIS_MODEL)
    except Exception as e:  # noqa: BLE001 — verify 실패해도 본 보고는 살린다
        return synthesis, f"ERROR({type(e).__name__})"
    verdict = ev.verdict
    if verdict in ("FAIL", "CONDITIONAL"):
        crit = "\n".join(f"[{lv.lens}:{lv.verdict}] {lv.findings}" for lv in ev.lens_verdicts)
        blocks = []
        for q, r in zip(axes, results):
            body = r.text if r.ok else f"(subagent failed: {r.error})"
            blocks.append(f"### Sub-question: {q}\n{body}")
        user = (
            f"{ctx}Topic: {topic}\n\nYour prior synthesis:\n{synthesis}\n\n"
            f"An adversarial critic raised these concerns (verdict={verdict}):\n{crit}\n\n"
            f"Original findings:\n\n" + "\n\n".join(blocks) + "\n\n"
            "Revise the synthesis to address EVERY nameable concern. Keep the three headers "
            "(## Consensus / ## Divergence / ## Open Questions). Do not over-claim; hedge honestly."
        )
        repaired = _complete_with_fallback(
            client,
            system=_SYNTH_SYS,
            user=user,
            model=SYNTHESIS_MODEL,
            max_tokens=4096,
            effort="high",
            tier=synth_tier,
        )
        return repaired.text, verdict
    return synthesis, verdict


__all__ = [
    "ResearchReport",
    "TreeNode",
    "expand_tree",
    "plan_axes",
    "reduce_tree",
    "research",
    "synthesize",
]
