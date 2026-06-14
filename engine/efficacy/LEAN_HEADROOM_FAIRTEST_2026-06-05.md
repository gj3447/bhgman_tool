# Lean headroom fair-test — oracle-guided repair loop vs best-of-N (2026-06-05)

> Answers part of the open hypothesis in `VERDICT.md` §3 ("the one fair test ... was never run").
> Runner: `engine/efficacy/lean_headroom_run.py` (+ `--out-dir` raw JSONL, replication controls,
> graded oracle). Analyzer: `engine/efficacy/analyze_lean_headroom.py`.
> Verified per `feedback_verify_async_results_before_writeup`: processes exited, JSON re-fetched + parsed.
>
> **Headline: a powered re-test (Run B) OVERTURNS Run A's thin-band null.** With a proper headroom band
> (10 tasks, 5 live) and 10 replications, the oracle-guided repair **loop beats best-of-N** on boundary
> headroom Lean tasks — reproducibly and significantly (sign-test p=0.016, repair ≥ best-of-N in 10/10
> runs, never loses). Run A (4 tasks, 1 live) saw no signal *because the band was too thin*, not because
> the loop has no value. Both runs are kept below; Run B is authoritative.

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
That is the loop-value claim. Repair ≈ bestN ⇒ the loop is operational, not better than independent retries.

Fairness conditions (both runs): seed threaded per attempt at `P1_TEMP=0.8` → genuinely independent draws
(not the collapsed-to-single confound found 2026-06-03; verified seeds 1,2 give *different* proofs);
`SEED_OFFSET` replication control symmetric across all three arms (no bias); real `lean` 4.30 core oracle,
Mac-local; model on dgx ollama via SSH tunnel.

### Reproduction hardening (2026-06-09)

The historical Run B write-up was verified from process outputs and fetched/parsing checks, but its raw
per-attempt JSONL was not committed. The runner now supports raw logs and a separate analyzer, so a rerun
can be audited without trusting this markdown table:

```bash
P1_MODEL=qwen2.5:32b-instruct P1_TEMP=0.8 \
  uv run python -m engine.efficacy.lean_headroom_run \
  --k 4 --replications 10 --seed-step 10 --out-dir verification/lean_headroom_runB

uv run python -m engine.efficacy.analyze_lean_headroom verification/lean_headroom_runB
```

The raw JSONL includes every generated proof, proof hash, Lean verdict, graded score, error tail, task
summary, and run summary. The analyzer recomputes the repair-vs-bestN exact sign-test from `run_summary`
records and per-task proven counts from `task_summary` records.

---

## Run A — thin band (4 headroom tasks), 5 reps — NULL (later shown to be an artifact)

Model `qwen2.5:32b-instruct`, K=4, seed_offset ∈ {0,10,20,30,40}. Headroom proven count:

| seed_offset | single | repair | bestN |
|---|---|---|---|
| 0/10/20/30 | 1 | 2 | 2 |
| 40 | 1 | 1 | 2 |

repair never beat best-of-N → *apparent* null. **But the band had only 1 live headroom task** (`sumto_mono`);
the other 3 were floor (`gauss`,`double`: all arms 0) or ceiling (`cnt_len`: all arms 1). A single live task
— which happened to be a tie — has no power to detect a loop edge. This null was a **sampling artifact**.

## Run B — powered re-test (10 headroom tasks + graded oracle), n=10 reps — REPRODUCIBLE SIGNAL

Same model/K. Band enriched to **10 headroom tasks** (added 6 custom-recursive-def tasks, all with verified
reference proofs: `sumlist_app`, `addone_len`, `repl_len`, `pow2_pos`, `le_sumto`, `dbl_ge`). Graded oracle
(0 = no-compile / 0.5 = compiles-with-sorry / 1 = proven) tracked per arm. **10 replications** (seed_offset
0…90 step 10; non-overlapping seeds).

**Per-run headroom (repair vs best-of-N):**

| outcome | count |
|---|---|
| repair > bestN | **7 / 10** |
| tie | 3 / 10 |
| bestN > repair | **0 / 10** |

repair ≥ best-of-N in **10/10** runs. **Sign test** on the 7 non-tied runs: **7/7 repair-wins, two-sided p = 0.016.**

