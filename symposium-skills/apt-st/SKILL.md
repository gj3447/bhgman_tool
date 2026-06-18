---
name: apt-st
kg_ref: ATOM_Skill_apt_st
version: "27.1.0"
channel: stable
description: >
  APT SemanticTwin (ST) — crystallization of AtomicSpans into Contract + Task + 8 ST Decision Areas.
  Enters ONLY after Crystallization Frontier (all leaves = AtomicSpan).
  v27: Exhaustive Cover Scope — 8 areas (AST/Workflow/DP/PS/DataFlow/Algo/Store/Class) mandatory before SCW. Tier 1 5 areas HIGH ★, Tier 3 3 areas MEDIUM.
  Contract = typed DTO/Schema (default 7 fields + v25 error_variants; v26 A2 pluggable via ContractSchema slot).
  v26 A2: Contract v2 (9 axes + access_rights_closure + ArchitectureContract + 6 CrossAxisInvariant + ReferenceSite/DriftMorphism).
  v25: SharedType→Contract.shared=true. SemanticTask via MethodologyConfig.vibe_coding_sweet.
  Invoke when: parent /apt orchestrator dispatch only — direct user call rejected by APT_GATE_VERSION=v27_phase_st_dispatch_guard.
  ST 는 SA→SP→ST→SCW chain 의 3/4 phase — 단독 호출 시 SP gate APPROVED + Crystallization Frontier + 8 areas exhaustive cover precondition 자동 만족 불가 (E1.4 PATTERN_D→PATTERN_A).
  Active Weapons (2026-05-14): Longinus L3-L4 (Contract→ReferenceSite 7-tuple, Step 8) + 재배맨 per-AtomicSpan SubagentTaskSpec (1:1:1:1, Step 9) + Naesengmoon `/tlb <Contract> --lens constitutional` (Step 9.5).
  # KG: ATOM_Skill_apt_st_v27, lesson-st-cover-scope-exhaustive-2026-04-29, APT_v26_RFC_draft_2026-04-21, rf-prom16-cc-eng-E1-S4-skill-activation-2026-05-14
---

## 🎛 v26 A6 Resolve-Only

> Contract field count / SemanticTask line band — **하드코딩 금지**. ContractSchema + MethodologyConfig slot resolve.

```cypher
// ContractSchema (default 7-field v25 + error_variants; v2 = 9 canonical axes + SharedType)
MATCH (slot:MethodologySlot {name:'ContractSchema'})-[:RESOLVES_TO]->(schema) RETURN schema.fields, schema.version

// Task line band (vibe-coding sweet spot)
MATCH (cfg:MethodologyConfig {name:'MethodologyConfig_default_v26'})
RETURN cfg.vibe_coding_sweet_min, cfg.vibe_coding_sweet_max, cfg.vibe_coding_hard_max

// Contract v2 reference instance
MATCH (sa:SemanticAnchor {name:'SA_Contract_v2_DbC_Interface_2026-04-21_v2'})-[:USES_CANONICAL]->(axes)
RETURN axes.name

// ST decision area cfg pointers (2026-05-04 wired, 5 ConfigSchema MIC slot)
// — magic number hardcoding 금지, Cypher resolve only.
MATCH (cs:ConfigSchema:MICSlot)
WHERE cs.name STARTS WITH 'MIC_v1.' AND cs.name ENDS WITH '_decision'
RETURN cs.name              AS slot,           // MIC_v1.{area}_decision
       cs.skill_md_pointer  AS pointer,        // cfg.{area}_decision
       cs.decision_summary  AS summary,
       cs.materializes_into AS skill_section,  // ## ST.{area}_decision
       cs.source_cycle      AS prom_cycle      // 2026-05-04 wave
// 8/8 areas wired (2026-05-04 complete):
//   T1 ★: AST / Workflow / DesignPattern / DataFlow / Store
//   T3:   ProjectStructure / Algorithm / ClassDesign
// Source cycles: hole{1..8} cycles (PROM-16 wave) + hole2-v2 + hole6-v2 fixes
//
// v0.8.A1 Gate Hook reference (2026-05-05): apt-gate-check.sh dual-mode
//   APT_GATE_VERSION=v07 (default, lensCount>=9 floor) | v08-A1 (ensemble UNION concern-coverage>=0.8)
//   Pirsig holistic synthesis = ensemble union의 Cypher instantiation
//   RFC: rfc-taliban-v08-concern-coverage-2026-05-04 (DRAFT_v0.8.A1_PHASE3_DEPLOYED)
MATCH (rfc:MethodologyRFC {name:'rfc-taliban-v08-concern-coverage-2026-05-04'})
RETURN rfc.status, rfc.amendment_a1_2026_05_04, rfc.phase_3_status
```

**SharedType detection**: Contract.shared=true. SharedType_access_rights_closure_v2 = ownership ⊔ capability Fiber Bundle. # KG: APT_v26_A6_2026-04-21, SharedType_access_rights_closure_v2, MIC_v1.ProjectStructure_decision, MIC_v1.DataFlow_decision, MIC_v1.ClassDesign_decision, MIC_v1.Algorithm_decision, MIC_v1.DesignPattern_decision

---

## 🔗 MIC Binding (SOLID-DIP)

**IS slot**: APT_Phase (ST, 3/4)
**USES slots**: SubagentSeeder, MetaVerifier (Contract 수학 속성), AdversarialValidator

```cypher
MATCH (mic:MethodologyIntegrationContract {name:'MIC_v1'})-[:HAS_SLOT]->(s:MethodologySlot)
WHERE s.name IN ['SubagentSeeder','MetaVerifier','AdversarialValidator']
RETURN s.name, s.currentConcrete, s.invocation
```

