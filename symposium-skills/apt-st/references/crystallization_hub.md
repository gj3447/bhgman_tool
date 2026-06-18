# CrystallizationEvent Hub (Phase-Specific)

> AtomicSpan → SemanticTwin 결정화 시점에 *hub-and-spoke* 노드 생성. 4 role 동시 연결.

---

## Hub-and-Spoke

```
                    +------------------------+
                    | CrystallizationEvent    |
                    | name: CE_Q1_Transfer    |
                    +----------+--------------+
                               |
        +----------+-----------+-----------+----------+
   INVOLVES{  INVOLVES{   INVOLVES{   INVOLVES{  INVOLVES{
    'atom'}    'twin'}     'task'}   'contract'}  'source'}
        |          |           |           |          |
        v          v           v           v          v
   AtomicSpan  Semantic    Semantic    AptContract  SourceCode
                Twin         Task                    Node (PH5)
```

4 mandatory role (ST 종료 시): atom / twin / task / contract.
1 optional role (SCW 완료 시 추가): source.

---

## 생성 cypher

```cypher
MATCH (atom:AtomicSpan {name: $atom_name})
MATCH (twin:SemanticTwin {name: $twin_name})
MATCH (task:SemanticTask {name: $task_name})
MATCH (ct:AptContract {name: $contract_name})
MERGE (cx:CrystallizationEvent {name: 'CE_' + $cycle_id + '_' + atom.name})
SET cx.created_at = datetime(),
    cx.cycle_id = $cycle_id,
    cx.actor = $agent
MERGE (cx)-[:INVOLVES {role: 'atom'}]->(atom)
MERGE (cx)-[:INVOLVES {role: 'twin'}]->(twin)
MERGE (cx)-[:INVOLVES {role: 'task'}]->(task)
MERGE (cx)-[:INVOLVES {role: 'contract'}]->(ct)
MERGE (atom)-[:CRYSTALLIZES_TO]->(twin)
MERGE (twin)-[:HAS_TASK]->(task)
MERGE (twin)-[:HAS_CONTRACT]->(ct)
RETURN cx, atom, twin, task, ct
```

SCW 완료 시 source role 추가:

```cypher
MATCH (cx:CrystallizationEvent {name: $cx_name})
MATCH (src:SourceCodeNode {name: $src_name})
MERGE (cx)-[:INVOLVES {role: 'source'}]->(src)
```

---

## 검증 query

```cypher
-- V14: Hub must have at least atom role
MATCH (cx:CrystallizationEvent)
WHERE NOT (cx)-[:INVOLVES {role: 'atom'}]->()
RETURN 'V14_HUB_INCOMPLETE' AS validation, cx.name

-- V14-Extended: Hub should have all 4 roles (before PH5)
MATCH (cx:CrystallizationEvent)
WHERE NOT (cx)-[:INVOLVES {role: 'atom'}]->()
   OR NOT (cx)-[:INVOLVES {role: 'twin'}]->()
   OR NOT (cx)-[:INVOLVES {role: 'task'}]->()
   OR NOT (cx)-[:INVOLVES {role: 'contract'}]->()
RETURN 'V14_HUB_MISSING_ROLE' AS validation, cx.name,
       size((cx)-[:INVOLVES]->()) AS role_count

-- Consistency: Every CRYSTALLIZES_TO must have a hub
MATCH (a:AtomicSpan)-[:CRYSTALLIZES_TO]->(t:SemanticTwin)
WHERE NOT EXISTS {
  MATCH (cx:CrystallizationEvent)-[:INVOLVES {role: 'atom'}]->(a)
  WHERE (cx)-[:INVOLVES {role: 'twin'}]->(t)
}
RETURN 'V14_CONSISTENCY_VIOLATION' AS validation, a.name, t.name
```

---

## hub의 가치

1. **추적성**: atom → twin → task → contract → source 모든 단계 시간 stamp + actor 기록.
2. **rollback**: amendment 시 어떤 atom 단계로 돌아갈지 명확.
3. **drift 탐지**: atom과 contract 사이 의미 drift 시 hub의 cycle_id로 시간 비교.
4. **multi-cycle**: 같은 atom이 여러 cycle에서 결정화될 때 각 hub가 분리되어 history 보존.

---

## anti-pattern

### E-ST-Hub-1: hub 누락
**Context:** CRYSTALLIZES_TO 엣지만 만들고 CrystallizationEvent 안 만듦.
**Lesson:** 추적성 깨짐. SCW에서 어느 contract 만족했는지 cypher 한 번에 못 찾음.
**Guard:** V14_CONSISTENCY_VIOLATION cypher. 발견 시 즉시 hub 생성 cypher 실행.

### E-ST-Hub-2: role 부분 누락
**Context:** atom + twin만 연결, task/contract 연결 안 함.
**Lesson:** ST 종료 시점에 4 role 모두 mandatory. 1개라도 누락 = Twin lifecycle 미완료.
**Guard:** V14_HUB_MISSING_ROLE cypher가 차단.

# KG: APT_ST_CrystallizationHub_canonical