**Per-task, proven out of 10 runs:**

| task | difficulty | single | repair | bestN | Δ(r−b) | reads as |
|---|---|---|---|---|---|---|
| `dbl_ge` | headroom (new) | 0 | **5** | **0** | **+5** | best-of-N *never* proves it; repair does 5/10 |
| `le_sumto` | headroom (new) | 0 | 5 | 1 | +4 | repair clearly ahead |
| `zero_add` | easy | 0 | 9 | 5 | +4 | loop wins on easy local-fix (consistent with Run A) |
| `sumto_mono` | headroom | 2 | 9 | 7 | +2 | repair edges |
| `sumlist_app` | headroom (new) | 0 | 2 | 0 | +2 | repair edges (floor in Run A's band) |
| `double` | headroom | 0 | 1 | 2 | −1 | the only reversal — marginal |
| `app_nil` `cnt_len` `addone_len` `repl_len` | ceiling | 10 | 10 | 10 | 0 | no discrimination |
| `gauss` `pow2_pos` | floor | 0 | 0 | 0 | 0 | model below capability — no partial progress to build on |

repair beats best-of-N on **4 of 5 live headroom tasks** (ties/marginally-loses on 1). The `dbl_ge` result
(best-of-N 0/10, repair 5/10) is the cleanest: independent resampling never lands the proof, but feeding the
Lean error back does — 5 times out of 10.

## Verdict (revises Run A)

**At the qwen2.5:32b tier, the oracle-guided repair loop BEATS best-of-N on boundary headroom Lean tasks —
reproducibly (repair ≥ best-of-N 10/10 runs, strict win 7/10, sign-test p=0.016, never loses).** Run A's
"repair never beats best-of-N" was a **thin-band artifact** (1 live task, an unlucky tie); the powered band
(5 live tasks) reveals a clear, statistically-supported edge.

**Mechanism.** The discriminating tasks need a specific tactic combination (`by induction … simp [def] <;>
omega`). The model often gets *close* — wrong simp lemma, missing `omega`, wrong base case — and the Lean
error names the defect. The repair loop uses that error to converge; best-of-N's independent draws resample
*without* the signal, so they hit the exact combo less often. **The loop's value is using the verifier's
error text to climb — which independent retries structurally cannot.** That is the loop structure beating
best-of-N, not just "more tries + a verifier."

**Where the edge lives: the competence boundary.** Floor tasks (`gauss`,`pow2_pos`: model can't start →
no partial progress for the error to guide) and ceiling tasks (solved trivially by all arms) show no edge.
The loop helps exactly where the model is *near* the answer — which is mechanistically the right place.

## Honest limitations (what stays open)

1. **Bounded repair, not discovery.** The proofs are 1–2 tactic lines; "repair" = fixing a tactic combo
   from an error, not multi-step search. This is evidence for *oracle-guided repair* (which `VERDICT.md`
   already named the defensible value) **beating best-of-N** — a step beyond the prior "loop ≤ best-of-N",
   but not a claim about open-ended discovery.
2. **Not frontier / not reasoning.** qwen2.5:32b-instruct. The stronger-reasoning-model axis (qwen3:14b/32b)
   was attempted and is **infeasible on the available backend** (>150 s/call on hard Lean prompts → a
   10-rep sweep would be ~10 h). So this is a tier result, not a frontier close.
3. **Graded ≈ proven here.** The graded oracle was wired (0/0.5/1) but these tasks are effectively pass/fail —
   the model rarely produces "compiles-with-sorry" middles — so graded tracked proven exactly and added no
   hidden partial-progress signal. (Useful instrumentation for tasks where it would; not load-bearing here.)
4. **Real F3 island diversity still unimplemented.** This tests ARM repair vs ARM best-of-N, not the full
   FunSearch island/migration mechanism.
5. **K=4.** The edge's dependence on the budget K is unmeasured.

## Lesson

Run A's null was a **thin-discriminating-band artifact** (n=1 live task → no power). The fix was not a bigger
model but a **bigger, calibrated task band** + replication. A "no signal" from an underpowered design is not
evidence of "no effect" — it is evidence of no power. (Mirrors the original premature-close postmortem: there
too, the design *structurally could not* return a positive.)
