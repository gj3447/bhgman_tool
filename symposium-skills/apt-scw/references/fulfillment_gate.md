# FulfillmentGate 7 Checks (Phase-Specific)

> ContractMaterialized 수락 *전* 모든 7개 검사 통과 필수. 하나라도 FAIL이면 차단.

---

## 7 Checks

| # | Check | 상세 |
|---|---|---|
| 1 | **All acceptance tests pass** | contract.acceptance_criteria의 모든 테스트 PASS. impact_tests 포함. 단일 FAIL도 차단. skip 금지. |
| 2 | **Output type matches** | 실제 반환 타입 == contract.output_type. 동적 타입 언어는 런타임 타입 검사. 구조적 서브타이핑은 문서화 시 허용. |
| 3 | **Pre/postconditions checked in code** | 명시적 `assert`/`raise ValueError`로 사전조건 검증 + 사후조건 검증. 유효하지 않은 입력 silent ignore 금지. |
| 4 | **KG reference comments present** | 소스 파일에 `# KG: TASK_{name}`, `# KG: CONTRACT_{name}` 주석. 자세히: [kg_ref_comments.md](kg_ref_comments.md) |
| 5 | **Complexity within threshold** | `lines(source) <= cfg.complexity_threshold` ({{cfg.complexity_threshold}}, 현재 500). 빈 줄/주석 제외. 초과 시 SP 재분해. |
| 6 | **Test-Contract alignment** | 테스트가 postcondition을 실제 검증. happy path만 = 불충분. 동어반복 = FAIL. |
| 7 | **NFR assertions pass** | `nfr_*` 설정 시 벤치마크 통과. latency=N회 p99, memory=peak, accuracy=mean. nfr_* 없으면 자동 PASS. |

---

## Gate 자동 cypher

```cypher
MATCH (ct:AptContract {name: $contract, status: 'Active'})
MATCH (task:SemanticTask)-[:HAS_CONTRACT]->(ct)
OPTIONAL MATCH (run:AptTestRun)-[:TESTS]->(ct)
WITH ct, task, run
ORDER BY run.timestamp DESC LIMIT 1

WITH ct, task, run,
     // 1: all tests pass
     CASE WHEN run.failed = 0 AND run.skipped = 0 THEN true ELSE false END AS c1_tests,
     // 5: complexity
     CASE WHEN run.lines <= 500 THEN true ELSE false END AS c5_complex,  -- {{cfg.complexity_threshold}}
     // 7: NFR
     CASE WHEN ct.nfr_latency_p99_ms IS NULL
              OR run.latency_p99_ms <= ct.nfr_latency_p99_ms THEN true ELSE false END AS c7_nfr
RETURN ct.name AS contract,
       c1_tests, c5_complex, c7_nfr,
       (c1_tests AND c5_complex AND c7_nfr) AS gate_pass
```

(checks 2/3/4/6은 source code 정적 분석 + KG ref scan으로 별도 검증 — `apt-gate-check.sh` 또는 `gate_endpoint_prototype/`.)

---

## Gate FAIL 시 행동

```cypher
// gate FAIL 시 Kafka 이벤트
MATCH (ct:AptContract {name: $contract})
SET ct.gate_check_failed_at = datetime(),
    ct.gate_check_failed_count = coalesce(ct.gate_check_failed_count, 0) + 1
```

Kafka:

```json
{
  "event_type": "GateCheckFailed",
  "payload": {
    "gate_name": "FulfillmentGate",
    "check_failed": 5,
    "check_name": "Complexity within threshold",
    "actual_value": 678,
    "threshold_value": 500,
    "action": "block_materialization",
    "remediation": "return to PH3 for decomposition"
  }
}
```

자세한 Kafka 형식: [_common/kafka_event_convention.md](../../_common/kafka_event_convention.md)

---

## anti-pattern

### E-SCW-FG-1: silent gate skip
**Context:** FulfillmentGate cypher 실행 안 하고 ContractMaterialized 발행.
**Lesson:** silent skip = 7 check 우회. 안 한 check 만큼 위험.
**Guard:** ContractMaterialized 발행 *전* gate cypher 실행. `gate_pass = false` 이면 발행 차단.

### E-SCW-FG-2: 부분 통과 인정
**Context:** 7 check 중 6 PASS, 1 FAIL인데 "별 거 아닌 항목" 판단으로 진행.
**Lesson:** AND 의무. 임의 한 check를 "별 거 아님" 분류 = 자체 임의 판단.
**Guard:** `gate_pass` 단일 boolean. 우회 불가.

# KG: APT_SCW_FulfillmentGate_canonical
