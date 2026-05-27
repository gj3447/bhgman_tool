"""하네스 진단 코어 — 결정론. agent/framework/instance를 3계층+4축으로 분류.

순수 함수, 인프라 0. 두 신호원:
  ① KNOWN_FRAMEWORKS — 이름 매치(HIGH) + 그 프레임워크가 *primitive를 제공하는* 축.
  ② 키워드 신호 추출 — 미상 subject의 free-text에서 tier/축 신호 탐지(MEDIUM).
호출자가 explicit signals dict 주면 그게 우선(override).

정직: 축 부재는 Presence.UNKNOWN (부재 ≠ 능력 없음). **KNOWN_FRAMEWORKS의 framework→축 매핑은
*주관적 휴리스틱 KB*(외부 인용 미첨부, 빌더 단정) — falsifiable 외형이나 매핑 자체는 미검증.**
신호 추출(키워드 매칭)은 결정론이지만 그 키워드 집합도 휴리스틱. tier 분류(이름 매치)가 가장
근거 강함. 나생문 AC-bhgman-harness-4axis-subjective (2026-05-28) 반영.

# KG: ATOM_Skill_harness, lesson-harness-drift-corrected-2026-04-29,
#     bhgman-harness-diagnose-engine-2026-05-28
"""

from __future__ import annotations

from harness_models import (
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
    "aider": (Tier.IDE_HOST, (Axis.INFORM,)),
    "copilot": (Tier.IDE_HOST, (Axis.INFORM,)),
    "windsurf": (Tier.IDE_HOST, (Axis.INFORM,)),
    "continue": (Tier.IDE_HOST, (Axis.INFORM,)),
    "zed": (Tier.IDE_HOST, (Axis.INFORM,)),
    "langgraph": (Tier.RUNTIME, (Axis.CONSTRAIN, Axis.VERIFY)),  # graph state-machine + checkpoint
    "crewai": (Tier.RUNTIME, (Axis.INFORM, Axis.CORRECT)),  # roles + delegation
    "autogen": (Tier.RUNTIME, (Axis.INFORM, Axis.CORRECT)),  # conversational + reflection
    "google adk": (Tier.RUNTIME, (Axis.CONSTRAIN,)),
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

# tier 키워드 휴리스틱 (이름 매치 실패 시). 순서 = 우선순위.
_TIER_KEYWORDS: tuple[tuple[Tier, tuple[str, ...]], ...] = (
    (Tier.IDE_HOST, ("ide", "editor", "plugin", "extension", "vscode", "jetbrains")),
    (Tier.MANAGED_CLOUD, ("managed", "hosted", "serverless", "control plane", "assistants api")),
    (Tier.RUNTIME, ("framework", "orchestrat", "graph", "workflow", "library", "sdk", "runtime")),
)

# 축 신호 키워드 (free-text 추출).
_AXIS_KEYWORDS: dict[Axis, tuple[str, ...]] = {
    Axis.INFORM: ("context", "inject", "rag", "retriev", "memory", "prompt", "role", "embedding"),
    Axis.CONSTRAIN: (
        "gate",
        "guardrail",
        "state machine",
        "state-machine",
        "schema",
        "valid",
        "policy",
        "permission",
        "constrain",
        "hook",
    ),
    Axis.VERIFY: ("test", "eval", "verif", "assert", "critic", "oracle", "lint"),
    Axis.CORRECT: (
        "retry",
        "feedback",
        "self-correct",
        "self correct",
        "repair",
        "rollback",
        "reflect",
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
    """축 PRESENT 판정. 우선순위: explicit signal > known primitive > 키워드. 없으면 UNKNOWN."""
    if signals is not None and axis.value.lower() in signals:
        present = signals[axis.value.lower()]
        return AxisFinding(
            axis, Presence.PRESENT if present else Presence.UNKNOWN, "explicit signal"
        )
    if axis in primitives:
        return AxisFinding(axis, Presence.PRESENT, "framework primitive")
    hit = next((k for k in _AXIS_KEYWORDS[axis] if k in text), None)
    if hit:
        return AxisFinding(axis, Presence.PRESENT, f"keyword '{hit}'")
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
        "h.mcpAdapter=$mcp, h.diagnosedAt=datetime(), h.diagnosedBy='harness' "
        "RETURN h.name AS diagnosed"
    )
    params = {
        "subject": diag.subject,
        "tier": diag.tier.value,
        "conf": diag.tier_confidence.value,
        "axes": [a.value for a in diag.present_axes],
        "mcp": diag.mcp_adapter,
    }
    return cypher, params


__all__ = ["KNOWN_FRAMEWORKS", "build_diagnosis_cypher", "diagnose"]
