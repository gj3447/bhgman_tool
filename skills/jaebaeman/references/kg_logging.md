# jaebaeman — KG Logging

> Lazy-load reference. Parent: [`../SKILL.md`](../SKILL.md).

## 1. SubagentTaskSpec (seed canonical)

```cypher
MERGE (ts:SubagentTaskSpec:AbstractNode {name: $name})
SET ts.skill = $skill, ts.phase = $phase, ts.displayName = $display,
    ts.checkItems = $checks,                          // [{name, query, expected}, ...]
    ts.parallelism_min = $par_min, ts.parallelism_max = $par_max,
    ts.treasure_coverage_min = 0.9,
    ts.fulfillment_gate_cypher = $gate_cypher,
    ts.expected_outcome_schema = $schema,             // FullFindingRecord schema
    ts.cypherQueries = $queries,                      // KG pre-fetch queries
    ts.status = 'READY', ts.created_at = datetime()
```

## 2. DispatchHyperedge (parent-side reification)

```cypher
MERGE (he:DispatchHyperedge:AbstractNode {name: 'hyperedge-' + $cycle_id})
SET he.cycle_id = $cycle_id,
    he.skill = $skill, he.phase = $phase,
    he.cardinality = $intent_N,
    he.actual_subagents = $actual_N,
    he.cardinality_match = ($intent_N = $actual_N),
    he.dispatch_pattern = 'single-message-multi-call',  // SUB-OPTIMAL if 'sequential'
    he.parent_model = $parent_model,
    he.subagent_type = $subagent_type,                  // 'taliban-ensemble-critic'|'prometheus-expert'|...
    he.created_at = datetime()
WITH he
UNWIND $finding_names AS fn
MATCH (rf:ResearchFinding {name: fn})
MERGE (rf)-[:GENERATED_VIA]->(he)
```

## 3. SeedBundleAudit

```cypher
CREATE (sba:SeedBundleAudit {
  cycle_id: $cycle_id,
  agent_id: $agent_id,
  fields_present: $fields,                            // ["agent_id","task_spec_name",...]
  fields_count: size($fields),
  schema_valid: ($fields_count = 9),
  parent_intent: $intent,
  audited_at: datetime()
})
```

## 4. SOPViolationLog (anti-pattern 검출)

```cypher
CREATE (v:SOPViolationLog {
  pattern: $jb_code,                                  // JB_InlineCritic|JB_MCPInheritanceAssumption|...
  cycle_id: $cycle_id,
  evidence: $evidence,
  severity: $severity,
  resolution: $resolution,
  detected_at: datetime()
})
```

## 5. ProvenanceChain (W3C PROV)

```cypher
MERGE (act:prov_Activity {name: $cycle_id})
SET act.label = 'jaebaeman-cycle-' + $skill + '-' + $phase,
    act.startedAtTime = datetime($start),
    act.endedAtTime = datetime($end)
WITH act
UNWIND $rf_names AS rf_name
MATCH (rf:ResearchFinding {name: rf_name})
MERGE (rf)-[:wasGeneratedBy]->(act)
WITH act
MATCH (parent_agent:prov_Agent {name: 'parent-claude'})
MERGE (act)-[:wasAssociatedWith]->(parent_agent)
```

## 6. Audit Queries

```cypher
// Cycle 별 cardinality_match
MATCH (he:DispatchHyperedge) WHERE he.created_at >= datetime() - duration('P7D')
RETURN he.skill, he.phase, he.cardinality_match, count(he)

// SOP violation 빈도
MATCH (v:SOPViolationLog) WHERE v.detected_at >= datetime() - duration('P30D')
RETURN v.pattern, count(v) ORDER BY count(v) DESC
```

# KG: ATOM_Skill_jaebaeman, fw-jaebaeman-references-apt-parity-2026-05-06
