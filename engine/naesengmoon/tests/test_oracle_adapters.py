"""4 deterministic oracle adapters TDD — bhgman's confirmed oracle-substrate value.

lean-goals is tested end-to-end on a REAL self-contained proof (strongest evidence: an external
proof checker, substrate-disjoint from any LLM). The 4 factories all yield ScalarOracle with the
right kind. (drift/occam/pytest full execution is covered by their own modules' tests + needs live
state; here we assert construction + the lean real-verification path.)

# KG: prom16-bhgman-ci-design-2026-06-02, lesson-premature-close-confirmation-toward-closure-2026-06-02
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from engine.naesengmoon.oracle_adapters import (
    drift_recount_oracle,
    lean_goals_oracle,
    occam_twins_oracle,
    pytest_ratio_oracle,
)

_LEAN_DIR = Path(__file__).resolve().parents[3] / "lean"
_HAS_LEAN = shutil.which("lean") is not None


@pytest.mark.skipif(not _HAS_LEAN, reason="lean toolchain not installed (e.g. CI runner)")
def test_lean_goals_oracle_real_proof():
    """실제 자족 증명 → 닫은 goal 14 (theorem 14 - sorry 0), `lean` exit 0 전제."""
    o = lean_goals_oracle(_LEAN_DIR)
    sc = o.evaluate("Occam_SupersessionScore.lean")
    assert sc.kind == "lean-goals"
    assert sc.value == 14.0  # substrate-disjoint 진짜 검증: 외부 proof checker가 못박음


def test_lean_goals_oracle_missing_file_is_failure():
    o = lean_goals_oracle(_LEAN_DIR)
    assert o.evaluate("Does_Not_Exist.lean").value == -1000.0


def test_all_four_factories_yield_scalar_oracle_with_kind():
    assert lean_goals_oracle().kind == "lean-goals"
    assert pytest_ratio_oracle().kind == "pytest-ratio"
    assert drift_recount_oracle(code_root=".", kg=None).kind == "drift-recount"
    assert occam_twins_oracle(run_cypher=lambda *_a, **_k: []).kind == "occam-twins"
