"""MCP tool — `apt_phase_detect`.

KG: span-mcp-tool-apt-phase-detect-2026-05-13 (:AtomicSpan)

Inspects a project for APT phase state by reading file-system artifacts (apt-progress.md,
feature-spans.json) — no live Neo4j dependency at the skeleton stage. Returns the detected
phase per branch plus a confidence flag explaining the evidence base.

Honest limitations (Goodhart safeguard):
- File-based detection only; if a project tracks state in KG without on-disk artifacts the
  tool returns 'unknown' rather than fabricating a phase.
- "Confidence" is the evidence-source label (EXTRACTED file marker / INFERRED heuristic /
  AMBIGUOUS partial), not a scalar score. Do not promote any single number as a quality
  metric.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

# Lifecycle order (Phase 1..6) used to find "current" = latest open Phase.
APT_PHASES = ("SA", "SP", "ST", "SCW", "Cleanup", "MetaReview")

# Markers in apt-progress.md that indicate a phase is in progress / done.
_PHASE_PATTERNS = {
    "SA": re.compile(r"\bSA\s*(complete|bootstrap|EXTEND|in[_\s]progress)\b", re.IGNORECASE),
    "SP": re.compile(r"\bSP\s*(decomposition|in[_\s]progress|complete)\b", re.IGNORECASE),
    "ST": re.compile(r"\bST\s*(crystalliz|contract|in[_\s]progress|complete)\b", re.IGNORECASE),
    "SCW": re.compile(r"\bSCW\s*(implementation|TDD|in[_\s]progress|complete)\b", re.IGNORECASE),
    "Cleanup": re.compile(r"\b(Phase\s*6|Cleanup|ratchet)\b", re.IGNORECASE),
    "MetaReview": re.compile(r"\bMeta[\s-]?Review\b", re.IGNORECASE),
}


def _validate_repo_path(repo_path: str) -> Path:
    p = Path(repo_path).expanduser().resolve()
    if not p.exists():
        raise FileNotFoundError(f"repo path not found: {repo_path}")
    if not p.is_dir():
        raise NotADirectoryError(f"not a directory: {repo_path}")
    return p


def _find_apt_progress(root: Path) -> Path | None:
    """Locate apt-progress.md at repo root (the only canonical location)."""
    candidate = root / "apt-progress.md"
    return candidate if candidate.is_file() else None


def _find_feature_spans(root: Path) -> Path | None:
    candidate = root / "feature-spans.json"
    return candidate if candidate.is_file() else None


def _detect_phases_in_text(text: str) -> dict[str, bool]:
    return {phase: bool(pat.search(text)) for phase, pat in _PHASE_PATTERNS.items()}


def _current_phase(detected: dict[str, bool]) -> str:
    """Pick the latest phase with evidence, or 'unknown' if nothing matches."""
    for phase in reversed(APT_PHASES):
        if detected.get(phase):
            return phase
    return "unknown"


_NOTE_NO_ARTIFACTS = (
    "No apt-progress.md or feature-spans.json at repo root. The project may "
    "track APT state in KG only — call this tool against a path that contains "
    "the on-disk artifact, or upgrade to KG-backed detection (Phase 4)."
)

_NOTE_DETECTION = (
    "File-based detection only; phase progression markers parsed from apt-progress.md "
    "via regex. confidence=EXTRACTED requires apt-progress.md present. No scalar "
    "score is reported — the boolean phase map and confidence tag are the canonical output."
)


def _empty_report(root: Path) -> dict[str, Any]:
    return {
        "repo_path": str(root),
        "current_phase": "unknown",
        "phases_detected": {p: False for p in APT_PHASES},
        "evidence_sources": [],
        "confidence": "AMBIGUOUS",
        "note": _NOTE_NO_ARTIFACTS,
    }


def _read_progress_markers(progress: Path, detected: dict[str, bool]) -> None:
    text = progress.read_text(errors="replace")
    for phase, found in _detect_phases_in_text(text).items():
        if found:
            detected[phase] = True


def _read_spans_file(spans_file: Path) -> list[dict[str, Any]]:
    try:
        data = json.loads(spans_file.read_text(errors="replace"))
    except json.JSONDecodeError:
        return []
    if not (isinstance(data, dict) and isinstance(data.get("spans"), list)):
        return []
    summary: list[dict[str, Any]] = []
    for s in data["spans"]:
        if isinstance(s, dict) and isinstance(s.get("name"), str):
            summary.append({"name": s["name"], "depth": s.get("depth"), "status": s.get("status")})
    return summary


def _confidence_for(phase: str, has_progress: bool) -> str:
    if phase == "unknown":
        return "AMBIGUOUS"
    return "EXTRACTED" if has_progress else "INFERRED"


def apt_phase_detect_impl(repo_path: str) -> dict[str, Any]:
    """Detect current APT phase by reading on-disk artifacts.

    Returns a structured dict; never raises for "unknown" — that's a valid signal.
    """
    root = _validate_repo_path(repo_path)
    progress = _find_apt_progress(root)
    spans_file = _find_feature_spans(root)

    if progress is None and spans_file is None:
        return _empty_report(root)

    detected = {p: False for p in APT_PHASES}
    sources: list[str] = []
    spans_summary: list[dict[str, Any]] = []

    if progress is not None:
        _read_progress_markers(progress, detected)
        sources.append(progress.name)

    if spans_file is not None:
        spans_summary = _read_spans_file(spans_file)
        if spans_summary:
            sources.append(spans_file.name)

    phase = _current_phase(detected)
    return {
        "repo_path": str(root),
        "current_phase": phase,
        "phases_detected": detected,
        "evidence_sources": sources,
        "spans_summary": spans_summary,
        "confidence": _confidence_for(phase, progress is not None),
        "note": _NOTE_DETECTION,
    }


def register(mcp: Any) -> None:
    """Attach `apt_phase_detect` tool to the FastMCP instance."""

    @mcp.tool()
    def apt_phase_detect(repo_path: str) -> dict[str, Any]:
        """Detect current APT methodology phase in a repo (file-based skeleton).

        Args:
            repo_path: path to the repository (absolute or ~-prefixed)

        Returns: PhaseDetectionReport dict.
        """
        return apt_phase_detect_impl(repo_path)
