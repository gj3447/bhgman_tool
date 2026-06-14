# 7-commander efficacy sweep — honest scoreboard

Run 2026-06-02 against the **real KG** (`bolt://100.64.0.3:7687`, 1738 `SourceCodeNode`,
460 with `disk_present`+`invocation_count` backfilled, 322 under `bhgman_tool/`). Every
cell passed — or honestly failed — the same 3-falsifier preflight
(`engine/efficacy/falsifier.py`: circularity / signal-absent / signal-inverted). Numbers
are reproduced by the commands shown; no value is hand-authored.

> ⚠️ **HONESTY QUALIFIER (2026-06-14, hardening audit H3):** "reproduced by the commands shown" holds
> *against the live KG snapshot + dgx ollama available on the run date* — 7 of the 9 scoreboard cells
> need live neo4j + dgx with no committed fixtures, so they are reproduced **on that infrastructure**,
> not offline. Only `scale_curve` + the synthetic `Δ+0.227` reproduce from committed inputs alone.

> ⚠️ **HONESTY CORRECTION (2026-06-14, hardening audit H2):** the `p=0.016` cited just below was on
> `qwen2.5:32b` with **uncommitted raw JSONL** → not independently regenerable (historical, not
> authoritative). A committed re-pin on a weaker `qwen2.5:7b` (n=10,
> `verification/lean_headroom_repin_7b_2026-06-14/`) is a **NULL** (repair = best-of-N, p=1.00); it
> does not refute the 32b claim but the 32b result is unreproduced with committed logs (re-run on dgx).

> **⚠️ SUPERSEDED-IN-PART (2026-06-05): the "LOOP-HYPOTHESIS = OPEN / leaning negative" conclusions below were REVERSED for the bounded-repair regime.** A powered Lean fair-test (`LEAN_HEADROOM_FAIRTEST_2026-06-05.md`, `VERDICT.md` §3, commit `88839e0`) found an oracle-guided **repair loop beats best-of-N on competence-boundary tasks**: repair ≥ best-of-N in 10/10 runs, strict win 7/10, never loses, sign-test **p=0.016** *(historical — raw logs lost, see correction above)*. The negatives below are real but regime-scoped (FunSearch *island-evolve* on bin-packing/symreg at small budget + an underpowered early Lean band) — they do NOT cover oracle-guided *repair* at the competence edge. Full dated note at the end of this file. within-competence cognitive ~0 is unchanged.

## Scoreboard

| commander | verb | verdict | number | oracle (independent of the commander?) |
|---|---|---|---|---|
| **occam** | 정리 | **MEASURED** | AUC **0.602** (pos 77 / neg 242) | `disk_present` — filesystem, not occam's label. ✅ non-circular |
| **longinus** | 연결 | **MEASURED** | ON **0.932** vs naive OFF 0.705, **Δ+0.227** on *injected* mutations (perm p<1e-4); ⚠ **deflates to Δ+0.050 on real git history** (class 0.875 vs 0.825 — the synthetic sandbox stacked pure-MOVE cases, inflating it ~4.5×; see VERDICT.md §1 / `git_oracle`) | injected disk mutations (20 seeds) + 101 drift events; real-data hold-out via git net-status. |
| **naesengmoon** | 검증 | **MEASURED** | mutation catch-rate **0.600** (6/10; escapes 4 boundary/sign mutants) | injected code mutants on `engine/occam/scoring.py`. ✅ |
| **jaebaeman** | 출격 | **MEASURED** | dispatch success-rate **1.000** (2588/2596, 8 pending, 0 error) | run-record telemetry (success/(success+fail), NOT intent==actual "fidelity" which stays UNMEASURED — H4). operational, not AUC. |
| **hades** | 실현 | **MEASURED** | realization **0.839** (141/168 source modules test-reached) | static import-reachability + pytest GREEN. ✅ non-circular. operational/state. |
| **prometheus** | 획득 | **MEASURED** | groundedness: sourcing **0.077** (946/12356), verifiability **0.931** (881/946 external), self-cite **0.001** (1/946) | `urlparse` URL-structure classification — not prometheus's judgment. ✅ non-circular. verifiability/precision-floor, NOT novelty. |
| **prometheus** (novelty) | 획득 | **MEASURED** | novelty **0.933** (14/15 beyond base-LLM recall), control_acc **1.00** | dgx-local qwen2.5:32b recall-delta, instrument-validated. ✅ non-circular. recall-delta *upper bound*, not precision. |
| **prometheus** (faithful) | 획득 | **MEASURED** | extractive-faithfulness **0.045** (1/22 verbatim-supported by cited page), control_acc **1.00**, shuffled 0.000 | cited external page = oracle; positive + permutation controls. ✅ non-circular. **prometheus synthesizes, doesn't quote** (low ≠ false). |
| **eureka** | 발견·창조 | **MEASURED** | recovery lift **+1.000** (6/6 planted) · KG reuse-breadth: 7 abstractions cover 319/319 nodes, extents [98..3] | planted concepts + real-KG synchronic cover. ✅ non-circular. extraction + breadth, NOT diachronic fan-in. |
| occam (registry) | 정리 | UNMEASURABLE | AUC 0.476 | KG `status` label is **73% occam-authored** → circular + inverted. |

