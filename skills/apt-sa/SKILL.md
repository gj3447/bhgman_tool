---
name: apt-sa
kg_ref: ATOM_Skill_apt_sa
version: "27.1.0"
channel: stable
description: >
  APT SemanticAnchor (SA) phase — project identity and context bootstrap.
  # KG: ATOM_Skill_apt_sa, APT_v26_RFC_draft_2026-04-21 (A1 MIC slot expansion, A4 MethodologyConfig slot), APT_v25_RFC_draft_2026-04-17
  Invoke when: starting a new project/feature, establishing work identity,
  bootstrapping agent environment, or determining where new work fits in the KG.
  Enforces: Anchor identity, Progressive Disclosure, Context Budget, KG-first exploration.
  v26: Context budget + SA core fields (objective/definition/keyAssertion/C_S/contextBudget) from MethodologyConfig slot (A4). SA→SP gate uses LensSet slot (A3). v22: Gate Check enforcement via Claude Code Hook. 5대 무기(하네스/탈레반/프로메테우스/롱기누스/재배맨) 기반. SA는 프로메테우스(지식 선행)와 롱기누스(KG 접지)의 시작점.
  Active Weapons (2026-05-14): Prometheus `/prom <N> "<sa_topic>"` (Step 1 KG sparse OR Step 3 5 core fields 외부 grounding) + Longinus L1-L2 reverse binding (Step 2 기존 SemanticAnchor 후보 reverse scan). hub-prometheus-research + hub-longinus-reference resolve.
  # KG: lesson-feedback-is-emergent-not-weapon-2026-04-16, lesson-sa-contract-v2-rejected-redesign-2026-04-20 (5 mandatory core fields enforced)
---

## 🎛 v26 A6 Resolve-Only

> Context budget / SA core fields requirement → MethodologyConfig slot resolve. Prose hardcoding 금지.

```cypher
MATCH (cfg:MethodologyConfig {name:'MethodologyConfig_default_v26'})
RETURN cfg.context_budget_sa_default, cfg.context_budget_l1_avg, cfg.context_budget_l2_avg
```

**SA core fields** (v26 mandatory): `objective` · `definition` · `keyAssertion` · `C_S` (5-predicate) · `contextBudget`. 5 필드 null = Taliban gate reject.

# KG: APT_v26_A6_2026-04-21, MethodologyConfig_default_v26

---

## 🎯 v27 A15 — SA Phase Activation Matrix (Work-Kind Routing)

> SA를 *얼마나* 돌릴지 결정. Step 1-2 진입 *전에* work_kind 분류부터.
> A15는 SA *내부* 라우팅(2-A/B/C 새 앵커/재사용/브랜치)과 직교 — A15는 SA *진입* 게이트.

### Work-kind 결정 (사용자 발화 또는 KG 조회)

```cypher
// 사용자가 명시 발화 시: '새 기능' / '기능 확장' / '버그 수정' / '리팩터' / '유지보수'
// 미발화 시 SA bootstrap이 자동 분류:
//   NEW         := 관련 SemanticAnchor 0건
//   EXTEND      := 관련 SemanticAnchor ≥1건 + 새 scope (Step 1-3 결과)
//   MAINTENANCE := 동일 anchor 동일 scope 재진입 (bug fix / refactor / docs)
MATCH (cfg:MethodologyConfig {name:'MethodologyConfig_default_v26'})
RETURN coalesce(cfg.sa_phase_activation_matrix_default, 'auto') AS default_mode
```

### 라우팅 매트릭스 (A15)

| work_kind | SA Phase | 실행 단계 | 후속 |
|-----------|----------|-----------|------|
| **NEW** | **FULL** | Step 1 (KG 탐색) → Step 2-A (새 anchor) → Step 3 (5 core fields + context budget) → SA→SP Gate | SP 진입 |
| **EXTEND** | **SHORT_CIRCUIT** | Step 1-1/1-2 (관련 anchor 조회) → Step 2-B 또는 2-C (재사용/브랜치) → 기존 anchor 5 core fields 검증만 → SA→SP Gate | SP 진입 |
| **MAINTENANCE** | **SKIP** | Step 1-1 (anchor 확인) → 즉시 ST drift-detection 으로 라우팅 (Longinus L7 drift check) | ST drift 모드 진입 |

### Phase Activation 결정 게이트 (Cypher)

