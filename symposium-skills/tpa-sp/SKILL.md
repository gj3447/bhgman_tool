---
name: tpa-sp
kg_ref: ATOM_Skill_tpa_sp
version: "1.2.0"
channel: stable
provenance: AI_DERIVED_FROM_USER_PRIMARY  # SKILL.md = AI engineering; underlying methodology = user-primary mythology (12 apostles + 5 weapons). Per PseudepigraphaValidationGate-v1-2026-04-30.
description: >
  TPA TargetPyramid (SP) — Phase 3/4. APT SP 거울 (역순).
  Pattern Library (51 DesignPattern 노드) 매칭. confidence ≥0.7 INSTANCE_OF / <0.7 RESEMBLES.
  카테고리별 검증 전략 매핑: Distributed→MetaVerifier(Naesengmoon --lens mathematical), Structural→AST,
  Behavioral→call graph, Creational→grep, PL→ResearchProvider.
  Gate Check Hook 강제: ST Gate 통과 없이 진입 불가.
  # KG: ATOM_Skill_tpa_sp, CONTRACT_AS_TPA_sp_SKILL, TPA_methodology_v10
---

<!-- KG: TASK_AS_TPA_sp_SKILL -->
<!-- KG: CONTRACT_AS_TPA_sp_SKILL -->
<!-- KG: IMPLEMENTS_SHARED CONTRACT_SHARED_TPA_SubSkillTemplate -->

## 🔗 MIC Binding (SOLID-DIP)

**IS slot**: TPA_Phase (SP, 3/4)
**USES slots**: SubagentSeeder, ResearchProvider (모르는 pattern), MetaVerifier (Distributed 수학 속성), AdversarialValidator, **AbstractionInducer(유레카), StaleArchiver(오캄)** (7-stage 2026-05-30)

> **유레카 (AbstractionInducer) — SP 본령 (2026-05-30):** span 역엮기 = 소스 패턴에서 추상 계층을
> bottom-up induction. 단순 pattern-library 매칭을 넘어 *새 추상 개념 재창조* (= APT/SCW 하데스의
> dual). 매칭 안 되는 NovelPattern 후보가 유레카 induction 대상. `/eureka`.
> **오캄 (StaleArchiver) — SP 보조:** 역엮기 중 만나는 dead code/stale/중복 노드는 복원 피라미드에
> 안 싣고 격리 (archive-only, 삭제 금지). `/occam`. KG: `tpa-7stage-eureka-core-2026-05-30`.

```cypher
MATCH (mic:MethodologyIntegrationContract {name:'MIC_v1'})-[:HAS_SLOT]->(s:MethodologySlot)
WHERE s.name IN ['SubagentSeeder','MetaVerifier','AdversarialValidator','ResearchProvider']
RETURN s.name, s.currentConcrete, s.invocation
```

> ⚠️ **본문의 concrete 이름(재배맨/Prometheus/Naesengmoon/Longinus/88-Naesengmoon)은 MIC slot 현재 스냅샷.**
> 진짜 호출은 `s.invocation` 경유. MIC_v1 교체 시 본문 무변경.

# KG: MIC_v1, lesson-tpa-gap-04-pattern-verification-strategy-2026-04-14, lesson-tpa-gap-88taliban-scope-2026-04-14, lesson-skill-mic-slot-ref-weak-2026-04-15

---

# /tpa-sp — TargetPyramid: 패턴 인식 + 수학 검증

> **질문**: "이 심볼들이 모여 어떤 패턴/구조를 이루는가?"
> Pattern Library 없이 SP 진입 금지. 중복 노드 방지.

## ⛔ GATE CHECK (Hook 강제)

> `apt-gate-check.sh`가 자동 실행.
> **ST Gate 미통과 시 `permissionDecision: deny`.**
> BLOCKED 시: `/tpa-st` → `/taliban` → ST Gate 통과 → `/tpa-sp` 재호출.

필수 조건:
```cypher
MATCH (exec:TPA_Execution {status:'IN_PROGRESS_ST'})
      -[:HAS_VALIDATION]->(vr:ValidationResult {phase:'ST', verdict:'APPROVED'})
RETURN exec LIMIT 1
```

---

