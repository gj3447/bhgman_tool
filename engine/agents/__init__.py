"""engine.agents — Anthropic API 기반 에이전트 런타임 + 3 LLM 군단장.

결정론 엔진(occam/eureka/hades/longinus)과 달리, 이 셋은 LLM 오케스트레이션이라 API 런타임 위:
  - 재배맨 (dispatch)    : 병렬 서브에이전트 출격 (다른 둘의 기반)
  - 프로메테우스 (research): 지식 선행 리서치 (plan→N병렬+web_search→합성)
  - 나생문 (critique)     : 판단렌즈 ensemble critic (oracle 렌즈는 occam/eureka/oracle_lens)

graceful degrade: 키/SDK 부재 시 AgentRuntimeUnavailable → CLI가 skill-route fallback.
flat-layout: 모듈 간 bare import (client/dispatch/models/prometheus/naesengmoon), conftest가 path 주입.

# KG: bhgman-llm-commander-runtime-2026-05-28
"""

from engine.agents.client import AgentClient, AgentRuntimeUnavailable, Completion, runtime_status
from engine.agents.dispatch import SubagentResult, SubagentSpec, dispatch_parallel
from engine.agents.naesengmoon import DEFAULT_LENSES, EnsembleVerdict, LensVerdict, critique
from engine.agents.prometheus import ResearchReport, plan_axes, research, synthesize

__all__ = [
    "DEFAULT_LENSES",
    "AgentClient",
    "AgentRuntimeUnavailable",
    "Completion",
    "EnsembleVerdict",
    "LensVerdict",
    "ResearchReport",
    "SubagentResult",
    "SubagentSpec",
    "critique",
    "dispatch_parallel",
    "plan_axes",
    "research",
    "runtime_status",
    "synthesize",
]
