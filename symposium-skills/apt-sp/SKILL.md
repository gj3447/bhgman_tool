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
  Invoke when: parent /apt orchestrator dispatch only — direct user call rejected by APT_GATE_VERSION=v27_phase_sp_dispatch_guard. Korean: APT 디컴포즈 페이즈 — 상위 orchestrator dispatch only. SP 는 SA→SP→ST→SCW gate chain 의 2/4 phase — 단독 호출 시 SA gate APPROVED + Root Span HAS_ROOT precondition 자동 만족 불가, dispatch_only=true (E1.4 PATTERN_D guard, rf-prom16-cc-eng-E1-S4-skill-activation-2026-05-14).
  Active Weapons (2026-05-14): 재배맨 SubagentTaskSpec seed per Span (D(S) parallel decomposition, Step 4) + Naesengmoon `/tlb <SPAN> --lens constitutional` per Crystallization Frontier 진입 후보 (C(S) 5-predicate gate, Step 6). hub-jaebaeman-sop + hub-taliban-immunity resolve.
  # KG: ATOM_Skill_apt_sp, CONTRACT_apt_sp, APT_v26_RFC_draft_2026-04-21, lesson-taliban-shortcut-antipattern-2026-04-21, rf-prom16-cc-eng-E1-S4-skill-activation-2026-05-14
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
// — Naesengmoon gate: prefer Agent(taliban-ensemble-critic) over single /taliban call
MATCH (rfc:MethodologyRFC {name:'rfc-taliban-v08-concern-coverage-2026-05-04'})
RETURN rfc.status
```

**C(S) 5-predicate fields** (non-null 필수): `objective` · `definition` · `keyAssertion` · `verification` · `c_s_predicate`. 누락 = Naesengmoon reject. # KG: APT_v26_A6_2026-04-21, lesson-taliban-shortcut-antipattern-2026-04-21

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

## ⚔ Active Weapons — Phase SP (2/5)

> SP 측 활성 5무기 (parent /apt orchestrator §"5무기 Phase Integration Matrix" mirror).

| Step | Weapon | Invocation | Trigger | Output |
|------|--------|-----------|---------|--------|
| Step 4 (D(S) recursive decomposition) | **재배맨** (SubagentSeeder) | per-Span `SubagentTaskSpec` seed (parent Pre-fetch → Dispatch → Collect → Write) | parent Span 측 자식 후보 N 개 결정 필요 (LOC > `cfg.vibe_coding_sweet_max` OR multi-concern) | 자식 Span N 개 (each carrying objective/definition/keyAssertion) |
| Step 5 (wave_index 할당) | **재배맨** | `MATCH (s:Span) SET s.wave_index = $level` | 자식 Span 생성 직후 (parallel dispatch wave 결정) | `Span.wave_index` (same wave = single-message parallel) |
| Step 6 (C(S) 5-predicate gate) | **Naesengmoon** (AdversarialValidator) | `/tlb <SPAN_id> --lens constitutional` (LensSet completeness 강제) | leaf Span → AtomicSpan 격상 후보 | `VerdictRecord` APPROVED + `:AtomicSpan` 라벨 |
| Step 7 (Crystallization Frontier 통과) | **Naesengmoon** (mathematical lens optional) | `/88-taliban <Frontier>` (sibling-wellformedness A3 axiom) | 모든 leaf=AtomicSpan 도달 시 | Frontier APPROVED → ST 진입 trigger |

**SP→ST mini-RGR** (RFC2 transition):
- RED: Naesengmoon prior contract conflict 검사
- GREEN: Naesengmoon Crystallization Frontier gate (모든 leaf=AtomicSpan)
- REFACTOR: Longinus 중복 ReferenceSite 통합

**SP 진입 hub**: `hub-jaebaeman-sop` (Span DAG decomposition seed) + `hub-taliban-immunity` (C(S) gate).

# KG: hub-jaebaeman-sop, hub-taliban-immunity, MIC_v1.SubagentSeeder, MIC_v1.AdversarialValidator

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

같은 레이어의 형제 Span 사이 *hidden/미선언* 의존성 금지 (사용자 verdict 2026-05-27).
숨은 의존 발생 시 → 분해 오류, 상위로 올려 재분해. **단 irreducible coupling은 *명시적 DAG edge*(DEPENDS_ON/REQUIRES/COMMUNICATES_VIA_EVENT)로 declare + ST Contract로 묶으면 허용** (Rule 3.1 + contract dual axiom) — 이건 분해 오류 아님.
**DP의 independent subproblems = APT의 sibling independence (hidden 의존 기준).**

### Rule 3.1: Coupling-minimization criterion (Rule 3 operationalization, 2026-05-27)

> Rule 3은 "독립하라"는 *당위*. **어떻게 cut하면 독립이 나오나** = information-hiding seam(Parnas 1972: 변할 design decision을 한 span에 은닉) + connascence-minimizing + DDD bounded-context. ⚠ **"병렬 위해 쪼갬"으로 독립 가정 금지** — 병렬성↑은 결합도↑ (`oq-planfirst-coupling-minimization-resolution-2026-05-27`).
> **irreducible coupling**: Rule 3의 'error/재분해'로 강제하지 말고 — *명시적 DAG edge*(DEPENDS_ON/REQUIRES/COMMUNICATES_VIA_EVENT)로 declare + ST에서 그 edge에만 non-trivial Contract(contract dual axiom). 숨은 sibling 의존(Rule3 금지) vs declared DAG coupling 구분. **[A3 재해석 CANONICAL: 사용자 verdict 2026-05-27 — hidden/미선언만 금지, declared+contracted 허용. `decision-a3-hidden-only-reconciliation-2026-05-27`]**
> **guard**: "완전 독립"은 edge-부재 default 금지 — information-hiding seam positive 판정.
> # KG: apt-sp-coupling-minimization-criterion-2026-05-27, apt-contract-root-axiom-2026-05-27, oq-planfirst-coupling-minimization-resolution-2026-05-27

### Rule 3.2: declared coupling은 *퍼블릭 경계*로만 (APT-D2 fix, 2026-06-01)

<!-- KG: APT-D2-2026-06-01 (:MethodologyDefect), lesson-tpa-dogfood-spacegirl-defects-2026-06-01 -->

> **결함 출처**: spacegirl_tool — span AS2(surface)가 AS1(ssb)의 *private 함수*(`_apply`/`_collect_rename_targets`)를 직접 호출 = declared coupling이 information-hiding seam을 뚫음. AS1 내부 구현 바뀌면 AS2가 조용히 깨진다.

Rule 3.1의 *declared DAG edge*(DEPENDS_ON 등)는 **대상 span의 퍼블릭 경계(노출 API/Contract)로만** 결선한다. private/내부 심볼(언더스코어·non-exported) 직접 참조 = seam 위반.

- ST Contract 결정화 시 각 span은 *노출 surface*(public symbols)를 명시 → 다른 span은 그 surface로만 의존.
- private 심볼 cross-span 참조 발견 → `TR_PrivateBoundaryViolation` flag → 노출 API 추출로 정정.

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

**Naesengmoon SP gate**: `kind`가 인프라 계열이면 `--lens infra`(infra-specific LensSet) 자동 적용. 일반 constitutional 렌즈로 판정 시 false positive 위험(YAML/Dockerfile τ 미충족으로 오판).

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
-- C(S) 5-predicate 통과 시 반드시 이 형식으로 마킹 (Russell stratification: parent(S) ≠ Root)
MATCH (s:AptSpan {name: $SPAN_NAME})
MATCH (s)<-[:DECOMPOSES_TO]-(parent)            -- parent 존재 강제 = Root 제외 (MATH-F2 fix)
SET s:AtomicSpan,                               -- ← 라벨 추가 필수 (labels(s)에 'AtomicSpan' 포함돼야 함)
    s.is_atomic = true,
    s.estimated_lines = $LINES,                 -- ν predicate 실측값
    s.measure_value = toFloat($LINES) / toFloat(cfg.vibe_coding_sweet_max),  -- contraction metric (Banach k<1)
    s.c_s_verified_at = datetime()
RETURN s.name, labels(s), s.measure_value       -- ['AptSpan', 'AtomicSpan'] + measure ∈ [0, 1] 확인
```

