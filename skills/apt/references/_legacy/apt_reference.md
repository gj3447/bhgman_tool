# APT v11 — Part V: Practical Reference

> **File:** `05_reference.md` | §31–§38 | Validation, Traceability, Gap Resolution, Theory, Errors, Anti-Patterns, Feedback, Clarifications

---

## §31 Validation Queries (17)

모든 쿼리는 copy-paste 즉시 실행 가능. 결과가 **0행이면 정상**, 1행 이상이면 위반.

### V1 — A1: ContractOnlyAtST

Contract 소유자가 SemanticTwin이 아닌 경우를 탐지한다.

```cypher
// 대상: Axiom A1 — Contract는 Twin만 소유 가능
// 설명: HAS_CONTRACT 역방향 도메인이 SemanticTwin이 아닌 노드 탐지
// 예상: 0행 (위반 없음)
MATCH (x)-[:HAS_CONTRACT]->(c:AptContract)
WHERE NOT x:SemanticTwin
RETURN 'V1_A1_ContractOnlyAtST' AS validation,
       x.name AS violator,
       labels(x) AS violator_labels,
       c.name AS contract
```

### V2 — A3: SiblingIndependence

같은 부모의 자식 간 DEPENDS_ON 존재를 탐지한다.

```cypher
// 대상: Axiom A3 — 형제 간 독립성
// 설명: 동일 부모에서 DECOMPOSES_TO로 연결된 두 자식 간 DEPENDS_ON 존재 여부
// 예상: 0행
MATCH (parent)-[:DECOMPOSES_TO]->(a:AptSpan),
      (parent)-[:DECOMPOSES_TO]->(b:AptSpan)
WHERE a <> b
  AND (a)-[:DEPENDS_ON]->(b)
RETURN 'V2_A3_SiblingIndependence' AS validation,
       parent.name AS parent,
       a.name AS dependent,
       b.name AS dependency
```

### V3 — A2: RecursiveDecomposition (branching)

비원자 Span이 자식을 1개만 가진 경우를 탐지한다.

```cypher
// 대상: Axiom A2 — min_children ≥ 2
// 설명: AtomicSpan이 아닌 Span이 DECOMPOSES_TO 자식이 1개뿐인 경우
// 예상: 0행
MATCH (s:AptSpan)-[:DECOMPOSES_TO]->(child)
WHERE NOT s:AtomicSpan
WITH s, count(child) AS child_count
WHERE child_count = 1
RETURN 'V3_A2_BranchingFactor' AS validation,
       s.name AS span,
       child_count
```

### V4 — A2: Termination

리프인데 AtomicSpan이 아닌 Span을 탐지한다.

```cypher
// 대상: Axiom A2 — 모든 경로 종료
// 설명: 자식이 없는데(리프) AtomicSpan 라벨이 없는 Span
// 예상: 0행
MATCH (leaf:AptSpan)
WHERE NOT (leaf)-[:DECOMPOSES_TO]->()
  AND NOT leaf:AtomicSpan
RETURN 'V4_A2_Termination' AS validation,
       leaf.name AS unterminated_span,
       leaf.status AS status
```

### V5 — A4: CrystallizationFrontierUniqueness

CRYSTALLIZES_TO가 아닌 관계로 Span→Twin이 연결된 경우를 탐지한다.

```cypher
// 대상: Axiom A4 — SP↔ST 유일 브릿지
// 설명: AptSpan에서 SemanticTwin으로 CRYSTALLIZES_TO 외의 관계가 존재하는 경우
// 예상: 0행
MATCH (s:AptSpan)-[r]->(t:SemanticTwin)
WHERE type(r) <> 'CRYSTALLIZES_TO'
RETURN 'V5_A4_FrontierUniqueness' AS validation,
       s.name AS span,
       type(r) AS illegal_relation,
       t.name AS twin
```

### V6 — Cycle Detection

DECOMPOSES_TO 그래프에 순환이 있는지 탐지한다.

```cypher
// 대상: DECOMPOSES_TO 비순환성
// 설명: 길이 2 이상의 DECOMPOSES_TO 경로가 자기 자신으로 돌아오는 경우
// 예상: 0행
MATCH path = (s:AptSpan)-[:DECOMPOSES_TO*2..10]->(s)
RETURN 'V6_CycleDetection' AS validation,
       [n IN nodes(path) | n.name] AS cycle_nodes
LIMIT 1
```

### V7 — Injective CRYSTALLIZES_TO

하나의 AtomicSpan이 두 개 이상의 Twin에 결정화된 경우를 탐지한다.

```cypher
// 대상: CRYSTALLIZES_TO 단사성
// 설명: AtomicSpan 하나가 여러 Twin에 연결된 경우
// 예상: 0행
MATCH (a:AtomicSpan)-[:CRYSTALLIZES_TO]->(t1:SemanticTwin),
      (a)-[:CRYSTALLIZES_TO]->(t2:SemanticTwin)
WHERE t1 <> t2
RETURN 'V7_Injective' AS validation,
       a.name AS atom,
       t1.name AS twin1,
       t2.name AS twin2
```

### V8 — Functional HAS_CONTRACT

하나의 Twin이 두 개 이상의 Contract를 가진 경우를 탐지한다.

```cypher
// 대상: HAS_CONTRACT 함수성 (1 Twin → 1 Contract)
// 설명: SemanticTwin 하나에 여러 Contract가 연결된 경우
// 예상: 0행
MATCH (t:SemanticTwin)-[:HAS_CONTRACT]->(c1:AptContract),
      (t)-[:HAS_CONTRACT]->(c2:AptContract)
WHERE c1 <> c2
RETURN 'V8_Functional' AS validation,
       t.name AS twin,
       c1.name AS contract1,
       c2.name AS contract2
```

### V9 — Label Disjointness

금지된 라벨 조합을 가진 노드를 탐지한다.

```cypher
// 대상: 집합 분리성 (𝔄∩𝕊=∅, 𝕊∩𝕋=∅, 𝕋∩𝕂=∅)
// 설명: AptSpan+SemanticTwin 또는 SemanticTwin+AptContract 동시 라벨 탐지
// 예상: 0행
MATCH (n)
WHERE (n:AptSpan AND n:SemanticTwin)
   OR (n:SemanticTwin AND n:AptContract)
   OR (n:AptContract AND n:SemanticTask)
RETURN 'V9_Disjoint' AS validation,
       n.name AS node,
       labels(n) AS conflicting_labels
```

### V10 — Duplicate Twin Names

같은 이름의 SemanticTwin이 여러 개인 경우를 탐지한다.

```cypher
// 대상: SemanticTwin 이름 유일성
// 설명: 동일 이름의 Twin 노드가 2개 이상
// 예상: 0행
MATCH (tw:SemanticTwin)
WITH tw.name AS twin_name, count(tw) AS cnt
WHERE cnt > 1
RETURN 'V10_DuplicateTwin' AS validation,
       twin_name,
       cnt
```

### V11 — Null Status

핵심 노드에 status 프로퍼티가 없는 경우를 탐지한다.

```cypher
// 대상: status 필드 무결성
// 설명: AptSpan, SemanticTwin, AptContract 중 status가 null인 노드
// 예상: 0행
MATCH (n)
WHERE (n:AptSpan OR n:SemanticTwin OR n:AptContract)
  AND n.status IS NULL
RETURN 'V11_NullStatus' AS validation,
       n.name AS node,
       labels(n) AS node_labels
```

### V12 — Orphan Contract

어떤 Twin에도 연결되지 않은 고아 Contract를 탐지한다.

```cypher
// 대상: Contract 연결 무결성
// 설명: HAS_CONTRACT 역방향이 없는 AptContract
// 예상: 0행
MATCH (ct:AptContract)
WHERE NOT ()-[:HAS_CONTRACT]->(ct)
RETURN 'V12_OrphanContract' AS validation,
       ct.name AS orphan_contract,
       ct.status AS status
```

### V13 — Chain Completeness

루트에서 AtomicSpan까지 전체 체인 (Atom→Twin→Contract)이 완전한지 검증한다.

```cypher
// 대상: SA→SP→ST→SCW 전체 체인 완전성
// 설명: 루트 하위 모든 AtomicSpan에 대해 Twin, Contract 수가 일치하는지 확인
// 예상: 0행 (atoms=twins=contracts이면 정상)
MATCH (root:AptSpan {name: $root})-[:DECOMPOSES_TO*1..6]->(a:AtomicSpan)
WITH DISTINCT a
OPTIONAL MATCH (a)-[:CRYSTALLIZES_TO]->(tw:SemanticTwin)
OPTIONAL MATCH (tw)-[:HAS_CONTRACT]->(ct:AptContract)
WITH count(DISTINCT a) AS atoms,
     count(DISTINCT tw) AS twins,
     count(DISTINCT ct) AS contracts
WHERE atoms <> twins OR twins <> contracts
RETURN 'V13_ChainCompleteness' AS validation,
       atoms, twins, contracts
```

