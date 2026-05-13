---
name: apt-meta-review
kg_ref: ATOM_Skill_apt_meta_review
version: "27.1.0"
channel: stable
description: >
  APT MetaReview Phase (5/5) — 의심/피드백을 자동으로 스킬 강화로 이어지는 피드백 루프.
  SCW 완료 후 자동 제안. Lesson 생성 → SKILL.md 패치 → MATERIALIZES 갱신 → Taliban Gate.
  v2 (APT v26 A6 alignment): SKILL.md 패치는 resolve_slot(ContractSchema|LensSet|MethodologyConfig) 패턴 유지. Prose magic number 주입 금지. KG = 정본.
  종료조건: self_application_forbidden, max_depth=1, delta=0.
  # KG: ATOM_Skill_apt_meta_review, CONTRACT_Hardening_MetaReview, SPAN_Hardening_MetaReview, APT_v26_RFC_draft_2026-04-21, MIC_v1.ReasoningProtocol→KGFirstCheck_v1 (R1-R5 mandatory before any framing/diagnostic, lesson-ai-skipped-kg-check-before-framing-2026-04-29)
---

## 🎛 v26 A6 Resolve-Only

> SKILL.md 패치 시 prose hardcoding 금지. KG slot 참조만. magic number/lens count 주입 시 Taliban reject.

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
**USES slots**: AdversarialValidator (Taliban Gate 자체재검증), KgCodeBinder (Longinus MATERIALIZES 갱신), SubagentSeeder (재배맨 taskspec, Lesson 생성 자동화)

**동적 resolution**:
```cypher
MATCH (mic:MethodologyIntegrationContract {name:'MIC_v1'})-[:HAS_SLOT]->(s:MethodologySlot)
WHERE s.name IN ['AdversarialValidator','KgCodeBinder','SubagentSeeder']
RETURN s.name, s.currentConcrete, s.invocation
```

본문의 `Taliban`/`Longinus`/`재배맨`은 MIC slot 현재 스냅샷. 진짜 호출은 `s.invocation`.
**Self-application 금지**: MetaReview가 자기 자신을 다시 MetaReview하면 무한루프. `max_depth=1, delta=0` 경계 준수.

# KG: MIC_v1, ATOM_Skill_apt_meta_review, lesson-apt-skill-drift-audit-2026-04-17

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
"제대로 한 거 맞아?" / "왤케 금방이야?" / "탈레반 제대로 동작했어?"
→ apt-meta-review 즉시 발동
```

### 경로 B: SCW 완료 후 자동 제안
```
SCW 완료 시 항상 물음:
"이번 사이클에서 방법론 문서에 보완이 필요한 부분이 있었나요?"
→ YES → apt-meta-review 발동
→ NO → 종료
```

### 경로 C: Taliban REJECTED 패턴
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
- **Taliban** 계열 → Anti-Rubber-Stamp 섹션 강화
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

### Step 5: Taliban Gate (executor ≠ reviewer)

```
/taliban apt-meta-review 산출물 --lens constitutional
→ APPROVED: ValidationResult(phase='MetaReview', verdict='APPROVED') 기록
→ REJECTED: Finding 반영 후 Step 3으로 돌아가 재패치 (max_depth 카운터 확인)
```

**executor(패치 작성자) ≠ reviewer(Taliban agent)** 원칙 엄수.

### Step 6: Lesson resolved 갱신

```cypher
MATCH (l:Lesson {name: $lesson_name})
SET l.resolved = true,
    l.resolvedAt = datetime(),
    l.resolvedBy = 'apt-meta-review: SKILL.md patch + MATERIALIZES link'
RETURN l.name, l.resolved
```

---

## 피드백 루프 다이어그램

```
사용자 의심 / SCW 완료 / Taliban 반복 REJECTED
          ↓
    apt-meta-review 트리거
          ↓
    Lesson 기록 (KG)
          ↓
    SKILL.md 패치 (파일)
          ↓
    MATERIALIZES 갱신 (KG↔파일 바인딩)
          ↓
    Taliban Gate (executor≠reviewer)
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
| executor가 Taliban Gate 통과 선언 | VR Self-Fulfillment 위반 |
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
| **v1** | 2026-04 | Lesson → SKILL.md 패치 → MATERIALIZES 갱신 → Taliban Gate. SCW 완료 후 자동 제안 | `APT_SkillHardening_v1`, `lesson-apt-scw-tdd-skipped-context-compression-2026-04-16` |

⚠️ **TDD REFACTOR phase 거울 부재** (cycle-level): apt-meta-review 만으로 *평면 누적 / fat file* 못 막음. atomic-span shipping 정규화 자체가 평면 누적 메커니즘. **Phase 6 (Cleanup Gate) 신설 필요** (`lesson-apt-phase6-cleanup-missing-2026-04-28`, HIGH, unresolved). meta-review 는 *방법론 메타-개선*, Phase 6 는 *cycle 차원 cleanup* — 보완 관계.

# KG history: ATOM_Skill_apt_meta_review / lesson-prom16-skill-versioning-academic-2026-04-29 / lesson-apt-phase6-cleanup-missing-2026-04-28 / lesson-solid-class-level-vs-package-level-mismatch-2026-04-29
