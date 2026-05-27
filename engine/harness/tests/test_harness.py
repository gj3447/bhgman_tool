"""하네스 3계층/4축 진단 엔진 TDD. # KG: bhgman-harness-diagnose-engine-2026-05-28"""

from __future__ import annotations

from harness import diagnose
from harness_models import Axis, Confidence, Presence, Tier


def _present(diag, axis):
    return next(f for f in diag.axes if f.axis is axis).presence is Presence.PRESENT


def test_known_runtime_framework_high_confidence():
    d = diagnose("LangGraph")
    assert d.tier is Tier.RUNTIME
    assert d.tier_confidence is Confidence.HIGH
    assert _present(d, Axis.CONSTRAIN) and _present(d, Axis.VERIFY)  # graph + checkpoint primitives


def test_known_ide_host():
    assert diagnose("Cursor").tier is Tier.IDE_HOST
    assert diagnose("Claude Code").tier is Tier.IDE_HOST


def test_known_managed_cloud():
    assert diagnose("OpenAI Assistants API").tier is Tier.MANAGED_CLOUD
    assert diagnose("Anthropic Managed Agents").tier is Tier.MANAGED_CLOUD


def test_keyword_fallback_medium():
    d = diagnose("my custom orchestration framework")
    assert d.tier is Tier.RUNTIME
    assert d.tier_confidence is Confidence.MEDIUM
    assert "keyword" in d.tier_reason


def test_unknown_low():
    d = diagnose("a fuzzy thing")
    assert d.tier is Tier.UNKNOWN
    assert d.tier_confidence is Confidence.LOW


def test_axis_signal_extraction_from_text():
    d = diagnose("an agent runtime with retry loops, guardrails, and an eval suite")
    assert _present(d, Axis.CORRECT)  # retry
    assert _present(d, Axis.CONSTRAIN)  # guardrails
    assert _present(d, Axis.VERIFY)  # eval
    assert not _present(d, Axis.INFORM)  # no inform signal → UNKNOWN


def test_explicit_signals_override():
    d = diagnose("Cursor", signals={"verify": True, "inform": False})
    assert _present(d, Axis.VERIFY)  # explicit True
    assert not _present(d, Axis.INFORM)  # explicit False beats framework primitive


def test_mcp_adapter_detection():
    assert diagnose("LangGraph with an MCP adapter").mcp_adapter is True
    assert diagnose("Cursor").mcp_adapter is False


def test_summary_shape():
    d = diagnose("CrewAI")
    assert d.summary.startswith("harness[CrewAI]: tier=RUNTIME(HIGH)")
