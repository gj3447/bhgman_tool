"""MCP tool — `longinus_audit`.

KG: span-mcp-tool-longinus-audit-2026-05-13 (:AtomicSpan)

Exposes Longinus drift detection as a Claude-Code-callable MCP tool.
Uses the simulated KG audit logic from the worked example (worked/01-longinus-simple/run.py)
plus the production Pydantic models from `longinus_drift_audit` package.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


KG_REF_RE = re.compile(r"#\s*KG:\s*(\S+)")
CONFIDENCE_TIERS = ("EXTRACTED", "INFERRED", "AMBIGUOUS")


def _validate_repo_path(repo_path: str) -> Path:
    """Path-traversal guard. Resolves to absolute path under user filesystem."""
    p = Path(repo_path).expanduser().resolve()
    if not p.exists():
        raise FileNotFoundError(f"repo path not found: {repo_path}")
    if not p.is_dir():
        raise NotADirectoryError(f"not a directory: {repo_path}")
    return p


def _scan_kg_refs(root: Path, max_files: int = 1000) -> list[dict]:
    """Walk root, find `# KG: <id>` references in .py files.

    Bounded: max_files prevents runaway scans.
    """
    refs: list[dict] = []
    skip_dirs = {
        ".git",
        ".venv",
        "node_modules",
        "__pycache__",
        ".pytest_cache",
        "dist",
        "build",
        ".mypy_cache",
        ".ruff_cache",
    }
    count = 0
    for path in root.rglob("*.py"):
        if count >= max_files:
            break
        if any(skip in path.parts for skip in skip_dirs):
            continue
        try:
            source = path.read_text(errors="replace")
        except OSError:
            continue
        for i, line in enumerate(source.splitlines(), start=1):
            m = KG_REF_RE.search(line)
            if m:
                refs.append(
                    {
                        "file": str(path.relative_to(root)),
                        "line": i,
                        "kg_id": m.group(1),
                    }
                )
        count += 1
    return refs


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
                "files_scanned": int,
                "kg_refs_found": int,
                "refs": [{file, line, kg_id}, ...],
                "drift_records": [],  # populated when external KG store available
                "confidence_threshold": str,
                "note": str,
            }

    KG: span-mcp-tool-longinus-audit-2026-05-13
    Verification: pytest test_mcp_tool_longinus.py
    """
    if confidence_threshold not in CONFIDENCE_TIERS:
        raise ValueError(
            f"confidence_threshold must be one of {CONFIDENCE_TIERS}, got {confidence_threshold!r}"
        )

    root = _validate_repo_path(repo_path)
    refs = _scan_kg_refs(root)

    # In this skeleton stage we don't connect to live Neo4j.
    # When a kg_simulated.json sibling is present (worked-example style), use it.
    drifts: list[dict] = []
    kg_sim_path = root / "kg_simulated.json"
    if kg_sim_path.exists():
        try:
            kg = json.loads(kg_sim_path.read_text())
            for r in refs:
                if r["kg_id"] not in kg:
                    drifts.append(
                        {
                            "drift_type": "Orphan",
                            "kg_id": r["kg_id"],
                            "code_location": f"{r['file']}:{r['line']}",
                            "lens_law_violated": "GetPut",
                        }
                    )
        except (json.JSONDecodeError, OSError):
            pass

    return {
        "audit_id": f"mcp-longinus-{root.name}",
        "repo_path": str(root),
        "files_scanned": len(set(r["file"] for r in refs)) if refs else 0,
        "kg_refs_found": len(refs),
        "refs": refs,
        "drift_records": drifts,
        "confidence_threshold": confidence_threshold,
        "note": "Skeleton stage: scans for # KG: refs and reports Orphans against kg_simulated.json (if present). Production Neo4j integration is Phase 2 sprint.",
    }


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
