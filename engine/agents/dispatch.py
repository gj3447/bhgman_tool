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
import threading
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
    # L4: tier 라우팅 — 0=fast(35B 브레드스), 1=big(122B 디코릴레이터/하드 축/synth).
    # 멀티 엔드포인트 미구성이면 무시(레거시 단일 백엔드). 기본 0 = 오늘 동작 불변.
    tier: int = 0
    # L6: openai-compat tool-calling (FOLLOWUPS emit_followups 강제). None = tool 미사용(오늘 동작).
    tools: tuple[dict, ...] | None = None
    tool_choice: str | dict | None = None


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

    # L4: per-endpoint 세마포어 — 얕은 Ollama(122B)를 K×N width 로 범람시키지 않게.
    # endpoint_for_tier 가 None(레거시 단일 백엔드 / 테스트 더블)이면 게이팅 없음(오늘 동작).
    # duck-typed: 이 메서드 없는 client(테스트 stub)는 세마포어 미사용으로 graceful degrade.
    _concurrency = getattr(client, "endpoint_concurrency", None)
    _ep_for_tier = getattr(client, "endpoint_for_tier", None)
    _sems: dict[str, threading.Semaphore] = (
        {base: threading.Semaphore(max(1, mc)) for base, mc in _concurrency().items()}
        if callable(_concurrency)
        else {}
    )

    def _sem_for(spec: SubagentSpec) -> threading.Semaphore | None:
        if not _sems or not callable(_ep_for_tier):
            return None
        ep = _ep_for_tier(spec.tier)
        return _sems.get(ep.base_url) if ep is not None else None

    def _run(spec: SubagentSpec) -> SubagentResult:
        sem = _sem_for(spec)
        if sem is not None:
            sem.acquire()
        try:
            c = client.complete(
                system=spec.system,
                user=spec.user,
                model=spec.model,
                max_tokens=spec.max_tokens,
                web_search=spec.web_search,
                temperature=spec.temperature,
                seed=spec.seed,
                tier=spec.tier,
                tools=list(spec.tools) if spec.tools is not None else None,
                tool_choice=spec.tool_choice,
            )
            return SubagentResult(spec.name, True, c.text, "", c)
        except Exception as e:  # noqa: BLE001 — 한 서브 실패가 출격 전체를 죽이지 않게 격리
            return SubagentResult(spec.name, False, "", f"{type(e).__name__}: {e}")
        finally:
            if sem is not None:
                sem.release()

    cap = int(os.environ.get("BHGMAN_MAX_INFLIGHT", "24"))
    workers = min(max_workers or cap, max(1, len(specs)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(_run, specs))


__all__ = ["SubagentResult", "SubagentSpec", "dispatch_parallel"]