# KG: MIC_v1, lesson-apt-not-truly-jaebaeman-2026-04-14

---

## ⚔ Active Weapons — Phase ST (3/5)

> ST 측 활성 5무기 (parent /apt orchestrator §"5무기 Phase Integration Matrix" mirror).

| Step | Weapon | Invocation | Trigger | Output |
|------|--------|-----------|---------|--------|
| Step 7 (Contract DTO 결정화) | **재배맨** (SubagentSeeder) | per-AtomicSpan parallel research → Contract DbC 4-측면 합의 | Crystallization Frontier 통과 직후 (all leaves = AtomicSpan) | `Contract` (input_type/output_type/pre/post/invariant) |
| Step 8 (ReferenceSite 7-tuple binding) | **Longinus** (KgCodeBinder) | L3-L4 forward binding: `(:Contract)-[:HAS_REFERENCE_SITE]->(:ReferenceSite {name, kind, source, target, cardinality, label, provenance})` | Contract 결정화 직후 | `ReferenceSite` per Contract (7-tuple complete) + Longinus L3-L4 trace |
| Step 9 (1:1:1:1 seed) | **재배맨** (SubagentSeeder) | per-AtomicSpan SubagentTaskSpec seed (TDD RED test 4-tuple: file/contract_ref/test_id/expected) | Contract APPROVED 직후 | `SubagentTaskSpec` per AtomicSpan (SCW wave dispatch 준비) |
| Step 9.5 (RefinementGate) | **Naesengmoon** (AdversarialValidator) | `/tlb <Contract_id> --lens constitutional` (LensSet completeness mandatory) | Contract + SubagentTaskSpec 작성 직후 | `VerdictRecord` APPROVED + SCW 진입 trigger |

**ST→SCW mini-RGR** (RFC2 transition):
- RED: Naesengmoon prior code conflict 검사 (작성할 file path의 sibling 충돌)
- GREEN: 재배맨 wave dispatch GO/NO-GO (wave_index 같은 SubagentTaskSpec batch 측 readiness)
- REFACTOR: Harness 3-tier file placement audit (atomic-span dump 평면 누적 차단 — IDE-host / runtime / managed 측 정확 layer 배치)

**ST 진입 hub**: `hub-longinus-reference` (Contract ReferenceSite 7-tuple) + `hub-jaebaeman-sop` (1:1:1:1 seed) + `hub-taliban-immunity` (RefinementGate).

# KG: hub-longinus-reference, hub-jaebaeman-sop, hub-taliban-immunity, MIC_v1.KgCodeBinder, MIC_v1.SubagentSeeder, MIC_v1.AdversarialValidator

---

# /apt-st — SemanticTwin: Contract Crystallization

> **ST = Verify & Correct 축.**
> Contract는 APT 품질의 유일한 병목. 모호한 Contract → 모호한 코드. 정밀한 Contract → 검증 가능한 코드.
> SemanticTwin = Contract(DTO) + SemanticTask(TDD 완료조건)의 결합체.

## ⛔ GATE CHECK (Hook 강제)

> `apt-gate-check.sh`가 자동 실행. SP Gate 미통과 시 `permissionDecision: deny`.
> `$PROJECT`는 apt-progress.md의 `## Anchor:` 에서 읽는다.
> BLOCKED 시: `/apt-sp` → `/taliban` → SP Gate 통과 → `/apt-st` 재호출.

---

## ST 핵심 원칙

### 1. Crystallization Frontier — SP↔ST 유일한 관문

SP에서 **모든** leaf가 AtomicSpan(C(S) 5-predicate 통과)이 된 후에만 ST 진입.
개별 Span이 먼저 ST로 빠지지 않음 — **전체 DAG의 모든 leaf가 Atomic이면 그때 전환.**
SP는 Contract를 직접 소유하지 않는다.

### 2. 전체를 펼쳐놓고 — 개별이 아닌 집합

> "개별 span이 아닌 **전체 Atomic span 집합**을 한꺼번에 보며
> span 간 데이터 흐름, 의존성, SharedType을 고려한 일관된 Contract 생성"

이것이 ST가 SP와 다른 핵심. SP는 하향식 분해, ST는 **수평적 전체 조감**.

### 2.1 Coupling-edge contract — edge TYPE별 mechanism + strictness (2026-05-27)

