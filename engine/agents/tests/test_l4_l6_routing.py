"""L4/L5/L6 TDD — 엔드포인트 라우팅·verify·트리 (FakeAnthropic / injected http_post, 실 네트 불필요).

L4 = endpoint-aware tier routing + malformed-JSON fallback + dead-code model-bug fix.
L5 = verify→repair (naesengmoon critique gated).
L6 = recursive tree expand/reduce + tool-call FOLLOWUPS parse + leaf fallback.

# KG: bhgman-llm-commander-runtime-2026-05-28
"""

from __future__ import annotations

from engine.agents.client import AgentClient, Completion, _load_endpoints
from engine.agents.dispatch import SubagentSpec, dispatch_parallel
from engine.agents.prometheus import (
    TreeNode,
    _parse_followups,
    _pick_hard_axes,
    research,
)
from fake_anthropic import FakeAnthropic


# ─────────────────────────── L4: _load_endpoints ───────────────────────────


def test_load_endpoints_unset_is_none(monkeypatch):
    monkeypatch.delenv("BHGMAN_LLM_ENDPOINTS", raising=False)
    assert _load_endpoints() is None


def test_load_endpoints_malformed_falls_back_to_legacy(monkeypatch):
    monkeypatch.setenv("BHGMAN_LLM_ENDPOINTS", "{not valid json")
    assert _load_endpoints() is None  # never raises → 레거시 단일 경로


def test_load_endpoints_missing_field_falls_back(monkeypatch):
    monkeypatch.setenv("BHGMAN_LLM_ENDPOINTS", '[{"name":"x"}]')  # base_url/model 누락
    assert _load_endpoints() is None


def test_load_endpoints_valid(monkeypatch):
    monkeypatch.setenv(
        "BHGMAN_LLM_ENDPOINTS",
        '[{"name":"fast","base_url":"http://a:1/v1","model":"m35","tier":0,"max_concurrency":24},'
        '{"name":"big","base_url":"http://b:2/v1","model":"m122","tier":1,"max_concurrency":2}]',
    )
    eps = _load_endpoints()
    assert eps is not None and len(eps) == 2
    assert eps[1].tier == 1 and eps[1].model == "m122" and eps[1].max_concurrency == 2


def test_tier_routes_to_distinct_endpoint_and_fixes_model_bug(monkeypatch):
    """L4 핵심: complete()가 caller model 을 버리고 tier→endpoint→model 로 물리 모델 선택."""
    monkeypatch.setenv("BHGMAN_LLM_BASE_URL", "http://a:1/v1")
    monkeypatch.setenv("BHGMAN_LLM_MODEL", "m35")
    monkeypatch.setenv(
        "BHGMAN_LLM_ENDPOINTS",
        '[{"name":"fast","base_url":"http://a:1/v1","model":"m35","tier":0},'
        '{"name":"big","base_url":"http://b:2/v1","model":"m122","tier":1}]',
    )
    c = AgentClient()  # real init → loads endpoints
    calls: list = []

    def fake_post(url, payload, headers, timeout):
        calls.append((url, payload["model"]))
        return {"model": payload["model"], "choices": [{"message": {"content": "x"}}], "usage": {}}

    c._post = fake_post
    c.complete(system="S", user="u", model="claude-haiku-4-5", tier=0)
    c.complete(system="S", user="u", model="claude-haiku-4-5", tier=1)
    assert calls[0] == ("http://a:1/v1/chat/completions", "m35")
    assert calls[1] == ("http://b:2/v1/chat/completions", "m122")  # caller model 무시, tier 가 결정


