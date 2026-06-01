"""씨앗 불변식 게이트 TDD (PROM 16 P1) — fail-closed, 로컬+KG.

# KG: lesson-jaebaeman-engine-impl-prom16-2026-06-01 (C4), finding-jbm-eng-C4
"""

from __future__ import annotations

from engine.jaebaeman.invariants import validate_seed_invariants
from engine.jaebaeman.jaebaeman_models import Goal, SeedRecord, ViolationCode
from engine.jaebaeman.jaebaeman_runner import run_jaebaeman


def _seed(name, *, source_id=None, depth=0, parent=None):
    return SeedRecord(
        name=name,
        skill="jaebaeman",
        source_id=source_id if source_id is not None else name,  # 기본 self-anchored
        display_name=name,
        task_type="research",
        target_domain="",
        expected_outcome="x",
        germination_method="singleton",
        depth=depth,
        parent=parent,
    )


class _Runner:
    def __init__(self, present_names=()):
        self.present = set(present_names)
        self.calls = []

    def __call__(self, cypher, params):
        self.calls.append((cypher, params))
        if "RETURN collect(a) AS missing" in cypher:
            anchors = params.get("anchors") or []
            return [{"missing": [a for a in anchors if a not in self.present]}]
        return []


# ── 로컬 체크 (run_cypher 불필요) ─────────────────────────────────────────────
def test_clean_batch_passes():
    seeds = [_seed("s0"), _seed("s1", parent="s0", depth=1)]
    assert validate_seed_invariants(seeds) == []


def test_dup_seed_name():
    seeds = [_seed("s0"), _seed("s0")]
    v = validate_seed_invariants(seeds)
    assert any(x.code is ViolationCode.DUP_SEED_NAME for x in v)


def test_depth_out_of_range():
    seeds = [_seed("s0", depth=4), _seed("s1", depth=-1)]
    codes = {x.code for x in validate_seed_invariants(seeds)}
    assert ViolationCode.E4_DEPTH_RANGE in codes
    assert sum(x.code is ViolationCode.E4_DEPTH_RANGE for x in validate_seed_invariants(seeds)) == 2


def test_dangling_parent():
    seeds = [_seed("s1", parent="ghost", depth=1)]
    v = validate_seed_invariants(seeds)
    assert any(x.code is ViolationCode.DANGLING_PARENT for x in v)


def test_multiple_seed_per_anchor():
    # 두 씨앗이 같은 외부 anchor 'span-x' 점유 → E3
    seeds = [_seed("s0", source_id="span-x"), _seed("s1", source_id="span-x")]
    v = validate_seed_invariants(seeds)
    assert sum(x.code is ViolationCode.E3_MULTIPLE_SEED_PER_ANCHOR for x in v) == 2


# ── KG 체크 (E1 orphan anchor) ───────────────────────────────────────────────
def test_orphan_anchor_flagged_when_kg_missing():
    seeds = [_seed("s0", source_id="span-present"), _seed("s1", source_id="span-absent")]
    run = _Runner(present_names={"span-present"})
    v = validate_seed_invariants(seeds, run_cypher=run)
    orphans = [x for x in v if x.code is ViolationCode.E1_ORPHAN_ANCHOR]
    assert len(orphans) == 1 and orphans[0].seed_id == "s1"


def test_no_kg_no_e1():
    # run_cypher 없으면 E1 체크 안 함 (로컬만)
    seeds = [_seed("s0", source_id="span-absent")]
    v = validate_seed_invariants(seeds)
    assert not any(x.code is ViolationCode.E1_ORPHAN_ANCHOR for x in v)


def test_self_anchored_not_checked_for_orphan():
    # source_id == name (self-anchored) → 외부 anchor 아님, E1 대상 아님
    seeds = [_seed("s0")]  # source_id defaults to name
    run = _Runner(present_names=set())
    assert validate_seed_invariants(seeds, run_cypher=run) == []


# ── runner fail-closed 통합 ──────────────────────────────────────────────────
def test_runner_blocks_apply_on_violation():
    # depth>3을 강제로 만드는 decompose는 planner가 막으니, max_depth로 위반 유도 대신
    # 외부 anchor가 KG에 없는 상황으로 E1 유발 + apply 차단 검증
    children = {"span-root": [{"child": "span-ghost", "objective": "g", "target_domain": ""}]}

    def run_cypher(cypher, params):
        if "-[:DECOMPOSES_TO|HAS_CHILD|DEPENDS_ON]->(c)" in cypher:
            return children.get(params["anchor"], [])
        if "RETURN collect(a) AS missing" in cypher:
            # span-root 존재, span-ghost 없음
            anchors = params.get("anchors") or []
            return [{"missing": [a for a in anchors if a != "span-root"]}]
        return []

    writes = []

    def write_cypher(c, p):
        writes.append((c, p))
        return []

    res = run_jaebaeman(
        Goal(name="span-root", objective="r", anchor="span-root"),
        run_cypher=run_cypher,
        write_cypher=write_cypher,
        apply=True,
    )
    assert res.violations  # span-ghost orphan 잡힘
    assert res.apply_result.dry_run  # fail-closed: apply여도 write 안 함
    assert res.apply_result.applied_count == 0
    assert writes == []  # 실제 write 0


def test_runner_validate_false_skips_gate():
    res = run_jaebaeman(Goal(name="g", objective="g"), validate=False)
    assert res.violations == ()
