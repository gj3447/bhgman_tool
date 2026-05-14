---
name: jaebaeman
aliases: [SOP, subagent-orchestration-protocol]
kg_ref: ATOM_Skill_jaebaeman
version: "2.4.0"
channel: stable
description: >
  재배맨(JaebaeMan) v2.1 — Subagent Orchestration Protocol (SOP). 모든 AI subagent 동작의 바닥(foundation).
  씨앗(SubagentTaskSpec)을 KG에서 관리하고, 부모가 Pre-fetch → Dispatch → Collect → Write하는 프로토콜.
  재배맨은 서비스가 아닌 프로토콜이다. 부모 Claude가 따르는 규약.
  v2.1 (2026-05-05): MAS misnomer 정정 — Wooldridge BDI agent와 다름(internal state 부재, KG seed=외부 명세).
  학문적 정확 명칭 = SOP(Subagent Orchestration Protocol). 재배맨은 한국어 alias 유지.
  Invoke when: subagent 출격이 필요할 때 (프로메테우스/탈레반/solve 등이 내부적으로 호출).
  직접 호출보다는 MIC_v1.SubagentSeeder slot을 통해 간접 resolve.
  # KG: ATOM_Skill_jaebaeman, 재배맨-v2-subagent-runtime-protocol, SA_methodology_v4_triple_upgrade
  # KG: jaebaeman-grounding-2026-05-05, finding-prom32-jaebaeman-J1-F2 (MAS misnomer), lesson-jaebaeman-rebrand-SOP-2026-05-05
---

## 🔗 MIC Binding (SOLID-DIP)

**IS slot**: `SubagentSeeder` (MIC_v1.currentConcrete = "재배맨")
**소비자 slot**: Prometheus(ResearchProvider), Taliban(AdversarialValidator), Solve, APT-* (Phase별)

**동적 resolution**:
```cypher
MATCH (mic:MethodologyIntegrationContract {name:'MIC_v1'})-[:HAS_SLOT]->(s:MethodologySlot {name:'SubagentSeeder'})
RETURN s.currentConcrete, s.invocation
```

**역할 대체 가능성 (L 원칙)**: 미래에 재배맨 대신 다른 subagent 프로토콜로 교체 시 `MIC_v1.SubagentSeeder.currentConcrete` SET만. 소비자는 slot 참조이므로 본문 수정 불필요.

**프로토콜 불변**: 재배맨은 상주 서비스가 아니다. **부모 Claude가 따르는 4단계 프로토콜**(Seed→Dispatch→Collect→Write).

## 🛡 v2.1 Saga Compensation Slot (2026-05-05, RFC J3-F2)

> Garcia-Molina & Salem 1987 Sagas와 비교 시 4단계 protocol에 compensation 부재 → 부분 실패 시 KG inconsistent state. Write 단계에 compensating_action slot 신설.

**SubagentTaskSpec schema 추가 필드:**
| 필드 | 타입 | 설명 |
|---|---|---|
| `compensating_action` | Cypher string \| null | dispatch 후 collect 실패 시 호출되는 inverse action. KG에 미완 ValidationResult/Finding 정리 |
| `failure_mode` | enum: `best_effort`, `saga_compensate`, `2pc_abort` | 실패 처리 전략. default=`best_effort` (현 동작), 새 cycle은 `saga_compensate` 권장 |
| `idempotency_key` | string | retry 시 중복 write 방지용 (Write 단계 MERGE 정합성 강화) |

**Collect 실패 처리 prototocol:**
1. Subagent N개 중 M개만 결과 반환 (timeout/error)
2. `failure_mode=saga_compensate`이면 부모가 모든 dispatched subagent의 `compensating_action` Cypher 실행
3. KG에 `partial_failure_log` 노드 생성 + `IS_COMPENSATED_FOR` edge
4. `failure_mode=best_effort`(legacy)이면 부분 결과만 marshal + warning

## 🔌 v2.1 MCP inputSchema 통합 (2026-05-05, RFC J4-F3)

> SubagentTaskSpec.prompt(free-form Cypher property) → MCP server tool definition(JSON Schema)와 호환. type-safe + prompt injection 방어.

**SubagentTaskSpec schema 추가 (additive, prompt 병존):**
| 필드 | 타입 | 설명 |
|---|---|---|
| `inputSchema` | JSON Schema (object) | MCP tool inputSchema와 동일 spec. parent가 prompt 생성 시 type-validate |
| `outputSchema` | JSON Schema (object) | subagent 결과 validate. UNWIND batch write 전 필수 schema 통과 |
| `mcp_tool_compat` | boolean | true면 SubagentTaskSpec이 MCP tool 정의로 export 가능 |

**MCP tool export 패턴:**
```cypher
MATCH (ts:SubagentTaskSpec) WHERE ts.mcp_tool_compat = true AND ts.inputSchema IS NOT NULL
RETURN ts.name AS tool_name, ts.inputSchema, ts.outputSchema, ts.compensating_action
// → MCP server가 이 결과를 tool definition으로 publish
```

**기존 prompt-only TaskSpec 호환:**
- 기본값 `inputSchema=null`, `mcp_tool_compat=false`이므로 기존 동작 unchanged
- 신규 작성 시 inputSchema 권장. 향후 MCP server 통합 시 자동 export

# KG: MIC_v1, ATOM_Skill_jaebaeman, MethodologySlot:SubagentSeeder, lesson-apt-skill-drift-audit-2026-04-17, lesson-jaebaeman-rebrand-SOP-2026-05-05, lesson-jaebaeman-saga-compensation-2026-05-05, lesson-jaebaeman-mcp-inputschema-2026-05-05

---

## 🌱 v2.2 SubagentTaskSpec Schema — 9-field bundle + sourceId FK 1:1 (2026-05-14, GAP-3)

> 사용자 정전 2026-05-14: 「기본 동작 단위는 재배맨이야 재배맨 단위가 span 이기도하고 ㅇㅇ; 재배맨 씨앗단위」.
> 즉 **SubagentTaskSpec (재배맨 씨앗) 1개 = AtomicSpan 1개 1:1**. 씨앗 단위 = 작업의 atomic 단위.
> 상세: [`references/seed_fk_invariant.md`](./references/seed_fk_invariant.md).

### 9-field Seed Bundle (canonical core)

