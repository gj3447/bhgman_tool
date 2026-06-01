"""LLM decompose TDD (PROM 16 P4) — LLM generator + 결정론 gate, fallback. fake LLM.

# KG: lesson-jaebaeman-engine-impl-prom16-2026-06-01 (C5/C6), finding-jbm-eng-D2/D4
"""

from __future__ import annotations

from engine.jaebaeman.ab_compare import compare_decompose
from engine.jaebaeman.jaebaeman_models import Goal
from engine.jaebaeman.llm_decompose import from_agent_client, llm_decompose
from engine.jaebaeman.planner import plan, static_decompose, walk


def _names(tree):
    return [n.name for n, _ in walk(tree)]


def _fake(text, only_for="g"):
    """prompt-aware fake LLM — root goal에만 text 반환, 하위 노드엔 빈 배열(자연 잎).

    (constant fake는 모든 노드에 같은 분해 반환 → depth cap까지 재귀. 실 LLM도 그러면 폭주이므로
    P1/depth-cap이 받지만, 단위 테스트는 root-only로 의도 분해만 검증.)
    """
    return lambda prompt: text if f"목표: {only_for} " in prompt else "[]"


# ── 생성 + gate ──────────────────────────────────────────────────────────────
def test_valid_json_produces_subgoals():
    dec = llm_decompose(_fake('[{"name":"a","objective":"A"},{"name":"b","objective":"B"}]'))
    tree = plan(Goal(name="g", objective="r"), dec)
    assert _names(tree) == ["g", "a", "b"]


def test_json_in_code_fence_parsed():
    dec = llm_decompose(_fake('```json\n[{"name":"a","objective":"A"}]\n```'))
    assert _names(plan(Goal(name="g", objective="r"), dec)) == ["g", "a"]


def test_self_cycle_subgoal_dropped():
    # LLM이 자기 자신을 하위목표로 → gate가 제거 (무한 재귀 차단)
    dec = llm_decompose(_fake('[{"name":"g","objective":"self"},{"name":"a","objective":"A"}]'))
    assert _names(plan(Goal(name="g", objective="r"), dec)) == ["g", "a"]


def test_dedup_subgoals():
    dec = llm_decompose(_fake('[{"name":"a","objective":"A"},{"name":"a","objective":"dup"}]'))
    assert _names(plan(Goal(name="g", objective="r"), dec)) == ["g", "a"]


def test_cap_max_subgoals():
    many = ",".join(f'{{"name":"s{i}","objective":"o"}}' for i in range(20))
    dec = llm_decompose(_fake(f"[{many}]"), max_subgoals=3)
    tree = plan(Goal(name="g", objective="r"), dec)
    assert len(_names(tree)) == 1 + 3  # g + 3 capped


# ── fallback ─────────────────────────────────────────────────────────────────
def test_junk_output_uses_fallback():
    fb = static_decompose({"g": [Goal(name="fb", objective="fallback")]})
    dec = llm_decompose(_fake("sorry I cannot help"), fallback=fb)
    assert _names(plan(Goal(name="g", objective="r"), dec)) == ["g", "fb"]


def test_empty_array_uses_fallback():
    fb = static_decompose({"g": [Goal(name="fb", objective="f")]})
    dec = llm_decompose(_fake("[]"), fallback=fb)
    assert _names(plan(Goal(name="g", objective="r"), dec)) == ["g", "fb"]


def test_no_fallback_is_leaf():
    dec = llm_decompose(_fake("[]"))
    assert plan(Goal(name="g", objective="r"), dec).is_leaf


def test_llm_call_raises_uses_fallback():
    def boom(_prompt):
        raise RuntimeError("LLM down")

    fb = static_decompose({"g": [Goal(name="fb", objective="f")]})
    dec = llm_decompose(boom, fallback=fb)
    assert _names(plan(Goal(name="g", objective="r"), dec)) == ["g", "fb"]


# ── from_agent_client 어댑터 ─────────────────────────────────────────────────
def test_from_agent_client_adapter():
    class _Comp:
        text = '[{"name":"a","objective":"A"}]'

    class _FakeClient:
        def __init__(self):
            self.calls = []

        def complete(self, *, system, user, model):
            self.calls.append((system, user, model))
            return _Comp()

    client = _FakeClient()
    dec = llm_decompose(from_agent_client(client, model="m"))
    assert _names(plan(Goal(name="g", objective="r"), dec)) == ["g", "a"]
    assert client.calls and client.calls[0][2] == "m"


# ── A/B falsifier harness ────────────────────────────────────────────────────
def test_compare_decompose_reports_divergence():
    arm_a = llm_decompose(_fake('[{"name":"x","objective":"X"}]'))
    arm_b = static_decompose({"g": [Goal(name="y", objective="Y")]})
    cmp = compare_decompose(Goal(name="g", objective="r"), arm_a, arm_b, max_depth=2)
    assert cmp["a_only"] == ["x"] and cmp["b_only"] == ["y"]
    assert "g" not in cmp["a_only"]  # 공통 노드는 a_only 아님
    assert 0.0 <= cmp["jaccard"] <= 1.0
    assert "node_count" in cmp["arm_a"] and "node_count" in cmp["arm_b"]


def test_compare_identical_arms_jaccard_one():
    arm = static_decompose({"g": [Goal(name="a", objective="A")]})
    cmp = compare_decompose(Goal(name="g", objective="r"), arm, arm, max_depth=2)
    assert cmp["jaccard"] == 1.0 and cmp["a_only"] == [] and cmp["b_only"] == []
