---
name: apt-meta-review
kg_ref: ATOM_Skill_apt_meta_review
version: "27.1.0"
channel: stable
description: >
  APT MetaReview Phase (5/5) — 의심/피드백을 자동으로 스킬 강화로 이어지는 피드백 루프.
  SCW 완료 후 자동 제안. Lesson 생성 → SKILL.md 패치 → MATERIALIZES 갱신 → Naesengmoon Gate.
  v2 (APT v26 A6 alignment): SKILL.md 패치는 resolve_slot(ContractSchema|LensSet|MethodologyConfig) 패턴 유지. Prose magic number 주입 금지. KG = 정본.
  종료조건: self_application_forbidden, max_depth=1, delta=0.
  Invoke when: parent /apt orchestrator dispatch only — direct user call rejected by APT_GATE_VERSION=v27_phase_meta_review_dispatch_guard. Korean: APT 메타-리뷰 페이즈 (5/5) — 상위 /apt 가 SCW 완료 후 자동 dispatch, 단독 호출 금지. MetaReview 는 SA→SP→ST→SCW→MetaReview chain 의 terminal phase — 단독 호출 시 SCW Fulfillment Gate APPROVED + Lesson/Verdict provenance + Naesengmoon Gate precondition 자동 만족 불가, dispatch_only=true (E1.4 PATTERN_D → PATTERN_A 격상, self_application_forbidden 재귀 차단 포함, rf-prom16-cc-eng-E1-S4-skill-activation-2026-05-14).
  Active Weapons (2026-05-14): Naesengmoon `/tlb <MetaReview output> --lens constitutional` (rubber-stamp 방지 자체재검증, Step 17) + Prometheus `/prom <small N> "<lesson_topic>"` (lesson distillation 외부 grounding, Step 15) + Longinus MATERIALIZES 갱신 (SKILL.md 패치 ↔ KG slot drift 차단, Step 16). hub-taliban-immunity + hub-prometheus-research + hub-longinus-reference resolve.
  # KG: ATOM_Skill_apt_meta_review, CONTRACT_Hardening_MetaReview, SPAN_Hardening_MetaReview, APT_v26_RFC_draft_2026-04-21, MIC_v1.ReasoningProtocol→KGFirstCheck_v1 (R1-R5 mandatory before any framing/diagnostic, lesson-ai-skipped-kg-check-before-framing-2026-04-29), rf-prom16-cc-eng-E1-S4-skill-activation-2026-05-14
---

## 🎛 v26 A6 Resolve-Only

> SKILL.md 패치 시 prose hardcoding 금지. KG slot 참조만. magic number/lens count 주입 시 Naesengmoon reject.

```cypher
// Before patching SKILL.md, verify slot targets exist
MATCH (slot:MethodologySlot) RETURN slot.name, slot.currentConcrete
// Lesson 생성은 resolved=false로 시작 (auto_resolve 금지)
// MATERIALIZES 갱신: Contract.materialization_status, AptSpan.contract_dto_status
```

**Self-application forbidden, max_depth=1, delta=0**. MetaReview가 자기 자신 재귀 호출 금지. # KG: APT_v26_A6_2026-04-21

---

## 🔗 MIC Binding (SOLID-DIP)

**IS slot**: APT_Phase (MetaReview, 5/5)
**USES slots**: AdversarialValidator (Naesengmoon Gate 자체재검증), KgCodeBinder (Longinus MATERIALIZES 갱신), SubagentSeeder (재배맨 taskspec, Lesson 생성 자동화)

**동적 resolution**:
```cypher
MATCH (mic:MethodologyIntegrationContract {name:'MIC_v1'})-[:HAS_SLOT]->(s:MethodologySlot)
WHERE s.name IN ['AdversarialValidator','KgCodeBinder','SubagentSeeder']
RETURN s.name, s.currentConcrete, s.invocation
```

본문의 `Naesengmoon`/`Longinus`/`재배맨`은 MIC slot 현재 스냅샷. 진짜 호출은 `s.invocation`.
**Self-application 금지**: MetaReview가 자기 자신을 다시 MetaReview하면 무한루프. `max_depth=1, delta=0` 경계 준수.

