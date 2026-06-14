"""Phase B — gate KG→Rego materializer + evaluator (pure, fake-runner tested).

Turns the gate from a count-compare STUB (determinism theater) into a real KG-backed
engine: the evaluators mirror each .rego decision rule, the materializer projects KG rows
into the input doc each rego reads. No FastAPI / live Neo4j needed.
"""

from __future__ import annotations

import pytest

from engine.gate.kg_materialize import decide_gate, evaluate_gate, materialize_gate_input


class _FakeRunner:
    """Fake CypherRunner — returns canned rows by cypher signature."""

    def __init__(self, by_kind: dict[str, list[dict]] | None = None):
        self.by_kind = by_kind or {}
        self.calls: list[tuple[str, dict]] = []

    def __call__(self, cypher: str, params: dict) -> list[dict]:
        self.calls.append((cypher, params))
        if "taliban_verdict" in cypher:  # _CYPHER_SP_LENS
            return self.by_kind.get("lens", [])
        if "(leaf:Span" in cypher:
            return self.by_kind.get("leaves", [])
        if "(a:AtomicSpan" in cypher:
            return self.by_kind.get("st", [])
        if "(scw:SourceCodeNode" in cypher:
            return self.by_kind.get("fulfillment", [])
        if "sa.name AS name" in cypher:
            return self.by_kind.get("sa", [])
        return []


# ── evaluators (pure rego mirror) ────────────────────────────────────────────


def test_sa_to_sp_pass_and_fail():
    ok_inp = {
        "sa": {
            "name": "SA-x",
            "status": "active",
            "root_span_name": "root",
            "root_span_status": "open",
            "context_budget_total": 8000,
            "duplicate_anchor_count": 0,
            "work_kind": "NEW",
            "phase_activation_mode": "FULL",
        },
        "apt_progress": {"git_committed": True, "l1_span_count": 1},
    }
    # A15 work_kind / phase_activation_mode are now enforced (rego parity)
    assert (
        evaluate_gate("sa_to_sp", {**ok_inp, "sa": {**ok_inp["sa"], "work_kind": None}})[0] is False
    )
    assert evaluate_gate("sa_to_sp", ok_inp)[0] is True
    # break it three different ways
    bad = {**ok_inp, "sa": {**ok_inp["sa"], "status": "draft"}}
    assert evaluate_gate("sa_to_sp", bad)[0] is False
    bad2 = {**ok_inp, "apt_progress": {"git_committed": False, "l1_span_count": 1}}
    assert evaluate_gate("sa_to_sp", bad2)[0] is False
    bad3 = {**ok_inp, "sa": {**ok_inp["sa"], "duplicate_anchor_count": 2}}
    assert evaluate_gate("sa_to_sp", bad3)[0] is False


def _leaf(atomic=True, full=True):
    f = {"is_atomic": atomic}
    for k in ("objective", "definition", "keyAssertion", "verification", "c_s_predicate"):
        f[k] = "set" if full else None
    return f


_LENS_OK = {"taliban_verdict": "APPROVED", "taliban_lens_count": 9}


def test_sp_to_st_requires_all_atomic_with_full_cs():
    ok = {"sp": {"leaves": [_leaf(), _leaf()]}, **_LENS_OK}
    assert evaluate_gate("sp_to_st", ok)[0] is True
    assert (
        evaluate_gate("sp_to_st", {"sp": {"leaves": []}, **_LENS_OK})[0] is False
    )  # empty frontier
    assert (
        evaluate_gate("sp_to_st", {"sp": {"leaves": [_leaf(atomic=False)]}, **_LENS_OK})[0] is False
    )
    r = evaluate_gate("sp_to_st", {"sp": {"leaves": [_leaf(full=False)]}, **_LENS_OK})
    assert r[0] is False and "C(S)" in r[1]
    # lensset_complete now enforced: atomic + full C(S) but no 9-lens approval → deny
    r2 = evaluate_gate("sp_to_st", {"sp": {"leaves": [_leaf()]}, "taliban_verdict": "PENDING"})
    assert r2[0] is False and "LensSet" in r2[1]


