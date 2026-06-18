# Kafka Event Convention (Cross-Skill Shared)

> APT phase 전환, Contract FSM 전이, Feedback 생성 등 *상태 변경*은 모두 Kafka 이벤트로 발행. silent SET 금지.

---

## 표준 payload 형식

```json
{
  "event_type": "ContractMaterialized",
  "timestamp": "2026-05-11T14:30:00Z",
  "correlation_id": "uuid-v4",
  "agent": "agent_scw_02",
  "branch": "feature/xxx",
  "payload": {
    "contract": "CT_xxx",
    "task": "TASK_xxx",
    "source_file": "src/xxx.py",
    "target_file": "src/xxx.py",
    "impact_tests": ["tests/test_xxx.py"],
    "baseline_results": {...},
    "post_results": {...},
    "coverage": 0.87,
    "nfr_results": {...},
    "lines": 187,
    "complexity_threshold_resolved": "cfg.complexity_threshold"
  }
}
```

### 필수 필드 (모든 이벤트 공통)

| Field | Type | Required | 설명 |
|---|---|---|---|
| `event_type` | string | yes | event 이름 (대표 목록 아래 표) |
| `timestamp` | ISO 8601 UTC | yes | 발생 시각 |
| `correlation_id` | uuid v4 | yes | 같은 phase cycle 내 이벤트 cross-link |
| `agent` | string | yes | 발행 actor 이름 (executor != reviewer 검증용) |
| `payload` | object | yes | event-specific 데이터 (아래 phase별 표) |
| `branch` | string | optional | git branch (CI 통합 시) |

---

## Event 카탈로그

### Contract FSM (8 이벤트)
- `ContractActivated` — Draft → Active 또는 Amended → Active
- `ContractRejected` — Draft → Rejected 또는 Amended → Rejected
- `ContractMaterialized` — Active → Fulfilled (FulfillmentGate 통과 evidence 포함)
- `ContractAmended` — Active/Fulfilled → Amended (discovery/regression detail 포함)
- `ContractArchived` — Fulfilled → Archived

### Phase Transition (4 이벤트)
- `PhaseHandoff_SA_to_SP` — apt-sa 완료, apt-sp 진입
- `PhaseHandoff_SP_to_ST` — apt-sp 완료, apt-st 진입
- `PhaseHandoff_ST_to_SCW` — apt-st 완료, apt-scw 진입
- `PhaseTransitionCompacted` — context compaction 발생 (preserved keys + dropped count)

### Feedback (3 이벤트)
- `FeedbackCreated` — AptFeedback 노드 생성 (discovery type + category + target phase)
- `FeedbackResolved` — AptFeedback.status='resolved' (resolution + actor)
- `MaxReturnsEscalated` — return_count > max_returns_per_span → 인간 에스컬레이션

### Test Run (2 이벤트)
- `AptTestRunCompleted` — AptTestRun 노드 생성 (environment + pass_rate + cost)
- `CIDivergenceDetected` — agent_local vs CI 결과 5% 이상 발산

### Gate (3 이벤트)
- `GateCheckPassed` — 특정 gate (SA→SP, SP→ST, ST→SCW, FulfillmentGate) PASS
- `GateCheckFailed` — gate FAIL → blocking
- `BreakGlassActivated` — break-glass allowlist 사용 (audit log 의무)

---

## payload 예시 — 대표 4개

### ContractMaterialized (SCW → Fulfilled)

```json
{
  "event_type": "ContractMaterialized",
  "timestamp": "2026-05-11T14:30:00Z",
  "correlation_id": "abc-def-uuid",
  "agent": "agent_scw_02",
  "branch": "feature/user-profile",
  "payload": {
    "contract": "CT_UserProfile_Create",
    "task": "TASK_UserProfile_Create",
    "source_file": "src/auth/user_profile.py",
    "target_file": "src/auth/user_profile.py",
    "impact_tests": [
      "tests/test_user_profile.py::test_create_returns_uuid",
      "tests/test_user_profile.py::test_password_hashed",
      "tests/test_user_profile.py::test_email_validation",
      "tests/test_user_profile.py::test_duplicate_email",
      "tests/test_user_profile.py::test_latency_p99",
      "tests/test_user_profile.py::test_memory_peak"
    ],
    "baseline_results": {"tests/test_user_profile.py": "PASS (0 tests, NEW_FILE)"},
    "post_results": {"tests/test_user_profile.py": "PASS (6 tests, 0.4s)"},
    "new_tests_added": 6,
    "coverage": 0.92,
    "nfr_results": {
      "latency_p99_ms": 45.2,
      "latency_threshold_ms": 200,
      "memory_peak_mb": 73,
      "memory_threshold_mb": 128
    },
    "lines": 85,
    "complexity_threshold_resolved": 500
  }
}
```

### FeedbackCreated (SCW PH6 → SP/ST)

```json
{
  "event_type": "FeedbackCreated",
  "timestamp": "2026-05-11T14:35:00Z",
  "correlation_id": "abc-def-uuid",
  "agent": "agent_scw_02",
  "payload": {
    "feedback": "FB_UserProfile_001",
    "discovery_type": "contract_gap",
    "category": "Missing",
    "target_phase": "PH4",
    "affected_span": "ATOM_UserProfile_Create",
    "severity": "blocking",
    "description": "postcondition은 result.id != None만 검증, 길이 36 검증 누락. 빈 문자열 가능."
  }
}
```

### PhaseHandoff_SA_to_SP

