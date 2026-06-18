# tpa — KG Logging

> **Lazy-load reference for `tpa` skill.**
> Parent skill: [`../SKILL.md`](../SKILL.md). Mirror reference: [`../../apt/references/kg_logging.md`](../../apt/references/kg_logging.md).
> KG: `tpa-hardening-master-plan-2026-05-06`.

---

## 1. TpaDecisionLog (Every Gate Transition — TR7)

```cypher
CREATE (dl:TpaDecisionLog {
  id: randomUUID(),
  gate_type: $gate_type,
  exec_name: $exec_name,
  target_phase: $phase,
  decision: $decision,
  decided_by: $decided_by,
  decided_at: datetime(),
  adversarial_verdict: $adversarial_verdict,
  adversarial_findings_count: $findings_count,
  adversarial_blockers: $blocker_count,
  ground_truth_pass: $ground_truth_pass,
  ground_truth_details: $ground_truth_details,
  evidence_summary: $evidence_summary,
  override_reason: $override_reason,
  coverage_ratio: $coverage_ratio    // for TA gate only
})
WITH dl
MATCH (exec:TPA_Execution {name: $exec_name})
MERGE (dl)-[:TARGETS]->(exec)
RETURN dl.id, dl.gate_type, dl.decision
```

**gate_type values**: `TCW_Gate`, `ST_Gate`, `SP_Gate`, `SP_MetaVerify_Gate`, `TA_Gate`, `Drift_Audit`, `Lesson_Loop`

**decision values**: `PASS`, `RETURN`, `ESCALATE`, `BLOCKED`, `OVERRIDE`, `SUSPENDED`

---

## 2. TpaFeedback (Every Adversarial Finding)

```cypher
MERGE (fb:TpaFeedback {name: $finding_id})
SET fb.category = $category,        // see §6 categories
    fb.severity = $severity,        // BLOCKER | PERFORMANCE | DESIGN_DEBT | NITPICK
    fb.status = 'open',
    fb.description = $claim,
    fb.evidence = $evidence,
    fb.suggestion = $suggestion,
    fb.ground_truth_testable = $ground_truth_testable,
    fb.ground_truth_result = $ground_truth_result,
    fb.gate_type = $gate_type,
    fb.critic_model = $critic_model,
    fb.created_at = datetime(),
    fb.created_by = 'tpa-adversarial-critic',
    fb.target_phase = $target_phase,
    fb.target_artifact = $target_artifact   // TPA_TCW_Result | TPA_ST_Result | TPA_SP_Result | TPA_TA_Result | DesignPattern | Contract
WITH fb
OPTIONAL MATCH (a) WHERE a.name = $target_artifact
FOREACH (_ IN CASE WHEN a IS NOT NULL THEN [1] ELSE [] END |
  MERGE (fb)-[:TARGETS]->(a)
)
RETURN fb.name, fb.severity, fb.status
```

---

## 3. Lesson (TR10 — Auto on Discovery)

```cypher
MERGE (l:Lesson:AbstractNode {name: 'lesson-tpa-' + $finding + '-' + $date})
SET l.category = $category,                 // see §6 lesson categories
    l.scope = 'tpa-' + $phase + '-' + $target,
    l.problem = $problem,
    l.wrongAssumption = $wrong_assumption,  // mandatory pair (TR10 + agent feedback ontology)
    l.truth = $truth,                       // mandatory pair
    l.howToApply = $how_to_apply,
    l.evidence = $evidence,
    l.severity = $severity,
    l.resolved = false,
    l.created_at = datetime(),
    l.target_anchor = $anchor
WITH l
MATCH (fl:FeedbackLoopOntology {name: 'agent-feedback-loop-canonical-2026-04-27'})
MERGE (l)-[:INSTANCE_OF_FEEDBACK_LOOP]->(fl)
RETURN l.name
```

`wrongAssumption` ↔ `truth` symmetric pair is mandatory per CLAUDE.md feedback ontology rule. A Lesson with only one side = incomplete.

---

## 4. ActionPlan (TR10 — Lesson → improvement)

```cypher
MERGE (p:ActionPlan {name: 'AP-' + $lesson_name})
SET p.priority = $priority,                 // HIGH | MEDIUM | LOW
    p.improvements = $improvements,         // ["change X to Y", "add Z assertion", ...]
    p.target_skill = 'apt-scw',             // typical: APT SCW for materialization
    p.created_at = datetime(),
    p.expected_completion = $eta,
    p.auto_generated = $auto                // true if generated from stale Lesson sweep
WITH p
MATCH (l:Lesson {name: $lesson_name})
MERGE (l)-[:TRIGGERS]->(p)
RETURN p.name
```

---

## 5. Discovery Templates

