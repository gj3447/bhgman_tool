---
name: apt-scw
kg_ref: ATOM_Skill_apt_scw
version: "27.1.0"
channel: stable
description: >
  APT SourceCodeWorld (SCW) — TDD implementation of crystallized Contracts.
  Contract → Test first (RED) → Code (GREEN) → Refactor.
  Same-layer Tasks are fully parallel. Code MUST have KG refs in comments (Longinus ReferenceSite 7-tuple, v26 A2).
  v26 A5: FulfillmentGate 7 checks enforced via apt-gate-check.sh Cypher query (executor!=critic + LensSet completeness + prior VR APPROVED). TDAD (impact_tests mandatory).
  v26 A4: vibe_coding_sweet/min/hard_max via MethodologyConfig slot (no more hardcoded 500).
  v24: KG 정본 기반 재설계. AptClarificationNote 반영.
  # KG: ATOM_Skill_apt_scw, CONTRACT_apt_scw, APT_v26_RFC_draft_2026-04-21, ATOM_APT_v26_Gate_Hook_Lens_Enforcement_2026-04-21
---

## 🎛 v26 A6 Resolve-Only

> FulfillmentGate 7 checks / vibe_coding max line — **하드코딩 금지**. apt-gate-check.sh v0.7 자동 enforce.

```cypher
// FulfillmentGate enforcement (executor != critic + LensSet completeness)
MATCH (vr:ValidationResult)-[:USED_LENS]->(ls:LensSet) WHERE ls.deprecated <> true AND ls.lensCount >= 9 RETURN vr

// v0.8.A1 ensemble option (2026-05-05, opt-in via APT_GATE_VERSION=v08-A1)
// — FulfillmentGate에 ensemble UNION concern-coverage>=0.8 적용 가능
// — Agent(taliban-ensemble-critic) 권장: 4 LensSet ensemble + USED_LENS edge auto-bind
MATCH (rfc:MethodologyRFC {name:'rfc-taliban-v08-concern-coverage-2026-05-04'})
RETURN rfc.status

// Task line limits
MATCH (cfg:MethodologyConfig {name:'MethodologyConfig_default_v26'})
RETURN cfg.vibe_coding_hard_max, cfg.vibe_coding_sweet_max

// Longinus ReferenceSite 7-tuple binding (code↔KG)
MATCH (schema:SchemaDefinition {name:'schema-ReferenceSite-v1-2026-04-20'}) RETURN schema.fields
```

**Impact test mandatory** (TDAD). **Longinus Post-Write gate**: apt-gate-check-v0.5.sh PostToolUse Write/Edit audit. # KG: APT_v26_A6_2026-04-21, ATOM_APT_v26_Gate_Hook_Lens_Enforcement_2026-04-21

---

## 🔗 MIC Binding (SOLID-DIP)

**IS slot**: APT_Phase (SCW, 4/4)
**USES slots**: KgCodeBinder (코드 주석 KG ref), AdversarialValidator (FulfillmentGate)

```cypher
MATCH (mic:MethodologyIntegrationContract {name:'MIC_v1'})-[:HAS_SLOT]->(s:MethodologySlot)
WHERE s.name IN ['KgCodeBinder','AdversarialValidator']
RETURN s.name, s.currentConcrete, s.invocation
```

# KG: MIC_v1, lesson-apt-not-truly-jaebaeman-2026-04-14

---

# /apt-scw — SourceCodeWorld: TDD Implementation

> **SCW = Contract가 실행 코드가 되는 곳.**
> 코드 = Contract의 물질화(materialization).
> KG가 정본(canonical), 코드는 구현 공간.
> 코드가 contract를 구현하지만, 코드를 의미론적 정본과 혼동하면 안 된다.

## ⛔ GATE CHECK (Hook 강제)

> `apt-gate-check.sh`가 자동 실행. ST Gate 미통과 시 `permissionDecision: deny`.
> `$PROJECT`는 apt-progress.md의 `## Anchor:` 에서 읽는다.
> BLOCKED 시: `/apt-st` → `/taliban` → ST Gate 통과 → `/apt-scw` 재호출.

---

## ⛔ 세션 재개 가드 (context compression 방어)

**새 세션 또는 context compression 이후 SCW를 시작할 때 반드시 확인:**

