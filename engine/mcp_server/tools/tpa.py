"""MCP tool — `tpa_drift_audit`.

KG: span-mcp-tool-tpa-drift-audit-2026-05-13 (:AtomicSpan)

Counts the 5 TPA drift types (Missing / Orphan / SigMismatch / PatternDiv / LabelRot) for a
repository, using on-disk heuristics that don't require Neo4j.

Honest limitations (Goodhart safeguard):
- `coverage_ratio` is not synthesised here — the consumer must judge fitness from the
  per-drift counts and example file:line locations.
- "SigMismatch" / "PatternDiv" need AST + Pattern Library to detect properly; this skeleton
  returns 0 for those categories with a note.
- Scan budget capped at 1000 .py files to bound runtime.
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

_SKIP_DIRS = frozenset({
    ".git", ".venv", "node_modules", "__pycache__", ".pytest_cache",
    "dist", "build", ".mypy_cache", ".ruff_cache",
})


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


def _scan_kg_refs(root: Path) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    count = 0
    for path in root.rglob("*.py"):
        if count >= MAX_FILES:
            break
        if any(part in _SKIP_DIRS for part in path.parts):
            continue
        try:
            source = path.read_text(errors="replace")
        except OSError:
            continue
        for i, line in enumerate(source.splitlines(), start=1):
            m = KG_REF_RE.search(line)
            if m:
                refs.append({
                    "file": str(path.relative_to(root)),
                    "line": i,
                    "kg_id": m.group(1),
                })
        count += 1
    return refs


def _truncate(items: list[Any], limit: int = EXAMPLE_LIMIT) -> list[Any]:
    return items[:limit]


_NOTE_AUDIT = (
    "Skeleton-level detection. Missing/SigMismatch/PatternDiv need AST + Pattern Library; "
    "the skeleton returns 0 with a 'deferred' marker rather than guessing. Orphan requires "
    "kg_simulated.json at the repo root; otherwise it reports 0 (kg_simulated_present=false). "
    "Goodhart safeguard: no coverage_ratio scalar; consumers must judge from per-type counts + "
    "examples."
)


def _detect_orphans(refs: list[dict[str, Any]], known_kg: set[str] | None) -> list[dict[str, Any]]:
    if known_kg is None:
        return []
    return [r for r in refs if r["kg_id"] not in known_kg]


def _detect_label_rot(root: Path) -> list[dict[str, Any]]:
    """KG ref + DEPRECATED/STALE marker on the same line."""
    findings: list[dict[str, Any]] = []
    for path in root.rglob("*.py"):
        if any(part in _SKIP_DIRS for part in path.parts):
            continue
        try:
            source = path.read_text(errors="replace")
        except OSError:
            continue
        for i, line in enumerate(source.splitlines(), start=1):
            if KG_REF_RE.search(line) and ("DEPRECATED" in line or "STALE" in line):
                findings.append({"file": str(path.relative_to(root)), "line": i})
    return findings


def tpa_drift_audit_impl(repo_path: str) -> dict[str, Any]:
    """Count the 5 drift types for a target repo.

    Returns structured dict with per-type counts + example locations.
    """
    root = _validate_repo_path(repo_path)
    known_kg = _load_known_kg_ids(root)
    refs = _scan_kg_refs(root)

    counts = {d: 0 for d in DRIFT_TYPES}
    examples: dict[str, list[dict[str, Any]]] = {d: [] for d in DRIFT_TYPES}

    orphans = _detect_orphans(refs, known_kg)
    counts["Orphan"] = len(orphans)
    examples["Orphan"] = _truncate(orphans)

    label_rot = _detect_label_rot(root)
    counts["LabelRot"] = len(label_rot)
    examples["LabelRot"] = _truncate(label_rot)

    deferred = [d for d in ("Missing", "SigMismatch", "PatternDiv") if counts[d] == 0]

    return {
        "audit_id": f"mcp-tpa-{root.name}",
        "repo_path": str(root),
        "kg_simulated_present": known_kg is not None,
        "files_scanned": min(MAX_FILES, sum(1 for _ in root.rglob("*.py"))),
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
