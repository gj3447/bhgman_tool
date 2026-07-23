# Strong-reflector A/B — RESULTS (claude-sonnet-4-6 distills, 27b generates)

> 2026-07-19 · prereg commit `ce65ee7` (before the run) · LakatoTree `pred-strong-reflector-sonnet-2026-07-19`
> KG: `project_ultimate_ai_tool_halo_loop_2026_07_19` · closes `Q-32b-reflector-2026-07-19` (negative)

## Result (seeds 0+10, K=4, headroom of 20)

| arm | proven |
|---|---|
| reflect (claude hints) | **9** |
| repair (raw error) | 10 |
| **bestN** | **14** ★ |

Direct comparison, same seeds: self-reflect run was 10/10/14 — the claude reflector changed nothing
(9≈10 within noise) and still LOSES to best-of-N by −5.

## Honest verdict

**The literature-grounded "stronger feedback wins" path (Olausson) FAILED at this generator.** Even a
frontier-quality distilled hint does not lift the 27b: the bottleneck is not feedback quality, not
conditioning structure (hybrid tie), not distillation (self-reflect null) — it is the **generator's
capability floor**. `q<p` is a property of the 27b itself: it cannot convert even a correct strategy
hint into a compiling Lean proof term.

My preregistered credence was 0.55 (wrong) — recorded as an honest calibration miss.

## Caveats (honest, not excuses)

- Hint-domain mismatch observed: despite the "core Lean, NO Mathlib" system prompt, sonnet hints
  sometimes suggest Mathlib-only tactics (e.g. `ring`), which fail in core. A tighter reflector
  prompt might improve hint validity — but reflect≈repair (9≈10) suggests hints neither helped nor
  actively hurt; the generator simply cannot execute strategies it is handed.
- 2 seeds = directional, not confirmatory. The direction is consistent across all 4 experiments.

## Programme state after 5 deterministic verdicts (LakatoTree BhgmanCeilingPierce)

1. 27b generalization of the 32b lift → **rejected** (repair<bestN; repair=decoy)
2. hybrid explore-then-repair-BEST → **equivalent** (tie 34=34)
3. self-distilled reflect → **rejected** (−4)
4. strong-reflector (this) → **rejected** (−5)
5. (anchor) 32b raw-error repair → PLAUSIBLE-uncontrolled p=0.0078, concentrated

**Surviving frontier = the GENERATOR, not the feedback:** the only untested lever left is a capable
≥32b generator (the original anchor's regime). Every feedback-engineering lever at a below-floor
generator is now measured dead. Honest programme default (per KILL_CRITERIA time-box): operational
substrate, with the mechanism-3 cognitive edge alive ONLY in the capable-generator regime.
