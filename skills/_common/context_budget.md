# Context Budget — depth별 토큰 예산 (Cross-Skill Shared)

> APT phase 모두에서 사용하는 공학적 휴리스틱. 인지과학 이론 아닌 *경험적 fit*. Context Rot 방지의 1차 방어선.

---

## depth 기반 공식

| Span Depth | 토큰 예산 | 근거 |
|:----------:|:---------:|------|
| 0 (Root) | 50,000 | 프로젝트 전체 개요. L1 메타 + L2 구조. |
| 1 | 50,000 | 주요 모듈. 넉넉한 컨텍스트 필요. |
| 2 | 20,000 | 서브모듈. 범위 좁아짐. |
| 3+ (AtomicSpan) | 8,000 | 단일 파일 `cfg.vibe_coding_sweet_max` 줄 구현에 적정. |

---

## KG slot resolve

값 자체는 `MethodologyConfig` 노드의 slot에서 resolve. SKILL.md 본문 하드코딩 금지.

```cypher
MATCH (cfg:MethodologyConfig {name:'MethodologyConfig_default_v26'})
RETURN cfg.context_budget_total,
       cfg.context_budget_depth_0,
       cfg.context_budget_depth_1,
       cfg.context_budget_depth_2,
       cfg.context_budget_atomic
```

현재 slot 값 (2026-05-11):
- `context_budget_total`: 100,000
- `context_budget_per_span` (depth 3+ 기본값): 8,000
- depth 0/1: 50K / depth 2: 20K (위 표)

---

## 적용 cypher

```cypher
-- SA에서 SemanticAnchor 생성 시 총 예산 설정
MATCH (sa:SemanticAnchor {name: $sa_name})
SET sa.context_budget_total = 100000,
    sa.context_budget_per_span = 8000

-- Span 생성 시 depth 기반 자동 할당
MERGE (child:AptSpan {name: $name})
SET child.context_budget = CASE
  WHEN child.depth <= 1 THEN 50000
  WHEN child.depth = 2 THEN 20000
  ELSE 8000 END
```

---

## 검증 query (모든 phase 공통)

```cypher
-- V-CB1: Context Budget 미할당 SA
MATCH (sa:SemanticAnchor {status: 'active'})
WHERE sa.context_budget_total IS NULL
RETURN 'V_CB1_NoBudget_SA' AS validation, sa.name AS anchor

-- V-CB2: Context Budget 미할당 Span
MATCH (s:AptSpan)
WHERE s.context_budget IS NULL
RETURN 'V_CB2_NoBudget_Span' AS validation, s.name AS span

-- V-CB3: depth와 budget 불일치 (자동 할당 우회)
MATCH (s:AptSpan) WHERE s.depth IS NOT NULL AND s.context_budget IS NOT NULL
WITH s,
     CASE WHEN s.depth <= 1 THEN 50000
          WHEN s.depth = 2 THEN 20000
          ELSE 8000 END AS expected
WHERE s.context_budget <> expected
RETURN 'V_CB3_BudgetMismatch' AS validation,
       s.name, s.depth, s.context_budget, expected
```

---

## phase별 변형 / 추가 검증

| Phase | 추가 검증 |
|---|---|
| SA | `sa.context_budget_total IS NOT NULL` (V-SA4) — SA 핸드오프 체크리스트 #5 |
| SP | depth 기반 자동 할당 강제. 자식 생성 시 부모 budget < 자식 budget 시 경고. |
| ST | Contract 본문이 L3 8K 안에 들어가는지 확인 (NFR 4환경 변형 시 25K로 확장 가능). |
| SCW | impact_tests + 구현 코드 합산이 L3 안에 들어가는지. 초과 시 Span 재분해 강제. |

---

## anti-pattern

- **E-CB1: 하드코딩** — 본문에 "200~500줄", "8000 token" 직접 인용. → cfg slot 참조로 교체 (`magic_number_table.md` III.2 migration).
- **E-CB2: depth 기반 무시** — 모든 Span에 동일 budget. depth 깊어져도 줄어들지 않음. → 자동 할당 cypher 강제.
- **E-CB3: 토큰 폭주 무관심** — Context Rot 발생해도 계속 진행. → SA의 P-SA5 (Context Budget 할당됨) 게이트가 우회되지 않도록.

---

## Academic Grounding

Context Budget의 depth별 토큰 할당 (50K/50K/20K/8K)은 *engineering heuristic*이지만 3 academic foundation에 grounding:

### 1. Working Memory Capacity (Baddeley 2000)

> Baddeley, A. (2000). *The episodic buffer: a new component of working memory?* Trends in Cognitive Sciences, 4(11), 417-423.

작업 기억 4 component (phonological loop / visuospatial sketchpad / episodic buffer / central executive). 각 처리 자원 제한.

→ depth 0/1의 50K = "episodic buffer (전체 맥락 통합)" 단계. depth 3+의 8K = "phonological loop (단일 sequence 처리)" 단계. depth에 따라 동원되는 buffer 다름.

### 2. Transformer Quadratic Attention (Vaswani 2017)

> Vaswani, A. et al. (2017). *Attention Is All You Need*. arXiv:1706.03762.

self-attention FLOPs = O(n² · d). LLM throughput에 직접 영향.

→ 8K vs 50K token 처리 비용 = ~39× (단순 양적 비율로는 6.25× 이지만 attention quadratic으로 39×). depth 3+를 *최소 비용 layer*로 두는 것은 throughput 최적화.

### 3. Goldilocks Zone (Pinker 1994, Steels 2003)

> Steels, L. (2003). *The Evolution of Communication Systems by Adaptive Agents*. Springer.

*적정선* 원리 — 너무 작으면 표현력 부족, 너무 크면 attention 분산. 진화/학습 시스템은 자연스럽게 중간 zone 수렴.

→ 200-500 line / 8K token은 인간 + LLM 양쪽의 *공통 goldilocks*. Sweller cognitive load + transformer cost + 사용자 vibe coding 단위가 *교집합*에서 발생.

### 통합

3 grounding의 교집합:
| Layer | 권장 단위 |
|---|---|
| Baddeley | working memory 4-component fit |
| Vaswani | transformer O(n²) cost optimization |
| Steels | evolutionary goldilocks |
| → 교집합 | depth 3+ = 8K, depth 1-2 = 20K-50K |

# KG: APT_ContextBudget_canonical, MethodologyConfig_default_v26, magic_number_table_v27_A6.1
