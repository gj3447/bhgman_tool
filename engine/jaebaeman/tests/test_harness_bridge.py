"""harness → 재배맨 seed bridge — '하네스 자체가 재배맨 씨앗'을 코드로 닫는 RED 아티팩트.

재배맨 v2 = subagent-runtime-protocol: 씨앗 = :SubagentTaskSpec = 하네스(subagent) 컨텍스트.
하지만 harness *진단*(engine/harness, 3계층/4축)과 재배맨 *씨앗*은 아직 안 묶여 있었다. 이
브릿지가 그 갭을 닫는다: harness diagnosis → PRESENT로 확인되지 않은 각 축마다 plantable Goal(씨앗).
4축 완비 harness → 0 씨앗(보완 불필요), 축 무신호 → 4. RED until harness_seed_goals exists.

# KG: 재배맨-v2-subagent-runtime-protocol
"""
from __future__ import annotations

from engine.harness.harness import diagnose
from engine.jaebaeman.harness_bridge import harness_seed_goals


def _missing(goals) -> list[str]:
    return sorted(g.name.rsplit("ensure-", 1)[-1] for g in goals)


def test_missing_axes_become_compensation_seeds():
    # claude code: IDE_HOST, present {CONSTRAIN, VERIFY} → missing {INFORM, CORRECT}.
    goals = harness_seed_goals(diagnose("claude code"))
    assert len(goals) == 2
    assert _missing(goals) == ["correct", "inform"]
    assert all(g.task_type == "harness-compensation" for g in goals)
    assert all(g.target_domain == "IDE_HOST" for g in goals)  # the diagnosed tier


def test_full_four_axis_harness_yields_no_seed():
    # an explicit all-axes-present harness has no gap → no compensation seed.
    d = diagnose("x", signals={"inform": True, "constrain": True, "verify": True, "correct": True})
    assert harness_seed_goals(d) == []


def test_axis_less_harness_yields_four():
    goals = harness_seed_goals(diagnose("totally-unknown-xyz-framework"))
    assert len(goals) == 4
    assert _missing(goals) == ["constrain", "correct", "inform", "verify"]


def test_bridge_goals_are_plantable_via_jaebaeman():
    # the bridge output is real 재배맨 Goals → run_jaebaeman plants them as seeds (the handoff):
    # harness diagnosis → seeds → (germinate → subagent contexts, see test_germinate_handoff).
    from engine.jaebaeman.jaebaeman_models import Goal
    from engine.jaebaeman.jaebaeman_runner import run_jaebaeman
    from engine.jaebaeman.planner import static_decompose

    goals = harness_seed_goals(diagnose("claude code"))
    root = Goal(name="harness::claude code", objective="compensate harness gaps")
    res = run_jaebaeman(
        root,
        decompose=static_decompose({root.name: goals}),
        skill="harness",
        apply=False,
        validate=False,
    )
    seed_names = [s.name for s in res.seeds]
    assert any("ensure-inform" in n for n in seed_names)
    assert any("ensure-correct" in n for n in seed_names)