```
1. apt-progress.md 읽기 → Anchor 이름 확인
2. KG에서 ST Gate ValidationResult 확인:
   MATCH (sa:SemanticAnchor {name: $PROJECT})-[:HAS_VALIDATION]->(vr:ValidationResult)
   WHERE vr.phase = 'ST' AND vr.verdict = 'APPROVED'
   RETURN vr.name
3. 결과 없으면 → /apt-st → /taliban → ST Gate 통과 후 재진입
4. 결과 있으면 → Contract 목록 로드 후 TDD 시작
```

**금지**: context compression 후 이전 대화에서 "했던 것 같으니" 직접 코드 작성.
이유: `lesson-apt-scw-tdd-skipped-context-compression-2026-04-16` — 세션 단절 시 TDD Strange Loop 전체가 생략됨.

---

## FulfillmentGate — executor ≠ reviewer 강제

Contract 이행 완료 선언(Fulfilled) 전 반드시 확인:

```
⛔ SELF-FULFILLMENT 금지
IF executor(코드 작성자) == reviewer(Fulfilled 선언자):
    → REJECTED. lesson-apt-vr-self-fulfilled-executor-reviewer-2026-04-16 참조

올바른 절차:
1. SCW executor가 Task 구현 → acceptance_criteria 테스트 통과 확인
2. /taliban SCW Gate 실행 (executor != Taliban)
3. Taliban APPROVED → 그때만 ValidationResult(phase='SCW', verdict='APPROVED') 기록
4. 기록 주체 = Taliban agent (or 별도 reviewer), 절대 executor 본인 아님
```

---

## TDD Strange Loop

```
1. Contract의 acceptance_criteria에서 테스트 작성 (RED)
2. 테스트가 통과하는 최소 코드 구현 (GREEN)
3. 리팩토링 (REFACTOR)
4. FulfillmentGate `{{cfg.fulfillment_gate_checks}}` checks (현재 7)
5. 통과 → Contract status = Fulfilled
```

같은 레이어의 AtomicSpan은 **완전 독립**이므로 **병렬 구현 가능**.
Contract가 인터페이스 역할 — 각 Task는 자기 Contract만 이행.

---

## KG Ref 주석 — 롱기누스 필수

> "SourceCodeWorld의 코드 파일은 KG 노드 참조를 주석으로 포함해야 한다.
> 이는 코드↔KG 양방향 추적성(traceability)을 보장한다."

### 규칙

```python
# KG: TASK_OM_GPU_Modal_Hardening          ← 파일 상단: 이 파일이 구현하는 Task
# KG: CONTRACT_OM_GPUAllocateIO           ← 클래스/함수: 준수하는 Contract

class ModalGPUProvider(GPUProvider):
    def allocate(self, name, gpu_type, ...) -> GPUInstance:  # CONTRACT_OM_GPUInstance
        ...
```

1. **파일 상단**: `# KG: TASK_xxx` (이 파일이 구현하는 SemanticTask)
2. **클래스/함수 docstring**: `# KG: CONTRACT_xxx` (준수하는 Contract/DTO)
3. **주요 로직**: `# KG: ATOM_xxx` 또는 `SPAN_xxx` (관련 Span 참조)

**KG ref 없는 코드 = 롱기누스 추적 불가 = APT 위반.**

---

## SemanticTask 구현 단위

| 속성 | 규칙 |
|------|------|
| estimated_lines | **≤ `cfg.vibe_coding_hard_max`** (바이브코딩 최적 단위) |
| target_file | 단일 파일 |
| acceptance_criteria | 실행 가능한 테스트 |
| impact_tests | **필수** (TDAD) — 빈 값 = BLOCKING violation |

> "Task estimated_lines > `{{cfg.vibe_coding_sweet_max}}` (현재 500) → Span을 더 분해해야 함"
> "Contract가 잘게 쪼개져야 Task도 잘게 나뉨"

---

## SCW 실행 절차

### Step 1: Contract + Task 로드

```cypher
MATCH (sa:SemanticAnchor {name: $PROJECT})-[:HAS_ROOT]->(root)
MATCH (root)-[:DECOMPOSES_TO*1..10]->(atom:AtomicSpan)
MATCH (atom)-[:CRYSTALLIZES_TO]->(st:SemanticTwin)
MATCH (st)-[:HAS_CONTRACT]->(c:AptContract)
MATCH (st)-[:HAS_TASK]->(t:SemanticTask)
WHERE c.status = 'CRYSTALLIZED'
RETURN atom.name, c.name, c.input_type, c.output_type, c.acceptance_criteria,
       t.name, t.target_file, t.estimated_lines, t.impact_tests
ORDER BY atom.name
```

