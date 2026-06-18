# jaebaeman — Seed FK 1:1 Invariant (SubagentTaskSpec.sourceId → AtomicSpan.name)

> Lazy-load reference. Parent: [`../SKILL.md`](../SKILL.md) §v2.2.
> Sibling: [`./theory.md`](./theory.md) (SOP grounding), [`./phases.md`](./phases.md) (4-stage), [`./validation.md`](./validation.md) (V1-V14).
> KG: `span-gap3-jaebaeman-seed-fk-2026-05-14`, `ATOM_Skill_jaebaeman`, `lesson-jaebaeman-rebrand-SOP-2026-05-05`.

---

## 0. 사용자 정전 (2026-05-14)

> 「기본 동작 단위는 재배맨이야 재배맨 단위가 span 이기도하고 ㅇㅇ; 재배맨 씨앗단위」

→ **SubagentTaskSpec (씨앗) 1개 = AtomicSpan 1개** 의 1:1 bijection.
→ 단위 정전: 씨앗 = atomic 작업 단위. 둘이 다르면 *어떤* 단위가 작업 단위인지 모호 → drift.

이 reference 는 위 정전을 KG schema 와 invariant Cypher 로 결정화한 정전.

---

## 1. SOP Grounding (Wooldridge BDI vs 재배맨)

재배맨은 Wooldridge BDI agent 가 아니다 (`lesson-jaebaeman-rebrand-SOP-2026-05-05`).

| Wooldridge BDI (1995) | 재배맨 SOP |
|---|---|
| Beliefs (internal state) | **부재** — KG seed 가 외부 명세 |
| Desires (goals) | **부재** — sourceId FK 가 명세 anchor |
| Intentions (plans) | **부재** — `taskRef` 가 plan |
| Reactive (env perceive) | **부재** — single-shot input |
| Persistent | **부재** — 1회 실행 후 종료 |

→ subagent 는 *내부 state* 가 없으므로 **외부 anchor (sourceId)** 가 정체성을 정의한다.
→ sourceId 가 `:AtomicSpan(name)` 에 FK 로 박혀야 *어떤 atomic 작업의 dispatch 인지* 추적 가능.
→ FK 깨지면 = 외부 anchor 손실 = subagent identity 손실 = SOP 위반.

---

## 2. Schema 정전 (재정리)

### 2-1. 9-field Seed Bundle (canonical core)

```cypher
(:SubagentTaskSpec {
  skill: String,                    // (1) 소속 스킬
  sourceId: String,                 // (2) FK → :AtomicSpan(name) when skill='apt-scw'
  displayName: String,              // (3) 사람 읽기용
  taskType: String,                 // (4) enum: research|validation|methodology-skill-edit|code-impl|...
  targetDomain: String,             // (5) 도메인
  expectedOutcome: String,          // (6) 산출물 형식 (Contract postcondition 거울)
  contractRef: String,              // (7) → :Contract(name)
  taskRef: String,                  // (8) → :SemanticTask(name)
  germinationMethod: String,        // (9) enum: consensus|conflict|singleton|manual|<custom>
  // Schema-mandatory NOT NULL (v2.4 §p3 trigger 강제):
  depth: Int,                       // [0,3] — root=0, fractal child=parent+1, hard limit 3
                                    //   t_depth_not_null apoc trigger → NULL = 50N00 rollback
  // Phase 옵션 (additive):
  status: String,                   // READY|DISPATCHED|COLLECTED|FAILED|ARCHIVED
  createdAt: DateTime,
  inputSchema: JSON,                // v2.1 MCP
  outputSchema: JSON,               // v2.1 MCP
  compensating_action: String,      // v2.1 Saga
  failure_mode: String              // best_effort|saga_compensate|2pc_abort
})
```

### 2-2. HAS_SEED Edge

```cypher
(a:AtomicSpan)-[:HAS_SEED {
  wave_index: Int,        // 재시도/wave 순서 (0..)
  status: String,         // seed.status 거울 (denormalized for fast scan)
  created_at: DateTime,
  cycle_id: String
}]->(s:SubagentTaskSpec)
```

### 2-3. FK target table