```cypher
// 진입 시 work_kind 미정 → 자동 분류 시도
MATCH (sa_candidate:SemanticAnchor) WHERE sa_candidate.name CONTAINS $user_topic
WITH count(sa_candidate) AS hit, collect(sa_candidate.status)[..3] AS statuses
RETURN
  CASE
    WHEN hit = 0 THEN 'NEW'
    WHEN hit >= 1 AND any(s IN statuses WHERE s = 'active') AND $is_drift_scope = false THEN 'EXTEND'
    WHEN hit >= 1 AND $is_drift_scope = true  THEN 'MAINTENANCE'
    ELSE 'NEW'
  END AS work_kind,
  hit AS related_anchor_count
```

### 매트릭스 적용 규약

- 사용자 명시 발화(`work_kind`)는 자동 분류 override.
- **MAINTENANCE 라우팅으로 ST drift 진입 시 SA→SP Gate 우회 가능** — 단, ST에서 `tpa-st` drift check 통과(5종 drift coverage_ratio ≥ 0.8) 필수.
- EXTEND SHORT_CIRCUIT 모드에서도 5 core fields는 검증 (null 발견 시 NEW로 fallback).
- 본 매트릭스는 `MethodologyConfig.sa_phase_activation_matrix_default` slot에서 resolve. Prose 하드코딩 금지.

# KG: oq-prom16-apt-v27-A15-sa-branch-matrix-2026-05-10 (PROVISIONALLY_RATIFIED 2026-05-11), decision-log-blanket-proceed-2026-05-11, lesson-prom16-apt-v26-unresolved-4-issues-2026-04-30 (parent context)

---

## 🔗 MIC Binding (SOLID-DIP)

**IS slot**: APT_Phase (SA, 1/4)
**USES slots**: SubagentSeeder (재배맨 taskspec), AdversarialValidator (SA→SP Gate)

**동적 resolution**:
```cypher
MATCH (mic:MethodologyIntegrationContract {name:'MIC_v1'})-[:HAS_SLOT]->(s:MethodologySlot)
WHERE s.name IN ['SubagentSeeder','AdversarialValidator']
RETURN s.name, s.currentConcrete, s.invocation
```

본문의 `taliban`/`재배맨`/`taskspec`은 MIC slot 현재 스냅샷. 진짜 호출은 `s.invocation`.

# KG: MIC_v1, lesson-apt-not-truly-jaebaeman-2026-04-14

---

## ⚔ Active Weapons — Phase SA (1/5)

> SA 측 활성 5무기 (parent /apt orchestrator §"5무기 Phase Integration Matrix" mirror).

| Step | Weapon | Invocation | Trigger | Output |
|------|--------|-----------|---------|--------|
| Step 1 (KG 탐색) | **Prometheus** | `/prom <N> "<sa_topic> — KG 측 기존 anchor / 외부 정전 grounding"` | INFORMED_BY < `cfg.density_min_informed_by` OR source_types < `cfg.density_min_source_types` | N `ResearchFinding` (verified=true) + grounding citation |
| Step 2 (anchor 결정 2-A/B/C) | **Longinus** | L1-L2 reverse binding: `MATCH (sa:SemanticAnchor) WHERE sa.name CONTAINS $user_topic OR sa.objective CONTAINS $user_topic RETURN sa` | 새 anchor 진입 시 항상 (기존 anchor 중복 방지) | 2-A NEW / 2-B 재사용 / 2-C 브랜치 verdict |
| Step 3 (5 core fields) | **Prometheus** (mini) | `/prom 4 "<keyAssertion> 측 외부 정전 grounding"` (외부 grounding 부재 시) | `keyAssertion` 학문 정전 grounding 없음 | 외부 인용 (1차 source) + Lesson 노드 |
| SA→SP Gate | **Taliban** | `/tlb <SA_id> --lens constitutional` (LensSet completeness mandatory) | 5 core fields 작성 직후 | `VerdictRecord` APPROVED + post-gate reflection |

**SA 진입 hub**: `hub-prometheus-research` (지식 선행 spiral) + `hub-longinus-reference` (KG anchor binding).

# KG: hub-prometheus-research, hub-longinus-reference, MIC_v1.ResearchProvider, MIC_v1.KgCodeBinder

---

# APT SA: SemanticAnchor — Project Identity & Context Bootstrap