```cypher
// (a) Similarity — recovered pattern matches another project
MERGE (sim:Similarity {name: 'sim-' + $name})
SET sim.source_project = $source,
    sim.target_project = $target,
    sim.pattern = $pattern,
    sim.confidence = $conf,
    sim.source_evidence = $src_path,
    sim.target_evidence = $tgt_path
MERGE (analysis)-[:IDENTIFIES]->(sim)

// (b) QualityGap — target is better in some dimension
MERGE (gap:QualityGap {name: 'gap-' + $name})
SET gap.dimension = $dim,
    gap.source_level = $src_level,
    gap.target_level = $tgt_level,
    gap.improvement_action = $action
MERGE (analysis)-[:IDENTIFIES]->(gap)
MERGE (gap)-[:TRIGGERS]->(:Lesson {name: 'lesson-tpa-' + $name})

// (c) NovelPattern — only in target, not in our Pattern Library
MERGE (np:NovelPattern {name: 'NP_' + $name})
SET np.description = $desc,
    np.applicability = $app,
    np.first_observed_in = $target
MERGE (analysis)-[:IDENTIFIES]->(np)

// (d) AntiPattern — should NOT replicate
MERGE (ap:AntiPattern {name: 'AP_' + $name})
SET ap.description = $desc,
    ap.consequence = $con,
    ap.alternative = $alt
MERGE (analysis)-[:IDENTIFIES]->(ap)
```

---

## 6. Categories

### 6.1 TpaFeedback Categories

| # | Category | When to Use |
|---|----------|-------------|
| 1 | ManifestSkip | Files missing from union vs manifest (TR5 violation) |
| 2 | ParserMismatch | AST count vs `wc -l` divergence (TR4 violation) |
| 3 | OntologyPollution | Apt/Conventional contract label mixing |
| 4 | PatternHallucination | INSTANCE_OF without checklist evidence |
| 5 | DistributedNameOnly | Distributed pattern without SP-MetaVerify VR |
| 6 | DriftUnreported | 5-drift kind with non-zero count not surfaced |
| 7 | LongiusBindingMissing | Recovered Contract without ReferenceSite |
| 8 | LessonGap | Discovery happened but no Lesson logged (TR10) |
| 9 | StaleLesson | Lesson resolved=false age > 7 days, no ActionPlan |
| 10 | RecoveryMetaFailure | Both critic and recovery agents converged wrong |

### 6.2 Lesson Categories

| Category | Domain |
|----------|--------|
| `tpa-tcw-*` | TCW phase findings |
| `tpa-st-*` | ST contract extraction |
| `tpa-sp-*` | SP pattern matching |
| `tpa-ta-*` | TA anchor / drift |
| `tpa-cross-project` | Similarity / QualityGap between projects |
| `tpa-pattern-library` | DesignPattern Library defects |
| `tpa-methodology` | TPA itself improvement |

---

## 7. Audit Trail Queries

```cypher
// Full audit for one TPA_Execution
MATCH (dl:TpaDecisionLog)-[:TARGETS]->(exec:TPA_Execution {name: $exec_name})
RETURN dl.gate_type, dl.target_phase, dl.decision, dl.decided_by, dl.decided_at,
       dl.adversarial_verdict, dl.adversarial_findings_count,
       dl.adversarial_blockers, dl.ground_truth_pass, dl.coverage_ratio,
       dl.override_reason
ORDER BY dl.decided_at ASC
```

```cypher
// Open Lessons by severity
MATCH (l:Lesson) WHERE l.resolved = false AND l.scope STARTS WITH 'tpa-'
RETURN l.severity, l.category, count(l) AS open, collect(l.name)[0..5] AS sample
ORDER BY
  CASE l.severity
    WHEN 'BLOCKER' THEN 0
    WHEN 'HIGH' THEN 1
    WHEN 'MEDIUM' THEN 2
    WHEN 'LOW' THEN 3
  END
```

```cypher
// Lesson resolution rate (last 30 days)
MATCH (l:Lesson) WHERE l.scope STARTS WITH 'tpa-' AND l.created_at >= datetime() - duration('P30D')
WITH l.resolved AS resolved, count(l) AS n
RETURN resolved, n, n * 1.0 / sum(n) OVER () AS rate
```

```cypher
// ActionPlan throughput
MATCH (l:Lesson)-[:TRIGGERS]->(p:ActionPlan)
WHERE l.resolved = true
RETURN p.target_skill, count(p) AS resolved_plans,
       avg(duration.between(l.created_at, l.resolved_at).days) AS avg_resolution_days
ORDER BY resolved_plans DESC
```

---

## 8. Override Logging

If user explicitly overrides a TPA gate (e.g. `coverage_ratio = 0.65` accepted):

```cypher
CREATE (ol:TpaDecisionLog {
  id: randomUUID(),
  gate_type: 'TA_Gate',
  exec_name: $exec,
  decision: 'OVERRIDE',
  decided_by: 'human',
  decided_at: datetime(),
  override_reason: $human_reason,                  // MUST come from human, not agent
  overridden_rule: 'tpa_drift_coverage_ratio_min',
  original_coverage_ratio: 0.65,
  policy_threshold: 0.8
})
```

`override_reason` MUST come from the human. Agent generating it = TC4 violation (anti-rubber-stamp) and INSTANCE_OF hallucination class extension.

---

## 9. Resolve Lesson

```cypher
MATCH (l:Lesson {name: $lesson_name})
SET l.resolved = true,
    l.resolved_at = datetime(),
    l.resolved_by = $agent,
    l.resolution = $resolution,
    l.evidence = $evidence              // commit hash / VR id / artifact reference
RETURN l.name, l.resolved, l.evidence
```

V14: Lesson resolved=true without evidence field → BLOCKED. The evidence is what makes "resolved" verifiable.

---