### Step 2: Task별 TDD 루프

각 Task에 대해:

```
2a. acceptance_criteria → 테스트 파일 작성 (RED)
    - 테스트가 먼저. 코드 전에 테스트.
    - impact_tests 경로에 작성

2b. 테스트 통과하는 최소 코드 구현 (GREEN)
    - target_file에 작성
    - # KG: TASK_xxx, CONTRACT_xxx 주석 포함

2c. 리팩토링 (REFACTOR)
    - 테스트 여전히 통과 확인
    - 중복 제거, 명확성 개선
```

### Step 3: FulfillmentGate — `{{cfg.fulfillment_gate_checks}}` Checks (현재 7)

| # | Check | 검증 |
|:-:|-------|------|
| 1 | Tests pass | acceptance_criteria의 모든 테스트 GREEN |
| 2 | Coverage | 핵심 로직 테스트 커버 |
| 3 | Contract alignment | input_type/output_type이 코드와 일치 |
| 4 | KG refs present | # KG: 주석 존재 |
| 5 | Lines ≤ `{{cfg.vibe_coding_sweet_max}}` (현재 500) | target_file 줄 수 확인 |
| 6 | No abstract types | data/any/result 타입 미사용 |
| 7 | impact_tests filled | 빈 값 아님 |

**`{{cfg.fulfillment_gate_checks}}/{{cfg.fulfillment_gate_checks}}` PASS (현재 7/7) → Contract status = Fulfilled.**

### Step 4: KG 물질화 기록

```cypher
MATCH (c:AptContract {name: $CONTRACT})
SET c.status = 'Fulfilled', c.fulfilledAt = datetime()

MATCH (t:SemanticTask {name: $TASK})
SET t.status = 'PASS', t.passedAt = datetime()

// 롱기누스: 코드↔KG 바인딩
MERGE (src:SourceCode {name: 'SRC_' + $TASK})
SET src.file_path = $TARGET_FILE,
    src.lines = $LINES,
    src.sourceId = $TASK,
    src.sourcePath = 'file://' + $TARGET_FILE
MERGE (c)-[:MATERIALIZES]->(src)
```

### Step 5: Integration (병렬 Task 통합)

같은 레이어의 모든 Task가 PASS이면:

```cypher
-- 통합 검증: 모든 Contract Fulfilled?
MATCH (sa:SemanticAnchor {name: $PROJECT})-[:HAS_ROOT]->(root)
MATCH (root)-[:DECOMPOSES_TO*1..10]->(atom:AtomicSpan)
MATCH (atom)-[:CRYSTALLIZES_TO]->()-[:HAS_CONTRACT]->(c)
WHERE c.status <> 'Fulfilled'
RETURN c.name as unfulfilled
```

unfulfilled = 0이면 → **프로젝트 완료**.

---

## PH6 Feedback — Strange Loop

SCW 실행 중 발견된 문제:
- **Task FAIL** → Span 재분해 필요 → SP로 피드백
- **Contract 불충분** → ST로 피드백
- **새로운 요구** → SA 업데이트

```
SCW → SP 피드백: "이 Span의 분해가 틀렸다"
SCW → ST 피드백: "이 Contract의 타입이 부족하다"
SCW → SA 피드백: "프로젝트 범위 변경 필요"
```

> "APT의 피드백 루프(PH6)는 과학의 자기수정과 동일.
> 괴델이 증명했듯이 어떤 체계도 자기 완전성을 보장 못하므로,
> 외부 피드백(사용자, 실행 결과)을 통한 지속적 수정이 유일한 해결책."

---

## What NOT To Do

