# TDAD — Test Discovery After Diff (Phase-Specific)

> arXiv:2603.17973. 에이전트가 코드 수정 시 *어떤 특정 테스트*를 실행해야 하는지 알아야 함. 전체 스위트 실행 ≠ 충분.

---

## 방지하는 문제

- **Blind coding**: 무엇이 깨질 수 있는지 모르고 변경
- **Regression amnesia**: 컨텍스트 압축 후 기존 테스트 잊음
- **Test suite bloat**: 모든 변경마다 전체 스위트 실행 = 낭비

---

## impact_tests 5 규칙

| # | 규칙 | 설명 |
|---|---|---|
| 1 | **구체성** | 각 항목은 정확한 파일 경로. glob (`tests/*.py`), 디렉토리, "run all tests" 금지 |
| 2 | **비어있지 않음** | 최소 1개 항목. impact_tests 없는 Task는 PH5 진입 불가 |
| 3 | **Baseline 의무** | 코드 작성 전 impact_tests 실행. 모두 PASS 필수. FAIL이면 기존 코드베이스가 이미 깨진 상태 |
| 4 | **회귀 탐지** | 구현 후 재실행. baseline PASS였던 테스트가 FAIL이면 에이전트가 도입한 회귀 |
| 5 | **추적성** | 각 테스트 파일에 `# KG: CONTRACT_xxx` 주석 |

---

## NEW_FILE 예외

`contract.target_file`이 아직 없을 때:

- `impact_tests = ["NEW_FILE"]` 마커
- Baseline 실행 **skip** (테스트할 기존 코드 없음)
- RED phase **필수** — 실패 테스트 먼저
- 구현 후 `["NEW_FILE"]` → 실제 테스트 경로 교체:

```cypher
MATCH (task:SemanticTask {name: $task_name})
WHERE task.impact_tests = ['NEW_FILE']
SET task.impact_tests = [$actual_test_path]
```

---

## TDAD 흐름

```
1. Contract 로드 → impact_tests 목록 추출
2. Baseline 실행 (NEW_FILE이면 skip)
   - baseline_results 저장 → AptTestRun 노드
3. RED 작성 (테스트 먼저, 실패 확인)
4. 구현
5. Re-run impact_tests
   - regression = baseline_pass_rate - current_pass_rate > tolerance
6. regression 발견 시 ContractMaterialized 차단
```

---

## 검증 cypher

```cypher
-- V-SCW-TDAD-1: impact_tests 비어있음
MATCH (t:SemanticTask) WHERE t.status = 'in_progress'
WHERE t.impact_tests IS NULL OR size(t.impact_tests) = 0
RETURN 'V_SCW_TDAD_EmptyImpactTests' AS validation, t.name AS task

-- V-SCW-TDAD-2: NEW_FILE 마커 남아있음 (구현 완료인데)
MATCH (t:SemanticTask {status: 'fulfilled'})
WHERE 'NEW_FILE' IN t.impact_tests
RETURN 'V_SCW_TDAD_NewFileMarkerLeft' AS validation, t.name

-- V-SCW-TDAD-3: glob/dir 사용
MATCH (t:SemanticTask)
WHERE any(p IN t.impact_tests WHERE p CONTAINS '*' OR p ENDS WITH '/')
RETURN 'V_SCW_TDAD_GlobOrDir' AS validation, t.name, t.impact_tests
```

# KG: APT_SCW_TDAD_canonical