### V14 — Hub Integrity

atom 역할의 INVOLVES가 없는 CrystallizationEvent를 탐지한다.

```cypher
// 대상: CrystallizationEvent 허브 무결성
// 설명: INVOLVES {role:'atom'} 엣지가 없는 허브
// 예상: 0행
MATCH (cx:CrystallizationEvent)
WHERE NOT (cx)-[:INVOLVES {role: 'atom'}]->()
RETURN 'V14_HubIntegrity' AS validation,
       cx.name AS incomplete_hub
```

### V15 — Self-Approval

executor가 자기 자신을 승인한 경우를 탐지한다.

```cypher
// 대상: executor ≠ reviewer 규칙
// 설명: AtomicSpan의 executor가 APPROVED_BY 대상 agent와 동일인
// 예상: 0행
MATCH (s:AtomicSpan)-[:APPROVED_BY]->(r:AptAgent)
WHERE s.executor = r.name
RETURN 'V15_SelfApproval' AS validation,
       s.name AS span,
       r.name AS self_approver
```

### V16 — Sparse Links

INFORMED_BY 엣지가 부족한 AtomicSpan을 탐지한다.

```cypher
// 대상: Design Principle D4 — DenseBeforeContract
// 설명: INFORMED_BY 엣지 수가 config.min_informed_by(기본 5) 미만인 AtomicSpan
// 예상: 0행 (품질 경고, P4 심각도)
MATCH (s:AtomicSpan)
WITH s, size([(s)-[:INFORMED_BY]->() | 1]) AS link_count
WHERE link_count < 5
RETURN 'V16_SparseLinks' AS validation,
       s.name AS span,
       link_count
```

### V17 — Stale Lock

1시간 이상 잠긴 Contract를 탐지한다.

```cypher
// 대상: Contract 잠금 타임아웃
// 설명: locked_by가 있고 locked_at이 1시간 이상 경과한 Contract
// 예상: 0행
MATCH (ct:AptContract)
WHERE ct.locked_by IS NOT NULL
  AND ct.locked_at < datetime() - duration('PT1H')
RETURN 'V17_StaleLock' AS validation,
       ct.name AS contract,
       ct.locked_by AS held_by,
       ct.locked_at AS since
```

---

## §32 Requirement Traceability

### 개념

**SemanticWorkQueue**는 요구사항(Requirement)을 작업 큐로 변환하는 개념적 계층이다. 외부 요구사항이 KG에 `Requirement` 노드로 들어오면, Span 또는 Twin이 `FULFILLS_REQUIREMENT` 관계로 연결한다. **RequirementSpan**은 요구사항 범위를 나타내는 속성으로, 하나의 Requirement가 여러 Span/Twin에 걸칠 수 있다.

### Query 1 — Link: 요구사항 → Span 연결

```cypher
// 요구사항을 Span에 연결
MERGE (req:Requirement {name: $req_name})
SET req.description = $description, req.priority = $priority, req.source = $source
WITH req
MATCH (s:AptSpan {name: $span_name})
MERGE (s)-[:FULFILLS_REQUIREMENT {
  coverage: $coverage,
  linked_at: datetime(),
  linked_by: $agent
}]->(req)
RETURN req.name, s.name
```

### Query 2 — Trace: 요구사항 → 소스코드 추적

```cypher
// 요구사항에서 소스코드까지 전체 추적
MATCH (req:Requirement {name: $req_name})<-[:FULFILLS_REQUIREMENT]-(s)
OPTIONAL MATCH (s)-[:CRYSTALLIZES_TO]->(tw:SemanticTwin)
OPTIONAL MATCH (tw)-[:HAS_CONTRACT]->(ct:AptContract)
OPTIONAL MATCH (ct)-[:MATERIALIZES]->(src:SourceCodeNode)
RETURN req.name AS requirement,
       s.name AS span,
       tw.name AS twin,
       ct.name AS contract,
       src.file_path AS source_file,
       ct.status AS contract_status
ORDER BY s.name
```

### Query 3 — Unfulfilled: 미충족 요구사항 탐지

```cypher
// FULFILLS_REQUIREMENT 역방향이 없거나 contract가 미완인 요구사항
MATCH (req:Requirement)
OPTIONAL MATCH (req)<-[:FULFILLS_REQUIREMENT]-(s)
OPTIONAL MATCH (s)-[:CRYSTALLIZES_TO]->(tw)-[:HAS_CONTRACT]->(ct)
WITH req,
     count(DISTINCT s) AS span_count,
     count(DISTINCT ct) AS contract_count,
     collect(DISTINCT ct.status) AS statuses
WHERE span_count = 0
   OR contract_count < span_count
   OR ANY(st IN statuses WHERE st <> 'fulfilled')
RETURN req.name AS unfulfilled_requirement,
       req.priority AS priority,
       span_count,
       contract_count,
       statuses
ORDER BY req.priority DESC
```

---

## §33 Gap Resolution — Thompson Sampling

### 개요

Gap은 KG에서 발견된 지식 공백이다. Thompson Sampling으로 후보를 평가하여 최적 해법을 선택한다.

### 전체 루프

```
1. Gap 발견 → AptFeedback 생성 (category: 'Missing')
2. 후보 생성 → GapCandidate 노드 (70% KG 기존 패턴, 30% 탐색적 신규 접근)
3. 실험 수행 → 각 후보에 대해 소규모 PoC
4. 점수 업데이트 → positive/negative 카운트
5. 선택 → adopt 또는 reject 기준 충족 시 결정
```

### 규칙

| 규칙 | 설명 |
|------|------|
| **70/30 비율** | 후보 생성 시 70%는 KG 내 기존 패턴에서 도출 (exploitation), 30%는 신규 접근 (exploration) |
| **3× 금지** | 동일 후보가 3회 이상 실험되면 추가 실험 금지. 데이터 충분 → 판단 |
| **Adopt 기준** | positive ≥ 3 AND negative ≤ 1 → 채택 |
| **Reject 기준** | negative ≥ 3 → 폐기 |
| **중립 상태** | 위 기준 미충족 시 추가 실험 또는 인간 판단 위임 |

### Cypher — 후보 생성

```cypher
// Gap에 대한 후보 노드 생성
MERGE (gap:AptFeedback {name: $gap_name})
SET gap.category = 'Missing', gap.status = 'open'
WITH gap
MERGE (cand:GapCandidate {name: $candidate_name})
SET cand.approach = $approach,
    cand.source = $source_type,  // 'exploitation' | 'exploration'
    cand.positive = 0,
    cand.negative = 0,
    cand.trials = 0,
    cand.status = 'pending'
MERGE (gap)-[:HAS_CANDIDATE]->(cand)
RETURN gap.name, cand.name
```

### Cypher — 점수 업데이트

```cypher
// 실험 결과 반영
MATCH (cand:GapCandidate {name: $candidate_name})
WHERE cand.trials < 3  // 3× 금지 규칙
SET cand.trials = cand.trials + 1,
    cand.positive = CASE WHEN $result = 'positive'
                         THEN cand.positive + 1
                         ELSE cand.positive END,
    cand.negative = CASE WHEN $result = 'negative'
                         THEN cand.negative + 1
                         ELSE cand.negative END,
    cand.status = CASE
      WHEN cand.positive + (CASE WHEN $result='positive' THEN 1 ELSE 0 END) >= 3
           AND cand.negative + (CASE WHEN $result='negative' THEN 1 ELSE 0 END) <= 1
      THEN 'adopted'
      WHEN cand.negative + (CASE WHEN $result='negative' THEN 1 ELSE 0 END) >= 3
      THEN 'rejected'
      ELSE 'pending'
    END,
    cand.last_trial = datetime()
RETURN cand.name, cand.status, cand.positive, cand.negative, cand.trials
```

### Thompson Sampling 선택

```cypher
// Beta 분포 기반 후보 순위 (근사: positive/(positive+negative+1))
MATCH (gap:AptFeedback {name: $gap_name})-[:HAS_CANDIDATE]->(cand)
WHERE cand.status = 'pending' AND cand.trials < 3
RETURN cand.name,
       cand.approach,
       cand.source,
       cand.positive,
       cand.negative,
       toFloat(cand.positive + 1) / (cand.positive + cand.negative + 2) AS thompson_score
ORDER BY thompson_score DESC
```

> **참고:** 실제 Thompson Sampling은 Beta(positive+1, negative+1) 분포에서 샘플링한다. Cypher에서는 평균값 근사를 사용하고, 실제 샘플링은 애플리케이션 코드에서 수행한다.

---

## §34 Theoretical Foundations

