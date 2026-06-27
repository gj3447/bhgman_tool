"""MCP tool — `harness_diagnose`.

KG: span-mcp-tool-harness-diagnose-2026-05-13 (:AtomicSpan)

Diagnoses where an agent/framework instance sits in the Harness 3-tier family
(L_MC / L_RT / L_IDE) and which of the 4 axes (Inform/Constrain/Verify/Correct)
each instance provides primitives for.

Production classifier wired (2026-06-27): this facade now delegates to the
deterministic core ``engine.harness.harness.diagnose()`` (KNOWN_FRAMEWORKS
name-match → keyword fallback → explicit-signal override) instead of the old
skeleton lookup table. The previous ``KNOWN_INSTANCES`` registry (axes always
"unknown") is removed — the single source of truth for instance→tier/axis
mapping is now ``KNOWN_FRAMEWORKS`` in the core engine.

Honesty: axis absence = "unknown" (부재 ≠ 능력 없음). tier label uses the
canonical SYMPOSIUM 3-tier names (KG: hub-harness-3tier) via ``_TIER_LABEL``.
"""

from __future__ import annotations

from typing import Any

from engine.harness.harness import diagnose, primary_source
from engine.harness.harness_models import HarnessDiagnosis, Presence, Tier

# 결정론 코어 Tier enum → 캐논 SYMPOSIUM 3-tier 라벨 (KG: hub-harness-3tier).
_TIER_LABEL: dict[Tier, str] = {
    Tier.IDE_HOST: "L_IDE",
    Tier.RUNTIME: "L_RT",
    Tier.MANAGED_CLOUD: "L_MC",
    Tier.UNKNOWN: "UNKNOWN",
}
_TIER_KIND: dict[Tier, str] = {
    Tier.IDE_HOST: "IDE-host coding harness",
    Tier.RUNTIME: "application agent runtime",
    Tier.MANAGED_CLOUD: "managed cloud control plane",
    Tier.UNKNOWN: "unrecognized — extend KNOWN_FRAMEWORKS or use manual diagnosis",
}
# Presence → report status. 부재는 'failing'이 아니라 'unknown' (정직: 신호 없음 ≠ 능력 없음).
# 'inferred' = free-text feature(9부품) 약신호 (반박 가능), 'present' = primitive/explicit 강신호.
_PRESENCE_STATUS: dict[Presence, str] = {
    Presence.PRESENT: "present",
    Presence.INFERRED: "inferred",
    Presence.UNKNOWN: "unknown",
}


def _strip_control(target: str) -> str:
    """제어문자 제거(공백 보존, case 보존). KG: harness-input-sanitize-2026-05-13.

    diagnose()가 내부에서 lower()로 매칭하므로 case는 안 내려도 됨 (subject 가독성 보존).
    """
    return "".join(c for c in target if c.isprintable() or c == " ").strip()


def _to_report(diag: HarnessDiagnosis) -> dict[str, Any]:
    """HarnessDiagnosis → MCP DiagnosisReport dict (직렬화)."""
    return {
        "target": diag.subject,
        "tier": _TIER_LABEL[diag.tier],
        "tier_confidence": diag.tier_confidence.value,
        "tier_reason": diag.tier_reason,
        "kind": _TIER_KIND[diag.tier],
        "axes": {f.axis.value.capitalize(): _PRESENCE_STATUS[f.presence] for f in diag.axes},
        "axis_signals": {f.axis.value.capitalize(): f.signal for f in diag.axes},
        "mcp_adapter": diag.mcp_adapter,
        "citation": primary_source(diag.subject),
        "summary": diag.summary,
        "notes": list(diag.notes),
    }


def harness_diagnose_impl(
    target: str, signals: dict[str, bool] | None = None
) -> dict[str, Any]:
    """Diagnose target's Harness placement + 4-axis profile (production classifier).

    Args:
        target: agent/framework/instance name (case-insensitive) or free-text desc.
        signals: optional explicit axis signals (e.g. {"verify": True}) — override.

    Returns:
        DiagnosisReport dict:
            {
                "target": str,
                "tier": "L_MC" | "L_RT" | "L_IDE" | "UNKNOWN",
                "tier_confidence": "HIGH" | "MEDIUM" | "LOW",
                "tier_reason": str,
                "kind": str,
                "axes": {Inform/Constrain/Verify/Correct -> "present"|"unknown"},
                "axis_signals": {axis -> provenance str},
                "mcp_adapter": bool,
                "citation": str | None,   # 1차 source URL
                "summary": str,
                "notes": list[str],
            }

    KG: span-mcp-tool-harness-diagnose-2026-05-13
    Verification: pytest test_mcp_server.py — target="ruflo" -> tier="L_RT".
    """
    return _to_report(diagnose(_strip_control(target), signals))


def register(mcp: Any) -> None:
    """Attach `harness_diagnose` tool to the FastMCP instance."""

    @mcp.tool()
    def harness_diagnose(
        target: str, signals: dict[str, bool] | None = None
    ) -> dict[str, Any]:
        """Diagnose where a framework/agent sits in the Harness 3-tier family.

        Args:
            target: framework or agent name (case-insensitive) or free-text description.
            signals: optional explicit axis signals to override the classifier.

        Returns: DiagnosisReport dict with tier (L_MC/L_RT/L_IDE) + 4-axis profile.
        """
        return harness_diagnose_impl(target, signals)
