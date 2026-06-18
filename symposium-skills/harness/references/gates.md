# harness — Gates

> Lazy-load reference. Parent: [`../SKILL.md`](../SKILL.md). Sibling: [`./theory.md`](./theory.md).
> KG: `harness-grounding`, `family-expansion-pattern-canonical-2026-04-30`.

---

## 1. Diagnosis Gates Sequence

```
[/harness <instance_or_framework>]
   ↓
G0: Pre-flight  — instance/framework 식별
   ↓
G1: Tier Identification  — L_MC / L_RT / L_IDE 결정
   ↓
G2: 4-Axis Score  — Inform / Constrain / Verify / Correct
   ↓
G3: Family-Relation Mirror Position  — apex / substrate / end
   ↓
G4: Anti-Pattern Detection  — 5 drift kind
   ↓
G5: HarnessProfile Crystallization  — KG 결정화
   ↓
G6: Lakatos Test  — PROGRESSIVE vs DEGENERATING
   ↓
G7: Lesson Candidate Surface  — improvement actions
   ↓
[Diagnosis report returned]
```

---

## 2. G0 Pre-flight

**Required**:
- instance 가 식별 가능 (framework name OR repo path OR product description)
- 외부 정보 접근 가능 (WebSearch / docs)
- `MIC_v1.Harness` slot 정의 (currentConcrete = Harness)

---

## 3. G1 Tier Identification Gate

**Decision tree**:
```
Q1: Primary user = developer?
  YES → Q2: IDE plugin / CLI?
    YES → L_MC (IDE-host coding harness)
    NO  → L_RT 가능성
  NO → Q3: agent system designer 또는 infra engineer?
    designer → L_RT (application agent runtime)
    infra    → L_IDE (managed cloud)
```

**Evidence required**:
- 호스트 type (IDE / CLI / Cloud API)
- Persistence model (session-scoped vs durable agents)
- Pricing model (per-seat / per-API-call / managed-infra)

**On fail**: tier 결정 불가 → multi-tier sibling family 가능성 (Anthropic 3-tuple 같이 한 진영이 여러 tier cover)

---

## 4. G2 4-Axis Score Gate (각 0-3)

| 축 | Score 0 | Score 1 | Score 2 | Score 3 |
|----|---------|---------|---------|---------|
| **Inform** | 정보 주입 메커니즘 없음 | basic context window only | RAG / KG retrieve | Progressive Disclosure + KG-first |
| **Constrain** | 제약 없음 | basic permission denylist | hooks + schema validation | full PreToolUse + tool whitelist + dynamic context |
| **Verify** | 검증 없음 | basic linting/tests | adversarial gate | ground truth (compiler+test+adversarial+sigma_oracle) |
| **Correct** | feedback 없음 | manual user feedback | Lesson loop | Lesson → ActionPlan → re-execute + drift detection |

**Evidence per score**:
- 각 axis 점수에 cited evidence (docs / source code / public comments)
- `score >= 2` 는 *evidence 인용 의무* (Anti-Rubber-Stamp mirror)

**On fail**: evidence 없는 점수 = 추측 → BLOCK + 더 자세한 조사 (Prometheus 호출).

---

## 5. G3 Family-Relation Mirror Position Gate

```cypher
MATCH (h:HarnessProfile {name: $profile})
WITH h, h.tier AS t
RETURN h.name,
  CASE t
    WHEN 'L_MC' THEN 'apex (VerticalAxisHyperedge[1] in {#4,#8,#10})'
    WHEN 'L_RT' THEN 'substrate (VerticalAxisHyperedge[2])'
    WHEN 'L_IDE' THEN 'end (VerticalAxisHyperedge[3])'
    ELSE 'unknown'
  END AS mirror_position
```

**Required (Mirror STRONG)**:
- `responsibility_split = true` (apex/substrate/end 명확 분리)
- `cardinality_match = true` (3-tier 가 hyperedge 3-vertex 와 1:1)

**Lakatos**: Mirror STRONG 입증 시 PROGRESSIVE evidence (1:N family hypothesis 가 1:1 보다 강함).

KG: `family-relation-mirror-hypothesis-2026-04-30`.

---

## 6. G4 Anti-Pattern Detection Gate (5 drift kind)

