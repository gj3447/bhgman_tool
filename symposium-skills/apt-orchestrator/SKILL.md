---
name: apt-orchestrator
kg_ref: ATOM_Skill_apt_orchestrator
version: "1.0.0"
channel: stable
canonical_name: apt-orchestrator
description: >
  APT phase orchestration 책무 — SA→SP→ST→SCW→MetaReview→Cleanup chain dispatch.
  v26.1 RFC1 (C(S) ↔ A3 axiom layer 분리) + RFC2 (two-tier cleanup) + Apt_FourPlusOne motif.
  MIC Binding + 5무기 Phase Integration Matrix 본체.
  Migrated 2026-05-22 (4/4 final): Cross-Repo + v26.1 + MIC + 5무기 Matrix body 본 skill 안에 이전 완료.
  Invoke when: parent /apt orchestrator dispatch only; phase 흐름 조회 / 5무기 invocation 조회.
  # KG: ATOM_Skill_apt_orchestrator, challenge-apt-fix2-srp-label-mislabel-2026-05-22, vr-apt-fix2-partial-install-naesengmoon-3lens-2026-05-22
---

## 🎛 Cross-Repo Working Pattern (2026-05-19)

> SYMPOSIUM (paper-layer KG 정전) ↔ bhgman_tool (apt-implementation-layer code) 측 layer split. APT skill 호출 시 작업 layer 측 명시:
> - **KG = single canonical truth** (Neo4j on Mac VM, dgx pod worker). Cross-repo session 측에서도 KG 측 단일 entry.
> - **File edit 측 절대경로** mandatory. `~/CD/SYMPOSIUM/...` (paper) ≠ `~/CD/bhgman_tool/...` (tool). Same-layer 비교: ruflo/LangGraph/CrewAI ↔ bhgman_tool only (paper-layer 비교 = category error).
> - **APT-development work** default layer = bhgman_tool. SYMPOSIUM/THEORY 측 paper crystallization (자료집).

# KG: feedback_layer_split_symposium_vs_bhgman_tool / reference_symposium_monorepo_mirror / reference_kg_infra_topology

---

## 🎛 v26.1 Addendum — RFC1 + RFC2 + Apt_FourPlusOne (2026-04-29)

> v26.1은 v26 prose에 손대지 않고 KG slot resolve로만 적용. 본문 한 줄도 직접 magic number 박지 않음 (A6 resolve-only 준수).

### v26.1-A. C(S) predicate ↔ A3 axiom layer 분리 (RFC1)

```cypher
// C(S) = self-containment (한 Span 내부 atomicity 검사)
MATCH (cs:DefinedTerm {name:'APT_Layer_CrystallizationFrontier'}) RETURN cs.description
// 5-predicate: 타입 표현 / 의미 완결 / 구현 / 테스트 / 분해 비경제성

// A3 = sibling-wellformedness (Span 간 관계 검사)
MATCH (a3:KnowledgeNode {name:'APT20_S2_LayerIndependence'}) RETURN a3.description

// Greek 5-predicate (deprecated)
MATCH (greek:KnowledgeNode {name:'APT19_A4_CrystallizationFrontier'})
WHERE 'ARCHIVED' IN labels(greek) RETURN '⚠️ deprecated, use APT_Layer_CrystallizationFrontier'
```

**중요**: C(S)는 *한 Span 내부* 검사 (5-predicate). 형제 Span 간 wellformedness는 *별도 axiom layer* (A3 SiblingIndependence). 한 노드에 섞지 말 것.

### v26.1-B. Two-tier cleanup (RFC2)

```cypher
MATCH (rfc:MethodologyRFC {name:'rfc-apt-two-tier-cleanup-2026-04-29'}) RETURN rfc.proposes
// Local RGR: 각 transition (SA→SP, SP→ST, ST→SCW) 끝에 mini-RGR 3-beat
// Global Phase 6: 4 phase 종료 후 cross-phase 누적 관측 + 4-tool ratchet
```