# KG: MIC_v1, ATOM_Skill_apt_meta_review, lesson-apt-skill-drift-audit-2026-04-17

---

## ⚔ Active Weapons — Phase MetaReview (5/5)

> MetaReview 측 활성 5무기 (parent /apt orchestrator §"5무기 Phase Integration Matrix" mirror).

| Step | Weapon | Invocation | Trigger | Output |
|------|--------|-----------|---------|--------|
| Step 14 (의심 발견) | (5무기 emergent) | 5무기 순환 측 창발 — FeedbackProvider slot EMERGENT 상태 | SCW FulfillmentGate APPROVED 후 자동 dispatch | Doubt log + AptFeedback 후보 |
| Step 15 (Lesson 결정화) | **Prometheus** (mini) | `/prom 4 "<lesson_topic> — 외부 정전 grounding"` (small N) | Doubt log 분석 후 lesson 추출 필요 | `Lesson` node (wrongAssumption↔truth symmetric pair 둘 다 채움) |
| Step 16 (SKILL.md 패치) | **Longinus** (KgCodeBinder) | MATERIALIZES 갱신: SKILL.md ↔ MethodologyConfig slot resolve, prose hardcoding 금지 | Lesson 적재 후 SKILL.md 패치 필요 | SKILL.md patch + KG slot update (drift 차단) |
| Step 17 (Naesengmoon Gate 자체재검증) | **Naesengmoon** (AdversarialValidator) | `/tlb <Lesson + SKILL.md patch> --lens constitutional` (self_application_forbidden + max_depth=1) | SKILL.md 패치 직후 | `VerdictRecord` APPROVED + cycle 종료 |

**Self-application 금지** (재귀 차단): MetaReview Output 측 Naesengmoon Gate 적용은 *external* critic — 자기 자신 MetaReview 재호출 금지. `max_depth=1, delta=0`.

**MetaReview 진입 hub**: `hub-taliban-immunity` (rubber-stamp 방지) + `hub-prometheus-research` (lesson distillation grounding) + `hub-longinus-reference` (MATERIALIZES sync).

**MT_SuccessBias 회피**: success 도 비자명한 경우 Lesson 으로 기록 (corrections 만 모이면 over-cautious).

# KG: hub-taliban-immunity, hub-prometheus-research, hub-longinus-reference, MIC_v1.AdversarialValidator, MIC_v1.ResearchProvider, MIC_v1.KgCodeBinder, lesson-agent-learns-from-verdict-not-success-2026-04-27

---

# KG: CONTRACT_Hardening_MetaReview, lesson-apt-scw-tdd-skipped-context-compression-2026-04-16

---

# /apt-meta-review — 피드백→스킬 강화 루프

> **APT의 5번째 Phase. 면역 시스템의 학습 사이클.**
> 의심이 들면 → 즉시 Lesson → SKILL 패치 → 검증.
> 이 루프가 없으면 APT는 같은 실수를 반복한다.

---

## 트리거 조건 (3가지 경로)

### 경로 A: 사용자 피드백
```
"제대로 한 거 맞아?" / "왤케 금방이야?" / "나생문 제대로 동작했어?"
→ apt-meta-review 즉시 발동
```

### 경로 B: SCW 완료 후 자동 제안
```
SCW 완료 시 항상 물음:
"이번 사이클에서 방법론 문서에 보완이 필요한 부분이 있었나요?"
→ YES → apt-meta-review 발동
→ NO → 종료
```

### 경로 C: Naesengmoon REJECTED 패턴
```
같은 렌즈에서 반복 REJECTED →
동일 Lesson 2번 이상 재등장 시 → SKILL.md에 구조적 결함 존재 → apt-meta-review 발동
```

---

## 종료조건 (무한 재귀 방지)

```
1. self_application_forbidden: MetaReview는 자기 자신(apt-meta-review/SKILL.md)에 재적용 금지
2. max_depth = 1: MetaReview 산출물이 다시 MetaReview를 트리거하면 차단
3. delta = 0: 새로운 Lesson이 생성되지 않으면 자동 종료
```

