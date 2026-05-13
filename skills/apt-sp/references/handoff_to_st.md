# SP → ST Handoff (Phase-Specific)

> apt-sp 완료 후 apt-st 진입 *직전* 검증. C(S) 5조건 + APPROVED_BY + links + 분해 미결정 5조건 모두 충족해야 핸드오프 가능.

---

## 5 조건 검증 cypher

```cypher
-- SP → ST Handoff: 모든 조건 검증
MATCH (span:AptSpan {name: $span_name})

// 조건 1: AtomicSpan 라벨
WHERE span:AtomicSpan

// 조건 2: s 승인 (executor != reviewer)
WITH span
MATCH (span)<-[approval:APPROVED_BY {criterion: 'sigma'}]-(reviewer:AptAgent)
WITH span, reviewer, approval
MATCH (span)<-[:EXECUTED_BY]-(executor:AptAgent)
WHERE executor.name <> reviewer.name

// 조건 3: 링크 밀도 (Dense Linking)
WITH span, reviewer, executor
OPTIONAL MATCH (span)-[informed:INFORMED_BY]->()
WITH span, reviewer, executor, count(informed) AS link_count
MATCH (cfg:MethodologyConfig {name:'MethodologyConfig_default_v26'})
WHERE link_count >= cfg.density_min_informed_by

// 조건 4: 미해결 피드백 없음
WITH span, reviewer, executor, link_count
OPTIONAL MATCH (span)<-[:AFFECTS]-(fb:AptFeedback {resolved: false})
WHERE fb IS NULL

// 조건 5: 아직 결정화되지 않음
WITH span, reviewer, executor, link_count
WHERE NOT EXISTS { MATCH (span)-[:CRYSTALLIZES_TO]->() }

RETURN span.name AS span,
       reviewer.name AS approved_by,
       executor.name AS executed_by,
       link_count AS links,
       true AS handoff_ready
```

결과 없으면 핸드오프 차단. 5 조건 중 어떤 게 실패했는지는 각 조건 분리 cypher로 진단.

---

## 추가 검증: Span Boundary

[span_boundary.md](span_boundary.md) 의 V-SP-Boundary 통과 필수:

```cypher
-- V-SP-Boundary-1 추가 체크
MATCH (atom:AtomicSpan {name: $span_name})
WHERE atom.allowed_paths IS NULL OR size(atom.allowed_paths) = 0
RETURN 'V_SP_Boundary_NoAllowedPaths' AS blocked,
       atom.name AS atom
```

---

## Phase Transition Compaction (SP → ST)

[_common/phase_transition_compaction.md](../../_common/phase_transition_compaction.md) 의 SP → ST 표:

| 보존 | 제거 |
|---|---|
| 모든 AtomicSpan name + description | 분해 후보 비교 (어떤 분해를 택했는가의 과정) |
| 각 AtomicSpan의 INFORMED_BY 링크 ≥ N 충족 사실 | RefinementGate 통과 과정 (cypher 출력) |
| C(S) 5 술어 PASS 결과 | EXPLORES_VIA 미선택 대안 |
| s_oracle 승인 사실 (executor != reviewer) | Confluence 감지 과정 |
| Span Boundary (allowed_paths / forbidden_patterns) | 깊은 트리의 중간 노드 detail |

---

## Kafka 이벤트

[_common/kafka_event_convention.md](../../_common/kafka_event_convention.md) 형식:

```json
{
  "event_type": "PhaseHandoff_SP_to_ST",
  "timestamp": "2026-05-11T14:10:00Z",
  "correlation_id": "abc-def-uuid",
  "agent": "agent_sp_01",
  "payload": {
    "anchor": "SA_xxx",
    "atomic_spans": [
      {
        "name": "ATOM_xxx",
        "description": "...",
        "informed_by_count": 7,
        "cs_predicates": {"v":"PASS","t":"PASS","i":"PASS","d":"PASS","s":"PASS"},
        "approved_by": "agent_review_03",
        "executed_by": "agent_sp_01",
        "allowed_paths": ["src/xxx/"],
        "forbidden_patterns": []
      }
    ],
    "next_phase": "apt-st"
  }
}
```

---

## anti-pattern

### E-SP-Handoff-1: silent handoff
**Context:** SP → ST 전환 시 PhaseHandoff_SP_to_ST Kafka 이벤트 미발행.
**Lesson:** ST cold-start 시 어떤 atom들 처리해야 하는지 컨텍스트 손실.
**Guard:** 핸드오프 cypher가 동시에 Kafka producer call.

### E-SP-Handoff-2: PH3 → PH5 직행 (ST 건너뛰기, E1)
**Context:** Span 분해 후 Contract 없이 바로 코딩 진입. ST 단계 건너뜀.
**Lesson:** Contract 없는 코딩 = vibe coding. 타입 불일치와 암묵 가정이 통합 시점에 폭발.
**Guard:** D9 GenerativeFlowOrdering. SCW SKILL.md 시작 시 atom의 Contract 존재 확인:

```cypher
MATCH (span:AptSpan {name: $target})
OPTIONAL MATCH (span)-[:CRYSTALLIZES_TO]->(st)-[:HAS_CONTRACT]->(c)
WITH span, c
WHERE c IS NULL
RETURN 'BLOCKED: No Contract for ' + span.name AS error
```

### E-SP-Handoff-3: 조건 부분 충족
**Context:** 5 조건 중 4개 PASS, 1개 FAIL인데 SP가 "거의 다 됐다" 판단으로 ST 호출.
**Lesson:** AND 의무. 부분 충족 = 미충족.
**Guard:** 핸드오프 cypher가 `handoff_ready = true` 단일 boolean 반환. 5 조건 모두 PASS만 true.

# KG: APT_SP_HandoffToST_canonical