phase tree에서 transition 3곳에 mini-RGR marker 추가됨. Phase 6은 *유지* — 폐기 아님.

### v26.1-C. Apt_FourPlusOne meta-motif

```cypher
MATCH (m:AptMetaMotif {name:'Apt_FourPlusOne'})<-[:INSTANCE_OF_MOTIF]-(inst)
RETURN m.formal_signature, collect(inst.name) AS instances
// Framework self-similar: C(S) + 5-weapons + 4-phase 모두 4 worker + 1 meta 구조
```

**활용**: 새 컴포넌트 도입 시 4+1 fit 검토. 같은 layer 5번째 = anti-pattern. 5번째는 *다른 layer*여야 함.

# KG: rfc-apt-cs-axiom-visibility-drift-2026-04-29, rfc-apt-two-tier-cleanup-2026-04-29, Apt_FourPlusOne

### v26.1-D. APT essence — S-functor factorization (2026-05-14)

> APT 본질 정리: `F : MeaningSpace^∞ → SourceCode = F_SCW ∘ F_ST ∘ F_SP ∘ F_SA`.
> 4-phase 파이프라인은 *철학적 비유*가 아니라 **Mac Lane CWM II.3 의미의 functor 합성**이다.

```cypher
// Essence canonical
MATCH (e:AptEssence {name:'APT_essence_canonical_2026-05-14'})
RETURN e.factorization, e.lean_proof_path, e.theorem_count
// expected: factorization='F = F_SCW ∘ F_ST ∘ F_SP ∘ F_SA',
//           lean_proof_path='MIND/lean_formalization/APT_FunctorFactorization.lean',
//           theorem_count=12

// Sprint seed
MATCH (s:Span {name:'span-essence-S-functor-2026-05-14'}) RETURN s.status, s.outcome
```

**4 stage-functor** (각각 Aristotle αἰτία 매핑):

| Functor | 출발 | 도착 | Aristotle 원인 |
|---|---|---|---|
| `F_SA`  | MeaningSpace  | AnchorCtx       | Material (질료) |
| `F_SP`  | AnchorCtx     | SpanDecomp      | Formal (형상) |
| `F_ST`  | SpanDecomp    | ContractSchema  | Efficient (작용) |
| `F_SCW` | ContractSchema| SourceCode      | Final (목적) |

**핵심 정리** ([`MIND/lean_formalization/APT_FunctorFactorization.lean`](../../../MIND/lean_formalization/APT_FunctorFactorization.lean), 12 theorem / 0 sorry / Lean 4.29.1 PASS):
- T1 `F_total_well_typed` — `SmallFunctor MeaningSpace SourceCode` 잘 타입됨
- T2 `factorization_associative` — 합성 결합법칙 (obj_map level)
- T3 `factorization_matches_seed` — 정확히 `F_SCW ∘ F_ST ∘ F_SP ∘ F_SA` 와 일치
- T4 `F_total_obj_chain` — 모든 의미 운반체가 SA→SP→ST→SCW 4-stage 결정적 추적
- T5-T8 `F_{SA,SP,ST,SCW}_id` — 각 stage functoriality (id 보존)
- T9 `cardinality_monotonic_4stage` — `|◇P_0| ≥ |◇P_1| ≥ |◇P_2| ≥ |◇P_3| ≥ |◇P_4|` (Hegel Aufhebung)
- T10 `cardinality_endpoints_bound` — Meaning ≥ Code 추이성
- T11 `apt_essence_witnessed` — 6 본질 불변량 동시 witness
- T12 `essence_seed_equation` — essence 등식 `rfl`

**Deferred (TODO-1..6, ~1,030 lines Mathlib-backed sprint)**:
Free category Hom carriers / non-trivial functoriality / monoidal product /
first-principles cardinality drop / Curry-Howard 함자성 / Lakatos excess content.

