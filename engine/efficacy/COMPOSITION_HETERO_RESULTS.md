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

## Run 6 — REASONING models (qwen3 via dgx ollama) + the reproduction that wiped the signal

Pushed the faithful rig onto genuine **reasoning** models (Qwen3 thinking-mode) via the dgx GB10 over
an ssh tunnel, to ask the real question: *does a reasoning model + ungameable oracle (repair) reach
headroom theorems the bare reasoning model can't single-shot?* Three reasoning models, hard infra
reality on each:

| model | reasoning? | Lean capability | speed (GB10 ollama) | usable? |
|---|---|---|---|---|
| qwen3:32b | ✓ | sufficient | **4.1 tok/s** (245 s / ~1k tok) | **no** — 30-gen rig = multi-hour + random >timeout deaths |
| qwen3:8b  | ✓ | **too weak** (`rfl` for `0+n`, wrong induction case names) | fast | runs, but **all-zero** (no band exists) |
| qwen3:14b | ✓ | mid (attempts *close*, fixable) | 8.5 tok/s | **yes** — full rig completes |

**qwen3:14b full rig (K=3, max_tokens 6000, ungameable oracle), run 1:**

| task | diff | single | repair (oracle-fed) | bestN (blind) |
|---|---|---|---|---|
| zero_add | easy | 0 | 0 | 0 |
| app_nil | easy | 0 | 1 | 0 |
| gauss | headroom | 0 | 0 | 0 |
| double | headroom | 0 | **1** | 0 |
| cnt_len | headroom | 0 | 0 | 0 |
| sumto_mono | headroom | 0 | **1** | 1 |

headroom totals run 1: single **0** / repair **2** / bestN 1 → `repair_beats_single`=true. At face value the
cleanest opening yet (single=0 everywhere ⇒ every repair win is unambiguously "reached beyond bare").

**Then I reproduced it — and it vanished.** Re-ran the repair arm (fresh draws) on the two headroom
winners: **double 0/3, sumto_mono 0/3.** Both 0. The model *repeated the same error class* across all 3
attempts (double: `calc … : rfl` — Lean-3 `:` instead of `:=`, never fixed by the fed-back error;
sumto_mono: `Nat.le_add_right` variants that don't typecheck). The run-1 wins did not reproduce.

**Why (mechanism, not hand-wave).** The openai-compat path passes **no seed and no temperature** →
ollama samples at its default temp 0.8 with a fresh random seed every call (the rig's `_seed` arg is
ignored on this path; it only bites the local-`_ollama` path). So every generation is an independent
draw, and **run-1's "repair 2/4" was a lucky draw, not a stable effect.** The arms remain valid (bestN
= K independent samples; repair = K samples with error feedback), but a single run's counts are
**high-variance** and an n=1 win is unreliable.

**What is robust (survives reproduction) vs what is noise:**

- **ROBUST:** single-shot = 0 for 14b reasoning on *every* core-Lean task here — reasoning did **not**
  buy single-shot capability at this scale (capability floor). And 8b reasoning = all-zero. The
  reasoning models are simply weak at core Lean.
- **ROBUST:** taking K samples (repair *or* bestN) **occasionally** lands a valid proof that the
  ungameable oracle correctly certifies (compiles + `#print axioms` no `sorryAx`) — *unreliably*.
- **NOISE:** "repair beats single" and "repair beats bestN" on headroom. Both are within sampling
  variance at this n — repair headroom count was {2, then 0 on the same two tasks}. repair vs bestN is
  *indistinguishable* here: both are "K lottery tickets," and the run-1 repair>bestN edge did not hold.

**The honest verdict on the cell.** When tested *faithfully and with reproduction*, the "make the model
smarter via composition" cell does **not robustly open.** The narrow openings — Run 5's `sumto_mono`
(qwen2.5:32b, n=1) and Run 6's run-1 (qwen3:14b, n=2) — are **sampling noise at the floor**; the 14b one
explicitly failed to reproduce, and the rig's non-determinism means Run 5's was almost certainly the
same. What is real and reproducible is the **ungameable oracle**: you can take K shots and *trust* the
one that passes `#print axioms`. That trust — not "oracle-guided iteration is cognitively better than
blind retry" — is the value. This is exactly the **operational substrate**, and it is now confirmed by
the *failure* of the cognitive-uplift signal to survive replication, not just by its absence.

> Meta: this is the verify-before-writeup / never-close-on-an-n=1 discipline working as intended. The
> single-run "cell opens, narrowly" of Run 5 would have become canon had I not reproduced it. It didn't
> reproduce. Recorded as noise, not as a win. (cf. evolve_loop premature-close postmortem, numerology MC
> discipline.)

## Still untested (and now likely moot)

strong **reasoning** model that is *also* Lean-capable *and* fast enough to replicate (≥30 trials for a
rate with CI) — the reasoning×capable×fast cell is unreachable on local dgx (32b too slow, 8b/14b too
weak). A frontier API (the rig is wired: `ANTHROPIC_API_KEY` → AgentClient anthropic path) could test
it, but the reproduction result above predicts the same: any single-run opening must be replicated
before it counts, and the robust value will still be the ungameable oracle, not the orchestration.

## One-line

Across saturated, hard, weak-unsaturated **and now faithful-headroom-with-reasoning** regimes, the
7-commander composition's cognitive uplift over a bare single shot is **at the noise floor** — the only
positive signals (n=1/n=2) **failed to reproduce** under the rig's temp-0.8 independent draws. The
robust, replicated value is **ground-truth oracle gating** (trust a sample that passes `#print axioms` /
the compiler / the deterministic 0-token KG checks) — the operational substrate — *not* "composition
makes the model smarter." The cell did not open; the discipline of reproducing before writing up is
what kept a lucky draw from becoming a false canon.
