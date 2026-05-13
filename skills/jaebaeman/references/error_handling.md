# jaebaeman — Error Handling

> Lazy-load reference. Parent: [`../SKILL.md`](../SKILL.md).

## 1. Seed Resolution Failure (G0)

```
IF SubagentTaskSpec missing:
  1. G0.5 New Seed Planting Gate 진입
  2. checkItems / parallelism / fulfillment_gate_cypher / expected_outcome_schema 작성
  3. status='READY' SET
  4. 그 후 cycle 재진입
```

## 2. KG Pre-fetch Skip (JB_MCPInheritanceAssumption)

```
IF subagent 가 MCP server 자동 상속 가정 (GH#13605 violation):
  1. BLOCK
  2. parent 측에서 mcp__neo4j__read_neo4j_cypher 직접 호출
  3. 결과를 seed_bundle.cypher_queries 에 적재
  4. subagent 는 seed_bundle 만 사용 (자체 MCP 사용 안 함)
  5. Lesson JB_MCPInheritanceAssumption
```

## 3. Dispatch Truncation (JB_SelfCheckSkip — GH#29181)

```
IF intent_N != actual_N (dispatch 후):
  1. 누락된 agent_id 식별
  2. seed_bundle 재사용 (idempotent)
  3. 보충 dispatch
  4. 3 attempts 후 fail → partial collection 인정 + sigma_oracle
  5. Lesson JB_SelfCheckSkip 생성
```

## 4. Sequential Dispatch (JB_SequentialDispatch — SUB-OPTIMAL)

```
IF dispatch 가 single-message multi-call 가 아닌 sequential:
  1. WARN (BLOCK 아님 — 작동은 함, 비효율)
  2. dispatch_pattern = 'sequential' KG 기록
  3. Performance metric 추적 (latency 차이)
  4. 다음 cycle 부터 single-message 권장
```

## 5. Inline Provenance (JB_InlineCritic — TR11 violation)

```
IF subagent_count = 0 OR provenance = 'inline':
  1. BLOCK 즉시
  2. subagent 1+ 출격 강제
  3. 새 model 분리 (parent != subagent)
  4. provenance = 'subagent-<skill>-<idx>' 로 변경
  5. Lesson JB_InlineCritic
```

## 6. Cardinality Mismatch (JB_HyperedgeCardinalityMismatch)

```
IF DispatchHyperedge.cardinality != actual VERIFIED_BY edge count:
  1. ROLLBACK transaction
  2. 누락된 ResearchFinding 식별
  3. 보충 결정화 (cardinality 맞춤)
  4. 또는 cardinality 정정 (downgrade)
  5. Lesson JB_HyperedgeCardinalityMismatch
```

## 7. UNWIND Skip (JB_NPlus1Write)

```
IF write 가 loop (각 finding 별 별개 transaction):
  1. WARN (KG 트랜잭션 분산)
  2. 다음 cycle 부터 UNWIND single transaction 패턴
  3. Lesson JB_NPlus1Write
```

## 8. Common Failure Modes

| 증상 | 원인 | 처방 |
|------|------|------|
| subagent 가 MCP 사용 시도 | GH#13605 | parent pre-fetch 강제 |
| intent_N 누락 (self-check 안 함) | GH#29181 | 매 dispatch 후 self-check |
| dedup_hash 모두 null | Step 3.3 skip | hash 강제 |
| cardinality_match = false | Hyperedge 결정화 실패 | retry + 보충 dispatch |
| provenance = 'inline' 시도 | TR11 우회 시도 | BLOCK + escalate |

# KG: ATOM_Skill_jaebaeman, fw-jaebaeman-references-apt-parity-2026-05-06
