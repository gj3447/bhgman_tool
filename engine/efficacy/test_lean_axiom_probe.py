"""Tests for the W4 lean #print axioms oracle. lean-dependent tests skip if no toolchain.

KG: project-apt-ultracode-roadmap-2026-06-02
"""

import shutil
from pathlib import Path

import pytest

from engine.efficacy import lean_axiom_probe as P


def test_fqns_in_tracks_namespace_stack():
    src = (
        "namespace Foo\n"
        "theorem a : True := trivial\n"
        "namespace Bar\n"
        "lemma b : True := trivial\n"
        "end Bar\n"
        "theorem c : True := trivial\n"
        "end Foo\n"
        "theorem d : True := trivial\n"
    )
    assert P.fqns_in(src) == ["Foo.a", "Foo.Bar.b", "Foo.c", "d"]


def test_probe_file_skips_files_with_imports(tmp_path: Path):
    f = tmp_path / "APT_X.lean"
    f.write_text("import Mathlib\ntheorem t : True := trivial\n")
    rep = P.probe_file(f)
    assert rep.compiled is False and "imports" in rep.error


@pytest.mark.skipif(not shutil.which("lean"), reason="lean toolchain not installed")
def test_probe_file_detects_sorry_taint(tmp_path: Path):
    f = tmp_path / "APT_Y.lean"
    f.write_text("theorem t_clean : True := trivial\ntheorem t_sorry : True := by sorry\n")
    rep = P.probe_file(f)
    assert rep.n_theorems == 2
    assert rep.n_sorry_tainted == 1  # t_sorry → sorryAx
    assert rep.n_genuinely_proven >= 1  # t_clean → no axioms
    assert rep.n_unresolved == 0
