# harness — Validation

> Lazy-load reference. Parent: [`../SKILL.md`](../SKILL.md). Sibling: [`./gates.md`](./gates.md).

## V1-V10 — Harness Diagnosis Invariants

| V# | Target | Severity |
|----|--------|:--------:|
| V1 | HarnessProfile.tier ∈ {L_MC, L_RT, L_IDE} | P1 |
| V2 | All 4-axis scores set (0-3) | P1 |
| V3 | tier_evidence non-empty | P1 |
| V4 | evidence_per_axis cited (score >= 2 mandatory) | P1 |
| V5 | family_relation_position ∈ {apex, substrate, end, none} | P2 |
| V6 | anti_patterns_detected list (empty OK) | P2 |
| V7 | citation 출처 정확 (Bockeler drift 차단) | P1 (HR_BockelerCitationDrift) |
| V8 | tier sibling family 검토 (1:1 drift 차단) | P2 |
| V9 | MCP 가 framework 가 아닌 adapter 로 분류 | P2 |
| V10 | Lakatos 4-criterion 통과 (1:N hypothesis) | P2 |

## V1 Cypher

```cypher
MATCH (h:HarnessProfile) WHERE h.tier NOT IN ['L_MC','L_RT','L_IDE']
RETURN h.name AS invalid_tier, h.tier AS got, 'V1 violation' AS reason
```

## V4 Cypher (Evidence-Free Scoring)

```cypher
MATCH (h:HarnessProfile)
WHERE (h.inform_score >= 2 AND h.evidence_inform IS NULL)
   OR (h.constrain_score >= 2 AND h.evidence_constrain IS NULL)
   OR (h.verify_score >= 2 AND h.evidence_verify IS NULL)
   OR (h.correct_score >= 2 AND h.evidence_correct IS NULL)
RETURN h.name AS unfounded_score, 'V4 violation' AS reason
```

## Events

| Event | Payload | When |
|-------|---------|------|
| TierIdentified | `{instance, tier, evidence}` | G1 |
| AxisScored | `{instance, axis, score, evidence}` | G2 |
| AntiPatternDetected | `{instance, pattern, severity}` | G4 |
| HarnessProfileCrystallized | `{profile, total_score}` | G5 |
| LakatosTest | `{profile, classification}` | G6 |
| MultiInstanceCompared | `{instances[], comparison_table}` | comparison mode |

## TC

| # | Clarification |
|---|--------------|
| TC1 | family-as-1:1 drift 가 default — 진단 시 actively 1:N 가설 사용 |
| TC2 | 4축 score 절대값 보다 distribution 이 중요 (한 축 monopoly 의심) |
| TC3 | MCP 는 framework 아님 — adapter (호스트 책임 정반대) |
| TC4 | Bockeler 출처 사용 시 = citation drift (lesson-harness-citation-drift-bockeler-2026-04-30 참조) |
| TC5 | family-relation mirror 는 비행기맨(#4) 만 STRONG — 다른 무기는 N/A 가능 |

# KG: ATOM_Skill_harness, fw-harness-references-apt-parity-2026-05-06
