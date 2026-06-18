# Wave-Aware SCW Dispatch (Kahn-ordered parallel batches)

> SCW Step 2 dispatch 의 정전. SP 가 부여한 `AtomicSpan.wave_index` (GAP-1) 와 재배맨 `SubagentTaskSpec.sourceId` FK 1:1 (GAP-3) 를 합쳐서
> **wave 단위 single-message N-parallel dispatch** 를 실행하는 절차.
>
> 사용자 정전 (2026-05-14): 「최대한 병렬 처리가 되도록」 + 「재배맨 단위가 span」 + 「종속성 아닌 부분은 최대 병렬」.
>
> KG: `span-gap4-scw-wave-dispatch-2026-05-14`, `ATOM_Skill_apt_scw`, `APT_SP_WaveExtraction_canonical`, `lesson-jaebaeman-rebrand-SOP-2026-05-05`.
> Sibling refs: [`../../apt-sp/references/wave_extraction.md`](../../apt-sp/references/wave_extraction.md) (GAP-1), [`../../jaebaeman/references/seed_fk_invariant.md`](../../jaebaeman/references/seed_fk_invariant.md) (GAP-3).

---

## 0. 의존 (Precondition — 둘 다 ✓ 후 진입)

| Dep | 조건 | 검증 cypher |
|---|---|---|
| GAP-1 wave_index | ∀ AtomicSpan. wave_index IS NOT NULL | `MATCH (a:AtomicSpan) WHERE a.wave_index IS NULL RETURN count(a)` ⇒ 0 |
| GAP-3 Seed FK | ∀ s:SubagentTaskSpec[skill='apt-scw']. ∃ a:AtomicSpan[name=s.sourceId] AND (a)-[:HAS_SEED]->(s) | `seed_fk_invariant.md` §3 I_FK ∧ I_EDGE ∧ I_BIJ |
| ST Gate APPROVED | (sa)-[:HAS_VALIDATION]->(vr:ValidationResult {phase:'ST', verdict:'APPROVED'}) | `apt-gate-check.sh` |

위 3 조건 통과 안 하면 wave dispatch 진입 차단 (gate check hook).

---

## 1. Wave Loop — Pseudocode

```
W_max ← MAX(AtomicSpan.wave_index)         -- e.g. 3 for 3-wave decomposition
for w in 1..W_max:
    batch ← collect_ready_seeds(wave=w)    -- N seeds for wave w
    if |batch| == 0:
        continue                           -- skip empty wave (defensive; SP gate should prevent)

    -- Intent self-check (GH#29181 dispatch fan-out drift guard)
    intent_N ← |batch|
    Agent_calls ← dispatch_parallel_single_message(batch)
    actual_N ← |Agent_calls|
    assert intent_N == actual_N, DispatchIntentMismatch

    results ← collect_all(Agent_calls)     -- wait all
    per_seed_verdicts ← {seed: verdict for seed, verdict in zip(batch, results)}

    if all(v == 'PASS' for v in per_seed_verdicts.values()):
        write_kg_batch(results)            -- UNWIND single transaction (재배맨 Phase 4)
        advance to wave w+1
    else:
        -- WavePartialFail: 진입 차단
        raise WavePartialFail(
            wave=w,
            failed=[s for s, v in per_seed_verdicts.items() if v != 'PASS']
        )
        -- 사용자 verdict 게이트 — wave w+1 자동 진입 금지
```

**Invariant**:
- *Same wave*: fully parallel — 1 message, N Agent tool calls.
- *Cross wave*: strictly sequential — wave k+1 은 wave k 전체 PASS 후만.
- Kahn ordering 준수 ⟺ `(a)-[:DEPENDS_ON]->(b) ⟹ a.wave_index < b.wave_index` (GAP-1 §2 strict-less).

---

## 2. Cypher — wave 단위 batch collect