9개 이론 도메인과 APT 대응 요소. 정직한 프레이밍 (Wolfram 교정 반영).

| # | Domain | APT Element | Description |
|---|--------|-------------|-------------|
| 1 | **Dynamic Programming** | SP decomposition | SP의 재귀 분해는 독립 부분문제로 분할하고, AtomicSpan은 메모이제이션된 해(solution)에 해당한다. 중복 계산을 KG 조회로 대체한다. DP의 최적 부분구조 성질을 차용하되, APT에서는 최적성 증명은 없다. |
| 2 | **P-Coalgebra** | DECOMPOSES_TO | DECOMPOSES_TO는 종료 조건이 있는 분기 시스템(branching system with termination)이다. 범주론적 functor가 아니라 coalgebraic 관점에서의 관찰 가능한 행동(observable behavior) 모델이다. 형식적 최종성(finality) 증명은 제공하지 않는다. |
| 3 | **Hoare Logic** | Contract, SEQUENCED_WITH | Contract는 {P}f{Q} Hoare triple의 **유비(analogy)**이다. SEQUENCED_WITH는 순차 합성 규칙을 반영한다. 단, Curry-Howard 대응이 아니며, 테스트는 부분적 반박(partial refutation)일 뿐 보편적 증명이 아니다. |
| 4 | **Extended Mind** | KG (Knowledge Graph) | Clark & Chalmers(1998)의 확장된 마음 가설에 따라, KG는 에이전트의 인지를 증강하는 외부 기억이다. 인간 주의(attention) 모델이 아니며, Context Budget은 공학적 휴리스틱이다. |
| 5 | **Thompson Sampling** | Gap Resolution | 지식 공백 해소 시 exploitation/exploration 균형을 위해 Beta 분포 기반 Thompson Sampling을 사용한다. 70/30 비율은 경험적 설정이며, 이론적 최적성 보장은 없다. |
| 6 | **DDD (Domain-Driven Design)** | Bounded Context, Ubiquitous Language | Span은 bounded context에 대응하고, Contract의 타입 시스템은 ubiquitous language를 강제한다. DDD의 전략적 설계 패턴을 차용하되, aggregate root 개념은 직접 매핑하지 않는다. |
| 7 | **CSP (Communicating Sequential Processes)** | Agent → Kafka → KG | 에이전트 간 통신은 공유 메모리가 아닌 Kafka 채널을 통한 CSP 모델이다. 실제로 CSP 의미론을 따르며, 단일 KG writer가 순차 처리를 보장한다. |
| 8 | **Kuhn / Gödel** | Version Evolution, §1 | v1→v11의 진화는 Kuhn의 패러다임 전환을 반영한다. Gödel 불완전성을 인정하여 σ_oracle의 계산적 비환원성(computational irreducibility)을 명시한다. |
| 9 | **Wolfram Hypergraph** | Bipartite Incidence, EXPLORES_VIA, Confluence | CrystallizationEvent는 **bipartite incidence encoding**이지 native hyperedge가 아니다. EXPLORES_VIA는 multiway branch에 유비되며, 두 대안이 동등한 결과를 낼 때 CONFLUENT_WITH로 기록한다. Wolfram 물리학의 인과 그래프는 Kafka 이벤트 순서로 근사된다. |

---

## §35 Error Cases (10)

### E1 — PH3→PH5 Skip (단계 건너뛰기)

**Context:** 에이전트가 Span 분해(PH3)를 마치자마자 Contract 없이 바로 코딩(PH5)에 진입. ST 단계를 건너뛰어 Contract가 없는 상태에서 코드를 작성함.
**Lesson:** Contract 없는 코딩은 vibe coding이다. 타입 불일치와 암묵적 가정이 통합 시점에 폭발한다.
**Guard:** D9 GenerativeFlowOrdering 강제. Phase Detection 쿼리(§12)를 구현 전 실행하여 현재 위상 확인.

```cypher
// Guard: 구현 전 위상 검증
MATCH (span:AptSpan {name: $target})
OPTIONAL MATCH (span)-[:CRYSTALLIZES_TO]->(st)-[:HAS_CONTRACT]->(c)
WITH span, c
WHERE c IS NULL
RETURN 'BLOCKED: No Contract for ' + span.name AS error
```

### E2 — Asyncio Lock at Import

**Context:** Python 모듈 최상단에서 `asyncio.Lock()`을 생성하면 import 시점에 이벤트 루프가 없어 `RuntimeError` 발생.
**Lesson:** 비동기 리소스는 반드시 이벤트 루프 내에서 초기화해야 한다.
**Guard:** lazy initialization 패턴 사용. Contract에 precondition으로 "event loop running" 명시.

```python
# BAD — import 시점에 lock 생성
import asyncio
_lock = asyncio.Lock()  # RuntimeError: no running event loop

# GOOD — lazy init
_lock: asyncio.Lock | None = None

def get_lock() -> asyncio.Lock:
    global _lock
    if _lock is None:
        _lock = asyncio.Lock()
    return _lock
```

### E3 — WebSocket Heartbeat Mismatch

**Context:** 클라이언트와 서버의 heartbeat 주기가 달라 연결이 끊어지는데, 양쪽 모두 상대가 죽었다고 판단. 데이터 유실.
**Lesson:** 통신 프로토콜의 타이밍 파라미터는 Contract에 명시해야 한다.
**Guard:** Contract의 `nfr_heartbeat_interval_ms` 필드로 양측 타이밍 합의. acceptance test에 heartbeat 시나리오 포함.

### E4 — Register Format Mismatch

**Context:** 하드웨어 레지스터 읽기에서 big-endian/little-endian 불일치. 값이 잘못 해석되어 장비 오작동.
**Lesson:** 바이트 오더는 암묵적 가정이 아닌 Contract의 input_type에 명시해야 한다.
**Guard:** Contract에 `input_type: 'bytes[4], endian=little'`처럼 엔디안 명시. acceptance test에 바이트 오더 검증 포함.

### E5 — SSH CLOSE_WAIT Saturation

**Context:** 에이전트가 SSH 연결을 닫지 않아 CLOSE_WAIT 상태 소켓이 누적. OS 파일 디스크립터 한도 도달 후 전체 서비스 중단.
**Lesson:** 연결 풀 크기와 해제를 config로 관리해야 한다.
**Guard:** `config.max_agents` 풀 제한. context manager(with문)로 연결 보장. 모니터링에 CLOSE_WAIT 카운트 SLI 추가.

```python
# Guard: context manager로 SSH 연결 관리
async with ssh_pool.acquire(timeout=config.lock_timeout_minutes * 60) as conn:
    result = await conn.execute(command)
# 자동 해제 보장
```

### E6 — Neo4j Wrong Port

**Context:** 환경별 Neo4j 포트가 다른데(로컬 7687, 스테이징 17687) 하드코딩하여 연결 실패.
**Lesson:** 인프라 설정은 KG AptConfig 노드 또는 apt-config.yaml에서 읽어야 한다.
**Guard:** Config from KG 패턴. 환경별 설정을 `config.environments` 섹션에서 관리.

### E7 — External SDK Version Mismatch

**Context:** 외부 SDK의 특정 API를 사용했으나, 프로젝트에서 사용하는 SDK 버전에서는 지원되지 않아 런타임 에러.
**Lesson:** 외부 의존성 제약은 Contract에 명시해야 한다.
**Guard:** HardwareContext 노드에 constraints 기록. Contract의 `nfr_hw_constraints` 필드와 REQUIRES_HARDWARE 관계.

### E8 — Self-Approval

**Context:** 에이전트가 자기가 작성한 Span에 대해 σ 승인을 자기가 수행. 검증 무의미화.
**Lesson:** 분리 의무(separation of duties)가 품질의 최후 방어선이다.
**Guard:** V15 쿼리 15분 주기 cron 실행. `executor ≠ reviewer` 규칙을 Kafka consumer에서 검증.

### E9 — MERGE+SET Last-Write-Wins 충돌

**Context:** 두 에이전트가 동시에 같은 노드에 MERGE+SET 실행. 나중 쓰기가 이전 값 덮어씀.
**Lesson:** 동시 쓰기는 단일 writer로 직렬화해야 한다.
**Guard:** Kafka single writer 패턴. 모든 KG 쓰기는 Kafka 이벤트를 통해 단일 consumer가 순차 처리.

### E10 — σ-First Order Waste (v10 이전 문제)

**Context:** v10 이전에는 σ(인간 검토)를 먼저 수행. 복잡도(ν) 위반처럼 자동으로 걸러낼 수 있는 Span에도 4시간 SLA 인간 검토를 기다림.
**Lesson:** 비용이 낮은 자동 검사를 먼저 수행하여 비싼 인간 검토를 절약한다.
**Guard:** v11 평가 순서: ν→τ→ι→δ→σ (cheap first). 자동 게이트가 먼저 거부하면 σ_oracle 요청 안 함.

