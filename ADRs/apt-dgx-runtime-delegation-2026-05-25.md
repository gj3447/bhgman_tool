# ADR: APT dgx runtime delegation — cross-repo contract

- **Status**: ACCEPTED (per cycle-bhgman-apt-completeness-remediation-2026-05-25 WQI F6)
- **Date**: 2026-05-25
- **KG ref**: `adr-apt-dgx-runtime-delegation-2026-05-25`
- **Cross-ref**: `adr-apt-engine-scope-decision-2026-05-25` (the OUT-OF-SCOPE decision this delegates from), `adr-apt-gate-semantics-2026-05-25` (what is delegated)

---

## Context

`adr-apt-engine-scope-decision-2026-05-25` declared APT runtime OUT-OF-SCOPE for `bhgman_tool`. The runtime lives in `SYMPOSIUM/THEORY/APT/{resolver,gate_endpoint}_prototype/` and executes on the dgx host (verified: resolver 9/9 + gate 6/6 + OPA 0.66, per `reference_symposium_monorepo_mirror.md`).

This ADR fixes the **delegation contract**: how a `bhgman_tool` consumer (or anything else) invokes the dgx-resident runtime, what it gets back, and what guarantees the delegation preserves.

## Decision

### Delegation surface

The dgx runtime is reached via **two endpoints**, both authenticated by SYMPOSIUM bare-repo mirror policy:

1. **`resolver_prototype/`** — pure-function phase precondition resolver. Input: `(cycle_id, target_phase)`. Output: `ResolverResult { satisfied: bool, missing: list[str], evidence: list[KGRef] }`. No side effects.
2. **`gate_endpoint_prototype/`** — policy-gated phase evaluator. Input: `(cycle_id, target_phase, evidence_bundle)`. Output: `GateResult { verdict: PASS|FAIL|SKIP|CONDITIONAL, opa_policy_hits: list[str], vr_node_name: str }`. Side effect: writes `:ValidationResult` node to dgx-side KG mirror.

### Invocation contract

- **Transport**: cross-repo invocation is git-mediated (Mac edit → auto push → dgx bare → post-receive checkout → dgx WT). The runtime is *not* exposed as an HTTP/RPC service in this ADR. Reason: per `engineboy-canonical-2026-05-19` + `adr-bhgman-tool-in-process-default-2026-05-19`, RPC orchestration violates the agent-substrate-join principle. Delegation = "ship the inputs as committed evidence; pull the verdict back from the next mirror push".
- **Latency model**: cycle-batch, not per-request. Typical: hourly. Not suitable for in-loop gating.
- **Failure mode**: if dgx is offline, hook layer (`adr-apt-gate-semantics-2026-05-25` layer 1) is sole enforcement. Annotated `:GateVerdict` carries `source: HOOK_ONLY` flag — downstream audit can demote.

### What dgx runtime guarantees

- Idempotency on `(cycle_id, target_phase, evidence_sha256)` triplet.
- KG write isolation: ValidationResult writes are tagged `runtime: dgx-prototype-v0.x` for provenance.
- OPA policy version is recorded in every verdict (`opa_policy_sha256` field).

### What `bhgman_tool` guarantees (counter-party)

- All evidence referenced by `bhgman_tool` SCN nodes is sha256-baselined (per `lesson-longinus-self-violated-sha256-covenant-recurrence-root-cause-2026-05-20`, root-cause-fixed in `scripts/longinus_folder_mirror.py` 2026-05-25).
- Skill markdown is canonical at `SERVER/.claude/skills/apt-*/SKILL.md` via symlink (per F1 `decision-bhgman-apt-skills-symlink-to-server-2026-05-25`).
- Any APT-related KG node created by `bhgman_tool` carries `originated_in: bhgman_tool` for cross-repo provenance.

### Out-of-scope (deferred)

- Synchronous HTTP/RPC gateway — not built; would conflict with engineboy substrate-join principle.
- bhgman_tool-local mini-resolver — reopened only if a tool-layer consumer emerges and dgx-latency cycle-batch is unacceptable.
- Multi-host dgx scale-out — single dgx assumed; revisit at >10× current cycle volume.

## Consequences

- **Positive**: Single runtime, single OPA policy version, no dual maintenance burden.
- **Positive**: Mirror-based delegation honors `engineboy-architectural-exclusion-rpc-2026-05-19` + `adr-bhgman-tool-in-process-default-2026-05-19`.
- **Negative (acknowledged)**: cycle-batch latency unsuitable for interactive gating. Hook layer must remain authoritative for editor-time enforcement.
- **Test surface**: `SYMPOSIUM/THEORY/APT/resolver_prototype/pytest` (9 tests) + `gate_endpoint_prototype/pytest` (6 tests) + OPA conftest. Coverage maintained as ratchet (no regression).

# KG: wqi-bhgman-apt-F6-apt-adr-authoring-2026-05-25, adr-apt-engine-scope-decision-2026-05-25, reference_symposium_monorepo_mirror, engineboy-canonical-2026-05-19
