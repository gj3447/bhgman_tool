# 32b re-pin, 5-arm, 10-seed — RESULTS (the decisive run)

> 2026-07-19 · governed verbatim by the frozen `PIERCE_PREREGISTRATION.md` + `KILL_CRITERIA.md`
> (band sha `4a73146e…` verified matching) · LakatoTree `pred-32b-repin-5arm-2026-07-19`
> (credence 0.45, prereg BEFORE run at harness commit `125b6ab`)
> Generator: qwen2.5:32b-instruct — dgx **ollama** q4 via tunnel :11435 (same serving stack as the
> June anchor; the `frontier:` backend label is the openai-compat client prefix, not the stack).

## Totals (headroom, 10 tasks × 10 seeds = 100 possible per arm)

| arm | proven |
|---|---|
| single | 32 |
| **repair** | **56** ★ |
| bestN | 40 |
| decoy | 41 |
| plain | 26 |

## The frozen gates — ALL PASS

- **P1 (equal-budget win, seed-fair):** repair vs bestN per-seed **8W/2T/0L, exact sign p=0.007812**
  — the June anchor statistic reproduces exactly, now under full controls. Per-task paired net
  **+16.0**, **positive on 6/10 tasks** (dbl_ge +5, le_sumto +5, sumto_mono +3, double +1,
  pow2_pos +1, sumlist_app +1); `top_task_delta_fraction` = **0.31** (dbl_ge) → **BROAD**, the June
  concentration caveat (46% sumto_mono) dissolved rather than worsened.
- **P2 (oracle-CONTENT, not volume):** repair vs decoy per-seed **9W/1T/0L, p=0.003906**; decoy vs
  bestN per-seed diffs `[-1,0,0,0,0,0,0,0,1,1]` (sum +1) — the placebo error is equivalent to no
  feedback at all. Real errors help; matched-volume bogus errors do nothing. This is, per the PROM
  literature sweep, the first placebo-controlled confirmation of a self-repair edge we know of.
- **P3 (bhgman-specific):** repair 56 > plain 26.
- **P4 (parity):** equal K=4 oracle-calls per K-arm by construction; per-attempt token ledger in the
  committed JSONL.
- **P5 (provenance):** raw `seed_0..seed_90.jsonl` committed; top-task fraction reported above.
- **K1 (power):** 9 live tasks (frozen definition) ≥ 5.

## The full picture this completes

| generator | repair vs bestN | repair vs decoy | verdict |
|---|---|---|---|
| qwen3.6-27b (NO_THINK) | 30 < 34 | **30 = 30** | channel DEAD (5 verdicts: no feedback engineering rescues it) |
| **qwen2.5:32b** | **56 > 40** (p=0.0078) | **56 > 41** (p=0.0039) | **channel LIVE — CONFIRMED under placebo control** |

HONESTY LAW: this confirms **oracle-channelled bounded repair above a capability/training floor** —
task-success rate, not raised model IQ, not collective intelligence. Scope: core-Lean band, K=4,
one live generator. Next discriminators (preregistered): qwen3:32b THINK/NO_THINK pair (size-vs-
family-vs-mode), Python control band (K6 domain generalization), vLLM serving robustness.
