# SP 4 Rules (Phase-Specific)

> apt-sp Phase 운영의 4 axiom. 모든 Span 분해는 4 Rule 동시 충족.

---

## Rule 1: SpanPlanningNature

Span은 **추상적 의미(meaning)**를 기술한다. 코드 아티팩트 아님.

- GOOD: "사용자 인증" (의미 단위)
- BAD: "auth.py 파일" (코드 아티팩트)
- BAD: "AuthService 클래스 구현" (구현 수준)

---

## Rule 2: 2-Layer Context Window

분해 시 로드 범위:

- **Layer 0:** S 자신 (description, links, status)
- **Layer 1:** S의 직계 자식 (이미 존재하는 경우)
- **로드 금지:** 손자, 사촌, 원거리 서브트리

전체 트리 로드 금지 → 로컬 추론 강제 → Context Rot 방지.

[_common/progressive_disclosure.md](../../_common/progressive_disclosure.md) 의 L2 패턴과 정합.

---

## Rule 3: Spider Web Weaving

자식은 *고립* 생성되지 않는다. 각 자식은 다음으로부터 직조 (woven):

- 부모 Span의 의미론
- INFORMED_BY 링크의 외부 지식 (논문, 문서, 도메인 모델) — [dense_linking.md](dense_linking.md)
- 형제 인식 (A3 독립성 유지)
- KG에 이미 존재하는 지식 (기존 Span, Contract, 패턴)

---

## Rule 4: N:N DAG

DECOMPOSES_TO와 EXPLORES_VIA 모두 다대다 (N:N):

- 한 Span이 **여러 부모** 가질 수 있음 (모듈 간 공유 관심사)
- 한 부모가 **여러 자식** 가질 수 있음 (분해 브랜치)
- DAG이며 트리 아님. **순환 탐지 필수** (A2 termination).

```cypher
-- V-SP4: 순환 탐지 (0행이면 정상)
MATCH path = (s:AptSpan)-[:DECOMPOSES_TO*2..10]->(s)
RETURN 'V_SP4_Cycle' AS validation,
       [n IN nodes(path) | n.name] AS cycle_nodes
LIMIT 1
```

depth 제한 `*2..10`: `cfg.span_tree_max_depth` slot resolve (현재 10, [magic_number_table.md](../../../THEORY/APT/magic_number_table.md) I 후보).

---

## 4 Rule 통합 cypher

```cypher
// 모든 4 Rule 일괄 검증
CALL {
  // Rule 1: SpanPlanningNature — name이 .py, .ts 등 확장자 포함 시 violation
  MATCH (s:AptSpan)
  WHERE s.name ENDS WITH '.py' OR s.name ENDS WITH '.ts' OR s.name ENDS WITH '.cpp'
     OR s.description CONTAINS '클래스' OR s.description CONTAINS 'class '
  RETURN 'V_SP_Rule1_PlanningNature' AS rule, s.name AS subject, s.description AS detail
  UNION ALL
  // Rule 2: 2-Layer 강제는 cypher가 아닌 SKILL.md flow에서 (Progressive Disclosure L2 의무)
  // Rule 3: INFORMED_BY 없음 (Rule 3은 dense_linking.md V-SP3과 동일)
  MATCH (s:AptSpan) WHERE s.status = 'open'
  OPTIONAL MATCH (s)-[ib:INFORMED_BY]->()
  WITH s, count(ib) AS ib_count
  WHERE ib_count = 0
  RETURN 'V_SP_Rule3_NoWeaving' AS rule, s.name AS subject, toString(ib_count) AS detail
  UNION ALL
  // Rule 4: DAG cycle
  MATCH path = (s:AptSpan)-[:DECOMPOSES_TO*2..10]->(s)
  RETURN 'V_SP_Rule4_Cycle' AS rule, s.name AS subject,
         reduce(s='', n IN nodes(path) | s + n.name + ' → ') AS detail
}
RETURN rule, subject, detail
ORDER BY rule
```

---

## anti-pattern

### E-SP-Rule1: 코드 아티팩트 이름
**Context:** Span 이름이 "AuthService 구현" 또는 "auth.py 작성".
**Lesson:** 의미 추상화 단계. 구현 단계는 SCW.
**Guard:** SP cypher가 Span name/description에 file extension 또는 "구현"/"클래스" 단어 탐지 시 차단.

### E-SP-Rule2: 깊은 트리 한 번에 로드
**Context:** 분해 시 손자, 증손자까지 cypher로 가져옴. Context 폭주.
**Lesson:** Layer 0+1만 의무. 더 깊이 = Context Rot.
**Guard:** Step 2 cypher가 `DECOMPOSES_TO*1..1` (직계 자식만)으로 한정.

### E-SP2: 단일 자식 분해 (Rule 4 위반, BranchingInvariant)
**Context:** Span을 *1개 자식*으로 분해. 실제로는 이름 바꾸기.
**Lesson:** A2 min_children >= 2. 1개 자식 = 리네이밍.
**Guard:** V-SP1 cypher (1-child 탐지).

### E-SP3: 형제 간 DEPENDS_ON (A3 위반)
**Context:** 같은 부모 자식 Span 간 DEPENDS_ON 관계.
**Lesson:** A3 SiblingIndependence. 형제 간 의존 = 분해 오류.
**Guard:** V-SP2 cypher + Step 7 Verify Sibling Independence.

# KG: APT_SP_4Rules_canonical
