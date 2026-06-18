# Dense Linking — INFORMED_BY ≥ N (Phase-Specific)

> 각 Span이 *외부 지식*에 충분히 연결되어야 분해 정당. blind decomposition (E-SP1) 방지.

---

## 임계값

`cfg.density_min_informed_by` slot resolve. 현재 5 (default).

```cypher
MATCH (cfg:MethodologyConfig {name:'MethodologyConfig_default_v26'})
RETURN cfg.density_min_informed_by
```

---

## 유효한 링크 종류

| 링크 대상 | 예시 | 유효 이유 |
|----------|------|----------|
| 도메인 논문/문서 | `:Research` 노드 | 알고리즘/기법 근거 |
| 기존 Span/Contract | 관련 모듈 노드 | 재사용/참조 |
| 도메인 개념 | `:Concept` 노드 | 용어 정의/온톨로지 |
| 외부 API/라이브러리 | `:Entity` 노드 | 의존성 명시 |
| 하드웨어 컨텍스트 | `:HardwareContext` 노드 | 물리적 제약 |
| Lesson | `:Lesson` 노드 | 과거 실수에서 학습 |
| ResearchFinding (PROM) | `:ResearchFinding` 노드 | 자동 리서치 결과 |

**무효한 링크:**
- 자기 참조 (Span A → Span A)
- 부모/자식 링크 (구조적 관계는 DECOMPOSES_TO로)
- 관련 없는 도메인 노드
- 동일 Span에 같은 대상으로 중복 INFORMED_BY

---

## 적용 cypher

```cypher
-- Dense Linking: 최소 N개 INFORMED_BY 보장
MATCH (s:AptSpan {name: $span})
MATCH (k) WHERE k.name CONTAINS $concept AND NOT (s)-[:INFORMED_BY]->(k)
MERGE (s)-[:INFORMED_BY {reason: $why, linked_at: datetime()}]->(k)
```

검증:

```cypher
-- V-SP3: Dense Linking 미충족
MATCH (s:AptSpan) WHERE s.status = 'open'
OPTIONAL MATCH (s)-[ib:INFORMED_BY]->()
WITH s, count(ib) AS ib_count
MATCH (cfg:MethodologyConfig {name:'MethodologyConfig_default_v26'})
WHERE ib_count < cfg.density_min_informed_by
RETURN 'V_SP3_NoInformedBy' AS validation,
       s.name AS span,
       ib_count AS actual_count,
       cfg.density_min_informed_by AS required_count
```

---

## D4 DenseBeforeContract 원리

분해 *전에* Dense Linking 우선. Contract 작성 시점에 외부 지식 없으면 명세가 "감"이 됨.

```
Step 1: KG 탐색 — 관련 노드 발견
Step 2: INFORMED_BY 링크 추가 (≥ N개)
Step 3: 그 후에 분해 또는 atomic 판정
```

**핵심:** Dense Linking은 분해 *조건*. 충족 안 되면 분해 차단. 일단 분해 후 나중에 채워 넣기 → 너무 늦음.

---

## phase별 변형

| Phase | density 요구 |
|---|---|
| SA | Root Span에 INFORMED_BY ≥ 3 (가벼움) |
| SP | 분해 후 모든 자식에 ≥ `cfg.density_min_informed_by` (현재 5) |
| ST | Contract에 INFORMED_BY ≥ 7 (NFR 환경 변형까지 포함) — 별도 ST 요구 |
| SCW | SourceCodeNode에 INFORMED_BY ≥ 2 (Task + Contract 최소) |

---

## anti-pattern

### E-SP1: blind decomposition
**Context:** INFORMED_BY 없이 "감"으로 분해. 도메인 지식 부재로 잘못된 구조.
**Lesson:** D4 DenseBeforeContract. 분해 전 외부 지식 필수.
**Guard:** Step 1 Link Density Check가 `links(S) >= cfg.density_min_informed_by` 강제. V-SP3 cypher.

### E-SP-DL-2: self-reference link
**Context:** Span A를 Span A에 INFORMED_BY 연결. 자체 강화.
**Lesson:** 외부 지식 아님. count에 잡혀도 의미 없음.
**Guard:** INFORMED_BY 생성 cypher에 `WHERE startNode <> endNode` 강제.

### E-SP-DL-3: parent-child를 INFORMED_BY로 잘못
**Context:** Span A → Span B에 INFORMED_BY 연결. 실제로는 A가 B를 분해함 (DECOMPOSES_TO).
**Lesson:** 의미 다름. INFORMED_BY = "knowledge dependency". DECOMPOSES_TO = "structural decomposition".
**Guard:** INFORMED_BY 생성 cypher에 startNode와 endNode 사이 DECOMPOSES_TO* 경로 없는지 확인.

# KG: APT_SP_DenseLinking_canonical
