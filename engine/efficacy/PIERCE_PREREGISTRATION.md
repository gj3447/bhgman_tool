# PIERCE PRE-REGISTRATION — repair-loop cognitive-edge A/B (frozen 2026-07-12)

> **This file's git commit timestamp MUST be strictly earlier than the mtime of any fresh
> post-2026-07-12 headroom JSONL.** It freezes the experimental design, the task band, and the
> pass/fail thresholds BEFORE the deciding run, to structurally block the confirmation-toward-closure
> relapse that already fired once (commit `8768b9f` declared CLOSE before the confirming run →
> `028fe54` corrected to PREMATURE). Any post-hoc edit to a threshold below invalidates the run's
> claim to this pre-registration. See [`KILL_CRITERIA.md`](KILL_CRITERIA.md) for the stopping rules.
>
> **HONESTY LAW**: even a clean confirmation is single-model, oracle-channelled *bounded-repair search
> compute* at the competence boundary — NOT collective IQ, NOT discovery, NOT a touch on the
> equal-compute multi-agent DPI≈0 prior. This is a 1-model repair experiment. Vocabulary: use
> "single-model oracle-channelled bounded-repair edge", never "pierce".

## 0. What is being tested

Whether an oracle **error-feedback repair loop** (`_arm_repair`) beats a budget-matched
**best-of-N** (`_arm_bestn`) on a capable LLM at the Lean competence boundary, *because of the oracle
error-text signal* (not because repair simply sees more input context), and whether that edge is
**bhgman-specific** (exceeds a plain agent-with-oracle loop) rather than a generic gen-verify-gap.

The committed run `headroom_32b_2026-06-14/` (qwen2.5:32b-instruct, K=4, n=10) reported 8W/2T/0L
repair-vs-bestN on `headroom_only`, p=0.007812. **Status of that run: PLAUSIBLE-uncontrolled** — it
has NO token/decoy control and NO per-task generality test; this pre-registration adds the controls a
credible confirmation (or a decisive refutation) requires. The committed run is *already-committed
regenerable evidence*; a fresh run is an INDEPENDENT 2nd confirmation, **not** double-counted as this
one.

## 1. Frozen artifacts (sha256 — band + pipeline)

| artifact | sha256 |
|---|---|
| `engine/efficacy/lean_tasks.py` (the 12-task band) | `4a73146e0e300439acf02a96390ca1303f25cd1b671d9ad3cb0462998504c2df` |
| `engine/efficacy/lean_oracle.py` (ungameable oracle) | `f8e84fd9785fd7f4f1abee5ceb2aec696d36c73258dc9dba71d562d88fd14bb2` |
| `engine/efficacy/analyze_lean_headroom.py` | `5e82e1e07f3d76422544f2153f5bd6a37bcd043128380674cf0e5f4d73cc7482` |
| `engine/efficacy/headroom_verdict.py` | `0ff1578b5dde9bc8af8834952c210952d6c4dbe1afed5cf2d0b88903dfec4b41` |
| `engine/efficacy/lean_headroom_run.py` | `599df16cc3d9452c3a3d0c519df5ee09524aac9f5504121d0787be77716142bb` |

A run claims this pre-registration ONLY if its `lean_tasks.py` sha matches row 1 (same band).
If the band changes, a NEW pre-registration is required — **re-banding to rescue a null is forbidden**
(K1 escape-hatch closure).

## 2. Frozen task-band classification (empirical, from the committed 32b run)

Per-task proven counts over the 10 committed seeds (arm ∈ single / repair / bestN), re-tallied this
session from `headroom_32b_2026-06-14/seed_*.jsonl` `task_summary` records:

| task | difficulty | single | repair | bestN | CLASS (frozen) |
|---|---|---:|---:|---:|---|
| zero_add | easy | 5 | 7 | 8 | saturation-baseline (not scored) |
| app_nil | easy | 8 | 10 | 10 | saturation-baseline (not scored) |
| gauss | headroom | 0 | 0 | 0 | **FLOOR** (excluded from live count) |
| double | headroom | 0 | 1 | 1 | live-tie |
| cnt_len | headroom | 9 | 10 | 10 | **CEILING** (repair=bestN) |
| sumto_mono | headroom | 1 | 10 | 4 | **LIVE — repair-favoring (top task)** |
| sumlist_app | headroom | 0 | 2 | 0 | LIVE — repair-favoring |
| addone_len | headroom | 8 | 10 | 10 | **CEILING** (repair=bestN) |
| repl_len | headroom | 10 | 9 | 10 | CEILING (bestN≥repair) |
| pow2_pos | headroom | 1 | 1 | 1 | live-tie |
| le_sumto | headroom | 1 | 2 | 0 | LIVE — repair-favoring |
| dbl_ge | headroom | 0 | 5 | 1 | **LIVE — repair-favoring** |

