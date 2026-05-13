"""bhgman-tool MCP server: assembles tools into a FastMCP instance.

KG: span-mcp-server-skeleton-fastmcp-2026-05-13 (:AtomicSpan)

Design:
- One FastMCP instance per server.
- Each tool registered via `@mcp.tool()` decorator from `tools/*` modules.
- stdio transport (default for `mcp.run()`).
- All tools must be deterministic, time-bounded, and structured (no eval/exec).
"""
from __future__ import annotations

from typing import Any


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

    register_longinus(mcp)
    register_harness(mcp)
    register_apt(mcp)
    register_taliban(mcp)
    register_tpa(mcp)

    return mcp


def list_registered_tool_names() -> list[str]:
    """For testing without a live MCP loop: enumerate tools that *would* be registered.

    KG: skeleton-time introspection helper for pytest verification.
    """
    return [
        "longinus_audit",
        "harness_diagnose",
        "apt_phase_detect",
        "taliban_lens_check",
        "tpa_drift_audit",
    ]
