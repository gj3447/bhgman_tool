# ADR: APT gate semantics — hook enforcement model + override mechanism

- **Status**: ACCEPTED (per cycle-bhgman-apt-completeness-remediation-2026-05-25 WQI F6)
- **Date**: 2026-05-25
- **KG ref**: `adr-apt-gate-semantics-2026-05-25`
- **Cross-ref**: `adr-apt-phase-contract-2026-05-25` (defines what is gated), `adr-apt-dgx-runtime-delegation-2026-05-25` (where the gate runs)

---

## Context

The APT phase contract (`adr-apt-phase-contract-2026-05-25`) declares preconditions for each phase. This ADR specifies **how** those preconditions are enforced, **where** the enforcement runs, and **how** overrides work.

Two enforcement layers exist:

1. **Claude Code Hook layer** (Inform + Constrain, runs on user's machine):
   - `~/.claude/hooks/pre_tool_apt_phase_gate_check.py` (PreToolUse on `mcp__neo4j__write_neo4j_cypher`)
   - `~/.claude/hooks/pre_tool_apt_autoflow_guard.py` (PreToolUse on `AskUserQuestion`)
   - `~/.claude/hooks/stop_apt_meta_review_ac_gate.sh` (Stop hook, Wave 9 §3 — installed 2026-05-25 per F5)
2. **SYMPOSIUM/dgx runtime layer** (Verify + Correct, runs on dgx):
   - `resolver_prototype/` (9/9 pytest) — phase precondition resolver
   - `gate_endpoint_prototype/` (6/6 pytest + OPA 0.66) — gate evaluator with policy

## Decision

### Two-layer enforcement (defense in depth)

- **Layer 1 (hook)**: fast-fail at editor time. Catches obvious violations (e.g. SCW dispatch without ST VR). Hook *exits non-zero* (block) for canonical violations; *exits zero with stderr alert* for borderline cases. Override per below.
- **Layer 2 (dgx runtime)**: authoritative verdict. Used when audit demands the policy engine (OPA) — e.g. multi-cycle batch audits. Hooks do not block on layer-2-only violations.

### Gate verdict states

`PASS` | `FAIL` | `SKIP` | `CONDITIONAL`. Per remediation of `taliban-blocker-C9-01-2026-05-13` (F9), SKIP is **never** counted as PASS — separate counter. `CONDITIONAL` requires a follow-up VR before downstream phase is unlocked.

### Override mechanism (escape hatch)

- **No silent override.** Every override requires a KG `:GateOverride` node with: `cycle_id`, `phase`, `bypass_reason`, `authorized_by` (= user verdict text), `expires_at`.
- Hook detects `:GateOverride {cycle_id: $cid, phase: $p, expires_at > now()}` and lets the action through with stderr disclosure.
- Default `expires_at` = 24 hours from creation. Permanent override requires `expires_at: 9999-12-31` + explicit user verdict including the phrase "permanent override".
- Cf. `feedback_blanket_proceed_authorization_pattern.md` — overrides recorded as `:DecisionLog` band `OVERRIDE_DELEGATED` for audit trail.

### Adversarial Challenge (AC) mandate

Per Wave 9 §3 (CLAUDE.md Constrain Layer 3): every sprint-end MetaReview cycle VR MUST emit `:AdversarialChallenge` ≥ 1. Hook `stop_apt_meta_review_ac_gate.sh` enforces. Zero AC = sprint-end fail.

### Numeric claim spot-check (CLAUDE.md Constrain Layer 4)

Any reported "N items done" claim adjacent to a gate verdict requires `MATCH (cycle {name: $cid})-[*]->(item) WHERE ... RETURN count(*)` reconciliation before send. Drift between report N and KG count = report rewrite, no override.

## Consequences

- **Positive**: Hooks catch 90% of violations in <100ms; dgx runtime handles the remaining policy-engine cases. Two-layer = no single point of bypass.
- **Positive**: GateOverride is recorded, time-boxed, and discoverable. No silent shortcuts.
- **Negative**: Hook scripts proliferate. Mitigation: each hook references its rule in `# KG:` comment; missing reference = orphan hook (Longinus L4 sweep catches).
- **Out-of-scope here**: layer-2 deployment topology — see `adr-apt-dgx-runtime-delegation-2026-05-25`.

# KG: wqi-bhgman-apt-F6-apt-adr-authoring-2026-05-25, APT_v26_A5_Gate_Hook_Lens_Enforcement_2026-04-21, hook-stop-apt-meta-review-ac-gate-2026-05-25
