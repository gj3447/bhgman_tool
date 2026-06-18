---
name: tpa-ta
kg_ref: ATOM_Skill_tpa_ta
version: "1.2.0"
channel: stable
provenance: AI_DERIVED_FROM_USER_PRIMARY  # SKILL.md = AI engineering; underlying methodology = user-primary mythology (12 apostles + 5 weapons). Per PseudepigraphaValidationGate-v1-2026-04-30.
description: >
  TPA TargetAnchor (TA) — Phase 4/4. APT SA 거울 (최종 앵커링).
  SemanticAnchor 라우팅 (2-A 신규/2-B 재사용/2-C 브랜치).
  5종 Drift 측정 (Missing/Orphan/SigMismatch/PatternDiv/LabelRot).
  coverage_ratio < 0.8 → status='SUSPENDED' 강제.
  Longinus 전수 바인딩 + 최종 Naesengmoon gate.
  Gate Check Hook 강제: SP Gate 통과 없이 진입 불가.
  # KG: ATOM_Skill_tpa_ta, CONTRACT_AS_TPA_ta_SKILL, TPA_methodology_v10
---

<!-- KG: TASK_AS_TPA_ta_SKILL -->
<!-- KG: CONTRACT_AS_TPA_ta_SKILL -->
<!-- KG: IMPLEMENTS_SHARED CONTRACT_SHARED_TPA_SubSkillTemplate -->

## 🔗 MIC Binding (SOLID-DIP)

**IS slot**: TPA_Phase (TA, 4/4)
**USES slots**: SubagentSeeder, KgCodeBinder (전수 바인딩), MetaVerifier (drift 검증), AdversarialValidator (최종 gate), **RoundTripRealizer(하데스), StaleArchiver(오캄)** (7-stage 2026-05-30)

> **하데스 (RoundTripRealizer) — TA round-trip (2026-05-30):** 복원한 추상(유레카 산출)을 하데스로
> *재실현*(추상→구체) → 원본 코드와 대조 = recovery fidelity 검증. 불일치 = drift 신호 (기존 5종
> drift와 직결). `/hades`. 복원-재실현 dual 루프 닫힘 (유레카↑·하데스↓).
> **오캄 (StaleArchiver) — TA 보조:** 최종 앵커링 시 stale 노드 격리 (archive-only). `/occam`.
> KG: `tpa-7stage-eureka-core-2026-05-30`, `hades-canonical-2026-05-27`.

```cypher
MATCH (mic:MethodologyIntegrationContract {name:'MIC_v1'})-[:HAS_SLOT]->(s:MethodologySlot)
WHERE s.name IN ['SubagentSeeder','KgCodeBinder','MetaVerifier','AdversarialValidator']
RETURN s.name, s.currentConcrete, s.invocation
```

> ⚠️ **본문의 concrete 이름(재배맨/Prometheus/Naesengmoon/Longinus/88-Naesengmoon)은 MIC slot 현재 스냅샷.**
> 진짜 호출은 `s.invocation` 경유. MIC_v1 교체 시 본문 무변경.

# KG: MIC_v1, lesson-tpa-gap-drift-validity-threshold-2026-04-14, lesson-tpa-surface-scan-shortcut-2026-04-15, lesson-skill-mic-slot-ref-weak-2026-04-15

---

# /tpa-ta — TargetAnchor: 최종 앵커링 + Drift 감사

> **질문**: "이 구조는 어디에 속하는가? 어디가 drift되었나?"
> coverage ≥ 0.8 아니면 SUSPENDED 명시. false baseline 금지.

## ⛔ GATE CHECK (Hook 강제)

> `apt-gate-check.sh`가 자동 실행.
> **SP Gate 미통과 시 `permissionDecision: deny`.**
> BLOCKED 시: `/tpa-sp` → `/taliban` → SP Gate 통과 → `/tpa-ta` 재호출.

