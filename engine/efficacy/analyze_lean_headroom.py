"""Analyze raw JSONL from ``lean_headroom_run.py``.

The runner writes one JSON object per line when invoked with ``--out-dir``. This module recomputes
the repair-vs-bestN headroom sign test from those raw logs, so the markdown table is no longer the
only audit artifact.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

_ARMS = ("single", "repair", "bestN")


def sign_test_two_sided(wins: int, losses: int) -> float:
    """Exact two-sided binomial sign test under p=0.5, ignoring ties."""
    n = wins + losses
    if n == 0:
        return 1.0
    extreme = max(wins, losses)
    tail = sum(math.comb(n, k) for k in range(extreme, n + 1)) / (2**n)
    return min(1.0, 2.0 * tail)


def _jsonl_files(paths: Iterable[Path]) -> list[Path]:
    files: list[Path] = []
    for path in paths:
        if path.is_dir():
            files.extend(sorted(path.glob("*.jsonl")))
        else:
            files.append(path)
    return files


def _iter_records(files: Iterable[Path]) -> Iterable[dict[str, Any]]:
    for path in files:
        with path.open(encoding="utf-8") as f:
            for lineno, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as exc:
                    msg = f"{path}:{lineno}: invalid JSONL: {exc.msg}"
                    raise ValueError(msg) from exc
                if isinstance(record, dict):
                    record["_source_path"] = str(path)
                    yield record


def _is_run_summary(record: dict[str, Any]) -> bool:
    return record.get("record_type") == "run_summary" or (
        "headroom_only" in record and "all" in record
    )


def _empty_counts() -> dict[str, Any]:
    return {
        "runs": 0,
        "single": 0,
        "repair": 0,
        "bestN": 0,
        "graded_single": 0.0,
        "graded_repair": 0.0,
        "graded_bestN": 0.0,
    }


def _add_summary_counts(target: dict[str, Any], summary: dict[str, Any]) -> None:
    target["runs"] += 1
    for arm in _ARMS:
        target[arm] += int(summary.get(arm, 0))
    for key in ("graded_single", "graded_repair", "graded_bestN"):
        target[key] += float(summary.get(key, 0.0))


def _accumulate_task_summary(
    record: dict[str, Any],
    per_task: dict[str, dict[str, Any]],
    task_difficulties: dict[str, str],
) -> None:
    """Fold a single task_summary record into the per-task accumulators."""
    task = str(record["task"])
    task_difficulties[task] = str(record.get("difficulty", "unknown"))
    task_counts = per_task[task]
    task_counts["runs"] += 1
    arms = record.get("arms", {})
    for arm in _ARMS:
        arm_record = arms.get(arm, {})
        task_counts[arm] += int(bool(arm_record.get("proven", False)))
        task_counts[f"graded_{arm}"] += float(arm_record.get("graded_score", 0.0))


def _aggregate_records(
    files: list[Path],
) -> tuple[
    list[dict[str, Any]],
    dict[str, Any],
    dict[str, Any],
    dict[str, dict[str, Any]],
    dict[str, str],
    int,
]:
    """Single pass over all records → (run_summaries, all_totals, headroom_totals,
    per_task, task_difficulties, attempt_count)."""
    run_summaries: list[dict[str, Any]] = []
    all_totals = _empty_counts()
    headroom_totals = _empty_counts()
    per_task: dict[str, dict[str, Any]] = defaultdict(_empty_counts)
    task_difficulties: dict[str, str] = {}
    attempt_count = 0

    for record in _iter_records(files):
        record_type = record.get("record_type")
        if record_type == "attempt":
            attempt_count += 1
            continue
        if _is_run_summary(record):
            run_summaries.append(record)
            _add_summary_counts(all_totals, record.get("all", {}))
            _add_summary_counts(headroom_totals, record.get("headroom_only", {}))
            continue
        if record_type == "task_summary":
            _accumulate_task_summary(record, per_task, task_difficulties)

    return run_summaries, all_totals, headroom_totals, per_task, task_difficulties, attempt_count


def _tally_wins(run_summaries: list[dict[str, Any]]) -> tuple[int, int, int]:
    """Per-run sign test tally on headroom_only repair vs bestN → (wins, ties, losses)."""
    wins = ties = losses = 0
    for summary in run_summaries:
        repair = int(summary["headroom_only"]["repair"])
        bestn = int(summary["headroom_only"]["bestN"])
        if repair > bestn:
            wins += 1
        elif repair < bestn:
            losses += 1
        else:
            ties += 1
    return wins, ties, losses


def analyze_paths(paths: Iterable[str | Path]) -> dict[str, Any]:
    files = _jsonl_files(Path(p) for p in paths)
    (
        run_summaries,
        all_totals,
        headroom_totals,
        per_task,
        task_difficulties,
        attempt_count,
    ) = _aggregate_records(files)
    wins, ties, losses = _tally_wins(run_summaries)

    task_rows = []
    for task, counts in per_task.items():
        row = dict(counts)
        row.update(
            {
                "task": task,
                "difficulty": task_difficulties.get(task, "unknown"),
                "delta_repair_bestN": counts["repair"] - counts["bestN"],
                "graded_delta_repair_bestN": round(
                    counts["graded_repair"] - counts["graded_bestN"], 4
                ),
            }
        )
        task_rows.append(row)
    task_rows.sort(key=lambda r: (-r["delta_repair_bestN"], r["task"]))

    return {
        "files": [str(path) for path in files],
        "attempt_records": attempt_count,
        "runs": len(run_summaries),
        "seed_offsets": [record.get("seed_offset") for record in run_summaries],
        "all_totals": _rounded_counts(all_totals),
        "headroom_totals": _rounded_counts(headroom_totals),
        "repair_vs_bestN_headroom": {
            "repair_gt_bestN": wins,
            "ties": ties,
            "bestN_gt_repair": losses,
            "non_ties": wins + losses,
            "p_two_sided": sign_test_two_sided(wins, losses),
        },
        "per_task": [_rounded_counts(row) for row in task_rows],
    }


def _rounded_counts(counts: dict[str, Any]) -> dict[str, Any]:
    out = dict(counts)
    for key in ("graded_single", "graded_repair", "graded_bestN"):
        if key in out:
            out[key] = round(float(out[key]), 4)
    return out


def format_report(result: dict[str, Any]) -> str:
    rvb = result["repair_vs_bestN_headroom"]
    lines = [
        f"files: {len(result['files'])}",
        f"runs: {result['runs']}",
        (
            "headroom repair-vs-bestN: "
            f"wins={rvb['repair_gt_bestN']} ties={rvb['ties']} "
            f"losses={rvb['bestN_gt_repair']} non_ties={rvb['non_ties']} "
            f"p_two_sided={rvb['p_two_sided']:.6f}"
        ),
    ]
    headroom = result["headroom_totals"]
    lines.append(
        "headroom totals: "
        f"single={headroom['single']} repair={headroom['repair']} bestN={headroom['bestN']} "
        f"graded={headroom['graded_single']:.2f}/{headroom['graded_repair']:.2f}/"
        f"{headroom['graded_bestN']:.2f}"
    )
    if result["per_task"]:
        lines.extend(
            ["", "per-task proven counts:", "task difficulty runs single repair bestN delta"]
        )
        for row in result["per_task"]:
            lines.append(
                f"{row['task']} {row['difficulty']} {row['runs']} {row['single']} "
                f"{row['repair']} {row['bestN']} {row['delta_repair_bestN']:+d}"
            )
    return "\n".join(lines)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Recompute Lean headroom repair-vs-bestN statistics from raw JSONL."
    )
    parser.add_argument(
        "paths", nargs="+", help="JSONL files or directories containing JSONL files."
    )
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    result = analyze_paths(args.paths)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(format_report(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
