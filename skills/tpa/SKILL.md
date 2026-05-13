---
name: tpa
kg_ref: ATOM_Skill_tpa_orchestrator_v10
version: "1.2.0"
channel: stable
description: >
  TPA v1.0 orchestrator — APT v24 역분석 기반 역순 사이클.
  코드→설계 복원 (TCW→ST→SP→TA). 5대 본질 MIC 참조.
  오답노트 피드백 루프 내장. Gate Check Hook 강제.
  # KG: ATOM_Skill_tpa_orchestrator_v10, TPA_methodology_v10, MIC_v1.ReasoningProtocol→KGFirstCheck_v1 (R1-R5 mandatory before any framing/diagnostic, lesson-ai-skipped-kg-check-before-framing-2026-04-29)
  Invoke when: "/tpa <path>", "/tpa --audit <anchor>", "/tpa --status",
  "reverse engineer", "analyze codebase", "코드 분석", "리버스 엔지니어링".
  Enforces: phase detection, flow control, adversarial gates, feedback loop, mandatory reflection.
---

<!-- KG: TASK_AS_TPA_orchestrator_v10, CONTRACT_AS_TPA_orchestrator_v10 -->

## 🎛 v26 A6 Resolve-Only

> TPA 4 phase 본문에 박힌 magic number(51 pattern, 0.7 confidence, LOC 100, coverage 0.8)는 모두 `MethodologyConfig_default_v26` slot에서 resolve. prose 직접 편집 금지.

```cypher
MATCH (cfg:MethodologyConfig {name:'MethodologyConfig_default_v26'})
RETURN cfg.tpa_pattern_library_size,            // 51
       cfg.tpa_pattern_confidence_instance_of,  // 0.7
       cfg.tpa_giant_method_loc_threshold,      // 100
       cfg.tpa_drift_coverage_ratio_min,        // 0.8
       cfg.tpa_drift_suspend_label,             // 'SUSPENDED'
       cfg.tpa_drift_kinds                      // ['Missing','Orphan','SigMismatch','PatternDiv','LabelRot']
```

# KG: APT_v26_A6_2026-04-21, MethodologyConfig_default_v26 (tpa_* 7 필드, 2026-04-26)

---

## 5대 본질 참조 (MIC Binding — SOLID-DIP)

> **본질이 업데이트되면 TPA도 자동 진화한다.**
> 아래 slot의 `currentConcrete`가 바뀌면 TPA 전체가 새 구현체를 사용.
> SKILL.md 본문 수정 불필요 (DIP 원칙).

**IS slot**: Orchestrator (역순 5 slots 조율)
**USES slots**: ResearchProvider, AdversarialValidator, MetaVerifier, KgCodeBinder, SubagentSeeder

**동적 resolution**:
```cypher
MATCH (mic:MethodologyIntegrationContract {name:'MIC_v1'})-[:HAS_SLOT]->(s:MethodologySlot)
RETURN s.name, s.currentConcrete, s.invocation
```

**6대 무기 ↔ MIC Slot 매핑 (참조 — 정본은 KG)**:

| 무기 | MIC Slot | 현재 Concrete | TPA 역할 |
|---|---|---|---|
| Prometheus | ResearchProvider | `/prom` | unknown 리서치, 패턴 탐색 |
| Taliban | AdversarialValidator | `/tlb` | 각 phase gate 검증 |
| 88-Taliban | MetaVerifier | `/88-taliban` | TPA 방법론 자체 메타검증 |
| Longinus | KgCodeBinder | `/longinus` | 코드↔KG 양방향 바인딩 |
| 재배맨 | SubagentSeeder | taskspec 조회 | 병렬 subagent 분산 |
| Harness | Harness | (구조적 제약) | 4축 제약 모델 |

> ⚠️ 본문의 구체 이름은 **현재 스냅샷**. 진짜 호출은 MIC `s.invocation` 경유.
> 본질 교체(예: Taliban→FutureValidator) 시 MIC 노드만 수정 → TPA 전체 자동 반영.

# KG: MIC_v1, APTWeapon, lesson-skill-mic-slot-ref-weak-2026-04-15

---

## 0. HARD RULES (v1.0 — APT v24 역분석)

APT HR1-HR15를 역방향에 맞게 재정의. 위반 시 orchestrator HALT.

