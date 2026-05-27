# ADR: 7군단장 Legion 아키텍처 — in-process 합성 over 공유 KG substrate

- **Status**: PRELIMINARY (propose, awaiting user CANONICAL verdict)
- **Date proposed**: 2026-05-27
- **Revised**: 2026-05-27 (나생문 3중 검증 `vr-adr-seven-commander-legion-naesengmoon-3lens-2026-05-27` REQUIRES_CHANGES 0.62 반영 — Contract 1급 추가 / 재배맨 plan-first 정정 / edge dedup / feedback loop 폐합 / stigmergy 용어 정정)
- **KG ref**: `adr-seven-commander-legion-architecture-2026-05-27`
- **Parent constraints**:
  - `adr-bhgman-tool-in-process-default-2026-05-19` (in-process embedding, RPC 아님)
  - `bihaenggiman-legioncommanders-2026-05-26` (7군단장 roster + 3직교축)
  - `bihaenggiman-7commander-boundaries-2026-05-26` (USES≠IS 경계 + bright-line)
- **Authority**: 사용자 발화 2026-05-27 "bhgman 을 더욱더 위대하게 7개가 긴밀하게 연결되서" → "먼저 전체 설계도부터"

---

## Context

비행기맨 #4 산하 7군단장(프로메테우스/유레카/롱기누스/오캄/나생문/재배맨/하네스)은 KG 정전엔
명명·경계가 다 정의돼 있으나, **bhgman_tool 코드에선 불균등 + 서로 안 부름**:

| 군단장 | 본령(동사) | engine 구현 | 공개 entry | 상태 |
|---|---|---|---|---|
| 롱기누스 | 연결(바인딩) | 39 py (`longinus_drift_audit`) | `longinus_audit_impl()` | 🟢 production |
| 나생문 | 검증 | 15 py | `taliban_lens_check_impl()` | 🟢 강함 |
| 하네스 | 제약 | 10 py (`gate/policies`) | `harness_diagnose_impl()` | 🟢 강함 |
| 재배맨 | 출격 | dispatch 13 py | (MCP 내부) | 🟡 중간 |
| 프로메테우스 | 획득 | 4 py | ❌ | 🟡 약함 |
| 유레카 | 창조(귀납→추상) | 12 py — **`longinus_l8_induction`로 오명** | ❌ | 🟠 misnamed |
| 오캄 | 정리(supersession) | **0 py** | ❌ | 🔴 미구현 |

문제 둘:
1. **오캄 0줄** — 2026-05-27 Occam pass는 사람이 cypher로 손으로 함(`occam-pass-bhgman_tool-2026-05-27`). feature 아님.
2. **연결 layer 부재** — `오캄→나생문(gate)`, `유레카→롱기누스(input)` 같은 USES는 KG property에 *글로만* 있고
   실제 edge도, 코드 call도 없음. 군단장이 silo.

**단 연결의 작동 prototype은 이미 1개 존재**: `longinus_l8_induction/pipeline.py` 의
`stage_4_induce_fca`(유레카) → `stage_5_naesengmoon_gate`(나생문). induced abstract class가
나생문 gate를 거쳐 `VERDICT_PENDING` 태깅된다. 이 shape를 일반화하는 것이 본 설계의 출발점.

## Decision

7군단장을 **in-process 합성(composition) over 공유 KG substrate**로 연결한다. RPC 마이크로서비스 아님
(`in-process-default` ADR 계승 — engineboy continuous tight coupling).

### 1. Substrate (공유 버스) — 이미 존재

모든 군단장이 읽고 쓰는 단일 in-process 기층:

- **KG** = `resolver/cypher_kg_client.py::CypherKgClient` — 정전 데이터 버스. 군단장 간 데이터는 인자 전달이 아니라 **KG 노드/edge를 통해 흐른다** (KG-mediated handoff — 직접 read/write 동기 handoff이지, 간접·비동기 stigmergy 아님). 한 군단장의 output 노드가 다음 군단장의 input.
- **Contract** = 군단장 간 handoff/gate edge는 전부 **인터페이스 계약(Contract)에 bound**. Contract = APT 전역 root 공리(`apt-contract-root-axiom-2026-05-27`) + 재배맨의 dual complement. 병렬분해된 군단장 조각은 Contract 없이 compose 불가. enforcement는 `gate/` + KG-resolve 상속.
- **벡터 메모리** = `memory/vector_store.py` + `embedder.py`.
- **enforcement** = `gate/`(circuit_breaker / opa_client / policies) — 하네스의 제약이 물리적으로 거주.

### 2. 군단장 = substrate 위의 transform

각 군단장은 `(input artifacts) → (KG-tagged output)` 순수 transform. 안정적 `*_impl()` entry 하나씩.
오캄·유레카·프로메테우스도 같은 shape로 신설/정명:

```
engine/
  prometheus/   acquire:  외부 → KG :ResearchFinding         [신설/승격]
  eureka/       create:   KG 반복패턴 → KG :AbstractClass     [l8_induction 정명]
  longinus/     bind:     code ↔ KG drift/sha + KG↔KG link    [drift_audit 유지]
  occam/        cleanup:  KG+code stale → SUPERSEDED_BY/archive [신설]
  naesengmoon/  verify:   임의 artifact → :ValidationResult     [taliban 유지]
  jaebaeman/    plan-first: 계획 먼저(본질) → 병렬분해+출격(공학 그림자)  [dispatch 유지]
  harness/      constrain: 3계층 구조제약 (cross-cutting)        [gate 유지]
```

> **재배맨 본질 = plan-first 일반원칙** (`jaebaeman-planfirst-essence-reframe-2026-05-27`):
> 어떤 일이든 *계획을 먼저 세운다*가 origin level 본질. SubagentTaskSpec 출격(dispatch)은
> 병렬-default 기층 위 공학적 instantiation((b)plan-first ⊇ (a)dispatch). 7직교 partition 내
> distinguishing verb는 여전히 "출격"(boundary level, 층위 다름 — reconcile OPEN).
> **Contract는 재배맨의 dual complement** — 병렬 plan(분해) ↔ 인터페이스 계약(compose 합의)이
> 한 동전 양면. 그래서 Contract가 본 아키텍처의 1급 요소(§1).

### 3. USES call-graph (= "긴밀한 연결") — 핵심 산출물

경계 스펙의 `uses_not_is`(USES≠IS, 비대칭)를 **실제 edge + in-process call**로 materialize.
두 종류:

**(a) 파이프라인 handoff** — *데이터 흐름* 방향 (producer→consumer):
```
프로메테우스 ──acquire──▶ 롱기누스 ──bind/link──▶ 유레카 ──create──▶ 오캄 ──cleanup──▶ (loop back)
   (외부지식)         (KG 노드 엮기)         (엮인그래프서 귀납)   (대체된 낡은것 archive)
```
> ⚠ **flow ≠ USES 방향**: 데이터 flow는 producer→consumer지만 canonical USES edge는 dependency
> 방향(consumer→producer). 그래서 `유레카─USES→롱기누스`(유레카가 롱기누스의 엮인 그래프를 input으로
> 의존)는 flow `롱기누스→유레카`의 dual이다 — 같은 관계의 두 view. KG엔 USES(dependency) edge를 정전으로
> 저장, 본 flow는 그 dual 서술. **두 군단장 정렬 순서(롱기누스 vs 유레카)는 canonical USES로 확정**
> (유레카가 엮인 그래프에서 귀납 ⇒ 롱기누스가 flow상 선행).