> per-AtomicSpan DTO(원칙 3)와 **별개로**, SP가 declare한 *inter-span coupling edge*에도 계약을 건다. **edge TYPE이 mechanism을 결정**:
> - `DEPENDS_ON`(data) → schema/DTO + Hoare `producer.postcond ⊒ consumer.precond` (behavioral 의무 시 full DbC pre/post/invariant)
> - `REQUIRES`(resource) → typestate(lifecycle)/ownership (fine-grained 공유 시 CSL resource invariant → rely-guarantee)
> - `COMMUNICATES_VIA_EVENT` → message schema + consumer-driven contract test(Pact) (stateful choreography 시 MPST session type)
>
> **escalation = property-presence 선택** (lightest-sufficient — SP edge의 *consumer-declared required-property set* 상대; climb은 속성 PRESENT일 때만, 숫자 threshold 아님). ⚠ **구조 주의(나생문 2026-05-27): 전부 chain 아님** — data=표현력 chain(shape‹refinement‹DbC) + higher-order 직교 flag(F-F) / **resource=2축 lattice**: lifecycle축(typestate) ⊥ sharing-granularity축(none‹unique-own‹read-share‹lock-protected‹lock-free) — 축-join, 곱 아님 / event=statefulness chain(schema‹MPST‹MPST+progress; **CDC는 mechanism tier 아니라 enforcement-layer**). hybrid edge → SP서 single-type 분해, 합치면 tier **MAX(곱 금지)**. 상세 KG: `apt-st-escalation-ladders-2026-05-27`.
>
> **strictness = (independent-deploy, blast-radius, change-freq)의 *ordinal join*** (단조 사다리 — ∝/곱(×) 아님; ratio 근거 없음, prior contract-axiom ordinal + Lean T1-T9 정합). consumer가 *실제 의존하는 subset만* enforce(나머지 Postel tolerant-reader). 계약 자체가 coupling point → over-enforcement 금지. **강도 lever는 topology 아닌 *risk(blast-radius)*에 묶음** — co-deploy는 현재 관측치일 뿐 강등 트리거 아님(오늘 co-deploy 내일 split). intra-cycle edge도 high-blast-radius면 heavy. 계약은 항상 present, 강도만 가변("뿌리깊게" walk-back 아님). enforcement: static(type/verifier) / CI(schema-compat, Pact can-i-deploy) / runtime(validation + Findler-Felleisen blame).
> ⚠ **structural analogy ONLY, NOT mechanism homology**: CSL/rely-guarantee/session type=런타임 동시성 기제, APT span=설계시 분해 단위(런타임 scheduler 없음). substrate-disjoint — 형식 보장 자동 전이 안 됨, 어휘 차용.
> # KG: apt-st-contract-enforcement-criterion-2026-05-27 (MIRRORS[metaphorical] apt-sp-coupling-minimization-criterion-2026-05-27, IMPLEMENTS apt-contract-root-axiom-2026-05-27; 나생문 vr-st-contract-enf-naesengmoon-3lens-lakatos-2026-05-27 5-fix applied)

### 3. Contract = Typed DTO/Schema (NOT prose)

> **Metaphysical grounding**: Contract = Aristotelian *μορφή (form)*. SCW 측 source code = *ὕλη (matter)*. ST 는 form 을 결정화 — 곧 matter 가 받을 준비를 마친 organizing principle 을 명시. (apt §🏛 Metaphysical Grounding 참조; PROM_16 P1.4 finding 2026-05-14: Plato methexis 대신 Aristotelian hylomorphism). 4 DbC fields = form 의 4 측면 (§C 아래 참조).

| Field | Type | 설명 |
|-------|------|------|
| `input_type` | typed | gRPC protobuf, function signature, dataclass |
| `output_type` | typed | 반환 타입. 추상(data, any, result) **금지** |
| `precondition` | predicate | 입력 조건. 실행 가능한 assertion |
| `postcondition` | predicate | 출력 보장. 실행 가능한 assertion |
| `acceptance_criteria` | test spec | 통과/실패 판정 기준 |
| `semantic_meaning` | string | 이 Contract가 왜 존재하는지 |
| `target_file` | path | 물질화될 파일 경로 |

#### §C. Contract = Form (Aristotle's μορφή, 4 측면)

Contract 의 DbC fields 가 Aristotle 의 form (μορφή) 4 측면을 직접 implement:

| DbC field | Aristotle 측면 | 의미 |
|-----------|---------------|------|
| `input_type` / `output_type` | **εἶδος (eidos)** — formal cause | what-it-is (τὸ τί ἦν εἶναι), the *intelligible structure* matter will receive |
| `precondition` | **ὕλη-readiness** — material cause prerequisite | matter 가 form 을 받기 위해 만족해야 할 조건. 빈약 = matter prerequisite 불명 |
| `postcondition` | **τελός (telos)** — final cause | form 이 matter 에 완전히 impressed 되었을 때의 상태 (ἐνέργεια realized) |
| `semantic_meaning` (→ `invariant` 결정화) | **οὐσία (ousia)** — substance, persistent identity | form-matter unity 가 시간 가로질러 유지하는 본질. semantic_meaning 의 명시 = ousia 의 articulation |

**규칙**: 4 fields 모두 채워져야 Contract = complete form. 한 측면 누락 = form incomplete → SCW 진입 시 matter 가 어떤 form 을 받아야 하는지 불완전 → 결과 σύνολον (synolon) 불안정.

**Cite**: Aristotle, *Metaphysics* Z.7 1032a12-15 (form-matter unity), Z.17 1041a6-b33 (substance as form-of-matter), H.6 1045a23-b23 (no third entity); Aquinas, *Summa Theologiae* I q.75 a.4 (*forma dat esse*).
# KG: aristotle-hylomorphism-grounding-2026-05-14, prom16-p14-methexis-suggestive-finding-2026-05-14

**예시:**
```
CONTRACT_OM_GPUInstance:
  input_type: {name: str, gpu_type: GPUType, count: int}
  output_type: GPUInstance  # @dataclass
  precondition: gpu_type in SUPPORTED_TYPES and count > 0
  postcondition: result.status == 'allocated' and result.gpu_count == count
  acceptance_criteria: test_gpu_allocation_returns_valid_instance()
  semantic_meaning: GPU 자원 할당 인터페이스
  target_file: src/gpu/provider.py
```

### 4. SharedType — 샌드위치 구조

하나의 Contract가 **여러 ST에 걸쳐 공유**된다.
```
AtomicSpan_A ──CRYSTALLIZES_TO──→ ST_A ──HAS_CONTRACT──→ CONTRACT_X
AtomicSpan_B ──CRYSTALLIZES_TO──→ ST_B ──HAS_CONTRACT──→ CONTRACT_X  (같은!)
```
Contract가 잘게 쪼개져야 Task도 잘게 나뉘고, **병렬 구현이 가능**해진다.

### 5. SemanticTask = `cfg.vibe_coding_sweet_max` 바이브코딩 단위