| # | 필드 | 타입 | 역할 |
|---|------|------|------|
| 1 | `skill` | String | 소속 스킬 (`apt-scw`, `prometheus`, `taliban`, ...) |
| 2 | `sourceId` | String **FK→:AtomicSpan(name)** | 발아 원천 AtomicSpan name. **1:1 invariant** |
| 3 | `displayName` | String | 사람 읽기용 역할명 |
| 4 | `taskType` | enum | `research` \| `validation` \| `methodology-skill-edit` \| `code-impl` \| ... |
| 5 | `targetDomain` | String | 담당 도메인 |
| 6 | `expectedOutcome` | String | 기대 산출물 형식 (Contract postcondition 거울) |
| 7 | `contractRef` | String → `:Contract(name)` | 입출력 계약 노드 ref (Phase 4 schema-validate 근거) |
| 8 | `taskRef` | String → `:SemanticTask(name)` | 작업 단위 ref (Phase 2 prompt 조립 근거) |
| 9 | `germinationMethod` | enum | `consensus` \| `conflict` \| `singleton` \| `manual` \| `1to1to1to1-dogfood-<date>` |

**Phase별 옵션 필드** (saga `compensating_action`, MCP `inputSchema/outputSchema` 등)는 위 9-field 위에 *additive*. 9-field 가 정전 core.

### sourceId FK 1:1 Invariant

```
∀ s:SubagentTaskSpec where s.skill = 'apt-scw'.
   s.sourceId ∈ {AtomicSpan.name}                          -- FK (no orphan)
∧ ∀ a:AtomicSpan ∃! s:SubagentTaskSpec[s.sourceId = a.name AND s.skill='apt-scw']  -- bijection
```

**Rationale**: 재배맨 SOP 의 단위 (씨앗) = APT 의 단위 (AtomicSpan). 둘이 다르면 *어떤* 단위가 작업 단위인지 모호 → drift. 사용자 정전이 1:1 강제.

**다른 skill** (`prometheus`, `taliban` 등) 은 `sourceId` 가 `Lesson` / `Span` / `Contract` 등 다른 anchor 일 수 있음. FK target 은 `(skill, sourceLabel)` pair 가 결정 (각 skill 의 references 에 명시). 단, **`skill='apt-scw'` 의 경우 sourceLabel = `AtomicSpan` 으로 정전 고정**.

### HAS_SEED Edge Schema

```cypher
(a:AtomicSpan)-[:HAS_SEED {
  wave_index: Int,           // dispatch 파편 순서 (0..N-1). 한 AtomicSpan 이 재배포(wave) 받으면 증가
  status: String,            // 'READY' | 'DISPATCHED' | 'COLLECTED' | 'FAILED'  (s.status 거울)
  created_at: DateTime,
  cycle_id: String           // 어느 APT cycle 의 결정인지 추적
}]->(s:SubagentTaskSpec)
```

**불변**: `wave_index` 가 다르면 같은 (a, s.skill) 에 대해 여러 SubagentTaskSpec 이 *시간순* 존재 가능 (재시도). 그러나 **현재 활성** (status ∈ {READY, DISPATCHED, COLLECTED}) 인 seed 는 **AtomicSpan 당 1개** (1:1 invariant).

### Orphan Seed Detection (FK 위반 감지)

```cypher
// 1. sourceId 가 :AtomicSpan(name) 에 존재하지 않음 → OrphanSeed
MATCH (s:SubagentTaskSpec {skill: 'apt-scw'})
WHERE NOT EXISTS { MATCH (a:AtomicSpan {name: s.sourceId}) }
RETURN count(s) AS orphan_seeds  // > 0 → invariant violation (E1)

// 2. HAS_SEED edge 누락 (sourceId 는 맞으나 edge 없음)
MATCH (s:SubagentTaskSpec {skill: 'apt-scw'})
MATCH (a:AtomicSpan {name: s.sourceId})
WHERE NOT EXISTS { MATCH (a)-[:HAS_SEED]->(s) }
RETURN count(s) AS missing_edges  // > 0 → invariant violation (E2)

// 3. 같은 AtomicSpan 에 활성 seed 2+ (MultipleSeedPerAtomicSpan)
MATCH (a:AtomicSpan)-[:HAS_SEED]->(s:SubagentTaskSpec {skill: 'apt-scw'})
WHERE s.status IN ['READY', 'DISPATCHED', 'COLLECTED']
WITH a, count(s) AS active_seeds
WHERE active_seeds > 1
RETURN a.name, active_seeds  // > 0 → invariant violation (E3)
```

### Error Variants

| Code | 이름 | 조건 | 복구 |
|------|------|------|------|
| E1 | `OrphanSeed` | `s.sourceId` ∉ `:AtomicSpan(name)` | seed 폐기 (FAILED) 또는 AtomicSpan 먼저 생성 |
| E2 | `MissingHasSeedEdge` | sourceId 매칭 AtomicSpan 존재하나 `:HAS_SEED` edge 부재 | backfill edge MERGE (아래 마이그레이션 Cypher) |
| E3 | `MultipleSeedPerAtomicSpan` | 동일 AtomicSpan 에 활성 seed > 1 | 가장 오래된 seed → ARCHIVED, 최신만 활성 유지 |

상세 worked example (3 case) + Wooldridge BDI grounding + backfill 마이그레이션 Cypher: [`references/seed_fk_invariant.md`](./references/seed_fk_invariant.md).

# KG: ATOM_Skill_jaebaeman, span-gap3-jaebaeman-seed-fk-2026-05-14, lesson-jaebaeman-rebrand-SOP-2026-05-05

---

## 🧷 v2.3 Schema Tool Param Binding (2026-05-14, PROM_16 E2.1 finding)

> Finding: `rf-prom16-cc-eng-E2-S1-agent-tool-params-2026-05-14` (PARTIAL_DRIFT, runtime fail 잠재).
> SOP references 가 `Agent(subagent_type=..., isolation=...)` 같은 비표준 param 을 prescribe 하고 있었음 → 실제 Anthropic Agent tool 시그니처 mismatch → InputValidationError.

### Anthropic Agent Tool 시그니처 정전

```
Agent(
  model: str,                    # full ID OR alias ('haiku' | 'sonnet' | 'opus')
  run_in_background: bool,       # True = 병렬 백그라운드, False = blocking
  prompt: str                    # 본문 — archetype / role / context 모두 여기 녹임
)
```

