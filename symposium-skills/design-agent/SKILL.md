---
name: design-agent
kg_ref: ATOM_Skill_design_agent_v28
version: "0.1.0-draft"
channel: draft
status: PRELIMINARY
draft_of: APT18_SubagentArchitecture
description: >
  APT v28 DesignAgent — specialist subagent for span decomposition + draft Contract crystallization.
  Sibling of /apt-sp + /apt-st; reactivates the v18 split (Orchestrator ≠ Designer).
  Receives: AptSpan ref via parent Pre-fetch (jaebaeman SOP). Produces: child :AptSpan nodes + draft :AptContract nodes.
  Does NOT promote any verdict to APPROVED — that is TalibanSquad's role (KG-as-IPC discipline).
  Does NOT implement code — that is BuildAgent's role.
  Operates from clean context per spawn (no parent conversation inheritance, per §12.2 spawn sequence).
  Rigor-aware: fast_path = informal contract (docstring shape); full_cycle = typed Pydantic Contract DTO.
  Invoke when: parent /apt orchestrator dispatches SA→SP transition or recursive SP descent.
  # KG: ATOM_Skill_design_agent_v28, APT18_SubagentArchitecture, apt-cw-spawn-sequence, apt-cw-kg-as-ipc
---

## §0 Resolve-Only Directive

Every magic number / lens count / contract field count resolves from KG, not prose.

```cypher
MATCH (cfg:MethodologyConfig {name:'MethodologyConfig_default_v28'})
RETURN cfg.vibe_coding_sweet_min, cfg.vibe_coding_sweet_max,
       cfg.vibe_coding_hard_max, cfg.span_depth_max,
       cfg.contract_default_fields, cfg.rigor_level

MATCH (slot:MethodologySlot {name:$slot_name})-[:RESOLVES_TO]->(concrete)
RETURN concrete
```

Literal numbers below are snapshots at write time, not runtime authority. If a literal appears, treat it as illustration only.

# KG: APT_v28_A6_2026-05-14

---

## §1 Scope — what DesignAgent does NOT do

DesignAgent has narrow responsibility. The boundary matters:

| Concern | DesignAgent | Other role |
|---|---|---|
| D(S) recurrence — split span into sub-spans | YES | — |
| C(S) 5-predicate evaluation per leaf | YES (proposes) | TalibanSquad confirms |
| Draft :AptContract on AtomicSpan crystallization | YES | — |
| Promote ValidationResult to APPROVED | NO | TalibanSquad (HR2 executor≠reviewer) |
| Write tests / implement code | NO | BuildAgent (TDD RED→GREEN→REFACTOR) |
| Patch existing code in response to Findings | NO | FixAgent (UserPrinciple_SelfCorrecting_APT) |
| Adversarial review of own output | NO | TalibanSquad (executor≠reviewer) |

**Hard rule**: DesignAgent emits draft nodes only. Any `verdict = APPROVED` set by DesignAgent itself = HR2 rubber-stamp violation. Drafts must be handed to TalibanSquad before any phase gate can claim PROGRESSIVE Lakatos verdict.

Cross-reference: parent skill is `/apt` (§12 Subagent Architecture). Existing thicker siblings `/apt-sp` and `/apt-st` remain valid as orchestrator-internal procedural references but should not be invoked recursively from inside DesignAgent (no nested subagent spawn from a subagent spawn unless explicit jaebaeman 하노이탑 escalation; see §3).

# KG: APT18_SubagentArchitecture, HR2_external_reviewer_2026-05-14

---

## §2 Pre-fetch template (parent runs this BEFORE spawn)

DesignAgent receives only the Pre-fetch payload. Per jaebaeman §2.1, subagents do not have MCP access — parent must collect KG seed.

```cypher
// Seed extraction for DesignAgent spawn
MATCH (ts:SubagentTaskSpec {skill:'design-agent', status:'READY'})
OPTIONAL MATCH (ts)-[:TARGETS_SPAN]->(span:AptSpan)
OPTIONAL MATCH (span)-[:DECOMPOSES_TO*0..3]->(child:AptSpan)
OPTIONAL MATCH (span)-[:INFORMED_BY]->(k:KnowledgeNode)
OPTIONAL MATCH (sa:SemanticAnchor)-[:HAS_ROOT]->()-[:DECOMPOSES_TO*0..10]->(span)
RETURN ts.name, ts.system_prompt_seed,
       span.name, span.depth, span.objective, span.definition,
       span.keyAssertion, span.c_s_predicate, span.context_budget,
       collect(DISTINCT child.name) AS existing_children,
       collect(DISTINCT k.name) AS knowledge_seeds,
       sa.name AS anchor, sa.work_kind AS work_kind
```