필수 조건:
```cypher
MATCH (exec:TPA_Execution {status:'IN_PROGRESS_SP'})
      -[:HAS_VALIDATION]->(vr:ValidationResult {phase:'SP', verdict:'APPROVED'})
RETURN exec LIMIT 1
```

---

## 진입 의식

```cypher
MATCH (ts:SubagentTaskSpec {name:'taskspec-tpa-TA', skill:'tpa'})
RETURN ts.checkItems, ts.cypherQueries, ts.expectedOutcome, ts.treasure_coverage_min
```

---

## 라우팅 매트릭스 (apt-sa 2-A/B/C 재사용)

| 상황 | 결정 | 액션 |
|---|---|---|
| 동일 앵커 존재 + active | 기존 재사용 | 2-B |
| 유사 앵커 존재 + 다른 scope | 브랜치 추가 | 2-C |
| 관련 앵커 없음 | 신규 생성 | 2-A |

```cypher
// 2-A 신규
MERGE (sa:SemanticAnchor {name:'SA_<target>_<date>'})
SET sa.domain=$d, sa.routing='2-A_new_anchor', sa.rootSpan=$rs, sa.createdAt=datetime()
```

---

## Longinus 전수 바인딩

TCW 파일 목록의 **모든** pub 심볼에 SourceBinding:

```cypher
UNWIND $symbols AS sym
MERGE (b:SourceBinding:Longinus {name:'SB_<target>_'+sym.name})
SET b.sourceId='SB_<target>_'+sym.name,
    b.sourcePath=sym.file+':'+toString(sym.line),
    b.symbol=sym.name, b.kind=sym.kind, b.kg_ref=sym.kg_node
MATCH (tp:TPA_SP_Result {name:'TP_<target>_<date>'})
MERGE (tp)-[:LONGINUS_BINDS]->(b)
```

**coverage = bound / total**. 임계 0.8 미달 시 SUSPENDED.

### coverage 분모 고정 (TPA-D4 fix, 2026-06-01)

<!-- KG: TPA-D4-2026-06-01 (:MethodologyDefect), lesson-tpa-dogfood-spacegirl-defects-2026-06-01 -->

> **결함 출처**: spacegirl_tool 도그푸드 — `total` 의 단위(파일/퍼블릭심볼/Contract)가 미정의라 같은 repo가 0.89(파일 기준) vs 0.96(심볼 기준)으로 흔들렸다. 분모가 흔들리면 0.8 임계가 무의미.

**`total` = 퍼블릭 심볼 수로 고정** (단일 레벨). 파일/Contract 기준 금지.

- 분모 = `totalPubSymbols` (TCW manifest Step 3.0-A에서 실측된 pub 심볼 카운트). `bound` 도 동일 단위(바인딩된 pub 심볼 수).
- 측정 대상은 **TCW manifest에서 선언된 집합**과 1:1 — TA에서 즉석 재정의 금지 (drift 자초).
- `coverage_ratio = boundSymbols / totalPubSymbols` (둘 다 결과 기록 노드에 명시 — 분자·분모 동시 기록 의무).

```cypher
// 분모 단위 일관성 검증 — totalPubSymbols 가 TCW manifest 의 pub 심볼 카운트와 일치해야
MATCH (tcw:TPA_TCW_Result {name:$tcw_name})
MATCH (ta:TPA_TA_Result {name:$ta_name})
WHERE ta.totalPubSymbols <> tcw.pubSymbolCount
RETURN 'TR_CoverageDenominatorMismatch' AS violation   // 불일치 = 분모 drift
```

---

## 결과 기록

```cypher
MERGE (ta:TPA_TA_Result {name:'TA_<target>_<date>'})
SET ta.sourcePath=$TARGET,
    ta.sourceId='tpa-ta-'+$target_id,
    ta.coverage_ratio=$coverage,
    ta.totalPubSymbols=$total,
    ta.boundSymbols=$bound,
    ta.driftTotal=$drift_total,
    ta.anchorName=$anchor_name,
    ta.routing=$routing_decision
MERGE (exec)-[:PHASE_OUTPUT {order:4}]->(ta)
```

