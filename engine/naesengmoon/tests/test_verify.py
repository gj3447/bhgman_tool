"""verify() surface TDD — the 'is this artifact sound?' API a reasoner calls.

# KG: prom16-bhgman-ci-design-2026-06-02, lesson-premature-close-confirmation-toward-closure-2026-06-02
"""

from __future__ import annotations

from pathlib import Path

import pytest

from engine.naesengmoon.verify import KINDS, Verdict, verify

_LEAN_DIR = Path(__file__).resolve().parents[3] / "lean"
_THIS_TEST_DIR = str(Path(__file__).parent)


def test_verify_lean_goals_real_proof_passes():
    v = verify("lean-goals", "Occam_SupersessionScore.lean", lean_dir=str(_LEAN_DIR))
    assert isinstance(v, Verdict)
    assert v.passed is True
    assert v.score == 14.0
    assert "14 closed goals" in v.detail


def test_verify_lean_goals_missing_fails():
    v = verify("lean-goals", "Nope.lean", lean_dir=str(_LEAN_DIR))
    assert v.passed is False
    assert v.score == -1000.0


def test_verify_pytest_ratio_passing_target():
    v = verify("pytest-ratio", _THIS_TEST_DIR + "/test_oracle_adapters.py")
    assert v.kind == "pytest-ratio"
    assert v.score == 1.0 and v.passed is True


def test_verify_unknown_kind_raises():
    with pytest.raises(ValueError, match="unknown oracle kind"):
        verify("bogus", "x")


def test_kinds_complete():
    assert set(KINDS) == {"lean-goals", "pytest-ratio", "drift-recount", "occam-twins"}