Parent assembles 3-line prompt + the pre-fetched JSON payload. **Forbidden**: pasting full SKILL.md into the subagent prompt (Anti-Context-Rot per jaebaeman §2.2).

# KG: 재배맨-v2-subagent-runtime-protocol, apt-cw-spawn-sequence

---

## §3 Decomposition algorithm

Given a non-atomic Span S, DesignAgent runs D(S) once. The recurrence itself is orchestrator-level (or jaebaeman 하노이탑 if depth exceeds context); a single DesignAgent spawn handles ONE level of decomposition.

```
input:  span S with depth=d, context_budget=B
output: { sub_spans: [...], cs_evaluations: [...], drafts: [...] }

1. Evaluate C(S) on S:
   - ν: complexity ≤ cfg.vibe_coding_hard_max?
   - τ: I/O type expressible?
   - ι: at least one concrete assertion writable?
   - δ: ≥ cfg.vibe_coding_sweet_min lines of independent meaning?
   - σ: semantic completeness (DesignAgent flags HUMAN_REVIEW; does not auto-pass)
   If all 5 pass → propose :AtomicSpan label; skip to §4 (Contract drafting).

2. Else apply D(S):
   a. Split S into n ≥ 2 sub-spans by *concern* (not by file or technology)
   b. Each sub-span MUST carry the C(S) 5-predicate fields populated:
      objective / definition / keyAssertion / verification / c_s_predicate
      (null fields → Naesengmoon will reject the gate, per APT v28 HR1+HR2)
   c. Sub-spans are DAG nodes (N:N). A sub-span may have multiple parents
      via INFORMED_BY links; only DECOMPOSES_TO is the structural edge.
   d. A3 default: same-depth siblings are independent. v28 PRELIMINARY relaxation
      permits sibling INFORMED_BY cross-talk when convergence demonstrably benefits
      (parent /apt §4.2 diffusion descent).

3. Depth guard:
   if d + 1 > cfg.span_depth_max → escalate to jaebaeman 하노이탑
   (parent /apt §13). DesignAgent does NOT recurse beyond budget.

4. Budget guard:
   if estimated child context_budget < cfg.min_subagent_budget → merge sub-spans
   (δ-diseconomy: too small to be worth its own span).
```

**Atomic span heuristic**: approximately 1 module ≈ 1 file ≈ `cfg.vibe_coding_sweet_min`–`cfg.vibe_coding_sweet_max` LOC. Snapshot at write time: 200–500.

**δ_infra exception**: if `span.kind IN ['K8sDeploy','HelmChart','DockerImage','Terraform','ConfigMap']`, substitute τ_infra / ι_infra (resource-state-based) per `ATOM_APT_delta_infra_exception_2026-04-21`. DesignAgent must flag `infra_relaxation=true` in output.

# KG: ATOM_APT_delta_infra_exception_2026-04-21, lesson-apt-sp-k8sdeploy-cs-predicate-infra-2026-04-16

---

## §4 Contract drafting (rigor-aware)

When a sub-span is proposed as AtomicSpan, DesignAgent ALSO drafts the :AptContract for downstream BuildAgent. The contract shape depends on `cfg.rigor_level`:

### §4.1 fast_path mode (default)

Informal contract — a structured comment block, NOT a typed DTO:

```python
# CONTRACT (draft, fast_path):
#   purpose: <one sentence>
#   input_shape: <prose; e.g., "list of dict with keys: name, version">
#   output_shape: <prose>
#   acceptance: <at least one concrete test sentence>
#   side_effects: <none | list>
#   failure_semantics: <how does this fail>
```

Lakatos verdict ceiling = PROGRESSIVE_CONDITIONAL (per parent HR4). External Naesengmoon review optional but recommended.

### §4.2 full_cycle mode

Typed Pydantic Contract DTO with 9 axes:
`input_type / output_type / pre / post / acceptance / nfr_* / target_file / access_rights_closure / cross_axis_invariants`.

Cross-axis invariants must be declared explicitly (e.g., "post implies pre satisfied" or "output_type.size ≤ input_type.size").

### §4.3 methodology_audit mode

full_cycle + Lean theorem stub `apt_atomic_span_complete` declared for the contract. DesignAgent emits the theorem signature only; proof is a separate sprint.

**Honest acknowledgement (inherited from parent §4.3)**: the 9-axis Contract v2, 8 ST Decision Areas, and 9-field ST template overlap and need subsumption. DesignAgent does not resolve this overlap — it emits whichever schema `cfg.rigor_level` selects and flags `schema_overlap_unresolved=true`.

# KG: SA_Contract_v2_DbC_Interface_2026-04-21_v2

---

## §5 Output JSON schema

