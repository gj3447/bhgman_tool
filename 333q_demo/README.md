# 몽환의숲 (Forest of Reverie) — 3-player Mermin GHZ pseudo-telepathy greybox

> **Game name (canonical, 2026-05-20)**: 몽환의숲 / Forest of Reverie / Dreamy Forest
> Module dir: `bhgman_tool/333q_demo/` (기술 path, 게임 이름 아님)
> SemanticAnchor: `anchor-333q-greybox-demo-2026-05-20` (KG node)
> Naming principle: Manifold Garden essence-name pattern + Antichamber psychology-pivot. *분위기/감정/장면 강조*, mechanic-name 표면화 회피.
> bhgman_tool 의 sub-module spike. APT v26.1 SA→SP→ST→SCW cycle 진행 중.
> User verdict: CANONICAL_DELEGATED 2026-05-20 (option A 최소 GHZ demo + "몽환의숲" game name)
> **Status**: ST phase 완료 + 3 HIGH blockers fixed, SCW phase entry ready (사용자 dispatch 대기)

## Two-layer separation reminder

bhgman_tool repo (이 repo) = practitioner toolkit layer. 333q_demo = browser TypeScript prototype sub-project (Python 본체 module 아님, nested workspace).

본 SYMPOSIUM paper 자료집 → `SYMPOSIUM/THEORY/333Q_MULTIPLAYER/` (별도 repo). 이 module 은 그 자료집의 *engineering crystallization*.

## What this is

3명이 브라우저에서 모여 1라운드 1샷 Mermin GHZ pseudo-telepathy 퍼즐을 푼다. Classical 협력은 75% 상한 (Mermin 1990 §III 증명). Cooperative quantum-encoded strategy 측 simulate 시 100% deterministic.

핵심 카피:
- **양자=carrier, 심리=essence** (Antichamber psychology-pivot 적용)
- **3명만** (n>3 quantum advantage exponential decay, Hypercube arXiv:1806.02642)
- **WebGPU compute ≤6 qubit** (browser memory 96 bytes well safe)
- **pre-shared seed PRNG = entanglement substitute** (실 양자 hardware 없음, structural pattern 만 leverage)
- **NO mid-round CRDT sync** (pseudo-telepathy game rule violation 회피, ys-* family ARCHIVED)
- **Post-round Trystero classical channel** (Mermin §III referee role)
- **Quantum Koan Wall** post-match (Antichamber 120 sign + Witness epiphany 적용)

## APT phase progress

| phase | status | key result |
|---|---|---|
| **Prometheus** pre-SA | ✅ complete | 2 cycle × 16 finding = 32 ResearchFinding (CANONICAL) |
| **SA** SemanticAnchor v1.2 | ✅ complete | 5 core fields + cheat_vs_honest 3-layer scoping + Naesengmoon D1-D4 fixed |
| **SP** SemanticPyramid | ✅ complete | 4-round D(S) (6→22→21+4 grand-children) + 25+1 per-leaf Naesengmoon gate + 14 HIGH fix + ys-* redesign → **21 leaves final Crystallization Frontier** |
| **ST** SemanticTwin | ✅ initial complete | 21 Contract v2 (9-axis) + 8 ST Decision Areas cycle-level + 21 SubagentTaskSpec SCW seed + 30 Contract→Contract edges (I1) + Longinus L4 sha256 anchor (I2) + ts-room-join precondition explicit (I3) |
| **SCW** SourceCodeWorld | ⏸ pending | 21 Wave dispatch (TDD RED→GREEN→Refactor per leaf). Wave 1.1: sv-A + ts-ice-fallback parallel start. 사용자 verdict 대기. |
| **MetaReview** | ⏸ pending | Lesson distillation + SKILL.md patch + Naesengmoon gate |

## SP phase 4-round D(S) progression (사용자 의심 3번 정당 instance)

