"""재배맨 = legion substrate 배선 TDD — planner/lifecycle가 legion 경로에서 load-bearing.

# KG: bihaenggiman-legioncommanders-2026-05-26, lesson-jaebaeman-engine-impl-prom16-2026-06-01
"""

from __future__ import annotations

from engine.jaebaeman.jaebaeman_models import SeedStatus
from engine.legion.jaebaeman_substrate import (
    LEGION_GOAL,
    outcomes_to_seed_outcomes,
    plan_legion_seeds,
)
from engine.legion.legion import CANONICAL_ORDER, LegionRun
from engine.legion.legion_models import StageOutcome


def test_plan_legion_seeds_is_root_plus_six_verbs():
    seeds = plan_legion_seeds()
    # 루트 + 6 commander verb
    assert len(seeds) == 7
    root = [s for s in seeds if s.parent is None]
    leaves = [s for s in seeds if s.parent is not None]
    assert len(root) == 1 and len(leaves) == 6
    # leaf seed들이 CANONICAL_ORDER verb를 담음
    leaf_objectives = [s.display_name for s in leaves]
    for verb in CANONICAL_ORDER:
        assert any(verb in obj for obj in leaf_objectives)


def test_plan_legion_seeds_deterministic_pk():
    # planner PK 안정 (재실행 멱등)
    assert [s.name for s in plan_legion_seeds()] == [s.name for s in plan_legion_seeds()]


def _legion_run(n_ok: int, completed: bool) -> LegionRun:
    ocs = tuple(
        StageOutcome(f"cmd{i}", verb, i < n_ok, "provided" if i < n_ok else "missing")
        for i, verb in enumerate(CANONICAL_ORDER)
    )
    return LegionRun(outcomes=ocs, completed=completed)


def test_outcomes_map_all_collected_when_run_completes():
    seeds = plan_legion_seeds()
    out = outcomes_to_seed_outcomes(seeds, _legion_run(6, completed=True))
    # 루트 + 6 leaf = 7 outcome, 전부 COLLECTED
    assert len(out) == 7
    assert all(o.status is SeedStatus.COLLECTED for o in out)


def test_outcomes_map_failure_when_loop_halts():
    seeds = plan_legion_seeds()
    # 3 stage만 ok 후 halt → 나머지 leaf FAILED + 루트 FAILED
    out = outcomes_to_seed_outcomes(seeds, _legion_run(3, completed=False))
    collected = sum(1 for o in out if o.status is SeedStatus.COLLECTED)
    failed = sum(1 for o in out if o.status is SeedStatus.FAILED)
    assert collected == 3  # 3 leaf ok
    assert failed == 4  # 3 leaf fail + 루트 fail
    # 루트(LEGION_GOAL seed)는 FAILED
    root_seed = next(s for s in seeds if s.parent is None)
    root_out = next(o for o in out if o.seed_name == root_seed.name)
    assert root_out.status is SeedStatus.FAILED


def test_root_seed_named_for_legion_goal():
    seeds = plan_legion_seeds()
    root = next(s for s in seeds if s.parent is None)
    assert LEGION_GOAL in root.name
