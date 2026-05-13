# prometheus — Gates

> Lazy-load reference. Parent: [`../SKILL.md`](../SKILL.md). Sibling: [`./theory.md`](./theory.md).
> KG: `prometheus-grounding-2026-05-05`, `rfc-prom-filesystem-dispersion-2026-04-29`.

---

## 1. Cycle Gates Sequence

각 transition 은 정확한 gate 통과 필수. 건너뛰면 BLOCK.

```
[/prom <N> <topic>]
   ↓
G0: Pre-flight  — KG 접근 가능 + N 결정 + topic 분해 가능
   ↓
G1: KG Pre-fetch (Step 0)  — MCP 우회 (GH#13605), parent context 적재
   ↓
G2: Axis Matrix (Step 1)   — axis × sub-axis 매트릭스 N seed 생성
   ↓
G3: Knowledge Scan (Step 2-2.5)  — 사전 지식 + dispersion check
   ↓
G4: Dispatch (Step 3)  — single-message N parallel Agent calls
   ↓
G5: Collect+Dedup (Step 3.3)  — FullFindingRecord schema + dedup_hash
   ↓
G6: Lakatos (Step 4)   — 4-criterion distinguishability test
   ↓
G6.5: Filesystem Dispersion (Step 6)  — KG↔fs invariants
   ↓
G7: Batch Write (Step 5)  — UNWIND single transaction
   ↓
G7.5: Lesson Crystallization (Step 7)  — W3C PROV provenance
   ↓
[CYCLE TERMINAL — feedback loop fires]
```

---

## 2. G0 Pre-flight

**Required**:
- `MATCH (n) RETURN count(n)` 가 응답 (KG 접근)
- N 값 결정 (small=4 / medium=8 / large=16 / TOE=64-100)
- topic 이 axis 분해 가능 (단일 명사 = REJECT)
- `MethodologyConfig.prometheus_N_default_*` slot resolve OK

**On fail**: BLOCK + sigma_oracle escalate.

---

## 3. G1 KG Pre-fetch (parent-side, MCP 우회)

```cypher
// 1. 기존 ResearchFinding 조회
MATCH (rf:ResearchFinding) WHERE rf.topic CONTAINS $topic
RETURN rf.name, rf.axis, rf.sub_axis, rf.confidence, rf.created_at LIMIT 30

// 2. axis 후보 검색
MATCH (concept:Concept|Theory|Pattern)-[:RELATED_TO]->(t {name: $topic})
RETURN concept LIMIT 50

// 3. 미해결 :Lesson 확인
MATCH (l:Lesson) WHERE l.scope CONTAINS $topic AND l.resolved = false
RETURN l.name, l.problem, l.severity
```

GH#13605 (MCP 비상속): subagent는 MCP server 자동 상속 못함. 부모 측에서 pre-fetch 후 seed_bundle 에 주입.

**On fail**: BLOCK + Neo4j 연결 진단 (`server-status` skill).

---

## 4. G2 Axis Matrix Gate

**Required**:
- N axis × N sub-axis = N total seed
- 각 cell 에 distinct check_query 정의
- treasure_coverage_min ≥ 0.9 (사이트 커버리지)
- `prov_Activity` provenance 노드 생성

```cypher
MERGE (m:AxisMatrix:AbstractNode {name: 'axis-matrix-' + $cycle_id})
SET m.cycle_id = $cycle_id,
    m.topic = $topic,
    m.N = $n,
    m.axes = $axes,                         // ["axis1", "axis2", ...]
    m.sub_axes = $sub_axes,                 // {"axis1": ["sub1", ...], ...}
    m.treasure_coverage_min = 0.9,
    m.created_at = datetime()
```

---

## 5. G3 Knowledge Scan + Dispersion Pre-Check (G6.5 mirror)

```
1. 기존 ResearchFinding 검색 (axis/sub_axis match)
2. filesystem 측 자료 (.md / .pdf / docs) 분산 검사
3. KG↔fs drift 사전 진단 (canonical_doc_path 검증)
4. axis 별 사전 지식 ratio 계산 (>0.5 면 dedup risk 높음)
```