**주의**: `s.is_atomic = true`만 쓰고 `SET s:AtomicSpan` 생략 시 Crystallization 쿼리에서 누락됨.

**measure_value 의미 (D2 finding `fp16apt-D2-contraction-mechanism`)**:
- Banach contraction metric. `measure = estimated_lines / vibe_coding_sweet_max`. AtomicSpan 도달 = `measure ≤ 1.0`.
- 자식 `measure < 부모 measure` 측 contraction invariant (D(S) recursion 종료 보장 — Banach fixed-point + Floyd variant).
- Kolmogorov K 측 incomputable → LOC 측 approximation (200-500 sweet range).

**Russell stratification (MATH-F2 fix from 3중 나생문 `VR_prom16_apt_bhgman_3lens_synthesis_1779282744414`)**:
- `MATCH (s)<-[:DECOMPOSES_TO]-(parent)` 측 parent 존재 강제 = **Root Span 측 :AtomicSpan 라벨 불가**.
- Root Span (예: `SPAN_bhgman_tool_phase3_ROOT`, `apt-progress` SA Root Span 17 등) termination 측 internal contraction proof 아닌 **external sigma_oracle (사용자 verdict) gate** 측 의존.
- Self-applied methodology cycle (예: PROM 16 자체) 측 Russell self-application paradox 회피.