**단 3 param**. 그 외는 모두 **runtime InputValidationError**.

### 9-field Bundle → Tool Param 분리 매트릭스

| # | 9-field name | Tool param? | 위치 |
|---|--------------|-------------|------|
| 1 | `skill` | ❌ KG metadata | `:SubagentTaskSpec.skill` + DispatchHyperedge.skill |
| 2 | `sourceId` | ❌ KG metadata | `:SubagentTaskSpec.sourceId` (FK→AtomicSpan) |
| 3 | `displayName` | ❌ KG metadata | `:SubagentTaskSpec.displayName` (prompt 본문에 녹임) |
| 4 | `taskType` | ❌ KG metadata | `:SubagentTaskSpec.taskType` (prompt 본문에 녹임) |
| 5 | `targetDomain` | ❌ KG metadata | `:SubagentTaskSpec.targetDomain` (prompt 본문에 녹임) |
| 6 | `expectedOutcome` | ❌ KG metadata | `:SubagentTaskSpec.expectedOutcome` (prompt 본문 closing 에 schema 명시) |
| 7 | `contractRef` | ❌ KG metadata | `:SubagentTaskSpec.contractRef` (prompt pre-fetch 에서 Contract 노드 조회 결과 주입) |
| 8 | `taskRef` | ❌ KG metadata | `:SubagentTaskSpec.taskRef` (prompt pre-fetch 에서 SemanticTask 조회 결과 주입) |
| 9 | `germinationMethod` | ❌ KG metadata | HAS_SEED edge property + `:SubagentTaskSpec.germinationMethod` |

**Tool param 으로 직접 전달되는 것은 9-field 중 0개**. 9-field 는 전부 KG metadata, parent 가 KG 조회 후 *prompt 본문에 녹여* tool 에 전달.

별도 ts.model field 가 alias resolution 거쳐 `Agent(model=...)` 에 들어감 (이건 9-field 외 부가 field).

### 잘못된 패턴 (Anti-Pattern, 사전 차단 mandatory)

```python
# ❌ AP-1: subagent_type 직접 전달
Agent(subagent_type='taliban-ensemble-critic', prompt=sb)
# → InputValidationError. 대신: archetype label 을 prompt 첫 줄에 명시.

# ❌ AP-2: isolation 직접 전달
Agent(isolation='sandbox', prompt=sb)
# → InputValidationError. 대신: KG metadata 로 박고 parent 가 격리 정책 enforce.

# ❌ AP-3: 9-field bundle 전체 spread
Agent(**sb)  # sb = {skill, sourceId, displayName, ..., model, prompt}
# → InputValidationError on 첫 unknown key.

# ❌ AP-4: cache_control 을 tool 시그니처에 직접
Agent(cache_control={'type': 'ephemeral'}, prompt=sb)
# → InputValidationError. cache_control 은 prompt content block 내부에 박힘 (Anthropic SDK 정전).
```

### 올바른 패턴 (정전)

```python
# 1. KG 에서 ts 조회 (9-field + model alias)
ts = kg_fetch_taskspec(name=seed_name)

# 2. KG pre-fetch — taskRef/contractRef 디레퍼런스
context_block = kg_prefetch(ts.taskRef, ts.contractRef, ts.targetDomain)

# 3. prompt 조립 — archetype/role/contract 모두 본문에 녹임
prompt = f"""\
역할: {ts.displayName} (archetype={archetype_from_skill(ts.skill)})
씨앗: {ts.name} — {ts.taskType} / {ts.targetDomain}
계약: {context_block.contract_summary}
사전지식: {context_block.kg_snapshot}
{ts.expectedOutcome 형식의 JSON 단일 블록 출력.}
"""

# 4. Agent tool 호출 — 3 param only
Agent(
  model = MODEL_MAP[ts.model or 'haiku'],
  run_in_background = (N > 1),
  prompt = prompt
)

# 5. dispatch 후 KG update — 9-field 전체는 이미 :SubagentTaskSpec 에 있음
# HAS_SEED edge status='DISPATCHED', cycle_id, wave_index 만 갱신
```

### MODEL_MAP — alias → full ID resolution

```python
# Anthropic Claude API model ID 정전 (2026-05-14 기준)
MODEL_MAP = {
    'haiku':  'claude-haiku-4-5-20251001',    # 4.5 Haiku, fast/cheap subagent (1M context)
    'sonnet': 'claude-sonnet-4-7-20260301',   # 4.7 Sonnet, balanced
    'opus':   'claude-opus-4-7-20260301',     # 4.7 Opus, parent orchestrator (1M context)
}

def resolve_model(alias_or_id: str) -> str:
    """alias 면 full ID 로, 이미 full ID 면 passthrough."""
    if alias_or_id in MODEL_MAP:
        return MODEL_MAP[alias_or_id]
    if alias_or_id.startswith('claude-'):
        return alias_or_id   # 이미 full ID
    raise ValueError(f'Unknown model: {alias_or_id}')
```

**Rationale**: SKILL.md 본문 / Subagent seed 는 alias ('haiku') 로 쓰는 편이 SKILL drift 시 model version bump 가 한 곳 (MODEL_MAP) 에서만 일어남. full ID 를 본문 흩뿌리면 retire-model 마이그레이션 시 수십 곳 grep.

### Prompt Caching Directive (5-min TTL ephemeral)

N개 dispatch 가 동일한 stable prefix (KG snapshot / Lesson list / prior RF) 공유하면 Anthropic prompt caching 적용:

```python
# Anthropic SDK 직접 호출 시 (Agent tool wrapper 내부에서):
messages = [{
    "role": "user",
    "content": [
        {
            "type": "text",
            "text": stable_prefix,                          # KG snapshot, > 1024 tokens
            "cache_control": {"type": "ephemeral"}          # 5-min TTL cache write
        },
        {
            "type": "text",
            "text": per_agent_suffix                        # role/axis/sub_axis — 다양
        }
    ]
}]
```

**조건**:
- prefix ≥ 1024 tokens (haiku) / 2048 tokens (sonnet/opus)
- bytes-exact match (1 char diff → cache miss)
- 5-min TTL (만료 후 cache write 다시)

**효과**: 첫 dispatch = cache write (full price), 이후 N-1 dispatch = cache read (≈ 10% price). N=32 dispatch 시 input token cost ≈ 1 + 31×0.1 = 4.1× (32× 대비 87% 절감).

