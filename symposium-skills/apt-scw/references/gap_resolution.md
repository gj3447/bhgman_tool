# Gap Resolution (Thompson Sampling) (Phase-Specific)

> Gap 발견 시 *70/30 exploitation/exploration* + Thompson Sampling으로 후보 선택. 3x 금지 + adopt/reject 기준.

---

## 전체 루프

```
1. Gap 발견 → AptFeedback 생성 (category: 'Missing')
2. 후보 생성 → GapCandidate 노드
   - 70% exploitation (KG 기존 패턴)
   - 30% exploration (신규 접근)
3. 실험 → 각 후보 소규모 PoC
4. 점수 업데이트 → positive/negative 카운트
5. 선택 → adopt / reject / pending
```

---

## 규칙

| 규칙 | 설명 |
|---|---|
| **70/30 비율** | 후보 생성 시 70% exploitation, 30% exploration |
| **3x 금지** | 동일 후보 3회 이상 실험 금지. 데이터 충분 → 판단 |
| **Adopt 기준** | positive >= 3 AND negative <= 1 → 채택 |
| **Reject 기준** | negative >= 3 → 폐기 |
| **중립** | 위 기준 미충족 → 추가 실험 또는 인간 위임 |

---

## Cypher

```cypher
-- 후보 생성
MERGE (gap:AptFeedback {name: $gap_name})
SET gap.category = 'Missing', gap.status = 'open'
WITH gap
MERGE (cand:GapCandidate {name: $candidate_name})
SET cand.approach = $approach,
    cand.source = $source_type,  -- 'exploitation' | 'exploration'
    cand.positive = 0, cand.negative = 0,
    cand.trials = 0, cand.status = 'pending'
MERGE (gap)-[:HAS_CANDIDATE]->(cand)

-- 점수 업데이트 (3x 금지 적용)
MATCH (cand:GapCandidate {name: $candidate_name})
WHERE cand.trials < 3
SET cand.trials = cand.trials + 1,
    cand.positive = CASE WHEN $result = 'positive'
                         THEN cand.positive + 1 ELSE cand.positive END,
    cand.negative = CASE WHEN $result = 'negative'
                         THEN cand.negative + 1 ELSE cand.negative END,
    cand.status = CASE
      WHEN cand.positive + (CASE WHEN $result='positive' THEN 1 ELSE 0 END) >= 3
           AND cand.negative + (CASE WHEN $result='negative' THEN 1 ELSE 0 END) <= 1
      THEN 'adopted'
      WHEN cand.negative + (CASE WHEN $result='negative' THEN 1 ELSE 0 END) >= 3
      THEN 'rejected'
      ELSE 'pending' END,
    cand.last_trial = datetime()

-- Thompson Sampling 선택 (Beta 분포 평균 근사)
MATCH (gap:AptFeedback {name: $gap_name})-[:HAS_CANDIDATE]->(cand)
WHERE cand.status = 'pending' AND cand.trials < 3
RETURN cand.name, cand.approach, cand.source,
       toFloat(cand.positive + 1) / (cand.positive + cand.negative + 2) AS thompson_score
ORDER BY thompson_score DESC
```

> 실제 Thompson Sampling은 Beta(positive+1, negative+1) 분포 샘플링. Cypher에서는 평균 근사. 실제 샘플링은 애플리케이션 코드.

---

## anti-pattern

### E-SCW-GR-1: 70/30 비율 무시
**Context:** 모든 후보를 exploitation에서만 생성. 신규 접근 (exploration) 0%.
**Lesson:** local optimum 갇힘. KG에 없는 더 나은 접근 발견 못 함.
**Guard:** 후보 생성 cypher에 `cand.source` 비율 검증. exploration < 30% 시 alert.

### E-SCW-GR-2: 3x 무시
**Context:** 같은 후보 5번, 7번 시도. 결정 미루기.
**Lesson:** 데이터 충분한데 판단 미룸 = 분석 마비.
**Guard:** trials >= 3 시 자동 status='pending_human' 전환.

# KG: APT_SCW_GapResolution_canonical
