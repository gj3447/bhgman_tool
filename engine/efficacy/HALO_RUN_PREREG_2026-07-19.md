# HALO-Loop live measurement — PREREGISTRATION (frozen before any run)

> 2026-07-19 · KG: `project_ultimate_ai_tool_halo_loop_2026_07_19`
> Committed BEFORE any `halo_27b_run_2026-07-19/seed_*.jsonl` exists (git mtime is the lock).
> Purpose: honestly test whether the oracle-repair loop (mechanism 3) genuinely reaches beyond
> best-of-N on a capable REACHABLE model — the "does intelligence actually increase" question,
> read under the HONESTY LAW.

## Setup (frozen)
- Generator: `qwen3.6-27b` (LAN vLLM, `http://192.168.0.23:8000/v1`, seed+temperature threaded).
  This is the **generalization arm** — a capable-but-not-frontier 27b, NOT the exact `qwen2.5:32b`
  of the committed `headroom_32b_2026-06-14` run. So this is a FRESH INDEPENDENT measurement, not a
  re-run of that anchor (no double-counting).
- Oracle: Lean 4.32.0 on Mac (`~/.elan/bin/lean`) — ungameable compile-check, graded 0/0.5/1.
- Budget: `LEAN_K=4`; 5 replications (seed offsets 0,10,20,30,40). Arms single/repair/bestN/decoy/plain
  each do K generations + K compiles (single = 1) ⇒ equal-K compute parity across the K-arms.
- Task set: the 10 headroom tasks in `lean_tasks` (+2 easy warmups), frozen: gauss, double, cnt_len,
  sumto_mono, sumlist_app, addone_len, repl_len, pow2_pos, dbl_ge, le_sumto.
- Harness: `engine.efficacy.lean_headroom_run` → `halo_27b_run_2026-07-19/seed_*.jsonl` (raw committed).

## Decision rule (frozen — evaluated on headroom GRADED score, per-task paired)
- **P1 (mechanism-3 lift):** repair graded > bestN graded on headroom. Report per-task paired delta
  AND per-seed sign test. Beating bestN is the equal-compute lift the loop must show.
- **P2 (oracle-CONTENT, not context-VOLUME):** repair > decoy AND decoy ≈ bestN. If decoy ≈ repair,
  the "win" was just more input tokens, not the oracle signal → mechanism-3 NOT shown.
- **P3 (bhgman-specific, not a generic gen-verify-gap):** repair > plain (plain-agent-with-oracle).
  If repair ≤ plain, the edge is generic "reading Lean errors", not our scaffolding.
- **Generality:** report top-task concentration. If one task carries ≥50% of the net delta OR <40%
  of headroom tasks are positive ⇒ label **CONCENTRATED**, not a general capability.

## NULL / kill handling (frozen)
- repair ≤ bestN on headroom graded ⇒ **mechanism-3 NOT SHOWN at 27b** = UNMEASURABLE, report as a
  null and keep OPEN. A null is NOT a refutation (the idea is not disproven; this setup did not show it).
- Saturation (all arms prove everything) ⇒ wrong tier/band artifact, re-run at a harder task band —
  NOT "no effect".

## Honest label (frozen — the only claim a positive result licenses)
A positive P1∧P2∧P3 means: **the oracle-repair loop reaches beyond best-of-N via the ungameable Lean
oracle — bounded, oracle-channelled search compute.** It is NOT raised model IQ, NOT discovery, and
NOT collective intelligence (HONESTY LAW). It raises task-success RATE; the model is not smarter.

## Analysis (frozen)
`engine/efficacy/analyze_headroom_pertask_paired.py::analyze(<out-dir>)` — per-task paired graded
delta + top-task concentration + per-seed sign test, over the frozen headroom set. Verdict cites
these verbatim; no post-hoc re-banding of the task set.
