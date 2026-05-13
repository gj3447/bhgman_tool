# Session Startup Protocol — 7단계 (Phase-Specific)

> SCW 세션 시작 시 *반드시* 수행. cold-start 컨텍스트 복원.

---

## 7단계

| # | 단계 | 목적 |
|---|---|---|
| 1 | `pwd` 확인 | 작업 디렉토리 올바른지 |
| 2 | `apt-progress.md` 읽기 | 이전 세션 상태 복원 |
| 3 | `git log --oneline -10` | 최근 커밋 이력으로 맥락 파악 |
| 4 | 미완성 Task 중 최고 우선순위 선택 (**1개만**) | 단일 Task 집중 (multi-task = Context Rot) |
| 5 | 해당 Contract 로드 (Progressive Disclosure L3) | 7 필드 + NFR 확인 |
| 6 | impact_tests 실행 → 기존 테스트 통과 확인 | TDAD baseline 확보 |
| 7 | 구현 시작 | RED phase부터 (테스트 먼저) |

---

## Step 4 단일 Task 강제 cypher

```cypher
MATCH (task:SemanticTask) WHERE task.status = 'in_progress'
RETURN task.name, task.priority,
       coalesce(task.assigned_to, 'unassigned') AS owner
ORDER BY task.priority ASC, task.created_at ASC
LIMIT 1
```

한 시점에 *한 Task*. multi-task 발견 시:

```cypher
MATCH (task:SemanticTask {status: 'in_progress', assigned_to: $agent})
WITH count(task) AS active_count
WHERE active_count > 1
RETURN 'E_SCW_SessionStartup_MultiTask' AS error, active_count
```

---

## Step 2 apt-progress.md 누락 시

```python
import os
if not os.path.exists('apt-progress.md'):
    print("E_SCW_SessionStartup_NoProgress: apt-progress.md 부재")
    print("→ SA Phase 미완료. apt-sa 실행 필요.")
    exit(1)
```

apt-progress.md 형식: [../../apt-sa/references/progress_template.md](../../apt-sa/references/progress_template.md)

---

## Step 6 baseline 실패 시

baseline impact_tests가 PASS가 아니면 기존 코드베이스가 이미 깨진 상태:

1. 코드 작성 *전*에 baseline 깨짐 발견
2. 새 Task의 회귀 아님 — 사전부터 broken
3. Task 진입 보류, 기존 코드 수정 우선
4. AptFeedback 생성 (`category: 'Bug'`, `target_phase: 'PH4'`)

---

## anti-pattern

### E-SCW-SS-1: Session Startup skip
**Context:** SCW 진입 시 곧장 코딩. Step 1-7 안 함.
**Lesson:** cold-start = 컨텍스트 없는 상태. 직전 세션 상태 무시 → 회귀 위험.
**Guard:** SCW SKILL.md 진입 시 자동 Step 1-3 cypher 실행. apt-progress.md 부재 시 차단.

### E-SCW-SS-2: 다중 Task 동시 진행
**Context:** Task A 진행 중인데 Task B 시작.
**Lesson:** Context Rot. 두 Task의 컨텍스트가 섞임. 둘 다 품질 저하.
**Guard:** Step 4 single-task cypher 강제.

### E-SCW-SS-3: baseline skip
**Context:** Step 6 (baseline 실행) 안 하고 곧장 RED 작성.
**Lesson:** 기존 회귀 못 잡음. 새 회귀와 구분 불가.
**Guard:** Step 5 → Step 7 순서 강제. Step 6 baseline 결과 AptTestRun에 기록 후만 Step 7 진입.

# KG: APT_SCW_SessionStartup_canonical