| 금지 | 이유 | 대안 |
|------|------|------|
| 테스트 없이 코드 작성 | TDD 위반 | RED → GREEN → REFACTOR |
| KG ref 주석 생략 | 롱기누스 추적 불가 | # KG: TASK_xxx 필수 |
| impact_tests 비워두기 | TDAD BLOCKING violation | 테스트 경로 명시 |
| `cfg.vibe_coding_hard_max` 초과 파일 | Task 단위 초과 | SP로 돌아가 추가 분해 |
| Contract 무시하고 코드 | 물질화가 아닌 임의 구현 | Contract `{{cfg.contract_default_fields}}`대 필드 준수 (현재 7) |
| 코드를 정본으로 취급 | KG가 canonical | Neo4j Canonicality 원칙 |
| executor = reviewer | 자기 승인 금지 | Taliban D20 protocol |

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
MATCH (ts:SubagentTaskSpec {skill:'apt-scw'}) WHERE ts.status='READY'
RETURN ts.name, ts.role LIMIT 10
```

### WorkBuffer 연속성
```cypher
MATCH (wb:WorkBuffer {status:'CURRENT'}) RETURN wb
```

# KG: ATOM_재배맨_v2_apt-scw, SA_methodology_v4_triple_upgrade

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

> Repo-level changes: [`/CHANGELOG.md`](../CHANGELOG.md). Per-commit: `git log -- apt-scw/SKILL.md`.
> Architecture: Progressive Disclosure v3 — 494L _world.md split (2026-05-11):
> - TDD Strange Loop + Hoare Analogy (~ not =): [`references/tdd_strange_loop_hoare.md`](references/tdd_strange_loop_hoare.md)
> - FulfillmentGate 7 Checks: [`references/fulfillment_gate.md`](references/fulfillment_gate.md)
> - TDAD impact_tests (Baseline + Regression): [`references/tdad.md`](references/tdad.md)
> - EDD 5 criteria (Stochastic + CI Divergence): [`references/edd.md`](references/edd.md)
> - Gap Resolution (Thompson Sampling 70/30): [`references/gap_resolution.md`](references/gap_resolution.md)
> - Session Startup Protocol 7-step: [`references/session_startup.md`](references/session_startup.md)
> - PH6 Feedback (6 Discovery × 10 Categories): [`references/ph6_feedback.md`](references/ph6_feedback.md)
> - Anti-Patterns AP1-AP9: [`references/anti_patterns.md`](references/anti_patterns.md)
> - KG Reference Comments (Longinus L3 binding): [`references/kg_ref_comments.md`](references/kg_ref_comments.md)
> - SCW-specific Kafka payloads: [`references/kafka_events.md`](references/kafka_events.md)
> - SCW → SP/ST feedback handoff (Max returns): [`references/scw_to_sp_st_handoff.md`](references/scw_to_sp_st_handoff.md)
> - Cross-skill shared: [`../_common/`](../_common/) (Contract Lifecycle FSM § migrated).
> - Legacy redirect: `references/scw_world.md`.

| Version | Date | Summary | KG Ref |
|---|---|---|---|
| **v26** | 2026-04-21~25 | A2 Contract v2 alignment + A4 vibe_coding_sweet/min/hard_max via MethodologyConfig slot (no more hardcoded 500). A5 FulfillmentGate 7 checks via apt-gate-check.sh Cypher (executor≠critic + LensSet completeness + prior VR APPROVED). TDAD (impact_tests mandatory) | `APT_v26_RFC_draft_2026-04-21`, `ATOM_APT_v26_Gate_Hook_Lens_Enforcement_2026-04-21`, `lesson-apt-vr-self-fulfilled-executor-reviewer-2026-04-16` |
| **v24** | 2026-04 mid | KG 정본 기반 재설계 (`CONTRACT_apt_scw`). Same-layer Tasks parallel | — |
| **v5~v23** | timestream | TDD implementation (Contract → Test RED → Code GREEN → Refactor). Code MUST have KG refs in comments (Longinus ReferenceSite 7-tuple) | — |

⚠️ **TDD REFACTOR phase 거울 부재** (cycle-level): `lesson-apt-phase6-cleanup-missing-2026-04-28` (HIGH, unresolved). atomic-span shipping 정규화가 *평면 누적* 메커니즘 그 자체. SOLID class-level 통과해도 folder-level CCP 위반 (Robert Martin Package Principles). KG: `lesson-solid-class-level-vs-package-level-mismatch-2026-04-29`.

# KG history: ATOM_Skill_apt_scw / lesson-prom16-skill-versioning-academic-2026-04-29 / lesson-apt-phase6-cleanup-missing-2026-04-28 / lesson-solid-class-level-vs-package-level-mismatch-2026-04-29