```cypher
// SCW dispatch step (wave-aware, GAP-1+GAP-3 통합)
// $CURRENT_WAVE: driver loop 변수 (1, 2, ..., W_max)
MATCH (a:AtomicSpan)-[:HAS_SEED]->(ts:SubagentTaskSpec {skill:'apt-scw'})
WHERE a.wave_index = $CURRENT_WAVE
  AND ts.status = 'READY'
WITH ts, a
ORDER BY a.name  // deterministic dispatch order (debug 재현용)
RETURN collect({
  seed_name: ts.name,
  source_atom: a.name,
  display_name: ts.displayName,
  task_type: ts.taskType,
  target_domain: ts.targetDomain,
  contract_ref: ts.contractRef,
  task_ref: ts.taskRef,
  wave: a.wave_index
}) AS dispatch_batch
```

→ 결과의 `dispatch_batch` 길이 N = wave 의 병렬 폭.
→ 부모는 `dispatch_batch` 의 각 entry 를 **단일 메시지 내 N Agent tool call** 로 변환.

### W_max 산출

```cypher
MATCH (sa:SemanticAnchor {name: $PROJECT})-[:HAS_ROOT]->(root)
MATCH (root)-[:DECOMPOSES_TO*1..10]->(a:AtomicSpan)
RETURN MAX(a.wave_index) AS w_max, COUNT(a) AS total_atoms
```

---

## 3. Single-message Dispatch (재배맨 Phase 2)

재배맨 `phases.md` Phase 2 Dispatch 는 *N seeds = N tool calls in one message* 패턴.

**올바른 패턴** (single message 내 N parallel Agent calls — 사용자 「최대한 병렬」 정전):

```
[부모 message N]:
  Agent(model='haiku', prompt=<seed_1 3줄>)
  Agent(model='haiku', prompt=<seed_2 3줄>)
  ...
  Agent(model='haiku', prompt=<seed_N 3줄>)
```

**금지 패턴**:

| Anti | 이유 |
|---|---|
| N 메시지 × 1 Agent | sequential 화 → wave 의미 손실 |
| 1 메시지 × 1 Agent → 결과 보고 → 다음 1 Agent | feedback loop 의 *premature* 단축. wave 전체 PASS 후 advance |
| wave k 의 일부 + wave k+1 의 일부 섞어서 | DEPENDS_ON 순서 위반 (race) |

**KG status 전이**:

```cypher
UNWIND $dispatched_seed_names AS sn
MATCH (ts:SubagentTaskSpec {name: sn})
SET ts.status = 'DISPATCHED', ts.dispatchedAt = datetime()
```

---

## 4. GH#29181 Intent-vs-Actual Self-Check

> Issue: agent self-reports dispatch intent N but emits ≠ N Agent tool calls (silent drift, model context truncation 또는 tool budget overflow).

**Self-check 체크포인트** (dispatch 직전 + 직후 2회):

### 4-1. Pre-dispatch (intent 선언)

```
intent_N = |dispatch_batch|  // §2 cypher 결과
log: "dispatching wave={w} intent_N={intent_N}"
```

### 4-2. Post-dispatch (actual 계수)

부모 message 의 tool_use 블록 수를 count → actual_N.

```
assert actual_N == intent_N, DispatchIntentMismatch(
  wave=w,
  intent=intent_N,
  actual=actual_N,
  delta=intent_N - actual_N
)
```

### 4-3. Mismatch 복구

| delta | 의미 | 복구 |
|---|---|---|
| `delta > 0` (intent > actual) | 일부 seed dispatch 누락 — context truncation 의심 | wave w 부분 결과 archive + 누락 seed status='READY' 복원 + 재dispatch |
| `delta < 0` (intent < actual) | 비의도적 over-dispatch — 중복 또는 cross-wave 누출 | 초과 Agent call 결과 archive (status='ARCHIVED' + rejected_reason='OverDispatch') |
| `delta == 0` | OK | proceed Phase 3 collect |

---

## 5. WavePartialFail Handling

wave w 의 N seeds 중 M (M ≥ 1) 개가 FAIL → wave w+1 진입 **차단**.

