"""bhgman-tool MCP server: assembles tools into a FastMCP instance.

KG: span-mcp-server-skeleton-fastmcp-2026-05-13 (:AtomicSpan)

Design:
- One FastMCP instance per server.
- Each tool registered via `@mcp.tool()` decorator from `tools/*` modules.
- stdio transport (default for `mcp.run()`).
- All tools must be deterministic, time-bounded, and structured (no eval/exec).
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def build_server() -> Any:
    """Construct and configure the FastMCP server.

    Returns a `fastmcp.FastMCP` instance ready to `.run()`.
    Raises ImportError if `fastmcp` is not installed (handled by __main__).
    """
    from fastmcp import FastMCP

    mcp: Any = FastMCP("bhgman-tool")

    # Register tools (each module attaches its @mcp.tool() functions to `mcp`)
    from .tools.longinus import register as register_longinus
    from .tools.harness import register as register_harness
    from .tools.apt import register as register_apt
    from .tools.taliban import register as register_taliban
    from .tools.tpa import register as register_tpa
    from .tools.prometheus import register as register_prometheus  # Legion step 6 (획득)
    from .tools.occam import register as register_occam

    # SYMPOSIUM-absorbed tools (Wave 7 P2-A, 2026-05-14):
    # KG: rs-mcp-symposium-absorb-2026-05-14
    from .tools.symposium import register as register_symposium

    # 7-commander legion (비행기맨#4) — full roster + closed loop (2026-06-18):
    # KG: adr-seven-commander-legion-architecture-2026-05-27
    from .tools.legion import register as register_legion

    # hades_realize — 실현(materialize) behind the verdict-provenance gate (OQ1, 2026-06-20):
    # KG: adr-legion-runtime-shape-review-2026-06-20
    from .tools.hades import register as register_hades

    register_longinus(mcp)
    register_harness(mcp)
    register_apt(mcp)
    register_taliban(mcp)
    register_tpa(mcp)
    register_prometheus(mcp)
    register_occam(mcp)
    register_symposium(mcp)
    register_legion(mcp)
    register_hades(mcp)

    # Security audit (PROM 16 lever ④): log the toolset's lethal-trifecta profile.
    # ⚠ This is a ONE-SHOT boot-time profiler, NOT a live guard: it runs once here
    # and the FastMCP loop never calls audit_tool_call per invocation, so no live
    # tool argument is ever scanned. Enforcement (BHGMAN_SECURITY_ENFORCE=1) only
    # bites if a caller explicitly wraps a call with audit_tool_call — the live path
    # does not. Per-call interception is a follow-up. See security.py docstring.
    try:
        from .security import audit_toolset, current_mode

        report = audit_toolset(list_registered_tool_names())
        if report.has_trifecta:
            logger.warning("MCP security: %s", report.summary)
        else:
            logger.info("MCP security: %s (mode=%s)", report.summary, current_mode().value)
    except Exception:  # pragma: no cover - audit must never break server build
        logger.debug("MCP security audit skipped (non-fatal)", exc_info=True)

    return mcp


def list_registered_tool_names() -> list[str]:
    """For testing without a live MCP loop: enumerate tools that *would* be registered.

    KG: skeleton-time introspection helper for pytest verification.
    """
    return [
        # bhgman_tool diagnostic tools (read-only project inspection)
        "longinus_audit",
        "harness_diagnose",
        "apt_phase_detect",
        "taliban_lens_check",
        "tpa_drift_audit",
        "prometheus_research",  # Legion step 6 — 획득(knowledge-first), 2026-05-27
        "occam_dedupe",
        # SYMPOSIUM dispatch tools (Wave 7 P2-A absorbed 2026-05-14)
        "apt_dispatch",
        "kg_query",
        "gate_check",
        "seed_germinate",
        # 7-commander legion (비행기맨#4), 2026-06-18
        "legion_roster",
        "legion_run",
        # hades_realize — gated 실현 (OQ1, 2026-06-20)
        "hades_realize",
    ]
