"""pytest for MCP server skeleton.

KG: span-mcp-server-skeleton-fastmcp-2026-05-13 (:AtomicSpan)
APT v26.1 SCW verification gate.

These tests exercise the tool implementations *directly* (without launching the
MCP loop). The actual stdio-loop test requires fastmcp installed; tests here
work without it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import sys

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent))  # mcp_server is at engine/mcp_server/

from mcp_server.tools.longinus import longinus_audit_impl, CONFIDENCE_TIERS
from mcp_server.tools.harness import harness_diagnose_impl
from mcp_server.server import list_registered_tool_names


# ─── server scaffold ────────────────────────────────────────────────────


def test_list_registered_tools_non_empty():
    tools = list_registered_tool_names()
    assert len(tools) >= 2
    assert "longinus_audit" in tools
    assert "harness_diagnose" in tools


# ─── longinus_audit tool ────────────────────────────────────────────────


def test_longinus_audit_confidence_threshold_validation():
    with pytest.raises(ValueError, match="confidence_threshold"):
        longinus_audit_impl(str(HERE), confidence_threshold="NOT_A_TIER")


def test_longinus_audit_accepts_all_three_tiers():
    for tier in CONFIDENCE_TIERS:
        result = longinus_audit_impl(str(HERE), confidence_threshold=tier)
        assert result["confidence_threshold"] == tier


def test_longinus_audit_rejects_nonexistent_path():
    with pytest.raises(FileNotFoundError):
        longinus_audit_impl("/nonexistent/path/should/not/exist")


def test_longinus_audit_on_worked_example_finds_drift(tmp_path):
    """Reuse the worked example: it has a known KG ref + simulated KG with Orphan possible."""
    # Set up a tiny repo with a KG ref + simulated KG
    src = tmp_path / "sample.py"
    src.write_text(
        "def foo(): pass  # KG: lesson-known-2026-05-13\n"
        "def bar(): pass  # KG: lesson-orphan-2026-05-13\n"
    )
    (tmp_path / "kg_simulated.json").write_text(
        '{"lesson-known-2026-05-13": {"expected_signature": "foo() -> Any"}}'
    )
    report = longinus_audit_impl(str(tmp_path))
    assert report["kg_refs_found"] == 2
    assert any(
        d["drift_type"] == "Missing" and d["sourceId"] == "lesson-orphan-2026-05-13"
        for d in report["drift_records"]
    )
    assert "lesson-known-2026-05-13" not in [d.get("sourceId") for d in report["drift_records"]]
    assert report["engine"] == "engine.longinus_engine.LonginusEngine"


def test_longinus_audit_no_kg_simulated_returns_empty_drifts(tmp_path):
    src = tmp_path / "x.py"
    src.write_text("def a(): pass  # KG: lesson-a\n")
    report = longinus_audit_impl(str(tmp_path))
    assert report["kg_refs_found"] == 1
    assert report["drift_records"] == []


# ─── harness_diagnose tool ──────────────────────────────────────────────


def test_harness_diagnose_ruflo_returns_LRT():
    result = harness_diagnose_impl("ruflo")
    assert result["tier"] == "L_RT"


def test_harness_diagnose_case_insensitive():
    a = harness_diagnose_impl("RUFLO")
    b = harness_diagnose_impl("ruflo")
    assert a["tier"] == b["tier"] == "L_RT"


def test_harness_diagnose_cursor_returns_LIDE():
    result = harness_diagnose_impl("Cursor")
    assert result["tier"] == "L_IDE"


def test_harness_diagnose_anthropic_managed_returns_LMC():
    result = harness_diagnose_impl("Anthropic Managed Agents")
    assert result["tier"] == "L_MC"


def test_harness_diagnose_unknown_target_returns_UNKNOWN():
    # 키워드-프리 + 이름 미매치 → 진짜 UNKNOWN. (구 'framework' 포함 타깃은 production 분류기가
    # RUNTIME 키워드로 잡으므로 skeleton 행동을 인코딩하지 않도록 키워드 없는 타깃 사용.)
    result = harness_diagnose_impl("totally-fictional-xyz-2026")
    assert result["tier"] == "UNKNOWN"


def test_harness_diagnose_axes_keys_present():
    """4-axis model must always have all 4 axes in the output schema."""
    result = harness_diagnose_impl("cursor")
    assert set(result["axes"].keys()) == {"Inform", "Constrain", "Verify", "Correct"}


def test_known_frameworks_map_to_valid_tier_labels():
    """통합 registry: 모든 KNOWN_FRAMEWORKS 엔트리가 캐논 L_ tier 라벨로 진단돼야 한다.

    (구 test_known_instances_all_have_valid_tier 대체 — facade가 별도 KNOWN_INSTANCES를
    버리고 코어 KNOWN_FRAMEWORKS를 단일 SoT로 쓰도록 배선됨, 2026-06-27.)
    """
    from engine.harness.harness import KNOWN_FRAMEWORKS

    valid = {"L_MC", "L_RT", "L_IDE"}
    for name in KNOWN_FRAMEWORKS:
        result = harness_diagnose_impl(name)
        assert result["tier"] in valid, f"{name} -> {result['tier']!r}"
        assert set(result["axes"].keys()) == {"Inform", "Constrain", "Verify", "Correct"}