| # | Rule | 근거 |
|---|------|------|
| TR1 | **매 phase gate에 AdversarialValidator 필수** | APT HR1 거울 |
| TR2 | **APPROVED verdict에 증거(evidence) 필수** | APT HR11 anti-rubber-stamp |
| TR3 | **Phase 순서 강제 (TCW→ST→SP→TA)** | APT HR7 거울, Gate Check Hook |
| TR4 | **AST 파서 필수 (grep 단독 금지)** | TCW 정확성 보장 |
| TR5 | **skipped_files = 0** | 부분 스캔 = 사각지대 |
| TR6 | **Unknown 발견 시 ResearchProvider 자동 호출** | 지식 공백 허용 불가 |
| TR7 | **모든 gate 전환 KG 기록** | APT HR7 거울 |
| TR8 | **2-Tier Taliban: Tier1(9-lens) for artifacts, Tier2(88-lens) for methodology only** | APT HR12 |
| TR9 | **Post-gate reflection 필수** | APT HR14 거울 |
| TR10 | **오답노트(Lesson) 발견 시 즉시 KG 기록** | 피드백 루프 강제 |
| TR11 | **executor ≠ reviewer (D20)** | 내가 만든 걸 내가 승인 금지. **인라인 APPROVED 금지 — Taliban subagent 최소 1개 독립 출격 강제.** |
| TR12 | **Longinus 바인딩: 결과물에 `# KG:` 주석 필수** | 양방향 추적 |
| TR13 | **treasure_coverage_min ≥ 0.9** | 본질 활용 최소 기준 |
| TR14 | **대형 repo(>10K LOC) 시 재배맨 병렬 분산 필수** | 단일 스캔 한계 교훈 |
| TR15 | **Essential ✗ 인정** | Arrow of Time, Gödel limit — 역분석은 원래 불완전 |

---

## 1. Configuration

```yaml
# tpa-config.yaml — v1.0
tpa:
  version: 1.0

  # --- LOCKED ---
  adversarial:
    enabled: true
    min_findings: 3
    gates: ["TCW_Gate", "ST_Gate", "SP_Gate", "TA_Gate"]

  approval:
    allow_agent_sigma: false    # 인간 승인 필수 (중요 결정)
    auto_approve_surface: true  # surface scan 단계는 자동 진행 가능

  ground_truth:
    tcw: "AST parser output"
    st: "contract extraction completeness"
    sp: "pattern library matching confidence"
    ta: "drift measurement < threshold"

  feedback_loop:
    enabled: true               # 오답노트 피드백 루프 활성
    lesson_auto_create: true    # 발견 즉시 Lesson 노드 생성
    quality_plan_auto: true     # Lesson → ActionPlan 자동 연결

  # --- Configurable ---
  parallel:
    enabled: true
    max_agents: 8
    strategy: "directory_split"

  reflection:
    mandatory: true
    template: "DISCOVERED: <what>, LESSON: <lesson-name>, QUALITY_ACTION: <improvement>"

  essential_failures:
    information_loss: "역분석은 원본 의도의 부분만 복원 가능 (Gödel)"
    naming_drift: "원저자 네이밍과 TPA 추출 네이밍 괴리 불가피"
    dead_code: "실행 경로 분석 없이 dead code 완전 식별 불가"
```

---

## 2. Phase Detection Algorithm

```cypher
// TPA Phase Detection — 역순이므로 코드→설계 방향
MATCH (exec:TPA_Execution {name: $exec_name})
OPTIONAL MATCH (exec)-[:PHASE_OUTPUT {order:1}]->(tcw:TPA_TCW_Result)
OPTIONAL MATCH (exec)-[:PHASE_OUTPUT {order:2}]->(tt:TPA_ST_Result)
OPTIONAL MATCH (exec)-[:PHASE_OUTPUT {order:3}]->(tp:TPA_SP_Result)
OPTIONAL MATCH (exec)-[:PHASE_OUTPUT {order:4}]->(ta:TPA_TA_Result)
OPTIONAL MATCH (exec)-[:HAS_VALIDATION]->(vr:ValidationResult)
WITH exec, tcw, tt, tp, ta, collect(vr.phase) AS validated_phases
RETURN exec.name,
  CASE
    WHEN ta IS NOT NULL THEN 'COMPLETE (TA done, use --audit for drift check)'
    WHEN 'SP' IN validated_phases THEN 'Phase 4: TA (pattern matched, run /tpa-ta)'
    WHEN 'ST' IN validated_phases THEN 'Phase 3: SP (contracts extracted, run /tpa-sp)'
    WHEN 'TCW' IN validated_phases THEN 'Phase 2: ST (code scanned, run /tpa-st)'
    WHEN tcw IS NOT NULL THEN 'Phase 1: TCW done but unvalidated (run /taliban)'
    ELSE 'Phase 1: TCW (start with /tpa-tcw)'
  END AS current_phase
```

