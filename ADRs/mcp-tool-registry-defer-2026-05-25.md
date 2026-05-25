# ADR: MCP tool registry + search (defer-loading foundation)

- **Status**: IMPLEMENTED (PRELIMINARY — awaiting user CANONICAL verdict)
- **Date**: 2026-05-25
- **KG ref**: `finding-aidev-mcp-tool-registry-2026-05-25`
- **Parent driver**: PROM 16 `prom16-ai-dev-tools-2026-05-25` lever ② (MCP Tool Search / `defer_loading`; CS2/AS3).

---

## Context

The MCP server eagerly registers all 9 tools; their full schemas all enter the
client context up-front. Claude Code's `defer_loading` / Tool Search pattern
avoids this by searching for the right tool on demand (PROM reports ~85% context
saving — but that figure is for large toolsets).

PROM honest caveat: at **9 tools the gain is limited**; it scales with toolset size.

## Decision

Add `engine/mcp_server/registry.py` — a searchable tool **catalog** (name, summary,
when_to_use, category, capabilities) + `search_tools(query)` (keyword relevance) +
`tool_manifest()` (lightweight name+summary list = the defer-loading surface).
Capability tags are sourced from `security.TOOL_CAPABILITIES` (single source of
truth; a `catalog_is_consistent_with_security()` invariant guards drift).

**Crucially, the live FastMCP tool surface is NOT changed** — no `search_tools`
meta-tool is auto-registered, so what Claude Code currently sees is identical
(zero dev impact). This builds the *foundation* only.

## Rationale

- **Proportionate**: matches PROM's "limited gain at this size" — build the
  searchable foundation now; defer the surface change until the toolset is large
  enough to justify it. Avoids over-engineering.
- **No drift**: capabilities derive from the security registry, not duplicated.

## Consequences

- (+) Toolset is now introspectable/searchable; manifest gives a cheap discovery surface.
- (+) 7 tests; no change to the live MCP tool surface → no Claude Code impact.
- (−) The actual context saving is not realized until a `search_tools` meta-tool +
  lazy per-tool registration are wired (follow-up).

## Follow-ups

- Register a `search_tools` meta-tool + lazy per-tool schema loading on FastMCP,
  gated behind a flag, once tool count grows enough to matter.