## 진입 의식

```cypher
MATCH (ts:SubagentTaskSpec {name:'taskspec-tpa-SP', skill:'tpa'})
RETURN ts.checkItems, ts.cypherQueries, ts.expectedOutcome, ts.treasure_coverage_min

// Pattern Library 존재 확인 (pre-check)
MATCH (p:DesignPattern) RETURN count(p) AS pattern_count
// 기대: pattern_count >= 38 (GoF23 + 분산10 + PL5). 51+ 권장.
```

**Pattern Library 없이 SP 실행 금지** — 중복 노드 생성 방지 (gap04 해결).

---

## Pattern 매칭 — 카테고리별 검증 전략 (gap04)

| Pattern Category | Verification Strategy | Tool (MIC slot) |
|---|---|---|
| Distributed (CRDT/BFT/HotStuff/Kademlia 등) | 수학 속성 (commute/assoc/idempotent/safety) | MetaVerifier (Naesengmoon --lens mathematical) |
| Structural (Facade/Adapter/Composite 등) | AST 시그니처 매칭 (wrapping/delegation) | KgCodeBinder + grep |
| Behavioral (Strategy/Observer/Command 등) | 메서드 호출 그래프 (polymorphic dispatch) | KgCodeBinder + call graph |
| Creational (Factory/Builder/Singleton 등) | 생성 지점 추적 (instantiation trace) | KgCodeBinder + grep |
| PL (DuckTyping/TypeClass/Monad 등) | 언어 기능 존재 확인 | ResearchProvider (lang docs) |

## confidence 규칙

<!-- KG: lesson-tpa-sp-no-pattern-checklist-2026-04-16 -->

### INSTANCE_OF 판정: 필수요소 체크리스트 기반 (v2)

**"이름이 비슷하다" ≠ INSTANCE_OF. 패턴의 필수요소가 전부 있어야 한다.**

| Pattern | 필수요소 (전부 충족해야 INSTANCE_OF) |
|---------|----------------------------------|
| State | 상태별 행동 차이 + 상태 객체가 dispatch + 컨텍스트가 상태에 위임. 단순 enum ≠ State Pattern. |
| Observer | 동적 등록/해제 + 이벤트 broadcast + subject가 observer 구체 타입 모름 |
| Strategy | 런타임 교환 가능 + 같은 인터페이스 + 클라이언트 코드 변경 없이 전략 교체 |
| Builder | consuming self 또는 &mut self 메서드 체인 + build() 최종 생성 |
| Facade | 복잡한 서브시스템 위임 + 자체 로직 최소 (직접 오케스트레이션하면 Mediator) |
| Factory | 생성 로직 분리 + 반환 타입이 trait/interface (concrete 아님) |
| Adapter | 기존 인터페이스 변환 + 원본 코드 수정 없음 |
| Composite | 개별/집합 동일 인터페이스 + 재귀 구조 |

**판정 절차**:
1. 필수요소 전부 확인 (코드에서 증거 인용)
2. 전부 충족 → confidence ≥ 0.7 → INSTANCE_OF
3. 일부만 충족 → confidence < 0.7 → RESEMBLES
4. 이름만 비슷 → confidence < 0.4 → 매칭하지 않음

```cypher
// ≥ 0.7 + 필수요소 전부 충족 → INSTANCE_OF
MERGE (src)-[r:INSTANCE_OF {confidence:$c, evidence:$ev, strategy:$verified_by, checklist_pass:true}]->(p:DesignPattern)
WHERE $c >= 0.7

// < 0.7 → RESEMBLES
MERGE (src)-[r:RESEMBLES {confidence:$c, evidence:$ev, missing_elements:$missing}]->(p:DesignPattern)
WHERE $c < 0.7
```

**evidence 없는 INSTANCE_OF = RUBBER_STAMP 위반.** HR11 (증거 필수).

### 변환 패턴 coverage rate (TPA-D3 fix, 2026-06-01)

<!-- KG: TPA-D3-2026-06-01 (:MethodologyDefect), lesson-tpa-dogfood-spacegirl-defects-2026-06-01 -->