## What SA Does

SA answers ONE question: **"이 작업이 정확히 무엇이며, KG에서 어디에 위치하는가?"**

SA는 단순한 이름 붙이기가 아니다. Anthropic의 Initializer Agent 패턴과 동일하게,
후속 Phase가 즉시 이어받을 수 있는 **실행 가능한 환경을 부트스트랩**한다.
SA가 없으면 모든 후속 Phase(SP, ST, SCW)의 기반이 없다 (D9 GenerativeFlowOrdering).

## SA = Inform Axis + Routing Pattern

### Inform 축 (Harness Engineering)

하네스 엔지니어링에서 Inform(정보 제공)은 에이전트에게 컨텍스트를 주입하는 축이다.
SA가 정확히 이 역할을 수행한다:

- **프로젝트 정체성**: 이 작업이 무엇인지 (이름, 도메인, 설명)
- **KG 위치**: 기존 지식과의 관계 (INFORMED_BY 링크, 관련 앵커)
- **실행 환경**: apt-progress.md, feature-spans.json, Context Budget

### Routing 패턴 (Anthropic Flow Patterns)

SA는 Anthropic의 **Routing 패턴**에 대응한다:

1. 입력(사용자 요청)을 분류한다
2. 적절한 앵커/브랜치로 라우팅한다
3. 새 앵커 생성 vs 기존 앵커 재사용 vs 기존 앵커에 브랜치 추가를 결정한다

라우팅 결정이 잘못되면 이후 모든 Phase가 잘못된 컨텍스트에서 진행된다.
**KG 탐색이 라우팅의 핵심**이며, 이것이 Step 1이 존재하는 이유다.

---

## Step 1: KG 탐색 — 기존 앵커 확인

**절대 새 앵커를 먼저 만들지 말 것.** 이것이 SA의 가장 흔한 실수(E-SA1)이다.
먼저 KG에 이미 관련 앵커가 있는지 확인한다.

### 1-1. 기존 SemanticAnchor 전체 목록

```cypher
-- 모든 활성 앵커 조회
MATCH (sa:SemanticAnchor)
RETURN sa.name, sa.description, sa.domain, sa.status,
       sa.context_budget_total, sa.created_at
ORDER BY sa.name
```

결과를 검토하여 현재 작업과 동일하거나 유사한 앵커가 있는지 확인한다.
이름뿐 아니라 description과 domain도 비교해야 한다.

### 1-1b. 전제 검증 — Property-Level Existence (lesson-apt-premise-drift)

ARGUMENTS에 "N개의 X가 있음" 전제가 오면 **실측 확인 필수**. 
Plan은 신호일 뿐, 실측 없는 가정은 Contract target_label 오류로 이어짐.

```cypher
-- 예: ARGUMENTS가 "ResearchFinding에 sourceRF 10건" 가정
MATCH (n:ResearchFinding) WHERE n.sourceRF IS NOT NULL RETURN count(n)
-- 실제 결과가 0이면 다른 라벨 확인:
MATCH (n) WHERE n.sourceRF IS NOT NULL RETURN DISTINCT labels(n), count(n)
```

**모든 L1 Span에 `target_label_verified=true` 필드 강제.** 실측 없이 다음 Phase 진입 금지.
# KG: lesson-apt-premise-drift-researchfinding-vs-subagenttaskspec-2026-04-15

### 1-2. 키워드로 관련 KG 노드 탐색

```cypher
-- 키워드로 관련 작업/개념 탐색
MATCH (n)
WHERE n.name CONTAINS $keyword
   OR n.description CONTAINS $keyword
RETURN n.name, labels(n), n.description
LIMIT 20
```

키워드를 여러 개 시도한다. 프로젝트명, 도메인 용어, 핵심 기술 등.
관련 노드가 나오면 해당 앵커로 라우팅할 수 있는지 검토한다.

### 1-3. 기존 앵커의 Span 트리 확인

```cypher
-- 특정 앵커의 하위 구조 확인
MATCH (sa:SemanticAnchor {name: $sa_name})-[:HAS_ROOT]->(root)
OPTIONAL MATCH (root)-[:DECOMPOSES_TO*1..3]->(s)
RETURN sa.name, sa.description,
       root.name AS root_span,
       s.name AS child_span, s.depth, s.status
ORDER BY s.depth, s.name
```