---

## 3. Dispatch Table

| Input | Action |
|---|---|
| `/tpa <path>` | Phase Detection → 해당 phase sub-skill 호출 |
| `/tpa --audit <anchor>` | `/tpa-ta --audit <anchor>` (drift 재감사) |
| `/tpa --status` | Phase Detection 쿼리 실행 + 미완료 TPA 목록 |
| `/tpa --lessons <target>` | 해당 target의 발견된 Lesson 목록 + 미해결 건 |

---

## 4. Flow Control with Adversarial Gates

```
/tpa <path>
    |
    v
[Phase Detection]
    |
    +-- No TPA_Execution exists ────────→ /tpa-tcw <path>
    |                                         |
    |                            TCW_Result   v
    |                                    [GATE: Taliban 9-lens]
    |                                    [GATE: Post-gate reflection]  ← TR9
    |                                    [LOG: KG + Lessons]           ← TR10
    |                                         |
    +-- TCW validated ──────────────────→ /tpa-st
    |                                         |
    |                            TT_Result    v
    |                                    [GATE: Taliban 9-lens]
    |                                    [GATE: Post-gate reflection]
    |                                    [LOG: KG + Lessons]
    |                                         |
    +-- ST validated ───────────────────→ /tpa-sp
    |                                         |
    |                            TP_Result    v
    |                                    [GATE: Taliban 9-lens]
    |                                    [GATE: Post-gate reflection]
    |                                    [LOG: KG + Lessons]
    |                                         |
    +-- SP validated ───────────────────→ /tpa-ta
    |                                         |
    |                            TA_Result    v
    |                                    [GATE: Taliban 9-lens]
    |                                    [FINAL: Feedback Loop 실행]
    |                                         |
    +-- COMPLETE ───────────────────────→ 오답노트 피드백 루프 발동
```

---

## 5. 오답노트 피드백 루프 (Lesson Feedback Loop)

> **TPA의 존재 이유**: 남의 코드를 분석해서 **우리 프로젝트의 교훈**을 얻는 것.

### 5.1 루프 구조

```
┌─────────────────────────────────────────────────────┐
│                 오답노트 피드백 루프                    │
│                                                     │
│  ① TPA 분석 (TCW→ST→SP→TA)                         │
│       ↓                                             │
│  ② 발견 (Discovery)                                 │
│     - 구조적 동형 (Similarity)                       │
│     - 품질 갭 (QualityGap)                           │
│     - 신규 패턴 (NovelPattern)                       │
│     - 안티패턴 (AntiPattern)                         │
│       ↓                                             │
│  ③ 오답노트 기록 (Lesson)                             │
│     MERGE (l:Lesson {name:'lesson-tpa-...'})         │
│     SET l.category, l.problem, l.truth, l.solution   │
│       ↓                                             │
│  ④ 개선 계획 (ActionPlan)                            │
│     MERGE (p:ActionPlan)                             │
│     SET p.improvements=[...], p.priority=...         │
│     (l)-[:TRIGGERS]->(p)                             │
│       ↓                                             │
│  ⑤ 적용 (APT SCW)                                   │
│     ActionPlan → APT /apt-scw 로 실제 구현            │
│       ↓                                             │
│  ⑥ 검증 (Taliban)                                    │
│     구현 결과 → Taliban Gate → APPROVED?              │
│       ↓                                             │
│  ⑦ 오답노트 해소 (resolved=true)                      │
│     MATCH (l:Lesson) SET l.resolved=true             │
│       ↓                                             │
│  [루프 종료 또는 다음 발견으로 재진입]                    │
└─────────────────────────────────────────────────────┘
```

### 5.2 발견 유형별 Cypher 템플릿

