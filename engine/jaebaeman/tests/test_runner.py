"""재배맨 runner TDD — plan→to_seeds→plant end-to-end. dry-run 기본.

# KG: jaebaeman-planfirst-essence-reframe-2026-05-27, project-legion-unification-kg-engine-2026-06-01
"""

from __future__ import annotations

from engine.jaebaeman.jaebaeman_models import Goal
from engine.jaebaeman.jaebaeman_runner import run_jaebaeman


class _Runner:
    def __init__(self, rows=None):
        self.rows = rows or []
        self.calls = []

    def __call__(self, cypher, params):
        self.calls.append((cypher, params))
        return self.rows


def test_singleton_dry_run_default():
    res = run_jaebaeman(Goal(name="g", objective="solve g"))
    assert res.depth_max == 0 and res.leaf_count == 1
    assert len(res.seeds) == 1
    assert res.apply_result.dry_run
    assert "DRY-RUN" in res.summary


def test_anchored_unfold_then_apply():
    # KG: span-root 밑에 a, b. a 밑엔 없음(잎).
    children = {
        "span-root": [
            {"child": "a", "objective": "A", "target_domain": ""},
            {"child": "b", "objective": "B", "target_domain": ""},
        ]
    }

    def run_cypher(cypher, params):
        if "-[:DECOMPOSES_TO|HAS_CHILD|DEPENDS_ON]->(c)" in cypher:
            return children.get(params["anchor"], [])
        return []

    write = _Runner()
    res = run_jaebaeman(
        Goal(name="root", objective="R", anchor="span-root"),
        run_cypher=run_cypher,
        write_cypher=write,
        apply=True,
    )
    assert [s.name for s in res.seeds] == [
        "seed-jaebaeman-root",
        "seed-jaebaeman-a",
        "seed-jaebaeman-b",
    ]
    assert res.depth_max == 1 and res.leaf_count == 2
    assert not res.apply_result.dry_run and res.apply_result.applied_count == 3
    assert write.calls  # 실제 write 발생


def test_apply_false_never_writes():
    write = _Runner()
    run_jaebaeman(Goal(name="g", objective="g"), write_cypher=write, apply=False)
    assert write.calls == []


def test_depth_cap_respected():
    def always_one(node):
        return [Goal(name=node.name + ".c", objective="deeper", anchor=node.name + ".c")]

    res = run_jaebaeman(
        Goal(name="g", objective="g", anchor="g"),
        decompose=always_one,
        max_depth=2,
    )
    assert res.depth_max == 2  # 무한 분해 규칙이어도 하드 cap