추적: `DispatchHyperedge.cache_hit_ratio` = (cache_read_count) / N.

### Validation Gate (Phase 2.3 pre-dispatch hook)

```python
ALLOWED_AGENT_KWARGS = {'model', 'run_in_background', 'prompt'}

def validate_agent_kwargs(kwargs: dict) -> None:
    extra = set(kwargs.keys()) - ALLOWED_AGENT_KWARGS
    if extra:
        raise SOPValidationError(
            f'PROM_16 E2.1: Agent tool only accepts {ALLOWED_AGENT_KWARGS}. '
            f'Unknown params: {extra}. '
            f'KG metadata (subagent_type/isolation/archetype 등) 는 prompt 본문에 녹이거나 KG 에만 박을 것.'
        )
```

# KG: rf-prom16-cc-eng-E2-S1-agent-tool-params-2026-05-14, lesson-jaebaeman-tool-param-binding-2026-05-14, ATOM_Skill_jaebaeman

---

## 🪵 v2.4 SubagentTaskSpec.depth NOT NULL Invariant (2026-05-14, p3 trigger)

> Finding: 직전 `/prom` drift fix (commits `4fec91f` / `7889067` / `7fade00`) 측 KG UNWIND 시 apoc trigger `t_depth_not_null` 발동 → `50N00 p3 invariant: SubagentTaskSpec.depth must not be null` → seed 누락. 우회 = `depth=0` 사전 박기. spec 측 미문서 = silent fail 재발 위험.
> Lesson: `lesson-jaebaeman-depth-invariant-2026-05-14`.

### Invariant 정전

```
I_DEPTH : ∀ s:SubagentTaskSpec . s.depth IS NOT NULL ∧ s.depth ∈ [0, 3]
          • root seed                  → depth = 0
          • fractal child (Step 4.7)   → depth = parent.depth + 1
          • depth > 3                  → hard fail (무한 증식 차단)
```

