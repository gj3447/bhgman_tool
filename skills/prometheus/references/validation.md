# prometheus — Validation

> Lazy-load reference. Parent: [`../SKILL.md`](../SKILL.md).

## V1-V14 — Prometheus Cycle Invariants

| V# | Target | Severity |
|----|--------|:--------:|
| V1 | KG Pre-fetch present (G1) | P1 |
| V2 | Axis Matrix N completeness | P1 (PR_AxisIncompleteness) |
| V3 | dedup_hash on every finding | P1 (PR_DedupSkipped) |
| V4 | Single-message multi-call (parallel) | P2 |
| V5 | intent_N == actual_N (GH#29181) | P1 (PR_DispatchTruncation) |
| V6 | FullFindingRecord schema valid | P1 |
| V7 | Lakatos 4-criterion test passed | P1 |
| V8 | Filesystem dispersion gate (G6.5) | P1 (PR_DispersionGateBypass) |
| V9 | UNWIND batch (not N+1) | P2 |
| V10 | DispatchHyperedge cardinality match | P2 |
| V11 | Lesson wrongAssumption ↔ truth pair complete | P1 (PR_LessonPairIncomplete) |
| V12 | INSTANCE_OF_FEEDBACK_LOOP edge | P2 |
| V13 | hot-fix override has human-supplied reason | P1 (PR_KGSkipWithoutJustification) |
| V14 | N >= default for problem size | P3 (PR_NUndersampling) |

## V11 Cypher (Lesson Pair Incomplete)

```cypher
MATCH (l:Lesson) WHERE l.scope STARTS WITH 'prom-'
  AND (l.wrongAssumption IS NULL OR l.truth IS NULL)
RETURN l.name AS incomplete_lesson, 'V11 / PR_LessonPairIncomplete' AS reason
```

## Events

| Event | Payload | When |
|-------|---------|------|
| CycleStarted | `{cycle_id, topic, N, size}` | G0 |
| AxisMatrixGenerated | `{matrix, axes, sub_axes}` | G2 |
| KnowledgeScanCompleted | `{prior_findings, dispersion_drift}` | G3 |
| DispatchSent | `{intent_N, model, type}` | G4 |
| FindingsCollected | `{count, dedup_collisions}` | G5 |
| LakatosVerdict | `{cycle, classification}` | G6 |
| DispersionChecked | `{drift_count, kg_fs_match}` | G6.5 |
| BatchWritten | `{nodes, hyperedge}` | G7 |
| LessonsCrystallized | `{count, severity_distribution}` | G7.5 |

## TC

| # | Clarification |
|---|--------------|
| TC1 | Hegel reframe — KG-first 가 단방향 아님 (thesis 자가운동) |
| TC2 | hot-fix latency-critical 만 KG-skip 허용 (justification 의무) |
| TC3 | DEGENERATING verdict 도 KG 결정화 (rescue 가설 분류) |
| TC4 | BX PutPut 충돌 시 자동 머지 회피 (sigma_oracle) |
| TC5 | N=4 default 는 small problem 만 — TOE 급은 N=64-100 |

# KG: ATOM_Skill_prometheus, fw-prometheus-references-apt-parity-2026-05-06
