"""Tests for MCP tool registry + search (defer-loading foundation).

# KG: finding-aidev-mcp-tool-registry-2026-05-25
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent))  # engine/ root

from mcp_server.registry import (
    TOOL_CATALOG,
    catalog_is_consistent_with_security,
    search_tools,
    tool_manifest,
)
from mcp_server.server import list_registered_tool_names


def test_search_ranks_relevant_tools() -> None:
    hits = [m.name for m in search_tools("drift audit")]
    assert "longinus_audit" in hits or "tpa_drift_audit" in hits


def test_search_dispatch_query() -> None:
    hits = [m.name for m in search_tools("dispatch subagent")]
    assert "apt_dispatch" in hits


def test_empty_query_returns_empty() -> None:
    assert search_tools("   ") == []


def test_search_limit_respected() -> None:
    assert len(search_tools("audit kg agent", limit=2)) <= 2


def test_manifest_is_lightweight() -> None:
    man = tool_manifest()
    assert len(man) == len(TOOL_CATALOG)
    assert all(set(entry.keys()) == {"name", "summary"} for entry in man)


def test_catalog_covers_registered_toolset() -> None:
    registered = set(list_registered_tool_names())
    catalogued = set(TOOL_CATALOG.keys())
    assert registered <= catalogued, f"uncatalogued: {registered - catalogued}"


def test_catalog_capabilities_match_security() -> None:
    # single-source-of-truth invariant: catalog caps == security.TOOL_CAPABILITIES
    assert catalog_is_consistent_with_security() is True
