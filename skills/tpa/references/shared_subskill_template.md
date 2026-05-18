<!-- KG: TASK_AS_TPA_SubSkill_SharedTemplate -->
<!-- KG: CONTRACT_SHARED_TPA_SubSkillTemplate -->
<!-- Placeholders: {{phase_id}} {{phase_num}} {{prev_phase}} {{mirror_apt}} {{mic_slots}} {{phase_body}} -->

# TPA Sub-Skill SharedTemplate

> **목적**: tpa-tcw/tt/tp/ta 4 sub-skill의 공통 6 섹션 template.
> SP-D7 depth lens 권고로 SharedType 추출. 각 sub-skill은 phase 고유 내용을 `{{phase_body}}` 슬롯에 주입.

---

## 섹션 1 — Frontmatter (YAML)

```yaml
---
name: tpa-{{phase_id}}
version: 0.4
description: >
  TPA {{phase_name}} ({{phase_id_upper}}) — Phase {{phase_num}}/4.
  APT {{mirror_apt}} 거울 (역순). {{one_line_purpose}}
  Gate Check Hook 강제. {{prev_phase_upper}} Gate 통과 없이 진입 불가.
  # KG: ATOM_Skill_tpa_{{phase_id}}, CONTRACT_tpa_{{phase_id}}, TPA_methodology_v04
---
```

## 섹션 2 — MIC Binding

```markdown
## 🔗 MIC Binding (SOLID-DIP)

**IS slot**: TPA_Phase ({{phase_id_upper}}, {{phase_num}}/4)
**USES slots**: {{mic_slots}}

\`\`\`cypher
MATCH (mic:MethodologyIntegrationContract {name:'MIC_v1'})-[:HAS_SLOT]->(s:MethodologySlot)
WHERE s.name IN {{mic_slots_list}}
RETURN s.name, s.currentConcrete, s.invocation
\`\`\`

# KG: MIC_v1, lesson-tpa-surface-scan-shortcut-2026-04-15
```

## 섹션 3 — Gate Check (Hook 강제)

```markdown
## ⛔ GATE CHECK (Hook 강제)

> `apt-gate-check.sh`가 자동 실행.
{{#if prev_phase}}
> **{{prev_phase_upper}} Gate 미통과 시 `permissionDecision: deny`.**
> BLOCKED 시: `/tpa-{{prev_phase}}` → `/taliban` → Gate 통과 → `/tpa-{{phase_id}}` 재호출.
{{else}}
> 본 스킬은 **시작 스킬(Phase 1/4)**이므로 pre-gate 없음.
> 종료시 {{phase_id_upper}} Gate 기록 필수 → 미기록 시 `/tpa-{{next_phase}}` 진입 차단.
{{/if}}

Cypher:
\`\`\`cypher
MATCH (exec:TPA_Execution)-[:HAS_VALIDATION]->(vr:ValidationResult {phase:'{{prev_phase_upper}}', verdict:'APPROVED'})
RETURN exec LIMIT 1
\`\`\`
```

## 섹션 4 — 진입 의식 (재배맨 첫 동작)

```markdown
## 진입 의식

\`\`\`cypher
MATCH (ts:SubagentTaskSpec {name:'taskspec-tpa-{{phase_id_upper}}', skill:'tpa'})
RETURN ts.checkItems, ts.cypherQueries, ts.expectedOutcome,
       ts.treasure_coverage_min, ts.parallelism_min
\`\`\`

**taskspec 조회 스킵 = 재배맨 bypass = gap02 재발**.
스킬 진입 최초 호출이어야 함.

{{phase_body}}  <!-- phase 고유 본문 삽입 지점 -->
```

## 섹션 5 — FulfillmentGate (7 checks)

```markdown
## FulfillmentGate {{phase_id_upper}} (7 checks)

1. [ ] {{phase_specific_check_1}}
2. [ ] {{phase_specific_check_2}}
3. [ ] {{phase_specific_check_3}}
4. [ ] taskspec.checkItems 전부 pass
5. [ ] treasure_coverage_min 만족
6. [ ] TPA_{{phase_id_upper}}_Result + PHASE_OUTPUT order={{phase_num}} 엣지
7. [ ] Longinus SourceBinding 생성 (해당 시)

하나라도 실패 → `status='INCOMPLETE'` 기록 후 중단.
```

## 섹션 6 — 종료 의식 (AdversarialValidator 자동)

```markdown
## 종료 의식 — Naesengmoon 9-lens

\`\`\`cypher
MATCH (s:MethodologySlot {name:'AdversarialValidator'})
RETURN s.invocation AS gate
-- {gate} TPA_{{phase_id_upper}}_<target>
\`\`\`

ValidationResult 기록:
\`\`\`cypher
MERGE (vr:ValidationResult {name:'VR_TPA_{{phase_id_upper}}_<target>_<date>', phase:'{{phase_id_upper}}'})
SET vr.verdict=$verdict, vr.evidence=[...], vr.validated_at=datetime(),
    vr.validator='Naesengmoon-9lens'
MATCH (exec:TPA_Execution)
MERGE (exec)-[:HAS_VALIDATION]->(vr)
\`\`\`

**APPROVED 아니면 `/tpa-{{next_phase}}` Gate Check에서 차단됨.**
```

---

## Placeholder 레퍼런스

| Placeholder | 의미 | 예시 (tcw) |
|---|---|---|
| `{{phase_id}}` | skill id suffix | `tcw` |
| `{{phase_id_upper}}` | 대문자 | `TCW` |
| `{{phase_num}}` | 1..4 | `1` |
| `{{prev_phase}}` | 이전 phase id (TCW는 없음) | `null` |
| `{{prev_phase_upper}}` | 이전 phase 대문자 | `""` |
| `{{next_phase}}` | 다음 phase id | `tt` |
| `{{mirror_apt}}` | 거울 APT 스킬 | `apt-scw` |
| `{{mic_slots}}` | 이 phase 가 사용하는 MIC slot 목록 | `SubagentSeeder, ResearchProvider, KgCodeBinder, AdversarialValidator` |
| `{{phase_name}}` | 사람 친화 이름 | `TargetCodeWorld` |
| `{{one_line_purpose}}` | 한 줄 목적 | `외부/레거시 코드에서 실제 존재하는 모든 것 기록` |
| `{{phase_body}}` | phase 고유 본문 (AST/Contract/Pattern/Anchor 로직) | 각 skill이 정의 |

## C(S) 5-predicate 검증

- ν: template 120줄, sub-skill당 rendered 300줄 (≤500) ✓
- τ: Markdown + YAML frontmatter + Cypher block 명시 ✓
- ι: `grep -c "^## " SKILL.md >= 6` 로 섹션 수 검증 ✓
- δ: 120줄 → 4회 재사용 = 실질 480줄 절약, merge diseconomy 없음 ✓
- σ: 공통 skeleton 단일 책임 ✓