### Step 3.5: Contraction invariant verification (P0-1 fix, 3중 나생문 D2/MATH-F2)

```cypher
-- ∀ child AtomicSpan: measure(child) < measure(parent) (Banach contraction k<1)
MATCH (parent)-[:DECOMPOSES_TO]->(child:AtomicSpan)
WHERE parent.measure_value IS NOT NULL AND child.measure_value IS NOT NULL
  AND child.measure_value >= parent.measure_value
RETURN parent.name AS parent_span,
       parent.measure_value AS parent_m,
       child.name AS child_span,
       child.measure_value AS child_m,
       '✗ CONTRACTION VIOLATED' AS verdict
```

**비어 있어야 정상**. result row 측 1+ 측 contraction failure → C(S) 5-predicate 재검증 필요.

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

### Step 5: Parallel Wave Extraction (Kahn topological order)

> Crystallization Frontier 도달 후 *모든* AtomicSpan 에 **wave_index** (Kahn 1962 topo sort) 부여.
> 같은 wave = antichain (DEPENDS_ON edge 없음) = SCW dispatch 완전 병렬 batch.
> 외부 정전: Kahn 1962 *CACM* 5(11):558-562 / CLRS §22.4 Topological Sort.

**Invariant**: `(a)-[:DEPENDS_ON]->(b)` ⟹ `a.wave_index < b.wave_index` (strict less).

```cypher
// Wave 1 — DEPENDS_ON in-degree 0 (root AtomicSpan)
MATCH (atom:AtomicSpan) WHERE NOT ()-[:DEPENDS_ON]->(atom) AND atom.wave_index IS NULL
SET atom.wave_index = 1
RETURN count(atom) AS wave1_size

// Wave k (k=2,3,...) — driver script 가 wave_size > 0 까지 반복
WITH $k AS k
MATCH (atom:AtomicSpan)
WHERE atom.wave_index IS NULL
  AND NOT EXISTS {
    MATCH (pred:AtomicSpan)-[:DEPENDS_ON]->(atom)
    WHERE pred.wave_index IS NULL OR pred.wave_index >= k
  }
SET atom.wave_index = k
RETURN k, count(atom) AS wave_size

// 종료 검증 — NULL 잔존 시 CyclicDAG
MATCH (atom:AtomicSpan) WHERE atom.wave_index IS NULL
RETURN atom.name AS cyclic_atom
```

**Complexity**: O(V+E). V=|AtomicSpan|, E=|DEPENDS_ON|.

**Error variants**:
- `CyclicDAG`: NULL 잔존. DEPENDS_ON cycle → 상위 Span 으로 의존 끌어올려 재분해.
- `OrphanLeaf`: :AtomicSpan 라벨 없는 leaf. Step 4 Crystallization Frontier 검증에서 사전 차단.

Worked example (3-wave 7-span) + edge case (single node / linear chain / all-parallel / cyclic) + SP→ST gate cypher → [`references/wave_extraction.md`](references/wave_extraction.md).

### Step 6: Naesengmoon RefinementGate

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
- **AtomicSpan.wave_index** (Kahn topo sort, SCW dispatch batch 결정용)
- INFORMED_BY 링크
- apt-progress.md 현재 상태

### SP→ST gate (wave_index 완전성 강제)

