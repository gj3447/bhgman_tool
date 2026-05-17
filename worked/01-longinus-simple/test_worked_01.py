"""pytest verification for worked example 1 (Longinus drift audit).

KG: span-worked-example-longinus-simple-2026-05-13 (:AtomicSpan)
APT v26.1 SCW verification gate: pytest passes ⇒ AtomicSpan validated.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


HERE = Path(__file__).parent


def test_run_py_executable() -> None:
    """run.py runs without import errors and exits with status 1 (drift present)."""
    result = subprocess.run(
        [sys.executable, str(HERE / "run.py")],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert (
        result.returncode == 1
    ), f"expected exit 1 (drift), got {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"


def test_output_reports_one_drift() -> None:
    result = subprocess.run(
        [sys.executable, str(HERE / "run.py")],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert "Drifts detected: 1" in result.stdout


def test_output_identifies_sigmismatch() -> None:
    result = subprocess.run(
        [sys.executable, str(HERE / "run.py")],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert "[SigMismatch" in result.stdout
    assert "lesson-validate-email-2026-05-13" in result.stdout
    assert "PutGet" in result.stdout


def test_output_does_not_falsely_report_clean_refs() -> None:
    result = subprocess.run(
        [sys.executable, str(HERE / "run.py")],
        capture_output=True,
        text=True,
        timeout=30,
    )
    # The two clean refs (greet, add) should NOT appear in drift records
    drift_section = (
        result.stdout.split("Drifts detected:")[1] if "Drifts detected:" in result.stdout else ""
    )
    assert "lesson-greet-user-2026-05-13" not in drift_section
    assert "lesson-add-numbers-2026-05-13" not in drift_section
