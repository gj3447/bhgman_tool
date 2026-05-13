# jaebaeman — Gates

> Lazy-load reference. Parent: [`../SKILL.md`](../SKILL.md). Sibling: [`./theory.md`](./theory.md).
> KG: `재배맨-v2-subagent-runtime-protocol`, `jaebaeman-grounding-2026-05-05`.

---

## 1. SOP 4-Stage Gate Sequence

```
[parent Claude — multi-agent dispatch decision]
   ↓
G0: Seed Resolution  — SubagentTaskSpec 조회
   ↓
G1: KG Pre-fetch  — MCP 우회 (GH#13605)
   ↓
G2: Seed Bundle Construction  — 9-field schema
   ↓
G3: Single-Message Multi-Call Dispatch  — N parallel Agent
   ↓
G4: Self-Check  — intent_N == actual_N (GH#29181)
   ↓
G5: Collect  — JSON harvest + schema validation
   ↓
G6: Dedup Detection  — Step 3.3
   ↓
G7: UNWIND Batch Write  — single Cypher transaction
   ↓
G8: Hyperedge Reification  — DispatchHyperedge cardinality match
   ↓
[Subagents 종료, parent 만 살아남음]
```

---

## 2. G0 Seed Resolution Gate

```cypher
MATCH (ts:SubagentTaskSpec)
WHERE ts.skill = $skill AND ts.phase = $phase
RETURN ts.checkItems, ts.parallelism_min, ts.treasure_coverage_min,
       ts.fulfillment_gate_cypher, ts.expected_outcome_schema, ts.cypherQueries
```

**Required**:
- `:SubagentTaskSpec` 노드 존재
- `checkItems` non-empty
- `parallelism_min` set
- `treasure_coverage_min >= 0.9`

**On fail**:
- TaskSpec 부재 → BLOCK + new seed 심기 의무 (G0.5)
- treasure_coverage < 0.9 → escalate

---

## 3. G0.5 New Seed Planting Gate

```cypher
MERGE (ts:SubagentTaskSpec:AbstractNode {name: $name})
SET ts.skill = $skill,
    ts.phase = $phase,
    ts.displayName = $display,
    ts.checkItems = $checks,                  // [{name, query, expected}, ...]
    ts.parallelism_min = $par_min,
    ts.parallelism_max = $par_max,
    ts.treasure_coverage_min = 0.9,
    ts.fulfillment_gate_cypher = $gate_cypher,
    ts.expected_outcome_schema = $schema,
    ts.status = 'READY',
    ts.created_at = datetime()
```

**Required**:
- 모든 필드 채워짐 (특히 `expected_outcome_schema`)
- `parallelism_min >= 1`
- `checkItems` ≥ 1

---

## 4. G1 KG Pre-fetch Gate (MCP 우회 — GH#13605)

```
1. parent Claude 가 mcp__neo4j__read_neo4j_cypher 직접 호출
2. 결과를 seed_bundle.kg_context 에 적재
3. subagent 는 seed_bundle 만 받음 (MCP 자동 상속 X)
```

**Required**:
- KG context 가 seed bundle 에 포함
- subagent 가 자체 MCP 사용 안 함 가정 (MCP 비상속)
- pre-fetch 결과 cache hit ratio 확인

**On fail**:
- pre-fetch 누락 → subagent 가 빈 KG 컨텍스트로 시작 → BLOCK
- MCP 자동 상속 가정 → BLOCK + GH#13605 violation

KG: `lesson-jaebaeman-mcp-noninheritance-2026-04-15`.

---

## 5. G2 Seed Bundle 9-Field Construction Gate

```yaml
seed_bundle:
  agent_id: "D<idx>"                         # mandatory
  task_spec_name: "taskspec-<skill>-<phase>" # mandatory
  axis: "<axis>"                              # for prom-style dispatch
  sub_axis: "<sub>"                           # for prom-style dispatch
  parent_intent: "<intent>"                   # mandatory
  cypher_queries: [...]                       # KG pre-fetch results
  expected_outcome: "<schema>"                # mandatory
  treasure_coverage_min: 0.9
  provenance: "재배맨-<skill>-<idx>"        # mandatory
```

**Required**: 9 fields all present (axis/sub_axis는 prom-style 만 mandatory).

**On fail**: BLOCK + seed_bundle schema validation error.

---

## 6. G3 Single-Message Multi-Call Dispatch Gate

**Required**:
- 모든 Agent tool call 이 *same message* 안에 (parallel spawn)
- N <= 100 (max parallel cap)
- `subagent_type` 명시 (default `taliban-ensemble-critic`, `prometheus-expert`, etc.)
- model 분리 (parent != subagent — bias 전염 차단)

**Pattern**:
```python
# pseudo:
[
  Agent(subagent_type=type, prompt=seed_bundle[0], ...),
  Agent(subagent_type=type, prompt=seed_bundle[1], ...),
  ...
]  # all in single message — parallel
```

**On fail**:
- sequential dispatch (다른 message 들로 쪼갬) → SUB-OPTIMAL warning
- N > 100 → chunk dispatch (재배맨 nested)

---

## 7. G4 Self-Check Gate (GH#29181)

```python
intent_N = len(seed_bundle_list)
results = await all_subagents()
actual_N = len(results)
assert intent_N == actual_N, f"truncation detected: {intent_N} → {actual_N}"
```

**Required**:
- `intent_N == actual_N` (count match)
- 각 subagent 의 result 가 valid JSON
- 누락된 subagent → re-dispatch (idempotent)

**On fail**:
- `intent_N > actual_N` → BLOCK + Lesson `lesson-jaebaeman-dispatch-truncation`
- partial collection → 누락된 axis 의 보충 dispatch

