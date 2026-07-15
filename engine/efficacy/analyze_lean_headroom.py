"""Analyze raw JSONL from ``lean_headroom_run.py``.

The runner writes one JSON object per line when invoked with ``--out-dir``. This module recomputes
the repair-vs-bestN headroom sign test from those raw logs, so the markdown table is no longer the
only audit artifact. It also computes the prereg §4 pairwise controls (repair-vs-decoy for P2,
repair-vs-plain for P3), a stdlib-only TOST equivalence test for `decoy ≈ bestN`, and per-arm
token/call accounting for the P4 parity gate — all backward-compatible with legacy single/repair/
bestN batches (the committed `headroom_32b_2026-06-14/`), where the newer arms are reported ABSENT
(never fake-zero-inflated p-values).

# KG: LakatosTree_BhgmanCeilingPierce_20260712, PIERCE_PREREGISTRATION §4 P1-P5, KILL_CRITERIA K4/K8
"""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

# single/repair/bestN are the legacy core; decoy (P2) and plain (P3) join for the 5-arm design. Legacy
# batches lack decoy/plain entirely → their aggregates stay 0 and their pairwise tests report ABSENT.
_ARMS = ("single", "repair", "bestN", "decoy", "plain")


def sign_test_two_sided(wins: int, losses: int) -> float:
    """Exact two-sided binomial sign test under p=0.5, ignoring ties."""
    n = wins + losses
    if n == 0:
        return 1.0
    extreme = max(wins, losses)
    tail = sum(math.comb(n, k) for k in range(extreme, n + 1)) / (2**n)
    return min(1.0, 2.0 * tail)


def _normal_cdf(z: float) -> float:
    """Standard-normal CDF via math.erf (stdlib-only; scipy is not a bhgman_tool dependency)."""
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


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
    counts: dict[str, Any] = {"runs": 0}
    for arm in _ARMS:
        counts[arm] = 0
        counts[f"graded_{arm}"] = 0.0
    return counts


def _add_summary_counts(target: dict[str, Any], summary: dict[str, Any]) -> None:
    target["runs"] += 1
    for arm in _ARMS:  # legacy summaries omit decoy/plain → .get(...,0) keeps them at 0
        target[arm] += int(summary.get(arm, 0))
        target[f"graded_{arm}"] += float(summary.get(f"graded_{arm}", 0.0))


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


def _empty_usage() -> dict[str, dict[str, int]]:
    return {arm: {"input_tokens": 0, "output_tokens": 0, "model_calls": 0} for arm in _ARMS}


def _accumulate_usage(usage: dict[str, dict[str, int]], record: dict[str, Any]) -> None:
    """Fold one attempt record's token/call accounting into per-arm usage (prereg P4). Legacy attempt
    records lack input_tokens/output_tokens → they contribute 0 tokens (surfaced as usage_hidden)."""
    arm = str(record.get("arm", ""))
    if arm not in usage:
        return
    usage[arm]["input_tokens"] += int(record.get("input_tokens", 0) or 0)
    usage[arm]["output_tokens"] += int(record.get("output_tokens", 0) or 0)
    usage[arm]["model_calls"] += int(record.get("model_calls", 0) or 0)


def _aggregate_records(
    files: list[Path],
) -> tuple[
    list[dict[str, Any]],
    dict[str, Any],
    dict[str, Any],
    dict[str, dict[str, Any]],
    dict[str, str],
    int,
    dict[str, dict[str, int]],
]:
    """Single pass over all records → (run_summaries, all_totals, headroom_totals,
    per_task, task_difficulties, attempt_count, usage)."""
    run_summaries: list[dict[str, Any]] = []
    all_totals = _empty_counts()
    headroom_totals = _empty_counts()
    per_task: dict[str, dict[str, Any]] = defaultdict(_empty_counts)
    task_difficulties: dict[str, str] = {}
    attempt_count = 0
    usage = _empty_usage()

    for record in _iter_records(files):
        record_type = record.get("record_type")
        if record_type == "attempt":
            attempt_count += 1
            _accumulate_usage(usage, record)
            continue
        if _is_run_summary(record):
            run_summaries.append(record)
            _add_summary_counts(all_totals, record.get("all", {}))
            _add_summary_counts(headroom_totals, record.get("headroom_only", {}))
            continue
        if record_type == "task_summary":
            _accumulate_task_summary(record, per_task, task_difficulties)

    return (
        run_summaries,
        all_totals,
        headroom_totals,
        per_task,
        task_difficulties,
        attempt_count,
        usage,
    )


