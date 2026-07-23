"""HALO-Loop L2 spine: ooptdd gate result → repair oracle.

Verifies the mechanism-3 mapping AND drives it end-to-end through the REAL
``legion.diagnostic_repair`` loop, with an injected NEGATIVE oracle (a cheated
green + an infra hold) so a vacuous pass cannot survive.

# KG: project_ultimate_ai_tool_halo_loop_2026_07_19
"""
from __future__ import annotations

import pytest

from engine.legion.diagnostic_repair import RepairStop, diagnostic_repair
from engine.naesengmoon.ooptdd_oracle import (
    OoptddGateOracle,
    feedback_from_ooptdd_result,
    _failed_gating,
)


def _green():
    return {"ok": True, "reachable": True, "complete": True, "cid": "t",
            "checks": [{"passed": True, "kind": "present", "label": "e1"}]}


def _red():
    return {"ok": False, "reachable": True, "complete": True, "cid": "t",
            "checks": [
                {"passed": True, "kind": "present", "label": "e1"},
                {"passed": False, "kind": "ratio", "label": "pass_ratio",
                 "reason": "0.5 < 1.0", "got": 0.5, "want": 1.0},
            ]}


# ----------------------- pure mapping -----------------------

def test_green_maps_to_passed_complete():
    fb = feedback_from_ooptdd_result(_green(), lens="ooptdd")
    assert fb.passed is True and fb.status == "passed" and fb.score == 1.0
    assert fb.valid is True and fb.terminal_error is False


def test_red_is_repairable_with_failed_check_tail():
    fb = feedback_from_ooptdd_result(_red(), lens="ooptdd")
    assert fb.passed is False and fb.status == "failed"
    assert fb.terminal_error is False  # a RED gate is repairable, not infra
    assert 0.0 < fb.score < 1.0        # 1 of 2 gating checks passed
    assert "pass_ratio" in fb.diagnostic and "ratio" in fb.diagnostic


def test_unreachable_store_is_infra_never_success():
    fb = feedback_from_ooptdd_result(
        {"ok": False, "reachable": False, "complete": True, "cid": "t", "checks": []},
        lens="ooptdd",
    )
    assert fb.passed is False and fb.status == "unavailable"
    assert fb.terminal_error is True and fb.valid is False
    assert "INFRA" in fb.diagnostic and "not a falsification" in fb.diagnostic.lower() \
        or "not a falsification" in fb.diagnostic


def test_incomplete_read_is_infra():
    fb = feedback_from_ooptdd_result(
        {"ok": False, "reachable": True, "complete": False, "cid": "t", "checks": []},
        lens="ooptdd",
    )
    assert fb.status == "unavailable" and fb.terminal_error is True


def test_alphacodium_fence_rejects_a_strength_regressed_green():
    """NEGATIVE oracle: a gate that went GREEN by WEAKENING must NOT be called passed."""
    fb = feedback_from_ooptdd_result(
        _green(), lens="ooptdd", weakened=True,
        regressions=["gating checks dropped 3 -> 1"],
    )
    assert fb.passed is False and fb.status == "failed"
    assert "REGRESSED" in fb.diagnostic and "gating checks dropped" in fb.diagnostic


# ----------------------- end-to-end through the real loop -----------------------

def test_repair_loop_reaches_complete_on_ooptdd_green():
    store = {"BROKEN": _red(), "FIXED": _green()}
    oracle = OoptddGateOracle(name="ooptdd", probe=lambda c: store[c])

    def repair(ctx):
        assert "pass_ratio" in ctx.missing  # the failed-check tail drove the repair
        return "FIXED"

    result = diagnostic_repair("BROKEN", repair, oracle, max_attempts=2)
    assert result.stop is RepairStop.COMPLETE
    assert result.verified is True and result.improved is True
    assert result.output == "FIXED"
    assert result.evaluations == 2


def test_infra_hold_stops_as_oracle_error_not_success():
    """NEGATIVE oracle: an unreachable store must halt the loop as ORACLE_ERROR — never
    a silent success, and repair must never be attempted on an infra hold."""
    infra = {"ok": False, "reachable": False, "complete": True, "cid": "t", "checks": []}
    calls = {"repair": 0}

    def repair(ctx):
        calls["repair"] += 1
        return "SHOULD_NOT_BE_CALLED"

    oracle = OoptddGateOracle(name="ooptdd", probe=lambda c: infra)
    result = diagnostic_repair("SEED", repair, oracle, max_attempts=3)
    assert result.stop is RepairStop.ORACLE_ERROR
    assert result.verified is False
    assert calls["repair"] == 0


def test_fence_flips_a_cheated_green_to_repairable_in_the_loop():
    """End-to-end NEGATIVE: a candidate whose gate is GREEN but strength-regressed is
    rejected by the fence, so the loop does not stop COMPLETE on it."""
    store = {"CHEAT": _green(), "HONEST": _green()}
    # CHEAT passes only by weakening; HONEST is a clean pass.
    fence = lambda c: (True, ["threshold lowered 1.0 -> 0.5"]) if c == "CHEAT" else (False, ())
    oracle = OoptddGateOracle(name="ooptdd", probe=lambda c: store[c], fence=fence)

    def repair(ctx):
        assert "REGRESSED" in ctx.missing
        return "HONEST"

    result = diagnostic_repair("CHEAT", repair, oracle, max_attempts=2)
    assert result.stop is RepairStop.COMPLETE
    assert result.output == "HONEST"  # the cheated green was not accepted


# ----------------------- real ooptdd contract cross-check -----------------------

def test_failed_gating_matches_real_ooptdd_failed_checks():
    """Pin our inline gating filter to ooptdd's canonical failed_checks so it can't drift."""
    gate = pytest.importorskip("ooptdd.engine.gate")
    result = {"ok": False, "reachable": True, "complete": True, "cid": "t", "checks": [
        {"passed": True, "kind": "present", "label": "a"},
        {"passed": False, "kind": "ratio", "label": "b"},
        {"passed": False, "kind": "present", "label": "c", "optional": True},
        {"passed": False, "kind": "present", "label": "d", "pending": True},
    ]}
    mine = [c["label"] for c in _failed_gating(result["checks"])]
    theirs = [c["label"] for c in gate.failed_checks(result)]
    assert mine == theirs == ["b"]  # optional/pending excluded on both sides
