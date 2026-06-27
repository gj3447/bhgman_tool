"""하네스 3계층/4축 진단 엔진 TDD. # KG: bhgman-harness-diagnose-engine-2026-05-28"""

from __future__ import annotations

from engine.harness.harness import build_diagnosis_cypher, diagnose
from engine.harness.harness_models import Axis, Confidence, Presence, Tier


def _present(diag, axis):
    return next(f for f in diag.axes if f.axis is axis).presence is Presence.PRESENT


def _inferred(diag, axis):
    return next(f for f in diag.axes if f.axis is axis).presence is Presence.INFERRED


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
    # free-text feature 신호 = INFERRED(약신호, 반박가능) — primitive/explicit 의 PRESENT 와 구분.
    d = diagnose("an agent runtime with retry loops, guardrails, and an eval suite")
    assert _inferred(d, Axis.CORRECT)  # retry → feature 'retry'
    assert _inferred(d, Axis.CONSTRAIN)  # guardrails → feature 'permission'
    assert _inferred(d, Axis.VERIFY)  # eval → feature 'test-feedback'
    assert not _present(d, Axis.INFORM) and not _inferred(d, Axis.INFORM)  # no inform → UNKNOWN


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


def test_build_diagnosis_cypher_persist_shape():
    # --apply persist용 cypher+params (occam/hades 패턴). 순수 — 실행 안 함.
    d = diagnose("LangGraph with retry")
    cypher, params = build_diagnosis_cypher(d)
    assert "MERGE (h:HarnessDiagnosis {name: $subject})" in cypher
    assert params["subject"] == "LangGraph with retry"
    assert params["tier"] == "RUNTIME"
    assert "CORRECT" in params["inferred"]  # retry → CORRECT (free-text feature = inferred)
    assert (
        "CONSTRAIN" in params["axes"] and "VERIFY" in params["axes"]
    )  # LangGraph primitive = present
    assert isinstance(params["mcp"], bool)


def test_present_vs_inferred_provenance():
    """primitive 축=PRESENT(강), free-text feature 축=INFERRED(약), 각각 provenance 명시."""
    d = diagnose("LangGraph with a retry loop")
    constrain = next(f for f in d.axes if f.axis is Axis.CONSTRAIN)
    correct = next(f for f in d.axes if f.axis is Axis.CORRECT)
    assert constrain.presence is Presence.PRESENT and constrain.signal == "framework primitive"
    assert correct.presence is Presence.INFERRED and "feature" in correct.signal
    assert Axis.CONSTRAIN in d.present_axes and Axis.CORRECT in d.inferred_axes


def test_new_oss_coding_harnesses_are_ide_host():
    # 2026-06-27 OSS 확장: 코딩 하네스는 전부 L_IDE (IDE-host).
    for name in (
        "swe-agent",
        "openhands",
        "cline",
        "opencode",
        "goose",
        "codex",
        "gemini cli",
        "crush",
    ):
        assert diagnose(name).tier is Tier.IDE_HOST, name


def test_aider_now_has_verify_and_correct():
    # aider INFORM-only → +VERIFY(auto-test/lint) +CORRECT(diff/reflection) 정정.
    d = diagnose("Aider")
    assert _present(d, Axis.INFORM) and _present(d, Axis.VERIFY) and _present(d, Axis.CORRECT)


def test_every_known_framework_has_citation():
    """external grounding 불변식: 모든 KNOWN_FRAMEWORKS 엔트리는 1차 source citation 보유."""
    from engine.harness.harness import FRAMEWORK_CITATIONS, KNOWN_FRAMEWORKS

    missing = [k for k in KNOWN_FRAMEWORKS if k not in FRAMEWORK_CITATIONS]
    assert not missing, f"citation 누락: {missing}"