```cypher
// ① 구조적 동형 (Similarity) — 두 프로젝트의 같은 패턴
MERGE (sim:Similarity {name:'sim-<name>'})
SET sim.source_project=$source, sim.target_project=$target,
    sim.pattern=$pattern, sim.confidence=$conf,
    sim.source_evidence=$src_path, sim.target_evidence=$tgt_path
MERGE (analysis)-[:IDENTIFIES]->(sim)

// ② 품질 갭 (QualityGap) — 타겟이 더 나은 점
MERGE (gap:QualityGap {name:'gap-<name>'})
SET gap.dimension=$dim, gap.source_level=$src_level,
    gap.target_level=$tgt_level, gap.improvement_action=$action
MERGE (analysis)-[:IDENTIFIES]->(gap)
MERGE (gap)-[:TRIGGERS]->(lesson:Lesson {name:'lesson-tpa-<name>'})

// ③ 신규 패턴 (NovelPattern) — 타겟에만 있는 패턴
MERGE (np:NovelPattern {name:'NP_<name>'})
SET np.description=$desc, np.applicability=$app
MERGE (analysis)-[:IDENTIFIES]->(np)

// ④ 안티패턴 (AntiPattern) — 피해야 할 것
MERGE (ap:AntiPattern {name:'AP_<name>'})
SET ap.description=$desc, ap.consequence=$con, ap.alternative=$alt
MERGE (analysis)-[:IDENTIFIES]->(ap)
```

### 5.3 피드백 루프 발동 조건

| 조건 | 동작 |
|---|---|
| TPA TA 완료 (COMPLETE) | 전체 발견 요약 → ActionPlan 생성 |
| QualityGap 발견 (any phase) | 즉시 Lesson 생성 (TR10) |
| NovelPattern confidence ≥ 0.8 | 적용 후보로 ActionPlan에 추가 |
| AntiPattern 발견 | 기존 코드에서 동일 패턴 검색 → Lesson 생성 |

---

## 6. Post-Gate Reflection (TR9 — 필수)

매 gate 통과 후:

```
REFLECTION:
  DISCOVERED: <이번 phase에서 발견한 핵심>
  LESSON: <lesson-name 또는 "신규 없음">
  QUALITY_ACTION: <333에 적용할 구체적 개선안>
  METHODOLOGY_GAP: <TPA 자체 방법론 개선점>
  NEXT_GATE_CHECKS: <다음 gate에서 추가로 확인할 것>
```

Reflection 미작성 = INCOMPLETE_GATE (TR9 위반).

---

## 7. 대형 Repo 전략 (TR14)

### 7.1 크기 판별

| LOC | 전략 |
|---|---|
| < 10K | 단일 스캔 |
| 10K - 100K | 재배맨 4-agent 분산 (디렉토리 분할) |
| 100K+ | 재배맨 8-agent 분산 + 계층적 합성 |

### 7.2 Chunking Protocol (v2 — Manifest-Based)

<!-- KG: lesson-tpa-missing-manifest-step-2026-04-16, lesson-tpa-conceptual-vs-file-chunking-2026-04-16 -->

> **v1 교훈**: 디렉토리 단위 분할 → 하위 dir 누락 + 경계 겹침 → 3600 LOC 미스캔 (wasmCloud TCW).
> **v2 규칙**: 파일 단위 분할. manifest 필수. 디렉토리명 지시 금지.

```
1. find $TARGET -name '*.{rs,ts,py,go}' -not -path '*/target/*' | sort → manifest.txt
2. 파일별 LOC 측정 (wc -l per file)
3. 에이전트 수 결정: N = ceil(total_loc / LOC_LIMIT)
   - haiku: 5K LOC/agent
   - sonnet: 10K LOC/agent
   - opus: 20K LOC/agent
4. 파일 단위 균등 분배 (LOC 내림차순 → 라운드로빈 → ±20% 허용)
   ⚠️ 디렉토리 단위 분할 금지 — 경계 겹침 → 누락 발생
5. 각 에이전트 프롬프트에 명시적 파일 경로 리스트 주입
   ⚠️ "이 디렉토리 읽어" 금지 — "이 N개 파일 읽어"만 허용
6. feature-gated 코드 동등 스캔 명시 (#[cfg(feature)] 축약 금지)
7. 부모 post-dispatch: assert union(agent_files) == manifest_files
   불일치 시 보충 에이전트 출격
8. 각 agent → FullFindingRecord JSON 반환
9. 부모: UNWIND 단일 트랜잭션으로 KG merge
10. 합성: 교차 참조 그래프 구축
```

