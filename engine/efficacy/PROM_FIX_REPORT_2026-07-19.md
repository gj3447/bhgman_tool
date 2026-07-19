# PROM — how to make oracle-repair beat best-of-N at equal compute

> 2026-07-19 · 16-agent PROM (12 research + synth + 3 adversarial critics, all SOUND_WITH_ADJUSTMENTS)
> KG: `project_ultimate_ai_tool_halo_loop_2026_07_19`
> Fixes the measured failure `halo_27b_run_2026-07-19/RESULTS.md` (repair 30 < bestN 34; repair = decoy 30).

## Consensus (what the literature + our data agree on)

- **C1 — DPI is the root (unanimous).** Error-conditioned retries are CORRELATED draws with per-retry
  fix-rate `q`; iid best-of-N draws have per-draw rate `p`. Repair beats bestN at equal K only when
  `q > p`. Measured 27b: `q < p` (feedback→fix 6 < 8; re-emit 14 > 3), so repair correctly loses the
  exploration it gave up. (Olausson, *Is Self-Repair a Silver Bullet?*, ICLR 2024 / arXiv:2306.09896.)
- **C2 — the CONDITIONING ACT collapses diversity, not signal quality.** decoy (bogus error, same
  volume) collapses diversity as much as real repair (2.36 ≈ 2.48). Our run confirmed it (repair =
  decoy = 30). ⇒ the primary lever is to REDUCE conditioning correlation, not improve the error text.
- **C3 — explore-FIRST beats pure sequential at a weak model / small budget.** Olausson: more initial
  samples `n_p` "consistently" gains; more repair fanout `n_fr` "not worth it". K=4 is the
  small-budget regime where best-of-N is compute-optimal (Wu; Snell). Spend the first N of K on iid
  draws to refill the coverage bestN had.
- **C4 — the load-bearing anchoring fix is DROPPING the verbatim failing proof** from the retry
  context (that is what produced the 14 re-emits), not writing a nicer error note.
- **C5 — a genuine `q`-lift needs a STRONGER feedback source.** Olausson: self-repair only clearly
  wins when feedback comes from a stronger model (human feedback lifts GPT-4 repair 33%→53%). At 27b
  self-feedback the model does not act on the oracle (our P2: repair = decoy).

## The honest ceiling (adversarial critics, all 3 lenses)

**At frozen 27b equal-compute, the structural fix can at best make repair TIE best-of-N — it cannot
win.** The critics overturned the synthesis's "structurally ≥ best-of-N" claim:

- The ONLY provable floor is **N=4 / M=0 = pure best-of-N**. Every `M ≥ 1` exploit slot trades an iid
  `p`-draw for a conditioned `q`-retry; with measured `q < p` that trade is **EV-NEGATIVE**, so a
  hybrid can land BELOW bestN, not merely tie. "Structural guarantee" was an overclaim.
- **keep-best-so-far is INERT for the binary proven-rate**: both arms early-exit on `proven`, so the
  proven count is already monotone; keep-best only changes the returned *graded* partial score.
- **re-emit→restart is INERT at M=1** (one slot, flag set after it is spent). The re-emit drop at K=4
  comes from explore-first cutting conditioned slots 3→1, not the dedup guard (it needs M ≥ 2).
- **WIN must be locked to proven-rate, not `graded_score`** (graded awards 0.5 to sorry-tainted
  compiles = a Goodhart surface).
- **Token parity is NOT "by construction"** — the exploit prompt carries the error note, so
  `halo_tokens > bestN_tokens`; only oracle-CALLS are equal. Verify token parity from the
  `in_tok/out_tok` ledger, don't assume it.
- **The 32b reflector is a DIFFERENT, larger compute class** — a separate flagged arm reported as
  "27b draws + 32b reflector", never silently switched inside a 27b equal-compute comparison.

## Recommended change (honest version)

1. **Move the hybrid split N=2/M=2 → N=3/M=1** (explore-first; Olausson) — the coverage restore. This
   removes the regression (repair stops LOSING) but only *ties* bestN at 27b.
2. **Drop the verbatim failing proof** from the exploit prompt; pass only the (short) error note.
3. **Lock the decision metric to PROVEN-rate**; bar `graded_score` from arm ranking.
4. **Temperature ladder 0.6→1.2 applied to BOTH arms** (compute-free diversity; laddering only repair
   = fake win). Keep decoy + plain as honesty gates; decoy must inherit the hybrid architecture.
5. **The only real-WIN path is a stronger reflector (dgx 32b) as a separate compute class** — or a
   revision-trained model — not a 27b equal-compute win.
6. Any N/G_THRESH sweep needs its OWN frozen prereg + held-out (the 10-task×4-seed grid is too small;
   a post-hoc winning config there is sweep noise).

## Honest bottom line

**You cannot make oracle-repair beat best-of-N at 27b equal compute — the honest deliverable is
"repair no longer loses" (ties bestN by degenerating toward it).** A genuine capability gain requires
`q > p`, which means a stronger feedback source (a bigger compute class), not raised model IQ. Every
gain here is oracle-channelled bounded search; the model is never made smarter (HONESTY LAW).
