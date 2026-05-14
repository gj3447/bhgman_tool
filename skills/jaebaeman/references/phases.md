# jaebaeman — Phases

> Lazy-load reference. Parent: [`../SKILL.md`](../SKILL.md).

## SOP 4-Stage Phases (Holacracy mirror)

```
[parent Claude — multi-agent dispatch decision]
   ↓
Phase 1 (Seed): facilitator archetype
   Stage G0-G2: SubagentTaskSpec resolution + KG pre-fetch + seed_bundle
   ↓
Phase 2 (Dispatch): lead_link archetype
   Stage G3-G4: single-message multi-call + GH#29181 self-check
   ↓
Phase 3 (Collect): rep_link archetype
   Stage G5-G6: FullFindingRecord harvest + dedup detection
   ↓
Phase 4 (Write): secretary archetype
   Stage G7-G8: UNWIND batch + Hyperedge reification
   ↓
[Subagents 종료, parent 만 살아남음]
```

## Phase 1 — Seed (facilitator)

**책무**:
1. SubagentTaskSpec 조회 (skill + phase 매칭)
2. KG pre-fetch (parent 측, MCP 우회 GH#13605)
3. seed_bundle 9-field 생성

**Output**: N seed_bundles ready for dispatch.

**Holacracy mirror**: facilitator 가 cycle 의식 진입 + invariants 적용.

## Phase 2 — Dispatch (lead_link)

**책무**:
1. single-message multi-call 패턴으로 N agents spawn
2. 각 Agent call 에 seed_bundle 주입
3. 모든 dispatch 완료 후 self-check (intent_N == actual_N, GH#29181)

**Pattern**:
```python
# 모두 같은 message — Anthropic Agent tool 은 (model, run_in_background, prompt) 3 param 만 받음.
# subagent_type / isolation / archetype 등은 KG metadata (HAS_SEED edge / DispatchHyperedge.subagent_type) 만 박힘,
# tool param 으로 전달 금지 (PROM_16 E2.1 finding, runtime fail 잠재).
[
  Agent(
    model = MODEL_MAP[sb.model],            # 'haiku' → 'claude-haiku-4-5-20251001' 등 full ID 매핑
    run_in_background = True,                # N>1 병렬
    prompt = sb.assembled_prompt             # 3줄 + pre-fetch context (SKILL.md §Phase 2.2)
  )
  for sb in seed_bundles
]
intent_N = len(seed_bundles)
results = await all_complete()
actual_N = len(results)
assert intent_N == actual_N
```

**Tool Param Binding Invariant**: `subagent_type` (archetype 분기) 는 *부모 측 prompt 조립* 단계에서 KG 조회로 풀어 prompt 본문에 녹여 넣음. Agent tool 시그니처에 직접 전달하면 InputValidationError. KG metadata-only fields → §SKILL.md v2.3 참조.

**Holacracy mirror**: lead_link 가 N circle role 동시 energizing.

## Phase 3 — Collect (rep_link)

**책무**:
1. 각 subagent 의 JSON result 수확
2. FullFindingRecord schema 검증
3. dedup_hash 계산 + 충돌 검출 (Step 3.3)

**Schema validation**:
- agent_id present
- claim non-empty
- evidence non-empty
- confidence 0.0-1.0
- provenance 형식 'subagent-...'

**Holacracy mirror**: rep_link 가 sub-circle 정보를 outer circle 에 보고.

## Phase 4 — Write (secretary)

**책무**:
1. UNWIND single transaction batch merge
2. DispatchHyperedge reification (cardinality_match)
3. W3C PROV provenance edges
4. Lesson 자동 (모든 발견)

**Pattern**:
```cypher
UNWIND $batch AS row
MERGE (rf:ResearchFinding {name: row.name})
SET rf += row.props
MERGE (rf)-[:GENERATED_VIA]->(:DispatchHyperedge {name: $he})
MERGE (rf)-[:wasGeneratedBy]->(:prov_Activity {name: $cycle_id})
```

**Holacracy mirror**: secretary 가 governance record-keeping (KG = governance log).

## Phase Detection Auto-Route

```cypher
MATCH (he:DispatchHyperedge {name: $hyperedge})
OPTIONAL MATCH (he)<-[:GENERATED_VIA]-(rf:ResearchFinding)
WITH he, count(rf) AS findings_count
RETURN he.name,
  CASE
    WHEN he.cardinality_match = true AND findings_count > 0 THEN 'COMPLETE'
    WHEN findings_count > 0 THEN 'Phase 4: Write (cardinality mismatch)'
    WHEN he.actual_subagents > 0 THEN 'Phase 3: Collect'
    WHEN he.cardinality > 0 THEN 'Phase 2: Dispatch'
    ELSE 'Phase 1: Seed'
  END AS current_stage
```

## Sub-Orchestration Pattern (모든 사이클의 바닥)

```
APT (orchestrator)
  └── Step 6 cleanup
        └── 재배맨 (Pre-fetch → Dispatch → Collect → Write)
              └── inner subagent (haiku N parallel)
TPA (orchestrator)
  └── TCW phase
        └── 재배맨 (file-level partition)
PROM (orchestrator)
  └── Step 3
        └── 재배맨 (axis × sub-axis matrix)
TLB (skill)
  └── Phase 1
        └── 재배맨 (lens-set parallel critic)
```

# KG: ATOM_Skill_jaebaeman, fw-jaebaeman-references-apt-parity-2026-05-06