# KG: lesson-tpa-gap-large-repo-chunking-2026-04-14, lesson-tpa-missing-manifest-step-2026-04-16

---

## 8. Migration (v0.4 → v1.0)

| 변경 | 영향 |
|---|---|
| Hard Rules TR1-TR15 추가 | sub-skill에 reflection 섹션 추가 필요 |
| 오답노트 피드백 루프 | 신규 — `--lessons` 명령 추가 |
| Phase Detection 쿼리 | 기존 dispatch 유지, 자동 감지 추가 |
| 5대 본질 참조 명시 | MIC Binding 이미 있었으므로 변경 없음 |
| Configuration yaml | 신규 — tpa-config.yaml |
| Post-gate reflection | 신규 — 각 sub-skill에 반영 필요 |

**하위 호환**: `/tpa <path>` 호출 동작 100% 유지. 신규 기능은 추가적.

## 9. Sub-Skills (4 phase)

- `/tpa-tcw` — Phase 1/4: TargetCodeWorld (코드 → 심볼 추출)
- `/tpa-st` — Phase 2/4: TargetTwin (심볼 → Contract 추출)
- `/tpa-sp` — Phase 3/4: TargetPyramid (Contract → Pattern 매칭)
- `/tpa-ta` — Phase 4/4: TargetAnchor (Pattern → SemanticAnchor 앵커링)

각 sub-skill은 독립 폴더에 SKILL.md + references/ 구조.
Hook (`apt-gate-check.sh`)가 phase 순서 강제.

---

## 10. References

- `references/hard_rules.md` — TR1-TR15 상세 설명 + APT 거울 매핑
- `references/feedback_loop.md` — 오답노트 피드백 루프 상세 프로토콜 **+ v1.1 Schema Extensions** (DOM-Side-Effect / Cross-Bundle-Write / Temporal / initialization_mode / silent_degradation / execution_context / type_params+ContractGap / state_ownership+layering_audit / workspace_resolver + 5 new DesignPatterns). 출처: `tpa-exec-mcp-superassistant-2026-04-18`.
- `references/phase_detection.cypher` — Phase Detection 쿼리 모음
- `references/shared_subskill_template.md` — 4 sub-skill 공통 템플릿
- `MIGRATION_v0.3_to_v0.4.md` — 이전 마이그레이션 가이드
- `MIGRATION_v0.4_to_v1.0.md` — v1.0 마이그레이션 가이드

## 11. 재배맨 바인딩

> SKILL.md는 **얇은 엔트리**. KG `SubagentTaskSpec` 씨앗이 본체.

### 세션 진입 시
```cypher
MATCH (wb:WorkBuffer {status:'CURRENT'}) RETURN wb
MATCH (e:TPA_Execution) WHERE e.status STARTS WITH 'IN_PROGRESS'
RETURN e.name, e.target, e.phase_current ORDER BY e.started_at DESC LIMIT 3
```

### 세션 종료 시
```cypher
MATCH (w:WorkBuffer) WHERE w.status='CURRENT' SET w.status='ARCHIVED', w.archived_at=datetime()
MERGE (wb:WorkBuffer {name:$next_name})
SET wb.status='CURRENT', wb.phase='TPA orchestrator', wb.updated_at=datetime()
```

---

## MIC Binding Disclaimer

> 이 SKILL.md에서 "Prometheus", "Taliban", "88-Taliban", "Longinus", "재배맨" 등의
> concrete 이름은 MIC_v1 MethodologySlot의 **현재 바인딩(currentConcrete)**이다.
> Slot이 다른 concrete로 교체되면 이 파일의 이름도 drift한다.
> 정본 해석: `MATCH (mic:MethodologyIntegrationContract {name:'MIC_v1'})-[:HAS_SLOT]->(s) RETURN s.name, s.currentConcrete`
> 유틸리티: `03_SCRIPTS/db/resolve_mic_slot.cypher`
> # KG: lesson-skill-mic-slot-ref-weak-2026-04-15

# KG: ATOM_Skill_tpa_orchestrator_v10, ATOM_재배맨_autoboot_tpa
