# taliban — KG Logging

> Lazy-load reference. Parent: [`../SKILL.md`](../SKILL.md).

## 1. ValidationResult (canonical adversarial verdict)

```cypher
MERGE (vr:ValidationResult:AbstractNode {name: 'VR_' + $skill + '_' + $target + '_' + $date})
SET vr.target_phase = $phase, vr.phase = $phase,
    vr.verdict = $verdict,                              // APPROVED|REJECTED|CONDITIONAL_PASS|APPROVED_PENDING_EXTERNAL_D20|SUPERSEDED
    vr.findings = $findings_array,
    vr.findings_count = size($findings_array),
    vr.findings_categories = $categories,
    vr.evidence = $evidence,
    vr.warnings = $warnings,
    vr.critics_dispatched = $critics_n,
    vr.validator = 'Taliban-' + $lens,
    vr.provenance = 'subagent-taliban-' + $skill,        // != 'inline'
    vr.parent_model = $parent_model,
    vr.critic_model = $critic_model,
    vr.validated_at = datetime()
WITH vr
MATCH (ls:LensSet {name: $lens_name})
MERGE (vr)-[:USED_LENS]->(ls)
WITH vr
MATCH (target {name: $target_name})
MERGE (target)<-[:VALIDATES]-(vr)
```

## 2. TalibanFeedback (per finding)

```cypher
MERGE (fb:TalibanFeedback:AbstractNode {name: $finding_id})
SET fb.category = $category,                            // RubberStamp|LensSetIncomplete|...
    fb.severity = $severity,                            // BLOCKER|PERFORMANCE|DESIGN_DEBT|NITPICK
    fb.status = 'open',
    fb.description = $claim,
    fb.evidence = $evidence,
    fb.suggestion = $suggestion,
    fb.ground_truth_testable = $gt_testable,
    fb.ground_truth_result = $gt_result,
    fb.gate_type = $gate,
    fb.lens = $lens_name,
    fb.critic_model = $critic_model,
    fb.created_at = datetime(),
    fb.target_artifact = $target_artifact
MERGE (fb)-[:TARGETS]->(target)
```

## 3. ModeCollapseLog

```cypher
CREATE (mc:ModeCollapseLog {
  signal: $signal,                                       // 'NITPICK_only_5_rounds'|'always_3_findings'|...
  rounds_observed: $rounds,
  action_taken: $action,                                 // 'rotate_critic'|'escalate'|'block'
  detected_at: datetime()
})
```

## 4. AdversarialRoundCompleted Event

```cypher
CREATE (e:AdversarialRoundCompleted {
  gate: $gate,
  span_or_target: $target,
  critic_model: $critic_model,
  parent_model: $parent_model,
  findings_count: $findings_n,
  blockers: $blocker_n,
  performance: $perf_n,
  design_debt: $debt_n,
  nitpick: $nitpick_n,
  ground_truth_overrides: $gt_overrides,
  verdict: $verdict,
  ensemble_coverage_score: $coverage,                   // v0.8.A1
  timestamp: datetime()
})
```

## 5. Audit Queries

```cypher
// Open feedback by severity
MATCH (fb:TalibanFeedback) WHERE fb.status = 'open'
RETURN fb.severity, count(fb), collect(fb.name)[0..5]
ORDER BY CASE fb.severity WHEN 'BLOCKER' THEN 0 WHEN 'PERFORMANCE' THEN 1 WHEN 'DESIGN_DEBT' THEN 2 ELSE 3 END

// Mode collapse history
MATCH (mc:ModeCollapseLog) WHERE mc.detected_at >= datetime() - duration('P30D')
RETURN mc.signal, count(mc), collect(mc.action_taken)
```

# KG: ATOM_Skill_taliban, fw-taliban-references-apt-parity-2026-05-06
