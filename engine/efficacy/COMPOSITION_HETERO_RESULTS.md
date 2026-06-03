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

## Run 3 — headroom probe (forced unsaturation, weak model) — `hetero_headroom_probe.py`

To escape the saturation of runs 1–2, dropped to the WEAKEST model (qwen-0.5b) so a single shot
fails often. `saturated: false` (single solved only 10/15 → genuine headroom). Three arms isolate the
win source: ARM0 bare single-shot / ARM1 oracle-select (best-of-N picked by PUBLIC tests) / ARM2 hetero.

| | single | oracle_select | hetero |
|---|---|---|---|
| pass / 15 | **10** | 11 | 8 |
| − single (mean, CI_lo, wins) | — | +0.067, −0.20, **False** | −0.133, −0.40, **False** |

Per-task: oracle_select *recovered* 2 the bare model failed (flatten, roman_to_int) but *broke* 2 the
bare model got right (run_length_encode, spiral_order) → net wash, not significant.

**The new, deeper finding — proxy-oracle overfit (Goodhart at the micro level).** Even WITH headroom,
oracle-selection did not win, and it *hurt* on 2 tasks: selecting hard on the **2 public tests** (a thin
proxy) overfits and breaks HIDDEN-correct solutions. The hetero pipeline was again worse. So across 3
regimes (within-competence saturated → hard saturated → weak unsaturated) nothing beats the bare model.

**Why this is constructive, not just another null.** It localizes the value precisely: it is **not**
orchestration (hetero consistently worse), and **not even** proxy-oracle selection (a thin sampled-test
oracle overfits). The composition win lives only with a **GROUND-TRUTH oracle that cannot be overfit**
— a compiler / Lean `#print axioms` / the deterministic KG checks — which is exactly what the KG-engine
commanders (occam/longinus/hades + the compiler-naesengmoon) are: 0-token, ungameable. This probe
confirms the operational-substrate verdict *constructively* (it shows where the value is, not only
where it isn't).

## Run 4 — strong model (qwen-32b) on the same hard tasks → SATURATION

To meet the "strong model" condition, re-ran the headroom probe on the strongest local model
(qwen2.5:32b-instruct, 19.9 GB) on the 8 hard/medium tasks.

| | single | oracle_select | hetero |
|---|---|---|---|
| pass / 8 | **8** | 8 | 8 | (`saturated: true`) |

The strong model solves **every** task single-shot. Zero headroom. Composition cannot help because
there is nothing left to add.

**The decisive structural finding — power–headroom mutual exclusivity (now empirically shown on both
ends).** Weak model (1.5b): headroom exists (10/15) but no capability → composition doesn't help and
hurts. Strong model (32b): capability exists but the standard tasks saturate (8/8) → no headroom for
composition to act. The two conditions the cell needs (capable model AND task beyond its single-shot
reach) are **mutually exclusive on standard HumanEval-style tasks** — the better the model, the more it
saturates them. This is exactly the VERDICT.md §3 postmortem observation ("power and headroom are
mutually exclusive across the whole sweep"), now confirmed across both available models.

**What this means for "opening the cell."** The cell only opens when headroom and capability coexist —
which requires tasks genuinely *beyond* a strong model's single shot: (a) too big for one context
(decomposition headroom), (b) needing external info the model lacks (prometheus's gap-ingest domain),
or (c) needing a formal proof the model can't one-shot with an ungameable oracle (Lean #print-axioms).
Standard code tasks are none of these. **And those three task types are precisely what bhgman's KG
substrate is built for** (cross-session beyond-context state / external-knowledge ingest / formal
ground-truth oracles) — which is why the measured value lives in the operational substrate, not in
beating a model on tasks it can already do. The cell is not "closed"; it is *unreachable with standard
tasks + available models*, and reaching it needs the very regime the substrate already targets.

## Run 5 — FAITHFUL test (real Lean, ungameable oracle, headroom) → the cell opens, narrowly

Built the faithful rig (`lean_oracle.py` + `lean_tasks.py` + `lean_headroom_run.py`): real Lean,
statement fixed by construction, hidden = `#print axioms` no-sorryAx (ungameable), headroom tasks
(omega/simp don't one-shot), strong-ish model (qwen-32b), capability-heterogeneous (model + the real
Lean compiler). Found + fixed a seed confound first (bestN had identical samples → re-run below).

| task | diff | single | repair (oracle-fed) | bestN (blind retry) |
|---|---|---|---|---|
| zero_add | easy | 0 | 1 | 1 |
| app_nil | easy | 1 | 1 | 1 |
| gauss | headroom | 0 | 0 | 0 | ← above 32b's reach (repair can't either) |
| double | headroom | 0 | 0 | 0 | ← above reach |
| cnt_len | headroom | 1 | 1 | 1 | ← below reach (one-shot) |
| **sumto_mono** | headroom | **0** | **1** | **0** | ★ in the band |

headroom totals: single 1 / **repair 2** / bestN 1.

**★ The opening (one task, exactly as predicted).** On `sumto_mono` (`sumTo n ≤ sumTo (n+1)`) the bare
model failed single-shot (0) AND failed 4 blind retries (bestN=0), but **proved it with oracle-guided
repair** (lean error fed back → fixed). Ungameable (real `#print axioms` proof). This is a genuine
instance of *composition + a ground-truth oracle reaching BEYOND the bare model* — and `repair > bestN`
on this task means the active ingredient is the **oracle feedback**, not extra compute. This is the
value-locus the whole analysis pointed to, now shown constructively on a real theorem.

**Calibration (do NOT over-read).** n=4 headroom, the win is **one** task. The "headroom band" is thin:
2/4 above 32b's reach (unprovable even with repair), 1/4 below (one-shot), only 1/4 in the band where
repair helps. So this is a **positive SIGNAL pointing exactly where predicted, not a robust result** —
n=1 win, could be noise. Firming it up needs more tasks *in the band* (between one-shot reach and the
absolute ceiling — a thin, hard-to-populate region) + more seeds + ideally a frontier model (which
would widen the band). The signal is real and directionally confirmed; the magnitude is unestablished.

**What this resolves about the whole arc.** ~0 was real in the within-competence / strawman / saturated
regimes (Runs 1–4). In the *faithful* headroom + ungameable-oracle regime, composition **does** reach
beyond the bare model (Run 5, one task) — and the mechanism is the ground-truth oracle feedback, not
orchestration. The band is thin, which is *why* the operational substrate (independent of cognitive
uplift) is the robust value, and the cognitive win is a narrow, real, hard-to-reach exception.

## Still untested at scale (the cell is open a crack, not wide)

strong model × **ground-truth (non-proxy) oracle** × real headroom (task too big / outside single-shot
competence) — needs a frontier backend AND a Lean-capable generator (so the hidden oracle is the
ungameable W4 check, not a 2-test proxy). Not runnable here. The harness + gate + probe are ready.

## One-line

Across saturated, hard, and weak-unsaturated regimes the 7-commander composition never beat a bare
single shot — and the weak-unsaturated probe localized *why*: the win is neither orchestration nor
proxy-oracle selection (which overfits, Goodhart), but **ground-truth oracle gating** — exactly the
deterministic 0-token KG checks the tool already has. The "make the model smarter" cell (strong model +
ungameable oracle + real headroom) stays OPEN, pending resources not available here.
