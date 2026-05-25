# ADR: deterministic dispatch-output eval ("evals as unit tests")

- **Status**: IMPLEMENTED (PRELIMINARY — awaiting user CANONICAL verdict)
- **Date**: 2026-05-25
- **KG ref**: `finding-aidev-dispatch-eval-2026-05-25`
- **Parent driver**: PROM 16 `prom16-ai-dev-tools-2026-05-25` lever ③ / D-axis consensus C5 ("evals as the new unit tests").

---

## Context

bhgman_tool had unit tests + `quality_gate.py` + `dispatch_audit` (cardinality
drift), but no regression eval of the **output** subagents return. PROM DS2/DS4
found that the reliable, cheap baseline is **deterministic checks (100% coverage,
~0 cost)** — LLM-as-judge is biased/costly and was explicitly NOT adopted.

The project already *has* the contracts to check: FullFindingRecord shape, the
Longinus L4 citation covenant (the same gate the KG trigger enforces), the
WRITE_DEFERRED_TO_PARENT rule (`lesson-subagent-self-drift-kg-write-prom16-2026-05-24`),
and the jaebaeman V5 cardinality invariant.

## Decision

Add `engine/longinus_drift_audit/dispatch_eval.py` — pure, offline (no KG/network,
so it runs in sandboxed CI) — encoding those contracts as deterministic eval rules:
`has_finding_id`, `has_summary`, `has_citation` (url OR references OR waiver),
`valid_confidence`, `no_self_write_claim`, `has_agent_id`; plus an optional
cardinality check. Verdict: PASS / WARN (soft pass-rate shortfall) /
FAIL (hard breach: cardinality miss or self-write claim).

## Rationale

- **Reliable + free**: deterministic, matches PROM's recommended baseline layer.
- **Reuses existing canon**: the eval *is* the project's own contracts, so it
  cannot drift from them; runnable in the 4-ratchet pre-commit gate.
- **Offline**: zero KG dependency → works in sandboxed test envs (same principle as
  the root conftest TSV-first design).

## Consequences

- (+) Subagent output regressions (missing citation, self-write claims, cardinality
  miss) are caught deterministically. 13 tests; no runtime deps.
- (−) Deterministic ≠ semantic-quality: it checks contract conformance, not whether
  the *content* is good. LLM-as-judge for semantic quality is intentionally deferred
  (PROM DS4: judge reliability <50% on hard cases) — would require careful calibration.

## Follow-ups

- Wire into `audit_runner` / pre-commit so a recorded dispatch batch is eval'd each cycle.
- Optional golden-trajectory corpus for content regression (calibrated, opt-in).
