---
name: jaebaeman
aliases: [SOP, subagent-orchestration-protocol]
kg_ref: ATOM_Skill_jaebaeman
version: "2.3.0"
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
  wave_index: Int,           // dispatch 파편 순서 (0..N-1)
  status: String,            // 'READY' | 'DISPATCHED' | 'COLLECTED' | 'FAILED'
  created_at: DateTime,
  cycle_id: String           // 어느 APT cycle 의 결정인지 추적
}]->(s:SubagentTaskSpec)
```

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
| 1-9 | (skill / sourceId / displayName / taskType / targetDomain / expectedOutcome / contractRef / taskRef / germinationMethod) | ❌ KG metadata | `:SubagentTaskSpec.*` + HAS_SEED edge property + prompt 본문 녹임 |
| 별도 | `ts.model` | ✅ 거쳐서 (`Agent(model=MODEL_MAP[ts.model])`) | alias resolution 후 tool param |
| 별도 | `prompt` (조립된 문자열) | ✅ 직접 | tool param |
| 별도 | `run_in_background` | ✅ 직접 | tool param (N>1 면 True) |

**Tool param 으로 직접 전달되는 9-field 는 0개**. 9-field 는 전부 KG metadata, parent 가 KG 조회 후 *prompt 본문에 녹여* tool 에 전달.

### 잘못된 패턴 (Anti-Pattern, 사전 차단 mandatory)

```python
# ❌ AP-1: subagent_type 직접 전달 → InputValidationError. 대신 archetype label 을 prompt 첫 줄.
Agent(subagent_type='taliban-ensemble-critic', prompt=sb)

# ❌ AP-2: isolation 직접 전달 → InputValidationError. 대신 KG metadata.
Agent(isolation='sandbox', prompt=sb)

# ❌ AP-3: 9-field bundle 전체 spread → 첫 unknown key 에서 InputValidationError.
Agent(**sb)

# ❌ AP-4: cache_control 을 tool 시그니처에 직접 → cache_control 은 prompt content block 내부.
Agent(cache_control={'type': 'ephemeral'}, prompt=sb)
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
  depth: Int,             // 프랙탈 세대 (최대 3)
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
    ts.depth = coalesce($depth, 0),
    ts.createdAt = datetime()
```

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

```python
Agent(
    model = ts.model or 'haiku',
    run_in_background = True,  # N>1이면 병렬
    prompt = assembled_prompt
)
```

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
| **v2** | 2026-04 | Subagent Runtime Protocol — 부모 4단계 (Pre-fetch → Dispatch → Collect → Write). 씨앗(SubagentTaskSpec) KG 관리. MIC_v1.SubagentSeeder slot resolve. 재배맨은 서비스 아닌 *프로토콜* | `재배맨-v2-subagent-runtime-protocol`, `ATOM_Skill_jaebaeman`, `SA_methodology_v4_triple_upgrade`, `lesson-jaebaeman-vs-erlang-actor-hadoop-celery-2026-04-25` |
| **v1** | (older) | 4단계 protocol 초안. agent dispatch + KG MERGE | — |

→ **PROM 64 정전화 (2026-04-29)**: 재배맨 ≅ μX. (CHUPiece + List X) initial algebra (Lambek 1968 / Goguen 1977 / Lean 4). Erlang OTP supervision tree = 가장 깊은 산업 동형 (AXD301 9-nines). Fractal Generative Models (Li et al. 2025.2 arXiv 2502.17437) = ML 결정화 vindication.
→ Linda tuple space (Gelernter 1985) = KG-as-coordination *literal* 동형 (재발명 아닌 결정화).

# KG history: ATOM_Skill_jaebaeman / lesson-prom16-skill-versioning-academic-2026-04-29 / lesson-prom64-jaebaeman-chu-agentfolder-2026-04-29