> **결함 출처**: spacegirl_tool TPA 도그푸드 — Transformer 패턴(식별자 치환)이 INSTANCE_OF로 판정됐으나, JS template literal `${...}` 내부 식별자가 **미치환**인 *불완전 구현*이 통과했다. 필수요소 체크리스트는 "패턴이 *있나*"만 보고 "패턴이 *모든 대상에 적용되나*"(coverage)는 안 본다.

**Transformer / Visitor / Mapper / Interpreter 류 *적용범위가 본질인* 패턴**은 필수요소 체크리스트에 더해 **coverage rate**를 측정한다:

```
coverage_rate = (패턴이 실제 적용된 대상 site 수) / (적용 대상이어야 할 전체 site 수)
```

- 측정은 **코드레벨 실측** (정적 카운트 또는 실행 프로빙) — 추정 금지.
- `coverage_rate < 1.0` → `INCOMPLETE_TRANSFORM` flag + 미적용 site 목록 evidence.
- coverage가 본질인 패턴에서 `coverage_rate < 0.9` → confidence 상한 0.7 (INSTANCE_OF 못 줌, RESEMBLES).

```cypher
MERGE (src)-[r:INSTANCE_OF {confidence:$c, evidence:$ev, checklist_pass:true,
                            coverage_rate:$cov, uncovered_sites:$gaps}]->(p:DesignPattern)
WHERE $c >= 0.7 AND ($cov IS NULL OR $cov >= 0.9)
// coverage 본질 패턴인데 cov < 0.9 → RESEMBLES + INCOMPLETE_TRANSFORM
```

---

## Distributed 패턴 매칭 시 MetaVerifier 자동 호출 (v0.4 통합)

**조건**: `INSTANCE_OF` 엣지가 `DesignPattern {category:"Distributed"}`로 생성되는 즉시.

### 자동 트리거 (매 distributed 매칭마다)

```
역할: 88-Naesengmoon MetaVerifier (agentId=M<idx>)
TaskSpec: MATCH (ts:SubagentTaskSpec {name:'taskspec-88taliban-*'}) RETURN *
Target: 방금 매칭한 Distributed DesignPattern (CRDT/BFT/HotStuff/Kademlia/Raft/Paxos/LWW/Vector_Clock/HLC/Merkle_Tree)
검증할 수학 속성: commute / assoc / idempotent / safety / liveness (패턴별 상이)
출력: ValidationResult {phase:'SP-MetaVerify', verdict:$v, math_properties:[...], target:<pattern>}
```

### FulfillmentGate Cypher 강제 (taskspec.fulfillment_gate_cypher_meta 참조)

```cypher
MATCH (tp:TPA_SP_Result {name:$tp_name})-[:MATCHED_PATTERN]->(p:DesignPattern {category:'Distributed'})
WITH count(p) AS dp_count
OPTIONAL MATCH (exec:TPA_Execution)-[:HAS_VALIDATION]->(vr:ValidationResult {phase:'SP-MetaVerify', verdict:'APPROVED'})
  WHERE (exec)-[:PHASE_OUTPUT]->(tp)
RETURN dp_count, count(vr) AS mv_count,
  CASE WHEN dp_count=0 OR mv_count>0 THEN 'PASS' ELSE 'FAIL — MetaVerifier required' END AS gate
```

**`FAIL — MetaVerifier required`** → SP phase 전체 verdict=REJECTED. 
`tpa-ta` Hook Gate에서 차단됨.

### 왜 필요한가

`lesson-tpa-gap-88taliban-scope-2026-04-14` 해결:
- GoF 구조/행위 패턴: AST 매칭 충분 (Structural/Behavioral lens)
- 분산 패턴: 수학 속성(commute/idempotent/safety) 미검증 시 "이름만 CRDT" false positive
- 88-Naesengmoon의 수학 렌즈가 유일한 gate

---

## 결과 기록

```cypher
MERGE (tp:TPA_SP_Result {name:'SP_<target>_<date>'})
SET tp.sourcePath=$TARGET,
    tp.sourceId='tpa-sp-'+$target_id,
    tp.totalPatterns=$pattern_count,
    tp.instanceOf_count=$io_count,
    tp.resembles_count=$res_count,
    tp.novelPatterns=$novel_count,
    tp.distributed_metaverified=$mv_count
MERGE (exec)-[:PHASE_OUTPUT {order:3}]->(tp)
```

