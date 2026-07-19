# HALO-Loop 27b live measurement — RESULTS

> 2026-07-19 · prereg: `../HALO_RUN_PREREG_2026-07-19.md` (committed before this run)
> Generator: qwen3.6-27b (LAN vLLM), Oracle: Lean 4.32 (Mac), K=4, 5 seeds (0,10,20,30,40).
> KG: `project_ultimate_ai_tool_halo_loop_2026_07_19`

## Result — headroom (10 tasks × 5 seeds = 50 possible proven per arm)

| arm | proven / 50 | avg/seed |
|---|---|---|
| single | 23 | 4.6 |
| repair | 30 | 6.0 |
| **bestN** | **34** | **6.8** ★ |
| decoy | 30 | 6.0 |
| plain | 15 | 3.0 |

## Verdict against the frozen decision rule

- **P1 repair > bestN — FALSE.** repair 30 < bestN 34. Per-seed sign test 1W/1T/3L, p=0.625
  (not significant, trending the wrong way); per-task paired net delta **−4.0**, only 1/10 tasks
  positive. The committed 32b `p=0.0078` does **not** generalize to 27b.
- **P2 repair > decoy — FALSE, and decisive.** repair 30 = decoy 30. Feeding the loop the REAL Lean
  error vs a BOGUS same-volume error gives the identical result ⇒ **the oracle CONTENT is not being
  used at 27b.** This is the controlled confirmation of the attempt-log diagnosis (conditioning
  collapses diversity; the 27b cannot convert a compiler error into a corrective edit).
- **P3 repair > plain — TRUE.** repair 30 > plain 15. The bhgman scaffolding (structured prompt,
  per-round seed jitter, expert persona) beats a plain generic agent-with-oracle — but that is
  OPERATIONAL scaffolding, not the oracle-repair mechanism.

## Honest conclusion (HONESTY LAW)

At 27b, **mechanism-3 (oracle-repair) is NOT SHOWN — best-of-N (pure sampling) wins**, and the
oracle signal is not load-bearing (repair ≈ decoy). This is a clean NULL for repair-vs-bestN at this
model — **not a refutation of the mechanism**, which held at 32b headroom under its own (concentrated,
PLAUSIBLE-uncontrolled) evidence. The carrying tasks even flip between models (le_sumto: 32b +2 →
27b −3), underscoring that the lift is model/regime-specific.

**Implication for the fix:** because repair ≈ decoy (the 27b ignores the oracle content), the real
lever is not "explore vs exploit budget" alone but **making the model ACT on the oracle** —
Reflexion-style error distillation (turn the raw Lean dump into a short actionable note) and/or a
more capable generator (the reachable 32b / frontier). The explore-then-repair-BEST hybrid
(`hybrid_repair_ab.py`, fix #1) is being A/B'd next; the honest prediction is that its repair-half
adds little at 27b and the decisive gain needs the feedback-distillation lever (PROM axis B).