| Field | 설명 |
|-------|------|
| description | 무엇을 구현하는가 |
| acceptance_criteria | PASS/FAIL 기준 (테스트) |
| estimated_lines | ≤ `cfg.vibe_coding_hard_max` |
| target_file | 구현될 파일 경로 |
| impact_tests | 관련 테스트 파일 경로 |

Task PASS = Contract 이행 완료 = ST 실현 완료.
같은 레이어의 Task들은 **완전 병렬** (Contract가 인터페이스 역할).

---

## ST 실행 절차

### Step 1: AtomicSpan 전체 로드

```cypher
MATCH (sa:SemanticAnchor {name: $PROJECT})-[:HAS_ROOT]->(root)
MATCH (root)-[:DECOMPOSES_TO*1..10]->(atom:AtomicSpan)
WHERE atom.is_atomic = true
RETURN atom.name, atom.description, atom.target_file, atom.estimated_lines
ORDER BY atom.name
```

### Step 2: SharedType 식별

전체 AtomicSpan을 보며 **공통 데이터 구조**를 찾는다:
- 여러 Span이 같은 입력/출력 타입을 공유하는가?
- 병렬 Task 사이를 흐르는 DTO가 있는가?
- 공통 인터페이스가 있는가?

→ 식별된 SharedType = **별도 Contract 노드**로 생성.

### Step 3: 개별 Contract 생성 (7대 필드)

각 AtomicSpan에 대해:
```cypher
MATCH (atom:AtomicSpan {name: $ATOM})
MERGE (st:SemanticTwin {name: 'ST_' + $ATOM})
MERGE (c:AptContract {name: 'CONTRACT_' + $ATOM})
SET c.input_type = $INPUT_TYPE,    // 구체적 typed
    c.output_type = $OUTPUT_TYPE,  // 추상 타입 금지
    c.precondition = $PRECONDITION,
    c.postcondition = $POSTCONDITION,
    c.acceptance_criteria = $ACCEPTANCE,
    c.semantic_meaning = $MEANING,
    c.target_file = $TARGET_FILE,
    c.status = 'CRYSTALLIZED'
MERGE (atom)-[:CRYSTALLIZES_TO]->(st)
MERGE (st)-[:HAS_CONTRACT]->(c)

// SemanticTask 생성
MERGE (t:SemanticTask {name: 'TASK_' + $ATOM})
SET t.description = $TASK_DESC,
    t.acceptance_criteria = $TASK_ACCEPTANCE,
    t.estimated_lines = $LINES,
    t.target_file = $TARGET_FILE,
    t.impact_tests = $TESTS
MERGE (st)-[:HAS_TASK]->(t)
```

### Step 4: Contract 간 SEQUENCED_WITH 연결

Task 간 실행 순서가 있다면 (e.g., DB 스키마 먼저 → API 다음):
```cypher
MERGE (c1)-[:SEQUENCED_WITH {order: 1}]->(c2)
```

### Step 5: KG Canonicality 확인

> "SA, SP, ST, Contract, SemanticTask는 Neo4j KG 안의 정본(canonical).
> 소스코드는 구현 공간일 뿐. 코드가 contract를 구현하지만,
> 코드 측 폴더를 의미론적 정본과 혼동하면 안 된다."

### Step 6: Naesengmoon Gate

```
/taliban → ST 산출물 검증 (Contract `{{cfg.contract_default_fields}}`대 필드 (현재 7) 완전성, SharedType 일관성)
→ APPROVED → ValidationResult(phase='ST') 기록
→ REJECTED → Finding 반영 후 Contract 수정
```

---

## Contract FSM (상태 머신)

```
Draft → [ContractSchema fields + review] → Active → [FulfillmentGate] → Fulfilled → Archived
```

- **Draft**: 필드 작성 중
- **Active**: 7대 필드 완성, 리뷰 통과
- **Fulfilled**: SCW에서 Task PASS
- **Archived**: 프로젝트 완료 또는 폐기

---

## 🔒 1:1:1:1 Cardinality Invariant Gate (ST→SCW 진입 차단)

> **사용자 정전 (2026-05-14)**: AtomicSpan ≡ Contract ≡ SemanticTask ≡ SubagentTaskSpec ≡ 1 file — **1:1:1:1**.
>
> **Drift 차단**: AtomicSpan 이 ST 통과 후 Contract/Task/Seed 중 하나라도 missing 인 채 SCW 로 흘러가면, SCW executor 가 KG 정본 없이 코드를 작성 → 롱기누스 추적 불가 + Contract-Code 정합성 붕괴.
>
> **DbC grounding**: Meyer (1992) — "Design by Contract" requires every routine to carry an explicit contract. AtomicSpan 단위 routine 의 contract = `:AptContract` 노드. 누락 = pre/postcondition 부재 = 검증 가능성 상실.

### Invariant (정전)

```
∀ atomic ∈ AtomicSpan:
  ∃! c ∈ Contract:        (atomic)-[:HAS_CONTRACT]->(c)
  ∃! t ∈ SemanticTask:    (atomic)-[:HAS_TASK]->(t)
  ∃! s ∈ SubagentTaskSpec: (atomic)-[:HAS_SEED]->(s)
```

**예외 (SharedType only)**: `c.shared = true` 인 Contract 는 1 Contract : N AtomicSpan 허용 (Contract Sandwich 패턴). 그 외 Contract 는 1:1 강제.
SharedType detection: `MIC_v1.ContractSchema` slot — Contract.shared=true flag (v25), access_rights_closure v2 (v26 A2).

### Gate Hook Cypher (apt-gate-check.sh 자동 실행)

