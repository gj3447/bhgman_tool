---
name: apt-sp
kg_ref: ATOM_Skill_apt_sp
version: "27.1.0"
channel: stable
description: >
  APT SemanticPyramid (SP) — recursive Span decomposition.
  SP is ONE world. Spans are DAG nodes (N:N, not tree).
  D(S) recurrence until ALL leaves satisfy C(S) 5-predicate = AtomicSpan.
  Then Crystallization Frontier → ST.
  v26: C(S) 5-predicate fields (objective/definition/keyAssertion/verification/c_s_predicate) MUST be non-null on every Span. v26 A3/A5: SP→ST gate enforces LensSet completeness via Cypher (lesson-taliban-shortcut-antipattern-2026-04-21). δ_infra exception via ATOM_APT_delta_infra_exception_2026-04-21. Magic number 500/200-500 → MethodologyConfig slot (A4).
  v24: KG 정본 기반 재설계. v5~v21 AptClarificationNote 22개 반영.
  # KG: ATOM_Skill_apt_sp, CONTRACT_apt_sp, APT_v26_RFC_draft_2026-04-21, lesson-taliban-shortcut-antipattern-2026-04-21
---

## 🎛 v26 A6 Resolve-Only

> Sweet spot band (`{{cfg.vibe_coding_sweet_min}}`-`{{cfg.vibe_coding_sweet_max}}` line, 현재 200-500) / δ_infra exception / span_depth_max — **하드코딩 금지**. MethodologyConfig slot resolve.

```cypher
// Sweet spot + hard max
MATCH (cfg:MethodologyConfig {name:'MethodologyConfig_default_v26'})
RETURN cfg.vibe_coding_sweet_min, cfg.vibe_coding_sweet_max, cfg.vibe_coding_hard_max, cfg.infra_relaxation_min

// δ_infra exception rule
MATCH (atom:ATOM {name:'ATOM_APT_delta_infra_exception_2026-04-21'}) RETURN atom.rule

// SP→ST gate lens completeness
MATCH (vr:ValidationResult)-[:USED_LENS]->(ls:LensSet {name:'constitutional-9-full'})
WHERE ls.deprecated <> true RETURN vr, ls.lensCount

// v0.8.A1 ensemble option (2026-05-05, opt-in via APT_GATE_VERSION=v08-A1)
// — single-LensSet borderline → ensemble UNION concern-coverage>=0.8
// — Taliban gate: prefer Agent(taliban-ensemble-critic) over single /taliban call
MATCH (rfc:MethodologyRFC {name:'rfc-taliban-v08-concern-coverage-2026-05-04'})
RETURN rfc.status
```

**C(S) 5-predicate fields** (non-null 필수): `objective` · `definition` · `keyAssertion` · `verification` · `c_s_predicate`. 누락 = Taliban reject. # KG: APT_v26_A6_2026-04-21, lesson-taliban-shortcut-antipattern-2026-04-21

---

## 🔗 MIC Binding (SOLID-DIP)

**IS slot**: APT_Phase (SP, 2/4)
**USES slots**: SubagentSeeder, AdversarialValidator

**동적 resolution**:
```cypher
MATCH (mic:MethodologyIntegrationContract {name:'MIC_v1'})-[:HAS_SLOT]->(s:MethodologySlot)
WHERE s.name IN ['SubagentSeeder','AdversarialValidator']
RETURN s.name, s.currentConcrete, s.invocation
```

# KG: MIC_v1, lesson-apt-not-truly-jaebaeman-2026-04-14

---

# /apt-sp — SemanticPyramid: Recursive Span Decomposition

> **SP = 1개의 세계.** Span들이 레이어(L1→Ln)로 배치.
> D(S)로 재귀 분해. 모든 leaf가 AtomicSpan이 될 때까지 반복.
> 코드 없음. Contract 없음. 분해와 탐색만.

## ⛔ GATE CHECK (Hook 강제)

> `apt-gate-check.sh`가 자동 실행. SA Gate 미통과 시 `permissionDecision: deny`.
> `$PROJECT`는 apt-progress.md의 `## Anchor:` 에서 읽는다.
> BLOCKED 시: `/apt-sa` → `/taliban` → SA Gate 통과 → `/apt-sp` 재호출.

---

## SP의 4가지 규칙

### Rule 1: SpanPlanningNature — Span은 의미 단위