Reproduce:

```bash
export NEO4J_URI=bolt://100.64.0.3:7687 NEO4J_USER=neo4j NEO4J_PASSWORD=…
uv run python -m engine.efficacy.run_all_commanders      # AUC-gate table (occam + registry sweep)
uv run python -m engine.efficacy.run_kg_efficacy          # occam disk-oracle, AUC 0.602
uv run python -m engine.efficacy.longinus_ab_experiment   # longinus ON/OFF Δ+0.227
uv run python -m engine.efficacy.drift_oracle             # 101 independent drift events
uv run python -m engine.efficacy.mutation_oracle          # naesengmoon catch 0.600
uv run python -m engine.efficacy.dispatch_telemetry       # jaebaeman success-rate 1.000
uv run python -m engine.efficacy.scale_curve              # operational scale to 100k
uv run python -m engine.efficacy.hades_oracle             # hades realization 0.839 + unrealized list
uv run python -m engine.efficacy.prometheus_oracle        # prometheus groundedness (sourcing/verifiability/self-cite)
uv run python -m engine.efficacy.eureka_oracle            # eureka recovery + real-KG reuse-breadth
ssh -fN -L 11434:localhost:11434 dgx                       # tunnel dgx-local ollama (for novelty)
uv run python -m engine.efficacy.prometheus_novelty       # prometheus novelty 0.933 (control-validated)
uv run python -m engine.efficacy.prometheus_faithfulness  # prometheus extractive-faithfulness 0.045 (fetches cited pages)
```

## What moved (vs the prior open items)

The ultracode-vs-legion run (`THEORY/efficacy_ab_ultracode_vs_legion/RESULTS.md`) left two
holes. Both are partly closed:

1. **"synthetic & tiny fixtures — external validity unproven."**
   occam is now measured on the **real KG (319 nodes, not a 6–15-node toy)**: AUC 0.602,
   circularity 0.000, availability 1.000. And `scale_curve` shows the longinus classifier
   holding **0.920 from N=100 to N=100 000**, where the base-LLM context **overflows at
   100k ($5.58/solve)** while the engine stays at 0.04 s. External validity is no longer
   *zero*; it is *modest-but-real* for occam and *operational* for longinus at scale.

2. **"only ~1.3 of 7 commanders tested."**
   Now **all 7** carry a number from an oracle the commander did **not** author:
   occam (disk), longinus (injected mutation), naesengmoon (code mutants), jaebaeman
   (dispatch telemetry), hades (test-reachability + pytest GREEN), prometheus
   (URL-structure groundedness), **eureka (planted-concept FCA recovery)**. Caveat: the
   numbers live at *different honesty tiers* — see the per-commander tier note below.