---

## 실행 절차

### Step 1: Lesson 즉시 기록

```cypher
MERGE (l:AbstractNode:Lesson {name: $lesson_name})
SET l.category = $category,
    l.problem = $problem,
    l.wrongAssumption = $wrong_assumption,
    l.truth = $truth,
    l.solution = null,
    l.severity = $severity,
    l.resolved = false,
    l.createdAt = datetime(),
    l.source = 'apt-meta-review'
RETURN l.name
```

### Step 2: 영향 스킬 식별

어떤 SKILL.md가 이 Lesson에 의해 수정돼야 하는가?

```cypher
MATCH (s:ClaudeCodeSkill)
WHERE s.skillName IN $affected_skills
RETURN s.skillName, s.file_path
```

### Step 3: SKILL.md 패치

Contract postcondition에 따라 구체적 방어 블록 삽입:
- **Naesengmoon** 계열 → Anti-Rubber-Stamp 섹션 강화
- **APT Phase** 계열 → 해당 Phase GATE CHECK 섹션 추가
- **Longinus** 계열 → MATERIALIZES 의무화 절차 추가

패치 형식:
```markdown
## ⛔ [결함명] 방어 (lesson-XXX)

> [무엇이 문제였는가]
> [어떻게 감지하는가]
> [어떻게 차단하는가]
```

### Step 4: MATERIALIZES KG 갱신

패치된 SKILL.md 파일 경로를 KG에 바인딩:

```cypher
MATCH (s:ClaudeCodeSkill {skillName: $skill_name})
MERGE (f:AbstractNode:SourceFile {name: $file_node_name})
SET f.file_path = $skill_md_path,
    f.language = 'markdown',
    f.updated_at = datetime()
MERGE (s)-[:MATERIALIZES]->(f)
RETURN s.skillName, f.file_path
```

### Step 5: Naesengmoon Gate (executor ≠ reviewer) — **inline parent execution 측 hard ban**

```
/taliban apt-meta-review 산출물 --lens constitutional
→ APPROVED: ValidationResult(phase='MetaReview', verdict='APPROVED') 기록
→ REJECTED: Finding 반영 후 Step 3으로 돌아가 재패치 (max_depth 카운터 확인)
```

**executor(패치 작성자) ≠ reviewer(Naesengmoon agent)** 원칙 엄수.

**Hard rule (`naesengmoon-canonical-2026-05-19` + `lesson-naesengmoon-inline-bypass-jaebaeman-sop-2026-05-19`)**:
- Parent Claude 측 inline self-judgment 측 **금지**. 반드시 separate subagent dispatch (`naesengmoon-ensemble-critic` agent OR canonical `/tlb` skill 측 SubagentTaskSpec seed 측 통한 dispatch).
- ValidationResult 측 record 측 `vr.executor != vr.reviewer` 측 D20 cypher 측 enforce. 같은 식별자 측 record 측 *automatic RUBBER_STAMP REJECTION*.

### Step 6: Lesson resolved 갱신

```cypher
MATCH (l:Lesson {name: $lesson_name})
SET l.resolved = true,
    l.resolvedAt = datetime(),
    l.resolvedBy = 'apt-meta-review: SKILL.md patch + MATERIALIZES link'
RETURN l.name, l.resolved
```

### Step 7: Mandatory Recursive Self-Meta-Naesengmoon (Wave 9 binding, P0-2 install 2026-05-20)

> Step 5 측 *retroactive* per-patch gate. Step 7 측 *recursive* sprint-end gate — *직후* cycle 측 self-meta-naesengmoon 측 dispatch. 두 측 별개 layer. **본 단계 측 skip 측 즉시 Constrain Layer (3) cypher gate fail (line 270-279).**

#### 7-1. Dispatch protocol (parent-claude only, NOT inline)

매 MetaReview cycle 종료 시 — parent Claude 측 다음 측 단일 메시지 측 dispatch:

