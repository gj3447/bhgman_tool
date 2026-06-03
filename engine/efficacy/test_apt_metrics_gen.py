"""Regression tests for apt_metrics_gen — the APT Lean single-source metric generator.

Pins two things:
  (1) classification correctness on a synthetic fixture — esp. that `sorry`/`admit`
      inside comments, docstrings, and STRING LITERALS are NOT counted as live proof
      holes (the over-count bug fixed 2026-06-02; measurement-accuracy pre-filter).
  (2) the current disk truth of the canonical Lean tree, so future drift is caught.

KG: project-apt-ultracode-roadmap-2026-06-02
"""

from pathlib import Path

from engine.efficacy import apt_metrics_gen as M


def test_strip_counts_only_live_proof_terms(tmp_path: Path):
    f = tmp_path / "APT_Fixture.lean"
    f.write_text(
        "-- a line comment mentioning sorry\n"
        "/-- a docstring mentioning sorry and admit -/\n"
        "theorem foo : True := by trivial\n"
        'def msg : String := "Mathlib-free 0 sorry exit 0, admit ok"\n'
        "theorem bar : True := by sorry\n"
        "lemma baz : True := by admit\n"
    )
    data = M.compute(tmp_path)
    agg = data["aggregate"]
    assert agg["n_files"] == 1
    assert agg["n_theorems"] == 2  # foo, bar (lemma counted separately)
    assert agg["n_lemmas"] == 1  # baz
    assert agg["n_live_sorry"] == 1  # only `by sorry` in bar — NOT comment/docstring/string
    assert agg["n_live_admit"] == 1  # only `by admit` in baz — NOT docstring/string
    assert agg["n_comment_sorry"] >= 2  # comment + docstring + string occurrences


def test_string_literal_sorry_is_not_live(tmp_path: Path):
    f = tmp_path / "APT_Str.lean"
    f.write_text(
        'def a : String := "Lean Mathlib-free 0 sorry exit 0"\n'
        'def b : String := "compositions admit a multiplicative bound"\n'
        "theorem t : True := trivial\n"
    )
    agg = M.compute(tmp_path)["aggregate"]
    assert agg["n_live_sorry"] == 0
    assert agg["n_live_admit"] == 0


def test_disk_reality_canonical_tree():
    """Pin current disk truth of MIND/lean_formalization. Skips if tree absent."""
    import pytest

    if not M.DEFAULT_LEAN_ROOT.exists():
        pytest.skip("canonical lean tree not present on this host")
    agg = M.compute(M.DEFAULT_LEAN_ROOT)["aggregate"]
    assert agg["n_files"] == 32
    assert agg["n_theorems"] == 340
    assert agg["n_live_sorry"] == 0  # proof-term level: 0 (the docs' "0 sorry" IS true here)
    assert agg["n_live_admit"] == 0
    # W4 honesty: no toolchain -> axiom-level classification must be UNKNOWN, never "proven"
    assert agg["axiom_classification"] in ("UNKNOWN", "AVAILABLE_NOT_RUN")


def test_population_split_full_vs_architecture():
    """W3 adversarial finding: docs' '25 files' = architecture subset, not the full 32-glob."""
    import pytest

    if not M.DEFAULT_LEAN_ROOT.exists():
        pytest.skip("canonical lean tree not present on this host")
    pops = M.compute(M.DEFAULT_LEAN_ROOT)["aggregate"]["populations"]
    assert pops["full_glob"] == {"n_files": 32, "n_theorems": 340}
    assert pops["architecture_subset"]["n_files"] == 24  # ≈ docs' "25 files"
    assert pops["non_architecture_stream"]["n_files"] == 8
    # architecture theorems (266) ≥ docs' "245+" lower bound — so "245+" is true, not drift
    assert pops["architecture_subset"]["n_theorems"] >= 245
