"""Honest per-TASK paired re-analysis of the committed 32b lean-headroom A/B.

The committed VERDICT (headroom_32b_2026-06-14/VERDICT.md) reports a per-SEED exact
sign test: repair vs best-of-N = 8W/2T/0L over 10 runs, p=0.0078. That statistic
counts SEEDS as the independent unit. The adversarial review (PROM 16 HALO-Loop,
project_ultimate_ai_tool_halo_loop_2026_07_19) demanded the per-TASK paired view +
top-task concentration, because significance driven by run-count over the same few
carrying tasks is the exact seed-Goodhart pattern the pierce prereg (K6) bars.

This module recomputes, from the SAME committed JSONL (no LLM, no re-run):
  - per-task paired net delta (Σ_seeds repair-score − bestN-score), headroom only,
  - top-task concentration (what fraction of the net signal one task carries),
  - generality (how many headroom tasks have net delta > 0),
  - the per-seed sign test, to confirm the committed p reproduces.

Honest finding: the p=0.0078 REPRODUCES, but the signal is carried by 4/10 tasks and
~46% of it by `sumto_mono` alone → the anchor must ship as
'PLAUSIBLE-uncontrolled, concentrated', not 'measured positive capability'.

# KG: project_ultimate_ai_tool_halo_loop_2026_07_19, project_bhgman_ceiling_pierce_programme_2026_07_12
# KG: PIERCE_PREREGISTRATION.md K6 (per-task paired mandatory), KILL_CRITERIA.md K4 (generality)
"""
from __future__ import annotations

import collections
import glob
import json
import math
import os
from pathlib import Path
from typing import Any

DEFAULT_DATA_DIR = Path(__file__).parent / "headroom_32b_2026-06-14"


def load_task_scores(data_dir: str | Path = DEFAULT_DATA_DIR):
    """Return ((seed, task) -> {arm: graded_score}), (task -> difficulty)."""
    cell: dict[tuple[int, str], dict[str, float]] = collections.defaultdict(dict)
    diff: dict[str, str] = {}
    paths = sorted(glob.glob(os.path.join(str(data_dir), "seed_*.jsonl")))
    if not paths:
        raise FileNotFoundError(f"no seed_*.jsonl under {data_dir}")
    for fp in paths:
        with open(fp) as fh:
            for line in fh:
                if not line.strip():
                    continue
                r = json.loads(line)
                if r.get("record_type") != "task_summary":
                    continue
                key = (r["seed_offset"], r["task"])
                diff[r["task"]] = r["difficulty"]
                for arm, v in r["arms"].items():
                    cell[key][arm] = float(v["graded_score"])
    return cell, diff


def per_task_paired_delta(cell, seeds, tasks, *, a="repair", b="bestN"):
    """Σ_seeds (score[a] − score[b]) per task."""
    out: dict[str, float] = {}
    for t in tasks:
        out[t] = sum(cell[(s, t)].get(a, 0.0) - cell[(s, t)].get(b, 0.0) for s in seeds)
    return out


def per_seed_sign_test(cell, seeds, tasks, *, a="repair", b="bestN"):
    """Two-sided exact sign test on per-seed (Σ_tasks a−b), ties ignored."""
    w = t = loss = 0
    for s in seeds:
        d = sum(cell[(s, task)].get(a, 0.0) - cell[(s, task)].get(b, 0.0) for task in tasks)
        if d > 0:
            w += 1
        elif d < 0:
            loss += 1
        else:
            t += 1
    nonties = w + loss
    if nonties == 0:
        return w, t, loss, 1.0
    tail = sum(math.comb(nonties, k) for k in range(max(w, loss), nonties + 1))
    p = min(1.0, 2 * tail / (2 ** nonties))
    return w, t, loss, p


def analyze(data_dir: str | Path = DEFAULT_DATA_DIR) -> dict[str, Any]:
    cell, diff = load_task_scores(data_dir)
    seeds = sorted({s for (s, _t) in cell})
    tasks = sorted({t for (_s, t) in cell})
    headroom = [t for t in tasks if diff[t] == "headroom"]

    deltas = per_task_paired_delta(cell, seeds, headroom)
    total = sum(deltas.values())
    pos = {t: d for t, d in deltas.items() if d > 0}
    top_task = max(deltas, key=deltas.get)
    top_delta = deltas[top_task]
    w, tie, loss, p = per_seed_sign_test(cell, seeds, headroom)

    top_frac = (top_delta / total) if total else 0.0
    return {
        "seeds": len(seeds),
        "headroom_tasks": len(headroom),
        "per_task_delta": deltas,
        "total_net_delta": total,
        "positive_tasks": sorted(pos, key=lambda x: -pos[x]),
        "n_positive_tasks": len(pos),
        "top_task": top_task,
        "top_task_delta": top_delta,
        "top_task_concentration": top_frac,
        "per_seed_sign_test": {"W": w, "T": tie, "L": loss, "p": p},
        # honest label: reproduces but concentrated → not a general measured capability.
        "verdict": (
            "PLAUSIBLE-uncontrolled (concentrated)"
            if top_frac >= 0.40 or len(pos) / len(headroom) < 0.5
            else "broad"
        ),
    }


def _main() -> None:
    r = analyze()
    print(f"seeds={r['seeds']} headroom_tasks={r['headroom_tasks']}")
    print("per-task net delta (repair−bestN), headroom:")
    for t in sorted(r["per_task_delta"], key=lambda x: -r["per_task_delta"][x]):
        print(f"  {t:14s} {r['per_task_delta'][t]:+5.1f}")
    st = r["per_seed_sign_test"]
    print(f"total net={r['total_net_delta']:+.1f}  positive_tasks={r['n_positive_tasks']}/{r['headroom_tasks']}")
    print(f"top={r['top_task']} ({100*r['top_task_concentration']:.0f}% of net)")
    print(f"per-seed sign test: {st['W']}W/{st['T']}T/{st['L']}L  p={st['p']:.6f}")
    print(f"verdict: {r['verdict']}")


if __name__ == "__main__":
    _main()
