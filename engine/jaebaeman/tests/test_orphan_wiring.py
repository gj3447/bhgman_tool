"""고아 capability 배선-또는-강등 oracle (jbm-s6, gap G6 of audit wf_376c327b-8f3).

RED-first: htn.py(168 LOC)/llm_decompose.py(115)/harness_bridge.py(109)/ab_compare.py(46)
— 합계 ~440 LOC가 engine/jaebaeman 자기 테스트+bench 외 소비자 0이었다. llm_decompose는
CLI에 legion용 --llm 배관이 있음에도 cmd_jaebaeman의 어떤 플래그로도 선택 불가였다.
이 파일이 처분을 고정한다:

  배선 (2 — production 소비자 획득):
  * htn.kg_method_decompose  → `bhgman-tool jaebaeman --method kg-htn`
    (KG HAS_METHOD/DECOMPOSES_TO method 계층 분해)
  * llm_decompose            → `--method llm` (LLM=untrusted generator + 결정론 gate,
    C5 정전; runtime 부재 시 결정론 fallback으로 *정직 강등* — 우위 가정 금지 C6)

  정직 강등 (2 — 기계 마커로 bench-only 사실 고정):
  * harness_bridge.py / ab_compare.py 는 G6-DEMOTED 마커를 지닌다 — 승격하려면 배선 +
    마커 제거 + 이 oracle 갱신이 함께 필요 (무음 극장/무음 승격 양방향 차단).

  novel 축 (judge P2, 소비자 수와 독립): method_flag_discrimination — 같은 goal에서
  --method auto/kg-htn/llm 이 서로 *다른* 분해를 산출한다 (플래그가 실제 라우팅이며
  화장품이 아님).

# KG: LakatosTree_BhgmanJaebaeman_20260702/jbm_s6_orphan_wire_or_prune
# KG: lesson-jaebaeman-engine-impl-prom16-2026-06-01
# KG: 재배맨-v2-subagent-runtime-protocol
"""

from __future__ import annotations

from pathlib import Path

from engine.cli import commands
from engine.cli.commands import _jaebaeman_decompose
from engine.cli.parser import build_parser
from engine.jaebaeman.jaebaeman_models import Goal, GerminationMethod, PlanNode
from engine.jaebaeman.jaebaeman_runner import run_jaebaeman

_JBM_DIR = Path(__file__).resolve().parents[1]

_NODE = PlanNode(
    name="wo-root",
    objective="orphan wiring probe",
    task_type="research",
    target_domain="",
    depth=0,
    anchor="wo-root",
    germination_method=GerminationMethod.DECOMPOSE,
)

# HAS_METHOD/DECOMPOSES_TO rows exactly as htn.methods_cypher() returns them.
_METHOD_ROWS = [
    {
        "method": "m-split",
        "ord": 0,
        "subgoals": [
            {"name": "sub-a", "objective": "A쪽 절반"},
            {"name": "sub-b", "objective": "B쪽 절반"},
        ],
    }
]


def _kg_with_methods(cypher: str, params: dict) -> list[dict]:
    if "HAS_METHOD" in cypher:
        return list(_METHOD_ROWS) if params.get("task") == "wo-root" else []
    return []  # kg_decompose children query → none (so kg path stays leaf)


def _llm_complete_ok(_prompt: str) -> str:
    # self-cycle + dup 포함 — 결정론 gate가 걸러내야 한다 (C5 generate-and-check proof).
    return (
        '[{"name": "llm-a", "objective": "제안 A"}, {"name": "wo-root", "objective": "self"},'
        ' {"name": "llm-a", "objective": "dup"}]'
    )


def test_parser_accepts_method_flag():
    """The production surface: the jaebaeman subcommand carries --method."""
    args = build_parser().parse_args(["jaebaeman", "goal-text", "--method", "kg-htn"])
    assert args.method == "kg-htn"


