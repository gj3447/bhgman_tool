# SCW → SP/ST Feedback Handoff (Phase-Specific)

> SCW 구현 중 PH6 discovery 발생 시 SP (PH3) 또는 ST (PH4) 로 피드백. Max returns + 인간 에스컬레이션.

---

## Max Returns + 에스컬레이션

| 조건 | 행동 |
|---|---|
| `return_count <= cfg.max_returns_per_span` (기본 3) | 정상 피드백 루프: PH3/PH4 복귀 |
| `return_count > max_returns_per_span` | **인간 에스컬레이션 필수**. 자동 복귀 금지. |

---

## Severity 매트릭스

| Category | Severity |
|---|:-:|
| Bug | P1-P2 |
| Violation | P1-P2 |
| SLABreach | P1-P2 |
| Missing | P2-P3 |
| Conflict | P2-P3 |
| PerformanceDrift | P2-P3 |
| Confusion | P3 |
| FalsePositive | P3 |
| FalseNegative | P2 |
| Improvement | P3-P4 |

---

## 피드백 라우팅

```
discovery_type: missing_span | accuracy_drift
  → PH3 (SP 재분해)
  → 새 Span 생성 → ST → 돌아오기

discovery_type: contract_gap | type_mismatch | edge_case | false_positive
  → PH4 (ST Contract 수정)
  → Contract 수정 → 테스트 재작성 → 돌아오기
```

자세히: [ph6_feedback.md](ph6_feedback.md)

---

## 사용 규칙

1. **Silent Patch 금지** (AP4) — 코드 변경 시 AptFeedback 생성 필수
2. **Max returns** — 동일 Span에 `cfg.max_returns_per_span` (기본 3) 초과 → 인간 에스컬레이션
3. **Severity 분류** — 위 표 따름
4. **카테고리 정확성** — FalsePositive/FalseNegative는 *검증 시스템* 자체 문제. 검증 로직 수정 필요
5. **PerformanceDrift/SLABreach** — NFR 재교정 + 재실험 트리거

---

## 피드백 해결 Cypher

```cypher
MATCH (fb:AptFeedback {name: $title})
SET fb.status = 'resolved',
    fb.resolved_at = datetime(),
    fb.resolved_by = $agent,
    fb.resolution = $resolution
RETURN fb.name, fb.status, fb.resolution
```

---

## 검증 query

```cypher
-- V-SCW-Handoff-1: max returns 초과 (인간 에스컬레이션 누락)
MATCH (span:AptSpan)<-[:AFFECTS]-(fb:AptFeedback)
WITH span, count(fb) AS return_count
WHERE return_count > 3   -- cfg.max_returns_per_span
RETURN 'V_SCW_Handoff_MaxReturnsExceeded' AS validation,
       span.name AS span, return_count

-- V-SCW-Handoff-2: severity 누락
MATCH (fb:AptFeedback) WHERE fb.severity IS NULL
RETURN 'V_SCW_Handoff_NoSeverity' AS validation, fb.name
```

---

## anti-pattern

### E-SCW-Handoff-1: silent patch (AP4 again)
**Context:** 코드 수정 후 AptFeedback 안 만듦.
**Lesson:** PH6 discovery는 기록 필수. KG 미기록 = 다음 사이클이 모름.
**Guard:** SCW 코드 변경 cypher가 AptFeedback 생성 mandatory.

### E-SCW-Handoff-2: 무한 반복
**Context:** 같은 Span에 5번, 7번 피드백. 인간 에스컬레이션 안 함.
**Lesson:** max_returns가 무시되면 결정 미루기.
**Guard:** V-SCW-Handoff-1 cypher가 매 피드백 생성 시 실행. 초과 시 자동 인간 알림.

# KG: APT_SCW_HandoffToSPST_canonical