```cypher
// ST→SCW 진입 차단 게이트 — 1:1:1:1 cardinality 검증.
// missing > 0 → permissionDecision: deny + reason 반환.

MATCH (sa:SemanticAnchor {name: $PROJECT})-[:HAS_ROOT]->(root)
MATCH (root)-[:DECOMPOSES_TO*1..10]->(atomic:AtomicSpan)
WHERE atomic.is_atomic = true

// 각 AtomicSpan 의 3 mandatory binding 확인.
OPTIONAL MATCH (atomic)-[:HAS_CONTRACT]->(c:AptContract)
OPTIONAL MATCH (atomic)-[:HAS_TASK]->(t:SemanticTask)
OPTIONAL MATCH (atomic)-[:HAS_SEED]->(s:SubagentTaskSpec)

WITH atomic, c, t, s,
     // SharedType 예외 — Contract.shared=true 면 N:1 허용, 그 외는 1:1.
     CASE WHEN c IS NULL THEN 'MissingContract'
          WHEN t IS NULL THEN 'MissingTask'
          WHEN s IS NULL THEN 'MissingSeed'
          ELSE 'OK' END AS missing_kind

WITH atomic, missing_kind
WHERE missing_kind <> 'OK'

WITH collect({atomic: atomic.name, missing: missing_kind}) AS violations,
     count(*) AS missing_count

RETURN missing_count = 0 AS gate_passed,
       missing_count AS violations_total,
       violations AS missing_atomicspans,
       CASE WHEN missing_count = 0
            THEN 'OK — ST→SCW handoff permitted (1:1:1:1 invariant satisfied)'
            ELSE 'BLOCKED — 1:1:1:1 cardinality violated. Run /apt-st to crystallize missing bindings.'
       END AS reason
```

### SharedType N:1 예외 검증 (별도 query)

```cypher
// shared=false Contract 가 2+ AtomicSpan 에 걸리면 위반 (Contract Sandwich 오용).
MATCH (a1:AtomicSpan)-[:HAS_CONTRACT]->(c:AptContract)<-[:HAS_CONTRACT]-(a2:AtomicSpan)
WHERE a1.name < a2.name
  AND (c.shared IS NULL OR c.shared = false)
RETURN 'V_ST_Cardinality_NonSharedMultiplex' AS violation,
       c.name AS contract,
       collect(DISTINCT a1.name) + collect(DISTINCT a2.name) AS atomic_spans,
       'Set c.shared=true OR split Contract per AtomicSpan' AS remediation
```

### 위반 시 행동

1. **MissingContract / MissingTask / MissingSeed**: `/apt-st` 재실행 → 누락 AtomicSpan 에 대해 Step 3 (Contract 생성) + Seed (SubagentTaskSpec) 발행.
2. **NonSharedMultiplex**: Contract Sandwich 의도면 `c.shared = true` 설정 + access_rights_closure 명시. 아니면 Contract 를 AtomicSpan 별로 분리 (`contract_sandwich.md` 의 derived Contract cypher 참조).
3. **Re-run gate**: `apt-gate-check.sh` 통과 후에만 `/apt-scw` 진입 허용.

### 참조

- 상세 grounding + worked example 3종 + `apt-gate-check.sh` 패치 예시: [`references/cardinality_invariant.md`](references/cardinality_invariant.md)
- SharedType 정의: [`references/contract_sandwich.md`](references/contract_sandwich.md)
- ContractSchema slot resolve: `MIC_v1.ContractSchema` (SKILL.md 상단 v26 A6 섹션)

# KG: span-gap2-st-1to1-cardinality-gate-2026-05-14, lesson-st-1to1-cardinality-canon-2026-05-14, ATOM_ST_CardinalityInvariantGate

---

## ST → SCW 핸드오프

### 보존
- 전체 Contract 목록 (7대 필드)
- SemanticTask 목록 (acceptance_criteria)
- SharedType 관계
- SEQUENCED_WITH 실행 순서

### 제거
- Contract 초안 히스토리
- SharedType 탐색 과정

---

## What NOT To Do

| 금지 | 이유 | 대안 |
|------|------|------|
| 추상 타입 (data, any, result) | 검증 불가 | 구체적 typed interface |
| 개별 Span에 1:1 Contract | SharedType 누락 | 전체를 펼쳐놓고 공유 타입 식별 |
| precondition/postcondition이 prose | 테스트 불가 | assertion으로 작성 |
| SP에서 바로 Contract | Crystallization Frontier 위반 | 모든 leaf Atomic 후 ST 진입 |
| Contract를 코드에서 유추 | KG가 정본 | KG에 먼저 기록, 코드는 물질화 |
| target_file 미지정 | 롱기누스 추적 불가 | 반드시 물질화 경로 명시 |

---

## 🌱 재배맨 v2 (MIC Slot Reference — 로직 복제 금지)

> 이 스킬의 subagent 운용은 **MIC_v1.SubagentSeeder** slot을 통해 resolve된다.
> 아래는 thin resolver. 로직 복제 = drift 유발.
>
> **WRITE_DEFERRED_TO_PARENT (PROM 16 T3 ship 2026-05-24)**: per-AtomicSpan SubagentTaskSpec
> dispatch 시 subagent prompt 본문에 jaebaeman SKILL.md §2-2 WRITE_DEFERRED_TO_PARENT clause
> mandatory 주입. Contract / SubagentTaskSpec MERGE 의도는 `kg_write_intent_json` field 로만
> 반환, 실제 write 는 parent (apt-st Step 7/9) 수행. 정전 anchor:
> `lesson-subagent-self-drift-kg-write-prom16-2026-05-24`.