---

## DriftReport — 5종 강제 측정 (gap06)

```cypher
MERGE (dr:DriftReport {name:'DRIFT_<target>_<date>'})
SET dr.coverage_ratio = $bound / toFloat($total),
    dr.status = CASE
      WHEN ($bound / toFloat($total)) < 0.8 THEN 'SUSPENDED'
      ELSE 'VALID'
    END,
    dr.drift_missing_count = $m,              // KG에 없는 pub symbol
    dr.drift_orphan_count = $o,               // KG엔 있는데 코드 없음
    dr.drift_signature_mismatch_count = $s,   // Contract vs 실제 시그니처
    dr.drift_pattern_divergence_count = $p,   // 주장 속성과 실제 코드 불일치
    dr.drift_label_rot_count = $l,            // 주석 KG ref의 대상 노드 삭제됨
    dr.total_pub_symbols = $total,
    dr.bound_symbols = $bound
```

### Drift 심각도

| 종류 | 의미 | 심각도 |
|---|---|---|
| Missing | KG에 없는 pub symbol | MEDIUM |
| Orphan | KG엔 있는데 코드 없음 | HIGH |
| SignatureMismatch | Contract vs 실제 시그니처 | CRITICAL |
| PatternDivergence | 주장 속성과 실제 코드 불일치 | CRITICAL |
| LabelRot | 주석 KG ref의 대상 노드 삭제됨 | LOW |

---

## FulfillmentGate TA (최종, 7 checks)

1. [ ] coverage_ratio ≥ 0.8 (아니면 `status='SUSPENDED'` 명시)
2. [ ] 모든 drift 5종 측정됨 (skipped=0)
3. [ ] SemanticAnchor + Root Span + SourceBinding 체인 완성
4. [ ] 라우팅 결정(2-A/B/C) 문서화
5. [ ] `AdversarialValidator.invocation` **전체 결과** gate 통과
6. [ ] DriftReport KG 기록 완료
7. [ ] TPA_Execution.status='COMPLETE' 또는 'SUSPENDED' 명시 + sourcePath+sourceId SET 확인

---

## 종료 의식 — Naesengmoon 9-lens 최종 Gate

```cypher
MATCH (s:MethodologySlot {name:'AdversarialValidator'})
RETURN s.invocation AS gate
-- {gate} TPA_TA_<target>
```

전체 TPA 실행 결과에 대한 최종 검증.

**⚠️ 부모 인라인 APPROVED 금지 — Naesengmoon subagent 최소 1개 독립 출격 강제.**
**⚠️ VR.provenance='subagent-taliban-ta' 필수. 'inline' 이면 향후 Hook에서 차단.**
**⚠️ 사용자가 "확인해봐"라고 안 해도 자동으로 실행해야 한다.**
<!-- KG: lesson-taliban-not-auto-triggered-2026-04-16 -->

ValidationResult 기록:

```cypher
MERGE (vr:ValidationResult {name:'VR_TPA_TA_<target>_<date>', phase:'TA'})
SET vr.verdict=$verdict, vr.evidence=[...], vr.validated_at=datetime(),
    vr.validator='Naesengmoon-9lens',
    vr.full_tpa_cycle_approved=CASE $verdict WHEN 'APPROVED' THEN true ELSE false END
MATCH (exec:TPA_Execution)
MERGE (exec)-[:HAS_VALIDATION]->(vr)
SET exec.phase_current='COMPLETE',
    exec.completed_at=datetime(),
    exec.status=CASE $verdict
      WHEN 'APPROVED' THEN 'COMPLETE'
      WHEN 'CONDITIONAL_PASS' THEN 'COMPLETE_WITH_CONDITIONS'
      ELSE 'SUSPENDED'
    END
```

---

## What NOT to Do

