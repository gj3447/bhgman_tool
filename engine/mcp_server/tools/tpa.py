"""MCP tool — `tpa_drift_audit`.

KG: span-mcp-tool-tpa-drift-audit-2026-05-13 (:AtomicSpan)

Counts the 5 TPA drift types (Missing / Orphan / SigMismatch / PatternDiv / LabelRot) for a
repository, using on-disk heuristics that don't require Neo4j.

Honest limitations (Goodhart safeguard):
- `coverage_ratio` is not synthesised here — the consumer must judge fitness from the
  per-drift counts and example file:line locations.
- "SigMismatch" / "PatternDiv" need AST + Pattern Library to detect properly; this skeleton
  returns 0 for those categories with a note.
- Scan budget capped at 1000 .py files to bound runtime; exceeding the budget sets
  `truncated=true` (silent clipping is forbidden).

2026-07-29 hardening:
- Skip-dir matching uses root-RELATIVE path parts. The old absolute `path.parts`
  comparison silently blanked any repo checked out under a directory named like a
  skip entry (e.g. .../build/<repo>) — same bug class as the longinus 'GIT' skip fix.
- refs + LabelRot share ONE walk and ONE read per file (previously 3 walks / 2 reads),
  and share the MAX_FILES budget.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

KG_REF_RE = re.compile(r"#\s*KG:\s*(\S+)")
DRIFT_TYPES = ("Missing", "Orphan", "SigMismatch", "PatternDiv", "LabelRot")
MAX_FILES = 1000
EXAMPLE_LIMIT = 5

_SKIP_DIRS = frozenset(
    {
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
)


def _validate_repo_path(repo_path: str) -> Path:
    p = Path(repo_path).expanduser().resolve()
    if not p.exists():
        raise FileNotFoundError(f"repo path not found: {repo_path}")
    if not p.is_dir():
        raise NotADirectoryError(f"not a directory: {repo_path}")
    return p


def _load_known_kg_ids(root: Path) -> set[str] | None:
    """If a kg_simulated.json sits at the repo root, treat it as the canonical KG.

    Returns None when no simulated KG is present — drift types that need it are skipped.
    """
    sim = root / "kg_simulated.json"
    if not sim.is_file():
        return None
    try:
        data = json.loads(sim.read_text(errors="replace"))
    except json.JSONDecodeError:
        return None
    ids: set[str] = set()
    if isinstance(data, list):
        for entry in data:
            if isinstance(entry, dict) and isinstance(entry.get("id"), str):
                ids.add(entry["id"])
            elif isinstance(entry, str):
                ids.add(entry)
    elif isinstance(data, dict) and isinstance(data.get("ids"), list):
        ids.update(i for i in data["ids"] if isinstance(i, str))
    return ids


def _scan_repo(root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int, bool]:
    """Single walk / single read: collect kg refs, LabelRot hits, scan count, truncation.

    Skip matching is root-relative (see module docstring). Both detectors share the
    MAX_FILES budget; when a (MAX_FILES+1)-th candidate exists the scan stops and
    reports truncated=True instead of silently clipping.
    """
    refs: list[dict[str, Any]] = []
    label_rot: list[dict[str, Any]] = []
    scanned = 0
    truncated = False
    for path in root.rglob("*.py"):
        if any(part in _SKIP_DIRS for part in path.relative_to(root).parts):
            continue
        if scanned >= MAX_FILES:
            truncated = True
            break
        try:
            source = path.read_text(errors="replace")
        except OSError:
            continue
        scanned += 1
        rel = str(path.relative_to(root))
        for i, line in enumerate(source.splitlines(), start=1):
            m = KG_REF_RE.search(line)
            if not m:
                continue
            refs.append({"file": rel, "line": i, "kg_id": m.group(1)})
            if "DEPRECATED" in line or "STALE" in line:
                label_rot.append({"file": rel, "line": i})
    return refs, label_rot, scanned, truncated


def _truncate(items: list[Any], limit: int = EXAMPLE_LIMIT) -> list[Any]:
    return items[:limit]


# Skeleton cannot detect these without AST + Pattern Library; they are deferred,
# not "zero drift". Reported as null (NotImplemented sentinel) so consumers cannot
# mis-read a silent 0 as "no drift found".
# KG: sprint-tpa-schema-not-implemented-sentinel-2026-05-14
DEFERRED_DRIFT_TYPES = ("Missing", "SigMismatch", "PatternDiv")

_NOTE_AUDIT = (
    "Skeleton-level detection. Missing/SigMismatch/PatternDiv need AST + Pattern Library; "
    "the skeleton returns null (NotImplemented sentinel) rather than 0, so consumers cannot "
    "mis-read silent-0 as 'no drift'. Orphan requires kg_simulated.json at the repo root; "
    "otherwise it reports 0 (kg_simulated_present=false). Orphan and LabelRot share one "
    "walk and the MAX_FILES budget; truncated=true discloses any clip. Goodhart safeguard: "
    "no coverage_ratio scalar; consumers must judge from per-type counts + examples."
)


def _detect_orphans(refs: list[dict[str, Any]], known_kg: set[str] | None) -> list[dict[str, Any]]:
    if known_kg is None:
        return []
    return [r for r in refs if r["kg_id"] not in known_kg]


def tpa_drift_audit_impl(repo_path: str) -> dict[str, Any]:
    """Count the 5 drift types for a target repo.

    Returns structured dict with per-type counts + example locations.
    """
    root = _validate_repo_path(repo_path)
    known_kg = _load_known_kg_ids(root)
    refs, label_rot, files_scanned, truncated = _scan_repo(root)

    counts: dict[str, int | None] = {
        d: (None if d in DEFERRED_DRIFT_TYPES else 0) for d in DRIFT_TYPES
    }
    examples: dict[str, list[dict[str, Any]]] = {d: [] for d in DRIFT_TYPES}

    orphans = _detect_orphans(refs, known_kg)
    counts["Orphan"] = len(orphans)
    examples["Orphan"] = _truncate(orphans)

    counts["LabelRot"] = len(label_rot)
    examples["LabelRot"] = _truncate(label_rot)

    deferred = list(DEFERRED_DRIFT_TYPES)

    return {
        "audit_id": f"mcp-tpa-{root.name}",
        "repo_path": str(root),
        "kg_simulated_present": known_kg is not None,
        "files_scanned": files_scanned,
        "truncated": truncated,
        "kg_refs_total": len(refs),
        "drift_counts": counts,
        "drift_examples": examples,
        "deferred_drift_types": deferred,
        "note": _NOTE_AUDIT,
    }


def register(mcp: Any) -> None:
    """Attach `tpa_drift_audit` tool to the FastMCP instance."""

    @mcp.tool()
    def tpa_drift_audit(repo_path: str) -> dict[str, Any]:
        """5-drift audit (Missing/Orphan/SigMismatch/PatternDiv/LabelRot) for a repo.

        Args:
            repo_path: path to the repository (absolute or ~-prefixed)

        Returns: DriftAuditReport dict.
        """
        return tpa_drift_audit_impl(repo_path)
