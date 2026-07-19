"""HALO-Loop fix #1: explore-then-repair-BEST arm + a 3-arm equal-compute A/B.

MEASURED failure being fixed (`halo_27b_run_2026-07-19`, live qwen3.6-27b, Lean 4.32, K=4):
the pure sequential repair arm does NOT beat best-of-N at 27b. Attempt-log root cause: conditioning
on the FAILING proof collapses diversity (repair 2.48 vs bestN 3.43 unique proofs/task; repair
re-emits the identical broken proof 14 tasks vs bestN 3) and the 27b cannot convert a raw Lean error
into a corrective edit (repair feedback→fix 6 < bestN 8). decoy (bogus error, same context volume)
has the same low diversity as repair, so it is the CONDITIONING ITSELF that collapses exploration.

FIX (AlphaCodium secret): explore N INDEPENDENT candidates first, keep the best partial, then
oracle-repair the BEST-SO-FAR (never the last attempt / a regression), advancing the anchor only when
a repair IMPROVES it (keep-best monotone). This restores exploration diversity AND stops the
basin-anchoring re-emission. Equal K oracle-calls with repair/bestN ⇒ hybrid-vs-{repair,bestN} is a
clean equal-compute A/B.

HONESTY LAW: a hybrid win = higher task-success RATE via oracle-channelled bounded search, NOT raised
model IQ. At strictly equal K this is an explore/exploit trade (hybrid spends ~K/2 on exploration vs
bestN's K), so dominance is an EMPIRICAL question the A/B decides — not a structural guarantee.

Run: BHGMAN_LLM_BASE_URL=... BHGMAN_LLM_MODEL=... LEAN_K=4 \
     uv run python -m engine.efficacy.hybrid_repair_ab --replications 5 --out-dir <dir>

# KG: project_ultimate_ai_tool_halo_loop_2026_07_19, HALO_LOOP_DESIGN_2026-07-19 (fix #1)
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, TextIO

from engine.efficacy.lean_headroom_run import (
    TASKS,
    _arm_bestn,
    _arm_repair,
    _eval_attempt,
    _gen,
    _log_record,
    _make_complete,
    _run_id,
    _usage,
    lean_available,
)


def _arm_hybrid(task, complete, k, off=0, *, log: TextIO | None = None, run_meta=None):
    """Explore N independent draws → oracle-repair the BEST-so-far (keep-best monotone).

    n_explore = ceil(k/2) independent attempts (== bestN diversity for half the budget); the rest
    repair the best partial, anchoring on the best-so-far and advancing the anchor ONLY on an
    improvement — so a regressing / identical re-emission never becomes the next anchor. Equal K
    oracle-calls with `_arm_repair` / `_arm_bestn`.
    """
    n_explore = max(1, (k + 1) // 2)
    best_proof: str | None = None
    best_err: str | None = None
    best_score = -1.0
    # Phase 1 — EXPLORE: independent draws, no feedback (bestN-like diversity).
    for i in range(n_explore):
        proof = _gen(task, complete, off + i)
        ti, to = _usage(complete)
        v = _eval_attempt(
            task, proof, arm="hybrid", attempt=i + 1, seed=off + i,
            log=log, run_meta=run_meta, used_feedback=False, in_tok=ti, out_tok=to,
        )
        if v.proven:
            return True, 1.0
        if v.graded_score > best_score:
            best_proof, best_err, best_score = proof, v.error_tail, v.graded_score
    # Phase 2 — EXPLOIT: repair the BEST-so-far; keep-best monotone (never chase a regression).
    for j in range(k - n_explore):
        proof = _gen(task, complete, off + n_explore + j, best_proof, best_err)
        ti, to = _usage(complete)
        v = _eval_attempt(
            task, proof, arm="hybrid", attempt=n_explore + j + 1, seed=off + n_explore + j,
            log=log, run_meta=run_meta, prior_proof=best_proof, used_feedback=True,
            in_tok=ti, out_tok=to,
        )
        if v.proven:
            return True, 1.0
        if v.graded_score > best_score:
            best_proof, best_err, best_score = proof, v.error_tail, v.graded_score
    return False, max(best_score, 0.0)


def _run_ab_once(complete, backend, *, k, seed_offset, log=None, run_id=None):
    run_meta = {
        "run_id": run_id or _run_id(seed_offset),
        "backend": backend, "K": k, "seed_offset": seed_offset,
    }
    _log_record(log, {
        "record_type": "run_start", **run_meta, "arms": ["hybrid", "repair", "bestN"],
        "n_tasks": len(TASKS),
        "tasks": [{"name": t.name, "difficulty": t.difficulty, "signature": t.signature} for t in TASKS],
    })
    print(f"[hybrid-ab] backend={backend} K={k} seed_offset={seed_offset} n={len(TASKS)}")
    rows = []
    for t in TASKS:
        h_p, h_g = _arm_hybrid(t, complete, k, seed_offset, log=log, run_meta=run_meta)
        r_p, r_g = _arm_repair(t, complete, k, seed_offset, log=log, run_meta=run_meta)
        b_p, b_g = _arm_bestn(t, complete, k, seed_offset, log=log, run_meta=run_meta)
        rows.append({
            "task": t.name, "difficulty": t.difficulty,
            "hybrid": h_p, "repair": r_p, "bestN": b_p,
            "graded_hybrid": h_g, "graded_repair": r_g, "graded_bestN": b_g,
        })
        _log_record(log, {
            "record_type": "task_summary", "run_id": run_meta["run_id"], "K": k,
            "seed_offset": seed_offset, "task": t.name, "difficulty": t.difficulty,
            "arms": {
                "hybrid": {"proven": h_p, "graded_score": h_g},
                "repair": {"proven": r_p, "graded_score": r_g},
                "bestN": {"proven": b_p, "graded_score": b_g},
            },
        })
        print(f"  [{t.difficulty:8s}] {t.name:12s} proven h/r/b={int(h_p)}/{int(r_p)}/{int(b_p)} "
              f"graded={h_g:.1f}/{r_g:.1f}/{b_g:.1f}")
    hr = [r for r in rows if r["difficulty"] == "headroom"]

    def sp(key):
        return sum(1 for r in hr if r[key])

    out = {
        **run_meta, "n_headroom": len(hr),
        "headroom_proven": {"hybrid": sp("hybrid"), "repair": sp("repair"), "bestN": sp("bestN")},
        "headroom_graded": {
            "hybrid": round(sum(r["graded_hybrid"] for r in hr), 2),
            "repair": round(sum(r["graded_repair"] for r in hr), 2),
            "bestN": round(sum(r["graded_bestN"] for r in hr), 2),
        },
        "hybrid_beats_bestN_proven": sp("hybrid") > sp("bestN"),
        "hybrid_beats_repair_proven": sp("hybrid") > sp("repair"),
    }
    _log_record(log, {"record_type": "run_summary", **out})
    print(json.dumps(out, indent=1))
    return out


def _parse_args(argv=None):
    p = argparse.ArgumentParser(description="3-arm hybrid vs repair vs bestN equal-compute A/B.")
    p.add_argument("--k", type=int, default=int(os.environ.get("LEAN_K", "4")))
    p.add_argument("--replications", type=int, default=int(os.environ.get("LEAN_REPLICATIONS", "1")))
    p.add_argument("--seed-offset", type=int, default=int(os.environ.get("SEED_OFFSET", "0")))
    p.add_argument("--seed-step", type=int, default=int(os.environ.get("LEAN_SEED_STEP", "10")))
    p.add_argument("--out-dir", default=os.environ.get("LEAN_OUT_DIR"))
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = _parse_args(argv)
    if args.k < 1 or args.replications < 1:
        print("[hybrid-ab] --k and --replications must be >= 1.")
        return 2
    if not lean_available():
        print("[hybrid-ab] lean toolchain not on PATH — cannot run.")
        return 2
    complete, backend = _make_complete()
    out_dir = Path(args.out_dir) if args.out_dir else None
    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
    summaries = []
    for rep in range(args.replications):
        seed_offset = args.seed_offset + rep * args.seed_step
        rid = _run_id(seed_offset)
        if out_dir is None:
            summaries.append(_run_ab_once(complete, backend, k=args.k, seed_offset=seed_offset))
            continue
        with (out_dir / f"seed_{seed_offset}.jsonl").open("w", encoding="utf-8") as log:
            print(f"[hybrid-ab] raw_jsonl={out_dir / f'seed_{seed_offset}.jsonl'}")
            summaries.append(
                _run_ab_once(complete, backend, k=args.k, seed_offset=seed_offset, log=log, run_id=rid)
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