### Slot Resolve
```cypher
MATCH (mic:MethodologyIntegrationContract {name:'MIC_v1'})-[:HAS_SLOT]->(s:MethodologySlot {name:'SubagentSeeder'})
RETURN s.currentConcrete, s.invocation, s.protocol
```

### 부모 Pre-fetch (v2 — MCP 우회)
```cypher
MATCH (l:Lesson)-[:HAS_RESEARCH]->(rf:ResearchFinding)
WHERE l.name CONTAINS $keyword RETURN rf.name, rf.domain, rf.oneLineSummary LIMIT 20
MATCH (ts:SubagentTaskSpec {skill:'apt-st'}) WHERE ts.status='READY'
RETURN ts.name, ts.role LIMIT 10
```

### WorkBuffer 연속성
```cypher
MATCH (wb:WorkBuffer {status:'CURRENT'}) RETURN wb
```

# KG: ATOM_재배맨_v2_apt-st, SA_methodology_v4_triple_upgrade

---

## MIC Binding Disclaimer

> 이 SKILL.md에서 "Prometheus", "Naesengmoon", "88-Naesengmoon", "Longinus", "재배맨" 등의
> concrete 이름은 MIC_v1 MethodologySlot의 **현재 바인딩(currentConcrete)**이다.
> Slot이 다른 concrete로 교체되면 이 파일의 이름도 drift한다.
> 정본 해석: `MATCH (mic:MethodologyIntegrationContract {name:'MIC_v1'})-[:HAS_SLOT]->(s) RETURN s.name, s.currentConcrete`
> 유틸리티: `03_SCRIPTS/db/resolve_mic_slot.cypher`
> # KG: lesson-skill-mic-slot-ref-weak-2026-04-15

---

## 🔷 ST Rigor v2 (2026-04-17)
<!-- # KG: SA_ST_Rigor_v2_2026-04-17, CONTRACT_ATOM_ST2_contract_boundary_rule -->

**원칙**: "유연성은 엄밀성 비용의 여백에서만 허용." 기본값 = 엄밀. 함수 내부 로직 = 자유. 데이터 타입 / 연결부위 / 전체 아키텍처 / 데이터 플로우 / 폴더 경로 = **엄밀 강제**.

### Contract v2 Schema 필수 필드 (Rigor Matrix)

| 필드 | Tier | Why |
|---|---|---|
| input_type | hard_rigid | 타입 한 줄 = 거의 공짜, benefit 막대 |
| output_channels {success, error, timeout, partial} | hard_rigid | 오류 채널이 성공 경로만큼 중요 |
| depends_on {data, control} | hard_rigid | 병렬성 자동 도출의 전제 |
| parallelism_pattern | hard_rigid | SCW dispatcher가 읽음 |
| module_graph {package, folder_path, file_name, imports, exports} | hard_rigid | 폴더 트리 ST에 박힘 |
| precondition / postcondition | soft_semantic | prose \| dbc \| formal 3-mode |
| semantic_meaning | soft_semantic | 함수 내부 설명 OK |
| version (SemVer) | hard_rigid | 진화 추적 |
| target_file | hard_rigid | 롱기누스 바인딩 |

### module_graph.folder_path 결정 = span_path_projection 사영 (2026-06-01 배선)

> `module_graph.folder_path` / `target_file`는 **임의 지정 금지**. span DAG의 *canonical-parent 선택함수 사영*으로 결정한다 — `THEORY/APT/span_path_projection_prototype/span_path_projection.py :: project_paths(spans, edges, base)`.
>
> **규칙** (`_canonical_parent`):
> - 부모 0개 → `base/` (단일 root는 base 자체, 다중 root만 `base/slug`)
> - 부모 1개 → `parent_path/slug` (nest)
> - 부모 ≥2개 → `Span.primary_parent` 명시 시 그쪽 nest, 미지정 시 `base/shared/slug` (공유 span의 단일 home)
>
> **Why**: tree-ancestry 폐기 — span은 N:N 다중부모 DAG (`span-nn-dag`). 공유 span(예: 333_MOD_CRDT가 5앱의 공유 부모)을 단일경로로 강제하면 N번 복제 = fix가 중복을 생산(자기훼손). canonical-parent 사영은 well-definedness 증명(위상순서 귀납 + acyclicity)으로 "어떤 span도 두 경로를 갖지 않음"을 보장 → 중복 생산 불가.
>
> **ST 절차 배선**:
> 1. SP가 만든 `DECOMPOSES_TO` edge 집합 = span DAG. ≥2 부모인 span은 SP/ST에서 `primary_parent` 명시 (없으면 `shared/`로 라우팅).
> 2. ST 진입 시 `validate_well_defined(spans, edges)` 먼저 — cycle / primary_parent∉parents 면 BLOCK (사영 ill-defined).
> 3. `project_paths()` 일괄 사영 → 각 AtomicSpan의 `module_graph.folder_path` + `target_file` 결정. ad-hoc 폴더 지정·SCW 사후 폴더 재건 금지.
>
> # KG: wqi-st-path-from-span-ancestry-2026-05-30 (DONE_CANONICAL), hades-span-path-projection-realized-2026-05-30, span-nn-dag, lesson-flat-structure-root-decomposition-tree-discarded-at-materialization-2026-05-30

### Contract Boundary Rule

**언제 Contract 붙이나**:
- 2+ 곳에서 호출되는 함수 → **Contract 필수**
- layer 경계를 넘는 함수 (UI↔API, Agent↔Agent) → **Contract 필수**
- 그 외 함수 → parent Contract에 흡수 (과부하 방지)

### Bootstrap 2-Stage Policy