---

## §36 Anti-Patterns (9)

### AP1 — Gold Plating (과잉 구현)

**Signal:** Contract에 없는 기능을 추가한다. "있으면 좋을 것 같아서" 코드가 늘어난다.
**Guard:** FulfillmentGate 7가지 검사 중 "Output type matches contract.output_type"이 과잉 산출물을 차단. Contract 필드에 명시된 것만 구현한다.
**Example:** Contract에 `output_type: str`인데 `Dict[str, Any]`를 반환하여 추가 메타데이터를 제공 → FulfillmentGate 실패.

### AP2 — Spec Amnesia (명세 망각)

**Signal:** 코딩 중 Contract를 다시 읽지 않는다. 기억에 의존하여 postcondition을 놓친다.
**Guard:** SCW 진입 시 Contract 재로딩을 의무화. KG ref 주석(`# KG: CT_xxx`)으로 Contract 추적.
**Example:** `postcondition: 'len(result) <= 100'`을 잊고 길이 제한 없이 구현 → 테스트에서 포착되어야 하지만, 테스트도 누락.

### AP3 — Test Afterthought (테스트 후행)

**Signal:** 코드를 먼저 작성하고 테스트를 나중에 맞춘다. RED 단계 건너뜀.
**Guard:** TDAD — RED 단계에서 테스트 FAIL 확인 필수. 새 파일은 `["NEW_FILE"]` 마커로 baseline skip하되 RED는 mandatory.
**Example:** 구현 후 테스트가 항상 PASS → 테스트가 postcondition을 검증하지 않고 trivial assert만 포함.

### AP4 — Silent Patch (무언 수정)

**Signal:** 버그를 발견하고 조용히 고친다. AptFeedback 없이 코드만 변경.
**Guard:** AptFeedback 생성 필수. PH6에서 Kafka FeedbackCreated 이벤트 발행. KG에 수정 이력 기록.
**Example:** 타입 불일치 발견 → Contract 수정 없이 코드만 변경 → 나중에 다른 에이전트가 이전 Contract 기준으로 코딩하여 충돌.

### AP5 — Monolith Creep (모놀리스 비대화)

**Signal:** 파일이 점점 커지는데 분해하지 않는다. 복잡도 임계값(500줄) 초과.
**Guard:** ν(복잡도) 게이트가 자동 탐지. FulfillmentGate에서 `complexity ≤ threshold` 검사. 위반 시 SP 재분해.
**Example:** 유틸리티 함수가 계속 추가되어 800줄 → V 검사에서 탐지 → 부모 Span으로 돌아가 재분해.

### AP6 — Vibe Coding (감 코딩)

**Signal:** Contract 없이 "이렇게 하면 될 것 같다"로 코딩. 결정의 근거가 KG에 없다.
**Guard:** 모든 결정을 Contract에 추적. D9 GenerativeFlowOrdering으로 SA→SP→ST→SCW 순서 강제. Phase Detection 쿼리.
**Example:** "일단 만들고 나중에 Contract 작성" → E1(단계 건너뛰기) 에러와 동일 결과.

### AP7 — Self-Approval (자기 승인)

**Signal:** executor가 reviewer를 겸한다. "내가 보니까 괜찮다."
**Guard:** V15 쿼리로 자동 탐지. Kafka consumer에서 `executor ≠ reviewer` 검증. 위반 시 APPROVED_BY 삭제 후 재승인 요구.
**Example:** 에이전트 A가 Span 작성 + σ 승인 → V15에서 탐지 → P1 알림 → 승인 무효화.

### AP8 — Trivial Tests (형식적 테스트)

**Signal:** 테스트가 postcondition을 검증하지 않는다. `assert True` 수준.
**Guard:** Test-Contract alignment gate — 테스트가 실제로 postcondition을 검증하는지 확인. coverage ≥ config.coverage_threshold.
**Example:** `def test_parse(): assert parse_args is not None` → postcondition 검증 안 함 → alignment gate 실패.

### AP9 — NFR Amnesia (비기능요건 망각)

**Signal:** 기능은 동작하지만 latency, memory, accuracy 검증을 건너뛴다. 프로덕션에서 성능 문제 발생.
**Guard:** D10 NFR as First-Class. Contract의 `nfr_*` 필드가 설정되어 있으면 stochastic test 필수. FulfillmentGate 7번째 검사.
**Example:** `nfr_latency_p99_ms: 200` 설정인데 latency 테스트 없이 배포 → 프로덕션에서 p99 500ms → 장애.

---

## §37 Feedback System

### 10 Categories

| # | Category | 설명 |
|---|----------|------|
| 1 | **Bug** | 코드 결함. postcondition 위반. |
| 2 | **Confusion** | 명세 모호성. 해석 분기 발생. |
| 3 | **Missing** | 누락된 Span, Contract, 또는 테스트. |
| 4 | **Improvement** | 기능 개선 요청. 현재 동작은 정상. |
| 5 | **Violation** | Axiom 또는 Principle 위반 탐지. |
| 6 | **Conflict** | 두 Contract 또는 Span 간 모순. |
| 7 | **FalsePositive** | 검증이 정상을 위반으로 오탐. |
| 8 | **FalseNegative** | 검증이 위반을 정상으로 미탐. |
| 9 | **PerformanceDrift** | 성능 메트릭(정확도, 처리량 등)이 기준선 이하로 하락. |
| 10 | **SLABreach** | SLA 초과. 응답 시간 또는 처리량 제약 위반. |

### Cypher — 피드백 생성

```cypher
MERGE (fb:AptFeedback {name: $title})
SET fb.category = $category,
    fb.severity = $severity,
    fb.status = 'open',
    fb.description = $description,
    fb.created_at = datetime(),
    fb.created_by = $agent,
    fb.target_span = $target_span,
    fb.target_contract = $target_contract
WITH fb
OPTIONAL MATCH (s:AptSpan {name: $target_span})
FOREACH (_ IN CASE WHEN s IS NOT NULL THEN [1] ELSE [] END |
  MERGE (fb)-[:TARGETS]->(s)
)
RETURN fb.name, fb.status
```

### Cypher — 피드백 조회

```cypher
// 카테고리별 열린 피드백 조회
MATCH (fb:AptFeedback)
WHERE fb.status = 'open'
RETURN fb.category AS category,
       count(fb) AS open_count,
       collect(fb.name) AS feedback_items
ORDER BY open_count DESC
```

### Cypher — 피드백 해결

```cypher
MATCH (fb:AptFeedback {name: $title})
SET fb.status = 'resolved',
    fb.resolved_at = datetime(),
    fb.resolved_by = $agent,
    fb.resolution = $resolution
RETURN fb.name, fb.status, fb.resolution
```

### 사용 규칙

1. **Silent Patch 금지** — 코드 변경 시 반드시 AptFeedback 생성.
2. **Max returns** — 동일 Span에 대해 `config.max_returns_per_span`(기본 3) 회 초과 피드백 → 인간 에스컬레이션.
3. **Severity 기준** — Bug/Violation: P1–P2, Missing/Conflict: P2–P3, 나머지: P3–P4.
4. **카테고리 정확성** — FalsePositive/FalseNegative는 검증 시스템 자체의 문제. 검증 로직 수정 필요.
5. **PerformanceDrift/SLABreach** — NFR 관련. Contract의 nfr_* 필드 재교정 + 재실험 트리거.

---

## §38 Clarification Notes (26)

