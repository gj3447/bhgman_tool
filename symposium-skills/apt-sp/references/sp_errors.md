# SP Error Patterns (Phase-Specific)

> apt-sp 고유 에러 사례. [_common/error_pattern_template.md](../../_common/error_pattern_template.md) 3절 양식 (Context/Lesson/Guard) 따름.

각 anti-pattern은 해당 개념의 references/ 내 anti-pattern 절에 분산되어 있고, 본 파일은 *cross-cutting* 또는 *historical drift* 사례 모음.

---

## E1: PH3 → PH5 직행 (ST 건너뛰기, historical)

**Context:** Span 분해 후 Contract 없이 바로 코딩 진입. ST 단계 건너뜀.

**Lesson:** Contract 없는 코딩 = vibe coding. 타입 불일치와 암묵적 가정이 통합 시점에 폭발.

**Guard:** D9 GenerativeFlowOrdering. Phase Detection 쿼리를 구현 전 실행:

```cypher
MATCH (span:AptSpan {name: $target})
OPTIONAL MATCH (span)-[:CRYSTALLIZES_TO]->(st)-[:HAS_CONTRACT]->(c)
WITH span, c
WHERE c IS NULL
RETURN 'BLOCKED: No Contract for ' + span.name AS error
```

[handoff_to_st.md](handoff_to_st.md) E-SP-Handoff-2 도 동일 사례.

---

## E10: s-First Order Waste (v10 legacy)

**Context:** v10 이전. s(인간 검토)를 v/t/i/d 전에 수행. 자동 거를 수 있는 것에도 4시간 SLA 인간 시간 낭비.

**Lesson:** cheap-first 평가는 경제성 의무. 비싼 인간 시간 절약.

**Guard:** v11 평가 순서: v → t → i → d → s. [cs_predicates.md](cs_predicates.md) E-SP-CS-1 와 동일.

---

## E-SP1: INFORMED_BY 없는 분해 (blind decomposition)

**Context:** 외부 지식 연결 없이 "감"으로 분해. 도메인 지식 부재로 잘못된 구조.

**Lesson:** D4 DenseBeforeContract. 분해 전 외부 지식 연결 필수.

**Guard:** Step 1 Link Density Check가 `links(S) >= cfg.density_min_informed_by` 강제. [dense_linking.md](dense_linking.md) V-SP3.

---

## E-SP2: 단일 자식 분해 (BranchingInvariant 위반)

**Context:** Span을 1개 자식으로 "분해". 실제로는 이름 바꾸기.

**Lesson:** A2 min_children >= 2. 1개 자식 = 분해가 아닌 리네이밍.

**Guard:** [sp_rules.md](sp_rules.md) V-SP1 cypher로 자동 탐지.

---

## E-SP3: 형제 간 DEPENDS_ON (A3 위반)

**Context:** 같은 부모 자식 Span 간 DEPENDS_ON 관계 생성.

**Lesson:** A3 SiblingIndependence. 형제 간 의존 = 분해 오류.

**Guard:** [refinement_gate.md](refinement_gate.md) Independence check + V-SP2 cypher.

---

## cross-cutting: E-SP-Drift-1 (concept duplication)

**Context:** Context Budget 공식을 SP 내부에 다시 정의 (sa_world.md와 중복).

**Lesson:** drift 가능성. 한 곳 갱신 시 다른 곳 stale.

**Guard:** _common/ 패턴 (2026-05-11 PD v3 refactor). 모든 phase는 [_common/context_budget.md](../../_common/context_budget.md) 참조.

---

## ErrorPattern KG 결정화

각 E-SP-XX은 KG에 `:ErrorPattern` 노드:

```cypher
MERGE (e:ErrorPattern:AbstractNode {name:'E-SP1'})
SET e.phase = 'SP',
    e.shortName = 'BlindDecomposition',
    e.context = '...',
    e.lesson = '...',
    e.guard = 'V-SP3 + STEP 1 Link Density Check',
    e.severity = 'P2'
WITH e
MATCH (l:Lesson {name:'lesson-d4-dense-before-contract-canonical'})
MERGE (e)-[:GROUNDED_IN_LESSON]->(l)
```

# KG: APT_SP_ErrorPatterns_canonical