v2 schema가 자기자신을 기술할 때 발생하는 self-reference cycle 해결:
1. **Stage 1 (현재 seeding)**: 16 Contract는 v1 prose format으로 v2 schema 기술. `format_mode = 'bootstrap-v1-describing-v2'`
2. **Stage 2 (post-SCW)**: schema 문서(`06_KG/schemas/st_rigor_v2_schema.md`)가 v2 SDL로 승격 → 16 Contract도 v2 SDL 재직렬화. `format_mode = 'v2-native-sdl'`

### 참조 문서
- `06_KNOWLEDGE-GRAPH/schemas/st_rigor_v2_schema.md` — 주 schema
- `06_KNOWLEDGE-GRAPH/schemas/contract_graphql_format.md` — SDL format
- `06_KNOWLEDGE-GRAPH/schemas/rigor_heuristic.md` — tier 결정 rubric
- `06_KNOWLEDGE-GRAPH/schemas/agent_protocols/` — 에이전트 간 Contract
- `03_SCRIPTS/cypher/{parallel_derive, sp_hyperedge_migration, contract_semver}.cypher`

# KG: ATOM_ST2_contract_boundary_rule, CONTRACT_ST2_SharedType_ContractSchemaV2, MetaContract_CONTRACT_ST2_self_describing_meta

---

## 🌐 ST Exhaustive Cover Scope (v27 — 2026-04-29)

> **사용자 verdict (verbatim)**: "쌍그리 깡그리 st 에 kg 에 구축이 다되있어야하거든 ㅇㅇ; ... 그리고 나서 scw 개발 드가는거야"
>
> **Drift 정정**: 이전 v25/v26 ST = Contract+Task 2 영역만 cover (6.5x scope drift). v27 = exhaustive 8 영역 결정화 후만 SCW 진입.
>
> **Source**: `lesson-st-cover-scope-exhaustive-2026-04-29` (HIGH) + `lesson-prom-holes-audit-2026-04-29` (HIGH) + 8 PROM cycles (96 ResearchFinding) 학문 grounding.

### `{{cfg.st_decision_areas}}` ST Decision Areas (mandatory, SCW 진입 차단 게이트, 현재 8)

| # | Area | KG Decision Subtype | PROM cycle | Tier |
|---|---|---|---|---|
| 1 | **AST 구조** | `:ASTDecision` | `prom16-ast-foundation-2026-04-29` (16) | T1 ★ |
| 2 | **Workflow** | `:WorkflowDecision` | `prom16-workflow-design-2026-04-29` (16) | T1 ★ |
| 3 | **Design Patterns** | `:DesignPatternDecision` | `prom32-design-patterns-2026-04-29` (32) | T1 ★ |
| 4 | **Project Structure** | `:ProjectStructureDecision` | `prom16-project-structure-2026-04-29` (16) | T3 |
| 5 | **Data Flow** | `:DataFlowDecision` | `prom16-dataflow-design-2026-04-29` (16) | T1 ★ |
| 6 | **Algorithm** | `:AlgorithmDecision` | `prom32-algorithm-selection-2026-04-29` (32) | T3 |
| 7 | **Store** | `:StoreDecision` | `prom16-store-design-2026-04-29` (16) | T1 ★ |
| 8 | **Class Design** | `:ClassDesignDecision` | `prom16-class-design-2026-04-29` (16) | T3 |

→ Contract + Task = **결정의 결과물** (decision artifact). 8 Decision = **결정의 상위 결정** (decision-of-decisions).

### KG schema (8 sub-decision types)

```cypher
// 모든 Decision 의 공통 supertype
(:Decision {
  cycle_id: String,
  area: String,  // 'ast' | 'workflow' | 'design-pattern' | 'project-structure' | 'data-flow' | 'algorithm' | 'store' | 'class-design'
  rationale: String,
  alternatives_considered: [String],
  parent_lesson: String,
  created_at: String
})

// 8 area 별 specialized subtype (각 PROM REPORT 에 schema 정의됨)
(:Decision:ASTDecision {cst_or_ast, parser_choice, span_tracking, trivia_preserved, ...})
(:Decision:WorkflowDecision {workflow_form, runtime, soundness_verified, recursion_bound, ...})
(:Decision:DesignPatternDecision {primary_pattern_family, selected_patterns, archetype_mapping, ...})
(:Decision:ProjectStructureDecision {topology, build_system, package_manager, ai_navigation, ...})
(:Decision:DataFlowDecision {flow_form, delivery_semantics, watermark_strategy, idempotency_key, ...})
(:Decision:AlgorithmDecision {domain, selected, complexity_class, ai_discovered, formal_proof, post_quantum_safe, ...})
(:Decision:StoreDecision {store_tier, store_choice, pacelc, isolation, embedding_model, ...})
(:Decision:ClassDesignDecision {paradigm, language, hierarchy_depth_max, solid_compliance, archetype_mapping, di_container, ...})
```

### SCW Entry Gate Hook (mandatory)

```cypher
// SCW 진입 전 8 area 결정 모두 채워졌는지 검증.
// 1개라도 missing → block, return reason.

MATCH (cycle:AptCycle {name: $cycle_id})
OPTIONAL MATCH (cycle)-[:HAS_DECISION]->(d:Decision)
WITH cycle,
     collect(DISTINCT d.area) AS decided_areas,
     ['ast','workflow','design-pattern','project-structure','data-flow','algorithm','store','class-design'] AS required
WITH cycle, decided_areas, required,
     [a IN required WHERE NOT a IN decided_areas] AS missing
RETURN cycle.name AS cycle,
       size(missing) = 0 AS gate_passed,
       missing AS missing_areas,
       size(decided_areas) AS decided_count,
       8 AS required_count,
       CASE WHEN size(missing) = 0
            THEN 'OK — SCW entry permitted'
            ELSE 'BLOCKED — ST.exhaustive_cover incomplete: ' + toString(missing)
       END AS reason
```

