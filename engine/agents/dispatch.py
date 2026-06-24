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

import os
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
    # 자기일관성(self-consistency) K-샘플링용 — 기본 0.0/None은 오늘의 greedy 동작을 그대로 보존.
    # temperature 0.0 → openai payload 미주입(greedy), seed None → 미주입. K>1 axis 복제 시에만 켜짐.
    temperature: float = 0.0
    seed: int | None = None


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
    max_workers: int | None = None,
) -> list[SubagentResult]:
    """N개 씨앗 병렬 출격 → 결과 수확. 입력 순서 보존. 실패 격리.

    max_workers=None(기본)이면 BHGMAN_MAX_INFLIGHT(기본 24)을 in-flight 상한으로 사용한다.
    K×N self-consistency 등으로 specs 가 늘면 그 폭만큼 vLLM 연속배칭에 동시 요청을 흘려 GB10을
    포화시킨다. min(..., len(specs))는 그대로라 specs 가 적으면 유휴 스레드를 만들지 않는다.
    (기본을 None으로 둬야 unchanged caller 들이 env 노브를 실제로 타게 된다 — 8 하드코드면 env 死코드.)
    """
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
                temperature=spec.temperature,
                seed=spec.seed,
            )
            return SubagentResult(spec.name, True, c.text, "", c)
        except Exception as e:  # noqa: BLE001 — 한 서브 실패가 출격 전체를 죽이지 않게 격리
            return SubagentResult(spec.name, False, "", f"{type(e).__name__}: {e}")

    cap = int(os.environ.get("BHGMAN_MAX_INFLIGHT", "24"))
    workers = min(max_workers or cap, max(1, len(specs)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(_run, specs))


__all__ = ["SubagentResult", "SubagentSpec", "dispatch_parallel"]