기존 앵커에 현재 작업이 브랜치로 들어갈 수 있는지 판단한다.
이미 유사한 Span이 있다면 새 앵커 대신 기존 구조에 합류한다.

### 라우팅 결정 매트릭스

| 상황 | 결정 | Step 2 분기 |
|------|------|------------|
| 동일 앵커 존재 + active | 기존 앵커 재사용 | Step 2-B |
| 유사 앵커 존재 + 다른 scope | 기존 앵커에 브랜치 추가 | Step 2-C |
| 관련 앵커 없음 | 새 앵커 생성 | Step 2-A |
| 동일 앵커 존재 + archived | 새 앵커 생성 (이전 앵커 참조) | Step 2-A |

---

## Step 2: 앵커 결정

### 2-A. 새 앵커 생성

KG 탐색 결과 관련 앵커가 없을 때만 실행한다.

```cypher
-- 새 SemanticAnchor 생성 (항상 MERGE로 중복 방지)
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

앵커 생성 직후 Root Span을 연결한다:

```cypher
-- Root Span 생성 및 연결
MATCH (sa:SemanticAnchor {name: $project_name, status: 'active'})
MERGE (root:AptSpan {name: 'SPAN_' + $project_name + '_ROOT'})
SET root.description   = $root_description,
    root.depth         = 0,
    root.status        = 'open',
    root.context_budget = 50000,
    root.created_at    = datetime()
MERGE (sa)-[:HAS_ROOT]->(root)
RETURN root
```

### 2-B. 기존 앵커 재사용

동일 앵커가 이미 존재하고 active인 경우. updated_at만 갱신한다.

```cypher
MATCH (sa:SemanticAnchor {name: $existing_sa, status: 'active'})
SET sa.updated_at = datetime()
RETURN sa
```

### 2-C. 기존 앵커에 브랜치 추가

기존 앵커의 Root Span 하위에 새로운 L1 브랜치를 추가한다.

```cypher
-- 기존 앵커의 Root에 새 브랜치 추가
MATCH (sa:SemanticAnchor {name: $existing_sa})-[:HAS_ROOT]->(root)
MERGE (branch:AptSpan {name: $new_branch_name})
SET branch.description   = $description,
    branch.depth         = 1,
    branch.status        = 'open',
    branch.context_budget = 50000,
    branch.created_at    = datetime()
MERGE (root)-[:DECOMPOSES_TO]->(branch)
RETURN branch
```

---

## SA as System Index (D17)

SA는 고립된 정체성 노드가 아니다. **전체 시스템의 인덱스**다.

SA는 생성 시점부터 연결되어야 하고, 나중에 발견한 연결도 **소급 추가**한다.

### 필수 연결

```cypher
// 도메인 지식 연결
MATCH (sa:SemanticAnchor {name: $project})
MERGE (k:KnowledgeNode {name: $knowledge})
MERGE (sa)-[:INFORMED_BY {reason: $why}]->(k)

// 기술 스택 연결
MERGE (lib:KnowledgeNode {name: $library, source: 'library'})
MERGE (sa)-[:USES {reason: $why}]->(lib)

// 다른 프로젝트 연결
MATCH (other:SemanticAnchor {name: $related_project})
MERGE (sa)-[:RELATED_TO {reason: $why}]->(other)