def test_method_kg_htn_wires_htn_module():
    """--method kg-htn routes through htn.kg_method_decompose: the HAS_METHOD rows a real
    CypherRunner returns become the node's subgoals — htn.py gains its first production
    consumer (audit: zero outside its own tests)."""
    decompose, note = _jaebaeman_decompose("kg-htn", _kg_with_methods)
    assert note is None
    assert decompose is not None
    children = decompose(_NODE)
    assert [g.name for g in children] == ["sub-a", "sub-b"]
    assert all(isinstance(g, Goal) for g in children)


def test_method_llm_wires_llm_decompose_with_gate():
    """--method llm routes through llm_decompose: the LLM proposal is consumed ONLY
    through the deterministic gate (self-cycle + dup are dropped) — C5 정전."""
    decompose, note = _jaebaeman_decompose("llm", None, llm_complete=_llm_complete_ok)
    assert note is None
    assert decompose is not None
    children = decompose(_NODE)
    assert [g.name for g in children] == ["llm-a"], "gate must drop self-cycle and dup"


def test_method_llm_without_runtime_degrades_honestly(monkeypatch):
    """No LLM runtime → honest downgrade to the deterministic fallback WITH a stated
    reason (never a silent pretend-LLM path)."""
    monkeypatch.setattr(commands, "_agent_runtime", lambda: (None, "probe: no runtime"))
    decompose, note = _jaebaeman_decompose("llm", _kg_with_methods)
    assert note is not None and "정직 강등" in note and "probe: no runtime" in note
    # fallback = kg_decompose over the injected runner (deterministic core).
    assert decompose is not None
    assert decompose(_NODE) == []  # kg children query returns none → leaf, honestly


def test_method_flag_discrimination():
    """NOVEL axis (judge P2, independent of consumer counts): the flag actually routes —
    the SAME node decomposes differently under auto / kg-htn / llm."""
    auto, _ = _jaebaeman_decompose("auto", _kg_with_methods)
    kg_htn, _ = _jaebaeman_decompose("kg-htn", _kg_with_methods)
    llm, _ = _jaebaeman_decompose("llm", _kg_with_methods, llm_complete=_llm_complete_ok)

    assert auto is None  # auto = run_jaebaeman 기존 규칙에 위임 (여기선 singleton/leaf)
    names = {
        "auto": frozenset(),
        "kg-htn": frozenset(g.name for g in kg_htn(_NODE)),
        "llm": frozenset(g.name for g in llm(_NODE)),
    }
    assert names["kg-htn"] == {"sub-a", "sub-b"}
    assert names["llm"] == {"llm-a"}
    assert len(set(names.values())) == 3, f"routes must pairwise differ: {names}"


def test_e2e_method_children_become_seeds():
    """End-to-end: the wired decompose flows through run_jaebaeman — method-derived
    children land as depth-1 seeds (value-pinned 1 root + 2 children)."""
    decompose, _ = _jaebaeman_decompose("kg-htn", _kg_with_methods)
    goal = Goal(name="wo-root", objective="orphan wiring probe", anchor="wo-root")
    res = run_jaebaeman(goal, run_cypher=None, decompose=decompose, apply=False)
    assert len(res.seeds) == 3
    assert sorted(s.name for s in res.seeds if s.depth == 1) == [
        "seed-jaebaeman-sub-a",
        "seed-jaebaeman-sub-b",
    ]


def test_demotion_markers_present():
    """Honest demotion oracle: the two NOT-wired orphans carry the G6-DEMOTED marker —
    their bench-only status is a recorded fact, not an accident. Promoting either
    requires wiring + removing the marker + updating this oracle together."""
    for mod in ("harness_bridge.py", "ab_compare.py"):
        src = (_JBM_DIR / mod).read_text(encoding="utf-8")
        assert "G6-DEMOTED" in src, f"{mod} must carry the demotion marker"
        assert "bench" in src.lower(), f"{mod} must state its bench-only status"