- **LIVE-discriminating headroom tasks (frozen definition)** = 0 < proven-rate < 10 for ≥1 arm AND
  not FLOOR/CEILING: `{sumto_mono, sumlist_app, le_sumto, dbl_ge, double, pow2_pos}` = **6 tasks**.
- **repair-favoring subset** (repair > bestN in the committed run): `{sumto_mono, sumlist_app,
  le_sumto, dbl_ge}` = **4 tasks**. `double`/`pow2_pos` = tie.
- **KNIFE-EDGE dominance (frozen caveat)**: `sumto_mono` alone (single 1 → repair 10, bestN 4)
  carries the majority of the repair-vs-bestN delta. **`top_task_delta_fraction` is a MANDATORY
  headline field** of every future analysis; a confirmation with `top_task_delta_fraction` > 0.5 is
  reported as "signal concentrated in one task", not "general".

## 3. The 5-arm design (naesengmoon-adjusted; current committed run has only 3 of these)

| arm | definition | isolates |
|---|---|---|
| `single` | 1 shot, no oracle | competence baseline |
| `bestN` | K independent draws, oracle-gated, no feedback | search-compute-only baseline |
| `repair` | K draws, real Lean error_tail fed back | the treatment |
| **`decoy`** (NEW) | K draws, feedback = a well-formed-but-WRONG Lean error from a DIFFERENT task (token/context matched, oracle SIGNAL removed) | context-VOLUME vs oracle-CONTENT |
| **`plain_baseline`** (NEW) | plain agent-with-oracle test-loop, same K, same oracle, no bhgman scaffolding | bhgman-specific vs generic gen-verify-gap |

**Parity (HARD invariant, pre-registered)**: report proven-rate **at equal oracle-calls** AND **at
equal input+output tokens** SEPARATELY. `repair`'s symmetric early-exit (≤K draws) must not grant an
average-compute discount vs `bestN`; token- and call-accounting fields are required on every attempt
record.

## 4. Pre-registered CONFIRM condition (all must hold)

A fresh capable-model run **CONFIRMs** the single-model oracle-channelled bounded-repair edge iff:

1. **P1 (edge)**: `repair > bestN`, two-sided exact sign test **p < 0.05**, reported BOTH per-run
   (seed-robustness) AND **per-task paired** (mixed-effects with task as random effect, or paired
   proven-rate across tasks), over **≥ 5 live-discriminating tasks** (§2).
2. **P2 (oracle-signal, not volume)**: `repair > decoy` p < 0.05 **AND** `decoy ≈ bestN` (TOST
   equivalence). If `decoy < bestN` (wrong errors actively hurt), P2 FAILS — `repair > decoy` is then
   inflated and does NOT establish oracle-signal.
3. **P3 (bhgman-specific)**: `repair > plain_baseline`. If not, the edge is a generic gen-verify-gap
   ("reading informative Lean errors > not", near true-by-construction), not a bhgman capability.
4. **P4 (parity)**: token-parity AND oracle-call-parity within a pre-declared bound; the edge holds at
   equal-tokens AND equal-calls.
5. **P5 (provenance)**: raw JSONL committed; `top_task_delta_fraction` reported.

Falling short of any → the mapped kill-criterion (K3/K4/K8) or INCONCLUSIVE (K1 power). A null on a
`< 5-live-task` band or a `< 32b` model is INCONCLUSIVE / floor, **never** "no effect" (K1, K2).

## 5. Model tiers (frozen)

- **32b reproduction** (`qwen2.5:32b-instruct`) = the literal 2nd confirmation. Cloud (`OpenRouter/
  DeepInfra`, ~$5) or dgx model-swap; pre-register cloud as "same nominal model, different serving".
- **27b generalization** (dgx-LAN `qwen3.6-27b` @ `192.168.0.23:8000`, verified reachable 2026-07-12)
  = a SECOND-capable-model arm; label **generalization**, NOT reproduction.
- **frontier API** = **WRONG tier** (headroom→ceiling band saturation = Q4, not Q2). Excluded here.

## 6. Scope lock

Steps 1–6 of the direction plan (this file, replay-regrade CI, seed/token fairness patch, decoy arm,
Q6 supersede, server-anchor) move the cognitive verdict by **exactly ZERO** — they are
machinery/record-honesty. Only a run satisfying §4 moves it. The cognitive claim is held at
`:VerdictPending` with a **hard no-propagation rule** (any green certificate certifies REPRODUCIBILITY
only and never appears in a positive/efficacy channel) until §4 is met, and **defaults to
"operational substrate is the honest end-state" if a capable generator stays unavailable N weeks**
(no indefinite OPEN).

# KG: LakatosTree_BhgmanCeilingPierce_20260712, prom16-bhgman-pierce-direction-2026-07-12, project_bhgman_efficacy_verdict_operational_substrate_2026_06_02