Span은 코드 아티팩트가 아닌 **의미(semantic) 단위**다.
- GOOD: "사용자 인증" — 의미 단위
- BAD: "auth.py" — 코드 아티팩트
- BAD: "AuthService 클래스 구현" — 구현 수준

상위 Span = 하위 Span을 만들기 위한 계획. 그 이상도 이하도 아님.

### Rule 2: DAG, Not Tree — N:N 관계

Span은 **반드시 트리일 필요 없다**. 핵심은 레이어(L1, L2, ..., Ln)가 있다는 것.
하나의 Span이 여러 부모를 가질 수 있다 (DAG).
INFORMED_BY로 외부 지식(디자인 패턴, 기술, 도메인 개념)이 연결된다.

### Rule 3: A3 — 같은 레이어의 형제는 완전 독립

같은 레이어의 형제 Span 사이에 의존성 금지.
의존이 발생하면 → 분해 오류. 상위로 올려서 재분해.
**DP의 independent subproblems = APT의 sibling independence.**

### Rule 4: TerminationGuarantee — 유한 단계에서 반드시 AtomicSpan 도달

모든 분해 경로는 유한 단계에서 AtomicSpan에 도달해야 한다.

---

## D(S) — Decomposition Function

```
D(S) = {S₁, S₂, ..., Sₙ} where n ≥ 2 (BranchingInvariant)

반복:
  for each leaf S in SP:
    if C(S) = true:  → mark as AtomicSpan (더 이상 분해 안 함)
    else:            → D(S) 적용 (하위 Span 생성)
  until ALL leaves are AtomicSpan
```

**DP 대응**: Span DAG = dependency DAG. DECOMPOSES_TO = subproblem 분해.
AtomicSpan = base case. Contract = subproblem 간 합의된 interface.

---

## C(S) — 5-Predicate Crystallization Condition

**모든 5개를 만족해야 AtomicSpan.**

| # | Sym | Criterion | Auto/Human | 실패 시 |
|:-:|:---:|-----------|:----------:|---------|
| 1 | ν | Complexity ≤ `cfg.vibe_coding_hard_max` | auto | Split |
| 2 | τ | Type expressibility — 구체적 I/O 타입 | auto | Split by type boundary |
| 3 | ι | Test feasibility — 구체적 assertion 작성 가능 | auto | 예시로 명확화 |
| 4 | δ | Decomposition diseconomy — 100줄 미만이면 합병 | auto | Merge upward |
| 5 | σ | Semantic completeness — 의미 완결 | human | Narrow scope |

### δ (Decomposition Diseconomy) 상세

- **Sweet spot: `{{cfg.vibe_coding_sweet_min}}`~`{{cfg.vibe_coding_sweet_max}}` (현재 200~500줄)**
- 100줄 미만: 상위 Span과 합병 (독립 의미 단위로 존재할 이유 없음)
- `cfg.vibe_coding_hard_max` 초과: 더 분해 필요 (바이브코딩 최적 단위 초과)

### 인프라 파일 예외 규칙 (Infra-Specific C(S))

> YAML, Dockerfile, Helm chart, Terraform 같은 **선언형 인프라 스펙**은 일반 τ/ι 로는 판정 불가.
> 입력·출력 타입이 함수 시그니처가 아닌 **리소스 상태(resource state)**이기 때문.
> `kind IN ['K8sDeploy','HelmChart','DockerImage','Terraform','ConfigMap']`이면 아래 규칙 적용.

| # | Sym | 일반 판정 | 인프라 판정 (대체) |
|:-:|:---:|----------|-------------------|
| 2 | τ | 구체적 I/O 타입 | **τ_infra**: 적용 후 상태 = 명세와 일치하는가 (`Deployment.spec ↔ 실제 Pod 상태`) |
| 3 | ι | 함수 반환값 assertion | **ι_infra**: `kubectl apply --dry-run=server` 성공 + 예상 리소스 생성 확인 |

**Taliban SP gate**: `kind`가 인프라 계열이면 `--lens infra`(infra-specific LensSet) 자동 적용. 일반 constitutional 렌즈로 판정 시 false positive 위험(YAML/Dockerfile τ 미충족으로 오판).

예: `ATOM_Landing_K8sDeploy` AtomicSpan의 Contract는 `input: yaml_manifest, output: k8s_resource_state_hash`. Task acceptance = `kubectl diff` empty + `kubectl apply --dry-run=server` 통과.

# KG: lesson-apt-sp-k8sdeploy-cs-predicate-infra-2026-04-16

