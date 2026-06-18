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
  Invoke when: parent /apt orchestrator dispatch only; direct user call 금지 (PATTERN_D guard, E1.4). SCW 는 SP→ST→SCW gate chain 의 4/4 phase — 단독 호출 시 ST gate APPROVED + AtomicSpan.wave_index + SubagentTaskSpec FK precondition 자동 만족 불가, dispatch_only=true.
  Active Weapons (2026-05-14): 재배맨 single-message N parallel Task dispatch (wave_index batch, Step 10) + Longinus L5-L7 forward binding (Code → `# KG:` ref comment, Step 12) + Naesengmoon `/tlb <SourceCodeNode> --lens constitutional` FulfillmentGate 7-check (Step 13). hub-jaebaeman-sop + hub-longinus-reference + hub-taliban-immunity resolve.
  # KG: ATOM_Skill_apt_scw, CONTRACT_apt_scw, APT_v26_RFC_draft_2026-04-21, ATOM_APT_v26_Gate_Hook_Lens_Enforcement_2026-04-21, rf-prom16-cc-eng-E1-S4
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

## ⚔ Active Weapons — Phase SCW (4/5)

> SCW 측 활성 5무기 (parent /apt orchestrator §"5무기 Phase Integration Matrix" mirror).

| Step | Weapon | Invocation | Trigger | Output |
|------|--------|-----------|---------|--------|
| Step 10 (wave dispatch) | **재배맨** (SubagentSeeder) | single-message N parallel `Task()` calls (max=`cfg.parallel_max_agents`, wave_index 같은 SubagentTaskSpec batch) | ST APPROVED + AtomicSpan.wave_index 결정 + SubagentTaskSpec FK 준비 | N 개 parallel implementation results (single assistant turn) |
| Step 11 (TDD RED→GREEN→REFACTOR) | **재배맨** + **Naesengmoon** | per-Task: RED test write → GREEN code → impact_tests verify → mini-RGR | wave dispatch 후 각 Task 내부 | Code + test (per AtomicSpan, ≤ `cfg.vibe_coding_hard_max` LOC) |
| Step 12 (Code → KG ref comment) | **Longinus** (KgCodeBinder) | L5-L7 forward binding: 모든 함수/클래스/모듈에 `# KG: <node_name>` 주석 강제 | GREEN 통과 직후 (PostToolUse Write/Edit hook) | `SourceCodeNode` + `MATERIALIZES` edge + Longinus 7-tuple binding |
| Step 13 (FulfillmentGate 7-check) | **Naesengmoon** (AdversarialValidator) | `/tlb <SourceCodeNode> --lens constitutional`: (1) executor!=critic (2) LensSet completeness (3) prior VR APPROVED (4) Contract 4-측면 충족 (5) `# KG:` ref 존재 (6) impact_tests PASS (7) fat-file ratchet 통과 | 모든 wave task GREEN + Longinus binding 완료 | `VerdictRecord` APPROVED + Cleanup 진입 trigger |

**SCW 진입 hub**: `hub-jaebaeman-sop` (wave dispatch parallel) + `hub-longinus-reference` (Code↔KG binding) + `hub-taliban-immunity` (FulfillmentGate).

**Anti-pattern 금지**:
- Sequential Task dispatch (= 재배맨 위반) — 반드시 *single assistant turn* 측 N parallel.
- Code orphan (= Longinus 위반) — `# KG:` 주석 없는 함수/클래스는 PostToolUse hook 측 차단.
- Same-model critic (= Naesengmoon HR3 위반) — design model ≠ critic model 강제.

# KG: hub-jaebaeman-sop, hub-longinus-reference, hub-taliban-immunity, MIC_v1.SubagentSeeder, MIC_v1.KgCodeBinder, MIC_v1.AdversarialValidator

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
2. /taliban SCW Gate 실행 (executor != Naesengmoon)
3. Naesengmoon APPROVED → 그때만 ValidationResult(phase='SCW', verdict='APPROVED') 기록
4. 기록 주체 = Naesengmoon agent (or 별도 reviewer), 절대 executor 본인 아님
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

### Step 2: Task별 TDD 루프 (wave-aware dispatch)

> v27.2 (2026-05-14, GAP-4): SP 가 부여한 `AtomicSpan.wave_index` (GAP-1) + 재배맨 `SubagentTaskSpec.sourceId` FK 1:1 (GAP-3) 를 합쳐 **wave 단위 single-message N-parallel dispatch**.
> 사용자 정전: 「최대한 병렬 처리가 되도록」 + 「종속성 아닌 부분은 최대 병렬」.
> 상세: [`references/wave_dispatch.md`](references/wave_dispatch.md).

#### 2-0. Wave Loop (외곽 — 부모 책임)

