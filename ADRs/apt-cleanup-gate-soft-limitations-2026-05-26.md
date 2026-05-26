# ADR: APT CleanupGate Soft Limitations — Accepted Constraints (F10)

- **Status**: Accepted — 2026-05-26
- **Supersedes / closes**: `ac-bhgman-tool-apt-completeness-constitutional-F10` (LOW)

## Context

apt-completeness Naesengmoon audit (2026-05-25) raised F10: CleanupGate run
`bhgman_tool-phase6-cleanup-2026-05-13` PASSed, but the completeness signal is weak:

- `commit_ratio` (refactor:feature) = **0.25** — target ≥0.2 is met, but the margin is thin.
- 3 honest_limitations recorded:
  1. `tach` not configured (no module-boundary enforcement).
  2. `deptry` runs in monorepo-pattern mode (not strict per-package).
  3. `complexipy` threshold = 15 (cognitive complexity), not the stricter 10.

No-discard policy is **not** violated — the gate ran and disclosed its limits honestly.

## Decision

Accept these as **permanent soft constraints** rather than forcing closure, per the
F10 remediation option *"escalate to ADR if accepted as permanent constraint."*

Rationale:

1. `commit_ratio` is a **forward-looking behavioral metric**, not a fixable state. It
   cannot be "perfected" — consistent with the APT essential property *Gödel: never
   complete*. Chasing it to 1.0 would be Goodhart's-law gaming.
2. `tach` config + `complexipy` strict-10 are **future tooling investments**, not
   correctness gaps. The current ≤15 threshold passes; 295 engine tests + 505 total green.
3. The limitations are disclosed, tracked, and now formally accepted — the opposite of
   silent ignorance.

## Consequences

- CleanupGate limitations are documented, not swept under the rug.
- **Revisit triggers**: `commit_ratio` degrades below 0.2, OR `tach`/`complexipy` strict-10
  tooling is adopted (at which point the constraint should be tightened, not just re-accepted).

# KG: ac-bhgman-tool-apt-completeness-constitutional-F10, cycle-bhgman-apt-completeness-remediation-2026-05-25