---

## Novel Pattern 처리

라이브러리에 없는 신규 패턴 발견 시:

```cypher
MERGE (np:NovelPattern:KG_PROJECTS {name:'NP_<domain>_<PatternName>'})
SET np.description=$desc,
    np.evidence=$ev,
    np.category=$cat,  // 'architectural_novel' | 'language_novel' | 'domain_novel'
    np.first_observed_in=$target,
    np.discovered_at=datetime()
MERGE (tp:TPA_SP_Result)-[:IDENTIFIES_NOVEL]->(np)
```

---

## 모르는 패턴 만나면 → ResearchProvider

```cypher
MATCH (s:MethodologySlot {name:'ResearchProvider'})
RETURN s.invocation AS auto_call
-- {auto_call} <unknown_pattern_name>
```

결과는 KnowledgeNode + tp Result에 INFORMED_BY.

---

## FulfillmentGate SP (7 checks)

1. [ ] Pattern Library ≥ 38 노드 존재 (pre-check 통과)
2. [ ] MECE check: leaf span 중복/누락 없음
3. [ ] 모든 INSTANCE_OF 엣지에 **confidence + evidence + strategy** 3필드
4. [ ] Distributed 카테고리는 MetaVerifier 수학 검증 완료
5. [ ] Novel Pattern은 `:NovelPattern` 라벨 + category 지정
6. [ ] orphan span 없음
7. [ ] TPA_SP_Result + PHASE_OUTPUT order=3 엣지 + sourcePath+sourceId SET 확인

---

## 종료 의식 — Naesengmoon 9-lens

```cypher
MATCH (s:MethodologySlot {name:'AdversarialValidator'})
RETURN s.invocation AS gate
-- {gate} TPA_SP_<target>
```

ValidationResult 기록:
```cypher
MERGE (vr:ValidationResult {name:'VR_TPA_SP_<target>_<date>', phase:'SP'})
SET vr.verdict=$verdict, vr.evidence=[...], vr.validated_at=datetime(),
    vr.validator='Naesengmoon-9lens+MetaVerifier(distributed)'
MATCH (exec:TPA_Execution)
MERGE (exec)-[:HAS_VALIDATION]->(vr)
```

**APPROVED 아니면 `/tpa-ta` Gate Check에서 차단됨.**

**⚠️ 부모 인라인 APPROVED 금지 — Naesengmoon subagent 최소 1개 독립 출격 강제.**
**⚠️ VR.provenance='subagent-taliban-tp' 필수. 'inline' 이면 향후 Hook에서 차단.**
**⚠️ 사용자가 "확인해봐"라고 안 해도 자동으로 실행해야 한다.**
<!-- KG: lesson-taliban-not-auto-triggered-2026-04-16 -->

---

## What NOT to Do

| 금지 | 이유 |
|---|---|
| Pattern library 없이 SP 진입 | 중복 노드 생성 |
| confidence 없이 INSTANCE_OF | HR11 rubber-stamp 위반 |
| Distributed 패턴 MetaVerifier skip | 수학 속성 미검증 |
| AST 없이 regex만 | 주석/문자열 오인식 |
| RESEMBLES를 APPROVED로 승격 | 0.7 threshold 위반 |
| Novel Pattern 그대로 방치 (KG 기록 X) | 지식 손실 |

---

## Post-Gate Reflection (TR9 — 필수)

매 gate 통과 후 아래 형식으로 reflection 작성. 미작성 = INCOMPLETE_GATE.

```
REFLECTION:
  DISCOVERED: <이번 phase에서 발견한 핵심>
  LESSON: <lesson-name 또는 "신규 없음">
  QUALITY_ACTION: <333에 적용할 구체적 개선안>
  NEXT_GATE_CHECKS: <다음 gate에서 추가로 확인할 것>
```

---

## Lesson 자동 생성 (TR10)

QualityGap 또는 AntiPattern 발견 시 즉시:
```cypher
MERGE (l:AbstractNode:Lesson {name:'lesson-tpa-sp-<finding>-<date>'})
SET l.category='tpa-sp', l.problem=$problem,
    l.severity=$severity, l.resolved=false, l.createdAt=datetime()
```

