# Amendment Scenarios (Phase-Specific)

> Contract Lifecycle FSM의 Fulfilled → Amended 트리거 사례. 일반 FSM은 [_common/contract_lifecycle_fsm.md](../../_common/contract_lifecycle_fsm.md).

---

## 1. Regression from Downstream

```
T1: CT_UserProfile fulfilled
T2: CT_UserAuth amended (token format changed)
T3: Integration test fails
T4: CT_UserProfile → Amended
```

Kafka:

```json
{
  "event_type": "ContractAmended",
  "payload": {
    "contract": "CT_UserProfile_Create",
    "reason": "regression_from_CT_UserAuth_Login_v2",
    "triggered_by": "downstream_change",
    "downstream_contract": "CT_UserAuth_Login"
  }
}
```

---

## 2. New Requirement

```
T1: CT_ParseArgs fulfilled
T2: 새 요구: "support --verbose flag"
T3: FULFILLS_REQUIREMENT edge added
T4: CT_ParseArgs → Amended (acceptance_criteria + postcondition field 추가)
```

---

## 3. Hardware Firmware Update

```
T1: CT_Search_ElasticSearch fulfilled (ES 8.10)
T2: ES 8.11 changes query DSL for nested fields
T3: HW_ElasticSearch_Cluster.sdk_version 업데이트
T4: CT_Search_ElasticSearch → Amended (precondition 새 API 반영)
```

---

## 4. Performance Drift (ML)

```
T1: CT_Search_MLRanking fulfilled (nDCG@10 = 0.85)
T2: 24h 평가: nDCG@10 = 0.68 (threshold 0.7 미달)
T3: alert → AptFeedback {category: 'PerformanceDrift', severity: 'P2'}
T4: CT_Search_MLRanking → Amended (NFR 재교정 또는 EXPLORES_VIA 신규 알고리즘)
```

자세한 NFR drift 추적: [nfr_env_variants.md](nfr_env_variants.md)

---

## 5. Accuracy Drift (Vision)

```
T1: CT_Vision_ObjectDetect fulfilled (mAP@0.5 = 0.92)
T2: 신규 환경 (조명 변화) 입력에 mAP 0.78
T3: HardwareContext 변경 가능성 (HW_Camera_Sony → HW_Camera_FLIR)
T4: CT_Vision_ObjectDetect → Amended (HardwareContext 재link + acceptance_criteria 확장)
```

---

## Amendment 실행 cypher

```cypher
// Fulfilled → Amended 전이
MATCH (ct:AptContract {name: $contract_name, status: 'Fulfilled'})
SET ct.status = 'Amended',
    ct.amended_at = datetime(),
    ct.amendment_reason = $reason,
    ct.amendment_trigger = $trigger     -- 'downstream_change'|'new_requirement'|'hardware_change'|'accuracy_drift'|'performance_drift'
WITH ct
// AmendmentEvent 노드 생성
MERGE (ae:AmendmentEvent {name:'AE_'+ct.name+'_'+toString(datetime().epochMillis)})
SET ae.contract = ct.name,
    ae.reason = $reason,
    ae.trigger = $trigger,
    ae.from_status = 'Fulfilled',
    ae.to_status = 'Amended',
    ae.timestamp = datetime(),
    ae.actor = $agent
MERGE (ct)-[:HAS_AMENDMENT]->(ae)
```

Kafka 이벤트는 [_common/kafka_event_convention.md](../../_common/kafka_event_convention.md) 의 `ContractAmended` 형식.

---

## 검증 query

```cypher
-- V-ST-AM-1: silent amendment (ContractAmended event 없는 status 변경)
MATCH (ct:AptContract) WHERE ct.status = 'Amended'
WITH ct
OPTIONAL MATCH (ct)-[:HAS_AMENDMENT]->(ae:AmendmentEvent)
WHERE ae IS NULL
RETURN 'V_ST_Amendment_Silent' AS validation, ct.name AS contract

-- V-ST-AM-2: amendment_reason 누락
MATCH (ct:AptContract)-[:HAS_AMENDMENT]->(ae:AmendmentEvent)
WHERE ae.reason IS NULL OR ae.reason = ''
RETURN 'V_ST_Amendment_NoReason' AS validation, ct.name, ae.name
```

---

## anti-pattern

### E-ST-AM-1: Silent Patch (AP4)
**Context:** Contract 본문 SET status='Amended'만, AmendmentEvent 미생성 + Kafka 미발행.
**Lesson:** 다음 phase가 amendment 사실 인지 못 함. 옛 Contract 기준으로 코딩 → 충돌.
**Guard:** V-ST-AM-1 cypher + ST SKILL.md amendment cypher가 AmendmentEvent + Kafka 자동 생성.

### E-ST-AM-2: reason 모호
**Context:** `amendment_reason: 'fix'` 같은 무내용 사유.
**Lesson:** trigger와 root cause 명시 필수. 다음 amendment 결정 시 history 참조.
**Guard:** V-ST-AM-2 cypher + reason 최소 길이 검증 (e.g. ≥ 20자).

# KG: APT_ST_Amendment_canonical
