"""하네스 진단 코어 — 결정론. agent/framework/instance를 3계층+4축으로 분류.

순수 함수, 인프라 0. 두 신호원:
  ① KNOWN_FRAMEWORKS — 이름 매치(HIGH) + 그 프레임워크가 *primitive를 제공하는* 축.
  ② 키워드 신호 추출 — 미상 subject의 free-text에서 tier/축 신호 탐지(MEDIUM).
호출자가 explicit signals dict 주면 그게 우선(override).

정직: 축 부재는 Presence.UNKNOWN (부재 ≠ 능력 없음). **KNOWN_FRAMEWORKS의 framework→축 매핑은
여전히 빌더의 *해석*이지만, 각 entry는 FRAMEWORK_CITATIONS dict를 통해 1차 source URL과
1:1 binding됨 (2026-05-28 external grounding pass).** Citation은 framework의 *existence* +
*advertised capability*를 근거 짓는다. axis 할당 (예: LangGraph→CONSTRAIN+VERIFY)은 여전히
1차 source 측 docs를 빌더가 4축 schema로 해석한 결과이므로, "근거 강도 + 해석 layer 1단"으로
명시. 사용자 반박 가능. tier 분류(이름 매치)가 여전히 가장 근거 강함.

# KG: ATOM_Skill_harness, lesson-harness-drift-corrected-2026-04-29,
#     bhgman-harness-diagnose-engine-2026-05-28,
#     lesson-harness-citation-drift-bockeler-2026-04-30 (Böckeler citation 본 KB 측 미사용 — drift 회피)
"""

from __future__ import annotations

from engine.harness.harness_models import (
    Axis,
    AxisFinding,
    Confidence,
    HarnessDiagnosis,
    Presence,
    Tier,
)

