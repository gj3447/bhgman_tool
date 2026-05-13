"""Entry point: `python -m mcp_server`.

KG: span-mcp-server-skeleton-fastmcp-2026-05-13 (:AtomicSpan)

Usage (from Claude Code):
    claude mcp add bhgman-tool -- python -m mcp_server
"""
from __future__ import annotations

import sys

from .server import build_server


def main() -> int:
    try:
        server = build_server()
    except ImportError as e:
        print(
            "ERROR: bhgman_tool MCP server requires fastmcp.\n"
            "Install with:  pip install fastmcp\n"
            f"Underlying ImportError: {e}",
            file=sys.stderr,
        )
        return 1
    server.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