| `skill` | sourceLabel (FK target) | 비고 |
|---|---|---|
| `apt-scw` | **`:AtomicSpan`** | GAP-3 정전 (이 문서) |
| `apt-st` | `:CrystallizationFrontier` 또는 `:AtomicSpan` 집합 | ST 는 AtomicSpan *집합* anchor |
| `apt-sp` | `:Span` (non-atomic 포함) | SP 는 D(S) decomposition target |
| `prometheus` | `:Lesson` | sourceRF 보조 |
| `taliban` | `:Span` \| `:Contract` \| `:ResearchFinding` | 검증 target 다양 |
| `solve` | `:Lesson` | 문제 단위 |

→ **`apt-scw` 가 가장 strict 한 1:1 FK** (이 문서가 다루는 정전).
→ 다른 skill 은 FK target 이 더 넓지만 *반드시 명시* 되어야 함 (각 skill SKILL.md 또는 references 에).

---

## 3. Invariant 형식 정의

```
I_FK :   ∀ s:SubagentTaskSpec where s.skill = 'apt-scw'.
            ∃ a:AtomicSpan. a.name = s.sourceId                  -- existence (no orphan)

I_EDGE : ∀ s:SubagentTaskSpec where s.skill = 'apt-scw'.
            ∃! a:AtomicSpan. (a)-[:HAS_SEED]->(s)                -- edge materialization

I_BIJ :  ∀ a:AtomicSpan. ∃≤1 s:SubagentTaskSpec.
            s.skill = 'apt-scw' ∧ s.sourceId = a.name
            ∧ s.status ∈ {READY, DISPATCHED, COLLECTED}          -- 활성 1:1 (FAILED/ARCHIVED 제외)

I_FK ∧ I_EDGE ∧ I_BIJ ⟹  apt-scw 씨앗 단위 = AtomicSpan 단위
```

`I_BIJ` 가 *활성* seed 만 강제하는 이유: 재시도 시 이전 FAILED seed 는 archive 로 남기고 새 seed 를 활성화. wave_index 로 시간순 추적.

---

## 4. Worked Examples (3 case)

### Case 1: 정상 — 1:1 FK 성립

```cypher
// 1. AtomicSpan 먼저 존재
MERGE (a:AtomicSpan {name: 'span-gap3-jaebaeman-seed-fk-2026-05-14'})
SET a.objective = 'GAP-3 재배맨 Seed sourceId FK 1:1',
    a.c_s_predicate = true;

// 2. Seed 생성 (sourceId 가 AtomicSpan.name 매칭)
MERGE (s:SubagentTaskSpec {
  skill: 'apt-scw',
  sourceId: 'span-gap3-jaebaeman-seed-fk-2026-05-14'
})
SET s.displayName = 'GAP-3 재배맨 Seed sourceId FK 1:1',
    s.taskType = 'methodology-skill-edit',
    s.targetDomain = '재배맨 SOP + KG schema',
    s.expectedOutcome = 'SKILL.md schema 명시 + references 신규',
    s.germinationMethod = '1to1to1to1-dogfood-2026-05-14',
    s.depth = 0,                                 // ★ NOT NULL (v2.4 §p3 trigger)
    s.status = 'READY',
    s.createdAt = datetime();

// 3. HAS_SEED edge MERGE
MATCH (a:AtomicSpan {name: 'span-gap3-jaebaeman-seed-fk-2026-05-14'})
MATCH (s:SubagentTaskSpec {sourceId: a.name, skill: 'apt-scw'})
MERGE (a)-[e:HAS_SEED]->(s)
ON CREATE SET e.wave_index = 0, e.status = s.status,
              e.created_at = datetime(), e.cycle_id = 'apt-cycle-2026-05-14';
```

검증:
```cypher
MATCH (a:AtomicSpan {name: 'span-gap3-jaebaeman-seed-fk-2026-05-14'})-[:HAS_SEED]->(s)
RETURN a.name, s.sourceId, s.sourceId = a.name AS fk_ok;
// fk_ok = true ✓
```

### Case 2: OrphanSeed (E1) — FK target 부재

```cypher
// 잘못된 seed 생성: sourceId 가 존재하지 않는 AtomicSpan 이름
MERGE (s:SubagentTaskSpec {
  skill: 'apt-scw',
  sourceId: 'span-typo-doesnt-exist-2026-05-14'
})
SET s.status = 'READY', s.createdAt = datetime();
// ⚠ HAS_SEED edge 도 못 만듦 (target AtomicSpan 없음)
```