| # | Title | Key Point |
|---|-------|-----------|
| **C1** | Prior Methods as Tactics | 기존 방법론(TDD, DDD 등)은 APT의 부분 전술이다. APT가 이들을 포괄하는 상위 프레임워크 역할을 한다. |
| **C2** | LeafSpan vs AtomicSpan | LeafSpan은 자식이 없는 상태(state)이고, AtomicSpan은 C(S)=true + σ 승인이라는 판단(judgment)이다. 리프라고 자동으로 원자적이지 않다. |
| **C3** | Bottom-Up Ascent | Code→Contract(추론)→Twin→Span 순서의 역방향 구축. `source:'bottom_up'` 표기. σ-gate(σ_auto+σ_oracle) 필수. |
| **C4** | Contract as Shared Surface | Contract는 양방향 공유 표면이다. 소비자와 생산자 모두 Contract를 기준으로 작업한다. |
| **C5** | Contract Dual Existence | Contract는 KG(정본)와 코드(구현체)에 이중 존재한다. KG가 canonical이고 코드는 materialization이다. |
| **C6** | CrystallizationFrontier | SP↔ST 경계의 명명된 프론티어. CRYSTALLIZES_TO 관계가 이 경계를 구성한다. |
| **C7** | Canonical ≠ Synced Duplicate | KG의 Contract는 의미 노드(semantic node)이지 코드의 동기화된 복사본이 아니다. |
| **C8** | Independent Branch Progression | 하나의 branch가 siblings보다 먼저 ST에 진입할 수 있다. A3 독립성 덕분에 병렬 진행 가능. |
| **C9** | KG Sparsity Impact | KG가 빈약하면 과거 버전들에서 경험한 오독(misreading)이 발생한다. D4 DenseBeforeContract가 방어. |
| **C10** | L3 Contract = Bridge Surface | L3 수준의 Contract는 전체 의미 도메인이 아닌 브릿지 표면(bridge surface)이다. 필요한 만큼만 명세한다. |
| **C11** | Depth Varies by Project | 분해 깊이는 프로젝트 규모에 따라 다르다. 소규모는 2단계, 대규모는 6단계 이상 가능. |
| **C12** | Legacy Methods as Sub-Elements | 기존 개발 방법론(Scrum, Kanban 등)은 APT의 하위 요소로 매핑 가능하다. |
| **C13** | KG=Metadata, Git=Code | KG는 메타데이터의 진실의 원천, Git은 코드의 진실의 원천. 둘은 보완적이지 대체적이지 않다. |
| **C14** | Span = Inhabitant of SP | Span은 SP world의 거주자(inhabitant)이지 SP 자체가 아니다. SP는 world, Span은 element이다. |
| **C15** | N:N DAG, Not Tree | DECOMPOSES_TO는 N:N DAG이다. 하나의 Span이 여러 부모를 가질 수 있다. A3는 각 부모별로 적용된다. |
| **C16** | Span-to-Contract Shorthand | "Span에서 Contract로"는 축약 표현. 실제는 Span→(CRYSTALLIZES_TO)→Twin→(HAS_CONTRACT)→Contract (A1). |
| **C17** | TDD at Contract→SCW | TDD는 Contract→SourceCode 단계(PH5)에서 수행한다. SP 단계에서의 테스트는 해당 없음. |
| **C18** | Hub = Bipartite Incidence | CrystallizationEvent 허브는 bipartite incidence encoding이다. Native hyperedge가 아니다. 기능적으로 동등하지만 구조적으로 다르다. |
| **C19** | Task ≠ Contract | Task는 자연어 스캐폴딩(NL scaffolding)이고 Contract는 형식적 명세(formal spec)이다. Task는 사라져도 Contract는 남는다. |
| **C20** | δ Prevents Over-Decomposition | δ(Decomposition Diseconomy)는 100줄 미만 조각으로의 과잉 분해를 방지한다. "이미 원자적"이면 병합 상향. |
| **C21** | ATOM_/SPAN_ = Convention | ATOM_/SPAN_ 접두사는 명명 규약이다. 진실은 is_atomic 프로퍼티 + C(S) 판정 결과에 있다. |
| **C22** | SpanPlanningNature | Span은 추상적 의미(meaning)를 기술한다. 코드 구조나 파일 경로가 아니다. |
| **C23** | EXPLORES_VIA ≠ DECOMPOSES_TO | EXPLORES_VIA는 대안(alternatives), DECOMPOSES_TO는 부분(parts). 전자는 선택, 후자는 전부 필요. |
| **C24** | NFR as First-Class | 비기능요건(latency, memory, accuracy, hardware)은 Contract의 일급 필드이다. 후순위가 아니다. |
| **C25** | σ = σ_auto + σ_oracle | σ는 자동화 가능한 부분(σ_auto: 용어 커버리지, 도메인 온톨로지 매칭)과 계산적으로 비환원적인 인간 판단(σ_oracle)으로 구성된다. |
| **C26** | Context Budget = Engineering Heuristic | Context Budget(50K/20K/8K)은 인지과학이 아닌 공학적 휴리스틱이다. 경험적으로 설정한 토큰 제한. |

---

*APT v11 §31–§38. 17 Validation Queries · Requirement Traceability · Thompson Sampling Gap Resolution · 9 Theoretical Foundations · 10 Error Cases · 9 Anti-Patterns · 10-Category Feedback System · 26 Clarification Notes.*
# APT v11 — Part VI: Tutorials

> **File:** `06_tutorial.md` | §39–§40 | Hello World Full Cycle, E-Commerce Search Example

---

## §39 Hello World — Full Cycle (Both Spans)

완전한 SA→SP→ST→SCW 사이클을 두 Span 모두에 대해 축약 없이 수행한다.

### 프로젝트 개요

CLI 프로그램 `hello_apt`: `--name Alice` 인자를 파싱하고, "Hello, Alice!" 형식의 인사말을 출력한다.

- **ATOM_HelloAPT_ParseArgs** — argv에서 `--name` 인자를 추출
- **ATOM_HelloAPT_FormatGreeting** — 이름으로 인사말 문자열 생성

---

### Span 1: ParseArgs

#### Step 1 — SA: SemanticAnchor 생성

```cypher
MERGE (sa:SemanticAnchor {name: 'HelloAPT'})
SET sa.domain = 'tutorial',
    sa.status = 'active',
    sa.created_at = datetime(),
    sa.description = 'CLI that greets users by name'
RETURN sa.name, sa.domain
```

#### Step 2 — Root Span 생성

```cypher
MERGE (root:AptSpan {name: 'SPAN_HelloAPT_Root'})
SET root.description = 'CLI that parses --name and prints greeting',
    root.depth = 0,
    root.status = 'active'
MERGE (sa:SemanticAnchor {name: 'HelloAPT'})
MERGE (sa)-[:DECOMPOSES_TO]->(root)
RETURN root.name, root.depth
```

#### Step 3 — Decompose: 두 자식 Span 생성

```cypher
// 자식 1: ParseArgs
MERGE (c1:AptSpan {name: 'ATOM_HelloAPT_ParseArgs'})
SET c1.description = 'Parse --name argument from argv',
    c1.depth = 1,
    c1.is_atomic = true,
    c1.status = 'active',
    c1.executor = 'agent_alpha'

// 자식 2: FormatGreeting
MERGE (c2:AptSpan {name: 'ATOM_HelloAPT_FormatGreeting'})
SET c2.description = 'Format greeting string with parsed name',
    c2.depth = 1,
    c2.is_atomic = true,
    c2.status = 'active',
    c2.executor = 'agent_alpha'

// 부모 연결
MERGE (root:AptSpan {name: 'SPAN_HelloAPT_Root'})
MERGE (root)-[:DECOMPOSES_TO]->(c1)
MERGE (root)-[:DECOMPOSES_TO]->(c2)

RETURN c1.name, c2.name
```

#### Step 4 — C(S) Check: ParseArgs

각 술어를 순서대로 판정한다 (cheap first):

| 순서 | 술어 | 판정 | 근거 |
|:----:|------|:----:|------|
| 1st | **ν** (Complexity) | PASS | 예상 코드 ~10줄. 임계값 500줄 이하. |
| 2nd | **τ** (Type Expressibility) | PASS | input: `argv: list[str]`, output: `str`. 구체적 타입. |
| 3rd | **ι** (Test Feasibility) | PASS | `assert parse_args(["app","--name","Alice"]) == "Alice"` — 구체적 assert 가능. |
| 4th | **δ** (Decomposition Diseconomy) | PASS | ~10줄이므로 추가 분할 시 오히려 비경제적. 이미 원자적. |
| 5th | **σ** (Semantic Completeness) | PENDING | σ_auto: "parse", "argv", "name" 용어 커버리지 충분. σ_oracle: reviewer 승인 필요. |

#### Step 5 — σ Approval

```cypher
// σ_oracle: reviewer_1이 승인 (executor agent_alpha ≠ reviewer reviewer_1)
MERGE (atom:AptSpan {name: 'ATOM_HelloAPT_ParseArgs'})
SET atom:AtomicSpan
MERGE (reviewer:AptAgent {name: 'reviewer_1'})
MERGE (atom)-[:APPROVED_BY {
  criterion: 'sigma',
  approved_at: datetime(),
  comment: 'Single responsibility, concrete types, testable'
}]->(reviewer)
RETURN atom.name, reviewer.name
```

#### Step 6 — Crystallize: Twin + Task + Contract + Hub