```json
{
  "event_type": "PhaseHandoff_SA_to_SP",
  "timestamp": "2026-05-11T14:00:00Z",
  "correlation_id": "abc-def-uuid",
  "agent": "agent_sa_01",
  "payload": {
    "anchor": "SA_UserProfile_Module",
    "work_kind": "NEW",
    "phase_activation_matrix_a15": "FULL",
    "l1_spans_count": 4,
    "context_budget_total": 100000,
    "next_phase": "apt-sp",
    "compacted_at": "2026-05-11T14:00:00Z"
  }
}
```

### GateCheckFailed

```json
{
  "event_type": "GateCheckFailed",
  "timestamp": "2026-05-11T14:32:00Z",
  "correlation_id": "abc-def-uuid",
  "agent": "agent_scw_02",
  "payload": {
    "gate_name": "FulfillmentGate",
    "check_failed": 5,
    "check_name": "Complexity within threshold",
    "actual_value": 678,
    "threshold_value": 500,
    "threshold_source": "cfg.complexity_threshold",
    "action": "block_materialization",
    "remediation": "return to PH3 for decomposition"
  }
}
```

---

## consumer side 검증

```python
# 검증 1: executor != reviewer (HR2, V15)
if event["event_type"] == "ContractMaterialized":
    contract_creator = kg_query(f"MATCH (c:AptContract {{name:'{event['payload']['contract']}'}})<-[:CREATED]-(a) RETURN a.name")
    if contract_creator == event["agent"]:
        flag_review(event, reason="self-approval V15 violation")

# 검증 2: silent transition (V-FSM4)
expected_event_for_status_change = {
    "Draft → Active": "ContractActivated",
    "Active → Fulfilled": "ContractMaterialized",
    # ...
}
# Contract status 변경 발견 시 해당 timestamp에 expected event 존재해야 함
```

---

## anti-pattern

- **E-K1: silent SET** — `SET ct.status='Fulfilled'` 만, Kafka 미발행. → V-FSM4가 잡음.
- **E-K2: correlation_id 누락** — 단일 사이클 내 이벤트 cross-link 불가. PROV 추적 깨짐.
- **E-K3: agent 거짓** — `agent: 'system'` 같은 일반 식별자. executor != reviewer 검증 무력화.
- **E-K4: event_type 신조어** — 카탈로그 외 임의 이름 (`MyCustomEvent`). consumer가 unknown으로 drop.
- **E-K5: payload 누락** — required 필드 빠짐. consumer fail.

---

## Academic Grounding

Kafka Event Convention은 *분산 시스템 이론*의 결정화:

### 1. Lamport's Happens-Before (Lamport 1978)

> Lamport, L. (1978). *Time, Clocks, and the Ordering of Events in a Distributed System*. CACM, 21(7), 558-565.

핵심: 분산 시스템에 *전역 시계* 없음. 인과 관계는 happens-before 부분 순서로만 정의. correlation_id가 인과 chain 추적.

→ event의 `correlation_id` (uuid)는 정확히 Lamport vector clock의 *causal ancestor identifier*. 같은 cycle 내 event들이 chain.

### 2. The Log: Unified Data Architecture (Kreps 2014)

> Kreps, J. (2014). *The Log: What every software engineer should know about real-time data's unifying abstraction*. LinkedIn Engineering blog.

핵심: append-only log = 분산 시스템의 *canonical primitive*. state = log의 fold. event sourcing.

→ APT의 *모든 phase transition / FSM transition / feedback 생성*이 Kafka log entry. KG state는 log fold. log 우선, KG는 derived view.

### 3. CloudEvents Spec (CNCF 2018)

> CNCF CloudEvents v1.0 (2019). *A specification for describing event data*. https://github.com/cloudevents/spec

핵심: 이벤트 standardization — `type`, `source`, `id`, `time`, `datacontenttype`, `data` 필드.

→ APT event format이 CloudEvents 직접 매핑:
- `event_type` → CloudEvents `type`
- `agent` → `source`
- `correlation_id` → `id`
- `timestamp` → `time`
- `payload` → `data`

### 4. CAP Theorem (Brewer 2000, Gilbert-Lynch 2002)

> Gilbert, S., & Lynch, N. (2002). *Brewer's conjecture and the feasibility of consistent, available, partition-tolerant web services*. SIGACT News, 33(2), 51-59.

핵심: Consistency + Availability + Partition tolerance 중 2개만 동시 가능.

→ Kafka는 *AP* (network partition 시 일관성 약화, availability 우선) 또는 *CP* (consumer ack 강제) 모드. APT는 *AP*로 가정 (consumer가 eventually consistent KG view).

### 5. Idempotent Producer (Kreps 2017)

> Kreps, J. (2017). *Exactly Once Semantics in Apache Kafka*. Confluent blog.

→ correlation_id + producer dedup으로 *at-most-once* OR *exactly-once*. APT는 *at-least-once*로 가정 (멱등 consumer 의무).

### 6. Anti-pattern: silent SET (E-K1) 의 학문 근거

silent state mutation = *side effect without trace* = pure functional language (Haskell)의 IO monad 우회와 동형. event log 없는 mutation은 *referentially opaque* (Strachey 1967).

> Strachey, C. (1967). *Fundamental Concepts in Programming Languages*. Lecture notes, Copenhagen.

→ E-K1을 막는 것은 *referential transparency 유지* 의무.

### 통합

Lamport + Kreps + CloudEvents + CAP + Strachey = 분산 / 이벤트 / 형식 / 일관성 / 의미 5 layer. APT event는 이 5 grounding의 교집합.

# KG: APT_KafkaEvent_convention_canonical, lesson-lamport-kreps-grounding-2026-05-11