Sister Lean: `APT_Cycle_Functor.lean` (phase-level, 9 thm — object map) +
`APT_FunctorFactorization.lean` (morphism-level, 12 thm — functor laws, NEW 2026-05-14).

# KG: APT_essence_canonical_2026-05-14, span-essence-S-functor-2026-05-14,
#     apt-philosophical-foundations-2026-05-11

### v26.1-E. Contract root axiom — 모든 phase contract-bound (2026-05-27)

> Contract = APT 전역 root 공리 (phase-국소 ST 산출물 아님). 병렬-by-default → 병렬로 쪼갠 조각이 compose되려면 인터페이스 계약이 필수 = 재배맨(plan-first, 병렬 dispatch)의 **dual complement** (병렬분해 ↔ 인터페이스합의, 한 동전 양면).
> **PROM16 정밀화 (2026-05-27, 4축 만장일치 HIGH)**: "계약 필수"는 무조건 아님. **contract-bound ⟺ inter-span 결합도>0** (공유상태/통신/간섭). 결합도=0(독립 span, embarrassingly-parallel)에선 계약이 **대수 항등원**(separation `emp` / rely `Id` / monoid `ε`)으로 degenerate = present but ZERO constraint (contract-free 아님 — steelman 통과로 정밀화). 계약 강도는 결합도에 **단조 비증가(ordinal)** (비례 ∝ 아님), unit(0)부터 상승. 형식근거: CSL Disjoint Concurrency Rule(O'Hearn 2007 Gödel Prize) + rely-guarantee(rely=Id) + session MIX/CUT + monoid identity. → SP 분해 시 결합도 판정, 결합 span만 ST에서 non-trivial Contract. **GUARD 해소 (steelman 2026-05-27)**: 계약은 *항상 존재*하므로 APT는 contract 분석 SKIP 안 함 — 독립 span은 항등원으로 *판정*될 뿐(부재 아님), edge-absence shortcut 무의미. 검증: `vr-prom16-contract-dual-naesengmoon-3lens-2026-05-27` (CONDITIONAL 0.72) + 독립성 재실행 PASS `rf-prom16-contract-dual-steelman-opposite-2026-05-27`.
> 모든 phase가 contract-bound: SA=anchor/identity contract / SP=span 간 interface contract / ST=Contract v2 결정화 / SCW=contract-first TDD. 5 phase에 prose 중복 금지 — KG resolve로 상속 (A6 resolve-only).
> enforce 세부는 KG 정본. 사용자 verdict 2026-05-27 ("contract 원칙도 apt에 뿌리깊게 박아줘야해").

```cypher
MATCH (ax:AptAxiom {name:'apt-contract-root-axiom-2026-05-27'})
OPTIONAL MATCH (ax)-[:DUAL_WITH]-(jb) RETURN ax.principle, ax.relation_to_jaebaeman AS dual, jb.name AS jaebaeman_reframe
```

# KG: apt-contract-root-axiom-2026-05-27, jaebaeman-planfirst-essence-reframe-2026-05-27

---

## 🔗 MIC Binding (SOLID-DIP) — 재배맨 진짜 구조

> 본 skill의 5대 무기 참조는 **concrete 이름 대신 MethodologySlot 조회**로 호출.
> Treasure 교체 시 `MIC_v1` 노드만 수정 → 본문 무수정.

**IS slot**: Orchestrator (5대 무기 조율)
**USES slots**: Harness, ResearchProvider, AdversarialValidator, KgCodeBinder, SubagentSeeder
**참고**: MetaVerifier는 AdversarialValidator(Naesengmoon)의 --lens mathematical로 통합. FeedbackProvider는 창발 속성(슬롯 아님).

**동적 resolution**:
```cypher
MATCH (mic:MethodologyIntegrationContract {name:'MIC_v1'})-[:HAS_SLOT]->(s:MethodologySlot)
RETURN s.name, s.currentConcrete, s.invocation
```

본문의 `Prometheus`/`Naesengmoon`/`Longinus`/`재배맨` 등은 MIC slot의 **현재 스냅샷**. 진짜 호출은 `s.invocation`.
88-Naesengmoon은 별도 concrete가 아니라 `Naesengmoon --lens mathematical`. MetaVerifier 슬롯은 Naesengmoon의 렌즈셋으로 통합됨.
피드백은 5대 무기 순환의 창발 속성 — FeedbackProvider 슬롯은 EMERGENT 상태.

# KG: lesson-feedback-is-emergent-not-weapon-2026-04-16, lesson-taliban-lens-pluggable-refactor-2026-04-16, MIC_v1, lesson-apt-not-truly-jaebaeman-2026-04-14

---

## 🛠 5무기 Phase Integration Matrix — Active Weapon Calls (NEW 2026-05-14)

> **APT 는 indirect MIC slot reference 만으로는 살아있지 않다.** 각 phase 가 *어느 무기*를 *어느 step*에서 *어떻게* 호출하는지 명시적이지 않으면 5무기는 dormant slot 으로 남는다. 본 섹션은 그 활성 호출망을 1:1 표화한 *integration matrix*. MIC slot indirect → 명시적 invocation pattern 으로 격상.

### A. Integration Matrix — Phase × Weapon × Step × Invocation

| Phase | Primary Weapons | Step in Phase | Invocation Pattern | Output |
|-------|----------------|---------------|--------------------|--------|
| **SA** (1/5) | **Prometheus** + **Longinus** | Step 1 KG 탐색 / Step 2 anchor 결정 / Step 3 5 core fields | `/prom <N> "<sa_topic>"` (지식 선행) + Longinus L1-L2 reverse binding (KG anchor → 기존 SemanticAnchor 후보) | `SemanticAnchor` 노드 + `ResearchFinding` N 개 (verified=true) + L1-L2 ReferenceSite |
| **SP** (2/5) | **재배맨** + **Naesengmoon** | Step 4 D(S) 재귀 분해 / Step 5 wave_index 할당 / Step 6 C(S) 5-predicate gate | `재배맨` SubagentTaskSpec seed per Span (parallel decomposition) + `/tlb <SPAN> --lens constitutional` per Crystallization Frontier 진입 후보 | `Span` DAG (모든 leaf = `AtomicSpan`) + `VerdictRecord` per gate |
| **ST** (3/5) | **Longinus** + **재배맨** | Step 7 Contract DTO 결정화 / Step 8 ReferenceSite 7-tuple binding / Step 9 1:1:1:1 (AtomicSpan : Contract : Task : Seed) | Longinus L3-L4 binding (Contract → AtomicSpan ReferenceSite) + 재배맨 per-AtomicSpan SubagentTaskSpec seed (TDD RED → GREEN test 4-tuple) | `Contract` (DbC 4-측면) + `SemanticTask` + `SubagentTaskSpec` (per AtomicSpan) + Longinus 7-tuple |
| **SCW** (4/5) | **재배맨** + **Naesengmoon** + **Longinus** | Step 10 wave dispatch (single-message N parallel) / Step 11 RED→GREEN→REFACTOR / Step 12 Code→KG ref comment / Step 13 FulfillmentGate | 재배맨 single-message parallel `Task` dispatch (max=`parallel_max_agents`) + Longinus L5-L7 forward binding (Code → KG ref `# KG: <node>` comment) + `/tlb` FulfillmentGate 7-check | `SourceCodeNode` (with `# KG:` refs) + `MATERIALIZES` edges + Naesengmoon `FulfillmentGate` verdict |
| **MetaReview** (5/5) | **Naesengmoon** + **Prometheus** | Step 14 의심 발견 / Step 15 Lesson 결정화 / Step 16 SKILL.md 패치 / Step 17 Naesengmoon Gate 자체재검증 | `/tlb <MetaReview output> --lens constitutional` (rubber-stamp 방지) + `/prom <small N> "<lesson_topic>"` (lesson distillation, 외부 정전 grounding) | `Lesson` node + SKILL.md MIC slot patch + `VerdictRecord` Naesengmoon gate APPROVED |
| **Cleanup** (6/5, RFC2) | **Harness** + **Naesengmoon** | Step 18 3-tier package audit / Step 19 4-tool ratchet / Step 20 folder-level CCP/ADP gate | Harness 3-tier (IDE-host / runtime / managed) 매핑 진단 + `/88-taliban <folder>` mathematical lens (CCP/CRP/REP/ADP/SDP/SAP folder-level audit) + `tach + complexipy + lizard + vulture + deptry` 4-tool ratchet | `CleanupVerdict` (PASS/NEEDS_REFACTOR/BLOCK) + Harness tier 라벨 + folder-level Lesson |

### B. Cypher Snippet — Weapon Invocation per Phase

```cypher
// SA phase: Prometheus 호출 (knowledge pre-fetch via MIC ResearchProvider slot)
MATCH (mic:MethodologyIntegrationContract {name:'MIC_v1'})
      -[:HAS_SLOT]->(s:MethodologySlot {name:'ResearchProvider'})
RETURN s.currentConcrete AS weapon, s.invocation AS pattern
// expected: weapon='Prometheus', pattern='/prom <N> "<topic> — <subgoal>"'
// trigger: SA Step 1 (KG sparse: INFORMED_BY < density_min_informed_by) OR Step 3 (new SemanticAnchor 5 core fields 미충족)

// SA phase: Longinus 호출 (KG anchor binding via 7-Layer Reference slot)
MATCH (mic:MethodologyIntegrationContract {name:'MIC_v1'})
      -[:HAS_SLOT]->(s:MethodologySlot {name:'KgCodeBinder'})
RETURN s.currentConcrete AS weapon, s.invocation AS pattern
// expected: weapon='Longinus', pattern='L1-L7 ReferenceSite 7-tuple binding'
// trigger: SA Step 2 (anchor 재사용/브랜치 결정 시 기존 SemanticAnchor 후보 reverse scan)

// SP phase: 재배맨 호출 (Span DAG decomposition seed via SubagentSeeder slot)
MATCH (mic:MethodologyIntegrationContract {name:'MIC_v1'})
      -[:HAS_SLOT]->(s:MethodologySlot {name:'SubagentSeeder'})
RETURN s.currentConcrete AS weapon, s.invocation AS pattern
// expected: weapon='재배맨/JaebaeMan', pattern='SubagentTaskSpec UNWIND batch, parent Pre-fetch → Dispatch → Collect → Write'
// trigger: SP Step 4 (D(S) recursive decomposition — 자식 Span 후보 N 개 parallel research)

// SP phase: Naesengmoon 호출 (Crystallization Frontier 진입 gate via AdversarialValidator slot)
MATCH (mic:MethodologyIntegrationContract {name:'MIC_v1'})
      -[:HAS_SLOT]->(s:MethodologySlot {name:'AdversarialValidator'})
MATCH (ls:LensSet {name:'constitutional'}) WHERE ls.deprecated <> true
RETURN s.currentConcrete AS weapon, s.invocation AS pattern, ls.lens_count AS lens_count
// expected: weapon='Naesengmoon', pattern='/tlb <SPAN_id> --lens constitutional'
// trigger: SP Step 6 (Span → AtomicSpan 격상 후보 C(S) 5-predicate gate 진입)

// ST phase: Longinus 호출 (Contract → ReferenceSite 7-tuple binding)
MATCH (mic:MethodologyIntegrationContract {name:'MIC_v1'})
      -[:HAS_SLOT]->(s:MethodologySlot {name:'KgCodeBinder'})
RETURN s.currentConcrete AS weapon, s.invocation AS pattern
// trigger: ST Step 8 (Contract 결정화 직후 AtomicSpan 측 ReferenceSite 7-tuple 작성 — name/kind/source/target/cardinality/label/provenance)

// ST phase: 재배맨 호출 (per-AtomicSpan 1:1:1:1 Contract+Task+Seed)
// trigger: ST Step 9 (Crystallization Frontier 통과 후 AtomicSpan 마다 SubagentTaskSpec seed 자동 생성, TDD RED 작성용)

// SCW phase: 재배맨 wave dispatch (single-message N parallel Task call)
MATCH (cfg:MethodologyConfig {name:'MethodologyConfig_default_v26'})
RETURN cfg.parallel_max_agents AS max_parallel, cfg.parallel_strategy AS strategy
// trigger: SCW Step 10 (wave_index 같은 SubagentTaskSpec batch → single-message Task() dispatch)

// SCW phase: Longinus Code→KG ref comment (forward binding L5-L7)
// trigger: SCW Step 12 (GREEN 통과 후 코드 작성 시 모든 함수/클래스에 `# KG: <node_name>` 주석 강제)

// SCW phase: Naesengmoon FulfillmentGate 7-check
MATCH (ls:LensSet {name:'constitutional'}) RETURN ls.lens_count
// trigger: SCW Step 13 (cargo test PASS + 7-check: executor!=critic / LensSet completeness / prior VR APPROVED / Contract 4-측면 / 코드 KG ref / impact_tests / fat-file ratchet)

// MetaReview phase: Naesengmoon 자체재검증 + Prometheus lesson distillation
MATCH (s1:MethodologySlot {name:'AdversarialValidator'}),
      (s2:MethodologySlot {name:'ResearchProvider'})
RETURN s1.invocation AS taliban_call, s2.invocation AS prometheus_call
// trigger: MetaReview Step 17 (Lesson 결정화 후 Naesengmoon Gate 통과 + 외부 정전 grounding 측 Prometheus mini-run)

// Cleanup phase: Harness 3-tier + Naesengmoon folder-level audit
MATCH (mic:MethodologyIntegrationContract {name:'MIC_v1'})
      -[:HAS_SLOT]->(s:MethodologySlot {name:'Harness'})
RETURN s.currentConcrete AS weapon, s.invocation AS pattern
// expected: weapon='Harness', pattern='3-tier instance routing (L_MC/L_RT/L_IDE)'
// trigger: Cleanup Step 18 (폴더 구조 ↔ Harness 3-tier 매핑 진단)

MATCH (ls:LensSet {name:'mathematical'}) WHERE ls.deprecated <> true RETURN ls.lens_count
// trigger: Cleanup Step 19-20 (88-taliban mathematical lens 측 folder-level CCP/ADP audit)
```

### C. KnowledgeHub Cross-Link (Active Hub Resolve)

> 본 matrix 측 각 weapon 측 정전 hub 노드는 KG 측 `hub-*` KnowledgeHub 노드. SKILL.md drift 시 hub 측 resolve 로 대체.

```cypher
// 5 weapon hubs (canonical entry points)
MATCH (h:KnowledgeHub) WHERE h.name STARTS WITH 'hub-'
  AND h.name IN [
    'hub-prometheus-research',
    'hub-jaebaeman-sop',
    'hub-taliban-immunity',
    'hub-longinus-reference',
    'hub-harness-3tier'
  ]
RETURN h.name AS hub, h.canonical_skill AS skill_path, h.essence AS essence_one_liner
ORDER BY h.name
```

| Hub | Skill path | Essence (one-liner) |
|-----|------------|---------------------|
| `hub-prometheus-research` | `SKILLS/prometheus/SKILL.md` | 지식-행동 spiral (Hegel reframe), N parallel subagent UNWIND batch |
| `hub-jaebaeman-sop` | `SKILLS/jaebaeman/SKILL.md` | Subagent Orchestration Protocol — KG 측 SubagentTaskSpec 씨앗 기반 |
| `hub-taliban-immunity` | `SKILLS/taliban/SKILL.md` | 적대적 검증 GAN-D, LensSet 플러거블 (constitutional/mathematical/solid) |
| `hub-longinus-reference` | `SKILLS/longinus/SKILL.md` | 7-Layer Reference Model + BX Lens Laws, KG ↔ Code 양방향 binding |
| `hub-harness-3tier` | `SKILLS/harness/SKILL.md` | Industry agent scaffolding 3-tier (IDE-host / runtime / managed) sibling family |

### D. Phase Transition mini-RGR — Weapon Call Trigger (RFC2 v26.1)

> Two-tier cleanup 측 *local* mini-RGR (RFC2) 도 5무기 측 호출 trigger 가 박혀있다. transition 측 RED/GREEN/REFACTOR 3-beat 각각 어느 무기 호출:

| Transition | RED beat | GREEN beat | REFACTOR beat |
|-----------|----------|-----------|---------------|
| SA → SP | (없음 — SA 결정화 직후) | Naesengmoon `--lens constitutional` (SA 5 core fields 완전성 gate) | 재배맨 (SP Span 첫 분해 SubagentTaskSpec seed) |
| SP → ST | Naesengmoon prior contract conflict 검사 | Naesengmoon Crystallization Frontier gate (모든 leaf=AtomicSpan) | Longinus 중복 ReferenceSite 통합 |
| ST → SCW | Naesengmoon prior code conflict 검사 (file move/delete plan) | 재배맨 wave dispatch GO/NO-GO | Harness 3-tier file placement audit (atomic-span dump 평면 누적 차단) |

### E. Anti-Pattern — Weapon Bypass Failure Modes

| Anti-pattern | Phase | 위반 무기 | 위반 결과 | 정정 |
|--------------|-------|-----------|-----------|------|
| KG-skip framing (R1-R5 미수행) | 임의 | Prometheus | 외부 정전 grounding 없는 가설 | `MIC_v1.ReasoningProtocol → KGFirstCheck_v1` 강제 |
| Same-model critic | Gate 전체 | Naesengmoon | Rubber-stamp 자기재검증 | HR3 (Critic model differs from design model) |
| No KG ref comment | SCW | Longinus | Code orphan, drift detect 불가 | SCW Step 12 강제 `# KG:` 주석 |
| Sequential Task dispatch | SCW | 재배맨 | wave-batch ≠ true parallel | single-message N Task() in one assistant turn |
| Folder flat dump | Cleanup | Harness | CCP/ADP 위반, 평면 누적 | 4-tool ratchet + 3-tier 매핑 진단 |
| Self-application | MetaReview | Naesengmoon | 무한 recursion (max_depth=1, delta=0) | `self_application_forbidden=true` 강제 |

# KG: hub-prometheus-research, hub-jaebaeman-sop, hub-taliban-immunity, hub-longinus-reference, hub-harness-3tier, MIC_v1, lesson-feedback-is-emergent-not-weapon-2026-04-16

---

## ✅ Migration Status (2026-05-22)

- **Status**: MIGRATED (4/4 final, completes cascade).
- **Source**: was at `SKILLS/apt/SKILL.md` lines 33-40 (Cross-Repo) + 44-132 (v26.1) + 146-166 (MIC) + 170-302 (5무기 Matrix).
- **Cascade order**: apt-magic-resolve (1/4) → apt-autoflow-guard (2/4) → apt-lens-enforce (3/4) → apt-orchestrator (4/4).
- **Closes**: `challenge-apt-fix2-srp-label-mislabel-2026-05-22` SCAFFOLDED_BODY_MIGRATION_PENDING → **ALL_4_BODIES_MIGRATED**.

# KG: scaffold-apt-skill-decomposition-2026-05-22, migration-apt-orchestrator-body-2026-05-22
