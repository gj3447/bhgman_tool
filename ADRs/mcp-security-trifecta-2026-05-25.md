# ADR: MCP/dispatch security audit — lethal-trifecta + prompt-injection (audit-default)

- **Status**: IMPLEMENTED (PRELIMINARY — awaiting user CANONICAL verdict)
- **Date**: 2026-05-25
- **KG ref**: `finding-aidev-mcp-security-trifecta-2026-05-25`
- **Parent driver**: PROM 16 `prom16-ai-dev-tools-2026-05-25` lever ④ / cross-cut risk C6 (`finding_aidev_CS4`); "lethal trifecta" framing (Simon Willison 2025).
- **User constraint (2026-05-25)**: security MUST NOT interfere with normal Claude Code development.

---

## Context

bhgman_tool ships an MCP server (`engine/mcp_server/`) exposing 9 tools and an
`apt_dispatch` subagent spawner. PROM 16 CS4 flagged the **lethal trifecta** —
private-data access + untrusted-content ingestion + exfiltration channel = an
unconditionally injectable composition — plus prompt-injection on tool/dispatch
inputs, as the highest-importance gap. The toolkit had Jinja sandboxing +
Pydantic validation but no trifecta awareness and no injection scanning.

The hard constraint: this must add **zero friction** to the developer using
`/prom`, `/apt`, dispatch, and MCP tools inside Claude Code.

## Decision

Add `engine/mcp_server/security.py` — pure, heuristic, **audit-by-default**:

1. **Structural trifecta check** (`audit_toolset`): each tool tagged with
   `Capability` legs; flags when a *composed* toolset holds all three. The
   current toolset reports **2/3 (no exfiltration tool)** — adding any
   http-POST/email/webhook tool would complete it and trip the warning.
2. **Heuristic prompt-injection scanner** (`scan_for_injection` / `audit_tool_call`):
   regex detection of instruction-override / role-impersonation / tool-poisoning /
   exfiltration-shaped content over (recursively) tool-call args.
3. **Two modes** (`current_mode`):
   - **AUDIT (default)** — detect + log, **never block**. Zero Claude Code dev impact.
   - **ENFORCE (opt-in `BHGMAN_SECURITY_ENFORCE=1`)** — HIGH detection ⇒ DENY verdict;
     caller may raise `SecurityViolation`.
4. **Wire**: `build_server()` logs the toolset trifecta profile at startup
   (warn-only, guarded so it can never break server build). No tool behavior changes.

This mirrors the established repo philosophy: `dispatch_audit` warn-mode +
`DISPATCH_PATTERN_HARD_BLOCK=1` opt-in, and observation-only pre_tool hooks.

## Rationale

- **Constraint-satisfying**: AUDIT default = observe-only ⇒ provably non-intrusive.
- **Honest (Goodhart)**: regex injection detection is defense-in-depth, not a
  guarantee; the *structural* trifecta check is the backstop that does not rely on
  pattern-matching the adversary.
- **Idiomatic**: same warn-first + env-opt-in-enforce pattern as `dispatch_audit`.

## Consequences

- (+) Trifecta composition is now visible; injection on dispatch/tool inputs is
  detectable. Enforcement is one env var away when desired (e.g. CI / untrusted deploy).
- (+) 96 mcp_server tests pass (+13 security tests); no behavioral change by default.
- (−) Injection scanner is heuristic (evadable); not a substitute for trust-boundary
  isolation. Per-tool-call enforcement wrapping of the live FastMCP path is the
  follow-up (currently `audit_tool_call` is library-exposed for callers to adopt).

## Follow-ups

- Optional FastMCP middleware to run `audit_tool_call` on every live tool invocation
  (kept out of the default path now to avoid touching FastMCP internals untested).
- Trust-boundary isolation policy: separate MCP servers/sessions for tools that read
  private data vs. those that fetch untrusted content (prevents trifecta by construction).