### LeafSpan ≠ AtomicSpan

- **LeafSpan**: 현재 하위 DECOMPOSES_TO가 없는 Span. **상태**일 뿐.
- **AtomicSpan**: C(S) 5-predicate를 만족한다고 **판정**된 Span.
- LeafSpan이 모두 AtomicSpan은 아니다. C(S) 확인 필수.

### L*_ 프리픽스는 레거시 식별자

depth는 SA에서의 홉 수일 뿐. 같은 depth에 atomic과 non-atomic 공존 가능.
L3이 AtomicSpan의 고정 레이어라는 뜻이 아님.

---

## KAL — Knowledge Acquisition Loop (v13)

각 Span에 INFORMED_BY ≥ 5 확보:

```cypher
MATCH (s:AptSpan {name: $SPAN})
OPTIONAL MATCH (s)-[:INFORMED_BY]->(k)
WITH s, count(k) as links
WHERE links < 5
RETURN s.name, links, "NEED MORE INFORMED_BY" as action
```

부족하면 → 프로메테우스 리서치 → KG에 KnowledgeNode 추가 → INFORMED_BY 연결.

---

## SP 실행 절차

### Step 1: Root Span 확인

```cypher
MATCH (sa:SemanticAnchor {name: $PROJECT})-[:HAS_ROOT]->(root)
RETURN root.name, root.description, root.status
```

### Step 2: L1 분해 — 관심사(concern) 기준

Root를 **관심사 단위**로 분해. 파일이나 기술이 아닌 의미.
```
"이 문제를 어떤 독립적 subproblem들로 나눌 수 있는가?" (DP 사고)
```

### Step 3: 재귀 — 각 leaf에 C(S) 확인

```
for each leaf:
  check C(S) 5-predicate
  if ALL pass → mark AtomicSpan (아래 Cypher로 :AtomicSpan 라벨 부여 필수)
  if ANY fail → D(S) 적용 → 하위 Span 생성
  repeat
```

**AtomicSpan 마킹 Cypher (is_atomic=true만으로 불충분 — :AtomicSpan 라벨 필수):**

```cypher
-- C(S) 5-predicate 통과 시 반드시 이 형식으로 마킹
MATCH (s:AptSpan {name: $SPAN_NAME})
SET s:AtomicSpan,               -- ← 라벨 추가 필수 (labels(s)에 'AtomicSpan' 포함돼야 함)
    s.is_atomic = true,
    s.estimated_lines = $LINES  -- ν predicate 실측값
RETURN s.name, labels(s)        -- ['AptSpan', 'AtomicSpan'] 확인
```

**주의**: `s.is_atomic = true`만 쓰고 `SET s:AtomicSpan` 생략 시 Crystallization 쿼리에서 누락됨.

### Step 4: Crystallization Frontier 도달 확인

```cypher
-- 모든 leaf가 :AtomicSpan 라벨 보유인지 확인 (is_atomic 속성만으로는 불충분)
MATCH (sa:SemanticAnchor {name: $PROJECT})-[:HAS_ROOT]->(root)
MATCH (root)-[:DECOMPOSES_TO*1..10]->(leaf)
WHERE NOT (leaf)-[:DECOMPOSES_TO]->()
RETURN leaf.name,
       leaf.is_atomic,
       'AtomicSpan' IN labels(leaf) AS has_atomic_label,
  CASE WHEN leaf.is_atomic = true AND 'AtomicSpan' IN labels(leaf)
       THEN '✓ READY'
       ELSE '✗ NEED DECOMPOSITION OR LABEL FIX' END AS status
```

**모든 leaf가 is_atomic=true AND :AtomicSpan 라벨 보유 → Crystallization Frontier 도달 → ST 진입 가능.**

### Step 5: Taliban RefinementGate

```
/taliban 호출 → SP 산출물 `{{cfg.lens_count_constitutional}}`-lens 검증 (현재 9)
→ APPROVED이면 KG에 ValidationResult(phase='SP') 기록
→ REJECTED이면 Finding 반영 후 재분해
```

---

## SP → ST 핸드오프

### 보존 (ST에 전달)

- 전체 AtomicSpan 목록 + description
- Span 간 DEPENDS_ON 관계
- INFORMED_BY 링크
- apt-progress.md 현재 상태

### 제거

- 분해 탐색 히스토리
- C(S) 중간 결과
- RefinementGate 로그

---

