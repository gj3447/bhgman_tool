"""프로메테우스 research + 나생문 critique TDD (FakeAnthropic).

# KG: bhgman-llm-commander-runtime-2026-05-28
"""

from __future__ import annotations

from engine.agents.client import AgentClient
from fake_anthropic import FakeAnthropic
from engine.agents.naesengmoon import critique
from engine.agents.prometheus import research


def _prometheus_responder(system: str, user: str, model: str) -> str:
    if "research planner" in system:  # plan_axes
        return "What is X?\nHow does X scale?\nWhat are X's risks?"
    if "research subagent" in system:  # per-axis research
        return f"- finding for [{user.splitlines()[0]}] (source: example.com)"
    if "synthesizing" in system:  # synthesize
        return "## Consensus\n- shared\n## Divergence\n- conflict\n## Open Questions\n- unknown"
    return "unexpected"


def test_research_plans_dispatches_synthesizes():
    c = AgentClient(client=FakeAnthropic(_prometheus_responder))
    report = research("test topic", 3, c, web_search=False)
    assert report.n == 3
    assert len(report.sub_questions) == 3
    assert len(report.findings) == 3
    assert all(f.ok for f in report.findings)
    assert "## Consensus" in report.synthesis and "## Open Questions" in report.synthesis
    assert "researched_ok=3/3" in report.summary


def test_research_fallback_to_topic_when_plan_empty():
    c = AgentClient(client=FakeAnthropic(lambda s, u, m: "" if "planner" in s else "x"))
    report = research("solo", 3, c, web_search=False)
    assert report.sub_questions == ("solo",)  # plan 비면 토픽 자체로


def _critic_responder(verdict_map):
    def responder(system: str, user: str, model: str) -> str:
        for lens, v in verdict_map.items():
            if lens in system.lower():
                return f"VERDICT: {v}\n- finding about {lens}"
        return "VERDICT: CONDITIONAL\n- ?"

    return responder


def test_critique_unanimous_pass():
    c = AgentClient(
        client=FakeAnthropic(
            _critic_responder({"constitutional": "PASS", "mathematical": "PASS", "solid": "PASS"})
        )
    )
    v = critique("CLAIM-x", "the claim text", c)
    assert v.verdict == "PASS"
    assert {lv.lens for lv in v.lens_verdicts} == {"constitutional", "mathematical", "solid"}


def test_critique_any_fail_is_fail():
    c = AgentClient(
        client=FakeAnthropic(
            _critic_responder({"constitutional": "PASS", "mathematical": "FAIL", "solid": "PASS"})
        )
    )
    v = critique("CLAIM-x", "the claim", c)
    assert v.verdict == "FAIL"  # UNANIMOUS_PASS: 하나라도 FAIL → FAIL


def test_critique_mixed_is_conditional():
    c = AgentClient(
        client=FakeAnthropic(
            _critic_responder(
                {"constitutional": "PASS", "mathematical": "CONDITIONAL", "solid": "PASS"}
            )
        )
    )
    v = critique("CLAIM-x", "the claim", c)
    assert v.verdict == "CONDITIONAL"


def test_critique_subagent_failure_becomes_fail():
    def responder(s, u, m):
        if "mathematical" in s.lower():
            raise RuntimeError("model down")
        return "VERDICT: PASS\n- ok"

    c = AgentClient(client=FakeAnthropic(responder))
    v = critique("CLAIM-x", "the claim", c)
    assert v.verdict == "FAIL"  # ERROR 렌즈는 FAIL로 집계(보수)
    assert any(lv.verdict == "ERROR" for lv in v.lens_verdicts)
