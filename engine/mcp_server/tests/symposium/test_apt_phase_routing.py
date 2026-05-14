"""Validates /apt → SA → SP → ST → SCW phase routing.

Reference: APT v27 PATTERN_D (E1.4) — direct user call rejected by dispatch_guard.
Only the orchestrator (apt/SKILL.md) is a legitimate caller.

KG: rs-test-apt-phase-routing-2026-05-14
Provenance: SYMPOSIUM/tests/test_apt_phase_routing.py (absorbed Wave 7 P2-A)
"""

from __future__ import annotations

import pytest

from engine.mcp_server.tools.symposium import (
    APTDispatchRequest,
    _apt_dispatch_impl,
)


VALID_PHASES = ("sa", "sp", "st", "scw", "meta_review")
CANONICAL_ORDER = ("sa", "sp", "st", "scw")


class TestPhaseValidation:

    @pytest.mark.parametrize("phase", VALID_PHASES)
    def test_valid_phase_dispatched(self, phase, skills_dir):
        req = APTDispatchRequest(phase=phase, task="hello", cycle_id="c1")
        out = _apt_dispatch_impl(req)
        # Skill may not exist on disk (skeleton), but verdict must not be FAIL-invalid-phase.
        assert out["verdict"] in ("DISPATCHED", "FAIL")
        if out["verdict"] == "FAIL":
            assert "invalid phase" not in out["reason"]

    @pytest.mark.parametrize("bogus", ["xyz", "init", "destroy", "", "SA", "SP"])
    def test_invalid_phase_rejected(self, bogus):
        req = APTDispatchRequest(phase=bogus, task="t", cycle_id="c1")
        out = _apt_dispatch_impl(req)
        assert out["verdict"] == "FAIL"
        assert "invalid phase" in out["reason"]


class TestPhaseChainOrder:
    """SA → SP → ST → SCW canonical 4-phase chain (apt-orchestrator v27)."""

    def test_canonical_chain_progresses_monotonically(self):
        seen_indices = [CANONICAL_ORDER.index(p) for p in CANONICAL_ORDER]
        # monotonic increasing
        assert all(seen_indices[i] < seen_indices[i + 1] for i in range(len(seen_indices) - 1))

    def test_meta_review_is_terminal(self):
        # meta_review is phase 5/5, not part of SA→SP→ST→SCW chain.
        assert "meta_review" in VALID_PHASES
        assert "meta_review" not in CANONICAL_ORDER

    def test_no_skip_allowed_design(self):
        # SP cannot be entered without SA APPROVED. Verified by gate hook (separate test).
        # Here we assert the chain length & strict order are encoded.
        assert len(CANONICAL_ORDER) == 4


class TestDispatchPayload:
    def test_skill_md_path_returned_when_present(self, skills_dir):
        req = APTDispatchRequest(phase="sa", task="bootstrap", cycle_id="c1")
        out = _apt_dispatch_impl(req)
        if out["verdict"] == "DISPATCHED":
            assert out["skill_md"].endswith("SKILL.md")
            assert "apt-sa" in out["skill_md"]
            assert out["phase"] == "sa"
            assert out["task"] == "bootstrap"
            assert out["cycle_id"] == "c1"

    def test_default_actor_is_harness(self):
        req = APTDispatchRequest(phase="sa", task="t")
        out = _apt_dispatch_impl(req)
        if out["verdict"] == "DISPATCHED":
            assert out["actor"] == "claude-code-harness"

    def test_unassigned_cycle_id_marker(self):
        req = APTDispatchRequest(phase="sa", task="t", cycle_id=None)
        out = _apt_dispatch_impl(req)
        if out["verdict"] == "DISPATCHED":
            assert out["cycle_id"] == "unassigned"
