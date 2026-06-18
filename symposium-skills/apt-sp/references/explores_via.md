# EXPLORES_VIA Pattern — Alternative Decomposition (Phase-Specific)

> 한 Span을 *여러 대안*으로 동시 탐색. DECOMPOSES_TO(분해)와 직교 — EXPLORES_VIA(탐색).

---

## 3 strategies

| 전략 | 의미 | 사용 시점 | Edge 속성 |
|------|------|----------|----------|
| **best_of_n** | N개 대안 독립 실행, 벤치마크 후 승자 1개 선택 | 복수 알고리즘 + 경험적 비교 필요 | strategy, created_at |
| **ensemble** | N개 대안의 출력 결합 (투표, 평균, 스태킹) | 조합이 개별보다 정확도 높을 때 | strategy, weight(0.0~1.0) |
| **fallback_chain** | 우선순위 순서로 시도, 첫 성공 사용 | 대안 신뢰도/비용이 다를 때 | strategy, priority(1=first) |

---

## Selection Span

탐색의 부모가 소유하는 *전용 평가자*. DECOMPOSES_TO로 연결 (EXPLORES_VIA가 아님).

```
Parent (탐색 소유자)
  |
  +-- EXPLORES_VIA {strategy:'best_of_n'} --> Alt_A (AtomicSpan)
  +-- EXPLORES_VIA {strategy:'best_of_n'} --> Alt_B (AtomicSpan)
  +-- EXPLORES_VIA {strategy:'best_of_n'} --> Alt_C (AtomicSpan)
  |
  +-- DECOMPOSES_TO --> Selection_Span (AtomicSpan)
       |-- 모든 대안 벤치마크 실행
       |-- 정확도, 지연시간, NFR 준수 평가
       +-- 승자를 KG에 SELECTED 엣지로 기록
```

**A3 (SiblingIndependence):** 대안들은 상호 독립. Selection Span은 대안 출력에만 의존 (내부 의존 안 함).

---

## Confluence Detection

두 대안이 동등한 결과를 산출하면 **confluent** (합류).

```cypher
-- 벤치마크 후 두 대안 결과가 허용 범위 내 동등
MATCH (a1:AtomicSpan)<-[:EXPLORES_VIA]-(parent)-[:EXPLORES_VIA]->(a2:AtomicSpan)
WHERE a1 <> a2
  AND a1.benchmark_result IS NOT NULL
  AND a2.benchmark_result IS NOT NULL
  AND abs(a1.benchmark_accuracy - a2.benchmark_accuracy) < $tolerance
MERGE (a1)-[:CONFLUENT_WITH {
  metric: 'accuracy',
  delta: abs(a1.benchmark_accuracy - a2.benchmark_accuracy),
  detected_at: datetime()
}]->(a2)
```

### 합류 감지 시
1. CONFLUENT_WITH 엣지 기록
2. Selection Span의 결정 근거에 합류 사실 기재
3. 향후 탐색에서 합류 대안 중 하나 건너뛸 수 있음
4. 모든 대안 합류 → 탐색이 단일 브랜치로 축소

---

## anti-pattern

### E-SP-EV-1: EXPLORES_VIA를 DECOMPOSES_TO로 잘못 사용
**Context:** 대안을 부모의 *자식*으로 추가. Selection Span 없음. 어떤 게 승자인지 KG에 없음.
**Lesson:** 대안 = 부모의 *외부* relationship (EXPLORES_VIA). 자식 = 부모의 *분해* (DECOMPOSES_TO). 의미 다름.
**Guard:** SP SKILL.md 진입 시 부모-자식 edge type 검증. EXPLORES_VIA 누락 발견 시 분해 ↔ 탐색 재구분.

### E-SP-EV-2: Selection Span 누락
**Context:** EXPLORES_VIA 3개 대안 등록했지만 평가자 (Selection Span) 없음.
**Lesson:** 평가 없는 탐색 = 결정 불가. 모든 대안이 "후보"로만 남고 승자 미선언.
**Guard:** Parent에 EXPLORES_VIA ≥1 발견 시 DECOMPOSES_TO 으로 Selection Span 1개 mandatory cypher 강제.

### E-SP-EV-3: A3 위반 (대안 간 의존)
**Context:** Alt_A가 Alt_B의 출력을 입력으로 사용. 형제이면서 의존.
**Lesson:** A3 SiblingIndependence. 대안은 *독립* 실행 가능해야 비교 의미 있음.
**Guard:** EXPLORES_VIA 끝점 간 DEPENDS_ON 탐지 cypher. 발견 시 즉시 재분해.

# KG: APT_SP_ExploresVia_canonical
