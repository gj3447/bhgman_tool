"""재배맨 LLM decompose (PROM 16 P4) — LLM=generator, 결정론 gate=verifier (neurosymbolic).

C5 정전: LLM은 *untrusted generator*. 계획 분해를 제안하되, 결정론 invariant gate가 검증하고
틀린 것은 버린다(generate-and-check). client 없으면 fallback(kg_decompose/singleton) — legion
commanders.py 패턴. 최종 FK/depth 불변식은 여전히 P1 validate_seed_invariants가 materialize 직전
강제(C4 다층): 여기 gate는 *생성 시점* 필터, P1은 *심기 시점* 게이트.

C6 정전: "LLM이 kg decompose보다 나은가"는 공정한 A/B falsifier(bench_decompose_ab.py)로만 — 같은
goal, 도구예산 통제, 외부 oracle. dispatch falsifier(인지기여 0) 전례 → 우위는 측정 전 가정 금지.

# KG: lesson-jaebaeman-engine-impl-prom16-2026-06-01 (C5/C6), finding-jbm-eng-D2, finding-jbm-eng-D4
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable

from engine.jaebaeman.jaebaeman_models import Goal, PlanNode
from engine.jaebaeman.planner import DecomposeFn

# LLM seam: user-prompt → completion text. fake로 테스트 / from_agent_client로 실 client 어댑트.
LlmComplete = Callable[[str], str]

_PROMPT = (
    "너는 계획 분해기다. 다음 목표를 1단계 하위 목표들로 쪼개라.\n"
    "목표: {name} — {objective}\n"
    "규칙: 자기 자신({name})을 하위목표로 넣지 마라. 최대 {cap}개. 더 못 쪼개면 빈 배열.\n"
    'JSON 배열만 출력: [{{"name": "<짧은-식별자>", "objective": "<한 줄>"}}]'
)

_JSON_ARRAY = re.compile(r"\[.*\]", re.DOTALL)


def _build_prompt(node: PlanNode, cap: int) -> str:
    return _PROMPT.format(name=node.name, objective=node.objective, cap=cap)


def _parse_subgoals(text: str) -> list[dict]:
    """completion에서 JSON 배열 추출·파싱. 실패/비배열 → []. (LLM 출력은 신뢰 안 함)"""
    m = _JSON_ARRAY.search(text or "")
    if not m:
        return []
    try:
        data = json.loads(m.group(0))
    except (json.JSONDecodeError, ValueError):
        return []
    return data if isinstance(data, list) else []


def _gate_subgoals(raw: list[dict], node: PlanNode, cap: int) -> list[dict]:
    """결정론 verifier: name 없는 것·self-cycle(==node.name)·중복 제거 + cap. (C5 gate)"""
    out: list[dict] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name or name == node.name or name in seen:
            continue
        seen.add(name)
        out.append({"name": name, "objective": str(item.get("objective") or name)})
        if len(out) >= cap:
            break
    return out


def llm_decompose(
    complete: LlmComplete,
    *,
    fallback: DecomposeFn | None = None,
    task_type: str = "research",
    max_subgoals: int = 8,
) -> DecomposeFn:
    """LLM이 하위 목표 제안 → gate 검증 → Goal 리스트. 실패/빈 결과 → fallback(없으면 잎).

    fallback = kg_decompose(run_cypher) 등 결정론 분해기 (client 없을 때 legion 패턴).
    """

    def decompose(node: PlanNode) -> list[Goal]:
        try:
            text = complete(_build_prompt(node, max_subgoals))
        except Exception:  # noqa: BLE001 — LLM 호출 실패는 fallback (graceful)
            text = ""
        clean = _gate_subgoals(_parse_subgoals(text), node, max_subgoals)
        if not clean:
            return fallback(node) if fallback is not None else []
        return [
            Goal(name=s["name"], objective=s["objective"], task_type=task_type, anchor=None)
            for s in clean
        ]

    return decompose


def from_agent_client(
    client, *, model: str = "claude-haiku-4-5-20251001", system: str = ""
) -> LlmComplete:
    """engine.agents.client.AgentClient → LlmComplete 어댑터. complete(system,user,model).text."""
    sys_prompt = system or "JSON만 출력. 설명 금지."

    def complete(user: str) -> str:
        return client.complete(system=sys_prompt, user=user, model=model).text

    return complete


__all__ = [
    "LlmComplete",
    "from_agent_client",
    "llm_decompose",
]
