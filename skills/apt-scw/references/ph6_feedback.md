# PH6 Feedback Detail (Phase-Specific)

> SCW 구현 중 발견된 gap/violation을 SP/ST로 피드백. 6 Discovery Type × 10 Category 분류.

---

## 6 Discovery Types

| # | Type | 설명 | Action | Target |
|---|---|---|---|:-:|
| 1 | **missing_span** | 전체 의미 관심사가 분해에서 누락 발견. 예: rate limiting Span 없음. | AptFeedback, 부모 Span에 link, PH3에서 형제 Span 분해 | PH3 |
| 2 | **contract_gap** | Contract 형식적 올바르지만 불완전. 유효 입력 케이스 postcondition 미커버. | PH4 복귀, Contract 수정, acceptance_criteria 추가. Kafka: ContractAmended | PH4 |
| 3 | **type_mismatch** | 실 데이터 흐름이 선언 타입과 불일치. 다운스트림 전파 필요. | 원본 + 다운스트림 Contract 수정. Kafka: ContractAmended for each | PH4 |
| 4 | **edge_case** | acceptance_criteria에 미예상 특정 시나리오 (구조적 누락 아닌 특정 데이터). | acceptance_criteria에 추가, 테스트 작성, 재구현. 재분해 불필요 | PH4 |
| 5 | **false_positive** | 테스트 FAIL인데 구현 옳음. 테스트 기대값 잘못 (도메인 오해). | 도메인 지식 기반 assertion 조정. INFORMED_BY 링크. 명세 오류이지 구현 오류 아님 | PH4 |
| 6 | **accuracy_drift** | 확률적 메트릭이 시간/환경에 따라 저하. | PH3 수준에서 Span 범위 재평가. EXPLORES_VIA 대안? NFR 임계값 비현실적? | PH3 |

---

## 10 Categories

| # | Category | 설명 | Severity |
|---|---|---|:-:|
| 1 | **Bug** | 코드 결함. postcondition 위반 | P1-P2 |
| 2 | **Confusion** | 명세 모호성. 해석 분기 | P3 |
| 3 | **Missing** | 누락된 Span/Contract/테스트 | P2-P3 |
| 4 | **Improvement** | 기능 개선 요청 (현재 동작 정상) | P3-P4 |
| 5 | **Violation** | Axiom 또는 Principle 위반 | P1-P2 |
| 6 | **Conflict** | 두 Contract/Span 간 모순 | P2-P3 |
| 7 | **FalsePositive** | 검증이 정상을 위반으로 오탐 | P3 |
| 8 | **FalseNegative** | 검증이 위반을 정상으로 미탐 | P2 |
| 9 | **PerformanceDrift** | 성능 메트릭 기준선 이하 하락. NFR 재교정 | P2-P3 |
| 10 | **SLABreach** | SLA 초과. 응답 시간/처리량 위반 | P1-P2 |

---

## AptFeedback Cypher

```cypher
CREATE (fb:AptFeedback {
  name:           'FB_' + $project + '_' + $id,
  discovery_type: $type,          -- 6 types 중 하나
  category:       $category,      -- 10 categories 중 하나
  description:    $description,
  source_phase:   'PH5',
  target_phase:   $target,        -- 'PH3' or 'PH4'
  severity:       $severity,      -- 'blocking' | 'degraded' | 'cosmetic'
  status:         'open',
  created_at:     datetime(),
  created_by:     $agent
})
WITH fb
MATCH (span:AptSpan {name: $affected_span})
MERGE (fb)-[:AFFECTS]->(span)
```

Kafka event: `FeedbackCreated` ([_common/kafka_event_convention.md](../../_common/kafka_event_convention.md))

---

## 라우팅

```
discovery_type: missing_span | accuracy_drift
  → PH3 (SP 재분해)
  → 새 Span 생성 → ST → 돌아오기

discovery_type: contract_gap | type_mismatch | edge_case | false_positive
  → PH4 (ST Contract 수정)
  → Contract 수정 → 테스트 재작성 → 돌아오기
```

---

## anti-pattern

### E-SCW-PH6-1: Silent Patch (AP4)
**Context:** 코드 변경만, AptFeedback 미생성.
**Lesson:** 다른 에이전트가 옛 Contract 기준으로 코딩 → 충돌.
**Guard:** SCW 코드 변경 cypher가 AptFeedback 생성 강제.

### E-SCW-PH6-2: category 잘못 분류
**Context:** 명세 모호성 (Confusion) 인데 Bug로 분류 → 코드 수정.
**Lesson:** Confusion은 명세 명확화로 해결, 코드 수정 아님.
**Guard:** category 분류 시 description 키워드 검증. 모호함 시 인간 확인.

# KG: APT_SCW_PH6Feedback_canonical