def test_st_to_scw_full_check():
    ok = {
        "st": {
            "atoms": [{"has_twin": True}],
            "twins": [{"has_contract": True, "has_task": True}],
            "contracts": [{"status": "Active", "tau_check_pass": True, "field_count": 9}],
            "tasks": [{"impact_tests": ["t1", "t2", "t3"]}],
            "decision_areas_completed": ["d1", "d2", "d3", "d4", "d5"],
        },
        "config": {"contract_default_fields": 7, "st_tier1_count": 5},
    }
    assert evaluate_gate("st_to_scw", ok)[0] is True
    # contract under field threshold
    bad = {
        **ok,
        "st": {
            **ok["st"],
            "contracts": [{"status": "Active", "tau_check_pass": True, "field_count": 3}],
        },
    }
    assert evaluate_gate("st_to_scw", bad)[0] is False
    # task with empty impact_tests list (TDAD)
    bad2 = {**ok, "st": {**ok["st"], "tasks": [{"impact_tests": []}]}}
    assert evaluate_gate("st_to_scw", bad2)[0] is False
    # decision areas below tier1
    bad3 = {**ok, "st": {**ok["st"], "decision_areas_completed": ["d1", "d2"]}}
    assert evaluate_gate("st_to_scw", bad3)[0] is False


def test_fulfillment_full_check():
    ok = {
        "test_run": {"passed": 10, "total_tests": 10, "failed": 0, "skipped": 0},
        "actual": {
            "output_type": "DTO",
            "kg_refs_in_source": "# KG: TASK_x CONTRACT_y",
            "lines": 120,
            "test_assertion_count": 5,
            "postcondition_verified": True,
            "precondition_check_present": True,
            "postcondition_check_present": True,
        },
        "contract": {"output_type": "DTO"},
        "config": {"complexity_threshold": 500},
    }
    assert evaluate_gate("fulfillment_gate", ok)[0] is True
    # newly-enforced rego checks (parity): skipped!=0 and missing precondition presence → deny
    assert (
        evaluate_gate("fulfillment", {**ok, "test_run": {**ok["test_run"], "skipped": 1}})[0]
        is False
    )
    assert (
        evaluate_gate(
            "fulfillment", {**ok, "actual": {**ok["actual"], "precondition_check_present": False}}
        )[0]
        is False
    )
    assert (
        evaluate_gate(
            "fulfillment", {**ok, "test_run": {"passed": 8, "total_tests": 10, "failed": 2}}
        )[0]
        is False
    )
    assert (
        evaluate_gate(
            "fulfillment", {**ok, "actual": {**ok["actual"], "kg_refs_in_source": "no refs"}}
        )[0]
        is False
    )
    assert (
        evaluate_gate("fulfillment", {**ok, "actual": {**ok["actual"], "lines": 999}})[0] is False
    )


# ── materialize (KG projection) + decide (end-to-end) ────────────────────────


def test_materialize_sp_leaves_shapes_input():
    runner = _FakeRunner(
        {
            "leaves": [
                {
                    "is_atomic": True,
                    "objective": "o",
                    "definition": "d",
                    "keyAssertion": "k",
                    "verification": "v",
                    "c_s_predicate": "c",
                },
            ]
        }
    )
    inp = materialize_gate_input("sp_to_st", "cyc-1", runner)
    assert inp["sp"]["leaves"][0]["is_atomic"] is True
    assert inp["sp"]["leaves"][0]["objective"] == "o"


def test_decide_gate_end_to_end_sp_to_st_pass():
    runner = _FakeRunner(
        {
            "leaves": [
                {
                    "is_atomic": True,
                    "objective": "o",
                    "definition": "d",
                    "keyAssertion": "k",
                    "verification": "v",
                    "c_s_predicate": "c",
                },
                {
                    "is_atomic": True,
                    "objective": "o2",
                    "definition": "d2",
                    "keyAssertion": "k2",
                    "verification": "v2",
                    "c_s_predicate": "c2",
                },
            ],
            "lens": [{"taliban_verdict": "APPROVED", "taliban_lens_count": 9}],
        }
    )
    ok, reason = decide_gate("sp_to_st", "cyc-1", runner)
    assert ok is True
    assert "PASS" in reason
    assert runner.calls and runner.calls[0][1] == {"cycle_id": "cyc-1"}


def test_decide_gate_end_to_end_st_to_scw_blocks_on_missing_contract():
    # atom with twin but the twin lacks a contract → block
    runner = _FakeRunner(
        {
            "st": [
                {
                    "atom": "a1",
                    "has_twin": True,
                    "has_contract": False,
                    "has_task": True,
                    "contract_status": None,
                    "tau_check_pass": False,
                    "field_count": 0,
                    "impact_tests": ["t1"],
                    "decision_areas_completed": ["d1", "d2", "d3", "d4", "d5"],
                },
            ]
        }
    )
    ok, reason = decide_gate("st_to_scw", "cyc-1", runner)
    assert ok is False
    assert "Contract/Task" in reason or "twin" in reason.lower()


def test_unknown_gate_raises():
    with pytest.raises(ValueError):
        materialize_gate_input("G_made_up", "c", _FakeRunner())
    with pytest.raises(ValueError):
        evaluate_gate("G_made_up", {})