감지:
```cypher
MATCH (s:SubagentTaskSpec {skill: 'apt-scw'})
WHERE NOT EXISTS { MATCH (a:AtomicSpan {name: s.sourceId}) }
RETURN s.sourceId AS orphan_sourceId, s.displayName, s.status;
// → 'span-typo-doesnt-exist-2026-05-14' 반환
```

복구 옵션:
- (a) AtomicSpan 을 먼저 생성하면 정상화 (typo 가 아닌 경우)
- (b) seed 를 FAILED 마킹 + rejected_reason='OrphanSeed: sourceId references non-existent AtomicSpan' 후 archive

### Case 3: MultipleSeedPerAtomicSpan (E3) — 활성 seed 2+

```cypher
// 동일 AtomicSpan 에 활성 seed 2개 (실수로 dedup 못함)
MATCH (a:AtomicSpan {name: 'span-gap3-jaebaeman-seed-fk-2026-05-14'})
MERGE (s1:SubagentTaskSpec {name: 'seed-v1-2026-05-14T10'})
SET s1.sourceId = a.name, s1.skill = 'apt-scw', s1.status = 'COLLECTED';
MERGE (s2:SubagentTaskSpec {name: 'seed-v2-2026-05-14T11'})
SET s2.sourceId = a.name, s2.skill = 'apt-scw', s2.status = 'READY';
MERGE (a)-[:HAS_SEED {wave_index: 0}]->(s1);
MERGE (a)-[:HAS_SEED {wave_index: 1}]->(s2);
```

감지:
```cypher
MATCH (a:AtomicSpan)-[:HAS_SEED]->(s:SubagentTaskSpec {skill: 'apt-scw'})
WHERE s.status IN ['READY', 'DISPATCHED', 'COLLECTED']
WITH a, collect(s) AS active_seeds, count(s) AS n
WHERE n > 1
RETURN a.name, n, [x IN active_seeds | x.name + ':' + x.status] AS seeds;
```

복구: 가장 오래된 seed → ARCHIVED, 최신만 활성 유지.
```cypher
MATCH (a:AtomicSpan)-[:HAS_SEED]->(s:SubagentTaskSpec {skill: 'apt-scw'})
WHERE s.status IN ['READY', 'DISPATCHED', 'COLLECTED']
WITH a, s ORDER BY s.createdAt DESC
WITH a, collect(s) AS seeds
WHERE size(seeds) > 1
WITH a, seeds[0] AS keep, seeds[1..] AS demote
UNWIND demote AS d
SET d.status = 'ARCHIVED', d.rejected_reason = 'MultipleSeedPerAtomicSpan: superseded by ' + keep.name;
```

---

## 5. Backfill Migration (legacy nodes)

기존 SubagentTaskSpec 노드들 중 `sourceId` 가 비어있거나 `:AtomicSpan` 매칭 안 되는 경우 backfill.

### 5-1. Audit (현황 파악)

```cypher
// 전체 seed 분류
MATCH (s:SubagentTaskSpec)
WITH
  count(s) AS total,
  count(CASE WHEN s.sourceId IS NULL THEN 1 END) AS missing_sourceId,
  count(CASE WHEN s.sourceId IS NOT NULL AND s.skill = 'apt-scw' THEN 1 END) AS apt_scw_seeds
RETURN total, missing_sourceId, apt_scw_seeds;

// apt-scw seed 중 orphan
MATCH (s:SubagentTaskSpec {skill: 'apt-scw'})
WHERE s.sourceId IS NOT NULL
  AND NOT EXISTS { MATCH (a:AtomicSpan {name: s.sourceId}) }
RETURN s.name, s.sourceId, s.status;
```

### 5-2. HAS_SEED edge backfill (sourceId 는 맞는데 edge 부재)

```cypher
MATCH (s:SubagentTaskSpec {skill: 'apt-scw'})
WHERE s.sourceId IS NOT NULL
MATCH (a:AtomicSpan {name: s.sourceId})
WHERE NOT EXISTS { MATCH (a)-[:HAS_SEED]->(s) }
MERGE (a)-[e:HAS_SEED]->(s)
ON CREATE SET e.wave_index = 0,
              e.status = s.status,
              e.created_at = coalesce(s.createdAt, datetime()),
              e.cycle_id = 'backfill-2026-05-14';
```