```cypher
MATCH (sa:SemanticAnchor {name: $PROJECT})-[:HAS_ROOT]->(root)
MATCH (root)-[:DECOMPOSES_TO*1..10]->(atom:AtomicSpan)
WHERE atom.wave_index IS NULL
RETURN 'V_SP_WaveIndex_Missing' AS validation, atom.name
// 1행 이상 = SP→ST 차단. references/wave_extraction.md 참조.
```

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

> 이 SKILL.md에서 "Prometheus", "Naesengmoon", "88-Naesengmoon", "Longinus", "재배맨" 등의
> concrete 이름은 MIC_v1 MethodologySlot의 **현재 바인딩(currentConcrete)**이다.
> Slot이 다른 concrete로 교체되면 이 파일의 이름도 drift한다.
> 정본 해석: `MATCH (mic:MethodologyIntegrationContract {name:'MIC_v1'})-[:HAS_SLOT]->(s) RETURN s.name, s.currentConcrete`
> 유틸리티: `03_SCRIPTS/db/resolve_mic_slot.cypher`
> # KG: lesson-skill-mic-slot-ref-weak-2026-04-15

---

## Plan Mode Workflow (Optional) — Claude Code Plan Mode ↔ APT SP D(S)→C(S) 매핑

> Claude Code Plan Mode (Shift+Tab cycle) 와 APT SP D(S) 재귀 → C(S) 검증 은 자연스러운 1:1 대응을 이룬다.
> 외부 정전: Claude Code Plan Mode 공식 spec (https://code.claude.com/docs).
> PROM_16 finding: `rf-prom16-cc-eng-E4-S2-plan-worktree-2026-05-14` (verdict: INTEGRATED_PARTIAL_MISSING_OPPORTUNITY).
> Korean: Plan Mode = 실행 *전* read-only 계획 시각화. APT SP 는 본질적으로 plan layer (코드 없음 / Contract 없음 / 분해와 탐색만) — Plan Mode 와 동형(homomorphic).

### 1:1 매핑 표

| Claude Code Plan Mode 단계 | APT SP 단계 | 외부 결과물 |
|----------|------|----------|
| Plan Mode 진입 (Shift+Tab → "plan") | Step 1 Root Span 확인 + Step 2 L1 분해 | plan tree (markdown) — user inspect |
| Plan tree iterate (read-only D(S) 시뮬레이션) | Step 3 재귀 D(S) → 하위 Span 생성 | DAG 시각화 (mermaid / cypher graph) |
| Plan tree leaf 확정 | Step 3 C(S) 5-predicate 검증 → AtomicSpan 마킹 | leaf set + C(S) verdict |
| Plan tree 승인 (user accept) | Step 4 Crystallization Frontier 도달 확인 + Step 5 wave_index | wave_index 할당된 atomic span list |
| Plan Mode exit → Edit mode | Step 6 Naesengmoon RefinementGate → ST handoff | KG commit (atomic Cypher transaction) |

### Plan Mode + Wave Extraction 시너지

> 어제 박힌 Step 5 Parallel Wave Extraction (Kahn 1962 topo sort) 은 Plan Mode 와 결합 시 **wave 단계 시각화** 단계가 된다.
> Plan Mode 의 read-only 특성 = wave_index 확정 *전* in-degree 0 set 검증 = user 가 plan tree 에서 "어떤 atomic span 이 wave 1 인가" 직접 확인 가능.

```
Plan Mode tree view (예시):
  Root Span
  ├── L1: Concern A
  │   ├── L2: AtomicSpan A1 [wave=1, in-degree=0]
  │   └── L2: AtomicSpan A2 [wave=2, DEPENDS_ON A1]
  └── L1: Concern B
      └── L2: AtomicSpan B1 [wave=1, in-degree=0]  ← antichain with A1

User APPROVED → exit Plan Mode → atomic Cypher commit:
  SET A1, B1 :AtomicSpan, wave_index=1
  SET A2 :AtomicSpan, wave_index=2
  → SP→ST gate V_SP_WaveIndex_Missing 자동 통과
```

### 활용 권장 시나리오

- **복잡 SP 사이클** (depth ≥ 3): Plan Mode 로 전체 DAG 한 번에 시각화 후 user 가 분해 sanity-check.
- **wave_index 결정 borderline**: in-degree 계산이 미묘할 때 Plan Mode 의 read-only iterate 로 DEPENDS_ON edge 직접 검토.
- **C(S) 5-predicate human σ predicate** (Rule 5 σ — Semantic completeness): Plan Mode 에서 user verdict 받기 자연스러움.

### 비-활용 시나리오

- **단순 SP** (atomic span ≤ 3): Plan Mode overhead 가 직접 분해보다 큼.
- **인프라 파일 SP** (K8s/Helm/Terraform): τ_infra/ι_infra 판정은 dry-run 결과 필요 — Plan Mode read-only 와 직교.
- **Hot-fix / 단기 사이클**: prometheus v6.1 paralysis-by-analysis 회피 패턴 우선.

### Atomic KG Commit 패턴 (Plan Mode exit 후)

```cypher
// Plan Mode 에서 user 확정된 wave 1 + wave 2 batch 를 단일 transaction 으로 commit
BEGIN
UNWIND $atomic_spans AS span
MATCH (s:AptSpan {name: span.name})
SET s:AtomicSpan,
    s.is_atomic = true,
    s.estimated_lines = span.lines,
    s.wave_index = span.wave,
    s.plan_mode_approved = true,
    s.plan_mode_approved_at = datetime()
COMMIT
```

# KG: rf-prom16-cc-eng-E4-S2-plan-worktree-2026-05-14, claude-code-plan-mode-canonical, ATOM_APT_SP_Plan_Mode_Integration_2026-05-14

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
> - Parallel Wave Extraction (Kahn topo sort, wave_index): [`references/wave_extraction.md`](references/wave_extraction.md)
> - SP error patterns (E1/E10/E-SP1/2/3): [`references/sp_errors.md`](references/sp_errors.md)
> - Cross-skill shared: [`../_common/`](../_common/) (Context Budget § migrated to dedup).
> - Legacy redirect: `references/sp_world.md`.

| Version | Date | Summary | KG Ref |
|---|---|---|---|
| **v27.2** | 2026-05-14 | GAP E4.2 (HIGH) Plan Mode Workflow appendix — Claude Code Plan Mode (Shift+Tab) ↔ APT SP D(S)→C(S) 1:1 매핑 + Step 5 wave_index 시각화 시너지 + atomic KG commit 패턴. GAP E1.4 (LOW) frontmatter 측 `Invoke when: parent /apt orchestrator dispatch only` 명시 (APT_GATE_VERSION=v27_phase_sp_dispatch_guard, PATTERN_D guard). Korean dual-language. | `rf-prom16-cc-eng-E4-S2-plan-worktree-2026-05-14`, `rf-prom16-cc-eng-E1-S4-skill-activation-2026-05-14`, `ATOM_APT_SP_Plan_Mode_Integration_2026-05-14` |
| **v27.1** | 2026-05-14 | GAP-1 Parallel Wave Extraction step (Kahn topo sort, AtomicSpan.wave_index). Crystallization Frontier 후 SP→ST gate 에 `V_SP_WaveIndex_Missing` 강제. 1to1to1to1 invariant 의 병렬 dispatch batch 명시화 | `lesson-apt-sp-wave-index-explicit-2026-05-14`, `APT_SP_WaveExtraction_canonical` |
| **v26** | 2026-04 | C(S) 5-predicate fields (objective/definition/keyAssertion/verification/c_s_predicate) MUST non-null on every Span. A3/A5 SP→ST gate Cypher LensSet completeness. δ_infra exception. Magic number 500/200-500 → MethodologyConfig slot (A4) | `APT_v26_RFC_draft_2026-04-21`, `lesson-taliban-shortcut-antipattern-2026-04-21`, `ATOM_APT_delta_infra_exception_2026-04-21` |
| **v24** | 2026-04 mid | KG 정본 기반 재설계. Crystallization Frontier. v5~v21 AptClarificationNote 22개 반영 | — |
| **v5~v23** | timestream | SP = ONE world. Spans = DAG nodes (N:N, not tree). D(S) recurrence until ALL leaves satisfy C(S) = AtomicSpan | — |

# KG history: ATOM_Skill_apt_sp / lesson-prom16-skill-versioning-academic-2026-04-29 / lesson-prom16-skillver-progressive-disclosure-drift-2026-04-29