// 인프라 연결
MERGE (infra:KnowledgeNode {name: $service, source: 'infrastructure'})
MERGE (sa)-[:DEPLOYED_ON]->(infra)
```

### 연결 종류

| Relation | 대상 | 예시 |
|----------|------|------|
| INFORMED_BY | 도메인 지식, 디자인 패턴 | SA → "ECS Pattern", "REST API Design" |
| USES | 라이브러리, 프레임워크, 외부 API | SA → "Three.js", "FastAPI", "PostgreSQL" |
| RELATED_TO | 다른 프로젝트 SA | SA → 다른 SA (공유 라이브러리, 마이크로서비스 간) |
| DEPLOYED_ON | 실행 환경 | SA → "Browser", "Jetson", "AWS Lambda" |
| OWNED_BY | 팀, 담당자 | SA → "TeamAlpha" |

### 소급 연결 규칙

**"아 이거 연결했어야 했는데"** 발견하면 **즉시 추가**:
```cypher
// 나중에 발견한 연결 추가
MATCH (sa:SemanticAnchor {name: $project})
MERGE (k:KnowledgeNode {name: $discovered_connection})
MERGE (sa)-[:INFORMED_BY {reason: $why, retroactive: true, discovered_at: datetime()}]->(k)
```

SA 연결 = **시스템 아키텍처 맵**. 전체 시스템 구조를 볼 때 SA의 연결을 보면 이 프로젝트가 어디에 위치하는지 한눈에 파악 가능.

---

## Step 3: Progressive Disclosure — 3단계 로딩

Context Rot(토큰 증가 시 n^2으로 주의력 분산) 방지를 위해 컨텍스트를 단계적으로 로드한다.
**절대 KG 전체를 한번에 로드하지 않는다** (E-SA2).

### L1: 메타데이터 (토큰 예산 ~2K)

프로젝트 정체성과 최상위 Span 이름/설명만 로드한다. KG 전체를 읽지 않는다.

```cypher
-- L1: SA + 직계 자식 메타데이터만
MATCH (sa:SemanticAnchor {name: $sa_name})-[:HAS_ROOT]->(root)
OPTIONAL MATCH (root)-[:DECOMPOSES_TO]->(l1)
RETURN sa.name, sa.description, sa.domain, sa.status,
       root.name AS root_span,
       l1.name AS l1_span, l1.description AS l1_desc, l1.depth
ORDER BY l1.name
```

**포함 항목:** SA name, description, domain, status, Root Span, L1 Span 이름/설명
**제외 항목:** Span 트리 구조, Contract, 소스코드, 테스트 결과

### L2: 구조 (토큰 예산 ~5K)

선택된 브랜치의 Span 트리와 Contract 존재 여부를 로드한다. **작업 대상 브랜치만** 로드한다.

```cypher
-- L2: 선택된 브랜치의 Span 트리 + Contract 존재 여부
MATCH (root:AptSpan {name: $branch})-[:DECOMPOSES_TO*1..5]->(s)
OPTIONAL MATCH (s)-[:CRYSTALLIZES_TO]->(st)-[:HAS_CONTRACT]->(c)
RETURN s.name, s.depth, labels(s) AS labels, s.status,
       c.name AS contract, c.status AS contract_status
ORDER BY s.depth, s.name
```

**포함 항목:** Span 계층 구조, 각 Span의 상태, AtomicSpan 라벨 여부, Contract 존재 여부
**제외 항목:** Contract 상세 필드(input/output type 등), 소스코드, 테스트 결과

### L3: 상세 (토큰 예산 ~8K)

특정 AtomicSpan의 Contract 전문, Task 상세, 소스코드 메타데이터를 로드한다.
SA 단계에서는 보통 L3까지 갈 필요가 없다. 기존 앵커를 재사용할 때 특정 Span의 상태를 확인할 때만 사용.

```cypher
-- L3: 특정 AtomicSpan 상세
MATCH (atom:AtomicSpan {name: $atom})-[:CRYSTALLIZES_TO]->(st)-[:HAS_CONTRACT]->(c)
OPTIONAL MATCH (st)-[:HAS_TASK]->(t)
OPTIONAL MATCH (c)-[:MATERIALIZES]->(src)
RETURN c.name, c.input_type, c.output_type,
       c.precondition, c.postcondition,
       c.acceptance_criteria, c.target_file,
       c.nfr_latency_p99_ms, c.nfr_memory_mb,
       c.nfr_accuracy_metric, c.nfr_execution_env,
       t.description, t.acceptance_criteria, t.impact_tests,
       src.file_path, src.lines, src.status
```

**포함 항목:** Contract 7대 필드, NFR, Task 상세, 소스코드 메타데이터
**제외 항목:** 다른 Span의 정보, KG 탐색 이력

### 로딩 순서 규칙

1. 항상 L1부터 시작한다
2. L1 결과를 보고 작업 대상 브랜치를 결정한 후 해당 브랜치만 L2 로드한다
3. L2에서 특정 AtomicSpan을 확인해야 할 때만 L3를 로드한다
4. **절대 L1을 건너뛰고 L2/L3로 직행하지 않는다**

---

## Step 4: Context Budget 할당

SA에서 전체 프로젝트의 depth별 토큰 예산을 할당한다.
이 예산은 인지과학이 아닌 **공학적 휴리스틱**(C26)이다.

### Depth별 토큰 예산

| Span Depth | 토큰 예산 | 근거 |
|:----------:|:---------:|------|
| 0 (Root)   | 50,000    | 프로젝트 전체 개요. L1 메타 + L2 구조 |
| 1          | 50,000    | 주요 모듈. 넉넉한 컨텍스트 필요 |
| 2          | 20,000    | 서브모듈. 범위가 좁아짐 |
| 3+         | 8,000     | AtomicSpan. 단일 파일 500줄 구현에 적정 |

### 할당 Cypher

```cypher
-- SA에 Context Budget 총량 설정
MATCH (sa:SemanticAnchor {name: $sa_name})
SET sa.context_budget_total    = 100000,
    sa.context_budget_per_span = 8000

