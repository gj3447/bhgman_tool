# APT v27 A7 Gate Hook (bhgman_tool engine/gate)

> **Absorbed**: 2026-05-14 Wave 7 P3-H from SYMPOSIUM/THEORY/APT/gate_endpoint_prototype/
> **Original verification**: 6/6 pytest PASS on dgx + OPA 0.66 (3 policy bundles: apt_phase_gates / harness / taliban)
> **RFC**: `rfc-apt-v27-A7-gate-hook-fail-closed-4-layer-2026-04-30` ACCEPTED
> **Sprint**: 3 (4주 estimate, 병렬 가능)
> **Stack**: Python 3.11+ / FastAPI / Redis (circuit breaker state) / `tenacity` (Resilience4j-style retry) / structlog

## CLI entry

```bash
bhgman-tool gate serve                       # uvicorn → http://127.0.0.1:8765
bhgman-tool gate check <gate-name> --cycle <id> --actor <name>
# or module mode:
python -m engine.gate.gate_endpoint
```

OPA Rego policies live in `engine/gate/policies/` (4 bundle dirs):
- `apt_phase_gates/` (sa_to_sp / sp_to_st / st_to_scw / fulfillment_gate / break_glass)
- `harness/constrain.rego`
- `taliban/constitutional_9.rego`
- `kg_mutations/admission_control.rego`

---

## Original prototype documentation

---

## 4-Layer 아키텍처

```
[1] Resilience4j-style timeout (500ms)
        ↓
[2] Redis 기반 circuit breaker state (영속화, gate process restart 생존)
        ↓
[3] Mandatory audit log (JFrog 패턴 — actor/timestamp/verdict)
        ↓
[4] 3 consecutive fail → PASS=false 자동 fallback + human alert (OPA 순환 lesson)
```

기존 `apt-gate-check.sh` shell script → HTTP gate endpoint 이전.

## 핵심 결정

### break-glass allowlist
- `cluster-autoscaler`, `essential-infra-pod` 등 system core entity는 fail-closed 우회 (순환 의존성 회피)
- override 사용 시 audit log 의무 + Slack/PagerDuty 알림

### 점진적 강제
- **Week 1**: `informational` 모드 — gate decision 기록만, blocker X
- **Week 2 (false-positive <5% 검증 후)**: `blocker` 모드 — actual fail-closed

### Polly v8 composition order
```
rate-limiter → timeout → circuit-breaker → retry → fallback
```

## 파일 구조

```
gate_endpoint_prototype/
├── README.md                    ← 본 파일
├── pyproject.toml
├── gate_endpoint.py             ← FastAPI 메인 (POST /gate/check)
├── circuit_breaker.py           ← Redis-backed 3-state FSM
├── audit_log.py                 ← JFrog 패턴 audit (KG `:GateAuditEntry` 노드)
├── allowlist.py                 ← break-glass essential infra 목록
├── enforcement_mode.py          ← informational vs blocker 전환 (KG slot)
├── kg_query.py                  ← Neo4j Cypher gate decision queries
└── tests/
    ├── test_gate.py
    ├── test_circuit_breaker.py
    └── test_break_glass.py
```

## API

### `POST /gate/check`

Request:
```json
{
  "gate_name": "G3.5",
  "cycle_id": "prom16-apt-v26-unresolved-4-2026-04-30",
  "actor": "haiku-A1S1",
  "context": { "expected_count": 16, "actual_count": 16 }
}
```

Response (성공):
```json
{
  "verdict": "PASS",
  "audit_id": "audit-G3.5-2026-04-30T12:34:56Z",
  "circuit_breaker_state": "CLOSED",
  "enforcement_mode": "blocker"
}
```

Response (실패, blocker 모드):
```json
{
  "verdict": "FAIL",
  "reason": "Cypher query returned partial write (12/16)",
  "audit_id": "audit-G3.5-2026-04-30T12:35:01Z",
  "circuit_breaker_state": "HALF_OPEN",
  "enforcement_mode": "blocker",
  "next_retry_at": "2026-04-30T12:35:31Z"
}
```

Response (failure, informational 모드 = 1주 점진 강제):
```json
{
  "verdict": "WOULD_FAIL",
  "reason": "...",
  "advisory_only": true,
  "audit_id": "..."
}
```

### `GET /gate/health`

Composition Root 검증:
- Neo4j 연결
- Redis 연결
- Allowlist KG node 로드
- Enforcement mode KG slot 조회

### `POST /gate/break-glass`

```json
{
  "actor": "ops-team",
  "reason": "essential-infra-pod recovery",
  "expires_at": "2026-04-30T13:00:00Z",
  "covers_gates": ["G3.5", "G6.5"]
}
```

→ 1시간 짜리 break-glass token. audit log + Slack/PagerDuty 알림 의무. quarterly review.

## Composition Root (eager validation)

서버 시작 시:
1. Neo4j health check + `MethodologyConfig_default_v27` 로드
2. Redis 연결 + `circuit:` keyspace 무결성 체크
3. KG `:BreakGlassAllowlist` 노드 로드 (essential-infra entity 목록)
4. `enforcement_mode` KG slot 조회 (`informational` / `blocker`)
5. structlog setup (audit log persistence path 검증)

위 5 중 하나라도 실패 → startup exception. shell script 폴백 X.

## Polly v8 정책 chain (Python tenacity 표현)

```python
from tenacity import (
    retry, stop_after_attempt, wait_exponential_jitter,
    retry_if_exception_type
)

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=0.1, max=2.0, jitter=0.5),
    retry=retry_if_exception_type(TransientGateError),
)
def call_kg_with_retry(query: str, params: dict, timeout_s: float = 0.5):
    # 1. rate limiter (token bucket per gate_name)
    # 2. timeout (500ms)
    # 3. circuit breaker (Redis state)
    # 4. retry (이 데코레이터)
    # 5. fallback (3 consecutive fail → human alert)
    ...
```

## 후속 sprint 의존

| Sprint | 의존 | 내용 |
|---|---|---|
| **Sprint 3 마지막 단계** | (본 prototype) | 점진 강제 1주 informational → false-positive <5% 검증 → blocker 전환 |
| **OPA Rego skeleton** | Sprint 3 완료 | Gate decision Cypher → Rego policy 변환 (FUTURE) |

## 상태

- [x] README + 명세 (본 파일)
- [x] pyproject.toml
- [x] gate_endpoint.py 골격 (FastAPI + 4-layer 인터페이스)
- [x] circuit_breaker.py (Redis-backed FSM stub)
- [x] tests/ 골격
- [ ] **Sprint 3 sub-task**: 실제 Redis 연결 + KG Cypher gate query 구현
- [ ] **Sprint 3 sub-task**: shell apt-gate-check.sh deprecate + replace
- [ ] **Sprint 3 sub-task**: 점진 강제 1주 informational + 메트릭 수집
- [ ] **Sprint 3 sub-task**: false-positive <5% 검증 후 blocker 전환