**(b) gate USES (검증 관문)** — output을 commit하기 전 나생문이 검증:
```
유레카 ──[나생문 gate]──▶ crystallize   (이미 존재: stage_5_naesengmoon_gate)
오캄   ──[나생문 gate]──▶ archive        (2026-05-27 수동으로 한 패턴: Occam→나생문 3중)
롱기누스──[나생문 gate]──▶ FulfillmentGate (APT SCW에 이미 존재)
```

**(c) cross-cutting 2인**:
- **재배맨** = plan-first(계획 먼저)가 본질. 그 공학적 그림자로 임의 군단장을 subagent로 출격(나생문 3중도 재배맨 SOP). 모든 군단장 위에.
- **하네스** = 모든 군단장이 거주하는 3계층 scaffold(IDE-host / runtime / managed) 제약. 모든 군단장 아래.

> KG materialize 결과: **17 distinct `:LEGION_USES` edge** (중복 0 — `오캄→나생문`은 canonical gate
> 1개로 통합, manual precedent는 edge property `manual_precedent`로 흡수).

### 4. 닫힌 루프 (the great loop)

```
        ┌────────────────── 재배맨 (plan-first/dispatch, 위) ──────────────┐
        │                                                                  │
  프로메테우스 → 롱기누스 → 유레카 → 오캄 ──[나생문 gate]──┐                │
   (획득)     (연결)    (창조)   (정리)                    │                │
        ▲                                                  ▼                │
        └──────── 나생문 verdict ──(feedback)──▶ 다음 acquire ─────────────┘
        └────────────────── 하네스 (constrain, 아래) ─────────────────────┘
```

획득→연결→창조→정리가 KG를 한 바퀴 돌고, 나생문이 매 단계 gate, 재배맨이 plan-first/출격, 하네스가 제약.
**루프는 실제로 폐합됨**: `나생문 ─(feedback)→ 프로메테우스` edge를 KG에 materialize했으므로
DAG가 아니라 진짜 cycle(검증 12개 확인). 단 feedback edge는 status=PROPOSED.
피드백 루프(`agent-feedback-loop-canonical-2026-04-27`)가 이 순환의 창발 속성.

### 5. 3 직교축 (형식 속성, 유지)

- 롱기누스 = code ↔ KG (가로)
- 오캄 = 현재 ↔ 과거 (시간)
- 유레카 = 구체 ↔ 추상 (수직)

세 축이 공간적으로 직교 → 연결돼도 본령이 안 겹침. 경계 bright-line은 경계 스펙 그대로 계승.

## Consequences

**좋음**: silo 해소 / 수동 패턴(오늘 Occam→나생문)이 정식 파이프라인화 / KG-mediated handoff로 느슨한 결합 유지하며 in-process 긴밀성 확보 / Contract가 compose 보증 / 피드백 루프가 자연 창발.

**비용/리스크**: KG 버스 단일 장애점(완화: in-process replica) / 정명 시 import 경로 변경(롱기누스 path-mismatch ← 오캄/롱기누스 본인이 처리) / 순환 의존 방지 위해 USES는 비대칭 단방향 유지(ADP).

## 권장 시퀀싱 (이 ADR 이후, 별도 verdict)

1. **오캄 결정화** `engine/occam/` — 0-file 메우기 + 나생문 gate wiring (오늘 검증된 절차 코드화). 첫 실제 연결.
2. **유레카 정명** `longinus_l8_induction` → `engine/eureka/` + 유레카→롱기누스 input edge.
3. **USES edge materialize** — KG에 7군단장 call-graph를 실제 edge로(본 ADR과 함께 1차분).
4. **Legion 합성 layer** — 닫힌 루프 orchestrator (APT 사이클로 dogfood).
5. **프로메테우스 승격** — MCP tool 노출.

# KG: adr-seven-commander-legion-architecture-2026-05-27, bihaenggiman-legioncommanders-2026-05-26, bihaenggiman-7commander-boundaries-2026-05-26, adr-bhgman-tool-in-process-default-2026-05-19, occam-pass-bhgman_tool-2026-05-27