```
W_max ← MAX(AtomicSpan.wave_index)            -- e.g. 3 for 3-wave 7-span 예제
for w in 1..W_max:
    batch ← collect_ready_seeds(wave = w)     -- §2-1 Cypher
    intent_N ← |batch|
    Agent_calls ← single_message_parallel(batch)   -- §2-2
    actual_N ← |Agent_calls|
    assert intent_N == actual_N               -- GH#29181 self-check, §2-3
    results ← collect_all(Agent_calls)
    if all(v == 'PASS' for v in results):
        UNWIND_write_kg(results)              -- 재배맨 Phase 4
        advance to wave w+1
    else:
        raise WavePartialFail(wave=w, failed=[...])    -- §2-4 차단
```

**Invariant**:
- **Same wave**: fully parallel (1 message, N Agent tool calls).
- **Cross wave**: strictly sequential (wave k+1 은 wave k 전체 PASS 후).
- Kahn ordering: `(a)-[:DEPENDS_ON]->(b) ⟹ a.wave_index < b.wave_index`.

#### 2-1. Wave-aware batch collect Cypher

```cypher
// SCW dispatch step (wave-aware, GAP-1 + GAP-3 통합)
// $CURRENT_WAVE: driver loop 변수
MATCH (a:AtomicSpan)-[:HAS_SEED]->(ts:SubagentTaskSpec {skill:'apt-scw'})
WHERE a.wave_index = $CURRENT_WAVE AND ts.status = 'READY'
WITH ts, a ORDER BY a.name
RETURN collect({
  seed_name: ts.name, source_atom: a.name,
  task_type: ts.taskType, contract_ref: ts.contractRef,
  task_ref: ts.taskRef, wave: a.wave_index
}) AS dispatch_batch
// → 재배맨 lead_link: single-message N parallel Agent calls
```

#### 2-2. Single-message dispatch (재배맨 Phase 2)

```
[부모 message]:
  Agent(model='haiku', prompt=<seed_1 3줄+pre-fetch>)
  Agent(model='haiku', prompt=<seed_2 3줄+pre-fetch>)
  ... (N seeds 동시)
```

> **WRITE_DEFERRED_TO_PARENT (PROM 16 T3 2026-05-24 ship)**: 각 seed prompt 본문에 다음 clause
> mandatory 주입 — "너는 KG 에 직접 write 할 수 없다. AptContract.status='Fulfilled',
> SemanticTask.status='PASS', SourceCode MERGE 의도는 `kg_write_intent_json` field 에 JSON 으로
> 반환만 한다. 실제 write 는 parent 가 Step 4 (KG 물질화 기록) 에서 수행. 금지 표현:
> `kg_writes_done=true` / 'Fulfilled 기록 완료' / 'MATERIALIZES edge 생성' 류 claim. 위반 시
> parent ReconciliationNode 발동." 정전 anchor: `lesson-subagent-self-drift-kg-write-prom16-2026-05-24`.

각 seed 내부에서 **TDD 3-step**:
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

#### 2-3. GH#29181 self-check (intent vs actual)

```
pre_dispatch:  intent_N = |dispatch_batch|
post_dispatch: actual_N = count(tool_use blocks in parent message)
assert actual_N == intent_N, DispatchIntentMismatch(wave, intent, actual, delta)
```

| delta | 복구 |
|---|---|
| `> 0` (under-dispatch) | 누락 seed status 'READY' 복원 + 재dispatch |
| `< 0` (over-dispatch) | 초과 Agent 결과 ARCHIVED + rejected_reason='OverDispatch' |

#### 2-4. WavePartialFail handling

wave w 의 N seed 중 M≥1 FAIL → wave w+1 진입 **차단**.

```cypher
MERGE (wpf:WavePartialFail {
  project: $PROJECT, wave: $CURRENT_WAVE, cycle_id: $CYCLE_ID
})
SET wpf.failed_count = $M, wpf.total_count = $N,
    wpf.failed_seeds = $failed_seed_names,
    wpf.user_verdict_required = true,
    wpf.advance_blocked = true;
```

복구 옵션 (사용자 verdict 게이트):
- (a) Retry-Seed (timeout 등 일시 실패)
- (b) Span 재분해 → SP 로 되돌려 D(S) 추가 분해 → wave_index 재계산
- (c) Contract 보강 → ST 로 되돌려 acceptance_criteria 강화
- (d) Force-advance — **금지** (DEPENDS_ON 순서 위반 → downstream 코드 폭발)

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
| executor = reviewer | 자기 승인 금지 | Naesengmoon D20 protocol |

---

## 🌱 재배맨 v2 (MIC Slot Reference — 로직 복제 금지)

> 이 스킬의 subagent 운용은 **MIC_v1.SubagentSeeder** slot을 통해 resolve된다.
> 아래는 thin resolver. 로직 복제 = drift 유발.

### Slot Resolve
```cypher
MATCH (mic:MethodologyIntegrationContract {name:'MIC_v1'})-[:HAS_SLOT]->(s:MethodologySlot {name:'SubagentSeeder'})
RETURN s.currentConcrete, s.invocation, s.protocol
```