| Round | 결과 |
|---|---|
| R1 initial | 6 candidate (모두 NOT_ATOMIC — 사용자 의심 1번째 정당 instance) |
| R2 D(S) sub-decompose | 6 parallel → 22 children (21 atomic + 1 split) |
| R3 cross-check | 21 confirmed + sv-B SPLIT_RECOMMENDED |
| R4 sv-B grand-children | 4 atomic (B3 σ caveat → cohesion-check resolved counterfactual) |
| **Per-leaf Naesengmoon** | 25 dispatched: 1 APPROVED + 22 CONDITIONAL + 2 BORDERLINE / 0 REJECTED |
| **12 HIGH defects** | All FIXED at SP-level (8 spans) |
| **ys-* redesign (사용자 의심 2번째 정당)** | 4 ARCHIVED (cargo-cult anti-pattern) + 1 TRANSFORMED → outcome-aggregator (Mermin §III referee classical post-measurement) |
| **outcome-aggregator Naesengmoon** | CONDITIONAL_APPROVED + 2 HIGH fixed (D1 collapse-complete event hook + D2 payload schema strict) |

## 21 AtomicSpan final Crystallization Frontier

| # | name | wave | LOC | layer |
|---|---|---|---|---|
| 1 | sv-A gpu-adapter | 1.1 | 180-300 TS | L1_per_player_local_HONEST |
| 2 | sv-B1 pauli-kernels | 1.21 | 240-440 TS | L1_HONEST |
| 3 | sv-B2 hadamard | 1.21 | 180-300 TS | L1_HONEST |
| 4 | sv-B3 cnot | 1.21 | 220-380 TS | L1_HONEST |
| 5 | sv-B4 pipeline-cache | 1.2 | 120-260 TS | L1_HONEST_SHARED_INFRA |
| 6 | sv-C born-sampling-ghz | 1.3 | 210-330 TS | L1_HONEST |
| 7 | mg-rule | 2.1 | 50-80 TS | L1_game_rule_HONEST + L3_bridge |
| 8 | mg-classical | 2.2 | 70-110 TS | L1 + L3 |
| 9 | mg-quantum-encoded | 2.3 | 90-130 TS | L1 + L3 |
| 10 | mg-measurement | 2.4 | 60-100 TS | L1 + L3 |
| 11 | ts-room-join | 1.2 | 80-120 TS | L2_engine_cheat_P2P |
| 12 | ts-ready-fsm | 1.2 | 50-80 TS | L2 |
| 13 | ts-ice-fallback | 1.1 | 60-100 TS | L2 |
| 14 | ts-entropy-seed | 1.2 | 50-80 TS | L2 |
| 15 | ts-failure-telemetry | 1.3 | 40-60 TS | L2 |
| 16 | **outcome-aggregator** (NEW, ys-* redesign) | 2.5 | 50-90 TS | **L_GAME_RULE_REFEREE_HONEST** |
| 17 | kw-library | 3.1 | 60-90 TS | L_psychology_essence |
| 18 | kw-harvest | 3.2 | 50-80 TS | L_psychology_essence |
| 19 | kw-moral-wall-ui | 3.3 | 70-120 TS | L_psychology_essence |
| 20 | th-v1v2 | 3.1 | 140-200 TS | L3_verification_CLASSICAL_SEPARATION |
| 21 | th-v3v5 | 4.1 | 110-180 TS | L3_verification_TIMING_DETERMINISM |

**Grand total**: 1850-3000 LOC TS + 280-500 LOC WGSL (state_vector + gate kernels) = **2130-3500 LOC**.

## ST Contract v2 9-axis (per leaf)

| axis | description |
|---|---|
| input | type signature input |
| output | type signature output |
| preconditions | what must hold before call |
| postconditions | what holds after |
| invariants | across-call invariants |
| error_variants | failure modes (v25) |
| shared | SharedType flag (sv-B4 / ts-ice-fallback / kw-library = true) |
| access_rights_closure | capability surface (v26 A2) |
| architecture_ref | ArchitectureContract category (v26 A2) |

## 8 ST Decision Areas (v27, cycle-level common)

