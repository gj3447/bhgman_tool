"""하데스 end-to-end runner TDD — fetch ACCEPTED 추상 → realize. dry-run 기본.

# KG: hades-canonical-2026-05-27, consensus-eureka-engine-impl-2026-05-26 (c6 materialize danger)
"""

from __future__ import annotations

from engine.hades.hades_models import RealizeStatus
from engine.hades.hades_runner import fetch_accepted_cypher, run_hades


class _Runner:
    def __init__(self, rows=None):
        self.rows = rows or []
        self.calls = []

    def __call__(self, cypher, params):
        self.calls.append((cypher, params))
        return self.rows


_ACCEPTED_ROWS = [
    {
        "concept": "ac_topology",
        "verdict": "ACCEPTED",
        "members": ["Topology", "Group Theory", "Algebra"],
    },
]
_MIXED_ROWS = [
    {"concept": "ac_ok", "verdict": "ACCEPTED", "members": ["a", "b"]},
    {"concept": "ac_prov", "verdict": "PROVISIONAL", "members": ["c", "d"]},
]


def test_fetch_cypher_no_concept_filters_accepted():
    cypher, params = fetch_accepted_cypher(None)
    assert "ACCEPTED" in cypher
    assert params == {}


def test_fetch_cypher_concept_binds_param():
    cypher, params = fetch_accepted_cypher("ac_topology")
    assert "$concept" in cypher
    assert params == {"concept": "ac_topology"}


def test_run_hades_dry_run_default_plans_not_applies():
    read, apply = _Runner(_ACCEPTED_ROWS), _Runner()
    res = run_hades(read, apply_cypher=apply)  # apply defaults False
    assert len(res.verdicts) == 1
    assert res.verdicts[0].status is RealizeStatus.PLANNED
    assert apply.calls == []  # c6 danger guard: dry-run never writes


def test_run_hades_apply_materializes():
    read, apply = _Runner(_ACCEPTED_ROWS), _Runner()
    res = run_hades(read, apply_cypher=apply, apply=True)
    assert res.verdicts[0].status is RealizeStatus.APPLIED
    assert len(apply.calls) >= 1


def test_run_hades_refuses_non_accepted_in_mixed():
    read, apply = _Runner(_MIXED_ROWS), _Runner()
    res = run_hades(read, apply_cypher=apply, apply=True)
    by_concept = {v.concept: v for v in res.verdicts}
    assert by_concept["ac_ok"].status is RealizeStatus.APPLIED
    assert by_concept["ac_prov"].status is RealizeStatus.REFUSED  # ACCEPTED만


def test_run_hades_apply_without_runner_stays_dry_run():
    read = _Runner(_ACCEPTED_ROWS)
    res = run_hades(read, apply_cypher=None, apply=True)  # no runner → can't write
    assert res.verdicts[0].status is RealizeStatus.PLANNED
    assert res.applied_count == 0
