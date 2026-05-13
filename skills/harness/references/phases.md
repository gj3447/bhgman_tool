# harness — Phases

> Lazy-load reference. Parent: [`../SKILL.md`](../SKILL.md).

## Diagnosis Phases

```
[harness-diagnostician <instance>]
   ↓
Phase 0: Pre-flight + instance identification
Phase 1: Tier identification (L_MC / L_RT / L_IDE)
Phase 2: 4-Axis scoring (Inform / Constrain / Verify / Correct)
Phase 3: Family-Relation Mirror position
Phase 4: Anti-Pattern detection (5 drift kind)
Phase 5: HarnessProfile crystallization
Phase 6: Lakatos test (PROGRESSIVE vs DEGENERATING)
Phase 7: Lesson candidate surface
   ↓
[Diagnosis report returned]
```

## Phase 0 — Pre-flight

**Inputs**: framework name, repo path, OR product description.
**External info**: WebSearch enabled (Anthropic docs / OpenAI docs / vendor blogs).

## Phase 1 — Tier Identification

**Decision**:
- Primary user = developer + IDE plugin → L_MC
- Primary user = agent system designer + framework → L_RT
- Primary user = infra engineer + cloud API → L_IDE
- Multi-tier sibling (Anthropic 3-tuple style) → 분해 진단

**Evidence**: 호스트 type, persistence model, pricing model.

## Phase 2 — 4-Axis Scoring

각 0-3:

| Axis | Score detection |
|------|----------------|
| Inform | RAG / KG retrieve / Progressive Disclosure 정도 |
| Constrain | hooks / permission / schema validation 정도 |
| Verify | tests / adversarial / ground truth 정도 |
| Correct | Lesson loop / re-execute / drift detection 정도 |

**Required**: score >= 2 면 evidence 인용 의무.

## Phase 3 — Family-Relation Mirror Position

| Tier | Position |
|------|----------|
| L_MC | apex (VerticalAxisHyperedge[1]) |
| L_RT | substrate ([2]) |
| L_IDE | end ([3]) |

Mirror STRONG: 비행기맨(#4) instance만. 다른 무기는 N/A 가능.

## Phase 4 — Anti-Pattern Detection

5 drift kind:
- HR_Family1to1: 한 instance 만 가지고 family 결정
- HR_TierConfusion: tier 잘못 분류
- HR_AxisMonopoly: 한 축만 강한 instance 평가
- HR_BockelerCitationDrift: 잘못된 출처
- HR_MCPRoleConfusion: MCP 를 framework 으로 분류

## Phase 5 — HarnessProfile Crystallization

```cypher
MERGE (h:HarnessProfile {name: 'harness-profile-' + $instance})
SET h.tier = $tier, h.inform_score = $i, h.constrain_score = $c,
    h.verify_score = $v, h.correct_score = $r,
    h.total_score = $i + $c + $v + $r,
    h.evidence_per_axis = $evidence,
    h.anti_patterns_detected = $aps,
    h.family_relation_position = $pos,
    h.diagnosed_at = datetime()
```

## Phase 6 — Lakatos Test

`lakatos-progressive-vs-rescue-test-canonical-2026-05-06` 4-criterion to family hypothesis (1:1 vs 1:N):

| Test | 1:1 vs 1:N |
|------|-----------|
| theory_laden_anomaly | 둘 다 인정 |
| independent_testable_consequence | 1:N 강함 (per-tier 책임) |
| excess_empirical_content | 1:N 강함 (sibling 발견) |
| principled_grounding_in_hard_core | 1:N 강함 (CHU 거울) |

→ default: PROGRESSIVE (1:N).

## Phase 7 — Lesson Candidate

각 anti-pattern → :Lesson 후보:
```cypher
MERGE (l:Lesson {name: 'lesson-harness-' + ap.kind + '-' + $instance})
SET l.wrongAssumption = ap.wrong, l.truth = ap.truth, l.howToApply = ap.how,
    l.evidence = ap.evidence, l.severity = ap.severity, l.resolved = false
```

## Comparison Mode (Multi-Instance)

```
harness-diagnostician comparison_mode [Cursor, Claude Code, Aider, Cline] (all L_MC)
```

**Output**:
- 4-axis comparison table
- best-in-class per axis
- collective anti-patterns

# KG: ATOM_Skill_harness, fw-harness-references-apt-parity-2026-05-06
