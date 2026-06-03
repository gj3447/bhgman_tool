# Heterogeneous composition A/B — run log (2026-06-03)

> Results of executing `hetero_composition_run.py` per `COMPOSITION_HETERO_PREREG.md`.
> **Backend available: only `qwen2.5:1.5b-instruct` (local ollama).** That is BELOW the pre-reg §4
> strong-model ceiling, so these are *underpowered* runs. Recorded honestly; **NOT** read as closure.

## Runs

| run | tasks | budget | ARM1 (base best-of-N) | ARM2 (hetero pipeline) | ARM3 (verify-only) | realized | Δ(ARM2−ARM1) |
|---|---|---|---|---|---|---|---|
| 1 | 4 easy | 1000 | **4/4** | 3/4 | 4/4 | False | mean −0.25, CI_lo −0.75 |
| 2 | 8 hard+med | 1500 | **8/8** | ~3–4/8 | ~5/8 | False | mean −0.375, CI_lo −0.875 |

Per-task (run 2): spiral_order ARM1=1/ARM2=0, int_to_roman 1/0, max_subarray 1/1, longest_common_prefix 1/1, flatten 1/0, roman_to_int 1/0, merge_sorted 1/1.

## What actually happened

1. **ARM1 (base best-of-N) saturated the whole task set** — 1/1 on every task, even the "hard" ones. qwen-1.5B + best-of-N at this budget already solves all 15 LEVER-style tasks. **Zero headroom** for composition to demonstrate an advantage.
2. **ARM2 (the heterogeneous pipeline) was consistently WORSE** (−0.25, −0.375). The gather→connect→abstract→prune→verify→realize transforms repeatedly took a *correct* base solution and **broke it** (is_palindrome, spiral_order, int_to_roman, flatten, roman_to_int all regressed from 1→0). On a weak model, each re-edit is a chance to introduce a bug.
3. **ARM3 (verify-only) ≈ ARM1 to slightly worse** — the single gate doesn't help either when the base is already correct.

## Honest interpretation (what this does and does NOT say)

- **Does NOT answer the hypothesis.** Both runs are doubly compromised — *underpowered model* (1.5B ≪ frontier) **and** *saturated tasks* (ARM1=1 everywhere ⇒ no headroom). This is exactly the uninformative-null regime the pre-reg (§4) and the evolve_loop postmortem (`VERDICT.md` §3) warned about. **The composition hypothesis remains OPEN.** Closing it on this would repeat the premature-close trap.
- **Does weakly confirm one thing** — *within-competence, heterogeneous re-editing has downside risk.* When the base solution is already correct, decomposing into stages and re-generating each stage can only stay equal or break it; on a weak model it broke it ~40% of the time. This is consistent with, and reinforces, the **operational-substrate verdict** (within-competence, structure doesn't add cognition and can subtract reliability).
- **The fair test still needs:** (a) a frontier-class model (above the self-improvement floor), and (b) tasks *outside* that model's single-shot competence (so ARM1 < 1 and there is headroom). Neither was available. The harness + gate are ready (`hetero_composition_ab.py`, 4/4 fire-test); only the backend is missing.

## One-line

On the only runnable regime (weak model + saturated tasks) the 7-commander composition performed **worse** than a single base call — but that is the *predicted uninformative null*, and reinforces operational-substrate within competence; it is **not** evidence on the headroom-regime hypothesis, which stays OPEN pending a frontier backend.