```cypher
// Twin
MERGE (atom:AtomicSpan {name: 'ATOM_HelloAPT_ParseArgs'})
MERGE (twin:SemanticTwin {name: 'ST_HelloAPT_ParseArgs'})
SET twin.status = 'crystallized', twin.created_at = datetime()
MERGE (atom)-[:CRYSTALLIZES_TO]->(twin)

// Task (NL scaffolding)
MERGE (task:SemanticTask {name: 'TASK_HelloAPT_ParseArgs'})
SET task.description = 'Parse the --name argument from command-line argv',
    task.acceptance_criteria = 'Returns the name string when --name is present. Raises ValueError when --name is missing.',
    task.target_file = 'hello_apt/cli.py',
    task.impact_tests = ['tests/test_cli.py::test_parse_args', 'tests/test_cli.py::test_parse_args_missing']
MERGE (twin)-[:HAS_TASK]->(task)

// Contract (formal spec)
MERGE (ct:AptContract {name: 'CT_HelloAPT_ParseArgs'})
SET ct.input_type = 'argv: list[str]',
    ct.output_type = 'str',
    ct.precondition = '--name flag exists in argv and is followed by a value',
    ct.postcondition = 'result == argv[argv.index("--name") + 1]',
    ct.acceptance_tests = [
      'parse_args(["app", "--name", "Alice"]) == "Alice"',
      'parse_args(["app"]) raises ValueError',
      'parse_args(["app", "--name"]) raises IndexError'
    ],
    ct.status = 'active',
    ct.created_at = datetime()
MERGE (twin)-[:HAS_CONTRACT]->(ct)

// CrystallizationEvent Hub
MERGE (hub:CrystallizationEvent {name: 'CX_HelloAPT_ParseArgs'})
SET hub.status = 'crystallized', hub.created_at = datetime()
MERGE (hub)-[:INVOLVES {role: 'atom'}]->(atom)
MERGE (hub)-[:INVOLVES {role: 'twin'}]->(twin)
MERGE (hub)-[:INVOLVES {role: 'task'}]->(task)
MERGE (hub)-[:INVOLVES {role: 'contract'}]->(ct)

RETURN atom.name, twin.name, ct.name, hub.name
```

#### Step 7 — TDD: RED → GREEN → REFACTOR

**RED — 테스트 작성 (FAIL 확인)**

```python
# tests/test_cli.py — RED phase
# KG: TASK_HelloAPT_ParseArgs | CT_HelloAPT_ParseArgs

import pytest


def test_parse_args():
    """CT postcondition: result == argv[argv.index('--name') + 1]"""
    from hello_apt.cli import parse_args
    assert parse_args(["app", "--name", "Alice"]) == "Alice"


def test_parse_args_different_name():
    """CT postcondition with different input"""
    from hello_apt.cli import parse_args
    assert parse_args(["app", "--name", "Bob"]) == "Bob"


def test_parse_args_missing():
    """CT precondition violation: --name not in argv → ValueError"""
    from hello_apt.cli import parse_args
    with pytest.raises(ValueError, match="--name required"):
        parse_args(["app"])


def test_parse_args_no_value():
    """CT edge case: --name present but no following value → IndexError"""
    from hello_apt.cli import parse_args
    with pytest.raises(IndexError):
        parse_args(["app", "--name"])
```

```bash
$ pytest tests/test_cli.py -v
# FAIL — ModuleNotFoundError: No module named 'hello_apt' ✓ (RED confirmed)
```

**GREEN — 구현**

```python
# hello_apt/cli.py — GREEN phase
# KG: TASK_HelloAPT_ParseArgs | CT_HelloAPT_ParseArgs


def parse_args(argv: list[str]) -> str:
    """Parse --name argument from argv.

    Precondition: --name flag exists in argv and is followed by a value.
    Postcondition: result == argv[argv.index('--name') + 1]
    """
    if "--name" not in argv:
        raise ValueError("--name required")
    return argv[argv.index("--name") + 1]
```

```bash
$ pytest tests/test_cli.py -v
# 4 passed ✓ (GREEN confirmed)
# Complexity: 6 lines (threshold: 500) ✓
# Coverage: 100% ✓
```

**REFACTOR** — 6줄이므로 리팩토링 불필요. GREEN 유지 확인.

#### Step 8 — Record: SourceCodeNode 등록

```cypher
MERGE (src:SourceCodeNode {name: 'SRC_HelloAPT_ParseArgs'})
SET src.file_path = 'hello_apt/cli.py',
    src.lines = 6,
    src.status = 'implemented',
    src.implemented_at = datetime(),
    src.executor = 'agent_alpha'
MERGE (ct:AptContract {name: 'CT_HelloAPT_ParseArgs'})
MERGE (ct)-[:MATERIALIZES]->(src)
SET ct.status = 'fulfilled'
MERGE (hub:CrystallizationEvent {name: 'CX_HelloAPT_ParseArgs'})
MERGE (hub)-[:INVOLVES {role: 'source'}]->(src)

RETURN src.name, src.file_path, ct.status
```

---

### Span 2: FormatGreeting (Full Cycle)

#### Step 1 — C(S) Check: FormatGreeting

| 순서 | 술어 | 판정 | 근거 |
|:----:|------|:----:|------|
| 1st | **ν** (Complexity) | PASS | 예상 코드 ~5줄. 임계값 500줄 이하. |
| 2nd | **τ** (Type Expressibility) | PASS | input: `name: str`, output: `str`. 구체적 타입. |
| 3rd | **ι** (Test Feasibility) | PASS | `assert format_greeting("Alice") == "Hello, Alice!"` — 구체적 assert 가능. |
| 4th | **δ** (Decomposition Diseconomy) | PASS | ~5줄이므로 추가 분할 시 비경제적. 이미 원자적. |
| 5th | **σ** (Semantic Completeness) | PENDING | σ_auto: "format", "greeting", "name" 용어 충분. σ_oracle: reviewer 승인 필요. |

#### Step 2 — σ Approval

```cypher
MERGE (atom:AptSpan {name: 'ATOM_HelloAPT_FormatGreeting'})
SET atom:AtomicSpan
MERGE (reviewer:AptAgent {name: 'reviewer_1'})
MERGE (atom)-[:APPROVED_BY {
  criterion: 'sigma',
  approved_at: datetime(),
  comment: 'Pure function, single responsibility, trivially testable'
}]->(reviewer)
RETURN atom.name, reviewer.name
```

#### Step 3 — Crystallize: Twin + Task + Contract + Hub

```cypher
// Twin
MERGE (atom:AtomicSpan {name: 'ATOM_HelloAPT_FormatGreeting'})
MERGE (twin:SemanticTwin {name: 'ST_HelloAPT_FormatGreeting'})
SET twin.status = 'crystallized', twin.created_at = datetime()
MERGE (atom)-[:CRYSTALLIZES_TO]->(twin)

// Task (NL scaffolding)
MERGE (task:SemanticTask {name: 'TASK_HelloAPT_FormatGreeting'})
SET task.description = 'Format a greeting string given a parsed name',
    task.acceptance_criteria = 'Returns "Hello, {name}!" for any non-empty name. Raises ValueError for empty string.',
    task.target_file = 'hello_apt/greeter.py',
    task.impact_tests = ['tests/test_greeter.py::test_format_greeting', 'tests/test_greeter.py::test_format_greeting_empty']
MERGE (twin)-[:HAS_TASK]->(task)

// Contract (formal spec)
MERGE (ct:AptContract {name: 'CT_HelloAPT_FormatGreeting'})
SET ct.input_type = 'name: str',
    ct.output_type = 'str',
    ct.precondition = 'len(name) > 0',
    ct.postcondition = 'result == f"Hello, {name}!"',
    ct.acceptance_tests = [
      'format_greeting("Alice") == "Hello, Alice!"',
      'format_greeting("Bob") == "Hello, Bob!"',
      'format_greeting("") raises ValueError'
    ],
    ct.status = 'active',
    ct.created_at = datetime()
MERGE (twin)-[:HAS_CONTRACT]->(ct)

// CrystallizationEvent Hub
MERGE (hub:CrystallizationEvent {name: 'CX_HelloAPT_FormatGreeting'})
SET hub.status = 'crystallized', hub.created_at = datetime()
MERGE (hub)-[:INVOLVES {role: 'atom'}]->(atom)
MERGE (hub)-[:INVOLVES {role: 'twin'}]->(twin)
MERGE (hub)-[:INVOLVES {role: 'task'}]->(task)
MERGE (hub)-[:INVOLVES {role: 'contract'}]->(ct)

RETURN atom.name, twin.name, ct.name, hub.name
```

#### Step 4 — TDD: RED → GREEN → REFACTOR

**RED — 테스트 작성 (FAIL 확인)**

```python
# tests/test_greeter.py — RED phase
# KG: TASK_HelloAPT_FormatGreeting | CT_HelloAPT_FormatGreeting

import pytest


def test_format_greeting():
    """CT postcondition: result == f'Hello, {name}!'"""
    from hello_apt.greeter import format_greeting
    assert format_greeting("Alice") == "Hello, Alice!"


def test_format_greeting_bob():
    """CT postcondition with different input"""
    from hello_apt.greeter import format_greeting
    assert format_greeting("Bob") == "Hello, Bob!"


def test_format_greeting_empty():
    """CT precondition violation: empty name → ValueError"""
    from hello_apt.greeter import format_greeting
    with pytest.raises(ValueError, match="name must not be empty"):
        format_greeting("")


def test_format_greeting_whitespace():
    """Edge case: whitespace-only name should still work (non-empty)"""
    from hello_apt.greeter import format_greeting
    assert format_greeting(" ") == "Hello,  !"
```

