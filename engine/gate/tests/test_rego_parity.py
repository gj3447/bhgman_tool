"""Conformance: the Python evaluators MUST be a faithful mirror of the .rego policies.

RED-first against TDD:gate_parity:* (KG-logged before this file). The audit (w5hoh7ww6) proved
the Python mirror was uniformly MORE PERMISSIVE than the Rego (it PASSed inputs OPA would DENY) and
nothing tied the two together. This runs the real `opa` binary against each .rego with the SAME
input the evaluator sees and asserts evaluate_gate == opa for both PASS and targeted-FAIL cases.

# KG: TDD:gate_parity:evaluator_mirrors_rego, TDD:gate_parity:sa_to_sp_a15_enforced,
#     TDD:gate_parity:sp_to_st_lensset_enforced, TDD:gate_parity:fulfillment_full_7checks
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from engine.gate.kg_materialize import evaluate_gate

_OPA = shutil.which("opa")
_POLICY_DIR = Path(__file__).resolve().parents[1] / "policies" / "apt_phase_gates"
_REGO = {
    "sa_to_sp": ("sa_to_sp.rego", "data.apt.phase_gates.sa_to_sp.allow"),
    "sp_to_st": ("sp_to_st.rego", "data.apt.phase_gates.sp_to_st.allow"),
    "st_to_scw": ("st_to_scw.rego", "data.apt.phase_gates.st_to_scw.allow"),
    "fulfillment": ("fulfillment_gate.rego", "data.apt.fulfillment_gate.allow"),
}

pytestmark = pytest.mark.skipif(_OPA is None, reason="opa binary not installed")


def _opa_allow(gate: str, inp: dict) -> bool:
    rego, query = _REGO[gate]
    proc = subprocess.run(
        [_OPA, "eval", "-d", str(_POLICY_DIR / rego), "-I", query, "--format", "raw"],
        input=json.dumps(inp),
        capture_output=True,
        text=True,
        check=True,
    )
    return proc.stdout.strip() == "true"


# ── canonical inputs (the .rego's own shape) — a PASS + targeted FAILs per gate ──
_SA_PASS = {
    "sa": {
        "name": "x",
        "status": "active",
        "root_span_name": "r",
        "root_span_status": "open",
        "context_budget_total": 8000,
        "duplicate_anchor_count": 0,
        "work_kind": "NEW",
        "phase_activation_mode": "FULL",
    },
    "apt_progress": {"git_committed": True, "l1_span_count": 1},
}
_SP_PASS = {
    "sp": {
        "leaves": [
            {
                "name": "l",
                "is_atomic": True,
                "objective": "o",
                "definition": "d",
                "keyAssertion": "k",
                "verification": "v",
                "c_s_predicate": "c",
            }
        ]
    },
    "taliban_verdict": "APPROVED",
    "taliban_lens_count": 9,
}
_ST_PASS = {
    "st": {
        "atoms": [{"name": "a", "has_twin": True}],
        "twins": [{"has_contract": True, "has_task": True}],
        "contracts": [{"status": "Active", "tau_check_pass": True, "field_count": 9}],
        "tasks": [{"impact_tests": ["t1"]}],
        "decision_areas_completed": ["a1", "a2", "a3", "a4", "a5"],
    },
    "config": {"contract_default_fields": 7, "st_tier1_count": 5},
}
_FUL_PASS = {
    "test_run": {"passed": 10, "total_tests": 10, "failed": 0, "skipped": 0},
    "actual": {
        "output_type": "DTO",
        "kg_refs_in_source": "# KG: TASK_x CONTRACT_y",
        "lines": 100,
        "test_assertion_count": 5,
        "postcondition_verified": True,
        "precondition_check_present": True,
        "postcondition_check_present": True,
        "latency_p99_ms": 50,
    },
    "contract": {"output_type": "DTO", "nfr_latency_p99_ms": 100, "nfr_memory_mb": None},
    "config": {"complexity_threshold": 500},
}


def _mut(base: dict, path: list, value) -> dict:
    out = json.loads(json.dumps(base))
    node = out
    for k in path[:-1]:
        node = node[k]
    node[path[-1]] = value
    return out


_CASES = [
    # (gate, input, intended_allow)
    ("sa_to_sp", _SA_PASS, True),
    ("sa_to_sp", _mut(_SA_PASS, ["sa", "work_kind"], None), False),  # A15 work_kind (drift)
    ("sa_to_sp", _mut(_SA_PASS, ["sa", "phase_activation_mode"], "X"), False),  # A15 mode (drift)
    ("sa_to_sp", _mut(_SA_PASS, ["sa", "status"], "draft"), False),
    ("sp_to_st", _SP_PASS, True),
    ("sp_to_st", _mut(_SP_PASS, ["taliban_verdict"], "PENDING"), False),  # lensset (drift)
    ("sp_to_st", _mut(_SP_PASS, ["taliban_lens_count"], 3), False),  # 3-lens shortcut (drift)
    ("sp_to_st", _mut(_SP_PASS, ["sp", "leaves", 0, "is_atomic"], False), False),
    ("st_to_scw", _ST_PASS, True),
    ("st_to_scw", _mut(_ST_PASS, ["st", "atoms", 0, "has_twin"], False), False),
    ("st_to_scw", _mut(_ST_PASS, ["st", "contracts", 0, "status"], "Draft"), False),
    ("fulfillment", _FUL_PASS, True),
    ("fulfillment", _mut(_FUL_PASS, ["test_run", "skipped"], 2), False),  # skipped (drift)
    (
        "fulfillment",
        _mut(_FUL_PASS, ["actual", "precondition_check_present"], False),
        False,
    ),  # check_3 (drift)
    (
        "fulfillment",
        _mut(_FUL_PASS, ["actual", "latency_p99_ms"], 200),
        False,
    ),  # NFR check_7 (drift)
]


@pytest.mark.parametrize("gate,inp,intended", _CASES)
def test_evaluator_matches_opa(gate, inp, intended):
    opa = _opa_allow(gate, inp)
    mine = evaluate_gate(gate, inp)[0]
    assert opa == intended, f"opa disagrees with intended for {gate}: opa={opa} intended={intended}"
    assert mine == opa, f"PARITY BREACH {gate}: evaluate_gate={mine} != opa={opa}"