-- Span 생성 시 depth 기반 자동 할당
MERGE (child:AptSpan {name: $name})
SET child.context_budget = CASE
  WHEN child.depth = 0 THEN 50000
  WHEN child.depth = 1 THEN 50000
  WHEN child.depth = 2 THEN 20000
  ELSE 8000 END
```

### Budget 초과 시 대응

- depth 0~1에서 50K 초과: L2 로딩 범위를 줄인다 (전체 트리 대신 작업 브랜치만)
- depth 2에서 20K 초과: 형제 Span 정보를 제거하고 대상 Span만 유지
- depth 3+에서 8K 초과: Span이 아직 atomic하지 않을 가능성. SP에서 추가 분해 검토

---

## Step 5: Initializer Bootstrap

SA 완료 시 후속 Phase를 위한 파일을 생성한다.

### 5-1. apt-progress.md 생성

세션 연속성의 핵심 파일. 모든 Phase에서 참조하고 갱신한다.

```markdown
# APT Progress: {project_name}

## Anchor: {sa_name}
## Domain: {domain}
## Status: active
## Created: {datetime}
## Last Updated: {datetime}
## Context Budget: total={total}K, per_span={per_span}K

---

### Completed Spans
(none yet)

### In Progress
- {current_span}: SA complete, ready for SP

### Blocked
(none)

### KG Stats
- SemanticAnchor: {sa_name}
- L1 Spans: {count}
- INFORMED_BY links: {count}

### Next Steps
1. SP Phase: {first_branch} 분해 시작
2. 각 L1 Span에 INFORMED_BY >= 5 확보

### Session Log
- [{datetime}] SA Phase: anchor {sa_name} created/reused
```

### 5-2. feature-spans.json 생성 (선택)

대규모 프로젝트에서 Span 목록을 구조화된 형태로 관리할 때 사용.

```json
{
  "anchor": "{sa_name}",
  "domain": "{domain}",
  "created_at": "{datetime}",
  "spans": [
    {
      "name": "SPAN_{project}_ROOT",
      "description": "...",
      "status": "open",
      "depth": 0,
      "context_budget": 50000
    }
  ]
}
```

### 5-3. 기존 파일이 있는 경우

기존 앵커를 재사용하는 경우(Step 2-B) apt-progress.md가 이미 존재한다.
이 경우 새로 생성하지 않고, Session Log에 현재 세션 기록만 추가한다.

---

## Step 6: Git Commit

SA 결과물을 커밋한다. 이것이 SA의 마지막 단계.

```bash
git add apt-progress.md feature-spans.json
git commit -m "APT SA: Initialize {project_name} anchor

- SemanticAnchor: {sa_name}
- Domain: {domain}
- Context Budget: {total}K total, {per_span}K per span
- L1 Spans: {count}"
```

기존 앵커 재사용 시:

```bash
git add apt-progress.md
git commit -m "APT SA: Resume {project_name} - {branch_description}"
```

---

## SA -> SP 핸드오프

SA에서 SP로 전환하기 전 **모든 항목**을 확인한다.

### 핸드오프 체크리스트

| # | 체크 항목 | 검증 방법 |
|---|----------|----------|
| 1 | SemanticAnchor가 KG에 존재 | `MATCH (sa:SemanticAnchor {name: $sa}) RETURN sa` |
| 2 | SA status = 'active' | `sa.status = 'active'` 확인 |
| 3 | Root Span이 SA에 연결됨 | `MATCH (sa)-[:HAS_ROOT]->(root) RETURN root` |
| 4 | Progressive Disclosure L1 로드됨 | apt-progress.md에 L1 Span 목록 기재 확인 |
| 5 | Context Budget 할당됨 | `sa.context_budget_total IS NOT NULL` |
| 6 | apt-progress.md 생성됨 | 파일 존재 확인 |
| 7 | 기존 앵커 중복 없음 | Step 1의 KG 탐색으로 유사 앵커 부재 확인 |
| 8 | Git commit 완료 | `apt-progress.md` 커밋됨 |

### 핸드오프 검증 쿼리

```cypher
-- 핸드오프 준비 상태 종합 확인
MATCH (sa:SemanticAnchor {name: $sa_name, status: 'active'})
MATCH (sa)-[:HAS_ROOT]->(root:AptSpan)
WHERE sa.context_budget_total IS NOT NULL
RETURN sa.name, sa.status, sa.context_budget_total,
       root.name AS root_span, root.status AS root_status
