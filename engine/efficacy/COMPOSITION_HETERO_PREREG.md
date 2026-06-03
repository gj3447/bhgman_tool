# Pre-registration — Heterogeneous 7-commander composition A/B (the untested cognitive axis)

> **PRE-REGISTERED 2026-06-03, BEFORE any run.** Committing the design first is the discipline
> the evolve_loop test violated (CLOSE committed before the confirming run = confirmation bias,
> `VERDICT.md` §3 postmortem). Predictions + falsification criteria below are fixed before data.
> KG: project-apt-ultracode-roadmap-2026-06-02, project-bhgman-efficacy-verdict-operational-substrate-2026-06-02

## 0. The gap this closes

The "cognitive advantage ≈ 0" verdict is, by construction, a **single-agent** result: every
commander was measured 1:1 vs a base-LLM at equal tool budget (`VERDICT.md` §1). Single-agent
measurement **cannot see composition effects**. The one composition test (`composition_ab.py`) tested
the *homogeneous* `evolve_loop` (one generator iterating on itself) — and that was retracted to
`LOOP-HYPOTHESIS = OPEN` (unfair: saturation / no oracle gradient / F3 unimplemented / premature
close).

**Never tested:** the *heterogeneous* 7-commander legion composition — 재배맨(출격) dispatching the
6-stage 이종 pipeline 획득(prometheus)→연결(longinus)→창조(eureka)→정리(occam)→검증(naesengmoon)→
실현(hades), where each stage is a **different** cognitive operation. The hypothesis: a heterogeneous
handoff produces a better artifact than one undecomposed base-LLM call at equal compute. This is the
axis the user flagged ("agent 하나하나만 봐서 그런 거 아니냐"). It is **OPEN, not refuted.**

## 1. Arms (equal total generation-token budget T — the honest control; loops/pipelines regenerate)

| arm | what | null it kills |
|---|---|---|
| **ARM1 base-monolith** | best-of-N undecomposed base-LLM calls up to T tokens; pick by PUBLIC signal | "one big call = the pipeline" |
| **ARM2 hetero-legion** | 재배맨 dispatches the 6-stage 이종 pipeline, total T tokens across stages; the assembled artifact | (the hypothesis arm) |
| **ARM3 gate-only ablation** | base-LLM + ONLY the 검증(naesengmoon) gate (no gather/connect/abstract/prune/realize), T tokens | "the win is just having a verify gate, not the heterogeneous structure" |

`realized` = ARM2 beats **both** ARM1 **and** ARM3 (paired bootstrap CI lower bound > 0).
ARM2 ≤ ARM1 ⇒ "just spent more compute". ARM2 ≤ ARM3 ⇒ "the gate did it, the pipeline is décor".
(Same non-circular logic as `composition_ab.py`, generalized from homogeneous loop → heterogeneous pipeline.)

## 2. Task set — leak-resistant, graded, unsaturated (primary: Lean proving)

Reuse the W4 oracle built 2026-06-03 (`lean_axiom_probe.py` + `apt_metrics_gen.disjunct_discharge_suspects`):

- **Task** = prove a target Lean lemma (Mathlib-free, standalone).
- **PUBLIC signal** (what the pipeline/loop may see) = `lake`/`lean` compiles + # subgoals closed (graded fitness, *not* binary — fixes evolve_loop's "no gradient").
- **HIDDEN non-circular oracle** (eval only) = genuine-proof check the generator never sees:
  (a) `#print axioms` shows **no `sorryAx`**, (b) **no disjunct-discharge** (statement not weakened — the exact Mirsky failure mode), (c) **statement-fidelity** (the proven proposition is the asked one, not a `∨ trivial` weakening).
- **Leak-resistant**: you cannot fake a real proof — the hidden oracle is ground truth, uncircular with any PUBLIC signal the agents optimize.
- **Difficulty**: tuned so the base-LLM does **not** saturate (baseline hidden-pass < ~0.7), fixing evolve_loop's all-arms=1.00 collapse.

(Secondary task family: code (LEVER/AlphaCode public→hidden split) for cross-domain check — but Lean is primary because the hidden oracle already exists and is uncircular.)

## 3. The 4 failures of the evolve_loop test → how this avoids each

| evolve_loop failure | this design |
|---|---|
| Saturation (6/6 → all-arms=1.00, delta=0 by arithmetic) | difficulty-tuned tasks, baseline hidden-pass < 0.7, graded oracle |
| No oracle gradient (binary 2-test) | subgoal-count + sorry-count graded fitness |
| F3 (island/diversity) unimplemented | N/A — heterogeneity is **inherent** (6 stages are different operations, not a population) |
| CLOSE committed before confirming run (confirmation bias) | **this doc pre-registers** prediction + criteria before any run |

## 4. Hard ceilings — stated upfront (PROM 16 revival audit `prom16-evolve-loop-revival-2026-06-02`)

Composition beats best-of-N only under: **strong model** (above the self-improvement floor — frontier-class, NOT 7B) × **unsaturated headroom** × **diversity/heterogeneity** × **graded/textual oracle**. For THIS design heterogeneity + graded oracle are satisfied by construction; **strong-model + non-trivial budget are a HARD CEILING** — a fair run needs a frontier-class backend (ANTHROPIC_API_KEY / capable local) and a real token budget. A weak-model run will reproduce the negative and prove nothing about the hypothesis.

## 5. Pre-registered prediction (fixed before data)

Honest prior, given single-agent ~0 + the anti-emergence discipline: **most likely ARM2 ≈ ARM1 (realized = False)** — composing ~0 agents tends to compound cost, not cognition. A *surprising* `realized = True` (ARM2 > ARM1 ∧ ARM2 > ARM3, CI_lower > 0) would be the first evidence of a genuine compositional cognitive win and would earn a scoped "cognitive exception" exactly as `VERDICT.md` §3 reserves for the headroom regime. Either result is informative; neither is assumed.

## 6. What runs NOW (deterministic) vs needs a backend

- **NOW (offline, falsifiable):** the harness + `realized` gate + a fake-LLM injection test proving the gate fires correctly (planted: heterogeneous handoff helps → realized / handoff useless → unrealized) — mirroring `test_composition_ab.py`.
- **Needs a frontier backend:** the three LLM arms on real Lean tasks. Without it the experiment is designed + gated but not executed (honestly UNRUN, never reported as a result).

## 7. Anti-over-claim clause

`realized = True` would mean **the 7-commander composition, at equal compute, produced more genuinely-proven artifacts than a base-LLM** — an operational+cognitive win *in this regime*, not a universal one. `realized = False` confirms the within-competence operational-substrate verdict extends to composition. Neither result is "the framework is superior"; both are scoped measurements. The word "emergence" is banned from the writeup (confirmation-bias attractor, `feedback_empirical_falsifier_before_grand_frame`).
