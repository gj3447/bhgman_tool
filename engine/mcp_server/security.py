"""MCP/dispatch security audit — lethal-trifecta + prompt-injection (Wave 12, 2026-05-25).

Addresses PROM 16 ``prom16-ai-dev-tools-2026-05-25`` lever ④ (cross-cut risk C6:
the "lethal trifecta", Simon Willison 2025 — *private-data access* + *exposure to
untrusted content* + *exfiltration channel* = unconditional prompt-injection risk).

DESIGN — non-intrusive by default (mirrors ``dispatch_audit`` warn-mode +
``DISPATCH_PATTERN_HARD_BLOCK`` opt-in, and the observation-only pre_tool hooks):

    - **AUDIT mode (default)**: scan + log detections, **never block**. Zero impact
      on normal Claude Code development / dispatch / MCP tool use.
    - **ENFORCE mode (opt-in via env ``BHGMAN_SECURITY_ENFORCE=1``)**: HIGH-severity
      detections flip the verdict to DENY (caller may raise :class:`SecurityViolation`).

All detection logic is **pure + heuristic** (Goodhart-honest: defense-in-depth,
NOT a guarantee — a determined injection can evade regex heuristics; the
capability-composition trifecta check is the structural backstop). Importable and
testable without ``fastmcp`` / any runtime.

# KG: finding-aidev-mcp-security-trifecta-2026-05-25 (PROM 16 lever ④)
# KG: finding_aidev_CS4 (lethal trifecta source finding)
"""

from __future__ import annotations

import enum
import os
import re
from typing import Any, Optional

from pydantic import BaseModel, Field


class Capability(str, enum.Enum):
    """The three legs of the lethal trifecta (Willison 2025)."""

    READS_PRIVATE_DATA = "reads_private_data"
    FETCHES_UNTRUSTED = "fetches_untrusted_content"
    CAN_EXFILTRATE = "can_exfiltrate"


# Per-tool capability tags for the registered MCP toolset. Conservative + honest:
# the current bhgman_tool toolset is read/dispatch-oriented with NO tool that can
# POST data to an arbitrary external sink, so it sits at 2/3 of the trifecta.
# Adding any tool with CAN_EXFILTRATE (e.g. a generic http-POST / email / webhook
# tool) would COMPLETE the trifecta — :func:`audit_toolset` flags that transition.
TOOL_CAPABILITIES: dict[str, frozenset[Capability]] = {
    "longinus_audit": frozenset({Capability.READS_PRIVATE_DATA}),
    "harness_diagnose": frozenset({Capability.READS_PRIVATE_DATA}),
    "apt_phase_detect": frozenset({Capability.READS_PRIVATE_DATA}),
    "taliban_lens_check": frozenset({Capability.READS_PRIVATE_DATA}),
    "tpa_drift_audit": frozenset({Capability.READS_PRIVATE_DATA}),
    "prometheus_research": frozenset({Capability.READS_PRIVATE_DATA}),
    "kg_query": frozenset({Capability.READS_PRIVATE_DATA}),
    "gate_check": frozenset({Capability.READS_PRIVATE_DATA}),
    "seed_germinate": frozenset({Capability.READS_PRIVATE_DATA}),
    # apt_dispatch spawns subagents that may pull web / untrusted content.
    "apt_dispatch": frozenset({Capability.FETCHES_UNTRUSTED}),
}


class SecurityMode(str, enum.Enum):
    AUDIT = "AUDIT"  # default — log only, never block
    ENFORCE = "ENFORCE"  # opt-in — HIGH detection ⇒ DENY


def current_mode() -> SecurityMode:
    """Read mode from env ``BHGMAN_SECURITY_ENFORCE`` (default AUDIT).

    AUDIT (default) guarantees zero impact on Claude Code development: detections
    are reported but never block a tool call or dispatch.
    """
    val = os.environ.get("BHGMAN_SECURITY_ENFORCE", "").strip().lower()
    return SecurityMode.ENFORCE if val in {"1", "true", "yes", "on"} else SecurityMode.AUDIT


# ─── prompt-injection heuristics (curated; NOT exhaustive) ───────────────

# (regex, severity, label). HIGH = instruction-override / system-impersonation /
# tool-poisoning; MEDIUM = exfiltration-shaped content. Heuristic detector —
# evasion is possible; pair with the structural trifecta check.
_INJECTION_PATTERNS: list[tuple[re.Pattern[str], str, str]] = [
    (
        re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+(instructions|prompts?)", re.I),
        "HIGH",
        "instruction_override",
    ),
    (
        re.compile(r"disregard\s+(the\s+)?(above|previous|system)", re.I),
        "HIGH",
        "instruction_override",
    ),
    (re.compile(r"\byou\s+are\s+now\b", re.I), "HIGH", "role_reassign"),
    (re.compile(r"new\s+(system\s+)?instructions?\s*:", re.I), "HIGH", "instruction_inject"),
    (re.compile(r"</?(system|assistant|developer)>", re.I), "HIGH", "role_marker_inject"),
    (
        re.compile(r"\b(developer\s+mode|jailbreak|do\s+anything\s+now|\bDAN\b)", re.I),
        "HIGH",
        "jailbreak",
    ),
    (
        re.compile(r"do\s+not\s+(tell|inform|mention)\s+(the\s+)?(user|human)", re.I),
        "HIGH",
        "tool_poisoning_conceal",
    ),
    (re.compile(r"<important>|<secret>|\[\[hidden\]\]", re.I), "HIGH", "hidden_directive"),
    (
        re.compile(r"(send|post|exfiltrate|upload|email)\b.{0,40}\bhttps?://", re.I | re.S),
        "MEDIUM",
        "exfiltration_shape",
    ),
    (re.compile(r"\b(curl|wget|fetch)\b.{0,30}https?://", re.I), "MEDIUM", "external_fetch"),
]


