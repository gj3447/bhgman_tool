"""실-API smoke test — LLM 3종(prom/tlb/dispatch) C-level(실 인프라 e2e) 검증.

나생문 AC-bhgman-llm-zero-real-call (2026-05-28): agents 3종이 실 LLM으로 한 번도 실행 안 됨
(전부 FakeAnthropic 더블). 이 테스트가 그 공백을 닫는다 — 백엔드(로컬 LLM 또는 Anthropic)가
있을 때만 실행, 없으면 skip. 둘 중 하나면 C-level 닫힘:

    # DGX/로컬 vLLM (Anthropic 키 불필요):
    BHGMAN_LLM_BASE_URL=http://100.64.0.3:8000/v1 BHGMAN_LLM_MODEL=qwen3.6-27b \
        pytest engine/agents/tests/test_smoke_real_api.py -v
    # 또는 Anthropic:
    ANTHROPIC_API_KEY=sk-... pytest engine/agents/tests/test_smoke_real_api.py -v

cheap: 작은 max_tokens + N=1. prom web_search는 anthropic 백엔드만(로컬은 자동 no-web).
"""

from __future__ import annotations

import os

import pytest

from engine.agents.client import runtime_status

_ready, _reason = runtime_status()
# 로컬 백엔드면 web_search 서버툴 없음 → prom no-web.
_LOCAL = bool(os.environ.get("BHGMAN_LLM_BASE_URL"))
pytestmark = pytest.mark.skipif(
    not _ready, reason=f"LLM 백엔드 없음 — 실-API smoke skip ({_reason})"
)


def test_prom_real_research_web_search():
    """plan→1 web_search 서브에이전트→합성. pause_turn 서버루프 실응답 검증."""
    from engine.agents.client import AgentClient
    from engine.agents.prometheus import research

    report = research(
        "a single well-known fact about the Eiffel Tower",
        1,
        AgentClient(),
        web_search=not _LOCAL,  # 로컬 LLM엔 web_search 서버툴 없음
        max_tokens_per=512,
    )
    assert report.n >= 1
    assert any(f.ok for f in report.findings)
    assert report.synthesis.strip()  # 실 합성 텍스트 비어있지 않음


def test_tlb_real_single_lens_critique():
    """1 판단렌즈 실 LLM 비평 → PASS/FAIL/CONDITIONAL 파싱."""
    from engine.agents.client import AgentClient
    from engine.agents.naesengmoon import critique

    v = critique("smoke-claim", "Claim: 2 + 2 = 4.", AgentClient(), lenses=("mathematical",))
    assert v.verdict in ("PASS", "FAIL", "CONDITIONAL")
    assert len(v.lens_verdicts) == 1 and v.lens_verdicts[0].ok


def test_dispatch_real_single_subagent():
    """재배맨 1 서브에이전트 실 출격 → 결과 수확."""
    from engine.agents.client import AgentClient
    from engine.agents.dispatch import SubagentSpec, dispatch_parallel
    from engine.agents.agent_models import HAIKU

    spec = SubagentSpec(
        name="smoke",
        system="Reply with exactly one word.",
        user="Say 'ok'.",
        model=HAIKU,
        max_tokens=16,
    )
    results = dispatch_parallel([spec], AgentClient())
    assert len(results) == 1 and results[0].ok and results[0].text.strip()
