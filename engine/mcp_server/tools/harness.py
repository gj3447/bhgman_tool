"""MCP tool — `harness_diagnose`.

KG: span-mcp-tool-harness-diagnose-2026-05-13 (:AtomicSpan)

Diagnoses where an agent/framework instance sits in the Harness 3-tier family
(L_MC / L_RT / L_IDE) and which of the 4 axes (Inform/Constrain/Verify/Correct)
is currently failing.

Skeleton stage: lookup table of known frameworks. Production classifier in Phase 2.
"""

from __future__ import annotations

from typing import Any


# Known framework registry — extend as new instances are absorbed.
# KG: hub-harness-3tier (canon in SYMPOSIUM — Harness 3-tier family hub)
KNOWN_INSTANCES: dict[str, dict[str, Any]] = {
    "cursor": {"tier": "L_IDE", "kind": "IDE-host coding harness"},
    "claude code": {"tier": "L_IDE", "kind": "IDE-host coding harness"},
    "claude-code": {"tier": "L_IDE", "kind": "IDE-host coding harness"},
    "aider": {"tier": "L_IDE", "kind": "IDE-host coding harness"},
    "swe-agent": {"tier": "L_IDE", "kind": "IDE-host coding harness"},
    "cline": {"tier": "L_IDE", "kind": "IDE-host coding harness"},
    "openhands": {"tier": "L_IDE", "kind": "IDE-host coding harness"},
    "github copilot": {"tier": "L_IDE", "kind": "IDE-host coding harness"},
    "langgraph": {"tier": "L_RT", "kind": "application agent runtime"},
    "crewai": {"tier": "L_RT", "kind": "application agent runtime"},
    "autogen": {"tier": "L_RT", "kind": "application agent runtime"},
    "google adk": {"tier": "L_RT", "kind": "application agent runtime"},
    "adk": {"tier": "L_RT", "kind": "application agent runtime"},
    "ruflo": {"tier": "L_RT", "kind": "application agent runtime"},
    "claude-flow": {"tier": "L_RT", "kind": "application agent runtime"},
    "anthropic managed agents": {"tier": "L_MC", "kind": "managed cloud control plane"},
    "openai assistants": {"tier": "L_MC", "kind": "managed cloud control plane"},
    "vertex ai agent engine": {"tier": "L_MC", "kind": "managed cloud control plane"},
    "bedrock agents": {"tier": "L_MC", "kind": "managed cloud control plane"},
}


def _sanitize_target(target: str) -> str:
    """Strip control chars + lowercase for lookup. KG: harness-input-sanitize-2026-05-13."""
    cleaned = "".join(c for c in target if c.isprintable() and not c.isspace() or c == " ")
    return cleaned.strip().lower()


def harness_diagnose_impl(target: str) -> dict[str, Any]:
    """Diagnose target's Harness placement + 4-axis status (skeleton).

    Args:
        target: name of the agent/framework/instance (case-insensitive)

    Returns:
        DiagnosisReport dict:
            {
                "target": str,
                "tier": "L_MC" | "L_RT" | "L_IDE" | "UNKNOWN",
                "kind": str,
                "axes": {Inform, Constrain, Verify, Correct} -> "ok"|"unknown"|"failing",
                "note": str,
            }

    KG: span-mcp-tool-harness-diagnose-2026-05-13
    Verification: pytest test_mcp_tool_harness.py with target="ruflo" -> tier=L_RT
    """
    key = _sanitize_target(target)
    found = KNOWN_INSTANCES.get(key)
    if found:
        return {
            "target": target,
            "tier": found["tier"],
            "kind": found["kind"],
            "axes": {
                "Inform": "unknown",
                "Constrain": "unknown",
                "Verify": "unknown",
                "Correct": "unknown",
            },
            "note": (
                f"Skeleton classifier: known instance, placed at {found['tier']}. "
                "Per-axis status assessment requires a production classifier "
                "(Phase 2 sprint). Use docs/02-concepts/harness.md for manual diagnosis."
            ),
        }
    return {
        "target": target,
        "tier": "UNKNOWN",
        "kind": "unrecognized — extend KNOWN_INSTANCES or use manual diagnosis",
        "axes": {
            "Inform": "unknown",
            "Constrain": "unknown",
            "Verify": "unknown",
            "Correct": "unknown",
        },
        "note": (
            "Target not in skeleton registry. Production classifier will use "
            "feature extraction (orchestration model, state location, IDE vs program-level) "
            "rather than lookup. Contribute via PR if you know the placement."
        ),
    }


def register(mcp: Any) -> None:
    """Attach `harness_diagnose` tool to the FastMCP instance."""

    @mcp.tool()
    def harness_diagnose(target: str) -> dict[str, Any]:
        """Diagnose where a framework/agent sits in the Harness 3-tier family.

        Args:
            target: framework or agent name (case-insensitive)

        Returns: DiagnosisReport dict with tier (L_MC/L_RT/L_IDE) + 4-axis status.
        """
        return harness_diagnose_impl(target)