**apoc trigger `t_depth_not_null` (live on neo4j://data/neo4j-0)** 가 DB 측 enforce:

```cypher
// Trigger source (cypher-shell verified 2026-05-14)
CYPHER 5 UNWIND keys($assignedNodeProperties) AS k
 UNWIND $assignedNodeProperties[k] AS entry
 WITH entry WHERE "SubagentTaskSpec" IN labels(entry.node) AND entry.node.depth IS NULL
 CALL apoc.util.validate(true, "p3 invariant: SubagentTaskSpec.depth must not be null", [])
 RETURN 0
```

→ `:SubagentTaskSpec` 노드의 *어떤* property assignment 든 `depth IS NULL` 이면 transaction rollback.
→ 따라서 SET 절 어디서든 `depth=coalesce($depth, 0)` 또는 명시적 `depth=0` *필수*.

### 모든 SubagentTaskSpec 관련 apoc trigger (audit 2026-05-14)

| Trigger | Type | Enforce |
|---|---|---|
| `t_depth_not_null` | property assignment guard | depth NOT NULL (p3 invariant) — **본 절 정전화** |
| `t_dep_unlock` | status transition (BLOCKED → READY) | DEPENDS_ON dep 모두 READY/COMPLETED 시 자동 unlock |
| `t_failure_spawn` | failureCount ≥ 3 | adversarial sibling seed 자동 생성 (`SPAWNED_SIBLING` edge) |
| `rf-audit-after-v2` | ResearchFinding create | TriggerAuditLogV2 자동 기록 |

추가 constraint:
- `p3_subagent_name_unique` (UNIQUENESS on `:SubagentTaskSpec(name)`)

→ p1/p2/p4 invariant trigger 는 **현재 DB 측 미설치** (audit 결과). p3 만 active.
→ 향후 p1 (sourceId FK), p2 (status enum), p4 (germinationMethod enum) 추가 시 동일 패턴으로 SKILL.md 측 amend.

### 9-field Bundle 갱신 — `depth` NOT NULL 필드 추가

v2.2 의 9-field core 는 *논리 spec*. 실제 DB 측 NOT NULL 강제 필드는 **9-field + `depth` + `status` + `createdAt`** 의 12 field. depth 는 9-field 의 *additive option* 으로 분류돼 있었으나 trigger 측 강제 → **schema-mandatory 격상**.

| # | 필드 | 타입 | NULL? | 기본값 | 비고 |
|---|------|------|-------|--------|------|
| 1-9 | (9-field core) | (v2.2 표 그대로) | 각 필드별 | — | 정전 core |
| +10 | **`depth`** | Int | **❌ NOT NULL** | **0** (root seed) | **`t_depth_not_null` trigger 강제 (p3)** |
| +11 | `status` | enum String | NOT NULL | `READY` | lifecycle anchor |
| +12 | `createdAt` | DateTime | NOT NULL | `datetime()` | provenance anchor |

### 씨앗 생성 Cypher 정전 — `depth` 명시 mandatory

**잘못된 패턴 (silent fail)**:

```cypher
// ❌ AP-D1: depth 누락 → t_depth_not_null 발동 → 50N00 rollback
MERGE (s:SubagentTaskSpec {name: $name})
SET s.skill = $skill, s.sourceId = $sid, s.status = 'READY', s.createdAt = datetime();
```

**올바른 패턴**:

```cypher
// ✓ root seed (대다수 경우)
MERGE (s:SubagentTaskSpec {name: $name})
SET s.skill = $skill,
    s.sourceId = $sid,
    s.displayName = $display,
    s.taskType = $taskType,
    s.targetDomain = $domain,
    s.expectedOutcome = $outcome,
    s.contractRef = $contractRef,
    s.taskRef = $taskRef,
    s.germinationMethod = $germ,
    s.depth = coalesce($depth, 0),    // ← MANDATORY. 누락 시 NULL → trigger rollback
    s.status = 'READY',
    s.createdAt = datetime();

// ✓ fractal child (Step 4.7 in-cycle germination)
MATCH (parent:SubagentTaskSpec {name: $parent_seed})
WITH coalesce(parent.depth, 0) + 1 AS newDepth
WHERE newDepth <= 3                   // hard limit
MERGE (s:SubagentTaskSpec {name: $name})
SET s.depth = newDepth, ...;          // 나머지 동일
```

### Validation Gate (Phase 1 pre-MERGE)

```python
def validate_seed_bundle(bundle: dict) -> None:
    if bundle.get('depth') is None:
        raise SOPValidationError(
            'p3 invariant: SubagentTaskSpec.depth must not be null. '
            'Set depth=0 for root seed or depth=parent.depth+1 (≤3) for fractal child. '
            'See SKILL.md §v2.4.'
        )
    if not (0 <= bundle['depth'] <= 3):
        raise SOPValidationError(
            f'depth out of range [0,3]: got {bundle["depth"]}. '
            'depth>3 is fractal infinite-expansion (Phase 4.7 hard limit).'
        )
```

### Error Variants 표 보강 (v2.2 E1/E2/E3 + E4 추가)

| Code | 이름 | 조건 | 복구 |
|------|------|------|------|
| E1 | `OrphanSeed` | (v2.2) | (v2.2) |
| E2 | `MissingHasSeedEdge` | (v2.2) | (v2.2) |
| E3 | `MultipleSeedPerAtomicSpan` | (v2.2) | (v2.2) |
| **E4** | **`DepthInvariantViolation` (p3)** | **`s.depth IS NULL` OR `s.depth > 3`** | **MERGE 절에 `depth = coalesce($depth, 0)` 명시 + fractal hard limit. Trigger `t_depth_not_null` 발동 시 50N00 rollback** |

### Backfill (legacy seeds with NULL depth)

```cypher
// 1. Audit
MATCH (s:SubagentTaskSpec) WHERE s.depth IS NULL
RETURN count(s) AS missing_depth, collect(s.name)[..10] AS sample;

// 2. Backfill — root seed assumption (sourceRF/sourceId 가 ResearchFinding 또는 AtomicSpan 1차 anchor)
MATCH (s:SubagentTaskSpec) WHERE s.depth IS NULL
SET s.depth = 0,
    s.depth_backfilled_at = datetime(),
    s.depth_backfilled_reason = 'p3 invariant v2.4 migration 2026-05-14';

// 3. (옵션) 프랙탈 child 감지 후 정정
MATCH (parent:SubagentTaskSpec)-[:GERMINATED_FROM]->(:ResearchFinding)<-[:HAS_RESEARCH]-(:Lesson)<-[:SPAWNED_FROM]-(child:SubagentTaskSpec)
WHERE child.depth = 0
SET child.depth = coalesce(parent.depth, 0) + 1;
```

(DB audit 결과 2026-05-14: `missing_depth = 0`. 즉 backfill 불필요 — 현재 모든 active seed 가 이미 depth 박힌 상태. v2.4 spec 정전화는 *미래 silent fail 차단* 목적.)

# KG: lesson-jaebaeman-depth-invariant-2026-05-14, ATOM_Skill_jaebaeman, 재배맨-v2-subagent-runtime-protocol

---

# /jaebaeman — Subagent Runtime Protocol

> **재배맨 = 씨앗에서 에이전트를 재배하는 사람.**
> KG에 심어둔 TaskSpec 씨앗이 발아하여 subagent가 되고,
> 열매(Finding)를 수확하여 다시 KG에 심는 순환.

---

## 재배맨은 프로토콜이다

재배맨은 상주 서비스가 아니다. **부모 Claude가 따르는 4단계 프로토콜**이다.

```
Phase 1: Seed    — KG에서 씨앗(TaskSpec) 조회 또는 생성
Phase 2: Dispatch — Pre-fetch → Prompt 조립 → Agent tool 호출
Phase 3: Collect  — JSON 수확 → 유효성 검증 → 중복 검사
Phase 4: Write   — UNWIND 배치 KG merge → 씨앗 상태 갱신
```

각 소비자(Prometheus, Taliban 등)는 이 4단계를 자기 도메인에 맞게 특화한다.
**프로토콜은 하나, 소비 패턴은 다수.**

---

## Phase 1: Seed — 씨앗 관리

### 씨앗 스키마 (SubagentTaskSpec)

```cypher
// 씨앗의 정본 구조
(:SubagentTaskSpec {
  name: String,           // PK. 'seed-{skill}-{domain}-{timestamp}'
  skill: String,          // 소속 스킬 ('prometheus', 'taliban', ...)
  displayName: String,    // 사람 읽기용 역할명
  role: String,           // subagent에게 전달할 역할 설명
  description: String,    // 상세 작업 내용
  checkItems: [String],   // 체크리스트
  cypherQueries: [String],// 참고 Cypher 쿼리들
  expectedOutcome: String,// 기대 산출물 형식
  targetDomain: String,   // 담당 도메인
  model: String,          // 'haiku' | 'sonnet' | 'opus'
  priority: String,       // 'HIGH' | 'MEDIUM' | 'LOW' | 'EXPLORATION' | 'VERIFY'
  status: String,         // READY → DISPATCHED → COLLECTED → ARCHIVED | FAILED
  depth: Int,             // 프랙탈 세대 [0,3] — **NOT NULL** (v2.4 §p3 trigger 강제)
  germinationMethod: String, // 'consensus' | 'conflict' | 'singleton' | 'manual'
  sourceRF: String,       // 발아 원천 ResearchFinding name
  createdAt: DateTime,
  dispatchedAt: DateTime,
  collectedAt: DateTime
})
```

### 씨앗 조회

```cypher
// 특정 스킬의 READY 씨앗 목록
MATCH (ts:SubagentTaskSpec {skill: $skill})
WHERE ts.status = 'READY'
RETURN ts.name, ts.displayName, ts.role, ts.priority, ts.targetDomain
ORDER BY ts.priority DESC, ts.createdAt DESC
LIMIT 10
```

### 씨앗 생성 (심기)

```cypher
MERGE (ts:SubagentTaskSpec {name: $name})
SET ts.skill = $skill,
    ts.displayName = $display,
    ts.role = $role,
    ts.description = $desc,
    ts.checkItems = $checks,
    ts.expectedOutcome = $outcome,
    ts.model = $model,
    ts.priority = $priority,
    ts.targetDomain = $domain,
    ts.status = 'READY',
    ts.depth = coalesce($depth, 0),    // ★ NOT NULL — v2.4 §p3 trigger (depth=0 root, parent+1 fractal)
    ts.createdAt = datetime()
```

> ⚠ **`t_depth_not_null` apoc trigger** (live)가 `:SubagentTaskSpec` 의 `depth IS NULL` SET 을 차단한다. `coalesce(...,0)` 누락 시 `50N00 p3 invariant` 로 transaction rollback. 상세: §v2.4.

### 씨앗 중복 검사 (Dedupe)

```cypher
// 심기 전 중복 확인
MATCH (ts:SubagentTaskSpec)
WHERE ts.skill = $skill
  AND ts.targetDomain = $domain
  AND ts.status IN ['READY', 'DISPATCHED']
RETURN ts.name, ts.role, ts.status
```

중복 발견 시: **새로 심지 않고 기존 씨앗 재사용**. MERGE 보장.

---

## Phase 2: Dispatch — 부모가 subagent 출격

### 2-1. Pre-fetch (하계 context 조회)

**subagent는 MCP 접근 불가** (GH #13605). 부모가 대신 KG 조회.

```cypher
// 기존 ResearchFinding (중복 방지용)
MATCH (l:Lesson)-[:HAS_RESEARCH]->(rf:ResearchFinding)
WHERE l.name CONTAINS $problem_keyword
RETURN rf.name, rf.domain, rf.oneLineSummary
LIMIT 20

// 관련 Lesson (기존 지식)
MATCH (l:Lesson)
WHERE l.problem CONTAINS $problem_keyword
  AND (l.resolved IS NULL OR l.resolved = false)
RETURN l.name, l.problem, l.severity
LIMIT 10

// 관련 Seeds (재사용 가능)
MATCH (ts:SubagentTaskSpec {skill: $skill})
WHERE ts.status = 'READY'
  AND (ts.description CONTAINS $keyword OR ts.role CONTAINS $keyword)
RETURN ts.name, ts.role
LIMIT 10
```

### 2-2. Prompt 조립 (3줄 + context)

```
역할: {ts.displayName}  (agentId=D{idx})
씨앗: {ts.name} — {ts.role}
기존_지식(하계): {pre_fetch_json}
이미 조사된 내용과 중복되지 않는 새로운 관점을 조사하세요.
출력: FullFindingRecord JSON 단일 블록.
```

**절대 금지**: SKILL.md 전체를 prompt에 넣지 않는다. 3줄 + context만.

### 2-3. Agent 호출

**Anthropic Agent tool 시그니처 정전**: `(model, run_in_background, prompt)` — 단 3 param. 9-field bundle 중 이 3 field 만 tool param 으로, 나머지 6 field (skill / sourceId / displayName / taskType / targetDomain / germinationMethod) 는 **KG metadata only** (HAS_SEED edge + DispatchHyperedge 에 박힘). `subagent_type` / `isolation` / `archetype` 같은 *비표준 param* 전달 시 **InputValidationError → runtime fail** (PROM_16 E2.1 finding `rf-prom16-cc-eng-E2-S1-agent-tool-params-2026-05-14`).

```python
# MODEL_MAP — alias → full ID (Anthropic Claude API 정전)
MODEL_MAP = {
    'haiku':  'claude-haiku-4-5-20251001',   # 4.5 Haiku, 1M context, fast/cheap subagent
    'sonnet': 'claude-sonnet-4-7-20260301',  # 4.7 Sonnet, balanced
    'opus':   'claude-opus-4-7-20260301',    # 4.7 Opus 1M context, parent orchestrator
}

# 정전 호출 패턴 (3 param only):
Agent(
    model = MODEL_MAP[ts.model or 'haiku'],   # alias 해석. ts.model 이 이미 full ID 면 passthrough
    run_in_background = True,                  # N>1 이면 병렬, single 이면 False 가능
    prompt = assembled_prompt                  # 3줄 + pre-fetch context. archetype/subagent_type 정보는 본문에 녹임
)

# ❌ 잘못된 패턴 (runtime fail):
# Agent(subagent_type='taliban-ensemble-critic', prompt=...)   # InputValidationError
# Agent(isolation='sandbox', prompt=...)                        # InputValidationError
```

**Prompt caching directive** (5-min TTL ephemeral cache, Anthropic prompt caching 정전):

N개 병렬 dispatch 시 pre-fetch context (KG snapshot / Lesson list / 기존 ResearchFinding) 가 동일하면 **cache_control: `{type: "ephemeral"}`** 을 prompt 의 stable prefix 에 박아 cache hit 활용. 첫 호출 = cache write (full price), 이후 N-1 호출 = cache read (≈ 10% price). 5분 TTL 동안 동일 cycle 내 재dispatch 시 효과적.

```python
# parent 가 prompt 조립 시 stable prefix 와 per-agent suffix 분리:
stable_prefix = build_pre_fetch_context(skill, problem_keyword)   # KG snapshot, Lesson, prior RF
per_agent_suffix = build_role_block(ts.displayName, ts.role, sb.axis, sb.sub_axis)

# Anthropic SDK 호출 시 cache_control:
[
  {"type": "text", "text": stable_prefix, "cache_control": {"type": "ephemeral"}},
  {"type": "text", "text": per_agent_suffix}
]
# → 첫 dispatch 가 prefix cache write, 이후 N-1 dispatch 가 cache hit
```

**Cache 적용 조건**:
- prefix 길이 ≥ 1024 tokens (haiku) / 2048 tokens (sonnet/opus) — 미만이면 cache 비활성
- 동일 prefix bytes-exact match — 1 char 다르면 cache miss
- 5분 TTL 내 재사용 — 만료 후 cache write 다시 필요

Cache hit ratio 추적은 `DispatchHyperedge.cache_hit_ratio` 필드에 기록 (Phase 4 Write 단계).

### 2-4. 씨앗 상태 전이

```cypher
MATCH (ts:SubagentTaskSpec {name: $seed_name})
SET ts.status = 'DISPATCHED', ts.dispatchedAt = datetime()
```

---

## Phase 3: Collect — 결과 수확

### 3-1. JSON 파싱

subagent 반환값에서 **FullFindingRecord JSON 블록**을 추출.

```json
{
  "findingId": "finding_<hash>",
  "domain": "<도메인>",
  "rootCause": "<200자>",
  "recommendation": "<300자>",
  "alternatives": ["...", "..."],
  "references": ["..."],
  "caveats": "<200자>",
  "confidence": "HIGH|MEDIUM|LOW",
  "oneLineSummary": "<300자>",
  "agentId": "D<idx>",
  "researchedAt": "<ISO8601>",
  "sourceKgBindings": ["<KG 노드명>"]
}
```

### 3-2. 유효성 검증

필수 필드: findingId, domain, rootCause, recommendation, confidence, oneLineSummary.
누락 시 → FAILED 마킹, 재시도 또는 스킵.

### 3-3. 중복 검사 (Dedup)

```cypher
// findingId 충돌
MATCH (rf:ResearchFinding {name: $findingId})
RETURN rf IS NOT NULL AS exists

// domain + 유사 내용
MATCH (rf:ResearchFinding)
WHERE rf.domain = $domain
  AND rf.oneLineSummary CONTAINS $keyword
RETURN rf.name, rf.oneLineSummary LIMIT 5
```

| 상황 | 조치 |
|------|------|
| findingId 충돌 | MERGE (기존 갱신) |
| domain + 유사 summary | alternatives에 추가만 |
| 완전 신규 | 정상 MERGE |

---

## Phase 4: Write — KG 배치 적재

### 4-1. UNWIND 배치 MERGE

**단일 트랜잭션. subagent가 직접 쓰지 않는다.**

```cypher
MATCH (l:Lesson {name: $lesson_name})
UNWIND $findings AS f
MERGE (r:AbstractNode:ResearchFinding {name: f.findingId})
SET r.domain = f.domain,
    r.rootCause = f.rootCause,
    r.recommendation = f.recommendation,
    r.alternatives = f.alternatives,
    r.references = f.references,
    r.caveats = f.caveats,
    r.confidence = f.confidence,
    r.oneLineSummary = f.oneLineSummary,
    r.agentId = f.agentId,
    r.researchedAt = datetime(f.researchedAt),
    r.sourceKgBindings = f.sourceKgBindings,
    r.provenance = $provenance,
    r.status = 'RESEARCHED'
MERGE (l)-[:HAS_RESEARCH]->(r)
RETURN count(r) AS writtenCount
```

### 4-2. 씨앗 상태 갱신

```cypher
MATCH (ts:SubagentTaskSpec {name: $seed_name})
SET ts.status = 'COLLECTED', ts.collectedAt = datetime()
```

### 4-3. 프랙탈 씨앗 발아 (선택)

수확된 finding에서 **새 씨앗을 발아**시킬 수 있다 (Prometheus Step 4.7).
depth 제한: 최대 3세대.

```cypher
// 새 씨앗의 depth = 부모 + 1
MATCH (parent:SubagentTaskSpec {name: $parent_seed})
WITH coalesce(parent.depth, 0) + 1 AS newDepth
WHERE newDepth <= 3
// ... MERGE new seed with depth = newDepth
```

---

## Lifecycle 상태 전이

### 씨앗 (SubagentTaskSpec) Lifecycle

```
READY ──dispatch──→ DISPATCHED ──collect──→ COLLECTED ──archive──→ ARCHIVED
  │                     │                      │
  └──(미사용 30일)──→ STALE          └──(실패)──→ FAILED
```

### Finding (ResearchFinding) Lifecycle (v5: Prometheus에서 승격)

<!-- # KG: SPAN_ResearchFinding_Lifecycle, CONTRACT_SharedType_RFStatus -->

Finding은 `RESEARCHED` 시작 후 다음 terminal 상태 중 하나로 수렴. **모든 소비자(Prometheus/Taliban/Solve/APT) 공유**.

```
RESEARCHED (Phase 4 write)
    │
    ├─→ CRYSTALLIZED        (새 SubagentTaskSpec 씨앗 생성 — GERMINATED_FROM 엣지 존재)
    ├─→ ABSORBED_INTO_PLAN  (ActionPlan.action 이 recommendation 직접 인용)
    ├─→ ORPHANED_RAW        (결정화 skip — 다음 cycle Step 2.5 pre-fetch 재방문 후보)
    └─→ ARCHIVED            (Lesson.resolved=true 또는 명시적 reject, reject는 rejected_reason 필드)
```

**전이 규칙**:

| From | To | Trigger |
|---|---|---|
| RESEARCHED | CRYSTALLIZED | `(ts:SubagentTaskSpec)-[:GERMINATED_FROM]->(rf)` 엣지 생성 |
| RESEARCHED | ABSORBED_INTO_PLAN | ActionPlan.action 이 rf.recommendation 인용 |
| RESEARCHED | ORPHANED_RAW | 결정화 완료 후에도 outgoing GERMINATED_FROM 없음 |
| CRYSTALLIZED / ABSORBED_INTO_PLAN | ARCHIVED | Lesson.resolved=true |
| ORPHANED_RAW | RESEARCHED (revisit) | 다음 cycle Step 2.5 pre-fetch 포함됨 |
| ANY | ARCHIVED (rejected) | 명시적 reject — `rejected_reason` 메타데이터 기록 |

**REJECTED는 별도 terminal이 아님**: ARCHIVED + `rejected_reason`으로 통합 (상태 수 최소화).

**재분류 Cypher** (skip 감지 + 자동 마킹):

```cypher
MATCH (rf:ResearchFinding {cycle_id: $cycle_id})
WHERE rf.status <> 'ARCHIVED'
OPTIONAL MATCH (rf)<-[:GERMINATED_FROM]-(ts:SubagentTaskSpec)
WITH rf, count(ts) AS seed_count
SET rf.status = CASE
  WHEN seed_count > 0 THEN 'CRYSTALLIZED'
  ELSE 'ORPHANED_RAW'
END,
rf.lifecycle_updated_at = datetime()
```

### 죽은 씨앗 감사 (주간)

```cypher
// 30일 이상 READY 상태인 씨앗 = STALE 후보
MATCH (ts:SubagentTaskSpec)
WHERE ts.status = 'READY'
  AND ts.createdAt < datetime() - duration('P30D')
RETURN ts.name, ts.skill, ts.createdAt
ORDER BY ts.createdAt
```

STALE 씨앗은 검토 후 ARCHIVED 또는 재활성화.

---

## 소비자별 특화 패턴

| 소비자 | Phase 1 | Phase 2 | Phase 3 | Phase 4 |
|--------|---------|---------|---------|---------|
| **Prometheus** | N개 도메인별 씨앗 동적 생성 | N개 병렬 dispatch (haiku) | FullFindingRecord JSON | UNWIND + Step 4.7 씨앗 발아 |
| **Taliban** | 9-lens 헌법 씨앗 (고정) | 9개 병렬 dispatch | Verdict JSON (PASS/FAIL) | ValidationResult MERGE |
| **88-Taliban** | 113-lens 수학 씨앗 | 113개 배치 dispatch | 5-category 평가 JSON | 88-lens 결과 MERGE |
| **Solve** | 문제별 단일 씨앗 | 단일 dispatch | Solution JSON | Lesson.resolved = true |
| **APT-*** | Phase별 전용 씨앗 | 필요 시 dispatch | Phase artifact | Phase 결과 MERGE |

---

## What NOT To Do

| 금지 | 이유 | 대안 |
|------|------|------|
| subagent에 SKILL.md 전체 주입 | Context Rot (Anti-Context-Rot) | 3줄 prompt + pre-fetch context |
| subagent가 KG 직접 write | MCP 미상속 + 동시성 lock | 부모 UNWIND 단일 경로 |
| 씨앗 없이 subagent 출격 | 추적 불가, 재현 불가 | 항상 TaskSpec 먼저 |
| depth > 3 프랙탈 | 무한 증식 | depth 3 hard limit |
| SKILL.md에 재배맨 로직 복사 | drift 유발 | MIC thin resolver만 |
| CREATE (MERGE 대신) | 중복 씨앗/finding | 항상 MERGE |

---

## Provenance 추적 (W3C PROV)

모든 finding에 provenance 기록:

```
provenance = '{method}-subagent-parallel-{N}'
  method: 'haiku' | 'sonnet' | 'opus'
  N: dispatch 수

예: 'haiku-subagent-parallel-32' (Prom #1)
    'haiku-subagent-parallel-9'  (Taliban 9-lens)
```

---

*씨앗을 심는 자가 수확도 한다.
재배맨은 KG를 밭으로, TaskSpec을 씨앗으로, subagent를 일꾼으로, Finding을 열매로 본다.
그리고 열매에서 다시 씨앗을 추출하여 심는다. 이것이 프랙탈 순환이다.*

# KG: 재배맨-v2-subagent-runtime-protocol, ATOM_Skill_jaebaeman, SA_methodology_v4_triple_upgrade

---

## History

> Repo-level changes: [`/CHANGELOG.md`](../CHANGELOG.md). Per-commit: `git log -- jaebaeman/SKILL.md`.
> 학문 grounding: [`/PROM_16_SKILL_VERSIONING_REPORT.md`](../PROM_16_SKILL_VERSIONING_REPORT.md) + [`/PROM_64_REPORT_v2.md` (THEORY/재배맨/)](../../THEORY/재배맨/PROM_64_REPORT_v2.md).

| Version | Date | Summary | KG Ref |
|---|---|---|---|
| **v2.4** | 2026-05-14 | `SubagentTaskSpec.depth NOT NULL` invariant 정전화 (p3 trigger). 직전 `/prom` drift fix 측 `50N00 p3 invariant` rollback → spec 미문서 silent fail 위험. apoc trigger 4종 audit (`t_depth_not_null` / `t_dep_unlock` / `t_failure_spawn` / `rf-audit-after-v2`) + constraint `p3_subagent_name_unique`. 9-field bundle → 12-field schema 격상 (depth/status/createdAt NOT NULL 추가). E4 `DepthInvariantViolation` 신설. 씨앗 생성 Cypher `coalesce($depth,0)` mandatory 명시. Validation gate Python. | `lesson-jaebaeman-depth-invariant-2026-05-14` |
| **v2.3** | 2026-05-14 | Schema Tool Param Binding (PROM_16 E2.1 patch) — Anthropic Agent tool 시그니처 `(model, run_in_background, prompt)` 3 param 정전. `subagent_type` / `isolation` 등 비표준 param 제거 (runtime fail 차단). 9-field bundle → KG metadata only matrix. MODEL_MAP alias resolution + cache_control ephemeral 5-min TTL directive. references/phases.md + gates.md + theory.md + kg_logging.md 동시 patch. | `rf-prom16-cc-eng-E2-S1-agent-tool-params-2026-05-14`, `lesson-jaebaeman-tool-param-binding-2026-05-14` |
| **v2.2** | 2026-05-14 | SubagentTaskSpec 9-field bundle + sourceId FK→AtomicSpan 1:1 invariant (GAP-3). Orphan/MissingEdge/MultipleSeed detection. | `span-gap3-jaebaeman-seed-fk-2026-05-14` |
| **v2.1** | 2026-05-05 | MAS misnomer 정정 (Wooldridge BDI ≠ KG-seed agent) — SOP 학문적 명칭 격상. Saga compensation slot + MCP inputSchema 통합. | `lesson-jaebaeman-rebrand-SOP-2026-05-05`, `lesson-jaebaeman-saga-compensation-2026-05-05`, `lesson-jaebaeman-mcp-inputschema-2026-05-05` |
| **v2** | 2026-04 | Subagent Runtime Protocol — 부모 4단계 (Pre-fetch → Dispatch → Collect → Write). 씨앗(SubagentTaskSpec) KG 관리. MIC_v1.SubagentSeeder slot resolve. 재배맨은 서비스 아닌 *프로토콜* | `재배맨-v2-subagent-runtime-protocol`, `ATOM_Skill_jaebaeman`, `SA_methodology_v4_triple_upgrade`, `lesson-jaebaeman-vs-erlang-actor-hadoop-celery-2026-04-25` |
| **v1** | (older) | 4단계 protocol 초안. agent dispatch + KG MERGE | — |

→ **PROM 64 정전화 (2026-04-29)**: 재배맨 ≅ μX. (CHUPiece + List X) initial algebra (Lambek 1968 / Goguen 1977 / Lean 4). Erlang OTP supervision tree = 가장 깊은 산업 동형 (AXD301 9-nines). Fractal Generative Models (Li et al. 2025.2 arXiv 2502.17437) = ML 결정화 vindication.
→ Linda tuple space (Gelernter 1985) = KG-as-coordination *literal* 동형 (재발명 아닌 결정화).

# KG history: ATOM_Skill_jaebaeman / lesson-prom16-skill-versioning-academic-2026-04-29 / lesson-prom64-jaebaeman-chu-agentfolder-2026-04-29
