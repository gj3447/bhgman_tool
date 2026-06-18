# longinus — Validation

> Lazy-load reference. Parent: [`../SKILL.md`](../SKILL.md). Sibling: [`./gates.md`](./gates.md).

## V1-V14 — Longinus Binding Invariants

| V# | Target | Severity |
|----|--------|:--------:|
| V1 | Every Contract has ReferenceSite | P1 (TR12 mirror) |
| V2 | ReferenceSite.l4_file_line set | P1 |
| V3 | parsed_with != 'grep' | P1 (TR4 mirror) |
| V4 | manifest = union(harvested_files) | P1 (TR5 mirror) |
| V5 | l6_sha256 baseline set | P2 |
| V6 | SHA256 baseline_at age <= 7 days | P2 |
| V7 | drift coverage_ratio >= 0.8 OR SUSPENDED | P1 |
| V8 | reverse orphan ratio < 0.2 | P2 |
| V9 | BX law violations resolved | P2 |
| V10 | DriftReport has all 5 kinds | P2 |
| V11 | crate-script L7 binding present | P3 |
| V12 | directory aggregator marked DIRECTORY_SKIP | P3 |
| V13 | layer_completeness >= 4 layers | P3 |
| V14 | sha256 daemon last_run < 2 hours ago | P3 |

## V1 Cypher (Longinus Binding Missing)

```cypher
MATCH (c) WHERE c:AptContract OR c:ConventionalContract
WHERE NOT EXISTS { MATCH (c)-[:BOUND_TO]->(:ReferenceSite) }
RETURN c.name AS unbound_contract, 'TR12 / V1 violation' AS reason
```

## V7 Cypher (Drift Silenced)

```cypher
MATCH (drift:DriftReport)
WHERE drift.coverage_ratio < 0.8
OPTIONAL MATCH (drift)<-[:HAS_DRIFT_REPORT]-(:TPA_Execution)-[:ANCHORS_TO]->(sa:SemanticAnchor)
WHERE sa.status <> 'SUSPENDED'
RETURN drift.name, sa.name, sa.status, 'V7 violation: drift unsuppressed' AS reason
```

## Events

| Event | Payload | When |
|-------|---------|------|
| BindingCreated | `{contract, ref_site, file_line}` | G4 |
| SHA256BaselineEstablished | `{ref_site, hash, baseline_at}` | G5 |
| DriftDetected | `{ref_site, kind, baseline, current}` | daemon scan |
| ReverseOrphanFound | `{symbol, file_line}` | G8 |
| BXLawViolation | `{ref_site, law, evidence}` | G6 |
| AnchorSuspended | `{anchor, coverage_ratio, threshold}` | TPA TA gate |

## TC

| # | Clarification |
|---|--------------|
| TC1 | Directory 는 sha256 미적용 (DIRECTORY_SKIP) — 빈 hash 가 아니라 type 표시 |
| TC2 | Reverse orphan 은 *drift* 가 아니라 *recovery 누락* (lesson 후보) |
| TC3 | BX PutPut 은 거의 항상 sigma_oracle 결정 — 자동 머지 위험 |
| TC4 | sha256 daemon 은 production 측 (launchd 1h) — dev 측은 manual |
| TC5 | L7 (crate/script) 는 v3.1 신규 — 기존 ReferenceSite 는 nullable |

# KG: ATOM_Skill_longinus, fw-longinus-references-apt-parity-2026-05-06