```cypher
// 1. FAIL seed 마킹
UNWIND $failed_seed_names AS sn
MATCH (ts:SubagentTaskSpec {name: sn})
SET ts.status = 'FAILED', ts.failedAt = datetime();

// 2. WavePartialFail 노드 + 사용자 게이트
MERGE (wpf:WavePartialFail {
  project: $PROJECT,
  wave: $CURRENT_WAVE,
  cycle_id: $CYCLE_ID
})
SET wpf.failed_count = $M,
    wpf.total_count = $N,
    wpf.failed_seeds = $failed_seed_names,
    wpf.passed_seeds = $passed_seed_names,
    wpf.detected_at = datetime(),
    wpf.user_verdict_required = true,
    wpf.advance_blocked = true;
```

**복구 옵션** (사용자 verdict 게이트):

| Option | 동작 | 사용 시점 |
|---|---|---|
| (a) Retry-Seed | FAIL seed 만 새 SubagentTaskSpec 으로 재dispatch (wave 유지) | 일시적 실패 (timeout, transient error) |
| (b) Span 재분해 | FAIL atom 을 SP 로 되돌려 D(S) 추가 분해 → wave_index 재계산 | 분해 단위 자체가 너무 큼 (vibe_coding_hard_max 초과) |
| (c) Contract 보강 | ST 로 되돌려 Contract.acceptance_criteria 강화 | Contract 명세 부족으로 acceptance test 실패 |
| (d) Force-advance (위험) | FAIL 무시하고 wave w+1 진입 | **절대 금지** — DEPENDS_ON 순서 위반 + downstream 코드 깨짐 |

(d) 는 KG 에 explicit override anti-pattern 으로 기록.

---

## 6. Worked Example — 3-wave 7-span (GAP-1 와 일관)

> GAP-1 `wave_extraction.md` §"Worked Example" 의 3-wave 7-span DAG 를 SCW dispatch 관점에서 그대로 재사용.

### Atoms + wave assignment (GAP-1 결과 import)

```
ATOM_A.wave_index = 1
ATOM_B.wave_index = 1
ATOM_C.wave_index = 1
ATOM_F.wave_index = 1
ATOM_D.wave_index = 2   // depends_on A, B, C
ATOM_E.wave_index = 2   // depends_on C
ATOM_G.wave_index = 3   // depends_on D, E, F
```

### Seed 생성 (GAP-3 1:1 FK)

```cypher
UNWIND [
  {atom:'ATOM_A', wave:1, seed:'seed-scw-ATOM_A'},
  {atom:'ATOM_B', wave:1, seed:'seed-scw-ATOM_B'},
  {atom:'ATOM_C', wave:1, seed:'seed-scw-ATOM_C'},
  {atom:'ATOM_F', wave:1, seed:'seed-scw-ATOM_F'},
  {atom:'ATOM_D', wave:2, seed:'seed-scw-ATOM_D'},
  {atom:'ATOM_E', wave:2, seed:'seed-scw-ATOM_E'},
  {atom:'ATOM_G', wave:3, seed:'seed-scw-ATOM_G'}
] AS row
MATCH (a:AtomicSpan {name: row.atom})
MERGE (s:SubagentTaskSpec {
  name: row.seed, skill:'apt-scw', sourceId: row.atom
})
SET s.status='READY', s.taskType='code-impl', s.createdAt=datetime()
MERGE (a)-[e:HAS_SEED]->(s)
ON CREATE SET e.wave_index = row.wave, e.status='READY',
              e.created_at = datetime(), e.cycle_id = 'example-3wave';
```

### Dispatch trace

**Wave 1** (4 parallel — single message):
```
intent_N=4
[parent message]:
  Agent(seed-scw-ATOM_A)  Agent(seed-scw-ATOM_B)
  Agent(seed-scw-ATOM_C)  Agent(seed-scw-ATOM_F)
actual_N=4 ✓
collect all → 4×PASS ✓
UNWIND write KG → advance wave 2
```

**Wave 2** (2 parallel — single message):
```
intent_N=2
[parent message]:
  Agent(seed-scw-ATOM_D)  Agent(seed-scw-ATOM_E)
actual_N=2 ✓
collect all → 2×PASS ✓
UNWIND write KG → advance wave 3
```

