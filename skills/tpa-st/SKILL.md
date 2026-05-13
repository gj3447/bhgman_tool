---
name: tpa-st
kg_ref: ATOM_Skill_tpa_st
version: "1.2.0"
channel: stable
description: >
  TPA TargetTwin (ST) — Phase 2/4. APT ST 거울 (역순).
  각 pub 심볼의 암묵적/명시적 Contract 추출. AptContract(명시 interface/trait)
  vs ConventionalContract(암묵 시그니처) 분리 라벨. LOC>100 giant method는 SP로 위임.
  pre/postcondition 주석 파싱. Gate Check Hook 강제: TCW Gate 통과 없이 진입 불가.
  # KG: ATOM_Skill_tpa_st, CONTRACT_AS_TPA_st_SKILL, TPA_methodology_v10
---

<!-- KG: TASK_AS_TPA_st_SKILL -->
<!-- KG: CONTRACT_AS_TPA_st_SKILL -->
<!-- KG: IMPLEMENTS_SHARED CONTRACT_SHARED_TPA_SubSkillTemplate -->

## 🔗 MIC Binding (SOLID-DIP)

**IS slot**: TPA_Phase (ST, 2/4)
**USES slots**: SubagentSeeder, ResearchProvider (giant method 시), KgCodeBinder, AdversarialValidator

```cypher
MATCH (mic:MethodologyIntegrationContract {name:'MIC_v1'})-[:HAS_SLOT]->(s:MethodologySlot)
WHERE s.name IN ['SubagentSeeder','KgCodeBinder','AdversarialValidator']
RETURN s.name, s.currentConcrete, s.invocation
```

> ⚠️ **본문의 concrete 이름(재배맨/Prometheus/Taliban/Longinus/88-Taliban)은 MIC slot 현재 스냅샷.**
> 진짜 호출은 `s.invocation` 경유. MIC_v1 교체 시 본문 무변경.

# KG: MIC_v1, lesson-tpa-gap-03-convention-label, lesson-tpa-gap-04-giant-method, lesson-skill-mic-slot-ref-weak-2026-04-15

---

# /tpa-st — TargetTwin: 암묵적 계약 발굴

> **질문**: "각 심볼이 지키고 있는 암묵적 계약은 무엇인가?"
> 공유 시그니처 = 계약. 명시 interface = 계약. 둘을 섞지 말 것.

## ⛔ GATE CHECK (Hook 강제)

> `apt-gate-check.sh`가 자동 실행.
> **TCW Gate 미통과 시 `permissionDecision: deny`.**
> BLOCKED 시: `/tpa-tcw` → `/taliban` → TCW Gate 통과 → `/tpa-st` 재호출.

필수 조건:
```cypher
MATCH (exec:TPA_Execution {status:'IN_PROGRESS_TCW'})
      -[:HAS_VALIDATION]->(vr:ValidationResult {phase:'TCW', verdict:'APPROVED'})
RETURN exec LIMIT 1
```

---

## 진입 의식

```cypher
MATCH (ts:SubagentTaskSpec {name:'taskspec-tpa-ST', skill:'tpa'})
RETURN ts.checkItems, ts.cypherQueries, ts.expectedOutcome, ts.treasure_coverage_min
```

---

## Contract 분류 (gap03 — 라벨 분리 강제)

### 명시 interface / trait → `:AptContract`

```cypher
MERGE (c:AptContract:AbstractNode {name:'AC_<target>_<SymbolName>'})
SET c.type='explicit',
    c.declared_in=$file, c.line=$line,
    c.sourcePath=$file+':'+toString($line),
    c.extends=$parent_class,
    c.protocol=$method_signatures_formal,
    c.preconditions=$pre_from_docstring,
    c.postconditions=$post_from_docstring
```

**조건**: interface / abstract class / trait / protocol / 명시 annotation 존재.

### 암묵 convention → `:ConventionalContract` (독립 라벨)

```cypher
MERGE (cv:ConventionalContract:AbstractNode {name:'CC_<target>_<Shape>'})
SET cv.type='implicit',
    cv.inferred_from=$n_implementors+' 심볼 공유 시그니처',
    cv.protocol=$shared_signature_pattern,
    cv.implementors=[$sym1, $sym2, ...],
    cv.evidence=$concrete_snippets,
    cv.confidence=$overlap_ratio  // ≥ 0.8 권장
```

**조건**: N ≥ 3 심볼이 같은 메서드/필드/생성자 시그니처 공유. 명시 interface **없음**.

### 섞지 말 것 (ontology 오염 금지)

| 실수 | 결과 |
|---|---|
| AptContract에 convention 넣음 | 명시/암묵 구분 소실 |
| ConventionalContract에 trait 넣음 | 컴파일러 강제 사실 누락 |
| 동일 노드 name으로 둘 다 label | Neo4j 유니크 제약 충돌 |

---

## 결과 기록

```cypher
MERGE (tt:TPA_ST_Result {name:'ST_<target>_<date>'})
SET tt.sourcePath=$TARGET,
    tt.sourceId='tpa-st-'+$target_id,
    tt.totalContracts=$contract_count,
    tt.aptContracts=$apt_count,
    tt.conventionalContracts=$conv_count,
    tt.giantMethodsDeferred=$gm_count,
    tt.prePostParsed=$pp_count
MERGE (exec)-[:PHASE_OUTPUT {order:2}]->(tt)
```

---

## Giant Method 처리 (gap04)

**LOC > 100 메서드는 AtomicSpan 아님** → SP phase로 deferred.

```cypher
MERGE (gm:GiantMethodDeferred {name:'GM_'+$sym})
SET gm.loc=$loc, gm.file=$file+':'+toString($line),
    gm.reason='LOC>100 — SP 패턴 분석 후 재평가',
    gm.deferred_to='SP'
MERGE (tt:TPA_ST_Result {name:$tt_name})-[:DEFERS_TO_SP]->(gm)
```

