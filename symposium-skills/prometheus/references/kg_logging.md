# prometheus — KG Logging

> Lazy-load reference. Parent: [`../SKILL.md`](../SKILL.md). Sibling: [`./gates.md`](./gates.md).

## 1. PrometheusCycle (cycle 단위 정전)

```cypher
MERGE (c:PrometheusCycle:AbstractNode {name: 'prom-' + $cycle_id})
SET c.topic = $topic, c.N = $n, c.size_class = $size,
    c.started_at = datetime(), c.parent_user = $user
```

## 2. AxisMatrix

```cypher
MERGE (m:AxisMatrix {name: 'axis-matrix-' + $cycle_id})
SET m.cycle_id = $cycle_id, m.axes = $axes, m.sub_axes = $sub_axes,
    m.treasure_coverage_min = 0.9, m.created_at = datetime()
MERGE (c:PrometheusCycle {name:'prom-'+$cycle_id})-[:USED_MATRIX]->(m)
```

## 3. ResearchFinding (FullFindingRecord)

```cypher
UNWIND $findings AS f
MERGE (rf:ResearchFinding:AbstractNode {dedup_hash: f.dedup_hash})
ON CREATE SET rf += f, rf.created_at = datetime(),
              rf.created_by = 'parent-prometheus'
ON MATCH SET rf.collision_count = coalesce(rf.collision_count, 0) + 1,
             rf.collision_evidence = coalesce(rf.collision_evidence, []) + [f.agent_id]
WITH rf
MATCH (c:PrometheusCycle {name:'prom-'+$cycle_id})
MERGE (rf)-[:GENERATED_FROM]->(c)
```

## 4. LakatosTest (Step 4 verdict)

```cypher
MERGE (lt:LakatosTest:AbstractNode {name: 'lakatos-' + $cycle_id})
SET lt.criteria_pass = $criteria,             // {theory_laden:true, ...}
    lt.criteria_count = size(keys($criteria)),
    lt.criteria_pass_count = $pass_count,
    lt.verdict = $verdict,                     // PROGRESSIVE | DEGENERATING
    lt.basis = 'lakatos-progressive-vs-rescue-test-canonical-2026-05-06',
    lt.tested_at = datetime()
WITH lt
MATCH (rf:ResearchFinding) WHERE rf.cycle_id = $cycle_id
MERGE (rf)-[:VERIFIED_BY]->(lt)
```

## 5. DispatchHyperedge (Step 5 cardinality match)

```cypher
MERGE (he:DispatchHyperedge:AbstractNode {name: 'hyperedge-' + $cycle_id})
SET he.cycle_id = $cycle_id, he.cardinality = $intent_N,
    he.actual_subagents = $actual_N,
    he.cardinality_match = ($intent_N = $actual_N),
    he.created_at = datetime()
```

## 6. Lesson (Step 7 — wrongAssumption ↔ truth pair mandatory)

```cypher
MERGE (l:Lesson:AbstractNode {name: 'lesson-prom-' + $finding + '-' + $date})
SET l.scope = 'prom-' + $cycle_id,
    l.problem = $problem,
    l.wrongAssumption = $wrong,                // mandatory
    l.truth = $truth,                          // mandatory
    l.howToApply = $how,
    l.evidence = $ev,
    l.severity = $severity,
    l.resolved = false,
    l.created_at = datetime()
WITH l
MATCH (fl:FeedbackLoopOntology {name: 'agent-feedback-loop-canonical-2026-04-27'})
MERGE (l)-[:INSTANCE_OF_FEEDBACK_LOOP]->(fl)
```

## 7. Override Logging (KG-skip with hot-fix justification)

```cypher
CREATE (ol:PrometheusDecisionLog {
  id: randomUUID(),
  decision: 'KG_SKIP',
  reason: $human_reason,                       // mandatory, agent-generated 금지
  cycle_id: $cycle_id,
  hot_fix_latency_critical: true,
  decided_at: datetime()
})
```

## 8. Audit Queries

```cypher
// 최근 Cycle 의 PROGRESSIVE / DEGENERATING 비율
MATCH (lt:LakatosTest) WHERE lt.tested_at >= datetime() - duration('P30D')
RETURN lt.verdict, count(lt)

// 미해결 Lesson by severity
MATCH (l:Lesson) WHERE l.scope STARTS WITH 'prom-' AND l.resolved = false
RETURN l.severity, count(l), collect(l.name)[0..5]
ORDER BY CASE l.severity WHEN 'BLOCKER' THEN 0 WHEN 'HIGH' THEN 1 WHEN 'MEDIUM' THEN 2 ELSE 3 END
```

# KG: ATOM_Skill_prometheus, fw-prometheus-references-apt-parity-2026-05-06
