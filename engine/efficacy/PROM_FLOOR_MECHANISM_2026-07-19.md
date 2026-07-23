# PROM — what turns the feedback channel on? (floor-mechanism decomposition)

> 2026-07-19 · 16-agent PROM (12 research + synth + 3 critics, all SOUND_WITH_ADJUSTMENTS)
> KG: `project_ultimate_ai_tool_halo_loop_2026_07_19` · LakatoTree `Q-floor-mechanism-decomposition-2026-07-19`
> Full output: session tasks/wmrk2oeoa.output

## The question

The generator swap (dead qwen3.6-27b → live qwen2.5:32b) bundles FOUR variables: size, family/
post-training, quantization/serving, reasoning-mode (NO_THINK). Which turned the oracle channel on?

## Consensus (adjusted per critics)

- **C1 — feedback-use is a TRAINED skill, not (only) a size artifact** *(critic-adjusted: this is
  the leading hypothesis, NOT settled — D1 below stays open until the qwen3:32b rung runs)*. Every
  documented channel FLIP is training-side at fixed size: RISE (Llama2-7B +0.6→+17.7 after on-policy
  trace SFT), CYCLE (350M–3B: 0.0% → +15.6..63.5% after feedback fine-tuning; exact-copy anchoring
  42–65% before = our 14 re-emissions), Baldur (8B uses errors ONLY when trained with them — repair
  without error info == resampling = our repair=decoy), LEDEX, SCoRe. No documented flip is
  size-side at fixed training (untrained GPT-4 *degrades* under intrinsic self-correction).
- **C3 — quantization RULED OUT** as the driver: both regimes near-lossless at 32B, and our MORE-
  quantized arm (ollama q4) is the LIVE one — opposite sign. Do not spend a rung on q4-vs-FP8.
- **C4 — NO_THINK is the leading un-eliminated suspect.** Qwen3's mode fusion serves NO_THINK with
  an empty think block, amputating the CoT-over-error mediator (whose gain scales with capability).
  Goedel-Prover-V2 (built on Qwen3-32B!) has WORKING compiler-feedback self-correction — through
  long CoT. → **Mandated design change: run qwen3:32b in BOTH THINK and NO_THINK** — a within-model
  toggle at fixed size+family+quant, sharper than the size rung itself.
- **C5 — our decoy arm is NOVEL.** No published self-repair study runs a placebo-error control;
  reported gains in the literature may partly be redraw effects our design catches. (Nearest prior:
  Baldur's no-error ablation.) Keep decoy unchanged under every intervention.
- **C6 — single-shot competence does NOT predict repair capability**: our dead 27b out-scores the
  live 32b on bestN (34 vs ~23-pace). Never gate rungs on proven-rate.
- **C8 — Lean-corpus absence ruled out for qwen3**: Goedel-Prover-V2-32B (Qwen3-32B base) hits 88%
  miniF2F. Latent Lean knowledge is there; the *usable repair channel* is gated by post-training
  behavior and reasoning mode.

## Central open split (D1 — the ladder decides)

qwen3:32b NO_THINK @ ollama q4 (quant+serving now MATCHED to the live arm): 4 findings predict DEAD
(trained-skill account), 3 predict LIVE (arXiv 2604.10508 measured this exact checkpoint consuming
Python tracebacks productively NO_THINK). Preregistered third state: repair>decoy but repair≤bestN =
content-used-but-unprofitable. Iscan (arXiv 2606.31511) provenance UNVERIFIED — possibly
adjacent-programme output; discount its statistics until verified.

## Probe design (critic-adjusted)

- **Stage 0 (screening ONLY, never a verdict):** hint-consumption probe (~1/5 cost). Retrospectively,
  our sonnet-hints −5 was the 27b death certificate before the full A/B ever ran.
- **Stage 1 (free, from transcripts):** localize-only probe (Lean prints line/col — is localization
  or error-conditioned *editing* the bottleneck) + CYCLE-style copy-rate (anchoring metric).
- **Stage 2:** the 5-arm A/B. **≥6 seeds for a LIVE verdict** (paired power 0.92); 3-seed interims
  (power 0.51–0.63) NEVER promote. DEAD = TOST equivalence, never a bare nonsignificant p.
- **Continuous-metric secondaries MANDATORY** (Schaeffer mirage guard): error-count delta,
  first-error-line progression, edit-distance. *Session check: summary-level graded==binary on
  headroom (no partial credit ever earned) → the mirage test must run at attempt level.*

## Induction paths (ranked; anti-paths measured dead)

P1 few-shot repair exemplars (RING; ~0 cost, strongest untried zero-training lever) → P2 THINK
toggle (~0 cost, serving flag) → P3 error-only prompt (drop the model's own failing draft — the
anchoring trap is part of bestN>repair) → P4 on-policy repair-trace SFT (500–3k own-failure traces,
oracle-verified; SWE-Gym 491 traces → +13.6pp at 32B; dgx-feasible) → P5 SCoRe-style RL (last
resort). **Anti-paths (spend nothing):** runtime frontier hints (our −5), self-reflection (−4),
off-policy teacher-trace SFT, diff-format outputs, q4-vs-FP8 rung.

## Critic adjustments honored

- one_line's "not a size floor" was premature — D1 stays OPEN (confound-honesty lens).
- Continuous-metric retrospective ran (vacuous at summary level; attempt-level queued).
- Stage-0 stop rule demoted to screening-only (power discipline).
- Backend label caveat: `frontier:` prefix is the openai-compat client label — both the June anchor
  and this re-pin actually serve via dgx **ollama** (tunnel); the label does not record the stack.
