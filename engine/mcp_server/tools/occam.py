"""MCP tool — `occam_dedupe`.

Exposes the shared Occam CommanderEngine over the bundled local KG backend.
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
) -> dict[str, Any]:
    """Run Occam dedup against local KG. Returns hygiene payload."""
    return OccamEngine().run_local(
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
    ) -> dict[str, Any]:
        """Deduplicate/supersede stale SourceCodeNode records in local KG.

        Args:
            scope: optional sourcePath substring filter.
            apply: false = dry-run; true = archive via SUPERSEDED_BY.
            kg_path: optional LocalKgStore JSON path.
            repo_root: optional repo root for disk-aware orphan/move detection.

        Returns: Occam hygiene payload.
        """
        return occam_dedupe_impl(scope=scope, apply=apply, kg_path=kg_path, repo_root=repo_root)


__all__ = ["occam_dedupe_impl", "register"]