| # | Drift | 검출 | 처방 |
|---|-------|------|------|
| HR_Family1to1 | 한 instance 만 있고 다른 tier 검토 안 함 | sibling list 확인 | 다른 tier instance 추가 검토 |
| HR_TierConfusion | L_RT framework를 L_MC라고 분류 | responsibility boundary 재확인 | tier reclassify |
| HR_AxisMonopoly | 한 축만 강한 instance 를 "강한 harness"로 평가 | 4-axis distribution skew check | 4축 모두 검사 |
| HR_BockelerCitationDrift | "Böckeler 2018" 같은 존재하지 않는 출처 | citation grep | family-expansion-pattern-canonical-2026-04-30 만 정전 사용 |
| HR_MCPRoleConfusion | MCP 를 framework 로 분류 | 어댑터 vs framework 구분 | MCP = adapter (호스트 책임 정반대) |

**On fail**: drift kind 발견 → :Lesson 후보 결정.

---

## 7. G5 HarnessProfile Crystallization Gate

```cypher
MERGE (h:HarnessProfile:AbstractNode {name: 'harness-profile-' + $instance})
SET h.tier = $tier,
    h.tier_evidence = $tier_ev,
    h.inform_score = $inform,
    h.constrain_score = $constrain,
    h.verify_score = $verify,
    h.correct_score = $correct,
    h.total_score = $inform + $constrain + $verify + $correct,
    h.evidence_per_axis = $axis_evidence,
    h.anti_patterns_detected = $anti_pat_list,
    h.family_relation_position = $position,
    h.diagnosed_at = datetime(),
    h.diagnosed_by = 'harness-diagnostician'
```

**Required**:
- 모든 4 축 점수 + evidence
- tier + position
- anti_patterns 검사 결과 (empty OR list)

---

## 8. G6 Lakatos Test Gate

`lakatos-progressive-vs-rescue-test-canonical-2026-05-06` 4-criterion 적용 to family hypothesis:

| Test | 1:1 hypothesis | 1:N hypothesis (Harness 정전) |
|------|----------------|-------------------------------|
| theory_laden_anomaly | 인정 | 인정 |
| independent_testable_consequence | 약함 | 강함 (각 tier 별 책임 분리 검증 가능) |
| excess_empirical_content | 적음 | 많음 (Anthropic 3-tuple sibling 발견) |
| principled_grounding_in_hard_core | 약함 | 강함 (CHU 공리 거울) |

**On fail**: 4-criterion 검사 결과 1:1 hypothesis 가 더 강함 → harness profile 자체 재조사 필요.

---

## 9. G7 Lesson Candidate Gate

```cypher
UNWIND $anti_patterns AS ap
MERGE (l:Lesson:AbstractNode {name: 'lesson-harness-' + ap.kind + '-' + $instance})
SET l.scope = 'harness-diagnosis',
    l.problem = ap.description,
    l.wrongAssumption = ap.wrong_assumption,
    l.truth = ap.truth,
    l.howToApply = ap.how_to_apply,
    l.severity = ap.severity,
    l.evidence = ap.evidence,
    l.resolved = false,
    l.target_instance = $instance,
    l.created_at = datetime()
WITH l
MATCH (fl:FeedbackLoopOntology {name:'agent-feedback-loop-canonical-2026-04-27'})
MERGE (l)-[:INSTANCE_OF_FEEDBACK_LOOP]->(fl)
```

**Required**: wrongAssumption ↔ truth pair complete.

---

## 10. Multi-Instance Comparison Mode

여러 instance 동시 진단 가능:
```
Use harness-diagnostician with instances=[Cursor, Claude Code, Aider, Cline] all L_MC
```

**Output**: comparison table:
- 4-axis score per instance
- tier consistency check
- best-in-class per axis
- collective anti-patterns

---

## 11. References

- theory: `./theory.md`
- skill: `../SKILL.md`
- 정전: `THEORY/00_공통/세계관_정전.md §5-C` (3-tier table + MCP + Anthropic 3-tuple)
- agent: `SYMPOSIUM/.claude/agents/harness-diagnostician.md`
- KG: `family-expansion-pattern-canonical-2026-04-30`, `family-relation-mirror-hypothesis-2026-04-30`, `lakatos-progressive-vs-rescue-test-canonical-2026-05-06`, `lesson-harness-drift-corrected-2026-04-29`, `lesson-harness-citation-drift-bockeler-2026-04-30`

# KG: ATOM_Skill_harness, fw-harness-references-apt-parity-2026-05-06