```
Agent(subagent_type='naesengmoon-ensemble-critic',
      description='Wave 9 recursive self-meta-naesengmoon',
      prompt='Target = MetaReview output of cycle <cycle_id>.
              Cardinality=3 (constitutional + mathematical + solid simple 1:1).
              Builds on Step 5 retroactive gate VR.
              Output: ValidationResult MERGE + ≥1 AdversarialChallenge node emit.
              Constraint: this is sprint-end recursive verification, NOT
                          MetaReview→MetaReview self-application (self_application_forbidden).
              MetaReview→Naesengmoon 측 ALLOWED.')
```

**Hard rules**:
- Parent inline self-judgment **금지** (`lesson-naesengmoon-inline-bypass-jaebaeman-sop-2026-05-19`).
- Subagent agent != parent execution context (D20 separate).
- AdversarialChallenge node ≥1 emit mandatory (rubber-stamp 차단).

#### 7-2. AdversarialChallenge MERGE template

```cypher
MERGE (ac:AbstractNode:AdversarialChallenge {
  name: 'challenge-meta-review-' + $cycle_id + '-' + toString(timestamp())
})
SET ac.cycle_id = $cycle_id,
    ac.severity = $severity,                   -- HIGH | MEDIUM | LOW
    ac.status = 'OPEN',                        -- OPEN | RESOLVED | SUPERSEDED
    ac.challenge_summary = $summary,
    ac.kg_evidence_anchors = $evidence_list,   -- list of :Lesson / :ResearchFinding node names
    ac.lens_origin = $lens,                    -- constitutional | mathematical | solid
    ac.emitted_at = datetime()
WITH ac
MATCH (vr:ValidationResult {name: $naesengmoon_vr_name})
MERGE (vr)-[:RAISES]->(ac)
RETURN ac.name
```

#### 7-3. Russell self-application boundary (MATH-F2 stratification)

- MetaReview 측 자기 자체 측 *MetaReview→MetaReview* 측 ban (self_application_forbidden, `lesson-prom16-meta-bayes-self-application-2026-05-19` cross-ref).
- *MetaReview→Naesengmoon* 측 ALLOWED — *다른 무기 측 5무기 측 다른 instance* 측.
- Root MetaReview cycle (예: PROM 16 자체 측 emit 하는 정리) 측 *external sigma_oracle (사용자 verdict) gate* 측 추가 의존.

#### 7-4. Gate cypher (Constrain Layer 3 측 동일)

`constrain_layer_3_passed = false` 측 sprint end fail → immediate retro backfill required (자세한 cypher 측 line 270-279 참조).

---

## 피드백 루프 다이어그램

```
사용자 의심 / SCW 완료 / Naesengmoon 반복 REJECTED
          ↓
    apt-meta-review 트리거
          ↓
    Lesson 기록 (KG)
          ↓
    SKILL.md 패치 (파일)
          ↓
    MATERIALIZES 갱신 (KG↔파일 바인딩)
          ↓
    Naesengmoon Gate (executor≠reviewer)
          ↓
    APPROVED → Lesson resolved → 종료
    REJECTED → 재패치 (depth+1, delta 체크)
          ↓ (delta=0)
        종료
```

---

## What NOT To Do

| 금지 | 이유 |
|------|------|
| MetaReview를 자기 자신에 적용 | self_application_forbidden — 무한 루프 |
| Lesson 없이 SKILL 패치 | 근거 없는 수정 — KG 정본 위반 |
| executor가 Naesengmoon Gate 통과 선언 | VR Self-Fulfillment 위반 |
| delta=0인데 계속 실행 | 종료조건 위반 |
| max_depth 초과 후 계속 실행 | 무한 재귀 — 강제 종료 |

---

*MetaReview는 APT가 스스로를 개선하는 메커니즘이다.*
*이 루프가 없으면 방법론은 정적이고 결함은 누적된다.*
*# KG: APT_SkillHardening_v1, lesson-apt-scw-tdd-skipped-context-compression-2026-04-16*

---

## History

> Repo-level changes: [`/CHANGELOG.md`](../CHANGELOG.md). Per-commit: `git log -- apt-meta-review/SKILL.md`.