3. **hades oracle built (2026-06-02).** `hades_oracle.py` — the 168 git-tracked source
   modules are the "specs to realize"; a module is *realized* when a test reaches it
   (static import graph) and the suite is GREEN. The oracle (import edges + pytest) is not
   authored by hades → circularity 0. Result: **realization 0.839 (141/168)**; the 27
   unrealized are CLI entry-points, bench scripts, mcp_server thin wrappers, and nightly
   jobs — code that genuinely lacks unit tests (an actionable list, not a failure).
   *Caveat:* this is realization **completeness** (operational/state), not a cognitive
   win — there is no hades-built-vs-naive-built counterfactual, because code generation is
   inherently LLM (no cheap deterministic baseline like longinus's sha-compare).

4. **prometheus oracle built (2026-06-02).** `prometheus_oracle.py` classifies every
   `ResearchFinding.citation_url` by URL *structure* (`urlparse`, not prometheus's
   judgment → circularity 0): external / self / text / empty. It sharpens the old
   "grounding 0.006" into two honest layers and **partly refutes the self-citation
   critique**: the real limit is **no-source (92.3%, 11410/12356)**, *not* self-citation
   (1/946 ≈ 0.1%); and of findings that *do* cite, **93.1% are real external URLs**
   (881 arxiv/doi/wiki/other). *Caveat:* this is groundedness/verifiability (a precision
   floor), **not novelty** — and liveness (HTTP 200) is not checked, so it is an *upper
   bound*. Real cognitive novelty (a fact a base-LLM can't recall) still needs a base-LLM
   recall-delta on the dgx-local model — that remains OPEN.

5. **eureka oracle built (2026-06-02).** `eureka_oracle.py` plants K concepts defined by
   *cyclic attribute pairs* (each single attribute spans two concepts, so only a
   conjunction-closure can separate them) and checks whether eureka's FCA recovers them.
   The planted ground truth is author-supplied, not eureka's → circularity 0. Result:
   **FCA recall 1.000 vs naive single-attribute 0.000 (lift +1.000)** — eureka extracts
   the conjunctive latent structure a naive grouping provably cannot. *Caveat:* this is a
   *constructed best-case capability demonstration* of **extraction correctness**, NOT a
   real-world rate and NOT **reuse value** — production reuse is genuinely UNMEASURABLE
   (the real KG has **0 `:AbstractCategory`** eureka-authored nodes and no fan-in
   timeseries to attribute reuse to eureka).

## Honesty tiers — all 7 measured, but not the same kind of number

- **Cognitive-leaning:** occam (AUC 0.602 on real KG). longinus's headline Δ+0.227 is
  vs naive on *injected* mutations — on **real git history it deflates to Δ+0.050**
  (VERDICT.md §1), so it sits nearer the operational tier than +0.227 suggests.
- **Operational / state, real data:** jaebaeman (dispatch success-rate 1.000), hades
  (realization 0.839), prometheus (groundedness layers on 12356 real findings).
- **Capability demonstration, synthetic:** eureka (FCA recovery lift +1.000 on a planted
  ideal), naesengmoon (mutation catch 0.600 on injected mutants).

6. **the two thinnest counterfactuals now have a first measurement (2026-06-02).**
   - **prometheus novelty** (`prometheus_novelty.py`): asks dgx-local qwen2.5:32b, no
     tools, to label each finding KNOWN/NOVEL from training alone. The instrument is
     **self-validated** — 5 control facts (3 known / 2 fabricated) must be discriminated
     first; here **control_acc = 1.00**, so the run is MEASURED (not INCONCLUSIVE). Result:
     **novelty 0.933 (14/15)** — prometheus's external-knowledge findings sit beyond base
     recall. *Caveat:* NOVEL conflates *genuinely acquired specialized facts* with
     *unverifiable assertions*, so 0.933 is a recall-delta **upper bound**, not precision.
   - **eureka reuse-breadth** (`eureka_oracle.py` layer 2): runs eureka on the real KG
     facet-graph (319 nodes) → 7 induced abstractions with extents [98, 95, 92, 91, 31,
     13, 3], covering 319/319 nodes. Each abstraction is a *synchronic* multi-node cover
     (immediate reuse breadth). *Caveat:* this is "how many existing nodes share an
     abstraction now," NOT the *diachronic fan-in* (future reuse over time) — and
     `min_extent=2` forces extent ≥ 2, so the meaningful signal is the extent
     *distribution*, not a rate.

7. **prometheus faithfulness + the three-layer synthesis (2026-06-02).**
   `prometheus_faithfulness.py` fetches each finding's cited page and asks whether the page
   *supports the claim verbatim* — the cited external source is the oracle (not prometheus).
   Result: **extractive-faithfulness 0.045** (1/22), with control_acc 1.00 and shuffled
   0.000. The three prometheus layers now form one coherent picture:
   - **verifiability 0.931** — the cited URLs are real external pages;
   - **novelty 0.933** — the claims are beyond base-LLM training recall;
   - **extractive-faithfulness 0.045** — but the claims are *not verbatim in the cited pages*.

   → **prometheus is a *synthesizer*, not a *quoter*.** It acquires by interpreting and
   combining sources into novel framings, citing them as pointers rather than extracting
   verbatim facts. (Low faithfulness ≠ false; whether a synthesis is *correct/valuable* is a
   separate, harder question this oracle does not answer.) This quantifies the self-critique
   note "통합력은 진짜, 신규 원리는 거의 없음" (`project_bhgman_self_critique_2026_05_28`).

   *Feedback-loop correction:* the first faithfulness run returned **INCONCLUSIVE** — the
   instrument had only a permutation control (catches "judge says FAITHFUL to everything"),
   so when matched-faithfulness was genuinely near-floor it couldn't tell *real-low* from
   *broken-instrument*. Root cause: no **positive** control. Added planted (claim, page)
   pairs; the judge scored 5/5 on them (control_acc 1.00), proving it *can* detect
   faithfulness — so 0.045 is a real measurement, not a dead instrument. (external verdict →
   root cause → fix → re-measure.)

## What is still honestly open (the frontier moved, it didn't close)

- **Every "MEASURED" still has a deferred deeper layer.** None of the 7 is yet a clean
  *cognitive win over a base-LLM at equal tool budget* — that controlled test
  (`project_bhgman_ab_falsifier_2026_05_30`) still reads ~0, and the operational value
  (scale / reproducibility / audit) is the honest through-line. The two new measurements
  sharpen but don't overturn this: prometheus is *beyond base recall* (0.933) yet that
  upper bound includes unverifiable claims; eureka covers nodes *now* but diachronic
  fan-in (does anyone reuse the abstraction later?) needs `:AbstractCategory` written to
  the KG and time to accrue. Those remain the genuine open frontier.
- **The positive longinus Δ is vs a *naive no-tracking* baseline**, on *injected* mutations.
  It is **not** a cognitive win over a base-LLM given equal tool budget — that controlled
  test (`project_bhgman_ab_falsifier_2026_05_30`) still reads ~0; longinus's value there is
  operational (scale / reproducibility / audit). Both are true; do not collapse them.
- **occam AUC 0.602 is modest** — real signal, but a long way from a clean separator. The
  twin-redundancy signal is weak; age/invocation carry most of it.

## Composition 4th gate — the §5 falsifier: read-back loop is UNREALIZED (2026-06-02)

`prom16-bhgman-ci-design §5` asked the one question that turns the FunSearch hypothesis from
opinion into measurement: does the read-back evolve loop beat BOTH blind best-of-N AND
oracle-only-gating at **equal generation-token budget**? (ARM2 must beat ARM1 *and* ARM3,
else "just more compute" / "the oracle did it, the loop is decoration".) `composition_ab.py`,
3 arms, code tasks (`p1_tasks`), qwen2.5 on dgx ollama, 3000 gen-tokens/arm (token parity
within 1.4%), hidden-test eval / public-test signal (non-circular split).

| config | ARM1 best-of-N | ARM2 evolve-loop | ARM3 oracle-gate | realized |
|---|---|---|---|---|
| medium / 0.5b (n=7) | 0.857 | 0.714 | 0.857 | **False** |
| hard / 0.5b (n=4)   | 0.50  | 0.25  | 0.75  | **False** |
| hard / 1.5b (n=4)   | 0.50  | 0.50  | 0.75  | **False** |
| medium / 1.5b (n=7) | 1.00  | 1.00  | 1.00  | **False** (saturated) |

**Verdict: 4/4 UNREALIZED.** The read-back loop never won; on the weak model it was *worse*
than best-of-N (the read-back prompt carries prior attempts → longer prompts → fewer
candidates per token; a 0.5b model can't exploit the refinement signal). The robust *positive*
hidden here: **ARM3 oracle-gate is the strongest arm in every non-saturated config** (hard:
0.75 vs 0.50) — deterministic oracle *filtering* helps; agentic *iteration* on top does not.
Canonical ARM2≤ARM3 failure mode ("the oracle did it, the loop is decoration").

Honest scope: small n per band (4–7, wide CIs), only qwen-0.5b/1.5b (weak vs FunSearch's
frontier models + thousands of iterations), 3000-token budget (modest), single task family
(code). So this does **not** refute the theory at frontier scale — that stays OPEN. But for
bhgman's current reach it is a robust negative, fully consistent with
`project_bhgman_ab_falsifier` (~0) and the operational-substrate VERDICT: the value is the
external oracle gate, not the agentic loop. The `evolve_loop` primitive stays an
operational/audit feature, not a cognitive-lift claim.

The gate logic is falsifiable offline: `test_composition_ab.py` proves it fires BOTH ways
(planted read-back-helps → realized; read-back-useless → unrealized) — so UNREALIZED here is a
real negative, not a dead instrument.

### Best-shot follow-up (2026-06-02): F4 textual-feedback + strongest local models → still UNREALIZED, now by saturation

After the revival PROM (`prom16-evolve-loop-revival`) named the loop's biggest meetable lever as
**C4 textual feedback** (Mind Evolution critic ablation 46→95), we gave the loop its best feasible
local shot: wired **F4** (`_arm_evolve_feedback` — feeds the *failed* public assertions, not just a
scalar, back into the read-back prompt) and ran the **strongest local models** on the hard band.

| config | ARM1 best-of-N | ARM2+F4 evolve | ARM3 oracle-gate | realized |
|---|---|---|---|---|
| hard / qwen2.5-7b + feedback (n=4) | 1.00 | 1.00 | 1.00 | **False (saturated)** |
| hard / qwen2.5-32b + feedback (n=4) | 1.00 | 1.00 | 1.00 | **False (saturated)** |

The stronger models **one-shot all 4 hard code tasks** → every arm = 1.00 → zero headroom, nothing
to differentiate. This is the **C1↔C2 squeeze** the PROM predicted, now empirical: weak models
(0.5/1.5b) violate C1 (loop is *worse* than best-of-N), strong models (7b/32b) violate C2
(saturation). **The local code-task set has no band where both C1 and C2 hold.** The headroom regime
needs tasks a strong model cannot one-shot but can improve toward (Lean proof-search / competition-hard)
= net-new + frontier-scale = the HARD CEILING.

> **CORRECTION 2026-06-02 (postmortem, 4 adversarial critics, conf 0.82–0.84): "6/6 UNREALIZED" was
> an inflated denominator and the loop-CLOSE was premature.** Code-verified honest tally: **2
> underpowered nulls** (hard/0.5b, hard/1.5b — n=4, CI too wide to detect a realistic partial win) +
> **4 non-measurements** (medium/1.5b, 7b+F4, 32b+F4 saturate to all-arms=1.00 → paired delta=0,
> bootstrap CI=(0,0), realized=False *by arithmetic*). Power (n=7) and headroom (non-saturated) are
> **mutually exclusive across the entire sweep**, so the gate *structurally cannot* return "realized"
> — that is the instrument's blind spot, not the loop's failure. Compounding: the oracle is a 2-test
> pass-count (fitness ∈ {0,1,2}, no gradient to climb); ARM2/ARM3 share that oracle (so "loop ≤
> oracle-gate" is half a design tautology); and **F3 island/diversity — the load-bearing FunSearch
> ingredient — was never implemented** (best_k is greedy top-2), so we tested a strawman of the
> concept. **Corrected: operational-substrate (within-competence) STANDS; LOOP-HYPOTHESIS = OPEN.**
> The one fair test (model above the self-improvement floor × unsaturated leak-resistant task e.g.
> Lean `lake build sorry=0` × real F3 island × graded oracle) was *never run*. What these 6 runs
> actually show: on independent toy functions + a binary oracle, best-of-N is provably optimal —
> true, and nearly silent on the loop hypothesis.

### FunSearch-regime fair test (2026-06-03): degenerate tie — both arms reach best-fit, no headroom above

The postmortem's "one fair test" was built (`funsearch_binpack.py`, GATE-FIRST: offline-validated to
fire both ways AND not favor ARM2) and run — graded continuous oracle (mean lower_bound/bins_used),
real F3 island model, leak-resistant single-hard-problem (online bin-packing heuristic, FunSearch's
own benchmark). qwen2.5-7b, 5 seeds, budget 6000, islands 4, token parity within 1.4%.

Result: **5/5 EXACT ties** — ARM1 best-of-N == ARM2 island-evolve to 4 decimals (0.915/0.915,
0.923/0.923, …), mean 0.9177 both, lift [0,0,0].

Diagnosis (verified, not a bug — the offline fairness gate passes): the 7b writes *textually diverse*
heuristics that collapse to two fitness levels — worst-fit variants (~0.83) and best-fit (~0.92).
**best-fit is the reachable ceiling for this uniform U[0.1,0.7] distribution, and BOTH arms find it by
sampling.** There is no heuristic *above* best-fit for this distribution that evolution could discover
but sampling couldn't → no headroom → exact tie. This is NOT "loop broken" and NOT a rig; it is the C2
(headroom) constraint again, now at the "is there a better-than-best-fit heuristic the model can iterate
toward" level. Uniform bin-packing has none; FunSearch deliberately used distributions where best-fit
*is* beatable.

**TRIANGULATION (3 fair-ish attempts, same wall):** (1) toy code → model-saturated; (2) hard code +
7b/32b → one-shot-saturated; (3) FunSearch regime → best-fit reachable, no headroom above. Every time
the binding constraint is **headroom × model-strength × eval-scale**. The genuinely-complete test = a
*provably-best-fit-beatable* distribution + a *frontier* model (can discover non-obvious heuristics) +
many evals = exactly FunSearch's regime = the HARD CEILING.

**Status (NOT a re-close — that word was burned once already): operational-substrate within-competence
STANDS; loop-hypothesis remains OPEN but now LEANS structural-negative for bhgman's local reach,
triangulated across 3 diagnosed regimes (not a single premature test).** Remaining open path: a
frontier-model run (Anthropic API) on a best-fit-beatable distribution.

### Stronger-model follow-up + a bootstrap false-positive I caught (2026-06-03)

Ran the same gate on the strongest LOCAL model (qwen2.5-32b) × weibull (FunSearch's distribution):
- **7b → flat tie** (lift 0, model below the self-improvement floor).
- **32b → weak POSITIVE, not significant.** n=8: per-seed **1 win (+0.0083), 7 exact ties, 0 losses**,
  mean lift +0.001. The loop is *never worse* and *occasionally better* — directionally consistent
  with "stronger model → loop edges up" (C1), but the effect is tiny and rare.

**The gate first reported `realized=True` at 32b — that was a FALSE POSITIVE from a broken bootstrap.**
`_bootstrap_ci` (shared by p1/composition/funsearch) resampled with `deltas[state % n]`, and an LCG's
low bits are periodic (period ≤ n) → every "resample" drew the same fixed cyclic index pattern →
degenerate lo==hi CI that clears 0 on sparse small-n deltas. Caught it (proper random bootstrap gives
lo95=0.000; sign test on 1-win/7-tie/0-loss is p≈0.5), **fixed to high bits `(state >> 33) % n`**
(verified vs true-random), recomputed → **UNREALIZED** (lo95=0.000). This is the mirror of the
premature-CLOSE catch: a premature-CLAIM, caught by the same verify-your-own-stats discipline.

Honest status (unchanged in direction, sharper): loop-hypothesis OPEN, leaning weak-positive-with-model-
strength but NOT significant locally. A +0.001 effect at a ~1/8 win rate needs either ~50+ seeds (power)
or a frontier model + headroom-rich problem (more wins) to confirm. The dgx credential is a Claude Code
*subscription OAuth* token (not a console API key) and is not usable for this scripted batch.

**Power check (2026-06-03): the n=8 weak-positive WASHED OUT at n=20 — it was noise.** Same gate, 32b ×
weibull × n=20, fixed bootstrap: mean lift +0.0012, **CI95 [-0.135, +0.138]** (straddles 0 widely),
**wins=2, ties=17, losses=1**. And one of the 2 "wins" is an artifact — best-of-N picked a heuristic
that passed PUBLIC but crashed on HIDDEN (score 0.0 → ARM2's 0.92 "beat" it); the only genuine win is a
single +0.008. Drop the outlier → ~1 win / 1 loss / 17 ties = a **wash**. So with proper power the 32b
loop shows **no detectable edge** over best-of-N. (The dgx OAuth token is also expired ~84 days, 401 — the
true frontier arm needs a fresh console `ANTHROPIC_API_KEY`.) Net across all FunSearch-regime runs: 7b flat,
32b wash. Loop-hypothesis stays OPEN but the *local* signal is gone; the decisive test is frontier + a
headroom-rich problem.

### dgx vLLM Qwen3.6-27B (2026-06-03): clean flat tie — completes the local triangulation

Ran the gate on the dgx "api" = k8s `ai/vllm` serving **Qwen3.6-27B** (newer-gen, reasoning model;
`enable_thinking=false` + terse-code prompt to avoid the reasoning/truncation traps). weibull, n=8,
budget 3000, fixed bootstrap. **Clean run: 0 timeouts, 0/8 crash-zeros (validity-checked).**

Result: **wins=0, ties=8, losses=0 — 8/8 EXACT ties**, lift [0,0,0], realized=False. Both arms
converge to the same best-fit heuristic (~0.93) every seed → no headroom above best-fit → flat.

**Local triangulation complete (3 model gens, all no edge):** 7b → flat; 32b → wash (n=20, signal
was noise); Qwen3.6-27B → flat 8/8. Across everything bhgman can run locally, the island-evolve loop
does **not** beat best-of-N — best-fit is the reachable ceiling for these distributions and both arms
reach it. (Getting infra-clean took 3 tries: timeout-crash → retry; 3h40m-slow → max_tokens cut;
truncation-0.0-artifact → terse prompt. Each artifact caught + fixed, not reported as a result.)

**Verdict (robust, NOT premature — clean data, multi-model, fixed/validated stats): loop-hypothesis
has NO local evidence through Qwen3.6-27B.** The decisive test remains a *frontier* model (can discover
non-obvious heuristics beating best-fit — FunSearch's regime) on a *headroom-rich* problem, which needs
a console `ANTHROPIC_API_KEY` (dgx has only an expired Claude Code OAuth token). operational-substrate
within-competence stands; loop stays OPEN-pending-frontier.

### Headroom-rich task (symbolic regression) on dgx vLLM (2026-06-03): the loop is SIGNIFICANTLY WORSE

The bin-packing ties were blamed on no-headroom (best-fit one-liner). So we built a headroom-rich task
— symbolic regression of a hidden g(x)=c0+c1x+c2x²+c3·sin(c4x), graded by 1/(1+RMSE), rich residual
feedback in read-back (the AlphaCodium lever). Gate-first validated (fires both ways, fair). Run on the
SAME dgx vLLM (Qwen3.6-27B), n=8, budget 3000, clean (0/8 crashes; arm1 scores spread 0.17–0.84 =
genuine fitting, headroom confirmed).

Result: **mean best-of-N 0.466 vs island-evolve 0.414, lift -0.0526, CI95 [-0.098, -0.010] — entirely
below 0. wins=2, ties=1, losses=5.** So with real headroom, the read-back loop is **statistically
*worse*** than best-of-N (not just a tie). Likely mechanism: read-back causes **premature convergence**
(refines around an early mediocre fit / local optimum) while best-of-N keeps sampling diverse fresh
formulas; plus the longer read-back prompt buys fewer candidates per token → less exploration. A modest
4-island/k=2/small-budget setup cannot supply the diversity FunSearch's huge populations + ~10⁶ evals do.

This is the sharpest datum yet and it *flips the framing*: the loop's problem isn't only "no room to
win" (bin-packing) — when there IS room, naive read-back at small scale actively **narrows exploration
and loses**. Net across all runs: 7b flat / 32b wash / Qwen3.6-27B binpack flat / Qwen3.6-27B symreg
**significantly worse**. The loop needs FunSearch-scale diversity+budget (frontier regime) to win;
at bhgman's reachable scale it is at best neutral and at worst counterproductive. operational-substrate
stands; the "evolve loop gives cognitive lift" claim has zero local support and one significant local
*negative*.

### External-value proxy (2026-06-04): the oracle's value = the reasoner's confident-error rate

After confirming bhgman = oracle substrate (the `bhgman-tool oracle` verify surface + 4 wired
adapters), the genuinely-untested axis (VERDICT.md: external value) got a first honest proxy. On real
code tasks a reasoner generates a solution AND self-rates it correct/incorrect; the bhgman oracle
(hidden-test execution) gives ground truth. The value the oracle adds over the reasoner alone =
**confident-but-wrong** (reasoner says YES, oracle says FAIL).

| reasoner | oracle-pass | self-assessment acc | confident-but-wrong |
|---|---|---|---|
| Qwen3.6-27B (strong) | 1.00 (15/15) | 1.00 | **0/15** |
| qwen2.5-0.5b (weak)  | 0.27 | 0.33 | **10/15 (0.667)** |

So bhgman verify's external value is **real but conditional — it scales with reasoner fallibility/
overconfidence.** A strong reasoner on within-competence tasks self-verifies reliably (acc 1.0) → the
oracle is marginal there. A fallible reasoner is confidently wrong 2/3 of the time, and the oracle
catches **every** one its self-assessment missed (Huang 2310.01798: intrinsic self-correction fails
without an external signal — confirmed empirically). The honest external-value answer: not a cognition
amplifier, but a **fallibility-proportional deterministic error-catcher** — most valuable exactly at the
competence edge / for weaker reasoners / on out-of-competence tasks where even strong models err. True
external *adoption* remains untested (needs a real user); this is the utility proxy.

### ★ Headroom reversal (2026-06-05): oracle-guided repair loop BEATS best-of-N — the OPEN above is resolved for bounded repair

Every "loop OPEN / leaning negative" conclusion above was measured on **island-evolve** (FunSearch-style population diversity) at small budget, plus one **underpowered** early Lean band (Run A: only 1 live headroom task → no power; a sampling artifact, not a null). A powered re-test reverses the headroom reading.

Run B (`LEAN_HEADROOM_FAIRTEST_2026-06-05.md`, commit `88839e0`): band enriched 4→10 headroom Lean tasks (5 live, +6 verified custom-recursive proofs), graded oracle (0/0.5/1), 10-seed replication, ungameable `#print axioms` check. Three arms at equal K=4: single / **oracle-guided repair** / best-of-N.

- **repair ≥ best-of-N in 10/10 runs, strict win 7/10, never loses; sign-test p=0.016.**
- Per-task: `dbl_ge` best-of-N 0/10 vs repair 5/10; `le_sumto` 1/10 vs 5/10.
- Mechanism: the model gets *close*, the Lean error names the defect, repair converges where independent draws can't.

**Scope (precise):** bounded oracle-guided **repair** (NOT open-ended discovery), at the **qwen2.5:32b** tier (NOT frontier — qwen3 reasoning infeasible at >150s/call), K=4. The edge lives exactly at the competence boundary (floor + ceiling tasks show none). within-competence cognitive ~0 is unchanged; this does not touch the drift/dedup F1=1.0 regime.

This also corrects the earlier "6/6 UNREALIZED → loop CLOSED" — a 4-critic postmortem (conf 0.82–0.84) caught it as PREMATURE: the denominator was 2 underpowered nulls + 4 non-measurements that saturate to delta=0 by arithmetic, F3 islands were never implemented, and CLOSE was committed before the confirming run.

Adversarially re-verified (workflow w24bu3fss; EFF-4/EFF-5/EFF-7 CONFIRMED, p recomputed 0.0156). Authoritative verdict: `VERDICT.md` §3. (Caveat: historical Run B raw per-run JSON was not committed — the per-task counts live in the markdown narrative. As of 2026-06-09, `lean_headroom_run.py --out-dir ...` writes raw JSONL and `analyze_lean_headroom.py` recomputes the sign-test/per-task counts from those logs. Frontier tier, open-ended discovery, and K-dependence remain open.)

# 2026-06-05 reversal source: VERDICT.md §3 + LEAN_HEADROOM_FAIRTEST_2026-06-05.md (commit 88839e0);
#     KG verdict node bhgman-efficacy-verdict-operational-substrate-2026-06-02 (headroom_resolution_2026_06_07 field), efficacy-map-final-2026-06-01 (headroom_update_2026_06_07)
# KG: efficacy-measurement-line-2026-06-01, efficacy-occam-sigma-ab-2026-06-01,
#     7cmd-measurement-driven-conditional-dispatch-2026-05-30, project_bhgman_ab_falsifier_2026_05_30,
#     prom16-bhgman-ci-design-2026-06-02, lesson-bhgman-cognitive-lift-requires-oracle-guided-search-2026-06-02,
#     lesson-premature-close-confirmation-toward-closure-2026-06-02