# (이름 substring) → (Tier, 그 도구가 primitive를 제공하는 축들). 축 = falsifiable 원시기능 보유.
KNOWN_FRAMEWORKS: dict[str, tuple[Tier, tuple[Axis, ...]]] = {
    "claude code": (Tier.IDE_HOST, (Axis.CONSTRAIN, Axis.VERIFY)),  # hooks + 테스트 게이트
    "cursor": (Tier.IDE_HOST, (Axis.INFORM,)),
    "aider": (
        Tier.IDE_HOST,
        (Axis.INFORM, Axis.VERIFY, Axis.CORRECT),
    ),  # repo-map / auto-test·lint / diff·reflection
    "copilot": (Tier.IDE_HOST, (Axis.INFORM,)),
    "windsurf": (Tier.IDE_HOST, (Axis.INFORM,)),
    "continue": (Tier.IDE_HOST, (Axis.INFORM,)),
    "zed": (Tier.IDE_HOST, (Axis.INFORM,)),
    # ── 2026-06-27 OSS 코딩-하네스 확장 (coding-harness-deepdive §4 근거; 축=deepdive 증거,
    #    citation=repo 1차 source. 정밀 citation 재검증은 grounding-pass 대상). ──
    "swe-agent": (
        Tier.IDE_HOST,
        (Axis.CONSTRAIN, Axis.VERIFY),
    ),  # ACI + bash/test 게이트 (mini-swe-agent 포함)
    "openhands": (
        Tier.IDE_HOST,
        (Axis.INFORM, Axis.CONSTRAIN, Axis.VERIFY, Axis.CORRECT),
    ),  # condenser/sandbox/test/reflection
    "cline": (
        Tier.IDE_HOST,
        (Axis.INFORM, Axis.CONSTRAIN, Axis.CORRECT),
    ),  # context/Plan-Act 승인/checkpoint
    "opencode": (
        Tier.IDE_HOST,
        (Axis.CONSTRAIN, Axis.VERIFY, Axis.CORRECT),
    ),  # findLast 권한/LSP/9단 폴백 edit
    "goose": (Tier.IDE_HOST, (Axis.CONSTRAIN, Axis.CORRECT)),  # extension 권한/edit
    "codex": (Tier.IDE_HOST, (Axis.CONSTRAIN, Axis.CORRECT)),  # OpenAI Codex CLI 샌드박스/edit
    "gemini cli": (Tier.IDE_HOST, (Axis.INFORM, Axis.CORRECT)),  # 1M 컨텍스트/edit
    "crush": (Tier.IDE_HOST, (Axis.CONSTRAIN, Axis.CORRECT)),  # Charm TUI 권한/edit
    "langgraph": (Tier.RUNTIME, (Axis.CONSTRAIN, Axis.VERIFY)),  # graph state-machine + checkpoint
    "crewai": (Tier.RUNTIME, (Axis.INFORM, Axis.CORRECT)),  # roles + delegation
    "autogen": (Tier.RUNTIME, (Axis.INFORM, Axis.CORRECT)),  # conversational + reflection
    "google adk": (Tier.RUNTIME, (Axis.CONSTRAIN,)),
    # 통합 registry 마이그레이션 2026-06-27: 구 KNOWN_INSTANCES(facade)에만 있던 L_RT 형제.
    # 축=미상(정직: 부재≠능력없음) — 축 부여는 OSS 확장 패스(item 3)에서 deepdive 근거로.
    "claude-flow": (Tier.RUNTIME, ()),  # ruvnet/claude-flow (harness.md L_RT 형제)
    "ruflo": (Tier.RUNTIME, ()),  # claude-flow 별칭(ruflo)
    # ── 2026-06-27 OSS L_RT 프레임워크 확장 (survey §3 + deepdive 근거축). ──
    "openai agents sdk": (Tier.RUNTIME, (Axis.CONSTRAIN,)),  # Runner agent-loop + guardrails
    "smolagents": (Tier.RUNTIME, (Axis.CONSTRAIN,)),  # CodeAgent code-action
    "vercel ai": (Tier.RUNTIME, (Axis.CONSTRAIN, Axis.CORRECT)),  # stopWhen + tool loop
    "mastra": (Tier.RUNTIME, (Axis.CONSTRAIN, Axis.CORRECT)),  # durable workflow suspend/resume
    "letta": (Tier.RUNTIME, (Axis.INFORM,)),  # tiered memory (MemGPT)
    "agno": (Tier.RUNTIME, (Axis.INFORM,)),  # AgentOS memory/runtime
    "microsoft agent framework": (Tier.RUNTIME, (Axis.CONSTRAIN, Axis.VERIFY)),  # AutoGen+SK 통합
    "strands": (Tier.RUNTIME, (Axis.CONSTRAIN,)),  # AWS harness-sdk
    "langchain": (Tier.RUNTIME, (Axis.INFORM,)),
    "llamaindex": (Tier.RUNTIME, (Axis.INFORM,)),  # retrieval
    "dspy": (Tier.RUNTIME, (Axis.VERIFY, Axis.CORRECT)),  # optimizer/metric
    "semantic kernel": (Tier.RUNTIME, (Axis.INFORM,)),
    "pydantic-ai": (Tier.RUNTIME, (Axis.CONSTRAIN, Axis.VERIFY)),  # schema 검증
    "pydantic ai": (Tier.RUNTIME, (Axis.CONSTRAIN, Axis.VERIFY)),
    "managed agent": (
        Tier.MANAGED_CLOUD,
        (Axis.CONSTRAIN, Axis.VERIFY),
    ),  # permission policy + outcome
    "openai assistant": (Tier.MANAGED_CLOUD, (Axis.INFORM,)),
    "vertex ai agent": (Tier.MANAGED_CLOUD, ()),
    "bedrock agent": (Tier.MANAGED_CLOUD, ()),
    "azure ai agent": (Tier.MANAGED_CLOUD, ()),
}