---

## pre/postcondition 파싱

docstring/JSDoc/Rust-doc에서:
- `@precondition`, `@param requires`, `Requires:`, `전제:`
- `@postcondition`, `@return`, `Ensures:`, `보장:`
- 없으면 `inferred='NONE — code contract only'`

---

## FulfillmentGate ST (7 checks)

1. [ ] 각 Contract 노드 `sourcePath=file:line` 포함
2. [ ] `:AptContract` vs `:ConventionalContract` 라벨 **명확 분리**
3. [ ] pre/postcondition 필드 존재 (없으면 explicit NONE)
4. [ ] giant_methods_deferred 목록 SP로 전달 (0 이상)
5. [ ] Longinus SourceBinding 생성 (Contract마다 1개 이상)
6. [ ] taskspec.checkItems 전부 pass
7. [ ] TPA_ST_Result + PHASE_OUTPUT order=2 엣지 + sourcePath+sourceId SET 확인

---

## 종료 의식 — Taliban 9-lens

```cypher
MATCH (s:MethodologySlot {name:'AdversarialValidator'})
RETURN s.invocation AS gate
-- {gate} TPA_ST_<target>
```

ValidationResult 기록:
```cypher
MERGE (vr:ValidationResult {name:'VR_TPA_ST_<target>_<date>', phase:'ST'})
SET vr.verdict=$verdict, vr.evidence=[...], vr.validated_at=datetime(),
    vr.validator='Taliban-9lens'
MATCH (exec:TPA_Execution)
MERGE (exec)-[:HAS_VALIDATION]->(vr)
SET exec.status = CASE $verdict WHEN 'APPROVED' THEN 'IN_PROGRESS_ST' ELSE 'BLOCKED_AT_ST' END
```

**APPROVED 아니면 `/tpa-sp` Gate Check에서 차단됨.**

**⚠️ 부모 인라인 APPROVED 금지 — Taliban subagent 최소 1개 독립 출격 강제.**
**⚠️ VR.provenance='subagent-taliban-st' 필수. 'inline' 이면 향후 Hook에서 차단.**
**⚠️ 사용자가 "확인해봐"라고 안 해도 자동으로 실행해야 한다.**
<!-- KG: lesson-taliban-not-auto-triggered-2026-04-16 -->

---

## What NOT to Do

| 금지 | 이유 |
|---|---|
| AptContract + Convention 라벨 섞기 | ontology 오염, 쿼리 불가능 |
| giant method를 ST에서 억지로 contract화 | atomic 아님 |
| implementors < 3인데 ConventionalContract | 우연 일치 |
| sourcePath 생략 | Longinus 깨짐 |
| TCW Gate 없이 진입 | hook이 차단함 (설계) |

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
MERGE (l:AbstractNode:Lesson {name:'lesson-tpa-st-<finding>-<date>'})
SET l.category='tpa-st', l.problem=$problem,
    l.severity=$severity, l.resolved=false, l.createdAt=datetime()
```

---

## References

- `../tpa/references/shared_subskill_template.md`
- Mirror: `apt-st` (3/4, 생성)
- Gap: `lesson-tpa-gap-03-convention-label`, `lesson-tpa-gap-04-giant-method`

---

## 🌱 재배맨 바인딩 (KG-first Subagent 재배)

> 원칙: SKILL.md 얇은 엔트리, KG `SubagentTaskSpec` 씨앗이 본체.

### 세션 진입 시
```cypher
MATCH (wb:WorkBuffer {status:'CURRENT'}) RETURN wb
MATCH (e:TPA_Execution) WHERE e.phase_current='ST' RETURN e.name, e.target LIMIT 3
MATCH (ts:SubagentTaskSpec {skill:'tpa', phase:'ST'}) RETURN ts.checkItems, ts.parallelism_min, ts.treasure_coverage_min
```

### Subagent 출격 (3줄)
```
역할: TPA ST Contract extractor (agentId=D<idx>)
TaskSpec: MATCH (ts:SubagentTaskSpec {name:'taskspec-tpa-ST'}) RETURN ts.*
Target: $SYMBOL_SUBSET. 출력: {AptContract[], ConventionalContract[], GiantMethodDeferred[]} JSON (provenance='재배맨-tpa-st').
```

### 새 씨앗 심기
```cypher
MERGE (ts:SubagentTaskSpec {name:$name})
SET ts.skill='tpa', ts.phase='ST', ts.displayName=$display, ts.checkItems=$checks,
    ts.status='READY', ts.createdAt=datetime()
```

### 세션 종료 시
```cypher
MATCH (w:WorkBuffer {status:'CURRENT'}) SET w.status='ARCHIVED', w.archived_at=datetime()
MERGE (wb:WorkBuffer {name:$next}) SET wb.status='CURRENT', wb.phase='TPA ST in progress', wb.updated_at=datetime()
```

---

## MIC Binding Disclaimer

> 이 SKILL.md에서 "Prometheus", "Taliban", "88-Taliban", "Longinus", "재배맨" 등의
> concrete 이름은 MIC_v1 MethodologySlot의 **현재 바인딩(currentConcrete)**이다.
> Slot이 다른 concrete로 교체되면 이 파일의 이름도 drift한다.
> 정본 해석: `MATCH (mic:MethodologyIntegrationContract {name:'MIC_v1'})-[:HAS_SLOT]->(s) RETURN s.name, s.currentConcrete`
> 유틸리티: `03_SCRIPTS/db/resolve_mic_slot.cypher`
> # KG: lesson-skill-mic-slot-ref-weak-2026-04-15

# KG: ATOM_재배맨_autoboot_tpa-st
