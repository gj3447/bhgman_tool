# SA Routing Decisions (Phase-Specific)

> apt-sa Phase 1/4의 *내부* 라우팅 매트릭스. Step 1 (KG 탐색) → Step 2 (앵커 결정) 의 cypher와 결정 표.
>
> **외부 진입 게이트 (work_kind NEW/EXTEND/MAINTENANCE)** 는 SKILL.md `🎯 v27 A15` 절 참조 — A15가 *SA 진입 여부* 결정, 본 문서는 *SA 내부* 라우팅.

---

## Step 1: KG 탐색

### 1-1. 동일 이름 앵커 확인

```cypher
MATCH (sa:SemanticAnchor {name: $candidate_name})
RETURN sa.name, sa.status, sa.description, sa.domain
```

### 1-2. 유사 키워드 앵커 탐색

```cypher
MATCH (sa:SemanticAnchor)
WHERE sa.name CONTAINS $keyword
   OR sa.description CONTAINS $keyword
RETURN sa.name, sa.description, sa.status,
       size((sa)-[:HAS_ROOT]->()-[:DECOMPOSES_TO*]->()) AS tree_size
ORDER BY tree_size DESC
LIMIT 5
```

### 1-3. 기존 앵커의 Span 트리 확인

```cypher
MATCH (sa:SemanticAnchor {name: $existing_sa})-[:HAS_ROOT]->(root)-[:DECOMPOSES_TO*0..3]->(s)
RETURN s.name, s.depth, s.description, s.status
ORDER BY s.depth, s.name
```

---

## Step 2: 라우팅 결정 매트릭스

| 상황 | 결정 | Step 2 분기 |
|------|------|------------|
| 동일 앵커 존재 + active | 기존 앵커 재사용 | Step 2-B |
| 유사 앵커 존재 + 다른 scope | 기존 앵커에 브랜치 추가 | Step 2-C |
| 관련 앵커 없음 | 새 앵커 생성 | Step 2-A |
| 동일 앵커 존재 + archived | 새 앵커 생성 (이전 앵커 참조) | Step 2-A |

---

## Step 2-A: 새 앵커 생성

```cypher
MERGE (sa:SemanticAnchor {name: $project_name})
SET sa.description         = $description,
    sa.domain              = $domain,
    sa.status              = 'active',
    sa.context_budget_total = 100000,
    sa.context_budget_per_span = 8000,
    sa.created_at          = datetime(),
    sa.updated_at          = datetime()
RETURN sa
```

Root Span 즉시 연결:

```cypher
MATCH (sa:SemanticAnchor {name: $project_name, status: 'active'})
MERGE (root:AptSpan {name: 'SPAN_' + $project_name + '_ROOT'})
SET root.description    = $root_description,
    root.depth          = 0,
    root.status         = 'open',
    root.context_budget = 50000,
    root.created_at     = datetime()
MERGE (sa)-[:HAS_ROOT]->(root)
RETURN root
```

---

## Step 2-B: 기존 앵커 재사용

```cypher
MATCH (sa:SemanticAnchor {name: $existing_sa, status: 'active'})
SET sa.updated_at = datetime()
RETURN sa
```

EXTEND work_kind (A15)에서 typical path. 5 core fields 검증만 추가 수행 (모두 채워져 있는지).

---

## Step 2-C: 기존 앵커에 브랜치 추가

```cypher
MATCH (sa:SemanticAnchor {name: $existing_sa})-[:HAS_ROOT]->(root)
MERGE (branch:AptSpan {name: $new_branch_name})
SET branch.description    = $description,
    branch.depth          = 1,
    branch.status         = 'open',
    branch.context_budget = 50000,
    branch.created_at     = datetime()
MERGE (root)-[:DECOMPOSES_TO]->(branch)
RETURN branch
```

depth=1 자동 설정. Context Budget도 depth 공식([_common/context_budget.md](../../_common/context_budget.md)) 자동 적용.

---

## A15와 Step 2의 상호 작용

A15 work_kind 별로 typical Step 2 분기:

| A15 work_kind | Typical Step 2 |
|---|---|
| **NEW** | Step 2-A (새 앵커) — 관련 anchor=0 case |
| **EXTEND** | Step 2-B (재사용) OR 2-C (브랜치) — 관련 anchor≥1 case |
| **MAINTENANCE** | **Step 2 우회**, ST drift-detection으로 직행 — A15 SHORT_CIRCUIT_BYPASS |

A15 매트릭스 전체는 `apt-sa/SKILL.md` 의 `🎯 v27 A15` 절 참조.

---

## phase 고유 anti-pattern

[_common/error_pattern_template.md](../../_common/error_pattern_template.md) 양식 따라:

### E-SA1: KG 중복 앵커
**Context:** Step 1 KG 탐색 없이 Step 2-A 직행. 기존 동일/유사 앵커 존재.
**Lesson:** Step 1 → Step 2 순서 강제. MERGE도 동명 SA에 대해 새 SA 만들지 않음 (그것이 옳음). 문제는 *의미적으로 유사한* SA를 발견 못 함.
**Guard:** Step 1-1 (동일 이름) + 1-2 (키워드) 둘 다 실행. 결과 0행이어야 Step 2-A 진입.

### E-SA-Routing-1: A15 work_kind 분류 누락
**Context:** SA 진입 즉시 Step 1로 들어감. work_kind (NEW/EXTEND/MAINTENANCE) 분류 누락.
**Lesson:** A15 분류가 Step 2 분기를 사전 안내. MAINTENANCE면 Step 2 자체를 우회 (ST drift 직행) — 분류 없으면 불필요한 Step 2-A 실행.
**Guard:** SA SKILL.md 진입 시 A15 자동 분류 cypher 우선 실행. 분류 결과를 PhaseHandoff payload 에 기록.

---

## 검증 query

[_common/validation_query_pattern.md](../../_common/validation_query_pattern.md) 양식 따라:

### V-SA1: OrphanRoot
```cypher
MATCH (root:AptSpan) WHERE root.depth = 0 AND NOT ()-[:HAS_ROOT]->(root)
RETURN 'V_SA1_OrphanRoot' AS validation, root.name AS orphan_root
```

### V-SA2: DuplicateAnchor
```cypher
MATCH (sa:SemanticAnchor)
WITH sa.name AS sa_name, count(sa) AS cnt
WHERE cnt > 1
RETURN 'V_SA2_DuplicateAnchor' AS validation, sa_name, cnt
```

### V-SA3: SA without Root Span
```cypher
MATCH (sa:SemanticAnchor {status: 'active'})
WHERE NOT (sa)-[:HAS_ROOT]->()
RETURN 'V_SA3_NoRoot' AS validation, sa.name AS anchor_without_root
```

### V-SA4: Context Budget 미할당
```cypher
MATCH (sa:SemanticAnchor {status: 'active'})
WHERE sa.context_budget_total IS NULL
RETURN 'V_SA4_NoBudget' AS validation, sa.name
```

### V-SA5 (A15 추가): work_kind 미기록
```cypher
MATCH (sa:SemanticAnchor {status: 'active'})
WHERE sa.created_via_work_kind IS NULL
RETURN 'V_SA5_NoWorkKindRecord' AS validation, sa.name
```

# KG: APT_SA_routing_canonical, oq-prom16-apt-v27-A15-sa-branch-matrix-2026-05-10