```bash
$ pytest tests/test_greeter.py -v
# FAIL — ModuleNotFoundError: No module named 'hello_apt.greeter' ✓ (RED confirmed)
```

**GREEN — 구현**

```python
# hello_apt/greeter.py — GREEN phase
# KG: TASK_HelloAPT_FormatGreeting | CT_HelloAPT_FormatGreeting


def format_greeting(name: str) -> str:
    """Format greeting with the given name.

    Precondition: len(name) > 0
    Postcondition: result == f"Hello, {name}!"
    """
    if not name:
        raise ValueError("name must not be empty")
    return f"Hello, {name}!"
```

```bash
$ pytest tests/test_greeter.py -v
# 4 passed ✓ (GREEN confirmed)
# Complexity: 5 lines (threshold: 500) ✓
# Coverage: 100% ✓
```

**REFACTOR** — 5줄이므로 리팩토링 불필요. GREEN 유지 확인.

#### Step 5 — Record: SourceCodeNode 등록

```cypher
MERGE (src:SourceCodeNode {name: 'SRC_HelloAPT_FormatGreeting'})
SET src.file_path = 'hello_apt/greeter.py',
    src.lines = 5,
    src.status = 'implemented',
    src.implemented_at = datetime(),
    src.executor = 'agent_alpha'
MERGE (ct:AptContract {name: 'CT_HelloAPT_FormatGreeting'})
MERGE (ct)-[:MATERIALIZES]->(src)
SET ct.status = 'fulfilled'
MERGE (hub:CrystallizationEvent {name: 'CX_HelloAPT_FormatGreeting'})
MERGE (hub)-[:INVOLVES {role: 'source'}]->(src)

RETURN src.name, src.file_path, ct.status
```

#### Step 6 — Contract Sequential Composition (SEQUENCED_WITH)

ParseArgs의 output이 FormatGreeting의 input이 된다:

```cypher
// Hoare triple chaining: {P1}parse:list[str]→str{Q1}, {P2}format:str→str{Q2}, Q1⊢P2
MATCH (ct1:AptContract {name: 'CT_HelloAPT_ParseArgs'})
MATCH (ct2:AptContract {name: 'CT_HelloAPT_FormatGreeting'})
MERGE (ct1)-[:SEQUENCED_WITH {
  justification: 'ct1.output_type=str, ct2.input_type=str. ct1.postcondition(result is name string) entails ct2.precondition(len(name)>0) when --name has a value.',
  linked_at: datetime()
}]->(ct2)
RETURN ct1.name, ct2.name
```

---

### V13 Chain Completeness 검증

두 Span 모두 완료 후 전체 체인이 완전한지 검증한다:

```cypher
// V13: 루트 하위 모든 AtomicSpan에 대해 atoms=twins=contracts 확인
MATCH (root:AptSpan {name: 'SPAN_HelloAPT_Root'})-[:DECOMPOSES_TO*1..6]->(a:AtomicSpan)
WITH DISTINCT a
OPTIONAL MATCH (a)-[:CRYSTALLIZES_TO]->(tw:SemanticTwin)
OPTIONAL MATCH (tw)-[:HAS_CONTRACT]->(ct:AptContract)
OPTIONAL MATCH (ct)-[:MATERIALIZES]->(src:SourceCodeNode)
WITH count(DISTINCT a) AS atoms,
     count(DISTINCT tw) AS twins,
     count(DISTINCT ct) AS contracts,
     count(DISTINCT src) AS sources
RETURN atoms, twins, contracts, sources,
       CASE
         WHEN atoms = twins AND twins = contracts AND contracts = sources
         THEN 'COMPLETE — all chains fulfilled'
         ELSE 'INCOMPLETE — missing links detected'
       END AS chain_status
// 예상 결과: atoms=2, twins=2, contracts=2, sources=2, chain_status='COMPLETE'
```

추가 검증 — 허브 무결성:

```cypher
// V14: 모든 CrystallizationEvent에 atom, twin, task, contract, source 역할 존재 확인
MATCH (cx:CrystallizationEvent)
WHERE cx.name STARTS WITH 'CX_HelloAPT_'
WITH cx,
     size([(cx)-[:INVOLVES {role:'atom'}]->() | 1]) AS has_atom,
     size([(cx)-[:INVOLVES {role:'twin'}]->() | 1]) AS has_twin,
     size([(cx)-[:INVOLVES {role:'task'}]->() | 1]) AS has_task,
     size([(cx)-[:INVOLVES {role:'contract'}]->() | 1]) AS has_contract,
     size([(cx)-[:INVOLVES {role:'source'}]->() | 1]) AS has_source
RETURN cx.name,
       has_atom, has_twin, has_task, has_contract, has_source,
       CASE
         WHEN has_atom=1 AND has_twin=1 AND has_task=1 AND has_contract=1 AND has_source=1
         THEN 'WELL_FORMED'
         ELSE 'INCOMPLETE'
       END AS hub_status
// 예상: 두 허브 모두 WELL_FORMED
```

---

## §40 Advanced Example: E-Commerce Search — Full Cycle

### 프로젝트 개요

**ECommerceSearch**: 상품 검색 서비스. L2_SearchEngine은 사용자 쿼리에 대해 최적의 검색 결과를 반환하는 모듈이다. 여러 검색 엔진 대안을 탐색(EXPLORES_VIA)하여 벤치마크 후 최적 엔진을 선택한다.

### Exploration 구조

```
SA: ECommerceSearch
└── L2_SearchEngine
    ├── EXPLORES_VIA {strategy:'best_of_n'} → L3_ElasticSearch    (오픈소스, 자체 호스팅)
    ├── EXPLORES_VIA {strategy:'best_of_n'} → L3_Meilisearch      (경량 오픈소스)
    ├── EXPLORES_VIA {strategy:'best_of_n'} → L3_Algolia           (SaaS, 관리형)
    └── DECOMPOSES_TO → L3_EngineSelection                         (벤치마크, 승자 선택)
```

#### Exploration Span 생성

```cypher
// L2 부모 + 3 대안 + Selection Span
MERGE (parent:AptSpan {name: 'L2_SearchEngine'})
SET parent.description = 'Full-text product search with ranking and filtering',
    parent.depth = 2,
    parent.status = 'active'

// 대안 1: ElasticSearch
MERGE (alt1:AptSpan {name: 'L3_ElasticSearch'})
SET alt1.description = 'Search via ElasticSearch with BM25 + custom scoring',
    alt1.depth = 3,
    alt1.is_atomic = true,
    alt1.status = 'active',
    alt1.executor = 'agent_search'
MERGE (parent)-[:EXPLORES_VIA {strategy: 'best_of_n'}]->(alt1)

// 대안 2: Meilisearch
MERGE (alt2:AptSpan {name: 'L3_Meilisearch'})
SET alt2.description = 'Search via Meilisearch typo-tolerant engine',
    alt2.depth = 3,
    alt2.is_atomic = true,
    alt2.status = 'active',
    alt2.executor = 'agent_search'
MERGE (parent)-[:EXPLORES_VIA {strategy: 'best_of_n'}]->(alt2)

// 대안 3: Algolia
MERGE (alt3:AptSpan {name: 'L3_Algolia'})
SET alt3.description = 'Search via Algolia managed search-as-a-service',
    alt3.depth = 3,
    alt3.is_atomic = true,
    alt3.status = 'active',
    alt3.executor = 'agent_search'
MERGE (parent)-[:EXPLORES_VIA {strategy: 'best_of_n'}]->(alt3)

// Selection Span (벤치마크)
MERGE (sel:AptSpan {name: 'L3_EngineSelection'})
SET sel.description = 'Benchmark alternatives and select best search engine',
    sel.depth = 3,
    sel.status = 'active',
    sel.executor = 'agent_eval'
MERGE (parent)-[:DECOMPOSES_TO]->(sel)

RETURN alt1.name, alt2.name, alt3.name, sel.name
```

---

### L3_ElasticSearch — Full Cycle

#### C(S) Check

| 순서 | 술어 | 판정 | 근거 |
|:----:|------|:----:|------|
| 1st | **ν** | PASS | ElasticSearch 어댑터 ~180줄. 임계값 500줄 이하. |
| 2nd | **τ** | PASS | input: `SearchQuery{query:str, filters:dict, page:int}`, output: `SearchResult{items:list[Product], total:int}`. 구체적 타입. |
| 3rd | **ι** | PASS | `assert len(result.items) <= page_size and result.total >= 0` 가능. |
| 4th | **δ** | PASS | 인덱싱과 검색을 분리하면 파이프라인 무결성 상실. 하나의 원자 단위가 적절. |
| 5th | **σ** | PASS | σ_auto: search, indexing, ranking 도메인 용어 충분. σ_oracle: reviewer 승인. |

