# tau_check 5/5 — Before/After Fix (Phase-Specific)

> Contract 결정화 *직전* 검증. 5 필드 모두 구체적이고 검증 가능해야 통과.

---

## 5 Checks

| # | Check | Question |
|---|---|---|
| 1 | input concrete? | input_type이 구체적 DTO/Schema인가? `data`, `any` 금지 |
| 2 | output concrete? | output_type이 구체적인가? `result`, `object` 금지 |
| 3 | precondition boolean? | precondition이 boolean 표현식? 산문 금지 |
| 4 | postcondition verifiable? | postcondition을 테스트 assertion으로 변환 가능? |
| 5 | semantic meaning? | semantic_meaning에 도메인 컨텍스트 명시? "처리한다" 같은 추상 금지 |

---

## Before (5/5 FAIL)

```yaml
input_type:       "data"                  # abstract
output_type:      "result"                # abstract
precondition:     "valid input"           # prose
postcondition:    "works correctly"       # not verifiable
semantic_meaning: "processes stuff"       # no domain context
```

## After (5/5 PASS)

```yaml
input_type:       "DataFrame{columns:['x','y','z'], dtypes:float64}"
output_type:      "ClusterResult{labels:ndarray int32[N], centroids:ndarray float64[K,3]}"
precondition:     "len(df) > 0 and set(['x','y','z']).issubset(df.columns)"
postcondition:    "len(result.labels) == len(input) and result.centroids.shape[1] == 3"
semantic_meaning: "K-means clustering of 3D points in mm, ROBOT_BASE frame.
  Labels 0..K-1, centroids in same frame."
```

---

## tau_check 자동 cypher

```cypher
-- 5 check 일괄 평가
MATCH (ct:AptContract {name: $contract_name})
WITH ct,
     // 1: input concrete
     CASE WHEN ct.input_type IN ['data','any','object','info','result',null,'']
          THEN false ELSE true END AS check_1_input,
     // 2: output concrete
     CASE WHEN ct.output_type IN ['data','any','object','info','result',null,'']
          THEN false ELSE true END AS check_2_output,
     // 3: precondition boolean
     CASE WHEN ct.precondition CONTAINS '==' OR ct.precondition CONTAINS '>'
              OR ct.precondition CONTAINS '<' OR ct.precondition CONTAINS 'len('
              OR ct.precondition CONTAINS 'in ' OR ct.precondition CONTAINS 'is not None'
          THEN true ELSE false END AS check_3_pre,
     // 4: postcondition verifiable
     CASE WHEN ct.postcondition CONTAINS '==' OR ct.postcondition CONTAINS '>'
              OR ct.postcondition CONTAINS '<' OR ct.postcondition CONTAINS 'len('
              OR ct.postcondition CONTAINS '.shape' OR ct.postcondition CONTAINS 'is not None'
          THEN true ELSE false END AS check_4_post,
     // 5: semantic meaning
     CASE WHEN ct.semantic_meaning IS NULL OR size(ct.semantic_meaning) < 20
          THEN false ELSE true END AS check_5_semantic
RETURN ct.name AS contract,
       check_1_input, check_2_output, check_3_pre, check_4_post, check_5_semantic,
       (check_1_input AND check_2_output AND check_3_pre AND check_4_post AND check_5_semantic) AS tau_check_pass
```

`tau_check_pass = false` → Contract status='Active' 전이 차단.

---

## 검증 query (집계)

```cypher
-- V-ST-TC-1: tau_check FAIL Contract 목록
MATCH (ct:AptContract) WHERE ct.status IN ['Draft','Active']
WITH ct
WHERE ct.input_type IN ['data','any','object','info','result',null,'']
   OR ct.output_type IN ['data','any','object','info','result',null,'']
   OR ct.semantic_meaning IS NULL OR size(coalesce(ct.semantic_meaning,'')) < 20
RETURN 'V_ST_TauCheck_Fail' AS validation, ct.name AS contract, ct.status
```

---

## anti-pattern

### E-ST-TC-1: tau_check skip
**Context:** Contract Draft에서 곧장 Active 전이. tau_check 자동 cypher 실행 안 함.
**Lesson:** prose 명세는 SCW에서 검증 불가능 → FulfillmentGate FAIL.
**Guard:** Draft → Active 전이 cypher에 tau_check 통합. `tau_check_pass = false` 이면 차단.

### E-ST-TC-2: 부분 통과
**Context:** 5 check 중 4 PASS, 1 FAIL인데 "거의 다 됐다" 판단으로 Active.
**Lesson:** AND 의무. 부분 통과 = 미통과.
**Guard:** tau_check_pass boolean 단일 반환. 부분 우회 불가.

# KG: APT_ST_TauCheck_canonical
