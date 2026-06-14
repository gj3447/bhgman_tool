# ADR: APT/TPA engine substrate scope — SUBSTRATE is in-scope, phase COGNITION stays orchestration

- **Status**: ACCEPTED
- **Date**: 2026-06-14
- **Supersedes (in part)**: `apt-engine-scope-decision-2026-05-25.md` ("APT execution engine OUT-OF-SCOPE")
- **KG ref**: `lesson-apt-tpa-engine-feasibility-2026-06-14`, `plan-apt-tpa-engine-substrate-2026-06-14`
- **Authority**: PROM 16 `prom16-apt-tpa-engine-2026-06-14` (16-cell unanimous HYBRID) + 3-lens naesengmoon adversarial verdict (`vr-prom16-apt-tpa-engine-consensus-naesengmoon-3lens-2026-06-14`) + filesystem reconciliation of a critic stale-KG drift (`reconcile-prom16-apt-tpa-critic-gate-stale-kg-drift-2026-06-14`); user verdict 2026-06-14 ("apt/tpa를 엔진으로 제대로" → Phase A+B+C) consistent with `apt-tpa-legion-engine-canon-2026-06-12`.

---

## Context — why the 2026-05-25 decision is reopened

The 2026-05-25 ADR decided "APT execution engine is OUT-OF-SCOPE for `bhgman_tool`; the resolver + gate + OPA runtime lives only on `SYMPOSIUM/dgx`." Its own escape clause: *"does NOT preclude bhgman_tool importing the prototype as a library later if a tool-layer consumer emerges. Reopen via new ADR if that happens."*

Two facts (2026-06-14, filesystem-verified) reopen it:

1. **The substrate already physically migrated into `bhgman_tool/engine/`** — and did so *before the 2026-05-25 ADR was even written*:
   - `engine/resolver/resolver.py` (A6 pre-prompt resolver) — provenance "Absorbed from SYMPOSIUM/THEORY/APT/resolver_prototype, Wave 7 P3-H, **2026-05-14**".
   - `engine/gate/` EXISTS: `gate_endpoint.py` (FastAPI, fail-closed) + `opa_client.py` + `circuit_breaker.py` + `policies/apt_phase_gates/{sa_to_sp,sp_to_st,st_to_scw,fulfillment_gate,break_glass}.rego` (dir dated 2026-05-14). Hardened 2026-06-14 (W1-C OPA decision-rule, W3-G circuit clock, W3-H break-glass).
   - `engine/legion/` (Contract-bound closed loop + G1/G2/G3 gated_run), `engine/longinus_drift_audit/` (tree_sitter/scip adapters + 5-drift), `engine/code_to_kg/` (tree-sitter `:CodeSymbol` extraction).
   So the original ADR's "lives only on dgx" claim was **partially stale from the day it was written**.

2. The PROM 16 cycle (16/16 HYBRID, HIGH) + adversarial review converged: APT/TPA decompose along a clean **generate-vs-check seam**, and only the **check/extract** half is engine-able — which is exactly the substrate already in `engine/`.

> **Honesty note (naesengmoon-corrected).** The reopen is justified by **substrate-already-migrated** (verified), NOT by "a tool-layer *APT* consumer emerged." `legion` is APT-*shaped* but APT-*content-disjoint* (it composes the 6 KG-graph commanders over Concept/Lesson nodes; it does not run the SA→SP→ST→SCW design→code workflow). Treating legion as an "APT consumer" is the conflation the adversarial pass refuted. The original ADR's *layer-split / duplication-drift concern remains valid*; the resolution is **import-not-port + single source of truth**, not a second copy.

---

## Decision

**The deterministic VERIFICATION/EXTRACTION substrate of APT/TPA is IN-SCOPE for `bhgman_tool/engine`. The GENERATION/JUDGMENT phases stay SKILL.md orchestration. "Engine the verbs, orchestrate the phases."**

- **ACCEPT as the APT/TPA tool-layer operational substrate** (already present, single source of truth = `engine/`):
  `engine/{gate, resolver, legion, longinus_drift_audit, code_to_kg, eureka, hades}`.
  `SYMPOSIUM/THEORY/APT/{resolver,gate_endpoint}_prototype/` is demoted to **spec/upstream reference** (one-way: engine/ is the runtime), pending the dedup decision (OQ2, user-verdict-gated as it is destructive).

- **RE-AFFIRM as orchestration (Rice-undecidable, LLM, must NOT be faked as deterministic engines)**:
  SA semantic-anchor selection; SP D(S) span decomposition + Crystallization-Frontier judgment + C(S) σ (semantic completeness, `apt-sp` marks 'human'); ST contract semantic content; SCW GREEN codegen; TPA semantic-intent recovery + Unknown→ResearchProvider + out-of-library NovelPattern. Engining any of these = *determinism theater* (the bhgman house lesson: cognitive lift ~0; value is operational substrate). Guard every PR with the `engine/efficacy/falsifier.py` circularity/signal-absent/signal-inverted preflight.

- **The one real missing deterministic piece (Phase B)**: `gate_endpoint._call_kg_with_retry` is a count-compare stub (no Neo4j). Replacing it with a real KG→Rego `input` materializer turns the gate from theater into a genuine engine. This is the only deterministic gap on the APT-forward verification spine.

- **Do NOT build an `engine/apt` facade.** With no APT-phase consumer, a re-export facade is ceremony (A3/S1 dissent, upheld). The APT-forward substrate is consumed directly via `legion/gated_run` + `gate`.

- **Build `engine/tpa` (Phase C) as a THIN composer** of existing engines (reversed legion loop TCW→ST→SP→TA), IMPORT-not-fork. This is the one genuine new build — TPA reverse extraction/drift is ~80% present but never composed into a runtime.

## Rejected alternatives

- **Port resolver+gate into a *new* copy** — re-litigates the 2026-05-25 rejected-alt-B (duplication-drift). They are already absorbed; the action is dedup + single-source, not re-port.
- **Build `engine/apt` that *runs* SA/SP/ST/SCW deterministically** — impossible (Rice) and dishonest (determinism theater).

## Consequences

- **Positive**: canon matches filesystem reality; the engine-vs-orchestration boundary is drawn explicitly and guarded; the one deterministic gap (gate materializer) and the one real build (engine/tpa) are named.
- **Negative (acknowledged)**: the SYMPOSIUM dgx prototype and `engine/` now provably diverge; OQ2 (freeze / re-point / delete the prototype after measuring drift) needs a user verdict (destructive).
- **Out of scope**: no change to the SA/SP/ST/SCW or TPA-intent skill workflow.

## Rollback

Revert by deleting this ADR; the 2026-05-25 ADR's OUT-OF-SCOPE stands again. Phase B (gate materializer) and Phase C (engine/tpa) are independent commits, individually revertible.

# KG: lesson-apt-tpa-engine-feasibility-2026-06-14 (resolved), plan-apt-tpa-engine-substrate-2026-06-14, vr-prom16-apt-tpa-engine-consensus-naesengmoon-3lens-2026-06-14, reconcile-prom16-apt-tpa-critic-gate-stale-kg-drift-2026-06-14, apt-engine-scope-decision-2026-05-25 (superseded-in-part)
