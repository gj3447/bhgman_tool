# Contract Lifecycle FSM (Cross-Skill Shared)

> AptContract 상태 머신. ST와 SCW가 직접 관여, SA/SP는 read-only 관찰. 전이마다 Kafka 이벤트 강제.

---

## 전체 상태 다이어그램

```
+--------+  7 fields  +--------+  FulfillmentGate  +-----------+   +----------+
| Draft  |----------->| Active |------------------>| Fulfilled |-->| Archived |
+---+----+            +---+----+                   +-----+-----+   +----------+
    |                     |    +---------+               |
    | design wrong        |<---| Amended |<--------------+ regression / discovery
    v                     |    +----+----+
+----------+              +---------+  re-activation
| Rejected |
+----------+
```

---

## 상태 정의

| State | 진입 조건 | 종료 조건 |
|---|---|---|
| **Draft** | ST가 새 Contract 생성 | 7 필드 모두 채워짐 + tau_check 5/5 PASS |
| **Active** | Draft에서 7 필드 + review 완료 | FulfillmentGate 7 checks 통과 OR Amendment 트리거 |
| **Fulfilled** | SCW가 ContractMaterialized 발행 + FulfillmentGate PASS | 프로젝트 종료 OR 다운스트림 regression/new requirement |
| **Amended** | Fulfilled/Active에서 discovery/regression 발생 | Amendment 리뷰 후 Active 재진입 OR Rejected (fundamental flaw) |
| **Rejected** | Draft/Amended에서 design invalidated | terminal — 새 Contract 생성 필요 |
| **Archived** | Fulfilled + 프로젝트 완료 | terminal |

---

## 전이 표

| From | To | Trigger | Kafka Event |
|---|---|---|---|
| Draft | Active | 7 fields populated + review | `ContractActivated` |
| Draft | Rejected | Design invalidated | `ContractRejected` |
| Active | Fulfilled | FulfillmentGate 7 checks pass | `ContractMaterialized` |
| Active | Amended | Discovery during impl | `ContractAmended` |
| Fulfilled | Archived | Project complete | `ContractArchived` |
| **Fulfilled** | **Amended** | **Regression / new req** | **`ContractAmended`** |
| Amended | Active | Amendment reviewed | `ContractActivated` |
| Amended | Rejected | Fundamental design flaw | `ContractRejected` |

---

## Fulfilled → Amended 트리거 (4 종)

1. **Regression detected**: 다운스트림 Contract 변경이 이 Contract의 테스트를 깨뜨림. 자동 regression runner가 포착.
2. **New requirement**: FULFILLS_REQUIREMENT 링크로 새 요구사항 추가. 현재 구현이 만족하지 못하는 acceptance criteria 추가.
3. **Accuracy drift**: ML/비전 Contract에서 주기적 평가 결과 NFR 임계값 이하 메트릭 저하.
4. **Hardware change**: HardwareContext 노드 업데이트 (새 펌웨어, 새 모델). 현재 구현의 가정 무효화.

---

## Invariants (FSM 차원)

- **단일 상태**: 한 시점 한 Contract = 1 state. NULL = 위반.
- **terminal 격리**: Rejected/Archived는 *outgoing edge 없음*. 새 Contract 생성으로만 재진입.
- **Draft → Fulfilled 직행 FORBIDDEN**: 반드시 Active 거침. 리뷰 강제.
- **silent 전이 FORBIDDEN**: 모든 전이는 Kafka 이벤트. 이벤트 없는 SET status = 위반.
- **executor != reviewer**: Active 전이 시 review actor와 contract creator 분리 필수 (V15 검증).

---

## 검증 cypher

```cypher
-- V-FSM1: NULL status (invariant 위반)
MATCH (ct:AptContract) WHERE ct.status IS NULL OR ct.status = ''
RETURN 'V_FSM1_NullStatus' AS validation, ct.name AS contract

-- V-FSM2: 허용 안 된 상태값
MATCH (ct:AptContract) WHERE NOT ct.status IN ['Draft','Active','Fulfilled','Amended','Rejected','Archived']
RETURN 'V_FSM2_UnknownStatus' AS validation, ct.name, ct.status

-- V-FSM3: terminal에서 outgoing 전이 시도 (Rejected/Archived에서 변경)
MATCH (ct:AptContract)-[:STATE_TRANSITION]->(:ContractStateTransition {to_state:$s})
WHERE ct.status IN ['Rejected','Archived']
RETURN 'V_FSM3_TerminalEscape' AS validation, ct.name, ct.status

-- V-FSM4: silent transition (Kafka event 없는 SET)
MATCH (ct:AptContract)
WHERE ct.status_updated_at IS NOT NULL
  AND NOT EXISTS {
    MATCH (ev:KafkaEvent)
    WHERE ev.contract = ct.name AND ev.timestamp = ct.status_updated_at
  }
RETURN 'V_FSM4_SilentTransition' AS validation, ct.name, ct.status, ct.status_updated_at
```

---

