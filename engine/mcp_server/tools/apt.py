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
- 2026-07-29 hardening (live mis-detection: an actively-developed repo reported 'Cleanup'):
  Cleanup/MetaReview are bare-word-prone — wave tables and history sections mention them
  in active repos — so they count as evidence ONLY with a status context (markdown heading
  or a status word) on the same line. Evidence older than STALE_AFTER_DAYS (via the file's
  own 'Last Updated:' stamp) caps confidence at INFERRED and sets stale=true.
"""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Any

# Lifecycle order (Phase 1..6) used to find "current" = latest open Phase.
APT_PHASES = ("SA", "SP", "ST", "SCW", "Cleanup", "MetaReview")

# Markers in apt-progress.md that indicate a phase is in progress / done.
# SA..SCW patterns embed activity words (decomposition/implementation/...) and are
# therefore self-contextual; Cleanup/MetaReview are gated by _CONTEXT_REQUIRED below.
_PHASE_PATTERNS = {
    "SA": re.compile(r"\bSA\s*(complete|bootstrap|EXTEND|in[_\s]progress)\b", re.IGNORECASE),
    "SP": re.compile(r"\bSP\s*(decomposition|in[_\s]progress|complete)\b", re.IGNORECASE),
    "ST": re.compile(r"\bST\s*(crystalliz|contract|in[_\s]progress|complete)\b", re.IGNORECASE),
    "SCW": re.compile(r"\bSCW\s*(implementation|TDD|in[_\s]progress|complete)\b", re.IGNORECASE),
    "Cleanup": re.compile(r"\b(Phase\s*6|Cleanup)\b", re.IGNORECASE),
    "MetaReview": re.compile(r"\bMeta[\s-]?Review\b", re.IGNORECASE),
}

# Phases whose bare name is too generic to count as evidence on its own — a mention
# in a wave table / history / honest-limitations section of an ACTIVE repo used to
# hijack current_phase (2026-07-29 live: bhgman_tool itself mis-detected 'Cleanup').
# They require a markdown heading or a status word on the same line.
# ('ratchet' was also dropped from the Cleanup pattern — it is a quality-gate term,
# not a phase marker.)
_CONTEXT_REQUIRED = frozenset({"Cleanup", "MetaReview"})
_STATUS_CONTEXT = re.compile(
    r"^\s*#{1,6}\s|in[_\s]?progress|active|current|complete|done|현재|진행|완료",
    re.IGNORECASE,
)

# Evidence freshness: parsed from the file's own stamp, never fabricated.
_LAST_UPDATED_RE = re.compile(r"Last\s+Updated\s*:\s*(\d{4}-\d{2}-\d{2})")
STALE_AFTER_DAYS = 14


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
    """Line-based detection with a context gate for bare-word-prone phases."""
    detected = {phase: False for phase in APT_PHASES}
    for line in text.splitlines():
        has_context = bool(_STATUS_CONTEXT.search(line))
        for phase, pat in _PHASE_PATTERNS.items():
            if detected[phase]:
                continue
            if phase in _CONTEXT_REQUIRED and not has_context:
                continue
            if pat.search(line):
                detected[phase] = True
    return detected


def _evidence_freshness(text: str, today: date | None = None) -> tuple[str | None, int | None, bool]:
    """Parse 'Last Updated: YYYY-MM-DD' → (stamp, age_days, stale).

    No stamp → (None, None, False): freshness is UNMEASURED, not fresh (honest-None).
    """
    m = _LAST_UPDATED_RE.search(text)
    if not m:
        return None, None, False
    stamp = m.group(1)
    ref = today or date.today()
    try:
        age = (ref - date.fromisoformat(stamp)).days
    except ValueError:
        return stamp, None, False
    return stamp, age, age > STALE_AFTER_DAYS


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
    "File-based detection only; phase markers parsed from apt-progress.md via regex. "
    "Cleanup/MetaReview require a status context on the same line (bare mentions in "
    "wave tables or history are not evidence). stale=true means the file's own "
    "'Last Updated' stamp is older than 14 days and confidence is capped at INFERRED. "
    "No scalar score is reported — the boolean phase map and confidence tag are the "
    "canonical output."
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


def _read_progress_markers(progress: Path, detected: dict[str, bool]) -> str:
    text = progress.read_text(errors="replace")
    for phase, found in _detect_phases_in_text(text).items():
        if found:
            detected[phase] = True
    return text


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


def _confidence_for(phase: str, has_progress: bool, stale: bool) -> str:
    if phase == "unknown":
        return "AMBIGUOUS"
    if stale:
        # 증거는 있으나 파일 자체 시인이 STALE_AFTER_DAYS 초과 — 현재 상태 확신 불가.
        return "INFERRED"
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
    progress_text = ""

    if progress is not None:
        progress_text = _read_progress_markers(progress, detected)
        sources.append(progress.name)

    if spans_file is not None:
        spans_summary = _read_spans_file(spans_file)
        if spans_summary:
            sources.append(spans_file.name)

    last_updated, age_days, stale = _evidence_freshness(progress_text)
    phase = _current_phase(detected)
    return {
        "repo_path": str(root),
        "current_phase": phase,
        "phases_detected": detected,
        "evidence_sources": sources,
        "spans_summary": spans_summary,
        "progress_last_updated": last_updated,
        "evidence_age_days": age_days,
        "stale": stale,
        "confidence": _confidence_for(phase, progress is not None, stale),
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