def _arm_present(run_summaries: list[dict[str, Any]], arm: str) -> bool:
    """An arm has DATA iff at least one run_summary's headroom_only dict carries its KEY. Legacy
    batches omit decoy/plain entirely, so this is False for them — the guard that keeps a legacy
    batch (decoy≡0 everywhere) from manufacturing a fake `repair > decoy` sweep."""
    return any(arm in s.get("headroom_only", {}) for s in run_summaries)


def _tally_pair(
    run_summaries: list[dict[str, Any]], arm_a: str, arm_b: str
) -> tuple[int, int, int]:
    """Per-run headroom_only sign tally: (a_gt_b wins, ties, b_gt_a losses)."""
    wins = ties = losses = 0
    for summary in run_summaries:
        hr = summary["headroom_only"]
        a, b = int(hr.get(arm_a, 0)), int(hr.get(arm_b, 0))
        if a > b:
            wins += 1
        elif a < b:
            losses += 1
        else:
            ties += 1
    return wins, ties, losses


def _tally_wins(run_summaries: list[dict[str, Any]]) -> tuple[int, int, int]:
    """Per-run sign test tally on headroom_only repair vs bestN → (wins, ties, losses)."""
    return _tally_pair(run_summaries, "repair", "bestN")


def _pair_block(
    run_summaries: list[dict[str, Any]], arm_a: str, arm_b: str
) -> dict[str, Any] | None:
    """Paired per-run sign test block for arm_a vs arm_b, or None (ABSENT) if either arm has no data.
    Keys mirror `repair_vs_bestN_headroom` with the arm names substituted, so the shape is uniform."""
    if not (_arm_present(run_summaries, arm_a) and _arm_present(run_summaries, arm_b)):
        return None
    wins, ties, losses = _tally_pair(run_summaries, arm_a, arm_b)
    return {
        f"{arm_a}_gt_{arm_b}": wins,
        "ties": ties,
        f"{arm_b}_gt_{arm_a}": losses,
        "non_ties": wins + losses,
        "p_two_sided": sign_test_two_sided(wins, losses),
    }


def _pair_deltas(run_summaries: list[dict[str, Any]], arm_a: str, arm_b: str) -> list[int]:
    """Per-run (arm_a − arm_b) headroom proven-count deltas."""
    return [
        int(s["headroom_only"].get(arm_a, 0)) - int(s["headroom_only"].get(arm_b, 0))
        for s in run_summaries
    ]


def _tost_equivalence(deltas: list[int], margin: float) -> dict[str, Any]:
    """Two one-sided tests (normal approx) for equivalence of a paired mean delta to 0 within ±margin
    (prereg P2 `decoy ≈ bestN`). Equivalent iff BOTH one-sided tests reject at alpha=0.05, i.e.
    p_lower<0.05 AND p_upper<0.05. Stdlib-only. Honesty guards: never `equivalent=True` when runs<3,
    and `small_n_caveat` flags runs<15 (normal approx is thin below that)."""
    n = len(deltas)
    mean_delta = sum(deltas) / n if n else 0.0
    result: dict[str, Any] = {
        "deltas": deltas,
        "mean_delta": round(mean_delta, 4),
        "margin": margin,
        "method": "tost-normal-approx",
        "small_n_caveat": n < 15,
    }
    if n < 3:
        result.update({"p_lower": None, "p_upper": None, "equivalent": False, "reason": "runs<3"})
        return result
    variance = sum((d - mean_delta) ** 2 for d in deltas) / (n - 1)
    se = math.sqrt(variance / n)
    if (
        se == 0.0
    ):  # zero variance → all deltas identical; equivalent iff that constant is within margin
        equivalent = abs(mean_delta) < margin
        result.update(
            {
                "p_lower": 0.0 if equivalent else 1.0,
                "p_upper": 0.0 if equivalent else 1.0,
                "equivalent": equivalent,
                "se": 0.0,
            }
        )
        return result
    # H0_lower: mean <= -margin  → reject if mean well above -margin;  H0_upper: mean >= +margin
    p_lower = 1.0 - _normal_cdf((mean_delta + margin) / se)
    p_upper = _normal_cdf((mean_delta - margin) / se)
    result.update(
        {
            "p_lower": round(p_lower, 6),
            "p_upper": round(p_upper, 6),
            "equivalent": (p_lower < 0.05 and p_upper < 0.05),
            "se": round(se, 4),
        }
    )
    return result


