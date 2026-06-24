"""MCP tool — `occam_dedupe`.

Exposes the shared Occam CommanderEngine over either the bundled local KG backend
(default) or the operational neo4j KG (backend="neo4j", via the mcp-neo4j-cypher HTTP
gateway or bolt). Same engine surface either way — CLI/MCP/legion parity.
Dry-run is the default; apply remains explicit.
"""

from __future__ import annotations

from typing import Any

from engine.occam_engine import OccamEngine


def occam_dedupe_impl(
    scope: str = "",
    apply: bool = False,
    kg_path: str = "",
    repo_root: str = "",
    backend: str = "local",
) -> dict[str, Any]:
    """Run Occam dedup. backend="local" (default) or "neo4j". Returns hygiene payload."""
    engine = OccamEngine()
    if backend == "neo4j":
        return engine.run_remote(
            scope=scope or None,
            apply=apply,
            repo_root=repo_root or None,
        )
    return engine.run_local(
        kg_path=kg_path or None,
        scope=scope or None,
        apply=apply,
        repo_root=repo_root or None,
    )


def register(mcp: Any) -> None:
    """Attach `occam_dedupe` to the FastMCP instance."""

    @mcp.tool()
    def occam_dedupe(
        scope: str = "",
        apply: bool = False,
        kg_path: str = "",
        repo_root: str = "",
        backend: str = "local",
    ) -> dict[str, Any]:
        """Deduplicate/supersede stale SourceCodeNode records.

        Args:
            scope: optional sourcePath substring filter.
            apply: false = dry-run; true = archive via SUPERSEDED_BY.
            kg_path: optional LocalKgStore JSON path (backend="local" only).
            repo_root: optional repo root for disk-aware orphan/move detection.
            backend: "local" (default, bundled JSON KG) or "neo4j" (operational KG via
                mcp-neo4j-cypher HTTP gateway / bolt).

        Returns: Occam hygiene payload.
        """
        return occam_dedupe_impl(
            scope=scope, apply=apply, kg_path=kg_path, repo_root=repo_root, backend=backend
        )


__all__ = ["occam_dedupe_impl", "register"]
