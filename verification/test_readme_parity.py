"""Test the README structural-parity guard (bin/check_readme_parity.py)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "check_readme_parity",
    Path(__file__).resolve().parent.parent / "bin" / "check_readme_parity.py",
)
assert _SPEC and _SPEC.loader
_MOD = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MOD)


def test_section_count_counts_only_h2_h3(tmp_path):
    f = tmp_path / "R.md"
    f.write_text("# Title\n## A\ntext\n### B\n## C\n#### deeper (not counted)\n", encoding="utf-8")
    assert _MOD.section_count(f) == 3  # ## A, ### B, ## C — h1 and h4 excluded


def test_check_reports_drift_when_translation_shorter(tmp_path):
    (tmp_path / "README.md").write_text("## A\n## B\n## C\n", encoding="utf-8")
    (tmp_path / "README.ko-KR.md").write_text("## A\n## B\n", encoding="utf-8")  # -1
    drifted = _MOD.check(tmp_path)
    assert "README.ko-KR.md" in drifted


def test_check_no_drift_when_parity(tmp_path):
    (tmp_path / "README.md").write_text("## A\n## B\n", encoding="utf-8")
    (tmp_path / "README.ko-KR.md").write_text(
        "## 가\n## 나\n", encoding="utf-8"
    )  # translated titles, same count
    assert _MOD.check(tmp_path) == []