---

## References

- `../tpa/references/shared_subskill_template.md`
- Pattern Library: 51 `DesignPattern` nodes (GoF+분산+PL)
- Mirror: `apt-sp` (2/4, 생성)
- Prior: `TPA_exec_puter_2026-04-15` Novel Patterns 4개 (Microkernel/Trait/Extension/BrowserOS)

---

## 🌱 재배맨 바인딩 (KG-first Subagent 재배)

> 원칙: SKILL.md 얇은 엔트리, KG `SubagentTaskSpec` 씨앗이 본체.

### 세션 진입 시
```cypher
MATCH (wb:WorkBuffer {status:'CURRENT'}) RETURN wb
MATCH (e:TPA_Execution) WHERE e.phase_current='SP' RETURN e.name, e.target LIMIT 3
MATCH (ts:SubagentTaskSpec {skill:'tpa', phase:'SP'}) RETURN ts.checkItems, ts.required_validator_conditions, ts.fulfillment_gate_cypher_meta
// Pattern Library pre-check (필수)
MATCH (p:DesignPattern) RETURN count(p) AS lib_size
```

### Subagent 출격 (3줄, 카테고리별 병렬)
```
역할: TPA SP pattern matcher — category={Structural|Behavioral|Creational|Distributed|PL} (agentId=D<idx>)
TaskSpec: MATCH (ts:SubagentTaskSpec {name:'taskspec-tpa-SP'}) RETURN ts.*
Target: $CONTRACT_SUBSET + Pattern Library. 출력: {INSTANCE_OF[{p,conf,ev,strategy}], RESEMBLES[...], NovelPattern[...]} JSON (provenance='재배맨-tpa-sp').
```

> ⚠️ **카테고리별 5 Agent() 호출은 반드시 jaebaeman Phase 2 (single-message multi-call) 규약을 따른다** — 5 category 모두 하나의 assistant message 안에 tool_use block 5개 emit. for-loop = sequential drift (GH#29181), '카테고리별 병렬' 측 실효 N=1. 정전: `SKILLS/jaebaeman/references/phases.md §Phase 2 L36-65`.
>
> # KG: finding-prom16-parallelism-bhgman-dep-D4 (GAP-3 patch, 2026-05-19)

### 자동 88-Naesengmoon 트리거 (Distributed 매칭 시, 위 섹션 참조)
```
역할: 88-Naesengmoon MetaVerifier (agentId=M<idx>)
TaskSpec: MATCH (ts:SubagentTaskSpec {name STARTS WITH 'taskspec-88taliban-'}) RETURN ts.*
Target: Distributed DesignPattern. 출력: VR{phase:'SP-MetaVerify', math_properties:[...]}.
```

### 새 씨앗 심기
```cypher
MERGE (ts:SubagentTaskSpec {name:$name})
SET ts.skill='tpa', ts.phase='SP', ts.pattern_category=$cat,
    ts.checkItems=$checks, ts.status='READY', ts.createdAt=datetime()
```

### 세션 종료 시
```cypher
MATCH (w:WorkBuffer {status:'CURRENT'}) SET w.status='ARCHIVED', w.archived_at=datetime()
MERGE (wb:WorkBuffer {name:$next}) SET wb.status='CURRENT', wb.phase='TPA SP in progress', wb.updated_at=datetime()
```

---

## MIC Binding Disclaimer

> 이 SKILL.md에서 "Prometheus", "Naesengmoon", "88-Naesengmoon", "Longinus", "재배맨" 등의
> concrete 이름은 MIC_v1 MethodologySlot의 **현재 바인딩(currentConcrete)**이다.
> Slot이 다른 concrete로 교체되면 이 파일의 이름도 drift한다.
> 정본 해석: `MATCH (mic:MethodologyIntegrationContract {name:'MIC_v1'})-[:HAS_SLOT]->(s) RETURN s.name, s.currentConcrete`
> 유틸리티: `03_SCRIPTS/db/resolve_mic_slot.cypher`
> # KG: lesson-skill-mic-slot-ref-weak-2026-04-15

# KG: ATOM_재배맨_autoboot_tpa-sp
