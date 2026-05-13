# SEQUENCED_WITH Composition (Phase-Specific)

> Contract 간 *순차 구성*. Hoare triple 체이닝. entailment 검증 필수.

---

## Hoare Triple Chaining

```
{P1} f1: A→B {Q1},  {P2} f2: B→C {Q2},  Q1 entails P2
=> {P1} f2∘f1: A→C {Q2}
```

### Entailment 3 조건 (ALL required)

1. **Type compatibility**: `k1.output_type` matches `k2.input_type`
2. **Postcondition coverage**: `k1.postcondition` implies `k2.precondition`
3. **Integration test**: k1→k2 sequence 실행 후 k2 postcondition 검증

---

## Non-Linear Patterns

### Branching (OK/NG)

```
k1 --{condition: 'output.status==OK'}--> k2_ok
k1 --{condition: 'output.status==NG'}--> k2_ng
```

양쪽 브랜치 모두 reachable 필수. Postcondition에 status 필드 포함.

### Parallel (Fan-out/Fan-in)

```
k1 --> k2a --+--> k3 (join, input = product type)
k1 --> k2b --+
```

### Feedback Loop

```
k1 --> k2 --{converged}--> k3
       k2 --{!converged}--> k1   // 종료 보장 mandatory
```

Loop는 **종료 가능성 증명 의무** (A2 termination).

---

## NOT Categorical Composition

| Property | Category Theory | APT |
|---|---|---|
| Identity | Required | Not required |
| Associativity | Proven | Not proven |
| Verification | Type-level proof | Runtime test + manual entailment |

실용적 파이프라인 검증. 추상 대수 아님.

---

## 파이프라인 예시

### Linear: E-Commerce Order

```
CT_ValidateCart {CartItems → ValidatedCart}
  | SEQUENCED_WITH
CT_ProcessPayment {ValidatedCart → PaymentResult}
  | SEQUENCED_WITH
CT_CreateOrder {PaymentResult → Order}
```

### Branching: Payment Check

```
CT_ProcessPayment {output: PaymentResult}
  +-- {status == 'approved'} --> CT_CreateOrder (OK)
  +-- {status == 'declined'} --> CT_NotifyUser (NG)
```

### Parallel: Data Enrichment

```
CT_FetchUserProfile {-> UserProfile}     --+
                                            +--> CT_PersonalizeResults
CT_FetchOrderHistory {-> list[Order]}    --+    {(profile, history) -> Recommendations}
```

### Feedback: Retry Pattern

```
CT_SendEmail
  +-- {delivered or attempts>=3} --> CT_LogResult
  +-- {failed and attempts<3} --> CT_SendEmail (retry, max 3)
```

---

## SEQUENCED_WITH 적재 cypher

```cypher
MATCH (k1:AptContract {name: $upstream}), (k2:AptContract {name: $downstream})
MERGE (k1)-[r:SEQUENCED_WITH]->(k2)
SET r.entailment = $entailment,         -- "k1.post(X) entails k2.pre(Y)"
    r.condition = $condition,            -- branching condition or null
    r.parallel_group = $group,           -- parallel 시 fan-in 그룹
    r.feedback_termination = $term_proof,-- feedback 시 종료 증명
    r.verified_at = datetime()
RETURN k1.name, type(r), k2.name
```

---

## 검증 query

```cypher
-- V-ST-SEQ-1: entailment 누락
MATCH ()-[r:SEQUENCED_WITH]->()
WHERE r.entailment IS NULL OR r.entailment = ''
RETURN 'V_ST_SEQ_NoEntailment' AS validation, startNode(r).name, endNode(r).name

-- V-ST-SEQ-2: type 불일치
MATCH (k1:AptContract)-[r:SEQUENCED_WITH]->(k2:AptContract)
WHERE k1.output_type <> k2.input_type
RETURN 'V_ST_SEQ_TypeMismatch' AS validation,
       k1.name, k1.output_type, k2.name, k2.input_type

-- V-ST-SEQ-3: feedback loop 종료 증명 누락
MATCH (k:AptContract)-[r:SEQUENCED_WITH]->(k)
WHERE r.feedback_termination IS NULL
RETURN 'V_ST_SEQ_NoTerminationProof' AS validation, k.name
```

---

## anti-pattern

### E-ST-SEQ-1: silent entailment
**Context:** SEQUENCED_WITH 엣지 생성 시 entailment 빈 문자열. type만 match 확인.
**Lesson:** type match는 필요조건이지 충분조건 아님. postcondition이 precondition을 implies해야 함.
**Guard:** V-ST-SEQ-1 cypher. entailment 필드 mandatory.

### E-ST-SEQ-2: branching 한쪽만
**Context:** OK branch만 정의, NG branch 누락. 실패 케이스 처리 안 됨.
**Lesson:** postcondition에 status 필드 있으면 양쪽 branch mandatory.
**Guard:** ST SKILL.md SEQUENCED_WITH 생성 cypher가 branching 시 양쪽 cypher 동시 실행.

### E-ST-SEQ-3: feedback 무한 루프
**Context:** retry pattern인데 attempts 카운터 없음. 영구 반복 가능.
**Lesson:** feedback loop = 종료 증명 의무. A2 termination invariant.
**Guard:** V-ST-SEQ-3 cypher + Contract 본문에 `attempts < N` 조건 명시.

# KG: APT_ST_SequencedWith_canonical
