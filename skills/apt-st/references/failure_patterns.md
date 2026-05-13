# Failure Pattern Detection (Phase-Specific)

> Contract 결정화 시점에 *흔한 실패 패턴*을 사전 감지. Signal → Fix 매핑.

---

## 7 Failure Patterns

| Pattern | Signal | Fix |
|---|---|---|
| **Over-ambition** | `estimated_lines > cfg.complexity_threshold` | Return to apt-sp for decomposition |
| **Over-ambition** | "and also" in description | One Contract = one concern |
| **False completion** | postcondition is prose | Rewrite as testable boolean |
| **False completion** | GREEN without RED | Delete tests, confirm RED, re-implement |
| **Testing gap** | impact_tests empty | Block: every Task needs test paths |
| **Testing gap** | NFR set but no perf tests | Add latency/memory/accuracy assertions |
| **Testing gap** | Only happy-path | Add boundary, null, overflow tests |

---

## 자동 탐지 cypher

```cypher
-- Over-ambition: estimated_lines 초과
MATCH (t:SemanticTask)
WHERE t.estimated_lines > 500   -- cfg.complexity_threshold ({{cfg.complexity_threshold}})
RETURN 'F_ST_OverAmbition_Lines' AS pattern, t.name AS subject, t.estimated_lines AS evidence

-- Over-ambition: "and also" in description
MATCH (t:SemanticTask)
WHERE t.description CONTAINS 'and also' OR t.description CONTAINS '그리고 또한'
RETURN 'F_ST_OverAmbition_AndAlso' AS pattern, t.name AS subject, t.description AS evidence

-- False completion: postcondition prose
MATCH (ct:AptContract)
WHERE ct.postcondition CONTAINS '잘 작동' OR ct.postcondition CONTAINS 'works correctly'
   OR NOT (ct.postcondition CONTAINS '==' OR ct.postcondition CONTAINS '>'
        OR ct.postcondition CONTAINS '<' OR ct.postcondition CONTAINS 'is not None')
RETURN 'F_ST_FalseCompletion_Prose' AS pattern, ct.name, ct.postcondition

-- Testing gap: impact_tests empty
MATCH (t:SemanticTask)
WHERE t.impact_tests IS NULL OR size(t.impact_tests) = 0
RETURN 'F_ST_TestingGap_Empty' AS pattern, t.name AS subject

-- Testing gap: NFR set, perf test 없음
MATCH (t:SemanticTask)-[:HAS_CONTRACT]->(ct:AptContract)
WHERE ct.nfr_latency_p99_ms IS NOT NULL
  AND NONE(test IN t.impact_tests WHERE test CONTAINS 'latency' OR test CONTAINS 'perf')
RETURN 'F_ST_TestingGap_NFR' AS pattern, t.name AS subject,
       ct.nfr_latency_p99_ms AS declared_nfr
```

---

## anti-pattern

### E-ST-FP-1: pattern 무시
**Context:** Signal 발견했지만 "급하니까 일단 SCW 진입" 결정.
**Lesson:** failure pattern은 *조기 발견* 기회. 무시하면 SCW에서 FulfillmentGate FAIL → 더 큰 비용.
**Guard:** ST → SCW 핸드오프 cypher가 failure pattern cypher 모두 실행. 1개라도 결과 있으면 차단.

### E-ST-FP-2: signal 정의 변경
**Context:** "and also" 단어 매칭만 → "and then" 같은 변형은 못 잡음.
**Lesson:** signal은 휴리스틱. 인간/에이전트 검토로 보강.
**Guard:** failure pattern cypher 결과는 *경고*. 인간/에이전트 false positive 판단 가능. 단, *재정의 시* lesson 작성.

# KG: APT_ST_FailurePatterns_canonical