| area | content |
|---|---|
| AST | TypeScript ES2022 + WGSL (separate compile target). Vite. ESM. Modern-browser baseline |
| Workflow | APT v26 SA→SP→ST→SCW→MetaReview. Wave-based parallel (1.1 → 1.2 → 1.21 → 1.3 → 2.x → 3.x → 4.x) |
| DP | 4 patterns active: Observer (per-player view) / Strategy (classical vs quantum) / Command (measurement projection) / Iterator (Born shot batch). DROPPED: Adapter (Yjs CRDT — ys-* archived) |
| PS | 3-player cooperative non-communicating game (Mermin 1990 §III GHZ pseudo-telepathy). Browser P2P. Pre-shared seed = entanglement substitute (Wiesner mirror) |
| DataFlow | per-player local: seed → state_vector → GHZ prep + basis rotation (input bit) → Born measurement → outcome bit. Post-round Trystero broadcast outcome_bit ONLY (payload schema strict) → 3-peer collect → GHZ rule score |
| Algo | state_vector evolution (Float32Array×2 complex128, WebGPU compute shader), Born rule sampling (cumsum + multinomial), GHZ rule check (Mermin §III parity), classical strategy comparator, quantum-encoded X/Y basis rotation, Lamport TS + replicaId tiebreak (outcome aggregator) |
| Store | in-memory only (greybox). state_vector = TypedArray double-buffer 1KB. Trystero ephemeral. koan library = static JSON 60-90 LOC |
| Class | Functional + minimal OOP. Pure functions: rule + strategies + Born + outcome score. Classes: GPUAdapter + FSM + koan classifier. NO inheritance |

## 30 Contract→Contract dependency edges (I1 fix)

```
sv-B1/B2/B3/C  --DEPENDS_ON-->  sv-A + sv-B4
mg-quantum-encoded  --CALLS-->  sv-B1/B2/C
mg-measurement  --CALLS-->  sv-C
outcome-aggregator  --CONSUMES_VIA_EVENT_ONLY-->  mg-measurement (collapse-complete)
outcome-aggregator  --CALLS-->  mg-rule + ts-room-join + ts-ready-fsm
ts-room-join  --DEPENDS_ON-->  ts-ice-fallback (rtc_config)
ts-failure-telemetry  --DEPENDS_ON-->  ts-ice-fallback + ts-room-join
ts-entropy-seed  --DEPENDS_ON-->  ts-room-join
kw-harvest  --READS-->  kw-library
kw-moral-wall-ui  --READS-->  kw-library + kw-harvest
th-v1v2  --CALLS-->  mg-classical + mg-quantum-encoded
th-v3v5  --CALLS-->  ts-room-join + outcome-aggregator + kw-harvest
```

## Longinus L4 sha256 anchored references

| ReferenceSite | path | sha256 baseline |
|---|---|---|
| `refsite-th-v1v2-to-numerology_mc_judge-py-2026-05-20` | `METAHUMOTONIC/ICE_ORCA_DRAGON/numerology_mc_judge.py` | `aaa051a84171f8d370a5d7d5b49a385327d5606a6660d75eae916f7dc3b1856a` |

## Verification spec (v1.1 numerology_mc gate 명시 + I7 Mermin §III canonical)

- V1: 1000 random Mermin GHZ trial 에서 classical win rate ≤ 0.75 측정 + **numerology_mc_judge gate** (random strategy distribution vs 0.75 bound MC null p ≤ 0.05)
- V2: Cooperative quantum-strategy win rate ≈ 1.0 ±5% separation + **V2-mc gate canonical p ≤ 0.01** (Python reference parity, ST I2 fix: relaxed from 0.001 strict to 0.01 canonical)
- V3: Trystero 3-player room creation latency < 5s (NAT traversal)
- V4 (absorbed into outcome-aggregator): post-round outcome collect latency < 1s p95 (Trystero classical channel, ys-* CRDT sync removed)
- V5: Koan harvest player action log deterministic mapping (no false positive) + seed-replay diff = 0

## Stack