def test_endpoint_concurrency_map(monkeypatch):
    monkeypatch.setenv("BHGMAN_LLM_BASE_URL", "http://a:1/v1")
    monkeypatch.setenv("BHGMAN_LLM_MODEL", "m35")
    monkeypatch.setenv(
        "BHGMAN_LLM_ENDPOINTS",
        '[{"name":"fast","base_url":"http://a:1/v1","model":"m35","tier":0,"max_concurrency":24},'
        '{"name":"big","base_url":"http://b:2/v1","model":"m122","tier":1,"max_concurrency":2}]',
    )
    c = AgentClient()
    assert c.endpoint_concurrency() == {"http://a:1/v1": 24, "http://b:2/v1": 2}


def test_synthesize_tier1_degrades_to_tier0_on_failure(monkeypatch):
    """L4 fault-tolerance: dead tier-1(122B OOM)이 raise하면 synthesize 가 tier-0(35B)로 degrade."""
    monkeypatch.setenv("BHGMAN_LLM_BASE_URL", "http://a:1/v1")
    monkeypatch.setenv("BHGMAN_LLM_MODEL", "m35")
    monkeypatch.setenv(
        "BHGMAN_LLM_ENDPOINTS",
        '[{"name":"fast","base_url":"http://a:1/v1","model":"m35","tier":0},'
        '{"name":"dead","base_url":"http://b:2/v1","model":"m122","tier":1}]',
    )
    from engine.agents.client import LLMHTTPError
    from engine.agents.prometheus import synthesize
    from engine.agents.agent_models import LOCAL_BIG_TIER
    from engine.agents.dispatch import SubagentResult

    c = AgentClient()

    def fake_post(url, payload, headers, timeout):
        if "b:2" in url:  # tier-1 dead 122B → 500 OOM
            raise LLMHTTPError("HTTP 500: OOM")
        return {
            "model": payload["model"],
            "choices": [{"message": {"content": "## Consensus\n- degraded ok"}}],
            "usage": {},
        }

    c._post = fake_post
    out = synthesize("t", ["q"], [SubagentResult("a", True, "- f")], c, tier=LOCAL_BIG_TIER)
    assert "degraded ok" in out  # tier-1 죽어도 tier-0 로 보고 살아남음


def test_dispatch_legacy_ignores_tier(monkeypatch):
    """엔드포인트 미구성이면 tier=1 이어도 레거시 단일 모델 유지(zero regression)."""
    monkeypatch.delenv("BHGMAN_LLM_ENDPOINTS", raising=False)
    monkeypatch.setenv("BHGMAN_LLM_MODEL", "solo")
    calls: list = []

    def fake_post(url, payload, headers, timeout):
        calls.append(payload["model"])
        return {"model": payload["model"], "choices": [{"message": {"content": "ok"}}], "usage": {}}

    c = AgentClient(http_post=fake_post)
    dispatch_parallel([SubagentSpec("a", "S", "u", tier=1)], c)
    assert calls == ["solo"]  # tier 무시


# ─────────────────────────── L5: verify→repair ───────────────────────────


def _verify_responder(synth_text, critic_verdict, repaired_text):
    """plan→research→synth→critique(FAIL/CONDITIONAL)→repair 시퀀스 응답."""

    def responder(system: str, user: str, model: str) -> str:
        s = system.lower()
        if "research planner" in s:
            return "Q1\nQ2\nQ3"
        if "research subagent" in s:
            return "- finding (source: x)"
        if "adversarial critic" in s:  # naesengmoon lens
            return f"VERDICT: {critic_verdict}\n- nameable concern"
        if "synthesizing" in s:
            # 첫 synth vs repair 구분: repair prompt 엔 'adversarial critic raised' 포함
            if "critic raised" in user.lower():
                return repaired_text
            return synth_text
        return "?"

    return responder


def test_verify_runs_repair_on_conditional():
    c = AgentClient(
        client=FakeAnthropic(
            _verify_responder(
                "## Consensus\n- a\n## Divergence\n- b\n## Open Questions\n- c",
                "CONDITIONAL",
                "## Consensus\n- REPAIRED\n## Divergence\n- b\n## Open Questions\n- c",
            )
        )
    )
    report = research("topic", 3, c, web_search=False, verify=True)
    assert report.verify_verdict == "CONDITIONAL"
    assert "REPAIRED" in report.synthesis  # repair synth ran
    assert "verify=CONDITIONAL" in report.summary


