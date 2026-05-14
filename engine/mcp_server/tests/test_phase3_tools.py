"""pytest for Phase 3 MCP tools — apt_phase_detect / taliban_lens_check / tpa_drift_audit.

KG: span-mcp-tool-{apt,taliban,tpa}-2026-05-13
APT v26.1 SCW verification gate — Phase 3 L1 branch C.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent))  # engine/

from mcp_server.tools.apt import APT_PHASES, apt_phase_detect_impl
from mcp_server.tools.taliban import LENS_REGISTRY, taliban_lens_check_impl
from mcp_server.tools.tpa import DRIFT_TYPES, tpa_drift_audit_impl
from mcp_server.server import list_registered_tool_names


# ─── server scaffold (expanded 2 → 5 native, then +4 SYMPOSIUM-absorbed → 9) ──


def test_native_tools_registered():
    """Phase 3 cohort: 5 native diagnostic tools must remain registered."""
    tools = set(list_registered_tool_names())
    native = {
        "longinus_audit", "harness_diagnose",
        "apt_phase_detect", "taliban_lens_check", "tpa_drift_audit",
    }
    assert native.issubset(tools), f"native cohort missing: {native - tools}"


def test_symposium_absorbed_tools_registered():
    """Wave 7 P2-A cohort: 4 SYMPOSIUM-absorbed dispatch tools must be present.

    KG: rs-mcp-symposium-absorb-2026-05-14
    """
    tools = set(list_registered_tool_names())
    absorbed = {"apt_dispatch", "kg_query", "gate_check", "seed_germinate"}
    assert absorbed.issubset(tools), f"SYMPOSIUM cohort missing: {absorbed - tools}"


# ─── apt_phase_detect ──────────────────────────────────────────────────


def test_apt_phase_detect_rejects_missing_path(tmp_path):
    with pytest.raises(FileNotFoundError):
        apt_phase_detect_impl(str(tmp_path / "nope"))


def test_apt_phase_detect_returns_unknown_for_bare_dir(tmp_path):
    result = apt_phase_detect_impl(str(tmp_path))
    assert result["current_phase"] == "unknown"
    assert result["confidence"] == "AMBIGUOUS"
    assert result["evidence_sources"] == []


def test_apt_phase_detect_picks_up_progress_md(tmp_path):
    (tmp_path / "apt-progress.md").write_text(
        "# APT Progress: sample\n"
        "## Anchor: sa-sample\n\n"
        "### In Progress\n- SPAN_x: SP decomposition in progress\n"
    )
    result = apt_phase_detect_impl(str(tmp_path))
    assert result["confidence"] == "EXTRACTED"
    assert result["phases_detected"]["SP"] is True
    assert result["current_phase"] == "SP"
    assert "apt-progress.md" in result["evidence_sources"]


def test_apt_phase_detect_latest_phase_wins(tmp_path):
    (tmp_path / "apt-progress.md").write_text(
        "SA complete\nSP decomposition\nSCW implementation complete\nMetaReview\n"
    )
    result = apt_phase_detect_impl(str(tmp_path))
    # All four phase markers present — MetaReview is the latest in APT_PHASES order
    assert result["current_phase"] == "MetaReview"
    assert all(result["phases_detected"][p] for p in ("SA", "SP", "SCW", "MetaReview"))


def test_apt_phase_detect_reads_feature_spans(tmp_path):
    (tmp_path / "apt-progress.md").write_text("SA bootstrap\n")
    (tmp_path / "feature-spans.json").write_text(json.dumps({
        "anchor": "sa-x",
        "spans": [
            {"name": "SPAN_X_ROOT", "depth": 0, "status": "open"},
            {"name": "SPAN_X_BRANCH_A", "depth": 1, "status": "open"},
        ],
    }))
    result = apt_phase_detect_impl(str(tmp_path))
    names = [s["name"] for s in result["spans_summary"]]
    assert names == ["SPAN_X_ROOT", "SPAN_X_BRANCH_A"]


def test_apt_phases_canonical_order():
    assert APT_PHASES == ("SA", "SP", "ST", "SCW", "Cleanup", "MetaReview")


# ─── taliban_lens_check ────────────────────────────────────────────────


def test_taliban_lens_registry_has_four_lenses():
    assert set(LENS_REGISTRY) == {"constitutional", "mathematical", "solid", "longinus"}


def test_taliban_lens_check_single_returns_axes():
    result = taliban_lens_check_impl("constitutional")
    assert result["mode"] == "single"
    assert result["lens_count"] == 9
    assert len(result["axes"]) == 9
    assert "correctness" in result["axes"]
    assert "hr12_note" in result


def test_taliban_lens_check_solid_axes_match_canon():
    result = taliban_lens_check_impl("solid")
    assert result["axes"] == ["SRP", "OCP", "LSP", "ISP", "DIP"]


def test_taliban_lens_check_longinus_seven_layer():
    result = taliban_lens_check_impl("longinus")
    assert result["lens_count"] == 7
    assert len(result["axes"]) == 7


def test_taliban_lens_check_unknown_raises():
    with pytest.raises(ValueError, match="unknown lens"):
        taliban_lens_check_impl("nope")


def test_taliban_lens_check_rejects_non_string():
    with pytest.raises(TypeError):
        taliban_lens_check_impl(123)  # type: ignore[arg-type]


def test_taliban_lens_check_all_mode_union():
    result = taliban_lens_check_impl("all")
    assert result["mode"] == "union"
    assert len(result["lenses"]) == 4
    enumerated_axes = sum(len(L["axes"]) for L in result["lenses"])
    # mathematical lens has no enumerated axes; union should equal sum of the other three
    # (no overlap in canonical naming)
    assert result["union_axis_count_partial"] == enumerated_axes


def test_taliban_lens_check_no_scalar_score():
    """Goodhart safeguard: tool must not emit a flat numeric quality score."""
    result = taliban_lens_check_impl("constitutional")
    assert "coverage_score" not in result
    assert "quality_score" not in result


# ─── tpa_drift_audit ───────────────────────────────────────────────────


def test_tpa_drift_audit_rejects_missing_path(tmp_path):
    with pytest.raises(FileNotFoundError):
        tpa_drift_audit_impl(str(tmp_path / "nope"))


def test_tpa_drift_audit_clean_repo_zero_drift(tmp_path):
    (tmp_path / "a.py").write_text("# KG: known-id-1\nprint('ok')\n")
    (tmp_path / "kg_simulated.json").write_text(json.dumps(["known-id-1"]))
    result = tpa_drift_audit_impl(str(tmp_path))
    assert result["kg_simulated_present"] is True
    assert result["drift_counts"]["Orphan"] == 0


def test_tpa_drift_audit_detects_orphan_kg_refs(tmp_path):
    (tmp_path / "a.py").write_text("# KG: not-in-canon\n")
    (tmp_path / "b.py").write_text("# KG: real-thing\n")
    (tmp_path / "kg_simulated.json").write_text(json.dumps(["real-thing"]))
    result = tpa_drift_audit_impl(str(tmp_path))
    assert result["drift_counts"]["Orphan"] == 1
    assert result["drift_examples"]["Orphan"][0]["kg_id"] == "not-in-canon"


def test_tpa_drift_audit_detects_label_rot(tmp_path):
    (tmp_path / "a.py").write_text("# KG: old-id  # DEPRECATED 2024-01\n")
    result = tpa_drift_audit_impl(str(tmp_path))
    assert result["drift_counts"]["LabelRot"] >= 1


def test_tpa_drift_audit_deferred_when_no_kg_sim(tmp_path):
    (tmp_path / "a.py").write_text("# KG: anything\n")
    result = tpa_drift_audit_impl(str(tmp_path))
    assert result["kg_simulated_present"] is False
    assert result["drift_counts"]["Orphan"] == 0
    # Missing / SigMismatch / PatternDiv are skeleton-deferred:
    assert "Missing" in result["deferred_drift_types"]
    assert "SigMismatch" in result["deferred_drift_types"]
    assert "PatternDiv" in result["deferred_drift_types"]


def test_tpa_drift_types_canonical():
    assert DRIFT_TYPES == ("Missing", "Orphan", "SigMismatch", "PatternDiv", "LabelRot")


def test_tpa_drift_audit_no_coverage_ratio(tmp_path):
    """Goodhart safeguard: tool must not synthesise a coverage_ratio scalar."""
    (tmp_path / "a.py").write_text("# KG: x\n")
    result = tpa_drift_audit_impl(str(tmp_path))
    assert "coverage_ratio" not in result
    assert "quality_score" not in result
