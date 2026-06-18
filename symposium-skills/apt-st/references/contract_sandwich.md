# Contract Sandwich (Phase-Specific)

> 여러 Twin이 *동일 Contract*를 공유하는 N:1 패턴. 같은 인터페이스 구현 시.

---

## 사용 시점

- **Use when**: 같은 adapter가 여러 모듈에 사용, shared utility, identical typed spec.
- **NOT when**: 다른 pre/postconditions, 다른 NFR, 다른 semantic_meaning.

---

## 적용 cypher

```cypher
MATCH (ct:AptContract {name: $shared_contract})
MATCH (twin1:SemanticTwin {name: $twin1}), (twin2:SemanticTwin {name: $twin2})
MERGE (twin1)-[:HAS_CONTRACT]->(ct)
MERGE (twin2)-[:HAS_CONTRACT]->(ct)
```

HAS_CONTRACT를 1:1에서 N:1로 완화. hub notes에 공유 이유 기록.

---

## 예시

```
CT_DBPort_Read (shared)
  ↑                ↑
  | HAS_CONTRACT   | HAS_CONTRACT
  |                |
TwinUserService   TwinOrderService
```

UserService와 OrderService 모두 *같은* DBPort.Read 인터페이스 구현. Contract 1개, Twin 2개.

---

## 변형 시 분리

Contract 진화 시 Twin마다 요구사항이 달라지면 분리:

```cypher
// 분리: TwinOrderService만 다른 NFR 필요 (예: 더 빠른 latency)
MATCH (twin:SemanticTwin {name:'TwinOrderService'})-[r:HAS_CONTRACT]->(shared:AptContract)
MERGE (specific:AptContract {name: shared.name + '_OrderVariant'})
SET specific.input_type = shared.input_type,
    specific.output_type = shared.output_type,
    specific.precondition = shared.precondition,
    specific.postcondition = shared.postcondition,
    specific.semantic_meaning = shared.semantic_meaning + ' (Order variant — stricter latency)',
    specific.nfr_latency_p99_ms = 20,  -- shared는 50
    specific.parent_contract = shared.name,
    specific.created_at = datetime()
DELETE r
MERGE (twin)-[:HAS_CONTRACT]->(specific)
MERGE (specific)-[:DERIVED_FROM]->(shared)
```

---

## 검증 query

```cypher
-- V-ST-Sandwich-1: 공유 Contract인데 Twin 간 NFR 요구 다름 (분리 누락)
MATCH (twin1:SemanticTwin)-[:HAS_CONTRACT]->(ct:AptContract)<-[:HAS_CONTRACT]-(twin2:SemanticTwin)
WHERE twin1.name < twin2.name
  AND twin1.nfr_latency_p99_ms IS NOT NULL
  AND twin2.nfr_latency_p99_ms IS NOT NULL
  AND twin1.nfr_latency_p99_ms <> twin2.nfr_latency_p99_ms
RETURN 'V_ST_Sandwich_NFRDivergence' AS validation,
       ct.name AS shared_contract,
       twin1.name, twin1.nfr_latency_p99_ms,
       twin2.name, twin2.nfr_latency_p99_ms
```

---

## anti-pattern

### E-ST-Sandwich-1: 무리한 공유
**Context:** 두 Twin이 처음엔 비슷한 요구사항이라 Contract 공유했는데 시간 지나 한쪽이 더 엄격한 NFR 필요.
**Lesson:** 진화 시점에 즉시 분리 필요. 안 하면 Contract 갱신이 다른 Twin에 영향.
**Guard:** V-ST-Sandwich-1 cypher 주기 실행. 발견 시 derived Contract 생성 cypher.

### E-ST-Sandwich-2: 서로 다른 semantic_meaning
**Context:** 두 Twin이 같은 input/output이지만 *의미*가 다른데 공유.
**Lesson:** Contract = type + 의미. semantic_meaning 다르면 다른 Contract.
**Guard:** Contract Sandwich 적용 전 두 Twin의 semantic_meaning 비교. 다르면 거부.

# KG: APT_ST_ContractSandwich_canonical