# External grounding: 각 framework 측 1차 source URL. axis 할당은 여전히 빌더 해석이지만,
# entry의 existence + advertised capability는 이 URL로 근거. 2026-05-28 external grounding pass
# (vp-harness-external-grounding 측 응답). 미상 framework는 KNOWN_FRAMEWORKS에 없음 (정직).
FRAMEWORK_CITATIONS: dict[str, str] = {
    "claude code": "https://docs.anthropic.com/en/docs/claude-code/hooks",
    "cursor": "https://docs.cursor.com",
    "aider": "https://aider.chat",
    "copilot": "https://docs.github.com/en/copilot",
    "windsurf": "https://docs.codeium.com/windsurf",
    "continue": "https://docs.continue.dev",
    "zed": "https://zed.dev/docs",
    "swe-agent": "https://github.com/SWE-agent/SWE-agent",
    "openhands": "https://github.com/OpenHands/OpenHands",
    "cline": "https://github.com/cline/cline",
    "opencode": "https://github.com/anomalyco/opencode",
    "goose": "https://github.com/aaif-goose/goose",
    "codex": "https://github.com/openai/codex",
    "gemini cli": "https://github.com/google-gemini/gemini-cli",
    "crush": "https://github.com/charmbracelet/crush",
    "langgraph": "https://langchain-ai.github.io/langgraph/",
    "crewai": "https://docs.crewai.com",
    "autogen": "https://microsoft.github.io/autogen/",
    "google adk": "https://google.github.io/adk-docs/",
    "claude-flow": "https://github.com/ruvnet/claude-flow",
    "ruflo": "https://github.com/ruvnet/claude-flow",
    "openai agents sdk": "https://github.com/openai/openai-agents-python",
    "smolagents": "https://github.com/huggingface/smolagents",
    "vercel ai": "https://github.com/vercel/ai",
    "mastra": "https://github.com/mastra-ai/mastra",
    "letta": "https://github.com/letta-ai/letta",
    "agno": "https://github.com/agno-agi/agno",
    "microsoft agent framework": "https://github.com/microsoft/agent-framework",
    "strands": "https://github.com/strands-agents/harness-sdk",
    "langchain": "https://python.langchain.com/docs/",
    "llamaindex": "https://docs.llamaindex.ai",
    "dspy": "https://dspy.ai",
    "semantic kernel": "https://learn.microsoft.com/en-us/semantic-kernel/",
    "pydantic-ai": "https://ai.pydantic.dev",
    "pydantic ai": "https://ai.pydantic.dev",
    "managed agent": "https://docs.anthropic.com/en/docs/agents-and-tools",
    "openai assistant": "https://platform.openai.com/docs/assistants/overview",
    "vertex ai agent": "https://cloud.google.com/vertex-ai/generative-ai/docs/agent-builder/overview",
    "bedrock agent": "https://docs.aws.amazon.com/bedrock/latest/userguide/agents.html",
    "azure ai agent": "https://learn.microsoft.com/en-us/azure/ai-services/agents/overview",
}


def primary_source(framework_name: str) -> str | None:
    """Framework 측 1차 source URL 반환 (소문자 이름 매치). 미상이면 None."""
    return FRAMEWORK_CITATIONS.get(framework_name.lower())


# tier 키워드 휴리스틱 (이름 매치 실패 시). 순서 = 우선순위.
_TIER_KEYWORDS: tuple[tuple[Tier, tuple[str, ...]], ...] = (
    (Tier.IDE_HOST, ("ide", "editor", "plugin", "extension", "vscode", "jetbrains")),
    (Tier.MANAGED_CLOUD, ("managed", "hosted", "serverless", "control plane", "assistants api")),
    (Tier.RUNTIME, ("framework", "orchestrat", "graph", "workflow", "library", "sdk", "runtime")),
)

# 4축 falsifiable feature 신호 — coding-harness-deepdive §1/§3.1 의 "보편 9부품"을 축별 신호로.
# 각 신호 = (component 이름, 그 부품을 가리키는 free-text 키워드). text 매치 시 INFERRED(약 신호),
# AxisFinding.signal 에 어느 부품이 근거인지 provenance 로 박는다 (단정 → 관찰 가능 구조신호).
# 9부품 → 축 매핑: system-prompt/context-mgmt/repo-map→Inform, tool-ACI/sandbox/permission/
# termination→Constrain, verify-feedback→Verify, edit-apply/reflection/checkpoint→Correct.
_FEATURE_SIGNALS: dict[Axis, tuple[tuple[str, tuple[str, ...]], ...]] = {
    Axis.INFORM: (
        ("system-prompt", ("system prompt", "instruction")),
        (
            "context-management",
            ("context", "compaction", "summariz", "memory", "subagent", "sub-agent"),
        ),
        ("repo-map", ("repo map", "repomap", "retriev", "rag", "embedding", "index")),
        ("role-prompt", ("role", "persona", "inject", "prompt")),
    ),
    Axis.CONSTRAIN: (
        ("tool-aci", ("aci", "tool schema", "tool definition", "function call", "function-call")),
        ("sandbox", ("sandbox", "container", "docker", "isolat")),
        (
            "permission",
            ("permission", "allow", "deny", "approve", "guardrail", "policy", "gate", "hook"),
        ),
        (
            "termination",
            ("step limit", "budget", "max turns", "max-iter", "timeout", "wall-time", "wall time"),
        ),
        ("state-machine", ("state machine", "state-machine", "schema", "valid", "constrain")),
    ),
    Axis.VERIFY: (
        ("test-feedback", ("test", "eval", "assert")),
        ("static-analysis", ("lint", "lsp", "type check", "typecheck", "formatter", "diagnostic")),
        ("critic-oracle", ("critic", "review", "oracle", "verif")),
    ),
    Axis.CORRECT: (
        ("edit-apply", ("edit", "diff", "search-replace", "search/replace", "patch", "fuzzy")),
        ("reflection", ("reflect", "self-correct", "self correct", "feedback")),
        ("retry", ("retry", "repair", "rollback")),
        ("checkpoint", ("checkpoint", "snapshot", "resume")),
    ),
}


