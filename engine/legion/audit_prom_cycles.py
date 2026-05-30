"""Phase 4 empirical validation — scan real PROM cycle finding JSONs for Stevens-scale violations.

PROM 16 7CMD MEASUREMENT GROUNDING P3 task #1.
Pair with bhgman_tool/lean/Measurement_Phase4_EmpiricalValidation.lean (spec-level).

Usage:
    python -m engine.legion.audit_prom_cycles \\
        --root /Users/lagyeongjun/CD/SYMPOSIUM/THEORY \\
        --json-out audit_report.json

CI invocation: standalone script, returns exit 0 on GREEN, 1 on violation.

# KG: mitigation-lean4-metricscale-phase4-2026-05-30
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from engine.legion.measurement import STEVENS_SCALE, valid_operation


# (commander, metric_substr) → metric_name + op_keywords
# Inferred from typical finding text patterns. Conservative: only patterns
# that *unambiguously* describe an operation on a known metric.
_OP_KEYWORDS: dict[str, tuple[str, ...]] = {
    "mean": ("mean of", "average of", "평균"),
    "median": ("median of", "중앙값"),
    "mode": ("mode of", "최빈값"),
    "pct": ("% of", "percent of", "ratio of", "/100", "퍼센트"),
    "sd": ("standard deviation of", "std of", "표준편차"),
    "count": ("count of", "개수"),
    "ratio": ("ratio of", "ratio between"),
}


def _scan_text_for_metric_ops(text: str) -> list[tuple[str, str, str]]:
    """Return list of (commander, metric, op) tuples found in a text blob.

    Conservative — only flags when commander.metric explicitly appears near an op keyword.
    """
    hits: list[tuple[str, str, str]] = []
    text_lower = text.lower()
    for (commander, metric), _scale in STEVENS_SCALE.items():
        # Look for "<commander>.<metric>" or "<commander>'s <metric>" patterns
        patterns = [
            rf"{re.escape(commander)}\.\s*{re.escape(metric)}",
            rf"{re.escape(commander)}'s\s+{re.escape(metric)}",
            rf"{re.escape(commander)}\s+{re.escape(metric)}\b",
        ]
        for pat in patterns:
            for m in re.finditer(pat, text_lower):
                window = text_lower[max(0, m.start() - 80) : m.end() + 80]
                for op, keywords in _OP_KEYWORDS.items():
                    if any(kw in window for kw in keywords):
                        hits.append((commander, metric, op))
                        break
    return hits


def _scan_json(obj: Any, hits: list[tuple[str, str, str]]) -> None:
    """Recursively walk a JSON structure collecting text → (cmd, metric, op) hits."""
    if isinstance(obj, str):
        hits.extend(_scan_text_for_metric_ops(obj))
    elif isinstance(obj, list):
        for item in obj:
            _scan_json(item, hits)
    elif isinstance(obj, dict):
        for value in obj.values():
            _scan_json(value, hits)


def audit_finding_file(path: Path) -> dict[str, Any]:
    """Audit a single finding JSON. Returns dict with violations and stats."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        return {"path": str(path), "error": str(e), "violations": [], "scanned_ops": 0}
    hits: list[tuple[str, str, str]] = []
    _scan_json(data, hits)
    violations = [
        {"commander": cmd, "metric": metric, "op": op, "scale": STEVENS_SCALE[(cmd, metric)]}
        for cmd, metric, op in hits
        if not valid_operation(cmd, metric, op)
    ]
    return {
        "path": str(path),
        "scanned_ops": len(hits),
        "violations": violations,
    }


def audit_tree(root: Path) -> dict[str, Any]:
    """Audit every _findings/*.json under root. Returns aggregate report."""
    finding_files = sorted(root.rglob("_findings/*.json"))
    file_reports = [audit_finding_file(p) for p in finding_files]
    total_violations = sum(len(r["violations"]) for r in file_reports)
    total_scanned = sum(r["scanned_ops"] for r in file_reports)
    return {
        "root": str(root),
        "files_scanned": len(finding_files),
        "ops_scanned": total_scanned,
        "violation_count": total_violations,
        "green": total_violations == 0,
        "files": file_reports,
    }


def _print_file_violations(files: list[dict[str, Any]]) -> None:
    """Print per-file violation detail (guard-clause flat — keeps main's complexity low)."""
    print("\n--- VIOLATIONS ---")
    for fr in files:
        if not fr["violations"]:
            continue
        print(f"  {fr['path']}")
        for v in fr["violations"][:5]:
            print(f"    {v['commander']}.{v['metric']} ({v['scale']}) ← op={v['op']}")
        extra = len(fr["violations"]) - 5
        if extra > 0:
            print(f"    ... {extra} more")


def _print_report(report: dict[str, Any]) -> None:
    """Human-readable report summary + violation detail."""
    print(f"Files scanned:    {report['files_scanned']}")
    print(f"Ops scanned:      {report['ops_scanned']}")
    print(f"Violation count:  {report['violation_count']}")
    print(f"GREEN:            {report['green']}")
    if report["violation_count"]:
        _print_file_violations(report["files"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Audit PROM cycle findings for Stevens-scale violations"
    )
    parser.add_argument("--root", type=Path, required=True, help="SYMPOSIUM/THEORY root")
    parser.add_argument("--json-out", type=Path, default=None, help="Write JSON report")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)
    if not args.root.is_dir():
        print(f"ERROR: --root {args.root} is not a directory", file=sys.stderr)
        return 2
    report = audit_tree(args.root)
    if args.json_out:
        args.json_out.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    if not args.quiet:
        _print_report(report)
    return 0 if report["green"] else 1


if __name__ == "__main__":
    sys.exit(main())