---

## 8. G5 Collect Gate (FullFindingRecord schema)

**Required schema**:
```json
{
  "agent_id": "D<idx>",
  "task_spec_name": "...",
  "axis": "...",
  "sub_axis": "...",
  "claim": "...",
  "evidence": ["..."],
  "confidence": 0.0-1.0,
  "ground_truth_testable": true|false,
  "ground_truth_result": "PASS|FAIL|null",
  "verified": false,
  "provenance": "재배맨-<skill>-<idx>",
  "dedup_hash": "<sha256>"
}
```

**On fail**:
- schema invalid → reject single result (cycle 진행)
- evidence empty → finding rejection
- provenance != "재배맨-..." → BLOCK + provenance forgery 의심

---

## 9. G6 Dedup Detection Gate (Step 3.3)

```cypher
UNWIND $findings AS f
MATCH (rf:ResearchFinding {dedup_hash: f.dedup_hash})
RETURN rf.name AS existing, count(*) AS dup_count
```

**Required**:
- 모든 finding 에 `dedup_hash` (sha256 of canonicalized claim)
- 충돌 (다른 axis/sub_axis 같은 hash) 표시
- 기존 finding 보강 vs 새 finding 결정

**On fail**: hash 누락 → finding rejection.

---

## 10. G7 UNWIND Batch Write Gate

**Required**:
- single Cypher transaction
- N+1 anti-pattern 차단 (loop write 금지)
- W3C PROV provenance edge

```cypher
UNWIND $batch AS row
MERGE (rf:ResearchFinding {name: row.name})
SET rf += row.props,
    rf.created_at = datetime(),
    rf.created_by = 'parent-claude'
MERGE (rf)-[:GENERATED_VIA]->(:DispatchHyperedge {name: $hyperedge})
MERGE (rf)-[:wasGeneratedBy]->(:prov_Activity {name: $cycle_id})
```

**On fail**: ROLLBACK + Cypher syntax 진단.

---

## 11. G8 Hyperedge Reification Gate

```cypher
MERGE (he:DispatchHyperedge:AbstractNode {name: 'hyperedge-' + $cycle_id})
SET he.cycle_id = $cycle_id,
    he.cardinality = $intent_N,                      // intent count
    he.actual_subagents = $actual_N,                 // collected count
    he.cardinality_match = ($intent_N = $actual_N),
    he.created_at = datetime()
WITH he, $finding_names AS names
UNWIND names AS fn
MATCH (rf:ResearchFinding {name: fn})
MERGE (rf)-[:GENERATED_VIA]->(he)
WITH he
MATCH (he)<-[:GENERATED_VIA]-(rf:ResearchFinding)
WITH he, count(rf) AS edges
WHERE edges = he.cardinality
RETURN he.name, edges, he.cardinality_match
```

**Required**:
- `he.cardinality_match = true`
- `count(VERIFIED_BY) == cardinality` (referential integrity)

**On fail**: cardinality mismatch → ROLLBACK + 누락된 subagent 검색.

---

## 12. Approval Gate Roles

| Gate | Who | SLA | On Timeout |
|------|-----|-----|-----------|
| Seed Resolution | automated | < 5s | BLOCK + new seed 의무 |
| KG Pre-fetch | automated (parent) | < 30s | BLOCK + Neo4j 진단 |
| Seed Bundle | automated (parent) | < 5s | BLOCK + schema validation |
| Dispatch | automated (Agent tool) | varies | BLOCK + GH#29181 self-check |
| Collect | automated (parent) | < 60s | partial collection + 보충 dispatch |
| Batch Write | automated | < 30s | ROLLBACK |
| sigma_oracle | HUMAN | 0 | BLOCK — re-ask (필요 시) |

---

## 13. Anti-Patterns Detection

| # | Anti-pattern | 검출 |
|---|--------------|------|
| JB_InlineCritic | parent 자체에서 critic 작업 | G3 subagent_count check |
| JB_MCPInheritanceAssumption | subagent 가 MCP 자동 상속 가정 | G1 pre-fetch 누락 |
| JB_SelfCheckSkip | post-dispatch verification 없음 | G4 intent vs actual |
| JB_DedupSkipped | Step 3.3 dedup detection 없음 | G6 hash null |
| JB_InlineProvenance | VR.provenance='inline' | schema check |
| JB_SequentialDispatch | parallel 가 아닌 loop dispatch | G3 message structure |
| JB_HyperedgeCardinalityMismatch | cardinality != actual edges | G8 |
| JB_NPlus1Write | UNWIND 안 쓰고 loop write | G7 transaction count |

---

## 14. Holacracy Archetype Mapping

각 stage 가 Holacracy role 1:1 mirror — specialized agent 가 책임:

| Stage | Holacracy Role | Specialized Agent |
|-------|----------------|-------------------|
| G0-G2 | Facilitator | `facilitator` agent |
| G3-G4 | Lead Link | `lead_link` agent |
| G5-G6 | Rep Link | `rep_link` agent |
| G7-G8 | Secretary | `secretary` agent |

---

## 15. References

- theory: `./theory.md`
- skill: `../SKILL.md`
- archetype agents: `../../.claude/agents/{facilitator, lead_link, rep_link, secretary}.md`
- KG: `재배맨-v2-subagent-runtime-protocol`, `MIC_v1.SubagentSeeder` slot, `lesson-jaebaeman-mcp-noninheritance-2026-04-15`, `lesson-jaebaeman-rebrand-SOP-2026-05-05`

# KG: ATOM_Skill_jaebaeman, fw-jaebaeman-references-apt-parity-2026-05-06