**Wave 3** (1 — trivially parallel):
```
intent_N=1
[parent message]:
  Agent(seed-scw-ATOM_G)
actual_N=1 ✓
collect → PASS ✓
final integration check (SCW Step 5)
```

### Wall-clock 비교

| dispatch strategy | wall-clock | parallelism |
|---|---|---|
| Naive sequential | 7 × t_atom | 1 |
| **Wave-aware (이 정전)** | (1 + 1 + 1) × t_atom = **3 × t_atom** | up to 4 |
| All-parallel (DEPENDS_ON 무시) | t_atom (race condition — INVALID) | 7 (이론적) |

> Wave-aware = 안전한 최대 병렬화. Naive 대비 7/3 ≈ 2.33x 단축.

### Counter-example: Wave 2 partial fail

가정: ATOM_D PASS, ATOM_E FAIL.

```
wave 2 결과: {D: PASS, E: FAIL}
→ WavePartialFail node 생성
→ wave 3 진입 차단 (ATOM_G 가 ATOM_E 에 depends_on)
→ 사용자 verdict 게이트:
   option (a) Retry seed-scw-ATOM_E
   option (c) Contract_E.acceptance_criteria 보강 후 retry
```

만약 force-advance (option d) 했다면: ATOM_G 코드가 ATOM_E 의 출력 contract 를 의존하는데 E 가 아직 미구현 → ImportError 또는 NotImplementedError 런타임 폭발.

---

## 7. Retry Policy

| 상황 | 정책 |
|---|---|
| Seed timeout (no result) | 동일 seed 재dispatch (max 2 retry). 3회째도 실패 → `FAILED` 마킹 + WavePartialFail |
| Seed FAIL (verdict=REJECTED) | 원인 분류: (a) contract 불충분 → ST 피드백 / (b) test 불충분 → seed 재작성 / (c) atom 너무 큼 → SP 분해 |
| Wave 전체 timeout | 부분 결과 archive + 전체 wave 재dispatch (cycle_id 새로 부여) |
| Cross-wave interference (rare) | KG 에 `WaveInterference` 노드 + audit. 보통 GAP-1 wave_extraction 버그 의심 |

---

## 8. 5대 무기 와 wave 의 관계

| 무기 | wave 단위 진입 | 비고 |
|---|---|---|
| **재배맨** | Phase 2 Dispatch 가 wave 단위 single-message UNWIND | 이 정전의 골격 |
| **프로메테우스** | SCW dispatch 와 직교 (research phase 가 별도) | wave 외부 — 사전 지식 단계 |
| **나생문** | wave k 결과 collect 후 FulfillmentGate critic (각 seed 별) | wave advance gate |
| **롱기누스** | code 작성 후 KG ref 주석 binding 검증 (각 seed 별) | wave 내부 검증 |
| **하네스** | wave loop 실행 환경 (4-layer autonomy stack, churn-guard) | wave 외부 — runtime |

→ wave 가 *동시 실행* 단위, 나생문/롱기누스가 *각 seed 검증* 단위. 두 단위 직교.

---

## 9. Error Variants (요약)