```

결과가 없으면 핸드오프 차단. 어떤 조건이 실패했는지 개별 쿼리로 확인해야 한다.

---

## Phase Transition Compaction: SA -> SP

SA 완료 후 SP로 전환할 때 컨텍스트를 압축한다.

### 보존 (SP에 전달)

- 앵커 이름, 설명, 도메인
- L1 Span 목록 (이름 + 설명)
- Context Budget 설정
- apt-progress.md 현재 상태

### 제거 (메모리에서 해제)

- KG 탐색 과정 (어떤 쿼리를 실행했는지)
- 앵커 후보 비교 로그
- 라우팅 의사결정 과정
- L2/L3 로딩 결과 (SP에서 필요할 때 다시 로드)

### 새 컨텍스트 (SP 시작 시 로드)

- SA 결과 압축 요약 (앵커명 + 도메인 + L1 구조 1줄 요약)
- 최근 5개 접근 파일 경로
- SP Phase 시작에 필요한 첫 번째 브랜치 정보

---

## Validation Queries

SA 관련 무결성을 검증하는 쿼리들. 문제 발생 시 사용한다.

### V-SA1: 고아 Root Span (SA 미연결)

```cypher
MATCH (root:AptSpan)
WHERE root.depth = 0
  AND NOT ()-[:HAS_ROOT]->(root)
RETURN 'V_SA1_OrphanRoot' AS validation, root.name
```

### V-SA2: SA 중복 (동일 프로젝트 이름)

```cypher
MATCH (sa:SemanticAnchor)
WITH sa.name AS sa_name, count(sa) AS cnt
WHERE cnt > 1
RETURN 'V_SA2_DuplicateAnchor' AS validation, sa_name, cnt
```

### V-SA3: Root Span이 없는 SA

```cypher
MATCH (sa:SemanticAnchor {status: 'active'})
WHERE NOT (sa)-[:HAS_ROOT]->()
RETURN 'V_SA3_NoRoot' AS validation, sa.name
```

### V-SA4: Context Budget 미할당

```cypher
MATCH (sa:SemanticAnchor {status: 'active'})
WHERE sa.context_budget_total IS NULL
RETURN 'V_SA4_NoBudget' AS validation, sa.name
```

---

## v21 Rules (SA Phase)

SA는 5대 무기 중 **프로메테우스(지식 선행)**와 **롱기누스(KG 접지)**의 시작점.
<!-- # KG: onto-apt-5weapons, weapon-prometheus, weapon-longinus -->

| Rule | SA에서의 의미 |
|------|-------------|
| HR11 (증거 필수) | SA 생성 시 KG 조회 증거 필수. "KG에 없었다"도 증거 |
| HR14 (Reflection) | SA 완료 후: "이 앵커의 약점은?" 기록 → SP 진입 시 참조 |

```cypher
-- v21: SA 완료 후 Reflection 기록
MATCH (sa:SemanticAnchor {name: $project})
SET sa.v21_reflection = $weakness,
    sa.v21_reflectedAt = datetime()
