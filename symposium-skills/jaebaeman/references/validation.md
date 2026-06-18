# jaebaeman — Validation

> Lazy-load reference. Parent: [`../SKILL.md`](../SKILL.md). Sibling: [`./gates.md`](./gates.md).

## V1-V14 — Jaebaeman SOP Invariants

| V# | Target | Severity |
|----|--------|:--------:|
| V1 | SubagentTaskSpec exists for skill+phase | P1 |
| V2 | KG pre-fetch present (MCP 비상속 우회) | P1 (GH#13605) |
| V3 | Seed bundle 9-field complete | P1 |
| V4 | Single-message multi-call dispatch | P2 |
| V5 | intent_N == actual_N | P1 (GH#29181) |
| V6 | Every finding has dedup_hash | P1 |
| V7 | UNWIND single transaction (not N+1) | P1 |
| V8 | DispatchHyperedge.cardinality_match = true | P1 |
| V9 | provenance != 'inline' | P1 (TR11 mirror) |
| V10 | parent != subagent model | P2 |
| V11 | parallelism_min >= 1 | P3 |
| V12 | treasure_coverage_min >= 0.9 | P2 |
| V13 | W3C PROV provenance edges | P3 |
| V14 | subagent JSON valid schema | P2 |

## V5 Cypher (Self-Check Skip)

```cypher
MATCH (he:DispatchHyperedge)
WHERE he.cardinality <> he.actual_subagents
RETURN he.name, he.cardinality AS intent, he.actual_subagents AS actual,
       'GH#29181 / V5 violation: dispatch truncation' AS reason
```

## V8 Cypher (Cardinality Mismatch)

```cypher
MATCH (he:DispatchHyperedge)
OPTIONAL MATCH (he)<-[r:GENERATED_VIA]-(rf:ResearchFinding)
WITH he, count(r) AS edges
WHERE edges <> he.cardinality
RETURN he.name, edges, he.cardinality, 'V8 violation' AS reason
```

## Events

| Event | Payload | When |
|-------|---------|------|
| SeedResolved | `{spec_name, parallelism}` | G0 |
| KGPreFetched | `{cypher_results_count}` | G1 |
| SeedBundleConstructed | `{bundle_count, fields}` | G2 |
| DispatchSent | `{intent_N, model, type}` | G3 |
| SelfCheckPass | `{intent_N, actual_N, match}` | G4 |
| FindingsHarvested | `{count, schema_valid}` | G5 |
| DedupDetected | `{dups, conflicts}` | G6 |
| BatchWritten | `{nodes, transaction_id}` | G7 |
| HyperedgeReified | `{he_name, cardinality_match}` | G8 |

## TC

| # | Clarification |
|---|--------------|
| TC1 | 재배맨은 Wooldridge BDI agent 아님 — internal state 부재, KG seed = 외부 명세 |
| TC2 | 학문적 정확명: SOP (Subagent Orchestration Protocol). 한국어 alias 유지 |
| TC3 | MCP 자동 상속 가정은 GH#13605 violation — parent pre-fetch 필수 |
| TC4 | single-message multi-call 이 sequential 보다 SUB-OPTIMAL 회피 |
| TC5 | 4-archetype agents (facilitator/lead_link/rep_link/secretary) = SOP 4-stage 의 specialized worker |

# KG: ATOM_Skill_jaebaeman, fw-jaebaeman-references-apt-parity-2026-05-06
