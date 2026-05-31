"""재배맨(Jaebaeman) SOP 실엔진 — 병렬 서브에이전트 출격.

재배맨 본질 = plan-first + 병렬 분해 후 출격(jaebaeman-planfirst-essence-reframe-2026-05-27).
정전상 "서비스 아닌 프로토콜"이지만, 실행 가능한 instantiation = N개 SubagentSpec을 병렬
디스패치하고 결과를 수확. 이 모듈이 그 공학적 본체. 프로메테우스/나생문이 이 위에서 fan-out.

각 서브에이전트 = (system, user, model). ThreadPoolExecutor로 병렬(SDK는 sync).
실패는 격리(한 서브 실패가 전체 죽이지 않음) → SubagentResult.ok=False로 수확.

# KG: jaebaeman-planfirst-essence-reframe-2026-05-27, 재배맨-v2-subagent-runtime-protocol,
#     bhgman-llm-commander-runtime-2026-05-28
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from engine.agents.client import AgentClient, Completion
from engine.agents.agent_models import SUBAGENT_MODEL


@dataclass(frozen=True)
class SubagentSpec:
    """씨앗 — 한 서브에이전트의 명세 (재배맨 SubagentTaskSpec의 실행형 최소판)."""

    name: str
    system: str
    user: str
    model: str = SUBAGENT_MODEL
    max_tokens: int = 2048
    web_search: bool = False


@dataclass(frozen=True)
class SubagentResult:
    name: str
    ok: bool
    text: str = ""
    error: str = ""
    completion: Completion | None = field(default=None)


def dispatch_parallel(
    specs: list[SubagentSpec],
    client: AgentClient,
    max_workers: int = 8,
) -> list[SubagentResult]:
    """N개 씨앗 병렬 출격 → 결과 수확. 입력 순서 보존. 실패 격리."""
    if not specs:
        return []

    def _run(spec: SubagentSpec) -> SubagentResult:
        try:
            c = client.complete(
                system=spec.system,
                user=spec.user,
                model=spec.model,
                max_tokens=spec.max_tokens,
                web_search=spec.web_search,
            )
            return SubagentResult(spec.name, True, c.text, "", c)
        except Exception as e:  # noqa: BLE001 — 한 서브 실패가 출격 전체를 죽이지 않게 격리
            return SubagentResult(spec.name, False, "", f"{type(e).__name__}: {e}")

    workers = min(max_workers, len(specs))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(_run, specs))


__all__ = ["SubagentResult", "SubagentSpec", "dispatch_parallel"]