### 5-3. sourceId 추론 (legacy seeds 중 sourceRF 만 있던 것)

```cypher
// v2.0 의 sourceRF (ResearchFinding ref) 가 있으면 그것을 임시로 sourceId 후보로
MATCH (s:SubagentTaskSpec {skill: 'apt-scw'})
WHERE s.sourceId IS NULL AND s.sourceRF IS NOT NULL
SET s.sourceId_legacy_candidate = s.sourceRF,
    s.needs_manual_fk_resolution = true;
// → 사람 검토 후 매뉴얼로 :AtomicSpan 매칭
```

### 5-4. Orphan archive (해소 불가)

```cypher
MATCH (s:SubagentTaskSpec {skill: 'apt-scw'})
WHERE NOT EXISTS { MATCH (a:AtomicSpan {name: s.sourceId}) }
  AND s.status IN ['READY', 'DISPATCHED']
SET s.status = 'ARCHIVED',
    s.rejected_reason = 'OrphanSeed backfill 2026-05-14: no matching AtomicSpan',
    s.archivedAt = datetime();
```

---

## 6. Drift 회피 — APT 다른 skill 과 일관성

| skill | 단위 정전 | sourceId FK target |
|---|---|---|
| `apt-sa` | SemanticAnchor 1개 = 1 cycle | `:SemanticAnchor` (loose) |
| `apt-sp` | Span 1개 = D(S) node | `:Span` (포괄, AtomicSpan 포함) |
| `apt-st` | Crystallization Frontier = AtomicSpan 집합 | `:AtomicSpan` (집합) |
| **`apt-scw`** | **AtomicSpan 1개 = seed 1개** | **`:AtomicSpan` (strict 1:1)** ★ |
| `apt-meta-review` | Lesson 1개 | `:Lesson` |

→ SCW 만 strict 1:1 인 이유: AtomicSpan 이 `C(S)` 5-predicate 통과한 *터미널* leaf 이고, 코드/문서 산출물 1개와 직접 대응. SP 의 non-atomic Span 은 추가 분해 가능하므로 1:1 강제 부적합.

---

## 7. 검증 체크리스트 (GAP-3 acceptance)

- [x] SKILL.md §v2.2 에 9-field bundle 표 + sourceId FK 명시
- [x] SKILL.md §v2.2 에 HAS_SEED edge schema (wave_index, status, cycle_id)
- [x] SKILL.md §v2.2 에 invariant Cypher 3종 (E1/E2/E3)
- [x] SKILL.md §v2.2 에 error variants 표 (E1/E2/E3 + 복구)
- [x] references/seed_fk_invariant.md (이 문서) — 3 worked example + backfill 마이그레이션
- [x] CLAUDE.md L11 "재배맨 = SOP" 와 일관 (Wooldridge BDI 정정 인용)

---

## 8. v2.4 amendment (2026-05-14) — depth NOT NULL p3 invariant

`SubagentTaskSpec.depth` 가 9-field 의 *additive option* 으로 분류돼 있었으나, 실제 KG (neo4j://data/neo4j-0) 측 apoc trigger `t_depth_not_null` 가 *모든* property assignment 에 `depth IS NULL` 차단을 enforce 한다 → **schema-mandatory 격상**. 상세: SKILL.md §v2.4.

검증:
```cypher
// p3 invariant Cypher (DB trigger 동일 source)
MATCH (s:SubagentTaskSpec) WHERE s.depth IS NULL
RETURN count(s) AS p3_violations;  // = 0 ⇒ I_DEPTH 성립
```

위 Case 1 의 정상 seed 도 v2.4 패치 후 `s.depth = 0` 명시 추가. 모든 worked example (Case 1/2/3) 의 MERGE 절은 v2.4 부터 depth field 가 *생략 불가*.

---

# KG: ATOM_Skill_jaebaeman, span-gap3-jaebaeman-seed-fk-2026-05-14, lesson-jaebaeman-rebrand-SOP-2026-05-05, lesson-jaebaeman-depth-invariant-2026-05-14, 재배맨-v2-subagent-runtime-protocol
