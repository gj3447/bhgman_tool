"""하네스(Harness) 진단 모델 — 3계층 + 4축. 결정론 value objects.

canon (harness v3 정정본): 4축(Inform/Constrain/Verify/Correct)은 *각 instance 내부* 조직
원리이지 family 정의가 아니다. 3계층은 *결정/컴포넌트가 어디 사는지*. MCP = 어댑터.
하네스=하데스 동일존재의 *수동 場/scaffold 측면* = 이 진단 (능동 동사 '실현'은 engine/hades).

# KG: ATOM_Skill_harness, lesson-harness-drift-corrected-2026-04-29,
#     bhgman-harness-diagnose-engine-2026-05-28
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Tier(str, Enum):
    """3계층 — 결정/컴포넌트가 사는 층."""

    IDE_HOST = "IDE_HOST"  # Cursor / Claude Code / Aider / Copilot — 편집기-호스트
    RUNTIME = "RUNTIME"  # LangGraph / CrewAI / AutoGen / ADK — application orchestration
    MANAGED_CLOUD = (
        "MANAGED_CLOUD"  # Managed Agents / OpenAI Assistants / Vertex — 호스티드 control plane
    )
    UNKNOWN = "UNKNOWN"


class Axis(str, Enum):
    """4축 — instance 내부 조직 원리 (구조가 에이전트를 제약한다)."""

    INFORM = "INFORM"  # 컨텍스트 주입 (prompt/RAG/memory/role)
    CONSTRAIN = "CONSTRAIN"  # 행동 제약 (gate/guardrail/state-machine/schema/policy)
    VERIFY = "VERIFY"  # 검증 (test/eval/critic/oracle/assert)
    CORRECT = "CORRECT"  # 교정 (retry/feedback/self-correct/rollback)


class Presence(str, Enum):
    PRESENT = "PRESENT"  # 신호 있음
    UNKNOWN = "UNKNOWN"  # 신호 없음 (부재 ≠ 능력 없음 — 정직)


class Confidence(str, Enum):
    HIGH = "HIGH"  # 알려진 프레임워크 이름 매치
    MEDIUM = "MEDIUM"  # 키워드 휴리스틱
    LOW = "LOW"  # 미상


@dataclass(frozen=True)
class AxisFinding:
    axis: Axis
    presence: Presence
    signal: str = ""  # 무슨 신호로 판정했는지 (provenance)


@dataclass(frozen=True)
class HarnessDiagnosis:
    """진단 결과. tier(어디 사나) + 4축 프로필(내부 조직) + MCP 어댑터."""

    subject: str
    tier: Tier
    tier_confidence: Confidence
    tier_reason: str
    axes: tuple[AxisFinding, ...]
    mcp_adapter: bool = False
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def present_axes(self) -> tuple[Axis, ...]:
        return tuple(f.axis for f in self.axes if f.presence is Presence.PRESENT)

    @property
    def summary(self) -> str:
        axes = "/".join(a.value[0] for a in self.present_axes) or "none-detected"
        mcp = " +MCP" if self.mcp_adapter else ""
        return (
            f"harness[{self.subject}]: tier={self.tier.value}({self.tier_confidence.value}) "
            f"axes={axes}{mcp}"
        )


__all__ = ["Axis", "AxisFinding", "Confidence", "HarnessDiagnosis", "Presence", "Tier"]
