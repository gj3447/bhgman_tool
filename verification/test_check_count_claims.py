"""Tests for the count-claim drift guard (verification/check_count_claims.py).

Covers the gating *policy* (lean HARD-exact, pytest soft-band on over-claim,
doc-presence) without re-running the real pytest suite — measurement functions
are monkeypatched so the tests are fast and deterministic.
"""

from __future__ import annotations

import json

import pytest

import verification.check_count_claims as g


@pytest.fixture
def manifest(tmp_path, monkeypatch):
    """Point the guard at a throwaway manifest + stub doc, and stub measurement."""
    doc = tmp_path / "lean-theorems.md"
    doc.write_text("tree 87, standalone 71 — index\n", encoding="utf-8")
    m = tmp_path / "count_claims.json"
    m.write_text(
        json.dumps(
            {
                "lean": {"theorems_tree": 87, "theorems_standalone": 71, "proof_position_sorry": 0},
                "pytest": {"engine_subset_collected": 299, "full_repo_collected": 853},
                "doc_presence": {"lean-theorems.md": [87, 71]},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(g, "MANIFEST", m)
    monkeypatch.setattr(g, "REPO", tmp_path)
    monkeypatch.setattr(
        g,
        "measure_lean",
        lambda: {
            "theorems_tree": 87,
            "theorems_standalone": 71,
            "proof_position_sorry": 0,
        },
    )
    monkeypatch.setattr(
        g,
        "measure_pytest",
        lambda: {
            "engine_subset_collected": 299,
            "full_repo_collected": 853,
        },
    )
    return m


def _set(m, section, key, value):
    d = json.loads(m.read_text())
    d[section][key] = value
    m.write_text(json.dumps(d))


def test_passes_when_everything_matches(manifest):
    assert g.run_check() == 0


def test_lean_mismatch_is_hard_failure(manifest, monkeypatch):
    monkeypatch.setattr(
        g,
        "measure_lean",
        lambda: {
            "theorems_tree": 88,
            "theorems_standalone": 71,
            "proof_position_sorry": 0,
        },
    )
    assert g.run_check() == 1  # exact-mismatch → fail (the 50→71 drift class)


def test_pytest_overclaim_is_hard_failure(manifest, monkeypatch):
    # doc claims 853 but reality only collected 800 → over-claim → fail
    monkeypatch.setattr(
        g,
        "measure_pytest",
        lambda: {
            "engine_subset_collected": 299,
            "full_repo_collected": 800,
        },
    )
    assert g.run_check() == 1


def test_pytest_stale_low_only_warns(manifest, monkeypatch, capsys):
    # reality grew past the doc (suite added tests) → warn, not fail
    monkeypatch.setattr(
        g,
        "measure_pytest",
        lambda: {
            "engine_subset_collected": 299,
            "full_repo_collected": 999,
        },
    )
    assert g.run_check() == 0
    assert "stale-low" in capsys.readouterr().out


def test_doc_presence_failure(manifest):
    (g.REPO / "lean-theorems.md").write_text("no numbers here\n", encoding="utf-8")
    assert g.run_check() == 1


def test_update_refreshes_manifest(manifest, monkeypatch):
    monkeypatch.setattr(
        g,
        "measure_pytest",
        lambda: {
            "engine_subset_collected": 299,
            "full_repo_collected": 860,
        },
    )
    assert g.run_update() == 0
    assert json.loads(manifest.read_text())["pytest"]["full_repo_collected"] == 860