### 부모 Pre-fetch (v2 — MCP 우회) + Wave-aware ready batch (v27.2)
```cypher
// (a) Lesson/RF context pre-fetch
MATCH (l:Lesson)-[:HAS_RESEARCH]->(rf:ResearchFinding)
WHERE l.name CONTAINS $keyword RETURN rf.name, rf.domain, rf.oneLineSummary LIMIT 20

// (b) Wave-aware READY seed batch (GAP-1 wave_index + GAP-3 sourceId FK 통합)
// $CURRENT_WAVE: driver loop 변수 (1..W_max)
MATCH (a:AtomicSpan)-[:HAS_SEED]->(ts:SubagentTaskSpec {skill:'apt-scw'})
WHERE a.wave_index = $CURRENT_WAVE AND ts.status = 'READY'
RETURN collect(ts) AS dispatch_batch
// → 재배맨 lead_link: single-message N parallel Agent calls (same wave fully parallel)
// → cross-wave sequential (wave k+1 은 wave k 전체 PASS 후만)

// (c) Legacy fallback (wave_index 미부여 — 차단 대상이지만 진단용)
MATCH (ts:SubagentTaskSpec {skill:'apt-scw'}) WHERE ts.status='READY'
RETURN ts.name, ts.role LIMIT 10
```

상세 wave loop pseudocode + WavePartialFail + GH#29181 self-check: §Step 2 (TDD 루프) 및 [`references/wave_dispatch.md`](references/wave_dispatch.md).

### WorkBuffer 연속성
```cypher
MATCH (wb:WorkBuffer {status:'CURRENT'}) RETURN wb
```

# KG: ATOM_재배맨_v2_apt-scw, SA_methodology_v4_triple_upgrade

---

## MIC Binding Disclaimer

> 이 SKILL.md에서 "Prometheus", "Naesengmoon", "88-Naesengmoon", "Longinus", "재배맨" 등의
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
> - **Wave-aware dispatch (Kahn batch + single-message N-parallel + WavePartialFail)**: [`references/wave_dispatch.md`](references/wave_dispatch.md) (v27.2 GAP-4 2026-05-14)
> - Cross-skill shared: [`../_common/`](../_common/) (Contract Lifecycle FSM § migrated).
> - Legacy redirect: `references/scw_world.md`.

| Version | Date | Summary | KG Ref |
|---|---|---|---|
| **v27.2** | 2026-05-14 | **Wave-aware dispatch (GAP-4)** — Step 2 TDD 루프 본문에 wave loop pseudocode + wave-aware batch Cypher (`a.wave_index = $CURRENT_WAVE`) + single-message N-parallel + GH#29181 intent-vs-actual self-check + WavePartialFail handling (wave k+1 진입 차단 + 사용자 verdict 게이트). GAP-1 (`apt-sp/references/wave_extraction.md`) + GAP-3 (`jaebaeman/references/seed_fk_invariant.md`) 통합. 3-wave 7-span worked example GAP-1 와 동일. | `span-gap4-scw-wave-dispatch-2026-05-14`, `APT_SP_WaveExtraction_canonical`, `lesson-jaebaeman-rebrand-SOP-2026-05-05` |
| **v26** | 2026-04-21~25 | A2 Contract v2 alignment + A4 vibe_coding_sweet/min/hard_max via MethodologyConfig slot (no more hardcoded 500). A5 FulfillmentGate 7 checks via apt-gate-check.sh Cypher (executor≠critic + LensSet completeness + prior VR APPROVED). TDAD (impact_tests mandatory) | `APT_v26_RFC_draft_2026-04-21`, `ATOM_APT_v26_Gate_Hook_Lens_Enforcement_2026-04-21`, `lesson-apt-vr-self-fulfilled-executor-reviewer-2026-04-16` |
| **v24** | 2026-04 mid | KG 정본 기반 재설계 (`CONTRACT_apt_scw`). Same-layer Tasks parallel | — |
| **v5~v23** | timestream | TDD implementation (Contract → Test RED → Code GREEN → Refactor). Code MUST have KG refs in comments (Longinus ReferenceSite 7-tuple) | — |

⚠️ **TDD REFACTOR phase 거울 부재** (cycle-level): `lesson-apt-phase6-cleanup-missing-2026-04-28` (HIGH, unresolved). atomic-span shipping 정규화가 *평면 누적* 메커니즘 그 자체. SOLID class-level 통과해도 folder-level CCP 위반 (Robert Martin Package Principles). KG: `lesson-solid-class-level-vs-package-level-mismatch-2026-04-29`.

# KG history: ATOM_Skill_apt_scw / lesson-prom16-skill-versioning-academic-2026-04-29 / lesson-apt-phase6-cleanup-missing-2026-04-28 / lesson-solid-class-level-vs-package-level-mismatch-2026-04-29
