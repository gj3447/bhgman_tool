# 7-commander efficacy sweep — honest scoreboard

Run 2026-06-02 against the **real KG** (`bolt://100.64.0.3:7687`, 1738 `SourceCodeNode`,
460 with `disk_present`+`invocation_count` backfilled, 322 under `bhgman_tool/`). Every
cell passed — or honestly failed — the same 3-falsifier preflight
(`engine/efficacy/falsifier.py`: circularity / signal-absent / signal-inverted). Numbers
are reproduced by the commands shown; no value is hand-authored.

## Scoreboard

| commander | verb | verdict | number | oracle (independent of the commander?) |
|---|---|---|---|---|
| **occam** | 정리 | **MEASURED** | AUC **0.602** (pos 77 / neg 242) | `disk_present` — filesystem, not occam's label. ✅ non-circular |
| **longinus** | 연결 | **MEASURED** | ON **0.932** vs naive OFF 0.705, **Δ+0.227, perm p<1e-4**; false-kill 1.000→0.333 | injected disk mutations (20 seeds) + 101 independent drift events. ✅ |
| **naesengmoon** | 검증 | **MEASURED** | mutation catch-rate **0.600** (6/10; escapes 4 boundary/sign mutants) | injected code mutants on `engine/occam/scoring.py`. ✅ |
| **jaebaeman** | 출격 | **MEASURED** | dispatch fidelity **1.000** (2588/2596, 8 pending, 0 error) | run-record telemetry (correctness, not AUC). operational. |
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
uv run python -m engine.efficacy.dispatch_telemetry       # jaebaeman fidelity 1.000
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

- **Cognitive-leaning, real data:** occam (AUC 0.602 on real KG), longinus (Δ+0.227 vs
  naive on injected mutations).
- **Operational / state, real data:** jaebaeman (dispatch fidelity 1.000), hades
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
= net-new + frontier-scale = the HARD CEILING. **Total: 6/6 UNREALIZED across model strengths and
feedback on/off.** CLOSE-AS-OPERATIONAL confirmed empirically — the deterministic oracle gate, not
the loop, is the value.

# KG: efficacy-measurement-line-2026-06-01, efficacy-occam-sigma-ab-2026-06-01,
#     7cmd-measurement-driven-conditional-dispatch-2026-05-30, project_bhgman_ab_falsifier_2026_05_30,
#     prom16-bhgman-ci-design-2026-06-02, lesson-bhgman-cognitive-lift-requires-oracle-guided-search-2026-06-02
