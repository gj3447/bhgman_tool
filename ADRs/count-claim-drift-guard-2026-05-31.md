# ADR: Count-claim drift guard — asymmetric (lean HARD / pytest soft)

- **Status**: ACCEPTED
- **Date**: 2026-05-31
- **KG ref**: `count-claim-drift-guard-2026-05-31`
- **Implements**: `verification/check_count_claims.py` + `verification/count_claims.json` + `.pre-commit-config.yaml` Stage 8
- **Authority**: follow-up to the 2026-05-30→31 README/docs honesty pass (commits `8095c88`, `bdc89e6`)

---

## Context

The README explicitly warns that theorem / sorry / pytest counts are
Goodhart-vulnerable — yet nothing *verified* that the documented numbers matched
the repo. They drifted silently and badly:

- `docs/04-references/lean-theorems.md` claimed "50 theorems / 5 files" long
  after the lean tree had grown to **71 / 13** (a whole `Measurement_*` family of
  26 theorems was undocumented).
- The README "Reproducing the claims" table told readers to run
  `grep ... lean/src/` and `lake build ... src/` — **`lean/src/` does not exist**,
  so the verifier commands could never reproduce the cited number.
- The "141+ theorems" figure (an *ecosystem-wide* count) was attached to a
  command that measures only *this repo*.
- pytest counts lagged ~2x (README said 267/446; reality 298/843, and growing).

The drift was *stale-low* (understatement from growth), not inflation — but it
still made the docs unreproducible and the project's own Goodhart warning came
true inside its own README.

## Decision

Add a guard (`verification/check_count_claims.py`) that re-measures the claimed
counts from the actual repo and compares them to a single source of truth
(`verification/count_claims.json`). Wire it as **pre-push Stage 8** (alongside
lychee / audit_grep_coverage — the existing network/slow ratchets).

The gating policy is **deliberately asymmetric**:

| Metric | Determinism | Gate | Rationale |
|---|---|---|---|
| `lean.theorems_tree` / `theorems_standalone` / `proof_position_sorry` | deterministic grep over `lean/` | **HARD** (exact match) | This is the metric that actually rotted (50→71). It changes only when `.lean` files change, so an exact pin costs nothing and blocks recurrence. |
| `pytest.*_collected` | grows as tests are added (often by a concurrent session) | **soft band** — fail only on *over-claim* (doc > reality, the credibility-damaging direction); *warn* on stale-low | Hard-pinning a growing number would manufacture churn and fight concurrent work. Over-claim is the only direction that is a *lie*; stale-low just nudges `--update`. |
| doc-presence | — | **HARD** | The manifest's lean numbers must literally appear in `lean-theorems.md`, so the prose cannot silently diverge from the manifest. |

pytest measurement uses `pytest --co -q` (collect-only): fast (~1.5s) and
independent of `ANTHROPIC_API_KEY` / optional extras (skipped tests are still
collected), which keeps the guard env-stable.

## Alternatives considered

- **Hard-pin every count exactly.** Rejected: pytest counts grow constantly
  (a concurrent session added 6 tests *during* this very change, 847→853). Exact
  pins would turn every test addition into a guard failure → churn → the guard
  gets disabled. Asymmetry keeps it credible.
- **No manifest, parse numbers straight out of README prose.** Rejected: brittle
  (a bare `298` matches many contexts) and couples the guard to prose wording. A
  small JSON manifest + a doc-presence assertion is more robust.
- **Auto-patch the README prose on drift.** Deferred: rewriting numbers across 4
  localized READMEs + docs is fragile. `--update` refreshes the *manifest*; the
  human refreshes the prose (the doc-presence check tells them which file).

## Consequences

- The exact drift we just cleaned up (lean counts, `src/` path) cannot silently
  recur — a stale lean count fails `git push`.
- Adding tests does **not** break everyone's push; it warns until someone runs
  `python verification/check_count_claims.py --update`.
- New count-claims are added by extending the manifest, not by editing the guard.
- Goodhart caveat (unchanged): the guard verifies *reproducibility of the
  indicator value*, not *validity of what it measures*. It stops the number from
  lying about itself; it does not certify the number means the system is correct.
