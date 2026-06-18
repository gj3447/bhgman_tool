# SCW Anti-Patterns 9개 (Phase-Specific)

> AP1-AP9. 모두 [_common/error_pattern_template.md](../../_common/error_pattern_template.md) 양식 (Context/Lesson/Guard).

---

## AP1: Gold Plating

**Context:** Contract에 없는 기능 추가. "있으면 좋을 것 같아서" 코드 증가.
**Lesson:** Contract = 명세. 더 많은 기능 = scope creep.
**Guard:** FulfillmentGate check 2 (output_type 일치). Contract 필드에 명시된 것만.
**Example:** `output_type: str` 인데 `Dict[str, Any]` 반환 → Gate FAIL.

---

## AP2: Spec Amnesia

**Context:** 코딩 중 Contract 미재열람. 기억에 의존하여 postcondition 누락.
**Lesson:** Contract는 진실. 기억은 drift.
**Guard:** SCW 진입 시 Contract 재로딩 mandatory ([session_startup.md](session_startup.md) Step 5).
**Example:** `postcondition: 'len(result) <= 100'` 잊고 무제한 구현.

---

## AP3: Test Afterthought

**Context:** 코드 먼저, 테스트 나중 맞춤. RED 건너뜀.
**Lesson:** TDD 본질 — RED 먼저, GREEN 다음, REFACTOR 마지막.
**Guard:** TDAD RED 단계 FAIL 확인 필수. NEW_FILE도 RED mandatory ([tdad.md](tdad.md)).
**Example:** 구현 후 테스트가 항상 PASS → trivial assert만.

---

## AP4: Silent Patch

**Context:** 버그 발견 후 KG 기록 없이 코드만 변경.
**Lesson:** 다음 에이전트가 옛 Contract 기준으로 코딩 → 충돌.
**Guard:** AptFeedback 생성 + Kafka FeedbackCreated mandatory ([ph6_feedback.md](ph6_feedback.md)).
**Example:** 타입 불일치 → Contract 수정 없이 코드만 → 충돌.

---

## AP5: Monolith Creep

**Context:** 파일이 `cfg.complexity_threshold` 초과 비대화.
**Lesson:** Span boundary 위반. Vibe coding sweet spot 벗어남.
**Guard:** v(복잡도) gate + FulfillmentGate check 5 complexity.
**Example:** 유틸리티 함수 계속 추가 → 800줄 → SP 재분해.

---

## AP6: Vibe Coding

**Context:** Contract 없이 "감"으로 코딩.
**Lesson:** D9 GenerativeFlowOrdering. Contract 선행 필수.
**Guard:** Phase Detection cypher가 Contract 부재 시 차단.
**Example:** "일단 만들고 Contract 나중에" → E1.

---

## AP7: Self-Approval

**Context:** executor = reviewer. "내가 보니까 괜찮다".
**Lesson:** V15 / HR2. executor != reviewer 분리 의무.
**Guard:** V15 cypher + Kafka consumer 검증.
**Example:** 에이전트 A가 작성 + s 승인 → V15 탐지 → 무효화.

---

## AP8: Trivial Tests

**Context:** 테스트가 postcondition 미검증. `assert True` 수준.
**Lesson:** Test-Contract alignment (FulfillmentGate check 6).
**Guard:** coverage ≥ threshold + assertion-postcondition 매칭.
**Example:** `def test_parse(): assert parse_args is not None` → postcondition 미검증.

---

## AP9: NFR Amnesia

**Context:** latency/memory/accuracy 검증 건너뜀.
**Lesson:** D10 NFR as First-Class. FulfillmentGate check 7.
**Guard:** `nfr_*` 필드 있으면 해당 벤치마크 테스트 mandatory.
**Example:** `nfr_latency_p99_ms: 200` 설정인데 latency 테스트 없이 배포 → p99 500ms.

---

## 통합 검증 cypher

```cypher
// 모든 AP 일괄 (휴리스틱)
CALL {
  // AP4 Silent Patch
  MATCH (ct:AptContract) WHERE ct.status = 'Amended'
  WHERE NOT EXISTS { MATCH (ct)-[:HAS_AMENDMENT]->(:AmendmentEvent) }
  RETURN 'AP4_SilentPatch' AS ap, ct.name AS subject
  UNION ALL
  // AP7 Self-Approval
  MATCH (span:AptSpan)<-[:APPROVED_BY]-(reviewer:AptAgent),
        (span)<-[:EXECUTED_BY]-(executor:AptAgent)
  WHERE executor.name = reviewer.name
  RETURN 'AP7_SelfApproval' AS ap, span.name AS subject
  UNION ALL
  // AP9 NFR Amnesia (nfr 설정 + perf 테스트 없음)
  MATCH (t:SemanticTask)-[:HAS_CONTRACT]->(ct:AptContract)
  WHERE ct.nfr_latency_p99_ms IS NOT NULL
    AND NONE(test IN t.impact_tests WHERE test CONTAINS 'latency' OR test CONTAINS 'perf')
  RETURN 'AP9_NFRAmnesia' AS ap, t.name AS subject
}
RETURN ap, subject ORDER BY ap
```

# KG: APT_SCW_AntiPatterns_canonical
