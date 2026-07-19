"""HALO fix #2 (frontier-tightening node): self-distilled REFLECT arm + 3-arm A/B.

Tests PROM axis B1+C6 on the 27b generator itself (a stronger reflector — 122b/35b — was
UNAVAILABLE 2026-07-19: 122b OOM, gemma4:31b empty output, spark1 vLLM backend down, no API key).
So this is the SELF-reflection intermediate, NOT the stronger-model win path (Q-32b-reflector).

Mechanism: on a failed proof, a SEPARATE reflection call distills the raw Lean error into ONE
actionable sentence (Reflexion), then the next attempt is conditioned on that NOTE with the verbatim
failing proof DROPPED (PROM C6 — the anchoring re-exposure that caused the 14 re-emits). This isolates
whether DISTILLATION alone (no stronger model) lifts repair.

HONESTY LAW / compute: reflect spends K generations PLUS up to K-1 extra reflection calls, so it is a
BIGGER compute class than bestN@K. The honest primary contrast is reflect vs repair (both K
generations; reflect adds distillation) — does distilling the error help over raw-error repair? A
reflect>bestN claim must be read as "at extra reflect compute", never a 27b equal-compute win.
Olausson (ICLR 2024) predicts weak self-reflection rarely helps; a null here tightens the frontier to
"a genuine win needs a stronger reflector".

# KG: project_ultimate_ai_tool_halo_loop_2026_07_19, Q-32b-reflector-2026-07-19 (blocked → self-reflect intermediate)
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from engine.efficacy.lean_headroom_run import (
    TASKS,
    _THINK,
    _arm_bestn,
    _arm_repair,
    _eval_attempt,
    _extract_proof,
    _gen,
    _log_record,
    _make_complete,
    _run_id,
    _usage,
    lean_available,
)

_REFLECT_SYS = (
    "You are a Lean 4 (core, NO Mathlib) proof-debugging expert. In ONE sentence, state the "
    "mathematical reason the attempt failed and the single concrete tactic or lemma to try next. "
    "Output only that one sentence — no code, no proof term, no markdown."
)


def _distill(task, complete, proof, error, seed) -> str:
    """One separate reflection call: raw Lean error -> one actionable hint sentence."""
    user = (
        f"theorem {task.name} {task.signature}\n"
        f"Failed proof term:\n{proof}\n\nLean error:\n{error}\n\nGive the one-sentence hint."
    )
    note = complete([{"role": "system", "content": _REFLECT_SYS}, {"role": "user", "content": user}], seed)
    return _THINK.sub(" ", note).strip()[:400]


def _reflect_prompt(task, note: str):
    sys = {
        "role": "system",
        "content": "You are a Lean 4 expert (core, NO Mathlib). Output ONLY the proof term that goes "
        "after ':=' — no theorem line, no markdown, no prose.",
    }
    pre = f"Given:\n{task.preamble}\n\n" if task.preamble else ""
    # NOTE: the verbatim failing proof is deliberately DROPPED (PROM C6); only the distilled hint.
    ask = (
        f"{pre}Prove:\ntheorem {task.name} {task.signature} := ?\n\n"
        f"Expert hint (a previous attempt failed): {note}\n\nProvide the proof after ':='."
    )
    return [sys, {"role": "user", "content": ask}]


def _arm_reflect(task, complete, k, off=0, *, log=None, run_meta=None):
    """Round 1 fresh; rounds 2..K = distill(error)->note, then generate from the NOTE (proof dropped).
    Keep-best. Uses K generations + (K-1) reflect calls (a bigger compute class than bestN)."""
    proof = _gen(task, complete, off)
    ti, to = _usage(complete)
    v = _eval_attempt(task, proof, arm="reflect", attempt=1, seed=off, log=log, run_meta=run_meta,
                      used_feedback=False, in_tok=ti, out_tok=to)
    if v.proven:
        return True, 1.0
    best = v.graded_score
    prev_proof, prev_err = proof, v.error_tail
    for i in range(1, k):
        note = _distill(task, complete, prev_proof, prev_err, off + i)
        proof = _extract_proof(complete(_reflect_prompt(task, note), off + i))
        ti, to = _usage(complete)
        v = _eval_attempt(task, proof, arm="reflect", attempt=i + 1, seed=off + i, log=log,
                          run_meta=run_meta, prior_proof=prev_proof, used_feedback=True,
                          in_tok=ti, out_tok=to)
        best = max(best, v.graded_score)
        if v.proven:
            return True, 1.0
        prev_proof, prev_err = proof, v.error_tail
    return False, best


def _run_ab_once(complete, backend, *, k, seed_offset, log=None, run_id=None):
    run_meta = {"run_id": run_id or _run_id(seed_offset), "backend": backend, "K": k, "seed_offset": seed_offset}
    _log_record(log, {"record_type": "run_start", **run_meta, "arms": ["reflect", "repair", "bestN"],
                      "n_tasks": len(TASKS),
                      "tasks": [{"name": t.name, "difficulty": t.difficulty, "signature": t.signature} for t in TASKS]})
    print(f"[reflect-ab] backend={backend} K={k} seed_offset={seed_offset} n={len(TASKS)}")
    rows = []
    for t in TASKS:
        f_p, f_g = _arm_reflect(t, complete, k, seed_offset, log=log, run_meta=run_meta)
        r_p, r_g = _arm_repair(t, complete, k, seed_offset, log=log, run_meta=run_meta)
        b_p, b_g = _arm_bestn(t, complete, k, seed_offset, log=log, run_meta=run_meta)
        rows.append({"task": t.name, "difficulty": t.difficulty, "reflect": f_p, "repair": r_p, "bestN": b_p,
                     "graded_reflect": f_g, "graded_repair": r_g, "graded_bestN": b_g})
        _log_record(log, {"record_type": "task_summary", "run_id": run_meta["run_id"], "K": k,
                          "seed_offset": seed_offset, "task": t.name, "difficulty": t.difficulty,
                          "arms": {"reflect": {"proven": f_p, "graded_score": f_g},
                                   "repair": {"proven": r_p, "graded_score": r_g},
                                   "bestN": {"proven": b_p, "graded_score": b_g}}})
        print(f"  [{t.difficulty:8s}] {t.name:12s} proven f/r/b={int(f_p)}/{int(r_p)}/{int(b_p)} "
              f"graded={f_g:.1f}/{r_g:.1f}/{b_g:.1f}")
    hr = [r for r in rows if r["difficulty"] == "headroom"]

    def sp(key):
        return sum(1 for r in hr if r[key])

    out = {**run_meta, "n_headroom": len(hr),
           "headroom_proven": {"reflect": sp("reflect"), "repair": sp("repair"), "bestN": sp("bestN")},
           "reflect_beats_bestN_proven": sp("reflect") > sp("bestN"),
           "reflect_beats_repair_proven": sp("reflect") > sp("repair")}
    _log_record(log, {"record_type": "run_summary", **out})
    print(json.dumps(out, indent=1))
    return out


def _parse_args(argv=None):
    p = argparse.ArgumentParser(description="3-arm reflect vs repair vs bestN A/B (self-distilled).")
    p.add_argument("--k", type=int, default=int(os.environ.get("LEAN_K", "4")))
    p.add_argument("--replications", type=int, default=int(os.environ.get("LEAN_REPLICATIONS", "1")))
    p.add_argument("--seed-offset", type=int, default=int(os.environ.get("SEED_OFFSET", "0")))
    p.add_argument("--seed-step", type=int, default=int(os.environ.get("LEAN_SEED_STEP", "10")))
    p.add_argument("--out-dir", default=os.environ.get("LEAN_OUT_DIR"))
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = _parse_args(argv)
    if args.k < 1 or args.replications < 1:
        print("[reflect-ab] --k and --replications must be >= 1.")
        return 2
    if not lean_available():
        print("[reflect-ab] lean toolchain not on PATH — cannot run.")
        return 2
    complete, backend = _make_complete()
    out_dir = Path(args.out_dir) if args.out_dir else None
    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
    for rep in range(args.replications):
        seed_offset = args.seed_offset + rep * args.seed_step
        rid = _run_id(seed_offset)
        if out_dir is None:
            _run_ab_once(complete, backend, k=args.k, seed_offset=seed_offset)
            continue
        with (out_dir / f"seed_{seed_offset}.jsonl").open("w", encoding="utf-8") as log:
            print(f"[reflect-ab] raw_jsonl={out_dir / f'seed_{seed_offset}.jsonl'}")
            _run_ab_once(complete, backend, k=args.k, seed_offset=seed_offset, log=log, run_id=rid)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
