# ADR: APT phase contract — SA → SP → ST → SCW gate chain

- **Status**: ACCEPTED (per cycle-bhgman-apt-completeness-remediation-2026-05-25 WQI F6)
- **Date**: 2026-05-25
- **KG ref**: `adr-apt-phase-contract-2026-05-25`
- **Authority**: cycle plan F6 (3-ADR set) + user verdict 2026-05-25 Session 2 blanket-proceed
- **Cross-ref**: companion ADRs `adr-apt-gate-semantics-2026-05-25`, `adr-apt-dgx-runtime-delegation-2026-05-25`

---

## Context

APT methodology (v27 canonical, per `SYMPOSIUM/THEORY/APT/`) defines a four-phase cycle: **SA (SemanticAnchor) → SP (SemanticPyramid) → ST (SemanticTwin) → SCW (SourceCodeWorld)** + optional Phase 5 MetaReview + Phase 6 Cleanup. Each transition is gated; gates carry preconditions and produce ValidationResult nodes.

The `bhgman_tool/skills/apt*` symlinks (per `decision-bhgman-apt-skills-symlink-to-server-2026-05-25`) ship the *instruction layer*: how each phase should behave. They do not enforce contracts at runtime — runtime enforcement lives on dgx per `adr-apt-engine-scope-decision-2026-05-25` (Option A).

This ADR captures the **contract** that the skill layer documents and any runtime enforces — naming the precondition and postcondition that every phase honors.

## Decision

The APT phase chain is governed by the following contract:

### Phase preconditions (incoming)

| Phase | Required from prior phase | Failure mode if missing |
|---|---|---|
| **SA** | Topic + project anchor; no prior phase required | `APT_GATE_VERSION=v27_phase_sa_no_topic` |
| **SP** | SemanticAnchor with 5 core fields (objective / definition / keyAssertion / C_S / contextBudget) populated; gate VR APPROVED | `APT_GATE_VERSION=v27_phase_sp_dispatch_guard` |
| **ST** | All SP leaf spans = AtomicSpan (Crystallization Frontier); gate VR APPROVED | `APT_GATE_VERSION=v27_phase_st_dispatch_guard` |
| **SCW** | Per-AtomicSpan Contract crystallized + 8 ST Decision Areas covered; gate VR APPROVED | `APT_GATE_VERSION=v27_phase_scw_dispatch_guard` |
| **MetaReview** | SCW completion VR + AdversarialChallenge ≥ 1 (Wave 9 §3 Constrain Layer) | `APT_GATE_VERSION=v27_phase_meta_review_dispatch_guard` |

### Phase postconditions (outgoing)

| Phase | Must emit | Consumer |
|---|---|---|
| **SA** | `:SemanticAnchor` node + 5 core fields + `:HAS_ROOT` to root Span | SP |
| **SP** | Root Span + N-level decomposition with leaves marked `:AtomicSpan`; C(S) 5-predicate non-null on every Span | ST |
| **ST** | Per-AtomicSpan `:Contract` + `:Task` + 8 ST Decision Area annotations | SCW |
| **SCW** | Per-Task `:SourceCodeNode` + tests (TDAD impact_tests mandatory) + `# KG:` ref comments (Longinus L5-L7 forward binding) | MetaReview |
| **MetaReview** | `:Lesson` (≥0) + Naesengmoon self-meta VR + `:AdversarialChallenge` ≥ 1 | Cycle close |

### Dispatch-only rule (PATTERN_D)

Phase skills (`apt-sp`, `apt-st`, `apt-scw`, `apt-meta-review`) **MUST NOT** be invoked directly by user — `/apt` orchestrator is the sole entry point. Direct invocation triggers `APT_GATE_VERSION=v27_phase_<X>_dispatch_guard` rejection. Rationale: SA→SP→ST→SCW chain preconditions are auto-satisfied only through orchestrator dispatch (lesson `rf-prom16-cc-eng-E1-S4-skill-activation-2026-05-14`).

### Self-application forbidden (MetaReview)

MetaReview MUST NOT recursively MetaReview itself (`self_application_forbidden, max_depth=1, delta=0`). Reason: infinite loop. Other 5-weapon dispatch FROM MetaReview is allowed (Naesengmoon recursive self-meta per Wave 9 §3 is *target=MetaReview output*, not *target=MetaReview self-invocation*).

## Consequences

- **Positive**: Single source of truth for what each phase delivers. Consumers (skills, runtime, audits) read the same contract.
- **Positive**: Failure modes have canonical `APT_GATE_VERSION` strings — easy to grep for in error reports.
- **Negative (acknowledged)**: Contract is prose ADR, not Lean-formalized. If a precondition is added in a future v28, this ADR must be revised in lockstep (cf. `feedback_canon_propagation_simultaneous.md`).

## Cross-references

- Runtime enforcement: `adr-apt-gate-semantics-2026-05-25` (hook model)
- Delegation to SYMPOSIUM/dgx: `adr-apt-dgx-runtime-delegation-2026-05-25`
- v26 → v27 RFC: `SYMPOSIUM/THEORY/APT/SOURCES.md` §RFC1+RFC2

# KG: wqi-bhgman-apt-F6-apt-adr-authoring-2026-05-25, APT_methodology_v27, MIC_v1