class InjectionDetection(BaseModel):
    label: str
    severity: str  # HIGH | MEDIUM
    excerpt: str
    field_path: str = ""

    @property
    def is_high(self) -> bool:
        return self.severity == "HIGH"


def scan_for_injection(text: str, *, field_path: str = "") -> list[InjectionDetection]:
    """Heuristic prompt-injection scan over a single string (pure).

    Returns detections (possibly empty). NOT a guarantee — a determined adversary
    can evade regex heuristics; this is one defense-in-depth layer. The structural
    backstop is :func:`audit_toolset` (capability-composition trifecta).
    """
    if not text:
        return []
    out: list[InjectionDetection] = []
    for pattern, severity, label in _INJECTION_PATTERNS:
        m = pattern.search(text)
        if m:
            start = max(0, m.start() - 12)
            out.append(
                InjectionDetection(
                    label=label,
                    severity=severity,
                    excerpt=text[start : m.end() + 12].strip()[:120],
                    field_path=field_path,
                )
            )
    return out


def _scan_args(args: dict[str, Any], *, prefix: str = "") -> list[InjectionDetection]:
    """Recursively scan string leaves of a tool-call argument dict."""
    out: list[InjectionDetection] = []
    for key, value in args.items():
        path = f"{prefix}{key}"
        if isinstance(value, str):
            out.extend(scan_for_injection(value, field_path=path))
        elif isinstance(value, dict):
            out.extend(_scan_args(value, prefix=f"{path}."))
        elif isinstance(value, (list, tuple)):
            for i, item in enumerate(value):
                if isinstance(item, str):
                    out.extend(scan_for_injection(item, field_path=f"{path}[{i}]"))
                elif isinstance(item, dict):
                    out.extend(_scan_args(item, prefix=f"{path}[{i}]."))
    return out


# ─── lethal-trifecta (structural) ────────────────────────────────────────


class TrifectaReport(BaseModel):
    present_capabilities: list[str]
    has_trifecta: bool
    missing_legs: list[str]
    summary: str


def has_lethal_trifecta(caps: frozenset[Capability]) -> bool:
    """True iff all three trifecta legs are simultaneously present (pure)."""
    return {
        Capability.READS_PRIVATE_DATA,
        Capability.FETCHES_UNTRUSTED,
        Capability.CAN_EXFILTRATE,
    }.issubset(caps)


def audit_toolset(tool_names: list[str]) -> TrifectaReport:
    """Compute the trifecta risk of a *composed* toolset (pure).

    The danger is compositional: any single tool may be safe, but a session that
    can read private data AND ingest untrusted content AND exfiltrate is
    unconditionally injectable. Unknown tool names contribute no capabilities.
    """
    present: set[Capability] = set()
    for name in tool_names:
        present |= TOOL_CAPABILITIES.get(name, frozenset())
    all_legs = {
        Capability.READS_PRIVATE_DATA,
        Capability.FETCHES_UNTRUSTED,
        Capability.CAN_EXFILTRATE,
    }
    missing = all_legs - present
    has = not missing
    summary = (
        "LETHAL TRIFECTA COMPLETE — toolset can read private data, ingest untrusted "
        "content, and exfiltrate. Isolate by trust boundary (separate servers/sessions)."
        if has
        else f"{len(present)}/3 trifecta legs present; missing: {sorted(c.value for c in missing)}"
    )
    return TrifectaReport(
        present_capabilities=sorted(c.value for c in present),
        has_trifecta=has,
        missing_legs=sorted(c.value for c in missing),
        summary=summary,
    )


# ─── per-tool-call audit ─────────────────────────────────────────────────


class SecurityReport(BaseModel):
    tool_name: str
    mode: str
    detections: list[InjectionDetection] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)
    verdict: str  # ALLOW | DENY

    @property
    def has_high(self) -> bool:
        return any(d.is_high for d in self.detections)


class SecurityViolation(Exception):
    """Raised by callers on a DENY verdict (ENFORCE mode only)."""


def audit_tool_call(
    tool_name: str,
    args: dict[str, Any],
    *,
    mode: Optional[SecurityMode] = None,
) -> SecurityReport:
    """Audit a single MCP tool call: injection-scan args + tag capabilities.

    Verdict is **ALLOW in AUDIT mode regardless of detections** (warn-only, no dev
    impact). Only ENFORCE mode + a HIGH detection yields DENY. The caller decides
    whether to raise :class:`SecurityViolation` on DENY.
    """
    m = mode if mode is not None else current_mode()
    detections = _scan_args(args)
    caps = sorted(c.value for c in TOOL_CAPABILITIES.get(tool_name, frozenset()))
    high = any(d.is_high for d in detections)
    verdict = "DENY" if (m is SecurityMode.ENFORCE and high) else "ALLOW"
    return SecurityReport(
        tool_name=tool_name,
        mode=m.value,
        detections=detections,
        capabilities=caps,
        verdict=verdict,
    )