| Version | Date | Summary | KG Ref |
|---|---|---|---|
| **v2** | 2026-04-21 | APT v26 A6 alignment. SKILL.md 패치는 resolve_slot(ContractSchema/LensSet/MethodologyConfig) 패턴 유지. Prose magic number 주입 금지. KG = 정본. self_application_forbidden, max_depth=1, delta=0 종료조건 | `APT_v26_RFC_draft_2026-04-21`, `CONTRACT_Hardening_MetaReview`, `SPAN_Hardening_MetaReview` |
| **v1** | 2026-04 | Lesson → SKILL.md 패치 → MATERIALIZES 갱신 → Naesengmoon Gate. SCW 완료 후 자동 제안 | `APT_SkillHardening_v1`, `lesson-apt-scw-tdd-skipped-context-compression-2026-04-16` |

⚠️ **TDD REFACTOR phase 거울 부재** (cycle-level): apt-meta-review 만으로 *평면 누적 / fat file* 못 막음. atomic-span shipping 정규화 자체가 평면 누적 메커니즘. **Phase 6 (Cleanup Gate) 신설 필요** (`lesson-apt-phase6-cleanup-missing-2026-04-28`, HIGH, unresolved). meta-review 는 *방법론 메타-개선*, Phase 6 는 *cycle 차원 cleanup* — 보완 관계.

# KG history: ATOM_Skill_apt_meta_review / lesson-prom16-skill-versioning-academic-2026-04-29 / lesson-apt-phase6-cleanup-missing-2026-04-28 / lesson-solid-class-level-vs-package-level-mismatch-2026-04-29

---

## Constrain Layer (3) — Recursive Self-Meta-Naesengmoon (2026-05-20 Wave 9)

> *4번 연속 같은 형태 위반 (sha256 covenant skip + SOURCES.md MATERIALIZES gap + numeric drift + AdversarialChallenge 0건) 측 root cause* = Harness 4-axis 비대칭 (Inform overflow / Constrain near-zero / Verify retroactive only / Correct retroactive only). MetaReview 측 *retroactive Verify+Correct* 측만 측 — *next-cycle 측 같은 실수* 측 prevent 안 됨.

### Mandatory at sprint end (3 fields enforced)

매 cycle (SCW → MetaReview) 종료 시 측 다음 3 측 mandatory:

1. **Recursive self-meta-naesengmoon dispatch**: MetaReview 측 *자기 산출물* 측 측 — *직후 cycle* 측 *naesengmoon-ensemble-critic* 측 dispatch (`/tlb <MetaReview output> --lens constitutional --lens mathematical --lens solid`). *self_application_forbidden* 측 *MetaReview→MetaReview* 측 ban, *MetaReview→Naesengmoon* 측 ALLOWED (다른 5무기 측).

2. **AdversarialChallenge node ≥1 emit**: 모든 sprint-end ValidationResult 측 측 — `:AdversarialChallenge` node 측 ≥1 측 MERGE + `(vr)-[:RAISES]->(ac)` edge. 0건 측 *rubber-stamp suspicion 측 trigger* — Naesengmoon gate auto-reject.

3. **Numeric claim KG count match**: 보고 송신 전 측 — *수치 N 측 claim* 측 *KG cypher count* 측 *동시 fetch* + *reconcile field SET on sv.metric_breakdown*. drift 측 detect 시 *immediate report 정정*.

### Cypher gate (sprint end self-check)

```cypher
// At sprint end — verify mandatory 3 fields populated
MATCH (vr:ValidationResult) WHERE vr.cycle_id = $cycle_id
OPTIONAL MATCH (vr)-[:RAISES]->(ac:AdversarialChallenge)
OPTIONAL MATCH (mr:MetaReviewOutput {cycle_id: $cycle_id})-[:VALIDATED_BY]->(naesengmoon_vr:ValidationResult)
OPTIONAL MATCH (sv:SkillVersion {cycle_id: $cycle_id})
WHERE sv.last_numeric_reconciled_at IS NOT NULL
WITH vr, count(DISTINCT ac) AS challenge_count, count(DISTINCT naesengmoon_vr) AS recursive_count, count(DISTINCT sv) AS reconciled_count
RETURN vr.name, challenge_count, recursive_count, reconciled_count,
       (challenge_count >= 1 AND recursive_count >= 1 AND reconciled_count >= 1) AS constrain_layer_3_passed
```

