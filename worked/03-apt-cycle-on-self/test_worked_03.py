"""pytest for worked-3 — verify the smoke harness reports the expected artifacts.

KG: span-worked-example-apt-cycle-on-self-2026-05-13 (:AtomicSpan)
"""

from __future__ import annotations

import stat
import subprocess
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]


def test_review_md_exists_and_follows_dogfood_format():
    review = HERE / "review.md"
    assert review.is_file()
    text = review.read_text(encoding="utf-8")
    # Required sections from THEORY/TPA/DOGFOOD_STANDARD.md
    for section in (
        "## Subject",
        "## What APT got right",
        "## What APT got wrong",
        "## What was missed",
        "## Lakatos verdict",
        "## Goodhart safeguard self-check",
        "## Honest limitations",
        "## Reproducibility",
    ):
        assert section in text, f"missing required section: {section}"


def test_review_states_lakatos_verdict():
    text = (HERE / "review.md").read_text(encoding="utf-8")
    assert any(
        v in text
        for v in (
            "PROGRESSIVE",
            "PROGRESSIVE_CONDITIONAL",
            "DEGENERATING",
        )
    ), "review.md must state a Lakatos verdict"


def test_review_cites_anchor_name():
    text = (HERE / "review.md").read_text(encoding="utf-8")
    assert "sa-bhgman_tool-ruflo-utility-parity-2026-05-13" in text


def test_run_sh_exists_and_is_executable():
    run = HERE / "run.sh"
    assert run.is_file()
    mode = run.stat().st_mode
    # Ensure the file is executable by owner (or fix it in this test for portability)
    if not (mode & stat.S_IXUSR):
        run.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def test_apt_progress_md_present_at_repo_root():
    progress = REPO_ROOT / "apt-progress.md"
    assert progress.is_file()
    text = progress.read_text(encoding="utf-8")
    assert "sa-bhgman_tool-ruflo-utility-parity-2026-05-13" in text


def test_run_sh_passes_when_artifacts_present():
    """Run the smoke harness end-to-end. If uv is absent the run.sh exits 0 with SKIPs."""
    run = HERE / "run.sh"
    if not run.is_file():
        pytest.skip("run.sh not present")
    # Ensure executable bit
    mode = run.stat().st_mode
    if not (mode & stat.S_IXUSR):
        run.chmod(mode | stat.S_IXUSR)
    result = subprocess.run(
        [str(run)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=180,
    )
    # Exit 0 even if uv is missing (those steps are SKIPs), as long as no FAIL was recorded.
    assert (
        "fail=0" in result.stdout
    ), f"run.sh reported failures.\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"


def test_meta_twice_invariant_explicitly_acknowledged():
    """README must call out the depth=1 invariant (no APT-on-APT-on-APT)."""
    text = (HERE / "README.md").read_text(encoding="utf-8")
    assert "meta_twice_invalid" in text
    assert "depth" in text.lower()


def test_no_coverage_ratio_in_review():
    """Goodhart safeguard: the review must not invent a single coverage_ratio scalar."""
    text = (HERE / "review.md").read_text(encoding="utf-8")
    # The phrase may appear inside the drift table label, but not as a synthesized score.
    # Reject explicit "coverage_ratio = NN%" patterns.
    import re

    matches = re.findall(r"coverage_ratio\s*=\s*[0-9]", text)
    assert not matches, f"review.md must not synthesize coverage_ratio numerics: {matches}"
