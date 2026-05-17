"""Goodhart antipattern detection on a target README.

KG: span-worked-example-goodhart-on-ruflo-2026-05-13 (:AtomicSpan)
LensSet: goodhart-detection-2026-05-13 (:LensSet, 3 lenses)

Pure regex + heuristic. No LLM, no network. Deterministic output.

Usage:
    python3 analyze.py                          # default: ruflo_readme_snapshot.md
    python3 analyze.py <path/to/README.md>      # any target README
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any


HERE = Path(__file__).parent
DEFAULT_TARGET = HERE / "ruflo_readme_snapshot.md"


# ─── Lens patterns ──────────────────────────────────────────────────────


# Lens 1: Goodhart metric-as-marketing
# Detects %-based claims on benchmark or reduction/improvement metrics
LENS_1_METRIC_RE = re.compile(
    r"\d+\.?\d*\s*%\s*(SWE-?Bench|HumanEval|MMLU|GSM8K|MBPP|"
    r"token reduction|token\s+\w*\s*reduction|solve\s+rate|"
    r"reduction|faster|improvement|accuracy|coverage)",
    re.IGNORECASE,
)
# Citation marker (lower-case mention of a primary external canon)
LENS_1_CITATION_MARKERS = (
    "goodhart",
    "lakatos",
    "tarski",
    "popper",
    "external canonical",
    "external citation",
)


# Lens 2: Enumeration inflation
# Detects "N+ agents/plugins/tools/commands" claims
LENS_2_ENUMERATION_RE = re.compile(
    r"(\d{2,})\s*\+?\s*(agents?|plugins?|tools?|commands?|modes?|MCP\s+tools?|integrations?)",
    re.IGNORECASE,
)
LENS_2_RESPONSIBILITY_MARKERS = (
    "responsibility_split",
    "responsibility split",
    "boundary location",
    "ccp",
    "common closure",
    "cherns",
    "3-tier sibling",
    "three-tier sibling",
    "robert martin",
    "package principles",
)


# Lens 3: Self-improving loop without safeguard
LENS_3_SELF_IMPROV_RE = re.compile(
    r"\b(self[\s-]?learn(?:ing)?|SONA|ReasoningBank|trajectory[\s-]?learn(?:ing)?|"
    r"self[\s-]?optimiz(?:e|ing)|self[\s-]?improv(?:e|ing)|neural[\s-]?pattern)\b",
    re.IGNORECASE,
)
LENS_3_SAFEGUARD_MARKERS = (
    "goodhart",
    "lakatos",
    "tarski",
    "yanofsky",
    "safeguard",
    "metric collapse",
    "incompleteness",
)


# ─── Detection ──────────────────────────────────────────────────────────


def _strip_bold(s: str) -> str:
    """Strip markdown ** bold markers so regex can match raw content."""
    return s.replace("**", "").replace("__", "")


def _find_evidence(text: str, regex: re.Pattern) -> list[tuple[int, str]]:
    """Return [(line_number, matched_excerpt), ...]

    Markdown bold markers are stripped before regex match so that
    `**84.8%** SWE-Bench` matches the same as `84.8% SWE-Bench`.
    """
    out: list[tuple[int, str]] = []
    for i, line in enumerate(text.splitlines(), start=1):
        stripped = _strip_bold(line)
        for m in regex.finditer(stripped):
            excerpt = line.strip()
            if len(excerpt) > 120:
                excerpt = excerpt[:117] + "..."
            out.append((i, excerpt))
    return out


def _has_marker(text_lower: str, markers: tuple[str, ...]) -> bool:
    return any(m in text_lower for m in markers)


def lens_1_goodhart_metric_marketing(text: str) -> dict[str, Any]:
    matches = _find_evidence(text, LENS_1_METRIC_RE)
    text_lower = text.lower()
    citation_present = _has_marker(text_lower, LENS_1_CITATION_MARKERS)
    detected = bool(matches) and not citation_present
    return {
        "lens_id": "lens-goodhart-metric-as-marketing",
        "detected": detected,
        "evidence_count": len(matches),
        "evidence": matches[:10],  # cap to keep output bounded
        "external_canonical_citation": "ABSENT" if not citation_present else "PRESENT",
    }


def lens_2_enumeration_inflation(text: str) -> dict[str, Any]:
    matches = _find_evidence(text, LENS_2_ENUMERATION_RE)
    text_lower = text.lower()
    responsibility_present = _has_marker(text_lower, LENS_2_RESPONSIBILITY_MARKERS)
    # Filter to N >= 10 only
    significant = [
        (line, excerpt)
        for line, excerpt in matches
        if any(int(n) >= 10 for n in re.findall(r"\d+", excerpt))
    ]
    detected = bool(significant) and not responsibility_present
    return {
        "lens_id": "lens-enumeration-inflation",
        "detected": detected,
        "evidence_count": len(significant),
        "evidence": significant[:10],
        "responsibility_split_mention": "PRESENT" if responsibility_present else "ABSENT",
    }


def lens_3_self_improving_no_safeguard(text: str) -> dict[str, Any]:
    matches = _find_evidence(text, LENS_3_SELF_IMPROV_RE)
    text_lower = text.lower()
    safeguard_present = _has_marker(text_lower, LENS_3_SAFEGUARD_MARKERS)
    detected = bool(matches) and not safeguard_present
    return {
        "lens_id": "lens-self-improving-no-safeguard",
        "detected": detected,
        "evidence_count": len(matches),
        "evidence": matches[:10],
        "safeguard_acknowledgment": "ABSENT" if not safeguard_present else "PRESENT",
    }


def detect_all(text: str) -> dict[str, Any]:
    """Run all 3 lenses + Lakatos verdict."""
    l1 = lens_1_goodhart_metric_marketing(text)
    l2 = lens_2_enumeration_inflation(text)
    l3 = lens_3_self_improving_no_safeguard(text)
    detected = [lens for lens in (l1, l2, l3) if lens["detected"]]
    return {
        "lensset": "goodhart-detection-2026-05-13",
        "lens_results": [l1, l2, l3],
        "errorpatterns_detected_count": len(detected),
        "errorpatterns_total": 3,
        "lakatos_verdict": "DEGENERATING"
        if len(detected) >= 2
        else ("PROGRESSIVE_CONDITIONAL" if len(detected) == 1 else "PROGRESSIVE"),
    }


# ─── Rendering ──────────────────────────────────────────────────────────


def render_report(target_name: str, result: dict[str, Any]) -> str:
    lines = [
        "Goodhart Antipattern Audit",
        "==========================",
        f"Target: {target_name}",
        f"LensSet: {result['lensset']} (3 lenses)",
        "",
    ]
    for idx, lr in enumerate(result["lens_results"], start=1):
        status = "DETECTED" if lr["detected"] else "not detected"
        lines.append(f"[Lens {idx}] {lr['lens_id']} — {status}")
        for line_no, excerpt in lr["evidence"][:5]:
            lines.append(f"  Evidence: {excerpt} (line {line_no})")
        for k in (
            "external_canonical_citation",
            "responsibility_split_mention",
            "safeguard_acknowledgment",
        ):
            if k in lr:
                lines.append(f"  {k}: {lr[k]}")
        lines.append("")
    lines.append("Summary:")
    lines.append(
        f"  ErrorPatterns detected: {result['errorpatterns_detected_count']} / {result['errorpatterns_total']}"
    )
    lines.append(f"  Lakatos verdict: {result['lakatos_verdict']}")
    return "\n".join(lines)


# ─── Entry ──────────────────────────────────────────────────────────────


def main() -> int:
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_TARGET
    if not target.exists():
        print(f"ERROR: target not found: {target}", file=sys.stderr)
        return 2
    text = target.read_text()
    result = detect_all(text)
    print(render_report(target.name, result))
    # exit 0 = PROGRESSIVE / PROGRESSIVE_CONDITIONAL; exit 1 = DEGENERATING
    return 0 if result["lakatos_verdict"] != "DEGENERATING" else 1


if __name__ == "__main__":
    sys.exit(main())
