# Lean headroom fair-test — oracle-guided repair loop vs best-of-N (2026-06-05)

> Answers part of the open hypothesis in `VERDICT.md` §3 ("the one fair test ... was never run").
> Runner: `engine/efficacy/lean_headroom_run.py` (+ `SEED_OFFSET` replication control added this run).
> Verified per `feedback_verify_async_results_before_writeup`: process exited, JSON re-fetched + parsed.

## What was tested

The FunSearch-style **loop** vs the **best-of-N** control, at **equal K budget**, on real Lean 4 proving
with an **ungameable oracle** (statement fixed by construction; `#print axioms` rejects `sorryAx`; a wrong
or weakened proof cannot compile). Three arms, K=4:

| arm | what it is | the claim it tests |
|---|---|---|
| `single` | one proof attempt | bare model |
| `repair` | attempt → feed the Lean error back → re-attempt … (×K) | **the loop** (model + ungameable oracle feedback) |
| `bestN` | K independent attempts (varied seed), first that PROVES | the control (generate-and-verify, no loop) |

**Repair > bestN at equal K ⇒ the oracle-feedback loop adds value beyond just "more tries + a verifier".**
That is the cognitive-uplift claim. Repair ≈ bestN ⇒ the loop is operational, not cognitive.

## Setup (the fairness conditions)

- **Model**: `qwen2.5:32b-instruct` (ollama on dgx GB10, via SSH tunnel; the strongest reachable model —
  *not* frontier; this is the one axis the harness docstring admits it cannot fix).
- **Oracle**: real `lean` 4.30 compiler, core (no Mathlib), `#print axioms` no-`sorryAx` gate. Mac-local.
- **Fair bestN**: seed threaded per attempt (`P1_TEMP=0.8`) → genuinely independent draws, not the
  collapsed-to-single confound found 2026-06-03. Verified: seed 1 and seed 2 produce *different* proofs.
- **Replication**: `SEED_OFFSET ∈ {0,10,20,30,40}` → **5 independent replications** (the crux — the prior
  n=1/n=2 signals *vanished* on reproduction). The offset is symmetric across all three arms (no bias).
- Tasks: 6 (`lean_tasks.py`); 4 tagged `headroom` (custom recursive def + a property `omega`/`simp` do
  not one-shot, verified 2026-06-03), 2 `easy`.

## Result — 5 replications

**Headroom only (4 tasks), proven count per arm:**

| seed_offset | single | repair (loop) | bestN (control) | repair > bestN? |
|---|---|---|---|---|
| 0  | 1 | 2 | 2 | no (tie) |
| 10 | 1 | 2 | 2 | no (tie) |
| 20 | 1 | 2 | 2 | no (tie) |
| 30 | 1 | 2 | 2 | no (tie) |
| 40 | 1 | 1 | 2 | **no (bestN wins)** |

**Repair never beats bestN on headroom across 5 replications** (4 ties + 1 bestN-win). Reproducible — this
is *not* the noise that vanished before; it is a stable negative.

**Per-task, summed over the 5 runs (proven / 5):**

| task | difficulty | single | repair | bestN | reads as |
|---|---|---|---|---|---|
| `zero_add` | easy | 0/5 | **5/5** | 2/5 | loop **wins** — but on an *easy* task (error points straight at the fix) |
| `app_nil` | easy | 5/5 | 5/5 | 5/5 | ceiling (no discrimination) |
| `gauss` | headroom | 0/5 | 0/5 | 0/5 | **floor** (all arms fail) |
| `double` | headroom | 0/5 | 0/5 | 0/5 | **floor** (all arms fail) |
| `cnt_len` | headroom | 5/5 | 5/5 | 5/5 | ceiling (no discrimination) |
| `sumto_mono` | headroom | 0/5 | **4/5** | 5/5 | the *only* discriminating headroom task — **bestN ≥ loop** |

## Verdict

**At the qwen2.5:32b tier, the oracle-guided repair loop does NOT beat best-of-N on headroom Lean tasks —
reproducibly (5/5).** The loop's *only* reproducible win is `zero_add`, an **easy** task where the Lean
error text names the fix directly (local repair, not search). On the single headroom task that actually
discriminates (`sumto_mono`), best-of-N matches-or-beats the loop (5/5 vs 4/5).

This **refines** the `operational-substrate, not cognitive-amplifier` verdict and adds a mechanism: the
loop's value concentrates where the oracle's error is *directly actionable* (easy, local fixes) — exactly
where you didn't need a loop. Where genuine multi-step construction is required (headroom), the loop adds
nothing over independent retries + the same verifier. The prior verdict holds for the repair-loop variant,
now with a **reproducible** fair test behind it rather than an unrun hypothesis.

## Honest limitations (what stays open)

1. **Not frontier.** qwen2.5:32b is strong-ish, not a FunSearch/AlphaEvolve-class model. A frontier model
   could lift the floor tasks (`gauss`/`double`) off 0 and create real headroom discrimination. This axis
   the harness cannot fix locally; it is a *negative at the 32b tier*, not a universal close.
2. **Thin headroom band.** Of 4 headroom tasks, 2 are floor (0/0/0) and 1 is ceiling (5/5/5). Only
   `sumto_mono` discriminates among arms — so the headroom conclusion effectively rests on **n=1 live task**.
   A wider, frontier-calibrated headroom set is needed for a powered headroom comparison.
3. **Tests the repair loop, NOT F3 islands.** This is ARM2 (oracle-guided repair) vs ARM3 (best-of-N).
   The load-bearing FunSearch ingredient — **F3 population/island diversity** — is still not implemented,
   so the *full* FunSearch-island hypothesis remains untested.
4. K=4, binary per-task oracle (proven/not). Larger K or a graded oracle could shift the picture.

**Net: the repair-loop ≤ best-of-N hypothesis on headroom now has a reproducible fair test (negative at the
32b tier). The residual open axes are: frontier model × richer headroom band × real F3 islands × graded
oracle.** The question is narrower than "never run," not closed.