### Tier 우선순위 (resource-bounded 진입 정책)

- **Tier 1 ★ HIGH 5 areas (1/2/3/5/7)**: 일반 cycle 진입 시 **반드시** 결정. (AST / Workflow / Design Patterns / DataFlow / Store)
- **Tier 3 MEDIUM 3 areas (4/6/8)**: 도메인이 명시적으로 요구할 때만 결정. 일상 cycle 은 default 채택 가능 (Project Structure = monorepo SYMPOSIUM, Algorithm = CLRS canonical, Class = composition 4-archetype trait).

→ 일상 cycle 의 minimal gate: **5/8 (Tier 1) 채워지면 SCW 진입 허용** (Tier 3 default-fallback 포함 시 full 8/8).

### 참조 (Longinus L1 binding)

- `s3://bhgman/apt-papers/STAxis/AST/PROM_16_REPORT.md` (Hole-1)
- `s3://bhgman/apt-papers/STAxis/Workflow/PROM_16_REPORT.md` (Hole-2)
- `s3://bhgman/apt-papers/STAxis/DesignPatterns/PROM_32_REPORT.md` (Hole-3)
- `s3://bhgman/apt-papers/STAxis/ProjectStructure/PROM_16_REPORT.md` (Hole-4)
- `s3://bhgman/apt-papers/STAxis/DataFlow/PROM_16_REPORT.md` (Hole-5)
- `s3://bhgman/apt-papers/STAxis/Algorithm/PROM_32_REPORT.md` (Hole-6)
- `s3://bhgman/apt-papers/STAxis/Store/PROM_16_REPORT.md` (Hole-7)
- `s3://bhgman/apt-papers/STAxis/Class/PROM_16_REPORT.md` (Hole-8)

# KG: lesson-st-cover-scope-exhaustive-2026-04-29, lesson-st-cover-tier1-complete-2026-04-29, ATOM_Skill_apt_st_v27_exhaustive_cover

---

## History

> Repo-level changes: [`/CHANGELOG.md`](../CHANGELOG.md). Per-commit: `git log -- apt-st/SKILL.md`.
> Architecture: Progressive Disclosure v3 — 626L _world.md split (2026-05-11):
> - Contract Examples 3 patterns (UserProfile/SearchIndex/HelloAPT): [`references/contract_examples.md`](references/contract_examples.md)
> - NFR Environment Variants (dev/staging/prod): [`references/nfr_env_variants.md`](references/nfr_env_variants.md)
> - Hardware Context Layer (REQUIRES_HARDWARE patterns): [`references/hardware_context.md`](references/hardware_context.md)
> - SEQUENCED_WITH Composition (Hoare chaining): [`references/sequenced_with.md`](references/sequenced_with.md)
> - Contract Sandwich (N:1 sharing): [`references/contract_sandwich.md`](references/contract_sandwich.md)
> - Failure Pattern Detection (7 signals): [`references/failure_patterns.md`](references/failure_patterns.md)
> - Amendment Scenarios (Fulfilled → Amended 5 triggers): [`references/amendment_scenarios.md`](references/amendment_scenarios.md)
> - tau_check 5/5 (Before/After Fix): [`references/tau_check.md`](references/tau_check.md)
> - CrystallizationEvent Hub (hub-and-spoke 4 roles): [`references/crystallization_hub.md`](references/crystallization_hub.md)
> - Boundary Mold (apt-st 정체): [`references/boundary_mold.md`](references/boundary_mold.md)
> - Cross-skill shared: [`../_common/`](../_common/) (Contract Lifecycle FSM § migrated).
> - Legacy redirect: `references/st_world.md`.

| Version | Date | Summary | KG Ref |
|---|---|---|---|
| **v27** | 2026-04-29 | **Exhaustive Cover Scope** — 8 ST decision areas (AST/Workflow/DesignPattern/ProjectStructure/DataFlow/Algorithm/Store/ClassDesign) materialized via 8 PROM cycles (96 ResearchFinding). SCW entry gate hook enforced. 사용자 verdict 정정 (Contract+Task 2-area drift → 8-area exhaustive). | `lesson-st-cover-scope-exhaustive-2026-04-29`, `lesson-st-cover-tier1-complete-2026-04-29`, 8 PROM cycles |
| **v26** | 2026-04-21 | A2 — Contract v2 (9 canonical axes + access_rights_closure + ArchitectureContract subtype + 6 CrossAxisInvariant + ReferenceSite/DriftMorphism) via ContractSchema slot. SA_Contract_v2_DbC_Interface_2026-04-21_v2 reference instance | `APT_v26_RFC_draft_2026-04-21`, `SA_Contract_v2_DbC_Interface_2026-04-21_v2`, `ATOM_ST2_contract_boundary_rule` |
| **v25** | 2026-04-17 | error_variants extension. SharedType → Contract.shared=true flag. SemanticTask = MethodologyConfig.vibe_coding_sweet (200-500 line, was hardcoded 500) | `APT_v25_RFC_draft_2026-04-17` |
| **v24** | 2026-04 mid | KG 정본 기반 재설계. AptClarificationNote 반영 | — |
| **v5~v23** | timestream | Crystallization (AtomicSpan → Contract + Task). Contract = typed DTO/Schema, NOT prose | — |

# KG history: ATOM_Skill_apt_st / lesson-prom16-skill-versioning-academic-2026-04-29 / lesson-prom16-skillver-progressive-disclosure-drift-2026-04-29