| 금지 | 이유 |
|---|---|
| coverage < 0.8에 drift=0 claim | false baseline (gap06) |
| drift 5종 중 skip | 사각지대 |
| 라우팅 결정 암묵 | 이력 추적 불가 |
| executor가 Naesengmoon 셀프 APPROVED | D20 rubber-stamp |
| SemanticAnchor 중복 생성 (2-B/2-C 고려 없이 2-A) | 앵커 난립 |

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
MERGE (l:AbstractNode:Lesson {name:'lesson-tpa-ta-<finding>-<date>'})
SET l.category='tpa-ta', l.problem=$problem,
    l.severity=$severity, l.resolved=false, l.createdAt=datetime()
```

---

## References

- `../tpa/references/shared_subskill_template.md`
- Mirror: `apt-sa` (1/4, 생성)
- Prior: `TPA_exec_puter_2026-04-15` (SURFACE_SCAN, coverage 0.006 → SUSPENDED)
- Drift threshold: `lesson-tpa-gap-drift-validity-threshold-2026-04-14`

---

## 🌱 재배맨 바인딩 (KG-first Subagent 재배)

> 원칙: SKILL.md 얇은 엔트리, KG `SubagentTaskSpec` 씨앗이 본체.

### 세션 진입 시
```cypher
MATCH (wb:WorkBuffer {status:'CURRENT'}) RETURN wb
MATCH (e:TPA_Execution) WHERE e.phase_current='TA' RETURN e.name, e.target LIMIT 3
MATCH (ts:SubagentTaskSpec {skill:'tpa', phase:'TA'}) RETURN ts.checkItems, ts.treasure_coverage_min
```

### Subagent 출격 (3줄 — Longinus + Drift 분산)
```
역할: TPA TA Longinus binder (agentId=L<idx>) | Drift detector (agentId=D<idx>)
TaskSpec: MATCH (ts:SubagentTaskSpec {name:'taskspec-tpa-TA'}) RETURN ts.*
Target: $PUB_SYMBOL_SUBSET. 출력: {SourceBinding[], DriftCandidate[{type:Missing|Orphan|SigMismatch|PatternDiv|LabelRot}]} JSON (provenance='재배맨-tpa-ta').
```

### 새 씨앗 심기
```cypher
MERGE (ts:SubagentTaskSpec {name:$name})
SET ts.skill='tpa', ts.phase='TA', ts.coverage_target=$cov,
    ts.checkItems=$checks, ts.status='READY', ts.createdAt=datetime()
```

### 세션 종료 시 (TPA 전체 완료 또는 SUSPENDED 기록)
```cypher
MATCH (w:WorkBuffer {status:'CURRENT'}) SET w.status='ARCHIVED', w.archived_at=datetime()
MERGE (wb:WorkBuffer {name:$next})
SET wb.status='CURRENT',
    wb.phase=CASE WHEN $coverage >= 0.8 THEN 'TPA TA COMPLETE' ELSE 'TPA TA SUSPENDED' END,
    wb.anchor=$anchor_name, wb.drift_report=$dr_name,
    wb.updated_at=datetime()
```

---

## MIC Binding Disclaimer

> 이 SKILL.md에서 "Prometheus", "Naesengmoon", "88-Naesengmoon", "Longinus", "재배맨" 등의
> concrete 이름은 MIC_v1 MethodologySlot의 **현재 바인딩(currentConcrete)**이다.
> Slot이 다른 concrete로 교체되면 이 파일의 이름도 drift한다.
> 정본 해석: `MATCH (mic:MethodologyIntegrationContract {name:'MIC_v1'})-[:HAS_SLOT]->(s) RETURN s.name, s.currentConcrete`
> 유틸리티: `03_SCRIPTS/db/resolve_mic_slot.cypher`
> # KG: lesson-skill-mic-slot-ref-weak-2026-04-15

# KG: ATOM_재배맨_autoboot_tpa-ta
