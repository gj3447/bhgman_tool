# prometheus — Phases

> Lazy-load reference. Parent: [`../SKILL.md`](../SKILL.md). Sibling: [`./gates.md`](./gates.md), [`./theory.md`](./theory.md).

## 9+1 Step Cycle (Hegel Spiral)

```
[/prom <N> <topic>]
   ↓
Step 0: KG Pre-fetch (parent-side, MCP 우회 GH#13605)
Step 1: Axis Matrix Template — axis × sub_axis × N seed
Step 2: 사전 지식 scan (KG + filesystem dispersion)
Step 2.5: KG Pre-fetch verification gate
Step 3: Subagent Dispatch (haiku N parallel, max 100)
Step 3.3: Dedup detection (FullFindingRecord)
Step 4: Lakatos distinguishability test (4-criterion)
Step 5: UNWIND batch write (single transaction)
Step 6: Filesystem dispersion sub-step (KG↔fs drift 차단)
Step 6.5: Dispersion gate G6.5
Step 7: Lesson + ResearchFinding 결정화 (W3C PROV)
Step 7.5: Cycle terminal — feedback loop fires
```

## Step 0 — KG Pre-fetch

**책무**: parent Claude 가 모든 관련 KG 데이터 직접 조회 → seed_bundle.cypher_queries 에 적재.

**Why**: GH#13605 — subagent MCP 비상속. 부모만 mcp__neo4j__read_neo4j_cypher 사용 가능.

**Output**:
- `kg_context = {prior_findings, related_concepts, open_lessons, methodology_config}`
- `prior_findings_count`
- `axis_candidate_concepts`

## Step 1 — Axis Matrix

**책무**: topic 을 N axis × N sub_axis 매트릭스로 분해.

**Output**:
```cypher
MERGE (m:AxisMatrix {name: 'axis-matrix-' + $cycle_id})
SET m.axes = $axes,                         // ["axis1", ...]
    m.sub_axes = $sub_axes,                 // {"axis1": ["sub1", ...]}
    m.treasure_coverage_min = 0.9
```

## Step 2-2.5 — Knowledge Scan

**책무**:
- 기존 ResearchFinding 검색 (axis/sub_axis match)
- filesystem dispersion 사전 검사
- KG↔fs drift 진단

**Output**: `prior_knowledge_ratio`, `dispersion_drift_count`.

## Step 3 — Subagent Dispatch

**책무**: single-message multi-call 패턴으로 N 개 subagent 동시 spawn.

**Pattern**:
```python
# 모두 같은 message:
[Agent(subagent_type='prometheus-expert', prompt=sb) for sb in seed_bundles]
```

**Output**: N FullFindingRecord JSON.

## Step 3.3 — Dedup Detection

```cypher
UNWIND $findings AS f
MATCH (rf:ResearchFinding {dedup_hash: f.dedup_hash})
RETURN rf, count(*) AS dup_count
```

**책무**: 같은 axis/sub_axis 의 중복 finding 검출.

## Step 4 — Lakatos Test

`lakatos-progressive-vs-rescue-test-canonical-2026-05-06` 4-criterion 적용.

**Verdict**:
- 4/4 PASS → PROGRESSIVE
- < 4 → DEGENERATING

## Step 5 — UNWIND Batch Write

**Pattern** (single transaction):
```cypher
UNWIND $batch AS row
MERGE (rf:ResearchFinding {name: row.name})
SET rf += row.props
MERGE (rf)-[:VERIFIED_BY]->(:LakatosTest {name: $test})
```

**Anti-pattern**: loop write (N+1) — BLOCK.

## Step 6 — Filesystem Dispersion

**책무**: 모든 새 ResearchFinding 의 canonical_doc_path 가 실제 file:
- 존재 확인
- SHA256 hash 일치
- line_range valid

## Step 6.5 — Dispersion Gate

**책무**: KG↔fs drift = 0 보장. 위반 시 BLOCK.

KG: `rfc-prom-filesystem-dispersion-2026-04-29`.

## Step 7 — Lesson Crystallization

**책무**: 모든 발견을 :Lesson 으로:
- wrongAssumption ↔ truth pair (mandatory)
- INSTANCE_OF_FEEDBACK_LOOP edge
- W3C PROV provenance

## Step 7.5 — Cycle Terminal

**책무**: feedback loop 발동:
- ActionPlan 자동 stub (severity HIGH lesson)
- WorkBuffer ARCHIVED → next_buffer CURRENT

## Phase Detection Auto-Route

```cypher
MATCH (c:PrometheusCycle {name: $cycle_id})
OPTIONAL MATCH (c)-[:USED_MATRIX]->(m:AxisMatrix)
OPTIONAL MATCH (c)<-[:GENERATED_FROM]-(rf:ResearchFinding)
OPTIONAL MATCH (rf)-[:VERIFIED_BY]->(lt:LakatosTest)
RETURN c.name,
  CASE
    WHEN lt IS NOT NULL AND count(rf) > 0 THEN 'COMPLETE'
    WHEN count(rf) > 0 THEN 'Step 4: Lakatos'
    WHEN m IS NOT NULL THEN 'Step 3: Dispatch'
    WHEN c IS NOT NULL THEN 'Step 1: Axis Matrix'
    ELSE 'Step 0: KG Pre-fetch'
  END AS current_step
```

# KG: ATOM_Skill_prometheus, fw-prometheus-references-apt-parity-2026-05-06
