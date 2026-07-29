"""MCP tool — `longinus_audit`.

KG: span-mcp-tool-longinus-audit-2026-05-13 (:AtomicSpan)

Exposes the production Longinus CommanderEngine as a Claude-Code-callable MCP tool.
"""

from __future__ import annotations

from typing import Any

from engine.longinus_engine import LonginusEngine
from engine.longinus_drift_audit.models import Confidence

CONFIDENCE_TIERS = tuple(c.value for c in Confidence)


def longinus_audit_impl(
    repo_path: str,
    confidence_threshold: str = "INFERRED",
) -> dict[str, Any]:
    """Audit a repo for KG drift markers.

    Args:
        repo_path: absolute or ~-prefixed path to scan
        confidence_threshold: minimum confidence tier to surface as actionable
            (EXTRACTED | INFERRED | AMBIGUOUS). AMBIGUOUS triggers human review.

    Returns:
        AuditReport dict (subset; full Pydantic model in longinus_drift_audit.models.AuditReport):
            {
                "audit_id": str,
                "repo_path": str,
                "files_scanned": int,          # 실제 스캔한 .py 파일 수
                "files_with_kg_refs": int,     # 그 중 KG anchor 를 품은 파일 수
                "kg_simulated_present": bool,  # False 면 drift 판정은 mock-KG 기반
                "kg_refs_found": int,
                "refs": [{file, line, kg_id}, ...],
                "drift_records": [],  # populated when external KG store available
                "confidence_threshold": str,
                "note": str,
            }

    KG: span-mcp-tool-longinus-audit-2026-05-13
    Verification: pytest test_mcp_tool_longinus.py
    """
    return LonginusEngine().audit_repo_for_mcp(repo_path, confidence_threshold)


def register(mcp: Any) -> None:
    """Attach `longinus_audit` tool to the FastMCP instance."""

    @mcp.tool()
    def longinus_audit(
        repo_path: str,
        confidence_threshold: str = "INFERRED",
    ) -> dict[str, Any]:
        """Scan a repository for `# KG: <id>` references and detect drift.

        Args:
            repo_path: path to the repository (absolute or ~-prefixed)
            confidence_threshold: EXTRACTED | INFERRED | AMBIGUOUS

        Returns: AuditReport dict.
        """
        return longinus_audit_impl(repo_path, confidence_threshold)
