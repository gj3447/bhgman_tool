# Lean-headroom 32b re-run — repair vs best-of-N (2026-06-14)

Closes the **H2 reproducibility gap**: the historical 32b "repair > best-of-N" signal (p=0.016)
was flagged non-reproducible because its raw JSONL was never committed (the committed 7b re-pin was
NULL, p=1.00). This re-runs 32b with the **raw JSONL committed** (`seed_0..seed_90.jsonl`).

## Setup
- Model: `qwen2.5:32b-instruct` (dgx ollama via ssh tunnel), `LEAN_K=4`, n=10 replications (seed offsets 0..90).
- Oracle: Lean 4.30 compile-check (ungameable), headroom task set, graded 0/0.5/1.
- Harness: `engine.efficacy.lean_headroom_run`; analysis: `analyze_lean_headroom.analyze_paths`.
- Gate: `engine.efficacy.headroom_verdict.HeadroomVerdict` (positive-invariant checker, RED-first).

## Result (n=10, gated)
```
headroom repair-vs-bestN: 8W / 2T / 0L over 10 runs, p=0.007812 → SIGNIFICANT (repair_favored)
```
- Two-sided exact sign test on `headroom_only` repair vs bestN, ties ignored: 8 wins, 0 losses → p=2·(0.5)^8 = 0.0078.
- `HeadroomVerdict` invariants PASS: runs≥1, tally conservation (8+2+0=10), non_ties==wins+losses (8==8+0), p∈[0,1].
- Reproduces (and slightly strengthens) the historical 32b p=0.016.

## Honesty notes
- A mid-run read showed n=9 (seed_90 was still being written — the stale-read pattern); the verdict
  above is the post-completion re-fetch (n=10). The gate computed conservation correctly on whatever
  completed, but the honest n is 10 only after the process exited.
- This is the **headroom** result (repair reaches beyond best-of-N via the ungameable oracle), NOT a
  within-competence cognitive-uplift claim. The house verdict stands: bhgman = operational substrate;
  the cognitive edge appears only in the bounded-repair headroom regime, and only at a capable model (32b),
  not 7b (NULL).

# KG: TDD:headroom_verdict:* (positive-TDD contracts), project_bhgman_efficacy_verdict_operational_substrate_2026_06_02