## What NOT To Do

| 금지 | 이유 | 대안 |
|------|------|------|
| 코드 아티팩트로 Span 이름 | SpanPlanningNature 위반 | 의미 단위로 이름 |
| 개별 Span을 바로 ST로 | 전체 leaf가 Atomic이어야 | 전부 끝날 때까지 SP |
| 트리 구조 강제 | Span은 DAG | N:N 허용 |
| 100줄 미만 AtomicSpan | δ-diseconomy | 상위와 합병 |
| C(S) 확인 없이 AtomicSpan 선언 | LeafSpan ≠ AtomicSpan | 5-predicate 전부 확인 |
| INFORMED_BY 없이 분해 | 근거 없는 분해 | KAL로 지식 확보 |

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
MATCH (ts:SubagentTaskSpec {skill:'apt-sp'}) WHERE ts.status='READY'
RETURN ts.name, ts.role LIMIT 10
```

### WorkBuffer 연속성
```cypher
MATCH (wb:WorkBuffer {status:'CURRENT'}) RETURN wb
```

# KG: ATOM_재배맨_v2_apt-sp, SA_methodology_v4_triple_upgrade

---

## MIC Binding Disclaimer

> 이 SKILL.md에서 "Prometheus", "Taliban", "88-Taliban", "Longinus", "재배맨" 등의
> concrete 이름은 MIC_v1 MethodologySlot의 **현재 바인딩(currentConcrete)**이다.
> Slot이 다른 concrete로 교체되면 이 파일의 이름도 drift한다.
> 정본 해석: `MATCH (mic:MethodologyIntegrationContract {name:'MIC_v1'})-[:HAS_SLOT]->(s) RETURN s.name, s.currentConcrete`
> 유틸리티: `03_SCRIPTS/db/resolve_mic_slot.cypher`
> # KG: lesson-skill-mic-slot-ref-weak-2026-04-15

---

## History

> Repo-level changes: [`/CHANGELOG.md`](../CHANGELOG.md). Per-commit: `git log -- apt-sp/SKILL.md`.
> Architecture: Progressive Disclosure v3 — references split (2026-05-11):
> - C(S) 5 predicates (v/t/i/d/s, cheap-first): [`references/cs_predicates.md`](references/cs_predicates.md)
> - EXPLORES_VIA 3 strategies + Selection Span + Confluence: [`references/explores_via.md`](references/explores_via.md)
> - RefinementGate 3 checks (Coverage/Consistency/Independence): [`references/refinement_gate.md`](references/refinement_gate.md)
> - Dense Linking (INFORMED_BY ≥ N): [`references/dense_linking.md`](references/dense_linking.md)
> - SP 4 Rules (SpanPlanningNature/2-Layer/SpiderWeb/N:N DAG): [`references/sp_rules.md`](references/sp_rules.md)
> - Span Boundary (allowed_paths / forbidden_patterns): [`references/span_boundary.md`](references/span_boundary.md)
> - SP → ST handoff cypher: [`references/handoff_to_st.md`](references/handoff_to_st.md)
> - SP error patterns (E1/E10/E-SP1/2/3): [`references/sp_errors.md`](references/sp_errors.md)
> - Cross-skill shared: [`../_common/`](../_common/) (Context Budget § migrated to dedup).
> - Legacy redirect: `references/sp_world.md`.

| Version | Date | Summary | KG Ref |
|---|---|---|---|
| **v26** | 2026-04 | C(S) 5-predicate fields (objective/definition/keyAssertion/verification/c_s_predicate) MUST non-null on every Span. A3/A5 SP→ST gate Cypher LensSet completeness. δ_infra exception. Magic number 500/200-500 → MethodologyConfig slot (A4) | `APT_v26_RFC_draft_2026-04-21`, `lesson-taliban-shortcut-antipattern-2026-04-21`, `ATOM_APT_delta_infra_exception_2026-04-21` |
| **v24** | 2026-04 mid | KG 정본 기반 재설계. Crystallization Frontier. v5~v21 AptClarificationNote 22개 반영 | — |
| **v5~v23** | timestream | SP = ONE world. Spans = DAG nodes (N:N, not tree). D(S) recurrence until ALL leaves satisfy C(S) = AtomicSpan | — |

# KG history: ATOM_Skill_apt_sp / lesson-prom16-skill-versioning-academic-2026-04-29 / lesson-prom16-skillver-progressive-disclosure-drift-2026-04-29