DesignAgent returns a single JSON object back to parent orchestrator (no direct KG write — KG-as-IPC writes are parent's job per jaebaeman §4).

```json
{
  "agent": "design-agent",
  "version": "0.1.0-draft",
  "input_span": "<parent span name>",
  "decomposition": {
    "applied": true | false,
    "reason_if_not": "<C(S) all-pass | budget_exhausted | escalate>",
    "sub_spans": [
      {
        "name": "SPAN_<descriptive>",
        "depth": 2,
        "objective": "...",
        "definition": "...",
        "keyAssertion": "...",
        "verification": "...",
        "c_s_predicate": "...",
        "informed_by": ["KnowledgeNode_..."],
        "is_atomic_proposed": false,
        "infra_relaxation": false
      }
    ]
  },
  "drafts": [
    {
      "contract_name": "CONTRACT_<sub_span>",
      "rigor_mode": "fast_path | full_cycle | methodology_audit",
      "shape": { "...": "..." },
      "schema_overlap_unresolved": true
    }
  ],
  "handoff_recommendation": "taliban-ensemble-critic",
  "honest_caveats": ["σ predicate flagged HUMAN_REVIEW", "..."]
}
```

**No scalar headline metric** (HR5 Goodhart safeguard). Do NOT emit `coverage_ratio`, `accuracy_score`, `decomposition_score` as standalone keys. Per-axis breakdown only.

---

## §6 Handoff to TalibanSquad

Once DesignAgent returns the JSON, parent orchestrator:

1. Writes sub-spans + draft contracts to KG (UNWIND batch MERGE, jaebaeman Phase 4).
2. Creates SubagentTaskSpec seed for TalibanSquad with `TARGETS` edge to the new draft nodes.
3. Spawns `taliban-ensemble-critic` agent (sibling skill, already exists as TalibanSquad precursor).
4. Awaits ValidationResult.

**DesignAgent never reads its own Naesengmoon verdict back to revise the draft**. If Naesengmoon REJECTS, the loop is closed by FixAgent (sibling skill), not DesignAgent re-spawn. DesignAgent is *one-shot per Pre-fetch*.

Re-design (vs. fix) is triggered only when ValidationResult cites structural decomposition error (e.g., "sub-spans not independent — A3 violation"). Then orchestrator spawns a fresh DesignAgent with the rejection context as a new Pre-fetch input.

Cross-reference siblings:
- **TalibanSquad** (`taliban-ensemble-critic`): adversarial review with constitutional+longinus+solid+lakatos LensSet UNION.
- **BuildAgent** (`build-agent`): consumes APPROVED contracts, runs TDD.
- **FixAgent** (`fix-agent`): consumes BlockerFinding, proposes patches.

# KG: HR2_external_reviewer_2026-05-14, taliban-ensemble-critic, UserPrinciple_SelfCorrecting_APT

---

## §7 Honest limitations

- **Untested as a runtime spec.** This file is a v0.1.0-draft sibling for the APT v28 RFC. No real spawn of DesignAgent has been executed end-to-end. v28 promotion gate requires at least one S2 user-test cycle.
- **σ predicate is auto-flagged HUMAN_REVIEW, not auto-decided.** The σ (semantic completeness) predicate of C(S) is intrinsically human-judgment-bound. DesignAgent marks but cannot resolve. If parent does not surface σ flags to user, the system silently degrades to executor-judges-self (HR2 violation by omission).
- **No sigma-auto-reviewer integration yet.** Dormant seed `seed-apt-fix-sigma-auto-reviewer-2026-04-17` is referenced by parent §4.2 but no implementation here. σ flag is currently a string in `honest_caveats`, not a structured KG escalation.
- **One-shot per Pre-fetch is operationally rigid.** Real decomposition is iterative; the current spec forces parent to re-spawn for each depth level. May produce excessive spawn overhead for deep DAGs (depth > 5). Mitigation: jaebaeman 하노이탑 escalation, but that itself is unimplemented.
- **A3 sibling relaxation is PRELIMINARY.** Parent §4.2 allows sibling cross-talk via INFORMED_BY; DesignAgent emits these links freely. If external Naesengmoon math-lens later rejects the relaxation, all DesignAgent outputs with sibling INFORMED_BY edges become structurally suspect.
- **Schema overlap unresolved.** As parent §4.3 acknowledges, 9-axis Contract v2 ∩ 8 ST Decision Areas ∩ 9-field ST template overlap is not yet subsumed. DesignAgent passes the contradiction through rather than resolving it.
- **Sample-of-one author.** Same agent (Claude) that designed parent /apt v28 also wrote this sibling. No independent design review.

# KG roots: ATOM_Skill_design_agent_v28, APT18_SubagentArchitecture, apt-cw-kg-as-ipc,
#           apt-cw-spawn-sequence, lesson-apt-degenerated-parallel-jaebaeman-2026-05-14
