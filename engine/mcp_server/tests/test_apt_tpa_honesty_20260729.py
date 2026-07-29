"""apt_phase_detect / tpa_drift_audit 정직성 회귀 봉인 (2026-07-29).

확정 버그 2건:
  B1 — apt_phase_detect: 'Cleanup'/'MetaReview' bare-word 가 wave 표/이력 언급만으로
       current_phase 를 오탐 (활성 repo 가 Cleanup 판정됐던 라이브 사고).
       + 증거 파일의 'Last Updated' 신선도 미공시.
  B4 — tpa_drift_audit: skip 매칭을 절대경로 parts 로 해서 .../build/<repo> 같은
       배치에서 전 파일이 조용히 스킵. + MAX_FILES 절단 침묵 + files_scanned 가
       skip 없는 제3의 walk 로 부정확.
"""

from __future__ import annotations

import json
from datetime import date

from engine.mcp_server.tools import tpa as tpa_module
from engine.mcp_server.tools.apt import apt_phase_detect_impl
from engine.mcp_server.tools.tpa import tpa_drift_audit_impl


# ── apt: context gate ───────────────────────────────────────────────────────


def test_apt_cleanup_bare_mention_not_evidence(tmp_path):
    (tmp_path / "apt-progress.md").write_text(
        "# APT Progress\n## Status: active\n\n"
        "| Wave 11 | pre-commit 4-ratchet local gate |\n"
        "Cleanup phase mentioned in history only.\n"
    )
    r = apt_phase_detect_impl(str(tmp_path))
    assert r["phases_detected"]["Cleanup"] is False
    assert r["current_phase"] != "Cleanup"


def test_apt_cleanup_with_context_detected(tmp_path):
    (tmp_path / "apt-progress.md").write_text("## Phase 6 Cleanup in progress\n")
    r = apt_phase_detect_impl(str(tmp_path))
    assert r["phases_detected"]["Cleanup"] is True
    assert r["current_phase"] == "Cleanup"


def test_apt_metareview_with_context_wins(tmp_path):
    (tmp_path / "apt-progress.md").write_text(
        "SCW implementation complete\n## MetaReview in progress\n"
    )
    r = apt_phase_detect_impl(str(tmp_path))
    assert r["phases_detected"]["MetaReview"] is True
    assert r["current_phase"] == "MetaReview"


# ── apt: staleness ──────────────────────────────────────────────────────────


def test_apt_stale_evidence_caps_confidence(tmp_path):
    (tmp_path / "apt-progress.md").write_text(
        "## Last Updated: 2020-01-01\nSCW implementation complete\n"
    )
    r = apt_phase_detect_impl(str(tmp_path))
    assert r["progress_last_updated"] == "2020-01-01"
    assert r["stale"] is True
    assert r["confidence"] == "INFERRED"
    assert r["current_phase"] == "SCW"  # 증거 자체는 보존 — 신선도만 강등


def test_apt_fresh_evidence_not_stale(tmp_path):
    (tmp_path / "apt-progress.md").write_text(
        f"## Last Updated: {date.today().isoformat()}\nSCW implementation complete\n"
    )
    r = apt_phase_detect_impl(str(tmp_path))
    assert r["stale"] is False
    assert r["confidence"] == "EXTRACTED"


def test_apt_no_stamp_freshness_unmeasured(tmp_path):
    (tmp_path / "apt-progress.md").write_text("SCW implementation complete\n")
    r = apt_phase_detect_impl(str(tmp_path))
    assert r["progress_last_updated"] is None
    assert r["evidence_age_days"] is None
    assert r["stale"] is False


# ── tpa: root-relative skip ─────────────────────────────────────────────────


def test_tpa_repo_under_build_dir_not_blanked(tmp_path):
    root = tmp_path / "build" / "repo"
    root.mkdir(parents=True)
    (root / "a.py").write_text("# KG: x-1\n")
    r = tpa_drift_audit_impl(str(root))
    assert r["kg_refs_total"] == 1
    assert r["files_scanned"] == 1


def test_tpa_intree_skip_dirs_still_skipped(tmp_path):
    (tmp_path / "ok.py").write_text("# KG: a\n")
    skip = tmp_path / "node_modules"
    skip.mkdir()
    (skip / "x.py").write_text("# KG: b\n")
    r = tpa_drift_audit_impl(str(tmp_path))
    assert r["files_scanned"] == 1
    assert r["kg_refs_total"] == 1


# ── tpa: truncation honesty ─────────────────────────────────────────────────


def test_tpa_truncation_disclosed(tmp_path, monkeypatch):
    for i in range(5):
        (tmp_path / f"f{i}.py").write_text(f"# KG: id-{i}\n")
    monkeypatch.setattr(tpa_module, "MAX_FILES", 2)
    r = tpa_drift_audit_impl(str(tmp_path))
    assert r["truncated"] is True
    assert r["files_scanned"] == 2


def test_tpa_no_truncation_when_within_budget(tmp_path):
    (tmp_path / "a.py").write_text("# KG: id-1\n")
    r = tpa_drift_audit_impl(str(tmp_path))
    assert r["truncated"] is False
    assert r["files_scanned"] == 1


# ── tpa: label rot still detected through the merged single-walk scan ───────


def test_tpa_label_rot_via_merged_scan(tmp_path):
    (tmp_path / "a.py").write_text("# KG: old-id  # DEPRECATED 2024-01\n")
    r = tpa_drift_audit_impl(str(tmp_path))
    assert r["drift_counts"]["LabelRot"] == 1
    assert r["drift_examples"]["LabelRot"][0]["file"] == "a.py"
    assert r["kg_refs_total"] == 1  # 같은 walk 에서 ref 도 수집됨
