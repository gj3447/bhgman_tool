"""재배맨 kg_adapter TDD — covenant(MERGE-only) + depth NOT NULL + 엣지 빌더.

# KG: 재배맨-v2-subagent-runtime-protocol, lesson-jaebaeman-depth-invariant-2026-05-14
"""

from __future__ import annotations

from engine.jaebaeman.jaebaeman_models import SeedRecord
from engine.jaebaeman.kg_adapter import (
    FORBIDDEN_TOKENS,
    build_decomposes_to_edge,
    build_has_seed_edge,
    build_seed_merge,
    children_cypher,
    kg_decompose,
    plant_seeds,
)


class _Runner:
    def __init__(self, rows=None):
        self.rows = rows or []
        self.calls = []

    def __call__(self, cypher, params):
        self.calls.append((cypher, params))
        return self.rows


def _seed(name="seed-jaebaeman-g", source_id="span-g", parent=None, depth=0):
    return SeedRecord(
        name=name,
        skill="jaebaeman",
        source_id=source_id,
        display_name="g",
        task_type="research",
        target_domain="",
        expected_outcome="artifact",
        germination_method="singleton",
        depth=depth,
        parent=parent,
    )


def test_seed_merge_is_merge_not_destructive():
    cypher, params = build_seed_merge(_seed(), cycle_id="c1")
    up = cypher.upper()
    assert "MERGE (S:SUBAGENTTASKSPEC" in up
    assert all(tok not in up for tok in FORBIDDEN_TOKENS)  # covenant: 심기만
    assert "COALESCE($DEPTH, 0)" in up  # depth NOT NULL invariant
    assert params["depth"] == 0 and params["name"] == "seed-jaebaeman-g"


def test_has_seed_edge_none_for_self_anchored_root():
    # source_id == name → self-anchored, HAS_SEED 안 검 (자기 자신에 발아 엣지 무의미)
    self_seed = _seed(name="seed-jaebaeman-g", source_id="seed-jaebaeman-g")
    assert build_has_seed_edge(self_seed, 0, "c1") is None
    # anchor 다르면 엣지 생성
    edge = build_has_seed_edge(_seed(source_id="span-g"), 2, "c1")
    assert edge is not None
    _, p = edge
    assert p == {"anchor": "span-g", "seed": "seed-jaebaeman-g", "wave": 2, "cycle": "c1"}


def test_decomposes_to_edge_none_for_root():
    assert build_decomposes_to_edge(_seed(parent=None)) is None
    edge = build_decomposes_to_edge(_seed(parent="seed-jaebaeman-root"))
    assert edge is not None and edge[1]["parent"] == "seed-jaebaeman-root"


def test_plant_seeds_dry_run_default_no_write():
    seeds = [_seed(), _seed(name="seed-jaebaeman-a", parent="seed-jaebaeman-g")]
    w = _Runner()
    res = plant_seeds(seeds, write_cypher=w, dry_run=True)
    assert res.dry_run and res.applied_count == 0
    assert w.calls == []  # covenant: dry-run never writes
    assert res.seeded == ("seed-jaebaeman-g", "seed-jaebaeman-a")


def test_plant_seeds_apply_writes_nodes_then_edges():
    seeds = [
        _seed(name="seed-jaebaeman-g", source_id="span-g"),
        _seed(name="seed-jaebaeman-a", source_id="span-a", parent="seed-jaebaeman-g", depth=1),
    ]
    w = _Runner()
    res = plant_seeds(seeds, write_cypher=w, dry_run=False)
    assert not res.dry_run and res.applied_count == 2
    kinds = [c[0] for c in w.calls]
    # 2 seed MERGE + 2 HAS_SEED (둘 다 anchor != name) + 1 DECOMPOSES_TO
    assert sum("SubagentTaskSpec {name: $name}" in c for c in kinds) == 2
    assert sum("HAS_SEED" in c for c in kinds) == 2
    assert sum("DECOMPOSES_TO" in c for c in kinds) == 1


def test_kg_decompose_reads_children():
    rows = [
        {"child": "a", "objective": "A", "target_domain": "d"},
        {"child": "b", "objective": "B", "target_domain": ""},
    ]
    run = _Runner(rows)
    decompose = kg_decompose(run)

    class _Node:
        anchor = "span-root"

    subgoals = decompose(_Node())
    assert [g.name for g in subgoals] == ["a", "b"]
    assert subgoals[0].anchor == "a"  # 자식 name이 다음 anchor (재귀 연쇄)
    assert "$anchor" in children_cypher("span-root")[0]


def test_kg_decompose_no_anchor_is_leaf():
    run = _Runner([{"child": "a", "objective": "A"}])

    class _Node:
        anchor = None

    assert kg_decompose(run)(_Node()) == []
    assert run.calls == []  # anchor 없으면 KG 안 침


# ── W1-H: DAG (diamond) / cycle KG → valid deduped plan, NOT a fail-closed block ──


class _GraphRunner:
    """fake CypherRunner over an adjacency dict {anchor: [child_name, ...]}."""

    def __init__(self, adj):
        self.adj = adj
        self.calls = []

    def __call__(self, cypher, params):
        self.calls.append((cypher, params))
        anchor = params.get("anchor")
        return [{"child": c, "objective": c, "target_domain": ""} for c in self.adj.get(anchor, [])]


def _node_names(seeds):
    return [s.name.rsplit("-", 1)[-1] for s in seeds]


def test_plan_diamond_dag_dedups_to_unique_seeds():
    """Diamond A→B, A→C, B→D, C→D: D is reached via two paths but must yield ONE seed
    (no DUP_SEED_NAME), so the runner does not fail-closed-block."""
    from engine.jaebaeman.invariants import ViolationCode, validate_seed_invariants
    from engine.jaebaeman.jaebaeman_models import Goal
    from engine.jaebaeman.planner import plan, to_seeds

    run = _GraphRunner({"A": ["B", "C"], "B": ["D"], "C": ["D"], "D": []})
    root = plan(Goal(name="A", objective="A", anchor="A"), kg_decompose(run), max_depth=5)
    seeds = to_seeds(root, skill="prom")
    names = _node_names(seeds)
    assert sorted(set(names)) == ["A", "B", "C", "D"]
    assert len(names) == len(set(names)), f"duplicate seeds: {names}"
    dups = [v for v in validate_seed_invariants(seeds) if v.code == ViolationCode.DUP_SEED_NAME]
    assert dups == []


def test_plan_cycle_terminates_and_dedups():
    """Cycle A→B→A: must terminate (not unfold to max_depth) and dedup to a unique set."""
    from engine.jaebaeman.invariants import ViolationCode, validate_seed_invariants
    from engine.jaebaeman.jaebaeman_models import Goal
    from engine.jaebaeman.planner import plan, to_seeds

    run = _GraphRunner({"A": ["B"], "B": ["A"]})
    root = plan(Goal(name="A", objective="A", anchor="A"), kg_decompose(run), max_depth=10)
    seeds = to_seeds(root, skill="prom")
    names = _node_names(seeds)
    assert sorted(set(names)) == ["A", "B"]
    assert len(names) == len(set(names)), f"cycle produced duplicate seeds: {names}"
    dups = [v for v in validate_seed_invariants(seeds) if v.code == ViolationCode.DUP_SEED_NAME]
    assert dups == []
