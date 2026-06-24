"""MCP tool registry + search — defer-loading foundation (Wave 12, 2026-05-25).

Addresses PROM 16 ``prom16-ai-dev-tools-2026-05-25`` lever ② (MCP Tool Search /
``defer_loading`` — Claude Code's pattern of NOT dumping every tool schema into
context up-front, searching for the right tool on demand instead; PROM CS2/AS3).

PROM honest caveat: at the current 9-tool count the context win is *limited* —
the gain scales with toolset size. So this module builds the **foundation**
(searchable catalog + lightweight manifest) WITHOUT altering the live FastMCP
tool surface (zero impact on what Claude Code currently sees). Wiring a live
``search_tools`` meta-tool + lazy per-tool registration is the documented
follow-up, to be enabled when the toolset grows enough to justify it.

Capability tags are sourced from :mod:`security` (single source of truth, so the
trifecta audit and the catalog never drift).

# KG: finding-aidev-mcp-tool-registry-2026-05-25 (PROM 16 lever ②)
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from .security import TOOL_CAPABILITIES, Capability


class ToolMeta(BaseModel):
    name: str
    summary: str
    when_to_use: str
    category: str  # "read" | "dispatch" | "write"
    capabilities: list[str] = Field(default_factory=list)


# Catalog metadata. ``capabilities`` is derived from security.TOOL_CAPABILITIES
# at module load so the two never drift.
_CATALOG_SEED: list[tuple[str, str, str, str]] = [
    (
        "longinus_audit",
        "KG↔code reference-binding / drift audit (7-layer, sha256 baseline).",
        "checking traceability between knowledge-graph nodes and source code, or drift",
        "read",
    ),
    (
        "harness_diagnose",
        "Locate an agent/framework on the Harness 4-axis (Inform/Constrain/Verify/Correct).",
        "diagnosing where an agent or framework sits across the harness axes",
        "read",
    ),
    (
        "apt_phase_detect",
        "Detect current APT phase (SA→SP→ST→SCW→meta) for a workspace.",
        "figuring out which APT methodology phase work is in",
        "read",
    ),
    (
        "taliban_lens_check",
        "Run a Naesengmoon adversarial lens check on a target.",
        "adversarially validating a span / contract / finding",
        "read",
    ),
    (
        "tpa_drift_audit",
        "Reverse-engineering drift audit (design recovered from code).",
        "auditing recovered-design vs code drift on external/legacy code",
        "read",
    ),
    (
        "prometheus_research",
        "Knowledge-first 연구 계획 (프로메테우스, 획득): topic → N + axis×sub-axis 매트릭스 + KG-first.",
        "planning research before acting (knowledge-first), grounding a critic with KG truth",
        "read",
    ),
    (
        "occam_dedupe",
        "Occam KG dedup / reversible supersession pass, dry-run by default.",
        "finding duplicate or stale SourceCodeNode records and planning archive-only supersessions",
        "write",
    ),
    (
        "kg_query",
        "Neo4j Cypher read wrapper (fail-open via ssh dgx → cypher-shell).",
        "reading the knowledge graph with a Cypher query",
        "read",
    ),
    (
        "gate_check",
        "APT gate-check (Resilience4j 4-layer fail-closed chain).",
        "verifying an APT phase gate precondition/postcondition",
        "read",
    ),
    (
        "seed_germinate",
        "Emit a 재배맨 SubagentTaskSpec seed (jaebaeman protocol).",
        "creating a reusable subagent task-spec seed",
        "write",
    ),
    (
        "apt_dispatch",
        "APT phase routing / subagent dispatch (sa|sp|st|scw|meta_review).",
        "dispatching subagents for an APT phase",
        "dispatch",
    ),
    (
        "legion_roster",
        "List the 7 legion commanders (비행기맨#4) + Contract requires/provides chain.",
        "inspecting which commanders exist and their handoff contracts",
        "read",
    ),
    (
        "legion_run",
        "Run the closed legion loop 획득→연결→창조→정리→검증→실현 on the bundled local KG (infra-0).",
        "exercising the full 7-commander deterministic loop without live Neo4j",
        "read",
    ),
]

TOOL_CATALOG: dict[str, ToolMeta] = {
    name: ToolMeta(
        name=name,
        summary=summary,
        when_to_use=when,
        category=category,
        capabilities=sorted(c.value for c in TOOL_CAPABILITIES.get(name, frozenset())),
    )
    for (name, summary, when, category) in _CATALOG_SEED
}


def tool_manifest() -> list[dict[str, str]]:
    """Lightweight manifest (name + summary only) — the defer-loading surface.

    An agent reads this cheap list first, then loads the full schema only for the
    tool(s) it actually needs, instead of paying full-schema context for all tools.
    """
    return [{"name": m.name, "summary": m.summary} for m in TOOL_CATALOG.values()]


def _score(meta: ToolMeta, terms: list[str]) -> int:
    """Keyword relevance: name hit = 3, when_to_use = 2, summary = 1 (per term)."""
    name = meta.name.lower()
    when = meta.when_to_use.lower()
    summ = meta.summary.lower()
    score = 0
    for t in terms:
        if t in name:
            score += 3
        if t in when:
            score += 2
        if t in summ:
            score += 1
    return score


def search_tools(query: str, *, limit: int = 5) -> list[ToolMeta]:
    """Rank catalog tools by keyword relevance to ``query`` (pure).

    Empty / whitespace query → empty list (the manifest is the right call for
    "list everything"). Ties broken by catalog order (stable).
    """
    terms = [t for t in query.lower().split() if t]
    if not terms:
        return []
    scored = [(meta, _score(meta, terms)) for meta in TOOL_CATALOG.values()]
    ranked = [m for m, s in sorted(scored, key=lambda kv: kv[1], reverse=True) if s > 0]
    return ranked[:limit]


def catalog_is_consistent_with_security() -> bool:
    """Invariant: every catalogued tool's capabilities match the security registry.

    Guards against catalog ↔ security.TOOL_CAPABILITIES drift (single-source rule).
    """
    for name, meta in TOOL_CATALOG.items():
        expected = sorted(c.value for c in TOOL_CAPABILITIES.get(name, frozenset()))
        if meta.capabilities != expected:
            return False
    return True


__all__ = [
    "Capability",
    "ToolMeta",
    "TOOL_CATALOG",
    "tool_manifest",
    "search_tools",
    "catalog_is_consistent_with_security",
]