## phase별 관여

| Phase | 관여 형태 |
|---|---|
| SA | read-only. Contract 존재 여부만 확인 (active anchor의 자식 atom들이 Active Contract를 가지는지). |
| SP | read-only. 분해 후 Contract 결정화는 ST에서. SP는 AtomicSpan 결정 후 ST에 위임. |
| ST | **Draft → Active 전이의 owner**. 7 필드 채우고 tau_check 통과시키고 review 수행. |
| SCW | **Active → Fulfilled 전이의 owner**. FulfillmentGate 7 checks 실행. 또한 Active → Amended (discovery), Fulfilled → Amended (regression) 전이 시작. |
| apt (oversight) | 사이클 종료 시 Archived 전이 의례. |
| apt-meta-review | Fulfilled Contract들 cross-check. Amendment trigger 감지. |

자세한 phase별 액션은 각 phase `references/` 내:
- `apt-st/references/contract_examples.md` (Draft → Active examples)
- `apt-st/references/amendment_scenarios.md` (Amended 사례)
- `apt-scw/references/fulfillment_gate.md` (Active → Fulfilled 7 check)
- `apt-scw/references/scw_handoff.md` (Amended trigger from SCW)

---

## anti-pattern

- **E-FSM1: Draft → Fulfilled 직행** — 리뷰 없이 구현 진입. Active 단계 우회 → 형식적 Contract.
- **E-FSM2: silent amendment** — Contract 수정하면서 Kafka event 미발행. 다운스트림이 옛 Contract 기준으로 코딩 → AP4 Silent Patch.
- **E-FSM3: terminal 재활용** — Rejected/Archived Contract를 update하여 재진입. 새 Contract 생성으로만 가능.
- **E-FSM4: self-review** — Active 전이 시 ST creator == reviewer. V15 위반.

---

## Academic Grounding

Contract Lifecycle FSM은 *formal methods + design-by-contract*의 결정화:

### 1. Harel's Statecharts (Harel 1987)

> Harel, D. (1987). *Statecharts: A visual formalism for complex systems*. Science of Computer Programming, 8(3), 231-274.

핵심: 단순 FSM 한계 (state explosion) 극복 — hierarchy / orthogonality / broadcast.

→ Contract FSM의 6 state (Draft/Active/Fulfilled/Amended/Rejected/Archived) + Amended↔Active 양방향 = Harel statechart pattern. Amended는 *sub-state of Active*로 볼 수도 있음 (hierarchy).

### 2. Design by Contract (Meyer 1992)

> Meyer, B. (1992). *Applying "Design by Contract"*. IEEE Computer, 25(10), 40-51.
>
> Meyer, B. (1997). *Object-Oriented Software Construction* 2nd ed. Prentice Hall.

핵심: 함수 호출은 *계약* — caller가 precondition 보장하면 callee가 postcondition 보장. Eiffel language로 직접 표현.

→ AptContract 의 7 필드 (input_type / output_type / precondition / postcondition / semantic_meaning / target_file / status) 가 Meyer DbC 직접 적용. tau_check 5/5 = Meyer 의 *contract well-formedness*.

### 3. Hoare CSP (Hoare 1978)

> Hoare, C. A. R. (1978). *Communicating Sequential Processes*. CACM, 21(8), 666-677.
>
> Hoare, C. A. R. (1985). *Communicating Sequential Processes*. Prentice Hall.

핵심: 프로세스 간 통신 = *event* (synchronous message passing). 시스템 = parallel processes.

→ Contract FSM의 Kafka event publishing = CSP event 모델. silent transition = CSP에서 *unobservable internal action* — pure functional 측면에선 OK이지만 verification 시 추적 불가.

### 4. Petri Net (Petri 1962)

> Petri, C. A. (1962). *Kommunikation mit Automaten*. PhD thesis, Univ. Bonn.

핵심: place-transition net. concurrent / non-deterministic 시스템의 graphical formalism.

→ Contract FSM이 *single state*만 갖는다는 invariant = Petri net place token = 1 (1-safe net). 동시 2 state = invariant 위반 (V-FSM1 정당화).

### 5. Liveness vs Safety Properties (Lamport 1977)

> Lamport, L. (1977). *Proving the correctness of multiprocess programs*. IEEE TSE, 3(2), 125-143.

- Safety: "something bad never happens" (e.g. Rejected에서 escape 못 함)
- Liveness: "something good eventually happens" (e.g. Active이면 결국 Fulfilled 또는 Amended)

→ V-FSM3 (terminal escape 차단) = safety. Brooks의 *project completion* = liveness. APT는 safety를 강제, liveness는 사이클 완료에 위임.

### 통합

Harel + Meyer + Hoare + Petri + Lamport = Contract FSM의 *5 학문 grounding*. 단순 status enum이 아닌 *formal verification 가능 model*.

# KG: APT_ContractLifecycle_FSM_canonical, lesson-contract-fsm-silent-transition, lesson-harel-meyer-grounding-2026-05-11
