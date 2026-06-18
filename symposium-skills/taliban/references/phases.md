# taliban — Phases

> Lazy-load reference. Parent: [`../SKILL.md`](../SKILL.md).

## Adversarial Round Phases

```
[/taliban <target> --lens <set>]
   ↓
Phase 0: Pre-flight + LensSet resolution
Phase 1: Subagent dispatch (재배맨 SOP)
Phase 2: Findings collection (FullFindingRecord)
Phase 3: Coverage calculation (ensemble UNION)
Phase 4: Anti-Rubber-Stamp audit
Phase 5: RTI/FVR enforcement
Phase 6: Verdict decision (5 categories)
Phase 7: ValidationResult crystallization
   ↓
[VR returned to caller]
```

## Phase 0 — Pre-flight

**Inputs**: target, lens_name, parent_model.
**Outputs**: validated input + LensSet resolved + critic_model assigned.
**Gate**: G0 (gates.md §2).

## Phase 1 — Subagent Dispatch

**Pattern**:
```
역할: Naesengmoon critic (agentId=C<idx>)
Target: <kg_node_name>
Lens: <lens_name>
Output: ValidationResult JSON
```

**Invariant**: subagent_count ≥ 1, parent_model != critic_model.

## Phase 2 — Findings Collection

**Schema** (per finding):
```json
{
  "category": "BLOCKER|PERFORMANCE|DESIGN_DEBT|NITPICK",
  "severity": "...",
  "description": "...",
  "evidence": ["..."],
  "ground_truth_testable": true|false,
  "ground_truth_result": "PASS|FAIL|null",
  "suggestion": "..."
}
```

**Invariant**: findings_count ≥ 3 (Anti-Rubber-Stamp #2).

## Phase 3 — Coverage Calculation (v0.8.A1)

```cypher
MATCH (vr)-[:USED_LENS]->(ls)
WITH vr, collect(DISTINCT ls) AS lensets
MATCH (ls2)-[cv:COVERS_CONCERN]->(c)
WHERE ls2 IN lensets
WITH vr, c, max(cv.weight) AS w
RETURN sum(w) / 9.0 AS ensemble_coverage
```

**Invariant**: ensemble_coverage >= 0.8 (default APT_GATE_COVERAGE_THRESHOLD).

## Phase 4 — Anti-Rubber-Stamp Audit

10 technique 검사 (theory.md §4):
1. Model separation
2. Min findings ≥ 3
3. Core assumption challenge
4. Anti-checklist
5. Falsifiability
6. Ground truth cross-check
7. Severity distribution audit
8. Historical finding rate
9. Blind review
10. Rotation

## Phase 5 — RTI/FVR

**RTI**: random attack vector 주입 (security/concurrency/boundary/null/overflow).
**FVR**: consecutive verdict pattern check + forced rotation.

## Phase 6 — Verdict Decision

| Verdict | When |
|---------|------|
| APPROVED | findings ≥ 3, coverage ≥ 0.8, 0 BLOCKER, RTI/FVR pass |
| APPROVED_PENDING_EXTERNAL_D20 | 자체-executor + sigma_oracle consent |
| REJECTED | ≥1 unresolved BLOCKER OR coverage < 0.8 |
| CONDITIONAL_PASS | PERFORMANCE only |
| SUPERSEDED | replaced |

## Phase 7 — VR Crystallization

```cypher
MERGE (vr:ValidationResult {name: $vr_name})
SET vr.verdict = $verdict, vr.evidence = $ev, vr.findings = $findings,
    vr.provenance = 'subagent-taliban-' + $skill, vr.validated_at = datetime()
MERGE (vr)-[:USED_LENS]->(:LensSet {name: $lens})
MERGE (target)<-[:VALIDATES]-(vr)
```

**Invariant**: USED_LENS edge present, evidence non-empty, provenance != 'inline'.

# KG: ATOM_Skill_taliban, fw-taliban-references-apt-parity-2026-05-06
