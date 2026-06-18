# tpa — Validation

> **Lazy-load reference for `tpa` skill.**
> Parent skill: [`../SKILL.md`](../SKILL.md). Mirror reference: [`../../apt/references/validation.md`](../../apt/references/validation.md).
> KG: `tpa-hardening-master-plan-2026-05-06`.

---

## 1. Validation Suite (V1-V20 — TPA-localized)

TPA reuses APT's validation pattern but targets the *recovered* artifacts instead of authored ones.

### 1.1 Phase Order Checks (P1 — Critical)

| V# | Target | What It Checks | Severity |
|----|--------|---------------|:--------:|
| V1 | TR3 PhaseOrder | Every `:TPA_Execution` only progresses TCW → ST → SP → TA | P1 |
| V2 | TR1 AdversarialMandatory | Every phase transition has VR with `:USED_LENS->(:LensSet)` | P1 |
| V3 | TR11 ExecutorReviewerSeparation | VR.executor != VR.reviewer; no inline subagent-less VR | P1 |
| V4 | TR2 EvidenceRequired | Every APPROVED VR has non-empty `evidence` array | P1 |

### 1.2 Recovery Quality Checks (P2)

| V# | Target | What It Checks | Severity |
|----|--------|---------------|:--------:|
| V5 | Manifest completeness | union(agent_files) == manifest_files (TR5) | P2 |
| V6 | AST parser used | every TCW Result has `parsed_with` field set (not "grep") | P2 |
| V7 | Convention discrimination | no node has both `:AptContract` AND `:ConventionalContract` labels | P2 |
| V8 | Pattern checklist | every INSTANCE_OF has `checklist_pass=true` AND `evidence` set | P2 |

### 1.3 Anchor Drift Checks (P2-P3)

| V# | Target | What It Checks | Severity |
|----|--------|---------------|:--------:|
| V9 | Coverage threshold | TA Result with `coverage_ratio < 0.8` has anchor.status='SUSPENDED' | P2 |
| V10 | Drift kinds enumeration | TA records all 5 drift kinds (Missing/Orphan/SigMismatch/PatternDiv/LabelRot) | P3 |
| V11 | Longinus binding | every recovered Contract has `:ReferenceSite` with sourcePath | P2 |

### 1.4 Lesson Feedback Checks (P3)

| V# | Target | What It Checks | Severity |
|----|--------|---------------|:--------:|
| V12 | Lesson on discovery (TR10) | every QualityGap / AntiPattern → has matching `:Lesson` | P3 |
| V13 | ActionPlan link | unresolved Lesson with `severity ≥ HIGH` has TRIGGERS edge to ActionPlan | P3 |
| V14 | Resolved provenance | Lesson with `resolved=true` has `resolved_at` AND `evidence` AND `resolved_by` | P3 |

### 1.5 Adversarial Validation (V27-V29 mirror)

| V# | Target | What It Checks | Severity |
|----|--------|---------------|:--------:|
| V27 | TPA Source Density | TCW manifest count >= configured minimum per repo size class | P1 |
| V28 | Adversarial Round Completion | Every TPA gate transition has a VR with USED_LENS edge | P1 |
| V29 | Ground Truth Primacy | parser output / `wc -l` ground truth matches recovered counts | P1 |

---

## 2. V28 Cypher (Adversarial Round Completion)

```cypher
// V28: Every TPA phase transition must have an adversarial round VR
MATCH (s:TPA_TCW_Result|TPA_ST_Result|TPA_SP_Result|TPA_TA_Result)
WHERE NOT EXISTS {
  MATCH (s)<-[:VALIDATES|TARGETS]-(vr:ValidationResult)-[:USED_LENS]->(:LensSet)
}
RETURN s.name AS recovered_artifact_missing_adversarial,
       labels(s)[0] AS phase,
       'TR1 VIOLATION: gate output without adversarial round' AS reason
```

---

## 3. V29 Cypher (Ground Truth Primacy)

```cypher
// V29: Recovered counts must match parser ground truth
MATCH (tcw:TPA_TCW_Result)
WHERE tcw.symbol_count IS NOT NULL
  AND tcw.parser_symbol_count IS NOT NULL
  AND tcw.symbol_count <> tcw.parser_symbol_count
RETURN tcw.name AS execution,
       tcw.symbol_count AS recovered,
       tcw.parser_symbol_count AS ground_truth,
       'TR4 VIOLATION: AST count mismatch — manual extraction suspected' AS reason
```

---

## 4. Quick Health Check

Run V1, V2, V3, V4, V11, V28, V29 (all P1-P2). These are the minimum invariants for any TPA cycle to be considered well-formed.

---

## 5. Events

| Event | Payload | When |
|-------|---------|------|
| TPA_PhaseEntered | `{exec, phase, target}` | Each `/tpa-*` invocation |
| TPA_PhaseGatePassed | `{exec, phase, vr, lensSet, lensCount}` | After Naesengmoon gate VR APPROVED |
| TPA_DriftMeasured | `{anchor, coverage_ratio, drift_table}` | TA Phase 4 finalization |
| TPA_LessonCreated | `{lesson, category, severity, target_anchor}` | Discovery on any phase (TR10) |
| TPA_ActionPlanLinked | `{lesson, action_plan, priority}` | Manual or auto-suggest after TA |
| TPA_LessonResolved | `{lesson, resolved_by, evidence}` | After APT /apt-scw + Naesengmoon gate |

---

## 6. Project-Specific Invariants

Each TargetAnchor may carry domain invariants:
```cypher
MATCH (sa:SemanticAnchor {name: $anchor})-[:HAS_INVARIANT]->(inv)
RETURN inv.name, inv.description, inv.check_query
```

These are inherited by APT going forward (the recovered anchor merges with APT's SemanticAnchor identity).

---

## 7. Clarifications

| # | Clarification |
|---|--------------|
| TC1 | TPA recovery is *lossy by theorem*. `confidence` < 1.0 is normal, not bug. |
| TC2 | Skipping TR15 (acknowledging Essential ✗) = false confidence in recovered design. |
| TC3 | A TPA cycle with `lessons_count = 0` is suspect — re-run with deeper Naesengmoon prompts. |
| TC4 | INSTANCE_OF without checklist_pass = pattern hallucination. Auto-blocked since v1.1. |
| TC5 | Distributed pattern recognized but no SP-MetaVerify VR = name-only match (fake CRDT). |
| TC6 | TA suspending an anchor (`status='SUSPENDED'`) is *protective*, not failure. |
| TC7 | sigma_oracle is HUMAN even in `auto_approve_surface: true` mode. |
| TC8 | KG state is canonical. Conversation memory is volatile. (Same as APT.) |

---
