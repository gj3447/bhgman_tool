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
    _LEAN_DECL,
    _LEAN_HOLE,
    _strip_lean_comments,
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


class TestLeanCommentStripping:
    """W1-F: sorry/admit inside comments are NOT open goals — must not be counted."""

    def test_line_comment_sorry_admit_stripped(self):
        src = "theorem t : True := trivial -- sorry admit left as a note\n"
        stripped = _strip_lean_comments(src)
        assert "sorry" not in stripped
        assert "admit" not in stripped
        assert len(_LEAN_HOLE.findall(stripped)) == 0
        assert len(_LEAN_DECL.findall(stripped)) == 1  # decl survives

    def test_nested_block_comment_stripped(self):
        src = "/- outer /- inner sorry -/ admit -/\ntheorem t : True := trivial\n"
        stripped = _strip_lean_comments(src)
        assert "sorry" not in stripped
        assert "admit" not in stripped
        assert len(_LEAN_DECL.findall(stripped)) == 1

    def test_real_proof_position_hole_survives_stripping(self):
        src = "theorem t : p := by\n  sorry  -- TODO: real admit here later\n"
        stripped = _strip_lean_comments(src)
        # the proof-position sorry stays; the commented 'admit' is gone
        assert len(_LEAN_HOLE.findall(stripped)) == 1
        # net closed-goal count = 1 decl − 1 real hole = 0 (commented admit not double-counted)
        assert len(_LEAN_DECL.findall(stripped)) - len(_LEAN_HOLE.findall(stripped)) == 0

    @pytest.mark.skipif(not _HAS_LEAN, reason="lean toolchain not installed")
    def test_lean_oracle_ignores_commented_sorry_end_to_end(self, tmp_path):
        f = tmp_path / "CommentedHole.lean"
        f.write_text("theorem t : True := trivial  -- sorry not a real hole\n")
        o = lean_goals_oracle(tmp_path)
        # compiles (exit 0); 1 decl − 0 real holes = 1.0  (was 0.0 before the fix)
        assert o.evaluate("CommentedHole.lean").value == 1.0


def test_all_four_factories_yield_scalar_oracle_with_kind():
    assert lean_goals_oracle().kind == "lean-goals"
    assert pytest_ratio_oracle().kind == "pytest-ratio"
    assert drift_recount_oracle(code_root=".", kg=None).kind == "drift-recount"
    assert occam_twins_oracle(run_cypher=lambda *_a, **_k: []).kind == "occam-twins"


def test_lean_goals_oracle_no_path_doubling(tmp_path, monkeypatch):
    """A target already carrying the lean_dir prefix must not double-join to lean_dir/lean_dir/X
    (regression). subprocess mocked → no lean toolchain needed; both prefixed and bare targets
    must resolve to the single real file."""
    import engine.naesengmoon.oracle_adapters as oa

    leandir = tmp_path / "lean"
    leandir.mkdir()
    (leandir / "X.lean").write_text("theorem t : True := trivial\n")
    monkeypatch.chdir(tmp_path)

    seen: list[str] = []

    class _Proc:
        returncode = 0
        stdout = ""
        stderr = ""

    def _fake_run(cmd, **_kw):
        seen.append(cmd[1])
        return _Proc()

    monkeypatch.setattr(oa.subprocess, "run", _fake_run)

    o = oa.lean_goals_oracle("lean")
    assert o.evaluate("lean/X.lean").value == 1.0  # prefixed target — must NOT double
    assert o.evaluate("X.lean").value == 1.0  # bare target — resolves against lean_dir
    assert seen == ["lean/X.lean", "lean/X.lean"], f"path doubled: {seen}"
