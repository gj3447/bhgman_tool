"""KG-input 접지(grounding) TDD — LocalGroundingSource / retrieve / format + 엔진 주입.

# KG: canon-kg-based-coding-essence-2026-05-28, KGFirstCheck_v1
"""

from __future__ import annotations

from engine.agents.client import AgentClient
from engine.agents.grounding import (
    LocalGroundingSource,
    Neo4jGroundingSource,
    build_grounding,
    format_context,
    retrieve,
)
from engine.agents.naesengmoon import critique
from engine.agents.prometheus import research
from fake_anthropic import FakeAnthropic


class _FakeStore:
    """LocalKgStore의 .nodes만 흉내 (접지원은 .nodes만 읽음)."""

    def __init__(self, nodes: list[dict]) -> None:
        self.nodes = nodes


_NODES = [
    {
        "labels": ["UserPrimaryCanon", "Principle"],
        "props": {"name": "canon-replay-tcb", "claim": "replay-가용성은 비대칭 TCB 이진 경계"},
    },
    {
        "labels": ["Lesson"],
        "props": {"name": "lesson-monism-overreach", "truth": "결정성은 kind not degree"},
    },
    {
        "labels": ["ResearchFinding"],
        "props": {"name": "rf-unrelated", "summary": "완전히 무관한 토픽 quantum foobar"},
    },
]


def test_local_source_matches_and_canon_weighted():
    src = LocalGroundingSource(_FakeStore(_NODES))
    rows = src.search(["replay", "결정성"], limit=5)
    names = [r["props"]["name"] for r in rows]
    assert "canon-replay-tcb" in names
    assert "lesson-monism-overreach" in names
    assert "rf-unrelated" not in names  # 무관 토픽은 0 score → 제외


def test_retrieve_and_format_context():
    src = LocalGroundingSource(_FakeStore(_NODES))
    facts = retrieve(src, "replay TCB 경계", limit=5)
    assert facts and facts[0].name == "canon-replay-tcb"
    ctx = format_context(facts)
    assert "사전 지식" in ctx and "canon-replay-tcb" in ctx


def test_grounding_empty_is_graceful():
    assert retrieve(None, "anything") == []
    assert format_context([]) == ""
    ctx, n = build_grounding(None, "topic")
    assert ctx == "" and n == 0


def test_short_tokens_filtered():
    # 4자 미만 토큰만 있으면 검색 안 함 (noise 방지)
    ctx, n = build_grounding(LocalGroundingSource(_FakeStore(_NODES)), "a b cd")
    assert ctx == "" and n == 0


def test_neo4j_source_builds_cypher_and_normalizes():
    captured: dict = {}

    def fake_run(cypher: str, params: dict) -> list[dict]:
        captured["cypher"] = cypher
        captured["params"] = params
        return [{"labels": ["Lesson"], "props": {"name": "x", "truth": "t"}}]

    rows = Neo4jGroundingSource(fake_run).search(["replay", "tcb"], limit=4)
    assert "CONTAINS $t0" in captured["cypher"] and "$labels" in captured["cypher"]
    assert captured["params"]["limit"] == 4
    assert rows[0]["props"]["name"] == "x"


def test_research_threads_grounding_into_prompts():
    seen: dict = {"grounded": False}

    def responder(system: str, user: str, model: str) -> str:
        if "사전 지식" in user or "canon-replay-tcb" in user:
            seen["grounded"] = True
        if "research planner" in system:
            return "Q1\nQ2"
        if "research subagent" in system:
            return "- finding (source: x.com)"
        return "## Consensus\n- s\n## Divergence\n- d\n## Open Questions\n- o"

    c = AgentClient(client=FakeAnthropic(responder))
    src = LocalGroundingSource(_FakeStore(_NODES))
    report = research("replay TCB 경계", 2, c, web_search=False, grounding=src)
    assert seen["grounded"], "KG 사전지식이 prompt에 주입되지 않음"
    assert report.grounded_facts >= 1
    assert "grounded=" in report.summary


def test_critique_threads_grounding_into_lens_prompts():
    seen: dict = {"grounded": False}

    def responder(system: str, user: str, model: str) -> str:
        if "관련 정전" in user or "canon-replay-tcb" in user:
            seen["grounded"] = True
        return "VERDICT: PASS\n- ok"

    c = AgentClient(client=FakeAnthropic(responder))
    src = LocalGroundingSource(_FakeStore(_NODES))
    v = critique("canon-replay-tcb", "replay 경계 주장", c, grounding=src)
    assert seen["grounded"], "KG 정전·교훈이 렌즈 prompt에 주입되지 않음"
    assert v.grounded_facts >= 1
    assert "grounded=" in v.summary


def test_critique_ungrounded_still_works():
    c = AgentClient(client=FakeAnthropic(lambda s, u, m: "VERDICT: PASS\n- ok"))
    v = critique("x", "claim", c, grounding=None)
    assert v.verdict == "PASS" and v.grounded_facts == 0
