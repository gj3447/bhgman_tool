"""TPA FulfillmentGate — verdict algebra + per-phase postcondition enforcement + receipts.

Covers the gap PROM 16 v2 isolated: `run_tpa` used to advance every reverse stage ungated
(gate=None), so a degraded extraction or an empty recovery reported a false green. These
tests pin the hardened default: postconditions gate the loop, and SKIP is never PASS.

# KG: seed-tpa-fulfillmentgate-hardening-2026-07-13
"""

from __future__ import annotations

from engine.tpa.fulfillment_gate import (
    PhaseReceipt,
    TpaFulfillmentGate,
    Verdict,
    evaluate_postcondition,
)
from engine.tpa.tpa_orchestrator import run_tpa, run_tpa_gated

_SRC = '''\
"""tiny module."""


def alpha(x):
    return x + 1


class Bar:
    def beta(self):
        return alpha(2)
'''


def _make_tree(tmp_path):
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "mod.py").write_text(_SRC)
    return tmp_path


# ── verdict algebra (APT parity: SKIP != PASS) ───────────────────────────────
def test_verdict_algebra_skip_is_never_pass():
    assert Verdict.PASS.unlocks_downstream is True
    assert Verdict.SKIP.unlocks_downstream is False  # the load-bearing rule
    assert Verdict.CONDITIONAL.unlocks_downstream is False
    assert Verdict.FAIL.unlocks_downstream is False


def test_verdict_advances_loop_pass_and_conditional_only():
    assert Verdict.PASS.advances_loop is True
    assert Verdict.CONDITIONAL.advances_loop is True  # vacuous recovery must not sink the cycle
    assert Verdict.SKIP.advances_loop is False
    assert Verdict.FAIL.advances_loop is False


# ── pure postcondition evaluator ─────────────────────────────────────────────
def test_postcondition_missing_key_fails():
    v, reason = evaluate_postcondition("TCW", {})
    assert v is Verdict.FAIL
    assert "no 'tcw_result'" in reason


def test_postcondition_degraded_fails():
    ctx = {"tcw_result": {"mode": "degraded", "reason": "code_root not found: /nope"}}
    v, reason = evaluate_postcondition("TCW", ctx)
    assert v is Verdict.FAIL
    assert "degraded" in reason


def test_postcondition_tcw_zero_symbols_fails():
    v, _ = evaluate_postcondition("TCW", {"tcw_result": {"symbol_count": 0}})
    assert v is Verdict.FAIL


def test_postcondition_st_empty_is_conditional_not_fail():
    v, _ = evaluate_postcondition("ST", {"contracts": {"count": 0}})
    assert v is Verdict.CONDITIONAL  # nothing structural to recover — flagged, not blocked


def test_postcondition_ta_zero_drift_passes():
    v, _ = evaluate_postcondition("TA", {"drift_report": {"drift_count": 0}})
    assert v is Verdict.PASS  # 0 drift is a valid measurement, not a failure


# ── gate as a stateful GateFn: order + receipts ──────────────────────────────
def test_gate_evaluates_phases_in_reverse_order():
    gate = TpaFulfillmentGate()
    gate({"tcw_result": {"symbol_count": 3}})
    gate({"contracts": {"count": 2}})
    gate({"patterns": {"groups": {"function": 1}}})
    gate({"drift_report": {"drift_count": 0}})
    assert [r.phase for r in gate.receipts] == ["TCW", "ST", "SP", "TA"]
    assert all(r.verdict is Verdict.PASS for r in gate.receipts)
    assert gate.all_passed is True
    assert gate.blocked_at is None


def test_gate_blocks_and_reports_first_failing_phase():
    gate = TpaFulfillmentGate()
    advanced, detail = gate({"tcw_result": {"mode": "degraded", "reason": "x"}})
    assert advanced is False
    assert detail.startswith("TCW:FAIL:")
    assert gate.blocked_at == "TCW"
    assert gate.all_passed is False


# ── end-to-end through run_tpa (default-gated) ───────────────────────────────
def test_run_tpa_valid_tree_completes_and_all_pass(tmp_path):
    root = _make_tree(tmp_path)
    result = run_tpa_gated(root)
    assert result.run.completed is True
    assert result.all_passed is True
    assert [r.phase for r in result.receipts] == ["TCW", "ST", "SP", "TA"]
    assert isinstance(result.receipts[0], PhaseReceipt)


def test_run_tpa_missing_code_root_now_fails_not_false_green(tmp_path):
    missing = tmp_path / "does_not_exist"
    result = run_tpa_gated(missing)
    # the hardening: a degraded TCW extraction halts at the gate instead of reporting green
    assert result.run.completed is not True
    assert result.run.gate_failure is not None
    assert "TCW" in result.run.gate_failure
    assert result.receipts[0].verdict is Verdict.FAIL
    assert len(result.receipts) == 1  # loop stopped at the first failing phase


def test_run_tpa_plain_returns_legionrun_and_stays_gated(tmp_path):
    # run_tpa keeps returning a LegionRun (back-compat) but is now gated by default.
    ok = run_tpa(_make_tree(tmp_path))
    assert ok.completed is True
    bad = run_tpa(tmp_path / "nope")
    assert bad.completed is not True