```

---

## What NOT to Do

| 금지 사항 | 이유 | 해당 Phase |
|----------|------|-----------|
| 코드 작성 | 코드는 SCW(PH5)의 책임 | SCW |
| Span 분해 | 분해는 SP(PH3)의 책임 | SP |
| Contract 정의 | Contract는 ST(PH4)의 책임 | ST |
| KG 탐색 없이 앵커 생성 | 중복 앵커가 가장 흔한 SA 오류(E-SA1) | - |
| 전체 KG 한번에 로드 | Context Rot 발생(E-SA2). Progressive Disclosure 위반 | - |
| apt-progress.md 없이 SP 진입 | 세션 연속성 단절. 다음 에이전트가 컨텍스트를 잃음 | - |
| CREATE 사용 (MERGE 대신) | 중복 노드 생성 위험. 항상 MERGE 사용 | - |

---

## 🌱 재배맨 v2 (MIC Slot Reference — 로직 복제 금지)

> 이 스킬의 subagent 운용은 **MIC_v1.SubagentSeeder** slot을 통해 resolve된다.
> 아래는 thin resolver. 로직 복제 = drift 유발.

### Slot Resolve
```cypher
MATCH (mic:MethodologyIntegrationContract {name:'MIC_v1'})-[:HAS_SLOT]->(s:MethodologySlot {name:'SubagentSeeder'})
RETURN s.currentConcrete, s.invocation, s.protocol
```

### 부모 Pre-fetch (v2 — MCP 우회)
```cypher
MATCH (l:Lesson)-[:HAS_RESEARCH]->(rf:ResearchFinding)
WHERE l.name CONTAINS $keyword RETURN rf.name, rf.domain, rf.oneLineSummary LIMIT 20
MATCH (ts:SubagentTaskSpec {skill:'apt-sa'}) WHERE ts.status='READY'
RETURN ts.name, ts.role LIMIT 10
```

### WorkBuffer 연속성
```cypher
MATCH (wb:WorkBuffer {status:'CURRENT'}) RETURN wb
```

# KG: ATOM_재배맨_v2_apt-sa, SA_methodology_v4_triple_upgrade

---

## MIC Binding Disclaimer

> 이 SKILL.md에서 "Prometheus", "Taliban", "Longinus", "재배맨" 등의
> concrete 이름은 MIC_v1 MethodologySlot의 **현재 바인딩(currentConcrete)**이다.
> 88-Taliban은 별도 concrete가 아닌 Taliban --lens mathematical.
> Slot이 다른 concrete로 교체되면 이 파일의 이름도 drift한다.
> 정본 해석: `MATCH (mic:MethodologyIntegrationContract {name:'MIC_v1'})-[:HAS_SLOT]->(s) RETURN s.name, s.currentConcrete`
> 유틸리티: `03_SCRIPTS/db/resolve_mic_slot.cypher`
> # KG: lesson-skill-mic-slot-ref-weak-2026-04-15

---

## History

> Repo-level changes: [`/CHANGELOG.md`](../CHANGELOG.md). Per-commit: `git log -- apt-sa/SKILL.md`.
> Architecture: Progressive Disclosure v3 — references split into focused files (2026-05-11):
> - SA *internal* routing (Step 1-2 matrix, A15 work_kind): [`references/routing_decisions.md`](references/routing_decisions.md)
> - `apt-progress.md` initial template (incl. v27 A15 fields): [`references/progress_template.md`](references/progress_template.md)
> - SA → SP handoff 8-check + A15 추가 3-check: [`references/handoff_to_sp.md`](references/handoff_to_sp.md)
> - Cross-skill shared concepts: [`../_common/`](../_common/) (progressive_disclosure / context_budget / phase_transition_compaction / validation_query_pattern / error_pattern_template / contract_lifecycle_fsm / kafka_event_convention)
> - Legacy single-file (kept as redirect): `references/sa_world.md` → see split files above.

| Version | Date | Summary | KG Ref |
|---|---|---|---|
| **v26** | 2026-04 | A1 MIC slot expansion (7→10) + A4 MethodologyConfig slot. Context Budget + SA core fields (objective/definition/keyAssertion/C_S/contextBudget) | `APT_v26_RFC_draft_2026-04-21`, `lesson-sa-contract-v2-rejected-redesign-2026-04-20` |
| **v22** | 2026-04 초 | Gate Check enforcement via Claude Code Hook | `lesson-feedback-is-emergent-not-weapon-2026-04-16` |
| **v5~v21** | timestream | SA = 프로메테우스(지식 선행) + 롱기누스(KG 접지) 의 시작점 | — |

# KG history: ATOM_Skill_apt_sa / lesson-prom16-skill-versioning-academic-2026-04-29 / lesson-prom16-skillver-progressive-disclosure-drift-2026-04-29