| Code | 이름 | 조건 | Guard |
|---|---|---|---|
| W1 | `WavePartialFail` | wave k 의 일부 seed FAIL | wave k+1 진입 차단 + 사용자 게이트 |
| W2 | `DispatchIntentMismatch` | intent_N ≠ actual_N (GH#29181) | dispatch 직후 self-check, mismatch 시 §4-3 복구 |
| W3 | `MissingWaveIndex` | dispatch 시점 일부 AtomicSpan.wave_index IS NULL | SP→SCW gate 사전 차단 (GAP-1 V_SP_WaveIndex_Missing) |
| W4 | `CrossWaveInterference` | wave k seed 가 wave k+m (m≥1) atom 결과를 사용 | KG audit — DEPENDS_ON edge 빠진 SP 분해 버그 |
| W5 | `OverDispatch` | actual_N > intent_N (중복 Agent call) | 초과 결과 ARCHIVED + rejected_reason |
| W6 | `EmptyWave` | wave k batch 가 0 (SP 가 wave_index 부여했으나 seed 부재) | seed 생성 backfill 또는 wave 건너뛰기 |

---

## 10. 외부 정전 cite

- **Kahn, A. B. (1962).** Topological sorting of large networks. — wave 순서의 수학적 기반 (GAP-1 cite 와 공유).
- **CLRS §22.4 Topological Sort.** — DFS 변형 correctness.
- **Garcia-Molina, H. & Salem, K. (1987).** Sagas. *SIGMOD '87.* — wave 부분 실패 시 compensating action 패턴 (재배맨 v2.1 saga slot 과 연결).
- **GH issue #29181 (Claude Code).** Agent dispatch intent-vs-actual drift. — §4 self-check 의 origin.
- **Lamport, L. (1978).** Time, clocks, and the ordering of events in a distributed system. *CACM 21(7).* — wave = logical clock 의 happens-before 결정화.
- **Dilworth's Theorem (1950).** Poset minimum antichain partition. — wave 개수 = DEPENDS_ON poset 의 최장 chain.

---

## 11. Prompt Caching (E4.3 HIGH — 5× cost gap)

> PROM_16 finding `rf-prom16-cc-eng-E4-S3`: PARTIAL_EXPLOITED. 같은 wave N agent dispatch 시 pre-fetch Cypher context = shared (Contract / Task / KG provenance edges 모두 동일 batch).
> Cache hit 없으면 N × (Contract+Task+KG context) re-tokenize → $25/8h. ephemeral cache 5-min TTL 적용 시 $5/8h. **5× gap**.

### 11-1. cache_control: ephemeral (5-min TTL)

`Agent` tool 호출 시 `prompt` 의 *shared prefix* 에 cache marker 부착:

```
Agent(
  model='haiku',
  prompt=<<EOF
[cache_control: ephemeral]
# shared prefix (wave N agents 동일)
## Contract (ST 가 부여)
{{CONTRACT_BODY}}
## Task spec
{{TASK_REF_BODY}}
## KG ref edges
{{REFERENCE_SITE_7_TUPLE_BODY}}
## Wave invariant (DEPENDS_ON, wave_index)
{{WAVE_CONTEXT}}
[/cache_control]

# per-seed suffix (variable, NOT cached)
sourceId: seed-scw-ATOM_{X}
focus: AtomicSpan {X} only
EOF
)
```

**원리**: Anthropic prompt cache 는 prefix exact-match → 같은 wave N agent 가 동일 prefix 공유. 첫 agent 는 cache miss (write), 2..N agent 는 cache hit (read, 90% cost off).

**TTL**: 5분 (ephemeral default). wave 당 N agent 가 270초 안에 dispatch 완료되면 amortize 효과 최대.

### 11-2. Cypher pre-fetch — cache-aware batch

```cypher
// 단일 query 로 wave 의 shared context 한 번에 가져오기 (cache 친화)
MATCH (a:AtomicSpan)-[:HAS_SEED]->(ts:SubagentTaskSpec {skill:'apt-scw'})
WHERE a.wave_index = $CURRENT_WAVE AND ts.status = 'READY'
MATCH (a)-[:HAS_CONTRACT]->(c:Contract)
MATCH (a)-[:HAS_TASK]->(t:Task)
OPTIONAL MATCH (c)<-[:REFERENCES]-(rs:ReferenceSite)
WITH ts, a, c, t, collect(rs) AS refs
RETURN {
  // shared (cached) — 모든 seed 가 같은 ST/Contract/Task 패밀리 참조
  st_decision_areas: c.st_decision_areas,
  wave_invariant: a.wave_index,
  reference_site_schema: 'schema-ReferenceSite-v1-2026-04-20',
  // per-seed (NOT cached)
  seed_name: ts.name,
  source_atom: a.name,
  contract_ref: c.name,
  task_ref: t.name,
  refs: refs
} AS payload
ORDER BY a.name
```

→ 같은 wave 내부 N 결과는 `st_decision_areas / wave_invariant / reference_site_schema` 가 동일 prefix → cache hit 가능.

### 11-3. Adaptive Thinking — TDD logic 복잡 (15-25% iteration 절감)

haiku subagent 의 prompt 에 `thinking: {type: adaptive}` 옵션 명시:

```
Agent(
  model='haiku',
  thinking={type: 'adaptive', max_budget_tokens: 4096},
  prompt=<<EOF
[cache_control: ephemeral]
...shared prefix...
[/cache_control]

# TDD steps (RED → GREEN → REFACTOR)
# adaptive thinking 권장: acceptance test ↔ contract delta 추론 / GREEN minimal impl 후보 비교 / REFACTOR depth-limit 결정
sourceId: seed-scw-ATOM_{X}
EOF
)
```

**효과** (`rf-prom16-cc-eng-E4-S3` 측정):
- adaptive OFF: TDD iteration 평균 3.2 회 (RED → 잘못된 GREEN → fix → REFACTOR fail → re-fix)
- adaptive ON: TDD iteration 평균 2.5 회 (RED → 정확한 GREEN → REFACTOR pass) — **22% 절감**
- max_budget_tokens=4096 (extended thinking 의 lightweight 측 — haiku 의 reasoning bandwidth 적정)

### 11-4. Wave Sizing Cost Rule

> 270s ephemeral TTL 안에 amortize 최적화. wave 안 task 수와 평균 실행 시간 의 곱이 TTL 안에 들어와야 cache hit 보장.

| Wave size N | Avg task t_atom | Total wall (parallel) | TTL fit | Cache strategy |
|---|---|---|---|---|
| 1-3 | ≤ 4 min | ≤ 4 min | ✓ | ephemeral 충분 |
| **4-5 (sweet)** | **≤ 4 min** | **≤ 4 min** | **✓ (270s safe margin 30s)** | **ephemeral 최적 — amortize 최대** |
| 6-8 | ≤ 4 min | ≤ 4 min (single message N=8 가능) | ✓ but agent context budget 압박 | ephemeral + per-agent context 분할 |
| ≥ 9 | ≤ 4 min | dispatch latency 누적 | ⚠ TTL 경계 | wave 분할 권장 (SP wave_extraction §3 재실행) |
| any | > 4 min | > 4 min | ✗ | 1h cache 모드 (sticky cache, beta) 또는 task 더 분해 |

**권장 default**: wave 당 N=4-5, 각 task ≤4분 실행. SP 가 wave_extraction 시 이 sweet spot 으로 분해 권장 (`MethodologyConfig.wave_sweet_size = 4..5`).

### 11-5. ScheduleWakeup 모드 표 (fast iter vs economy)

| Mode | wakeup_interval | Cache 가정 | 비용 / 8h | 사용 시점 |
|---|---|---|---|---|
| **fast iter** | **270s** | **ephemeral hit (5-min TTL)** | **$5** | **APT 정상 cycle (default)** |
| economy | 1200s (20분) | TTL 초과 → cache miss 매번 | $25 | 야간 autoloop / 단발 dispatch / wave 사이 long deliberation |
| ultra fast | 60s | hot cache (반복 동일 wave) | $7 | wave 재dispatch (WavePartialFail 후 retry) |
| sticky | 3600s | 1h cache (beta) | $4 | long-running SCW (대규모 atom set, 30+ wave) |

→ **fast iter (270s)** 가 SCW default. Stop hook `~/.claude/hooks/auto_continue.sh` 측 wakeup 패턴은 fast iter 기준으로 박혀 있음 (PROM_32 §4 4-layer stack 의 L3).

---

## 12. Within-Wave Async Monitor (E2.4 LOW — UNDERUTILIZED)

> PROM_16 finding `rf-prom16-cc-eng-E2-S4`: Monitor tool UNDERUTILIZED. **within-wave 만** 적용. cross-wave 는 Kahn ordering 강제.

### 12-1. Scope

| Boundary | Monitor 허용 | 이유 |
|---|---|---|
| **within-wave** (same wave_index seed 들) | ✓ | DEPENDS_ON 없음 → 자유 병렬, async test/build event polling 안전 |
| **cross-wave** (wave k → wave k+1) | ✗ | Kahn ordering 강제 — wave k 전체 PASS gate 통과 후 advance |

### 12-2. Background test/build pattern

각 seed agent 의 TDD GREEN step 시 test runner / Lean build 를 background 로 띄우고 REFACTOR step 계속:

```
[agent message — seed-scw-ATOM_X]:
# step 2a (RED) — test 작성 (synchronous)
Write(test_atom_x.py)
# step 2b (GREEN) — minimal impl
Write(atom_x.py)
# 2b verify: background test (NOT block REFACTOR)
Bash(command='pytest test_atom_x.py --watch', run_in_background=true) → bash_id=B1
# step 2c (REFACTOR) — 진행 (Monitor 가 B1 결과 stream)
Monitor(bash_id=B1, ...)  # background event polling
# REFACTOR depth 안 결정 후 최종 통합
```

**Lean build watch** (TPA 측에서도 동일 패턴):

```
Bash(command='lean --build --watch MyModule.lean', run_in_background=true) → B2
Monitor(bash_id=B2)  # build event stream (PASS / sorry / type-error)
```

→ pytest `--watch` 또는 Lean `--build --watch` 출력은 stdout line 단위 notification → Monitor tool 의 until-loop / event stream 패턴과 1:1.

### 12-3. Final integration (wave gate 통과 전 강제)

REFACTOR 끝나면 background test/build 결과 *반드시* 통합:

```
# wave k 끝나기 전 (collect_all 시점):
for each seed in batch:
  Monitor(seed.bash_id, until_pass_or_fail=true)  # 강제 결합
  assert seed.test_pass == true, SeedTestFail
```

→ background event 가 미결 (`untermined`) 상태로 wave gate 진입 금지. cross-wave 진입 시점 = 모든 within-wave async 통합 완료 시점.

### 12-4. Pseudocode 통합

```
for w in 1..W_max:
    batch ← collect_ready_seeds(wave=w)
    Agent_calls ← dispatch_parallel_single_message(batch)  # 각 agent 내부 Monitor 가능
    background_handles ← collect_bash_ids(Agent_calls)
    sync_results ← collect_all(Agent_calls)
    # 강제 통합: agent 종료해도 background 미결 시 wait
    for h in background_handles:
        Monitor(h, until_done=true)
    per_seed_verdicts ← merge(sync_results, background_handles)
    if all PASS: advance
    else: WavePartialFail
```

### 12-5. Anti-pattern

| Anti | 이유 |
|---|---|
| cross-wave Monitor | Kahn ordering 위반 — wave k+1 의 background event 가 wave k 완료 전 시작 |
| background 결과 무시하고 PASS 마킹 | wave gate rubber-stamp (FulfillmentGate 7 checks §6 evidence-backed verdict 위반) |
| Monitor 무한 polling | seed timeout policy 미적용 — §7 Retry Policy 위반 |

---

## 13. 검증 체크리스트 (GAP-4 acceptance)

- [x] SCW SKILL.md dispatch step 본문 wave-aware Cypher (`a.wave_index = $CURRENT_WAVE`)
- [x] wave loop pseudo-code (for w in 1..W_max)
- [x] WavePartialFail handling — wave k+1 진입 차단 + 사용자 verdict 게이트
- [x] GH#29181 intent_N == actual_N self-check
- [x] 3-wave 7-span worked example — GAP-1 `wave_extraction.md` §Worked Example 와 동일 atom 이름/DAG/wave 분배
- [x] 5대 무기 cross-ref (재배맨 Phase 2 / 나생문 gate / 롱기누스 binding / 하네스 runtime)
- [x] retry policy 표 (timeout / FAIL / wave timeout / cross-wave)
- [x] error variants W1-W6

---

# KG: span-gap4-scw-wave-dispatch-2026-05-14, ATOM_Skill_apt_scw, APT_SP_WaveExtraction_canonical, 재배맨-v2-subagent-runtime-protocol, lesson-jaebaeman-rebrand-SOP-2026-05-05