def _ratio(numer: float, denom: float) -> float | None:
    """numer/denom, or None when denom is 0 (usage hidden by the backend) — never a fake 1.0."""
    return round(numer / denom, 4) if denom else None


def _token_parity(
    usage: dict[str, dict[str, int]], treatment: str, baseline: str
) -> dict[str, Any]:
    """Call- and token-ratios of `treatment` over `baseline` (prereg P4). usage_hidden=True when the
    backend surfaced no token counts (all zero) — then tokens_ratio is null, never a fabricated 1.0."""
    t, b = usage.get(treatment, {}), usage.get(baseline, {})
    total_tokens = sum(t.get(k, 0) for k in ("input_tokens", "output_tokens")) + sum(
        b.get(k, 0) for k in ("input_tokens", "output_tokens")
    )
    b_tokens = b.get("input_tokens", 0) + b.get("output_tokens", 0)
    t_tokens = t.get("input_tokens", 0) + t.get("output_tokens", 0)
    return {
        "treatment": treatment,
        "baseline": baseline,
        "calls_ratio": _ratio(t.get("model_calls", 0), b.get("model_calls", 0)),
        "tokens_ratio": _ratio(t_tokens, b_tokens),
        "usage_hidden": total_tokens == 0,
    }


def analyze_paths(paths: Iterable[str | Path], tost_margin: float = 1.0) -> dict[str, Any]:
    files = _jsonl_files(Path(p) for p in paths)
    (
        run_summaries,
        all_totals,
        headroom_totals,
        per_task,
        task_difficulties,
        attempt_count,
        usage,
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

    decoy_present = _arm_present(run_summaries, "decoy")
    result = {
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
        # prereg §4 controls — each None (ABSENT) on a legacy single/repair/bestN batch.
        "repair_vs_decoy_headroom": _pair_block(run_summaries, "repair", "decoy"),
        "repair_vs_plain_headroom": _pair_block(run_summaries, "repair", "plain"),
        "decoy_vs_bestN_headroom": (
            {
                **(_pair_block(run_summaries, "decoy", "bestN") or {}),
                "tost": _tost_equivalence(
                    _pair_deltas(run_summaries, "decoy", "bestN"), tost_margin
                ),
            }
            if decoy_present
            else None
        ),
        "usage": usage,
        "token_parity": {
            "repair_vs_bestN": _token_parity(usage, "repair", "bestN"),
            "repair_vs_plain": (
                _token_parity(usage, "repair", "plain")
                if _arm_present(run_summaries, "plain")
                else None
            ),
        },
        "per_task": [_rounded_counts(row) for row in task_rows],
    }
    return result


def _rounded_counts(counts: dict[str, Any]) -> dict[str, Any]:
    out = dict(counts)
    for arm in _ARMS:
        key = f"graded_{arm}"
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
    parser.add_argument(
        "--tost-margin",
        type=float,
        default=1.0,
        help="Equivalence margin (proven-tasks) for the decoy≈bestN TOST test (prereg P2).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    result = analyze_paths(args.paths, tost_margin=args.tost_margin)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(format_report(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
