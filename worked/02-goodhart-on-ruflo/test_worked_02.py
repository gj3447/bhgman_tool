"""pytest for worked example 2 (Goodhart detection on ruflo).

KG: span-worked-example-goodhart-on-ruflo-2026-05-13 (:AtomicSpan)
APT v26.1 SCW verification gate.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


HERE = Path(__file__).parent
ANALYZE_PY = HERE / "analyze.py"


def _run_analyze(args: list[str] | None = None) -> subprocess.CompletedProcess:
    cmd = [sys.executable, str(ANALYZE_PY)] + (args or [])
    return subprocess.run(cmd, capture_output=True, text=True, timeout=30)


def test_analyze_runs_on_default_snapshot() -> None:
    result = _run_analyze()
    assert result.returncode in (0, 1), f"unexpected exit: {result.returncode}\n{result.stderr}"
    assert "Goodhart Antipattern Audit" in result.stdout


def test_ruflo_snapshot_returns_degenerating() -> None:
    result = _run_analyze()
    assert "DEGENERATING" in result.stdout
    assert result.returncode == 1


def test_all_three_lenses_detected_on_ruflo() -> None:
    result = _run_analyze()
    assert "[Lens 1] lens-goodhart-metric-as-marketing — DETECTED" in result.stdout
    assert "[Lens 2] lens-enumeration-inflation — DETECTED" in result.stdout
    assert "[Lens 3] lens-self-improving-no-safeguard — DETECTED" in result.stdout


def test_summary_count_three_of_three() -> None:
    result = _run_analyze()
    assert "ErrorPatterns detected: 3 / 3" in result.stdout


def test_bhgman_readme_self_application_progressive() -> None:
    """When applied to our own README, should NOT show 3 detections.

    bhgman README explicitly mentions Goodhart/Cherns/Lakatos and responsibility_split,
    so the lenses' safeguard markers should fire.
    """
    bhgman_readme = HERE.parent.parent / "README.md"
    result = _run_analyze([str(bhgman_readme)])
    assert "PROGRESSIVE" in result.stdout, (
        f"bhgman README should be PROGRESSIVE (or PROGRESSIVE_CONDITIONAL).\n"
        f"Output:\n{result.stdout}"
    )
    # Exit code 0 means non-DEGENERATING
    assert result.returncode == 0


def test_nonexistent_path_returns_error() -> None:
    result = _run_analyze(["/nonexistent/path/xxx.md"])
    assert result.returncode == 2
    assert "not found" in result.stderr.lower()


def test_lens_detection_individual_module_callable() -> None:
    """Detector functions are importable and callable."""
    sys.path.insert(0, str(HERE))
    try:
        from analyze import (
            lens_1_goodhart_metric_marketing,
            lens_2_enumeration_inflation,
            lens_3_self_improving_no_safeguard,
            detect_all,
        )
        text = "100+ agents and 84.8% SWE-Bench solve rate with SONA self-learning"
        r1 = lens_1_goodhart_metric_marketing(text)
        r2 = lens_2_enumeration_inflation(text)
        r3 = lens_3_self_improving_no_safeguard(text)
        assert r1["detected"]
        assert r2["detected"]
        assert r3["detected"]
        full = detect_all(text)
        assert full["lakatos_verdict"] == "DEGENERATING"
    finally:
        sys.path.pop(0)
