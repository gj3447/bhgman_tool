"""실-API smoke test — LLM 3종(prom/tlb/dispatch) C-level(실 인프라 e2e) 검증.

나생문 AC-bhgman-llm-zero-real-call (2026-05-28): agents 3종이 실 Anthropic API로 한 번도
실행 안 됨(전부 FakeAnthropic 더블). 이 테스트가 그 공백을 닫는다 — 단, 비용/네트워크 때문에
**ANTHROPIC_API_KEY가 있을 때만 실행**(없으면 skip). 키 꽂고 돌리면 C-level 닫힘:

    ANTHROPIC_API_KEY=sk-... pytest engine/agents/tests/test_smoke_real_api.py -v

cheap 설정: haiku 서브에이전트 + 작은 max_tokens + N=1. prom은 web_search=True로 pause_turn
서버루프까지 실응답으로 1회 검증. 합 ~5 API 호출(수 센트).
"""

from __future__ import annotations

import os

import pytest


def _runtime_ready() -> tuple[bool, str]:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return False, "ANTHROPIC_API_KEY 미설정 — 실-API smoke skip"
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False, "anthropic SDK 미설치 — pip install 'bhgman_tool[agents]'"
    return True, "ok"


_ready, _reason = _runtime_ready()
pytestmark = pytest.mark.skipif(not _ready, reason=_reason)


def test_prom_real_research_web_search():
    """plan→1 web_search 서브에이전트→합성. pause_turn 서버루프 실응답 검증."""
    from client import AgentClient
    from prometheus import research

    report = research(
        "a single well-known fact about the Eiffel Tower",
        1,
        AgentClient(),
        web_search=True,
        max_tokens_per=512,
    )
    assert report.n >= 1
    assert any(f.ok for f in report.findings)
    assert report.synthesis.strip()  # 실 합성 텍스트 비어있지 않음


def test_tlb_real_single_lens_critique():
    """1 판단렌즈 실 LLM 비평 → PASS/FAIL/CONDITIONAL 파싱."""
    from client import AgentClient
    from naesengmoon import critique

    v = critique("smoke-claim", "Claim: 2 + 2 = 4.", AgentClient(), lenses=("mathematical",))
    assert v.verdict in ("PASS", "FAIL", "CONDITIONAL")
    assert len(v.lens_verdicts) == 1 and v.lens_verdicts[0].ok


def test_dispatch_real_single_subagent():
    """재배맨 1 서브에이전트 실 출격 → 결과 수확."""
    from client import AgentClient
    from dispatch import SubagentSpec, dispatch_parallel
    from agent_models import HAIKU

    spec = SubagentSpec(
        name="smoke",
        system="Reply with exactly one word.",
        user="Say 'ok'.",
        model=HAIKU,
        max_tokens=16,
    )
    results = dispatch_parallel([spec], AgentClient())
    assert len(results) == 1 and results[0].ok and results[0].text.strip()