**On fail**:
- KG-fs drift > 10% → Step 6.5 dispersion gate 예약
- 사전 지식 부족 → 첫 dispatch 우선
- 사전 지식 과다 → dispatch 안 함, KG-only verdict

---

## 6. G4 Dispatch Gate (Single-Message Multi-Call invariant)

**Required**:
- `single message multiple Agent tool blocks` 패턴 (parallel spawn)
- 각 Agent call 에 seed_bundle 9-field 주입
- `intent_N == actual_N` self-check (GH#29181)
- model = haiku (default; sonnet for complex axis)
- max parallel = 100

```python
# pseudo-code
intent_N = len(seed_bundle_list)
# single message:
[Agent(...) for sb in seed_bundle_list]
actual_N = await all_complete()
assert intent_N == actual_N  # GH#29181
```

**On fail**:
- `intent_N != actual_N` → BLOCK + Lesson `lesson-prom-dispatch-truncation`
- seed_bundle 9-field 누락 → BLOCK before dispatch
- max parallel 초과 → chunk dispatch (재배맨 nested)

---

## 7. G5 Collect+Dedup Gate

**Required**:
- 모든 subagent 가 FullFindingRecord JSON 반환
- schema validation (axis / sub_axis / claim / evidence / confidence / ground_truth_testable)
- dedup_hash 계산 (sha256 of canonicalized claim)
- 충돌 감지 (같은 axis/sub_axis 다른 claim → conflict 표시)

```cypher
UNWIND $findings AS f
MERGE (rf:ResearchFinding {dedup_hash: f.dedup_hash})
ON CREATE SET rf += f
ON MATCH SET rf.collision_count = coalesce(rf.collision_count, 0) + 1,
             rf.collision_evidence = coalesce(rf.collision_evidence, []) + [f.agent_id]
```

**On fail**: schema invalid → reject single finding (전체 cycle 은 진행).

---

## 8. G6 Lakatos Distinguishability Test (Step 4)

`lakatos-progressive-vs-rescue-test-canonical-2026-05-06` — 4 criterion all PASS:

| Test | 통과 기준 |
|------|----------|
| theory_laden_anomaly | findings 가 기존 가설을 reframe 하는가? |
| independent_testable_consequence | 새 가설이 독립 검증 가능한 testable consequence 생산? |
| excess_empirical_content | 기존 보다 more 예측력 있는가? |
| principled_grounding_in_hard_core | hard-core invariant 에 근거? (rescue 가설 = degenerating) |

**Verdict**:
- 4/4 PASS → PROGRESSIVE — Step 5 batch write 진행
- < 4/4 → DEGENERATING / rescue → Lesson + revisit

---

## 9. G6.5 Filesystem Dispersion Gate (v6 신규)

```
1. 모든 새 ResearchFinding 의 canonical_doc_path 확인
2. 실제 파일 존재 검증 (Read or Glob)
3. SHA256 hash 계산 + KG sha256_hash 필드 검증
4. line_range 가 실제 line count 안에 fall
5. KG↔fs bi-directional drift = 0
```

**On fail**:
- canonical_doc_path 부재 → 빈 파일 생성 with TODO + Lesson
- SHA256 mismatch → KG 갱신 OR file revert (sigma_oracle 결정)
- line_range 초과 → 자동 truncate + Lesson

KG: `rfc-prom-filesystem-dispersion-2026-04-29`.

---

## 10. G7 Batch Write Gate (Step 5)

**Required**:
- single Cypher transaction (UNWIND batch)
- N+1 anti-pattern 차단 (loop write 금지)
- Hyperedge reification (DispatchHyperedge 노드 + cardinality match)
- W3C PROV provenance (`prov:wasGeneratedBy`, `prov:wasAttributedTo`)

```cypher
UNWIND $batch AS row
MERGE (rf:ResearchFinding {name: row.name})
SET rf += row.props
MERGE (rf)-[:VERIFIED_BY]->(:LakatosTest {name: $test_name})
MERGE (rf)-[:GENERATED_VIA]->(:DispatchHyperedge {name: $hyperedge_name})
```

**On fail**: cardinality mismatch (DispatchHyperedge.cardinality != actual VERIFIED_BY count) → ROLLBACK.

---

## 11. G7.5 Lesson Crystallization Gate (Step 7)

```cypher
MERGE (l:Lesson:AbstractNode {name: 'lesson-prom-' + $finding + '-' + $date})
SET l.scope = $cycle_id,
    l.problem = $problem,
    l.wrongAssumption = $wrong,
    l.truth = $truth,
    l.howToApply = $how,
    l.evidence = $ev,
    l.severity = $severity,
    l.resolved = false,
    l.created_at = datetime()
WITH l
MATCH (fl:FeedbackLoopOntology {name: 'agent-feedback-loop-canonical-2026-04-27'})
MERGE (l)-[:INSTANCE_OF_FEEDBACK_LOOP]->(fl)
```

**Required**:
- wrongAssumption ↔ truth pair complete (한쪽만 = incomplete)
- evidence non-empty
- INSTANCE_OF_FEEDBACK_LOOP edge

---

## 12. Approval Gate Roles

| Gate | Who | SLA | On Timeout |
|------|-----|-----|-----------|
| Pre-flight | automated | < 10s | BLOCK + escalate |
| KG Pre-fetch | automated | < 30s | BLOCK + Neo4j 진단 |
| Axis Matrix | automated | < 60s (LLM gen) | BLOCK + topic 재분해 요청 |
| Dispatch | automated (재배맨) | varies (per agent < 90s) | partial collection + GH#29181 self-check |
| Lakatos | automated | < 120s | DEGENERATING verdict 자동 |
| Dispersion | automated | < 60s | fail-soft warning OR fail-closed (env flag) |
| Batch Write | automated | < 30s | ROLLBACK + Cypher syntax 진단 |
| sigma_oracle | HUMAN | 0 | BLOCK — re-ask |

---

## 13. Hot-Fix Latency-Critical Exception (v6.1)

CLAUDE.md autoloop / cost guard 측 incident 같은 latency-critical 상황:

```
IF cycle_purpose = 'hot-fix' AND latency_critical = true:
  1. KG-skip allowed (G1 G6.5 skip)
  2. Immediate action 수행
  3. POST-HOC Lesson 생성 의무 (skipped reason + invariants 재검증 plan)
  4. Next cycle 의 G1 에서 추가 audit
```

KG: `prom-grounding-2026-05-05` (Hegel reframe — Begriff 자가운동 paralysis 회피).

---

## 14. Anti-Patterns Detection

| # | Anti-pattern | 검출 |
|---|--------------|------|
| PR_AxisIncompleteness | matrix N 미달 | G2 dimension count check |
| PR_DedupSkipped | dedup_hash 미생성 | G5 hash field null check |
| PR_DispersionGateBypass | G6.5 skip without justification | post-hoc audit |
| PR_KGSkipWithoutJustification | hot-fix 아닌데 G1 skip | cycle log audit |
| PR_DispatchTruncation | intent_N != actual_N | GH#29181 self-check |
| PR_LessonPairIncomplete | wrongAssumption ↔ truth 한쪽만 | G7.5 schema check |
| PR_NUndersampling | N < default for problem size | initial N 결정 audit |

→ G7.5 후 :PrometheusErrorPattern 결정화 sprint 로 별도 처리.

---

## 15. References

- theory: `./theory.md`
- skill: `../SKILL.md`
- sibling: `../taliban/references/gates.md` (gate role 보완)
- KG: `lakatos-progressive-vs-rescue-test-canonical-2026-05-06`, `rfc-prom-filesystem-dispersion-2026-04-29`, `MIC_v1.SubagentSeeder` slot

# KG: ATOM_Skill_prometheus, fw-prometheus-references-apt-parity-2026-05-06