#### σ Approval + Crystallize

```cypher
// σ approval
MERGE (atom:AptSpan {name: 'L3_ElasticSearch'})
SET atom:AtomicSpan
MERGE (reviewer:AptAgent {name: 'reviewer_backend'})
MERGE (atom)-[:APPROVED_BY {
  criterion: 'sigma',
  approved_at: datetime(),
  comment: 'Well-defined search adapter. Concrete I/O types. Testable with fixture data.'
}]->(reviewer)

// Twin
MERGE (twin:SemanticTwin {name: 'ST_ECommerce_ElasticSearch'})
SET twin.status = 'crystallized', twin.created_at = datetime()
MERGE (atom)-[:CRYSTALLIZES_TO]->(twin)

// Task
MERGE (task:SemanticTask {name: 'TASK_ECommerce_ElasticSearch'})
SET task.description = 'Implement ElasticSearch adapter for product search with BM25 scoring and faceted filtering',
    task.acceptance_criteria = 'Returns ranked products matching query. Supports category/price filters. p99 latency < 200ms. Memory < 512MB.',
    task.target_file = 'src/search/elastic_adapter.py',
    task.impact_tests = [
      'tests/test_search.py::test_elastic_basic_query',
      'tests/test_search.py::test_elastic_filters',
      'tests/test_search.py::test_elastic_latency'
    ]
MERGE (twin)-[:HAS_TASK]->(task)
```

#### L3_ElasticSearch Contract (NFR + HW Context 포함)

```cypher
// Contract with NFR and HW context
MERGE (ct:AptContract {name: 'CT_ECommerce_ElasticSearch'})
SET ct.input_type = 'query: SearchQuery{query:str, filters:dict[str,Any], page:int, page_size:int}',
    ct.output_type = 'SearchResult{items:list[Product], total:int, facets:dict[str,list]}',
    ct.precondition = 'len(query.query) > 0 and query.page >= 1 and query.page_size > 0 and query.page_size <= 100',
    ct.postcondition = 'len(result.items) <= query.page_size and result.total >= 0 and all(item.score > 0 for item in result.items)',
    ct.acceptance_tests = [
      'basic_query: "laptop" returns products with laptop in title/description',
      'filter_category: category="electronics" filters correctly',
      'filter_price: price_min=100, price_max=500 filters correctly',
      'empty_query: raises ValueError',
      'latency: p99 < 200ms on GPU server for ML ranking'
    ],
    ct.nfr_latency_p99_ms = 200,
    ct.nfr_accuracy_metric = 'nDCG@10',
    ct.nfr_accuracy_threshold = 0.7,
    ct.nfr_memory_mb = 512,
    ct.nfr_execution_env = 'gpu_server',
    ct.status = 'active',
    ct.created_at = datetime()
MERGE (twin:SemanticTwin {name: 'ST_ECommerce_ElasticSearch'})
MERGE (twin)-[:HAS_CONTRACT]->(ct)

// Hardware Context (GPU server for ML ranking)
MERGE (hw:HardwareContext {name: 'HW_GPU_Server'})
SET hw.type = 'gpu',
    hw.model = 'NVIDIA A100 80GB',
    hw.constraints = 'CUDA 12.0+ required. TDP 400W. Used for ML-based re-ranking.'
MERGE (ct)-[:REQUIRES_HARDWARE {criticality: 'optional', note: 'GPU for ML ranking, CPU fallback exists'}]->(hw)

// Hub
MERGE (atom:AtomicSpan {name: 'L3_ElasticSearch'})
MERGE (hub:CrystallizationEvent {name: 'CX_ECommerce_ElasticSearch'})
SET hub.status = 'crystallized', hub.created_at = datetime()
MERGE (hub)-[:INVOLVES {role: 'atom'}]->(atom)
MERGE (hub)-[:INVOLVES {role: 'twin'}]->(twin)
MERGE (hub)-[:INVOLVES {role: 'task'}]->(task)
MERGE (hub)-[:INVOLVES {role: 'contract'}]->(ct)

RETURN ct.name, ct.nfr_latency_p99_ms, ct.nfr_execution_env
```

---

### Selection Span at Parent Level

L3_EngineSelection은 parent(L2_SearchEngine)의 DECOMPOSES_TO 자식이다. 각 대안의 벤치마크를 수행하고 승자를 선정한다.

```cypher
MERGE (sel:AptSpan {name: 'L3_EngineSelection'})
SET sel:AtomicSpan
MERGE (reviewer:AptAgent {name: 'reviewer_backend'})
MERGE (sel)-[:APPROVED_BY {criterion: 'sigma', approved_at: datetime()}]->(reviewer)

MERGE (twin:SemanticTwin {name: 'ST_ECommerce_EngineSelection'})
SET twin.status = 'crystallized'
MERGE (sel)-[:CRYSTALLIZES_TO]->(twin)

MERGE (ct:AptContract {name: 'CT_ECommerce_EngineSelection'})
SET ct.input_type = 'candidates: list[SearchResult], benchmark_queries: list[str]',
    ct.output_type = 'selected: str (candidate name), report: BenchmarkReport',
    ct.precondition = 'len(candidates) >= 2 and len(benchmark_queries) > 0',
    ct.postcondition = 'selected is name of candidate with best (nDCG, latency) Pareto rank',
    ct.acceptance_tests = [
      'with known rankings → selects correct winner',
      'tie-breaking: same nDCG → lower latency wins',
      'report contains per-candidate metrics'
    ],
    ct.status = 'active'
MERGE (twin)-[:HAS_CONTRACT]->(ct)

RETURN sel.name, ct.name
```

---

### CT_SearchIndex_Build — Full Contract

검색 엔진에 상품 데이터를 색인(indexing)하는 구체적 계약이다. ElasticSearch 어댑터의 상위 데이터 처리 Contract.

```cypher
MERGE (ct:AptContract {name: 'CT_SearchIndex_Build'})
SET ct.input_type = 'products: list[Product{id:str, title:str, description:str, price:float, category:str}]',
    ct.output_type = 'IndexResult{indexed_count:int, failed_count:int, errors:list[str]}',
    ct.precondition = 'len(products) > 0 and all(p.id and p.title for p in products)',
    ct.postcondition = 'result.indexed_count + result.failed_count == len(products) and result.indexed_count > 0',
    ct.acceptance_tests = [
      'bulk_index: 1000 products indexed successfully',
      'duplicate_id: same id updates existing document',
      'missing_title: product without title → in errors list',
      'empty_list: raises ValueError',
      'large_batch: 100K products indexed in < 60s',
      'partial_failure: some invalid → indexed_count + failed_count == total',
      'latency: single batch of 1000 p99 < 5s'
    ],
    ct.nfr_latency_p99_ms = 5000,
    ct.nfr_memory_mb = 1024,
    ct.nfr_execution_env = 'gpu_server',
    ct.status = 'active',
    ct.created_at = datetime()

// Twin + Task 연결
MERGE (twin:SemanticTwin {name: 'ST_ECommerce_SearchIndex'})
SET twin.status = 'crystallized'
MERGE (task:SemanticTask {name: 'TASK_ECommerce_SearchIndex'})
SET task.description = 'Build search index from product catalog with bulk insert and error handling',
    task.acceptance_criteria = 'Bulk index with partial failure handling. p99 < 5s for 1000 products.',
    task.target_file = 'src/search/indexer.py',
    task.impact_tests = [
      'tests/test_indexer.py::test_bulk_index',
      'tests/test_indexer.py::test_partial_failure',
      'tests/test_indexer.py::test_latency'
    ]
MERGE (twin)-[:HAS_TASK]->(task)
MERGE (twin)-[:HAS_CONTRACT]->(ct)

// SEQUENCED_WITH: SearchIndex의 output이 ElasticSearch adapter의 input으로 연결
MERGE (ct_search:AptContract {name: 'CT_ECommerce_ElasticSearch'})
MERGE (ct)-[:SEQUENCED_WITH {
  justification: 'SearchIndex builds the index that ElasticSearch adapter queries. Index.postcondition(indexed_count > 0) entails ElasticSearch.precondition(index exists with searchable documents).'
}]->(ct_search)

RETURN ct.name, ct.input_type, ct.output_type, size(ct.acceptance_tests) AS test_count
// 예상: test_count = 7
```

---

*APT v13 §39–§40. Hello World 2-Span Full Cycle (ParseArgs + FormatGreeting) with V13 verification. E-Commerce Search Exploration Pattern with NFR, Hardware Context, Selection Span, and CT_SearchIndex_Build 7-test Contract.*
