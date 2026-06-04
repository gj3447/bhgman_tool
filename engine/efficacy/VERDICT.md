# Efficacy verdict — bhgman_tool is an *operational substrate*, not a cognitive enhancement

> The honest conclusion of the 7-commander efficacy line (`SWEEP_RESULTS.md`).
> Written 2026-06-02 after measuring every commander with an independent, non-circular
> oracle. This is a *reframe*, not a retraction: the operational value is real and the
> claims here are scoped precisely, not dismissively.

## 1. What measuring all 7 commanders actually concluded

Every commander now carries a number from an oracle it did **not** author (the discipline
is in `falsifier.py`: circularity / signal-absent / signal-inverted). The pattern across
all of them is one finding:

**No commander shows a cognitive win over a base-LLM at equal tool budget.**

- **longinus** looked like the one exception — Δ+0.227 vs a naive baseline. On *real git
  history* (rename truth from `git -M`, independent of longinus's own sha-twins) it
  deflates to **Δ+0.050** (class 0.875 vs 0.825). The synthetic figure was inflated ~4.5×
  by stacking pure-MOVE cases that don't occur in real history. Even the best case is
  near noise once the data is real.
- **prometheus** is a **synthesizer, not a quoter**: verifiability 0.931 (cites real
  external pages) · novelty 0.933 (beyond base-LLM recall) · extractive-faithfulness 0.045
  (but the claim is *not verbatim* in the cited page). It interprets and combines sources
  into new framings; the citation is a pointer, not an extraction. Quantifies the
  self-critique "통합력은 진짜, 신규 원리는 거의 없음."
- **occam** AUC 0.602 — modest, real, far from a clean separator (twin-redundancy is weak;
  age/invocation carry most of it).
- **naesengmoon** mutation-catch 0.52 ± 0.10 — and in the controlled A/B it matches a
  base-LLM (the prior single 0.600 was the high tail). Its edge is *precision* (an oracle
  can't hallucinate), not raw catch rate.
- **eureka** recovery lift +1.000 is a *constructed best-case* on a planted ideal; its
  real-KG number is *synchronic cover* (7 abstractions over 319 nodes), not diachronic
  reuse value.
- **hades** 0.839 and **jaebaeman** 1.000 are *operational completeness* metrics
  (test-reachability, dispatch fidelity), not cognition at all.

The controlled base-LLM A/B (`project_bhgman_ab_falsifier_2026_05_30`) reads ~0 cognitive
lift; the concurrent HARD-set hunt reads NULL/NEGATIVE within-competence. **Two independent
measurement lines converged on the same bitter lesson.**

## 2. The reframe

Apply the ICE workbench-reframe pattern (`project_ice_workbench_reframe_2026_05_18`:
`PhysicsTheoryProgramme` → `HypercomplexHypothesisTestbench`). Here:

> **`CognitiveEnhancementClaim` → `OperationalSubstrate`.**

bhgman_tool's 7군단장 are **operational instruments**, not smarter-than-the-model cognition.
Their value — which is real and measured — is:

- **Deterministic & reproducible** — same input, same output, no sampling variance.
- **Auditable** — every step is a logged, replayable record (run-record, PROV-O export).
- **Zero-token** — the KG-engine commanders run at 0 model tokens, sub-100 ms.
- **Scales past the context wall** — `scale_curve`: the engine holds 0.92 classification
  flat to **100 000 nodes** (0.04 s) where a base-LLM context **overflows at $5.58/solve**.

The honest one-liner: **bhgman_tool runs the same judgment a model could make, but cheaply,
repeatably, and at a scale a context window cannot hold.** That is an operational win, not
a cognitive one — and it is enough to justify the tool on its own terms.

## 3. Scope and what stays open

- **Regime.** This verdict is for the **within-competence regime** (tasks a base-LLM can
  already do). There, operational-only is robust.
- **Headroom regime — OPEN.** Whether structure wins on tasks *beyond* base-LLM competence
  (too large for context, needing persistent memory / audit / cross-session state) is being
  hunted (concurrent HARD-set line). If a headroom task shows real lift, this reframe earns
  a *cognitive exception there* — but the within-competence conclusion stands regardless.
  **Update 2026-06-02:** the first composition 4th-gate run (read-back evolve loop, the
  `prom16-bhgman-ci-design §5` falsifier) came back **4/4 UNREALIZED** on code tasks with
  qwen-0.5b/1.5b at token parity — the loop adds no equal-token win and on weak models is
  *worse* than best-of-N; oracle-gating alone is the strongest arm. Headroom at
  frontier-model / many-iteration scale (FunSearch's regime) stays open, but bhgman's
  current-reach answer is operational-only — consistent with this verdict, not an exception
  to it. See `SWEEP_RESULTS.md` §"Composition 4th gate".
  **PROM 16 revival audit 2026-06-02 → CLOSE-AS-OPERATIONAL.** A 16-cell literature PROM
  (`prom16-evolve-loop-revival-2026-06-02`) found the loop beats best-of-N at equal compute
  ONLY under 4 co-conditions — strong model (above the self-improvement floor), unsaturated
  headroom, island/diversity (not greedy top-K), and textual-feedback oracle (not scalar).
  Two are **HARD CEILING** for bhgman's reach: frontier-class models (FunSearch/AlphaEvolve
  win with Gemini-Pro/GPT-4, not 7B) and ~10⁶-sample eval budgets. So the loop is framed as
  *bounded oracle-guided repair*, never *discovery*; the deterministic oracle GATE (ARM3),
  not the agentic loop, is the defensible value. Reviving requires a frontier-scale experiment
  that would only re-confirm this negative. (A skeptic pass also voided one proposed "fix" as
  patching a non-existent bug — the read-back is already capped at best-K=2.)
  **CORRECTION 2026-06-02 (postmortem, 4 adversarial critics, conf 0.82–0.84): the loop-closure
  above was PREMATURE.** Splitting the two claims honestly: (i) *operational-substrate within
  competence* — VALID, robust (two independent lines). (ii) *"6/6 UNREALIZED → loop CLOSED for
  bhgman"* — PARTLY_ARTIFACT. The honest denominator is **2 underpowered nulls (hard/0.5b, hard/1.5b,
  n=4) + 4 non-measurements** (medium/1.5b, 7b+F4, 32b+F4 all saturate to all-arms=1.00 → paired
  delta=0, CI=(0,0), realized=False *by arithmetic*, not by measurement). Power and headroom are
  mutually exclusive across the whole sweep, so the design *structurally cannot* return "realized."
  Worse, the oracle is a 2-test pass-count (fitness ∈ {0,1,2}, no gradient for read-back to climb),
  ARM2 and ARM3 share that oracle (so "loop ≤ oracle-gate" is half a design tautology), and F3
  (island/diversity — the load-bearing FunSearch ingredient) was never implemented. And the CLOSE
  was committed (813da6f @21:21) *before* the confirming best-shot run (8768b9f @22:59) = confirmation
  toward closure. **Corrected status: operational-substrate (within-competence) STANDS;
  LOOP-HYPOTHESIS = POSITIVE (bounded repair) at the 32b tier — was "never tested fairly".** A fair test of
  the *repair-loop* variant (ARM2 oracle-guided repair vs ARM3 best-of-N, equal K=4) on real leak-resistant
  core-Lean with an ungameable `#print axioms` oracle was run 2026-06-05 (`LEAN_HEADROOM_FAIRTEST_2026-06-05.md`,
  model qwen2.5:32b-instruct). **Run A (thin band, 4 headroom tasks, 1 live) saw no edge — but that was a
  sampling artifact (no power), not a null.** **Run B — powered: headroom band enriched to 10 tasks (5 live)
  + graded oracle + 10 seed replications — REVERSED it: the repair loop BEATS best-of-N on boundary headroom
  (repair ≥ best-of-N in 10/10 runs, strict win 7/10, never loses; sign-test p=0.016). Per-task the new live
  tasks drive it: `dbl_ge` best-of-N 0/10 vs repair 5/10, `le_sumto` 1/10 vs 5/10.** Mechanism: the model
  gets *close* and the Lean error names the defect → repair converges where independent draws can't. So the
  loop structure (error-feedback) does add value beyond best-of-N **at the competence boundary** — bounded
  *repair*, not discovery. **Residual open axes:** frontier / reasoning model (qwen3 attempted, infeasible
  here >150 s/call) × real F3 island diversity (still unimplemented) × larger K × open-ended discovery (vs
  bounded tactic-repair). NB this *revises* the earlier "loop ≤ best-of-N" reading. See also `SWEEP_RESULTS.md`.
- **External impact — MEASURED 2026-06-04 → realized `trace` / potential `weak`.** A 6-dimension,
  13-agent audit (ungameable signals + preflight 3-falsifier + both-direction adversarial verify;
  all verdicts held) found **nothing has crossed an ungameable outside boundary**: GitHub stars/fork
  are all owner accounts and the 6567 clones are own-CI (r≈0.96 with Actions runs, 253:1 clone:view);
  not on PyPI/npm/Docker (the README's `pip install bhgman_tool` itself 404s); papers SUBMISSION_READY
  but unsubmitted in a PRIVATE repo (OpenAlex/Crossref/Zenodo/arXiv = 0 for author + "metahumotonic");
  the "3rd-party reproduction" is the owner's own company account running an AI agent (content
  non-circular, account-circular = trace); metahumotonic.com live but 7/7 feedback rows are owner
  LAN curl-probes; ~12 web searches + GitHub code-search = 0 genuine mentions. The two acts that would
  create external exposure (arXiv upload, PyPI publish) are owner-only and have not happened. Full:
  `EXTERNAL_IMPACT_AUDIT_2026-06-04.md`. (`project_bhgman_self_critique_2026_05_28`)
- **Do not over-correct.** "Not cognitively superior to a base-LLM" ≠ "useless." The
  operational properties above are real, valuable, and the correct basis for the tool's
  positioning. The claim is precise, not deflationary.

# KG: efficacy-measurement-line-2026-06-01, project_bhgman_ab_falsifier_2026_05_30,
#     project_ice_workbench_reframe_2026_05_18, project_bhgman_self_critique_2026_05_28