`constrain_layer_3_passed = false` 측 — *sprint end gate fail* + *immediate retro emit* (3 mandatory 측 backfill).

### Composite gate (MVP cypher + Naesengmoon) — added 2026-05-25

> *Empirical finding (PROM 32 scoring framework cycle 2026-05-25):* LLM-as-judge alone (Naesengmoon) is **noisy single sample** (0.78 measured, ~0.90 estimated, Δ=0.12 inflation). Adding **deterministic cypher predicate gate** in parallel gives composite signal.

매 cycle 종료 시 **두 gate 다 PASS** mandatory:

1. **Naesengmoon semantic gate** (existing): `constrain_layer_3_passed` from above. LLM verdict + ≥1 AC + numeric reconcile.
2. **MVP cypher structural gate** (NEW): `mvp_score ≥ 0.6` from `/Users/lagyeongjun/CD/SYMPOSIUM/scripts/cycle_score_checker/predicates_v02_cycle_type_aware.cypher` (cycle-type aware: RESEARCH / REMEDIATION / IMPLEMENTATION / UNKNOWN branches).

**Composite verdict node** (MERGE at sprint end):
```cypher
MERGE (csv:CompositeScoreVerdict {name: 'csv-' + $cycle_id + '-' + toString(date())})
SET csv.cycle_id = $cycle_id,
    csv.mvp_score = $mvp_score, csv.mvp_gate = $mvp_gate,
    csv.llm_score = $naesengmoon_score, csv.llm_verdict = $naesengmoon_verdict,
    csv.composite_band = CASE
      WHEN $mvp_gate IN ['PASS','CONDITIONAL'] AND $naesengmoon_verdict IN ['APPROVED','CONDITIONAL_APPROVED'] THEN 'BOTH_PASS'
      WHEN $mvp_gate = 'FAIL' AND $naesengmoon_verdict IN ['APPROVED','CONDITIONAL_APPROVED'] THEN 'LLM_PASS_MVP_FAIL'
      WHEN $mvp_gate IN ['PASS','CONDITIONAL'] AND $naesengmoon_verdict NOT IN ['APPROVED','CONDITIONAL_APPROVED'] THEN 'MVP_PASS_LLM_FAIL'
      ELSE 'BOTH_FAIL'
    END
MERGE (csv)-[:CONFORMS_TO]->(schema:CompositeScoreVerdictSchema {name: 'composite-score-verdict-schema-v1-2026-05-25'})
```

**Why composite**:
- MVP cypher = structural compliance (KG schema). Deterministic (3 re-runs IDENTICAL). Catches structural gaps LLM misses.
- Naesengmoon = semantic quality. LLM judgment of methodology rightness. Catches conceptual gaps cypher misses.
- 5-cycle empirical 2026-05-25: MVP harsher than Naesengmoon mean Δ -0.12 → MVP catches gaps Naesengmoon obscured.
- META-Goodhart self-test: MVP scored *itself* (prom32 cycle) 0.6 — not self-flattering ✓.

# KG: cycle-prom32-scoring-framework-2026-05-25, lesson-scoring-framework-rigorous-predicate-based-2026-05-25, composite-score-verdict-schema-v1-2026-05-25

### Cross-reference

- Schema-level enforcement: `t_sourcecode_required_fields_not_null` APOC trigger (Constrain Layer 1)
- Numeric protocol: `/Users/lagyeongjun/CD/SYMPOSIUM/CLAUDE.md` §Constrain Layer (4)
- Root cause Lesson: `lesson-longinus-self-violated-sha256-covenant-recurrence-root-cause-2026-05-20`

# KG: lesson-longinus-self-violated-sha256-covenant-recurrence-root-cause-2026-05-20, ATOM_Skill_apt_meta_review, naesengmoon-canonical-2026-05-19
