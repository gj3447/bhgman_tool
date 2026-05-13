# RefinementGate 3 Checks (Phase-Specific)

> 분해 후 자식 집합의 *품질*을 검증하는 게이트. Coverage / Consistency / Independence 3-check 통과해야 다음 sub-decomposition 진입.

---

## Coverage (커버리지)

**질문:** 자식들이 부모의 의미를 *완전히* 커버하는가?

**실패 시:** 누락된 Span 추가. 부모 description에서 커버되지 않은 의미 영역 식별 → 새 자식 생성.

```cypher
-- Coverage 검증: 부모 description의 핵심 단어가 자식 description에 등장
MATCH (p:AptSpan {name: $parent})-[:DECOMPOSES_TO]->(child)
WITH p, collect(child) AS children, p.description AS pdesc
WITH p, children, [word IN split(pdesc, ' ') WHERE size(word) > 4] AS pwords
UNWIND pwords AS pword
WITH p, children, pword
WHERE NONE(c IN children WHERE c.description CONTAINS pword)
RETURN 'V_SP_Coverage_Missing' AS validation,
       p.name AS parent, pword AS missing_word
```

---

## Consistency (일관성)

**질문:** 자식 간 *모순*이 없는가?

**실패 시:** 모순되는 자식의 description 수정. 동일 입력에 대해 상충하는 postcondition이 있으면 하나 조정.

```cypher
-- 동일 입력 → 다른 postcondition 자식 페어 탐지 (휴리스틱)
MATCH (p:AptSpan {name: $parent})-[:DECOMPOSES_TO]->(c1:AtomicSpan),
      (p)-[:DECOMPOSES_TO]->(c2:AtomicSpan)
WHERE c1 <> c2
MATCH (c1)-[:CRYSTALLIZES_TO]->()-[:HAS_CONTRACT]->(ct1),
      (c2)-[:CRYSTALLIZES_TO]->()-[:HAS_CONTRACT]->(ct2)
WHERE ct1.input_type = ct2.input_type
  AND ct1.postcondition <> ct2.postcondition
RETURN 'V_SP_Consistency_Conflict' AS validation,
       c1.name, c2.name, ct1.postcondition, ct2.postcondition
```

---

## Independence (독립성)

**질문:** 형제(sibling) 간 *의존*이 없는가?

**실패 시:** 의존 관계 형제 재분해. 의존을 부모 레벨로 올리거나 구조 변경.

```cypher
-- Independence 검증 (반드시 0행 반환)
MATCH (p:AptSpan {name: $parent})-[:DECOMPOSES_TO]->(a),
      (p)-[:DECOMPOSES_TO]->(b)
WHERE a <> b AND (a)-[:DEPENDS_ON]->(b)
RETURN 'V_SP_Independence_Violation' AS validation,
       a.name AS dependent, b.name AS dependency
-- 결과 있으면 A3 위반: 재분해 필요
```

---

## 통합 게이트 cypher

3-check 일괄:

```cypher
CALL {
  // Coverage
  MATCH (p:AptSpan {name: $parent})-[:DECOMPOSES_TO]->(child)
  WITH p, collect(child) AS children, p.description AS pdesc
  WITH p, children, [word IN split(pdesc, ' ') WHERE size(word) > 4] AS pwords
  UNWIND pwords AS pword
  WITH p, children, pword
  WHERE NONE(c IN children WHERE c.description CONTAINS pword)
  RETURN 'V_SP_Coverage_Missing' AS check, p.name AS subject, pword AS detail
  UNION ALL
  // Consistency (simplified — full version cypher 별도 파일)
  MATCH (p:AptSpan {name: $parent})-[:DECOMPOSES_TO]->(c1:AtomicSpan),
        (p)-[:DECOMPOSES_TO]->(c2:AtomicSpan)
  WHERE c1.name < c2.name  -- avoid duplicate pair
  MATCH (c1)-[:CRYSTALLIZES_TO]->()-[:HAS_CONTRACT]->(ct1),
        (c2)-[:CRYSTALLIZES_TO]->()-[:HAS_CONTRACT]->(ct2)
  WHERE ct1.input_type = ct2.input_type AND ct1.postcondition <> ct2.postcondition
  RETURN 'V_SP_Consistency_Conflict' AS check, c1.name AS subject, c2.name AS detail
  UNION ALL
  // Independence
  MATCH (p:AptSpan {name: $parent})-[:DECOMPOSES_TO]->(a),
        (p)-[:DECOMPOSES_TO]->(b)
  WHERE a <> b AND (a)-[:DEPENDS_ON]->(b)
  RETURN 'V_SP_Independence_Violation' AS check, a.name AS subject, b.name AS detail
}
RETURN check, subject, detail
ORDER BY check
```

결과 0행 = 3-check 통과. 1행 이상 = 재분해 필요.

---

## anti-pattern

### E-SP-RG-1: silent gate bypass
**Context:** 자식 분해 후 RefinementGate 실행 안 하고 다음 sub-decomposition 진입. 일부 자식이 A3 위반.
**Lesson:** 분해 마다 gate. 누적되면 자식 트리 전체가 A3 깨짐.
**Guard:** SP SKILL.md Step 3 (분해) 후 즉시 통합 게이트 cypher 실행. 0행 아니면 진행 차단.

### E-SP-RG-2: Coverage 휴리스틱 over-fitting
**Context:** Coverage check가 부모 description의 단어 단순 매칭 → 부모가 "사용자 인증 시스템" 인데 자식이 "auth", "session" 만 → 단어 매칭 실패하지만 의미적으로 커버됨.
**Lesson:** 단어 매칭은 휴리스틱일 뿐. 검증 결과는 *제안*이지 자동 차단 아님 (False Positive 가능).
**Guard:** Coverage 결과는 일단 보고. 인간/에이전트 검토 후 false positive 시 V_SP_Coverage_Missing 무시 가능.

# KG: APT_SP_RefinementGate_canonical
