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
- **External impact — UNMEASURED.** Every number here is internal/self-referential. Whether
  anyone *outside* this project uses or benefits from the tool is the genuinely untested
  axis (`project_bhgman_self_critique_2026_05_28`).
- **Do not over-correct.** "Not cognitively superior to a base-LLM" ≠ "useless." The
  operational properties above are real, valuable, and the correct basis for the tool's
  positioning. The claim is precise, not deflationary.

# KG: efficacy-measurement-line-2026-06-01, project_bhgman_ab_falsifier_2026_05_30,
#     project_ice_workbench_reframe_2026_05_18, project_bhgman_self_critique_2026_05_28