def _classify_tier(text: str) -> tuple[Tier, Confidence, str, tuple[Axis, ...]]:
    """이름 매치(HIGH) → 키워드(MEDIUM) → UNKNOWN(LOW). primitive 축도 반환."""
    for name, (tier, axes) in KNOWN_FRAMEWORKS.items():
        if name in text:
            return tier, Confidence.HIGH, f"known framework '{name}'", axes
    for tier, keywords in _TIER_KEYWORDS:
        hit = next((k for k in keywords if k in text), None)
        if hit:
            return tier, Confidence.MEDIUM, f"keyword '{hit}'", ()
    return Tier.UNKNOWN, Confidence.LOW, "no name/keyword match", ()


def _axis_finding(
    axis: Axis, text: str, primitives: tuple[Axis, ...], signals: dict[str, bool] | None
) -> AxisFinding:
    """축 판정. 우선순위: explicit signal(PRESENT) > framework primitive(PRESENT)
    > feature 추론(INFERRED, 9부품 provenance). 없으면 UNKNOWN.

    PRESENT=강신호(반박 어려움), INFERRED=약신호(free-text feature 추론, 반박 가능).
    """
    if signals is not None and axis.value.lower() in signals:
        present = signals[axis.value.lower()]
        return AxisFinding(
            axis, Presence.PRESENT if present else Presence.UNKNOWN, "explicit signal"
        )
    if axis in primitives:
        return AxisFinding(axis, Presence.PRESENT, "framework primitive")
    for component, keywords in _FEATURE_SIGNALS[axis]:
        hit = next((k for k in keywords if k in text), None)
        if hit:
            return AxisFinding(axis, Presence.INFERRED, f"feature '{component}' (keyword '{hit}')")
    return AxisFinding(axis, Presence.UNKNOWN, "no signal")


def diagnose(subject: str, signals: dict[str, bool] | None = None) -> HarnessDiagnosis:
    """subject(프레임워크명 또는 free-text 설명)를 3계층+4축으로 진단. 결정론."""
    text = subject.lower()
    tier, conf, reason, primitives = _classify_tier(text)
    axes = tuple(_axis_finding(ax, text, primitives, signals) for ax in Axis)
    mcp = "mcp" in text or bool((signals or {}).get("mcp", False))
    notes = (
        "4축=instance 내부 조직원리(family 정의 아님), 3계층=결정이 사는 곳 (harness v3).",
        "축 부재=UNKNOWN(능력 없음 아님). MCP=계층 간 어댑터.",
        "framework→축 매핑은 주관적 휴리스틱 KB(미검증 단정). tier(이름매치)가 근거 가장 강함.",
    )
    return HarnessDiagnosis(
        subject=subject,
        tier=tier,
        tier_confidence=conf,
        tier_reason=reason,
        axes=axes,
        mcp_adapter=mcp,
        notes=notes,
    )


def build_diagnosis_cypher(diag: HarnessDiagnosis) -> tuple[str, dict]:
    """진단을 KG에 persist하는 cypher+params (순수 — 실행은 호출자 주입 runner).

    occam/hades와 동일 패턴: 코어는 인프라 0, --apply 시에만 KG(local file 또는 neo4j) 기록.
    """
    cypher = (
        "MERGE (h:HarnessDiagnosis {name: $subject}) "
        "SET h.tier=$tier, h.tierConfidence=$conf, h.presentAxes=$axes, "
        "h.inferredAxes=$inferred, "
        "h.mcpAdapter=$mcp, h.diagnosedAt=datetime(), h.diagnosedBy='harness' "
        "RETURN h.name AS diagnosed"
    )
    params = {
        "subject": diag.subject,
        "tier": diag.tier.value,
        "conf": diag.tier_confidence.value,
        "axes": [a.value for a in diag.present_axes],  # 강신호 (primitive/explicit)
        "inferred": [a.value for a in diag.inferred_axes],  # 약신호 (feature 추론)
        "mcp": diag.mcp_adapter,
    }
    return cypher, params


__all__ = ["KNOWN_FRAMEWORKS", "build_diagnosis_cypher", "diagnose"]