def test_verify_pass_no_repair():
    c = AgentClient(
        client=FakeAnthropic(
            _verify_responder(
                "## Consensus\n- a\n## Divergence\n- b\n## Open Questions\n- c",
                "PASS",
                "SHOULD-NOT-APPEAR",
            )
        )
    )
    report = research("topic", 3, c, web_search=False, verify=True)
    assert report.verify_verdict == "PASS"
    assert "SHOULD-NOT-APPEAR" not in report.synthesis  # PASS → no repair


def test_verify_off_by_default():
    c = AgentClient(client=FakeAnthropic(_verify_responder("S", "FAIL", "R")))
    report = research("topic", 3, c, web_search=False)  # verify omitted
    assert report.verify_verdict == ""  # default OFF


# ─────────────────────────── L6: tree parse + research ───────────────────────────


def test_parse_followups_tool_call():
    comp = Completion(
        text="answer",
        model="m",
        tool_calls=({"name": "emit_followups", "arguments": '{"followups":["a","b","c","d"]}'},),
    )
    fu, ok = _parse_followups(comp, branch=2)
    assert ok and fu == ["a", "b"]  # branch cap


def test_parse_followups_empty_leaf():
    comp = Completion(
        text="done", model="m",
        tool_calls=({"name": "emit_followups", "arguments": '{"followups":[]}'},),
    )
    fu, ok = _parse_followups(comp, branch=3)
    assert ok and fu == []  # 명시적 leaf


def test_parse_followups_text_fallback():
    comp = Completion(text="ans\nFOLLOWUPS:\n- deeper q1\n- deeper q2", model="m")
    fu, ok = _parse_followups(comp, branch=5)
    assert ok and fu == ["deeper q1", "deeper q2"]


def test_parse_followups_unparseable_is_leaf():
    comp = Completion(text="just an answer, no block", model="m")
    fu, ok = _parse_followups(comp, branch=3)
    assert fu == [] and ok is False  # parse miss → treat as leaf (visible via ok=False)


def test_pick_hard_axes_keyword():
    axes = ["What is X?", "Compare X and Y tradeoffs", "List X facts"]
    hard = _pick_hard_axes(axes, hard_axes=1)
    assert hard == {"Compare X and Y tradeoffs"}  # keyword wins


def _tree_responder():
    """plan→(tree research with FOLLOWUPS text)→reduce synth."""

    def responder(system: str, user: str, model: str) -> str:
        s = system.lower()
        if "research planner" in s:
            return "Root Q1\nRoot Q2"
        if "recursive research tree" in s:
            # FakeAnthropic 엔 tool-call 없음 → 텍스트 FOLLOWUPS fallback 경로 검증
            return "- ans (source: x)\nFOLLOWUPS:\n- child q"
        if "synthesizing" in s:
            return "## Consensus\n- merged\n## Divergence\n- d\n## Open Questions\n- o"
        return "?"

    return responder


def test_research_depth2_tree_map_reduce():
    c = AgentClient(client=FakeAnthropic(_tree_responder()))
    report = research("topic", 2, c, web_search=False, depth=2, branch=1)
    assert report.depth == 2
    assert report.nodes > 2  # roots + children expanded
    assert "## Consensus" in report.synthesis  # map-reduce produced a synthesis
    assert "depth=2" in report.summary and "parse=" in report.summary


def test_research_depth1_is_flat_default():
    c = AgentClient(client=FakeAnthropic(_tree_responder()))
    report = research("topic", 2, c, web_search=False)  # depth default 1
    assert report.depth == 1 and report.nodes == 0  # flat — no tree fields


def test_treenode_post_init_children():
    n = TreeNode(nid="x", question="q")
    assert n.children == []  # mutable default guarded