- **TypeScript + Vite + WGSL** (browser)
- **Trystero** (P2P signaling via BitTorrent tracker, serverless) — D1 fix: explicit DEPENDS_ON ts-ice-fallback
- ~~**Yjs + y-webrtc-trystero**~~ (CRDT state replication) — **DROPPED** post ys-* redesign (cargo-cult anti-pattern for pseudo-telepathy)
- **WebGPU** compute shader (state vector evolution, ≤6 qubit)
- WebGL2 fallback for Safari pre-26 / older browsers

## Lessons cascade (4 levels) — 사용자 의심 측 3번 정당 instances

```
lesson-antichamber-visual-effects (engine-cheat-right-tool, Bruce psychology-pivot)
    ↓
lesson-333-quantum-multiplayer-game-feasibility (Trystero+Yjs+WebGPU 권장 stack)
    ↓ (SP per-leaf gate 측 surface)
lesson-333q-crdt-quantum-cargo-cult-pseudo-telepathy (Yjs mid-round CRDT 측 anti-pattern, post-round classical only)
    ↓ (ST gate 측 surface, KG hygiene)
[implicit] Contract→Contract edges 측 prose only 측 KG-resident enforcement gap (OPA dgx canonical_promotion_gate 측 prerequisite). Cross-cutting 측 ST I1 fix 측 30 edges 측 materialize.
```

## 사용자 의심 instances (방법론 자체 측 정전화)

| 측 | 사용자 발화 | 정당 사유 |
|---|---|---|
| 1 | "sp 가 이렇게 빨리될리가 없는데;" | SP 측 단순 KG write 측 shortcut. 실제 D(S) recursive subagent dispatch + per-Crystallization-Frontier-candidate Naesengmoon gate 측 미수행. 4-round D(S) 측 정직 진행 측 6→25 leaves 측 결과. |
| 2 | (C) D(S) sub-decompose 측 진지 실행 | Round 2 측 6 parents 측 6/6 NOT_ATOMIC. 22 children. Round 3+4 측 25 leaves. |
| 3 | (C) ys-* family 재설계 | Naesengmoon SP per-leaf gate 측 ys-* 5/5 spans 측 HIGH/borderline 측 surface. B1 finding (CRDT-quantum NOT_ISOMORPHIC) + Mermin §III game rule (no mid-round communication) 측 confirm → ys-* family cargo-cult anti-pattern. 4 ARCHIVED + 1 transformed → outcome-aggregator. 25 → 21 leaves. |

## 다음 단계 (SCW phase)

| Wave | parallel scope |
|---|---|
| 1.1 | sv-A + ts-ice-fallback (2 parallel, no deps) |
| 1.2 | ts-room-join + ts-ready-fsm + ts-entropy-seed + sv-B4 (4 parallel) |
| 1.21 | sv-B1 + sv-B2 + sv-B3 (3 parallel, after sv-B4) |
| 1.3 | ts-failure-telemetry + sv-C (2 parallel) |
| 2.1 | mg-rule |
| 2.2 | mg-classical |
| 2.3 | mg-quantum-encoded |
| 2.4 | mg-measurement (collapse-complete event emit) |
| 2.5 | outcome-aggregator (post-round Trystero classical channel) |
| 3.1 | kw-library + th-v1v2 (2 parallel) |
| 3.2 | kw-harvest |
| 3.3 | kw-moral-wall-ui |
| 4.1 | th-v3v5 |

각 SCW = TDD RED → GREEN → Refactor + Longinus L5-L7 forward binding (`# KG: <ref>` comment 측 source 측 add) + per-AtomicSpan Naesengmoon FulfillmentGate.

# KG: anchor-333q-greybox-demo-2026-05-20, lesson-333-quantum-multiplayer-game-feasibility-2026-05-20, lesson-antichamber-visual-effects-2026-05-20, lesson-333q-crdt-quantum-cargo-cult-pseudo-telepathy-2026-05-20, verdict-user-2026-05-20-canonical-promotion-antichamber-333q
