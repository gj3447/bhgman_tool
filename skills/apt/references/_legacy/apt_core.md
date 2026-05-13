# Part I: Foundations (기초)

> **APT Foundations** | [← index.md](index.md)
> 이 파일은 APT의 수학적·인식론적 기초를 다룬다.
> This file covers APT's mathematical and epistemological foundations.

---

## §1 Epistemological Honesty (인식론적 정직성)

### 1.1 세계 가정: 폐쇄 세계 가정 (World Assumption: CWA)

APT는 **폐쇄 세계 가정 (Closed World Assumption, CWA)** 을 채택한다. KG에 존재하지 않는 것은 거짓(false)으로 간주한다. 검증 쿼리는 **부재(absence)** 를 통해 위반을 감지한다.

APT adopts the **Closed World Assumption (CWA)**. What is not in the KG is considered false. Validation queries detect violations by absence.

예를 들어, V4 쿼리는 "분해되지 않았으면서(DECOMPOSES_TO 엣지 없음) AtomicSpan도 아닌 Span"을 찾는다. CWA 하에서 엣지가 없으면 분해가 일어나지 않은 것이다.

For example, V4 finds "Spans with no DECOMPOSES_TO edge that are not AtomicSpan." Under CWA, absence of the edge means decomposition has not occurred.

### 1.2 의사결정 프레임워크, 힐베르트 체계가 아님 (Decision Framework, not Hilbert)

이 명세는 **의사결정 프레임워크**이지, 힐베르트식 공리 체계가 아니다. "공리(Axiom)"라 부르는 것은 존재론적 진리(IS)가 아니라 규범적 제약(OUGHT)이다. 이를 솔직하게 인정한다.

This spec is a **decision framework**, not a Hilbertian axiom system. What we call "Axioms" are normative constraints (OUGHT), not ontological truths (IS). We acknowledge this openly.

- 완전성(completeness)이나 독립성(independence) 증명을 주장하지 않는다.
- 공리를 위반하면 "APT가 아니다"는 뜻이지, "논리적 모순"이라는 뜻이 아니다.
- We do not claim completeness or independence proofs.
- Violating an axiom means "not APT", not "logical contradiction".

### 1.3 형식적 유비에 대하여 (On Formal Analogies)

APT는 여러 수학적·철학적 개념을 **유비(analogy)** 로 사용하되, 동치(identity)로 혼동하지 않는다:

APT uses several mathematical and philosophical concepts as **analogies**, never confusing them with identities:

| 유비 (Analogy) | 정확한 관계 (Precise Relationship) | 흔한 오해 (Common Misconception) |
|---------------|----------------------------------|-------------------------------|
| Contract ≈ Hoare triple {P}f{Q} | 유비(analogy). Contract은 전·후조건과 타입 시그니처를 가진다. | Curry-Howard 대응이 **아니다**. Contract이 증명(proof)은 아니다. 테스트는 유한한 반증 시도(partial refutation)이다. |
| DECOMPOSES_TO ≈ P-coalgebra | **P-coalgebra** (종료 조건이 있는 분기 시스템). 상태 s가 자식 집합 D(s)로 전이하며, AtomicSpan에서 종료한다. | **Functor가 아니다.** 범주론적 함자 법칙(항등, 합성)을 만족시키지 않는다. coalgebra의 분기 구조만 빌려 쓴다. |
| KG ≈ Extended Mind | Clark & Chalmers (1998)의 확장된 마음. KG가 에이전트의 인지(cognition)를 증강한다. 에이전트가 KG 없이는 완전한 맥락을 가질 수 없다. | 인간 주의(attention) 모델이 **아니다**. Context Budget(D6)은 인지과학이 아니라 **공학적 휴리스틱**이다. |
| CrystallizationEvent ≈ hyperedge | **이분 발생 인코딩 (bipartite incidence encoding)**. 속성 그래프에서 하이퍼엣지를 표현하는 표준 그래프 이론 기법이다. | **네이티브 하이퍼엣지가 아니다.** Wolfram 스타일 하이퍼그래프의 네이티브 하이퍼엣지와 구조적으로 다르다. 기능적으로는 동치(functionally equivalent)이다. |

### 1.4 불투명 술어: σ의 분해 (Opaque Predicate: Decomposing σ)

σ(의미적 완전성, semantic completeness)는 두 부분으로 나뉜다:

σ (semantic completeness) has two parts:

- **σ_auto (자동 검증 가능 부분):** 용어 커버리지(terminology coverage), 도메인 온톨로지 매칭(domain ontology matching) 등 형식적으로 검증 가능한 측면. 자동화할 수 있다.
  - Formally verifiable aspects: terminology coverage, domain ontology matching. Automatable.

- **σ_oracle (오라클/인간 판단 부분):** "이것이 올바른 분해인가?(Is this the right decomposition?)"와 같은 질문. 계산적으로 환원 불가능(computationally irreducible)하며, 인간 또는 오라클의 판단이 필요하다.
  - Computationally irreducible judgment. Requires human/oracle assessment.

이 분리가 중요한 이유: σ_auto가 먼저 실패하면 값비싼 인간 리뷰를 절약할 수 있다. σ_oracle은 평가 순서에서 **마지막**에 온다(§5 참조).

This separation matters: if σ_auto fails first, we save expensive human review. σ_oracle comes **last** in evaluation order (see §5).

---

## §2 Configuration (설정)

모든 임계값은 프로젝트 수준 설정이며, 보편 상수가 아니다.

All thresholds are project-level settings, not universal constants.

```yaml
# apt-config.yaml — APT 전체 설정 (Full Configuration)
apt:
  # ── 분해 설정 (Decomposition) ──
  decomposition:
    min_children: 2                  # A2 분기 인수 (branching factor). 비원자 Span은 최소 2개 자식.
    min_informed_by: 5               # D4 링크 밀도 (link density). Crystallization 전 최소 INFORMED_BY 수.

  # ── 구현 설정 (Implementation) ──
  implementation:
    complexity_metric: "lines"       # "lines" | "cyclomatic" | "halstead" — 복잡도 측정 방식
    complexity_threshold: 500        # lines=500, cyclomatic=15, halstead=1000 — D5 단일 파일 투영

  # ── 컨텍스트 설정 (Context Budget) ──
  context:
    budget:
      depth_0: 50000                 # 루트: 50K 토큰 (root: 50K tokens)
      depth_1: 20000                 # 깊이 1: 20K 토큰 (depth 1: 20K tokens)
      depth_2plus: 8000              # 깊이 2+: 8K 토큰 (depth 2+: 8K tokens)

  # ── 동시성 설정 (Concurrency) ──
  concurrency:
    max_agents: 8                    # 최대 동시 에이전트 수 (max concurrent agents)
    lock_timeout_minutes: 60         # 잠금 타임아웃 (lock timeout). 초과 시 자동 해제.

  # ── 승인 설정 (Approval) ──
  approval:
    sigma_sla_hours: 4               # σ_oracle 응답 SLA (시간). 초과 시 자동 위임.
    max_returns_per_span: 3          # Span당 최대 반려 횟수. 초과 시 인간 에스컬레이션.
    allow_agent_sigma: false         # true면 에이전트가 σ_oracle 역할 가능 (dev 환경용).

  # ── 테스트 설정 (Testing) ──
  testing:
    coverage_threshold: 0.8          # 최소 테스트 커버리지 80%
    stochastic_repetitions: 10       # 확률적 테스트 반복 횟수 (deterministic=1)

  # ── 비기능 요구사항 기본값 (Non-Functional Requirements Defaults) ──
  nfr:
    latency_p99_ms: null             # p99 지연시간 (밀리초). null이면 미적용.
    memory_mb: null                  # 메모리 제한 (MB). null이면 미적용.
    accuracy_metric: null            # 정확도 메트릭. null이면 미적용.
    execution_env: "default"         # 실행 환경 (예: "production_server", "gpu_server", "default")

  # ── Kafka 설정 (Kafka) ──
  kafka:
    topic: "apt-events"              # 메인 이벤트 토픽
    partitions: 4                    # 파티션 수
    partition_key: "entity_name"     # 파티션 키 (엔티티 이름 기준)
    retention_days: 30               # 이벤트 보존 기간
    dlq_topic: "apt-events-dlq"      # Dead Letter Queue 토픽
    dlq_retention_days: 90           # DLQ 보존 기간
    consumer_group: "apt-kg-writer"  # 소비자 그룹 (단일 KG 작성자)

  # ── 지식 획득 루프 설정 (Knowledge Acquisition Loop) ──
  knowledge_acquisition:
    auto_search: true              # KAL 활성화 (enable Knowledge Acquisition Loop)
    confidence_threshold: 0.7      # 이 이하면 검색 트리거 (below this -> trigger search)
    max_searches_per_span: 5       # Span당 최대 검색 횟수 (max searches per Span)
    search_sources:                # 검색 소스 우선순위 (search source priority)
      - kg_internal                # KG 내부 검색 — 가장 빠름 (KG internal — fastest)
      - kg_cross_project           # 다른 프로젝트 KG 검색 (cross-project KG search)
      - web                        # 웹 검색 — 가장 느림 (web search — slowest)
    search_cooldown_seconds: 30    # 같은 Span 재검색 대기 (re-search cooldown for same Span)

  # ── 환경별 오버라이드 (Environment Overrides) ──
  environments:
    dev:
      complexity_threshold: 800      # 개발 환경: 복잡도 임계값 완화
      sigma_sla_hours: 0             # 개발 환경: σ SLA 비활성화
      allow_agent_sigma: true        # 개발 환경: 에이전트 σ 허용
    staging:
      execution_env: "gpu_server"    # 스테이징: GPU 서버에서 실행
    prod:
      execution_env: "production_server"  # 프로덕션: 운영 서버에서 실행
      kafka:
        min_insync_replicas: 2       # 프로덕션: 최소 동기 레플리카 2
```

**환경 오버라이드 동작 (Environment Override Behavior):** `environments` 하위의 키는 최상위 설정을 병합(merge) 방식으로 덮어쓴다. 명시되지 않은 키는 기본값을 유지한다.

**Environment overrides** under `environments` merge over top-level settings. Unspecified keys retain defaults.

---

## §3 Sets (집합)

### 3.1 집합 정의 테이블 (Set Definitions)

APT는 10개의 기본 집합으로 구성된다.

APT is composed of 10 fundamental sets.

| 기호 (Symbol) | 이름 (Name) | KG 라벨 (Label) | 정의 (Definition) |
|:------------:|-------------|:---------------:|-------------------|
| **𝔄** | Anchors (앵커) | `SemanticAnchor` | 프로젝트 정체성. 프로젝트당 \|𝔄\|=1. / Project identity. \|𝔄\|=1 per project. |
| **𝕊** | Spans (스팬) | `AptSpan` | SP 세계의 계획 단위. 재귀적으로 분해된다. / Planning units in SP world. Recursively decomposed. |
| **𝔸** | AtomicSpans (원자 스팬) | `AtomicSpan` | {s∈𝕊 : C(s) ∧ approved(s,σ)} ⊂ 𝕊. 결정화 술어를 만족하고 σ-승인을 받은 스팬. / Spans satisfying crystallization predicate with σ-approval. |
| **𝕋** | Twins (트윈) | `SemanticTwin` | ST 세계의 엔티티. Contract + Task 쌍을 보유. / ST world entities holding Contract + Task pair. |
| **𝕂** | Contracts (계약) | `AptContract` | 타입이 있는 I/O 명세. Hoare triple {P}f:A→B{Q} 형태. / Typed I/O specs in Hoare triple form. |
| **Θ** | Tasks (태스크) | `SemanticTask` | Contract에 대한 자연어 스캐폴딩. 구현자에게 맥락을 전달. / NL scaffolding for Contracts. Conveys context to implementer. |
| **Γ** | SourceCode (소스코드) | `SourceCodeNode` | SCW 세계의 산출물. 실제 코드 파일. / SCW world artifacts. Actual code files. |
| **ℍ** | CrystallizationEvents (결정화 이벤트) | `CrystallizationEvent` | 이분 발생 허브. Atom, Twin, Task, Contract, Source를 연결. / Bipartite incidence hubs linking all entities. |
| **𝒜** | Agents (에이전트) | `AptAgent` | executor ∪ reviewer. 역할 분리: executor(s) ≠ reviewer(s). / Agent set with role separation. |
| **ℜ** | Requirements (요구사항) | `Requirement` | 외부 요구사항. FULFILLS_REQUIREMENT로 추적. / External requirements. Traced via FULFILLS_REQUIREMENT. |

### 3.2 상호 배타성 (Disjointness) — 6개 조건

집합 간 중첩을 금지하는 6가지 조건이 있다. 𝔸은 𝕊의 부분집합이므로 배타 조건에서 제외된다.

Six disjointness conditions prevent overlap between sets. 𝔸 is a subset of 𝕊 and thus excluded from disjointness.

| # | 조건 (Condition) | 의미 (Meaning) |
|---|:----------------:|---------------|
| 1 | 𝔄 ∩ 𝕊 = ∅ | Anchor는 Span이 아니다. / Anchors are not Spans. |
| 2 | 𝕊 ∩ 𝕋 = ∅ | Span은 Twin이 아니다. / Spans are not Twins. |
| 3 | 𝕋 ∩ 𝕂 = ∅ | Twin은 Contract가 아니다. / Twins are not Contracts. |
| 4 | 𝕂 ∩ Θ = ∅ | Contract는 Task가 아니다. / Contracts are not Tasks. |
| 5 | Θ ∩ Γ = ∅ | Task는 SourceCode가 아니다. / Tasks are not SourceCode. |
| 6 | 𝔸 ⊂ 𝕊 | AtomicSpan은 Span의 **부분집합**이다 (배타가 아님). / AtomicSpan is a **subset** of Span (not disjoint). |

**검증 (Validation):** V9 쿼리가 이중 라벨 노드를 감지한다.

```cypher
// V9: 상호 배타 위반 감지 (Disjointness violation detection)
MATCH (n) WHERE (n:AptSpan AND n:SemanticTwin)
              OR (n:SemanticTwin AND n:AptContract)
RETURN 'DISJOINT', n.name
```

### 3.3 에이전트 역할 분리 (Agent Role Separation)

모든 Span s에 대해: **executor(s) ≠ reviewer(s)**. 이는 자기 승인(self-approval)을 방지하는 직무 분리(separation of duties) 원칙이다.

For any Span s: **executor(s) ≠ reviewer(s)**. This is a separation of duties principle preventing self-approval.

- **executor:** Span을 분해하거나 구현한 에이전트. / The agent who decomposed or implemented.
- **reviewer:** σ를 승인한 에이전트. executor와 반드시 달라야 한다. / The agent who approved σ. Must differ from executor.

V15 검증 쿼리가 이 위반을 감지한다:

```cypher
// V15: 자기 승인 감지 (Self-approval detection)
MATCH (s:AtomicSpan)-[:APPROVED_BY]->(r:AptAgent)
WHERE s.executor = r.name
RETURN 'SELF', s.name
```

---

## §4 Functions (함수)

APT는 8개의 핵심 함수를 정의한다. 이들은 집합 간의 관계를 계산하는 데 쓰인다.

APT defines 8 core functions used to compute relationships between sets.

| # | 시그니처 (Signature) | 이름 (Name) | 정의 (Definition) |
|---|---------------------|-------------|-------------------|
| F1 | **D : 𝕊 → 𝒫(𝕊)** | Decomposition (분해) | D(s) = {s' : (s,s') ∈ DECOMPOSES_TO ∨ (s,s') ∈ EXPLORES_VIA}. 주어진 Span의 모든 자식(부분 또는 대안)을 반환한다. / Returns all children (parts or alternatives) of a given Span. |
| F2 | **depth : 𝕊 → ℕ** | Depth (깊이) | depth(root) = 0; depth(s) = 1 + min{depth(p) : p ∈ parent(s)}. 루트에서의 최단 거리. DAG이므로 다중 부모가 가능하며 최솟값을 취한다. / Shortest distance from root. In a DAG, multiple parents possible; take minimum. |
| F3 | **parent : 𝕊 → 𝒫(𝕊)** | Parent (부모) | 다중 값 (DAG, 트리가 아님). Span은 여러 부모를 가질 수 있다. DECOMPOSES_TO 또는 EXPLORES_VIA의 역방향. / Multi-valued (DAG, not tree). Inverse of DECOMPOSES_TO or EXPLORES_VIA. |
| F4 | **siblings : 𝕊 → 𝒫(𝕊)** | Siblings (형제) | **부모 기준(per-parent)** 자식에서 자기 자신을 뺀 것. DAG에서 부모마다 형제 집합이 다를 수 있다. A3(형제 독립성)은 부모 기준으로 적용된다. / Per-parent children minus self. A3 (sibling independence) applies per-parent. |
| F5 | **links : 𝕊 → ℕ** | Link density (링크 밀도) | INFORMED_BY 엣지의 개수. D4에 의해 crystallization 전 최소 config.min_informed_by 이상이어야 한다. / Count of INFORMED_BY edges. Must be ≥ config.min_informed_by before crystallization (D4). |
| F6 | **lines : Γ → ℕ** | Code lines (코드 줄 수) | 공백과 주석을 제외한 줄 수. D5(단일 파일 투영)에서 complexity_threshold와 비교한다. / Excluding blank lines and comments. Compared against complexity_threshold in D5. |
| F7 | **executor : 𝕊 → 𝒜** | Executor (실행자) | 해당 Span을 분해하거나 구현한 에이전트. / The agent who decomposed or implemented the Span. |
| F8 | **reviewer : 𝕊 → 𝒜** | Reviewer (검토자) | σ를 승인한 에이전트. executor와 **반드시 다르다** (≠ executor). / The agent who approved σ. **Must differ** from executor. |

---

## §5 Predicates (술어)

### 5.1 결정화 술어 (Crystallization Predicate)

**C(S) = τ ∧ σ ∧ ν ∧ ι ∧ δ — 모두 통과해야 한다. 임계값 없음.**

**C(S) = τ ∧ σ ∧ ν ∧ ι ∧ δ — ALL must pass. No threshold.**

Span이 AtomicSpan으로 인정받으려면 5개 기준을 모두 충족해야 한다.

A Span must satisfy all 5 criteria to qualify as an AtomicSpan.

**평가 순서: 저비용 거부 우선 (Evaluation Order: Cheap Rejection First)**

비용이 낮은 자동 검사부터 수행하여, 명백히 비원자적인 Span에 대한 값비싼 인간 리뷰를 방지한다.

Perform low-cost automated checks first, preventing expensive human reviews on obviously non-atomic Spans.

| 순서 (Order) | 기호 (Sym) | 기준 (Criterion) | 게이트 (Gate) | 비용 (Cost) | 실패 시 조치 (On Fail) |
|:----------:|:---------:|-----------------|:-----------:|:---------:|---------------------|
| **1st** | **ν** | **복잡도 ≤ 임계값 (Complexity ≤ threshold)** — lines ≤ 500, cyclomatic ≤ 15, 또는 halstead ≤ 1000 (설정에 따름) | auto | ~0 | **분할 (Split)** — 너무 크다. 더 작은 조각으로 분해. |
| **2nd** | **τ** | **타입 표현 가능성 (Type Expressibility)** — 구체적 input/output 타입을 명시할 수 있는가? "data", "any", "result" 같은 모호한 타입 불가. | auto | low | **타입 경계로 분할 (Split by type boundary)** — 타입이 불명확하면 관심사가 혼재된 것. |
| **3rd** | **ι** | **테스트 실현 가능성 (Test Feasibility)** — 구체적 assert를 작성할 수 있는가? 예: `assert parse(["--name","Alice"]) == "Alice"` | auto | low | **예시로 명확화 (Sharpen with examples)** — assert를 쓸 수 없으면 명세가 불충분. |
| **4th** | **δ** | **분해 비경제 (Decomposition Diseconomy)** — 더 분할하면 100줄 미만 파편이 되는가? | auto | low | **상향 병합 (Merge upward)** — 이미 충분히 원자적. 과잉 분해 방지. |
| **5th** | **σ** | **의미적 완전성 (Semantic Completeness)** — 이 Span이 하나의 일관된 의미 단위를 형성하는가? | **human** | **high** | **범위 축소 (Narrow scope)** — σ_auto 먼저, 실패 시 돌아감. 통과 시 σ_oracle (4h SLA). |

**σ가 마지막인 이유 (Why σ is last):** σ_oracle은 가장 비용이 높다 (4시간 SLA, 인간 판단 필요). 자동 검사들이 먼저 거부하면, 명백히 비원자적인 Span에 대한 인간 리뷰를 절약한다.

σ_oracle is the most expensive (4h SLA, requires human judgment). Auto-checks rejecting first saves human reviews on obviously non-atomic Spans.

**σ의 분리 (σ Decomposition):**

| 구성요소 (Component) | 성격 (Nature) | 내용 (Content) | 자동화 (Automatable?) |
|:-------------------:|:-----------:|---------------|:-------------------:|
| **σ_auto** | 형식 검증 (formal) | 용어 커버리지: Contract에 사용된 모든 도메인 용어가 KG에 정의되어 있는가? 도메인 온톨로지 매칭: 분해 구조가 도메인 모델과 일치하는가? | **예 (Yes)** |
| **σ_oracle** | 인간 판단 (judgment) | "이것이 올바른 분해인가?" "의미 단위로서 일관성이 있는가?" 계산적으로 환원 불가능(computationally irreducible). | **아니오 (No)** |

### 5.2 보조 술어 (Auxiliary Predicates) — 3개

| # | 술어 (Predicate) | 정의 (Definition) | 용도 (Usage) |
|---|-----------------|-------------------|-------------|
| P1 | **isAtomic(s)** | C(s) ∧ approved(s, σ) | Span이 원자적인지 판별. C(S) 통과 + σ_oracle 승인 필요. AtomicSpan 라벨 부여 조건. / Determines if a Span is atomic. Requires C(S) pass + σ_oracle approval. |
| P2 | **independent(sᵢ, sⱼ)** | ¬∃ path in DEPENDS_ON (transitively checked) | 두 Span 간 의존 경로가 없음을 확인. DEPENDS_ON의 전이적 폐쇄(transitive closure)에서 검사. A3 공리의 기반. / Confirms no dependency path between two Spans. Checked in transitive closure of DEPENDS_ON. Basis for A3. |
| P3 | **wellFormed(h)** | atom + twin + contract가 허브에 존재 | CrystallizationEvent 허브 h가 최소한 atom, twin, contract에 대한 INVOLVES 엣지를 보유하는지 확인. V14 쿼리의 기반. / Confirms hub h has INVOLVES edges for at least atom, twin, contract. Basis for V14. |

---

## §6 Relations (관계) — 12개 전체

### 6.1 전체 관계 테이블 (Complete Relations Table)

| # | 관계 (Relation) | 도메인×공역 (Domain×Codomain) | 속성 (Properties) | 상세 설명 (Description) |
|---|----------------|:---------------------------:|------------------|----------------------|
| R1 | **DECOMPOSES_TO** | 𝕊 × 𝕊 | 비반사적(irreflexive), 비순환(acyclic), N:N DAG | **"전체의 부분" — 모든 자식이 필요.** 부모 Span을 의미적 부분들로 분할. 모든 자식이 구현되어야 부모가 완성. |
| R2 | **EXPLORES_VIA** | 𝕊 × 𝕊 | 비반사적, 비순환, N:N DAG | **"대안" — best_of_n / ensemble / fallback_chain.** 전략(strategy) 속성을 가짐. 부모 수준에 Selection Span 필요. |
| R3 | **DEPENDS_ON** | 𝕊 × 𝕊 | 전이적(transitive), 비순환(acyclic) | 실행 순서 의존. **형제 간(between siblings) 금지 (A3).** |
| R4 | **CRYSTALLIZES_TO** | 𝔸 × 𝕋 | 단사(injective) | **유일한 SP↔ST 교차 (A4).** AtomicSpan에서 SemanticTwin으로의 유일한 다리. |
| R5 | **HAS_CONTRACT** | 𝕋 × 𝕂 | 함수적(functional): 1 Twin → 1 Contract | Twin이 정확히 하나의 Contract를 보유. |
| R6 | **HAS_TASK** | 𝕋 × Θ | 함수적: 1 Twin → 1 Task | Twin이 정확히 하나의 Task를 보유. |
| R7 | **MATERIALIZES** | 𝕂 × Γ | 함수적: 1 Contract → 1 SourceCode | Contract가 정확히 하나의 SourceCode로 구체화. |
| R8 | **INFORMED_BY** | 𝕊 × 𝒰 | N:N | 출처 추적(provenance). 𝒰은 모든 노드의 합집합. D4(링크 밀도) 계산에 사용. |
| R9 | **FULFILLS_REQUIREMENT** | (𝕊∪𝕋) × ℜ | N:N | 요구사항 추적(traceability). Span 또는 Twin이 외부 요구사항을 충족. |
| R10 | **INVOLVES** | ℍ × 𝒰 | role ∈ {atom, twin, task, contract, source} | 이분 발생 인코딩(bipartite incidence encoding). CrystallizationEvent 허브의 연결. |
| R11 | **APPROVED_BY** | 𝕊 × 𝒜 | criterion ∈ {sigma, contract_review} | 승인 기록. executor ≠ reviewer 강제. |
| R12 | **SEQUENCED_WITH** | 𝕂 × 𝕂 | k1.postcondition ⊢ k2.precondition | **Hoare triple 순차 합성 (sequential composition).** |

### 6.2 DECOMPOSES_TO vs EXPLORES_VIA 비교 (Comparison)

이 두 관계는 APT에서 가장 혼동되기 쉬운 개념이다. 핵심 차이를 명확히 한다.

These two relations are the most commonly confused concepts in APT. We clarify the key differences.

| 비교 항목 (Aspect) | DECOMPOSES_TO | EXPLORES_VIA |
|:------------------:|:-------------:|:------------:|
| **의미 (Semantics)** | 부분-전체 (Part-whole) | 대안 (Alternatives) |
| **자식 필요성 (Children required)** | **모두 (ALL)** — 모든 자식이 구현되어야 부모 완성 | **선택 (BEST_OF_N)** 또는 **앙상블 (ENSEMBLE)** |
| **예시 (Example)** | Module → Auth + API + DB | Search → ElasticSearch \| Algolia \| Meilisearch |
| **A3 적용? (A3 applies?)** | 예 (Yes) — 형제 간 독립 | 예 (Yes) — 대안들도 독립이어야 함 |
| **선택 메커니즘 (Selection)** | 없음 (None) — 모두 필요 | 부모 수준의 Selection Span이 벤치마크 후 선택 |
| **strategy 속성 (strategy property)** | 없음 (N/A) | `best_of_n` \| `ensemble` \| `fallback_chain` |
| **합류 감지 (Confluence detection)** | N/A | 두 대안이 동등한 결과를 산출하면 `CONFLUENT_WITH` 엣지 기록 (Wolfram 다중경로 병합 유비) |

**EXPLORES_VIA 패턴 예시 (Exploration Pattern Example):**

```
Parent ──EXPLORES_VIA {strategy:'best_of_n'}──▶ Alt_1 (AtomicSpan)
       ──EXPLORES_VIA {strategy:'best_of_n'}──▶ Alt_2 (AtomicSpan)
       ──EXPLORES_VIA {strategy:'best_of_n'}──▶ Alt_3 (AtomicSpan)
       ──DECOMPOSES_TO──▶ Selection_Span (벤치마크, 승자 선택 / benchmarks, picks winner)
```

### 6.3 DEPENDS_ON 상세 (DEPENDS_ON Details)

DEPENDS_ON은 실행 순서 의존을 나타내며, 엄격한 제약을 가진다.

DEPENDS_ON represents execution order dependency with strict constraints.

| 속성 (Property) | 설명 (Description) |
|:--------------:|-------------------|
| **전이적 (Transitive)** | A→B, B→C이면 A→C도 암묵적으로 성립. independent(sᵢ,sⱼ) 검사는 전이적 폐쇄(transitive closure)에서 수행. / If A→B and B→C, then A→C is implicitly held. |
| **비순환 (Acyclic)** | 순환 의존 금지. V6 쿼리가 순환을 감지. / Cyclic dependencies forbidden. V6 query detects cycles. |
| **형제 간 금지 (Between siblings: FORBIDDEN)** | **A3 공리.** 같은 부모의 자식들 사이에 DEPENDS_ON이 있으면 공리 위반. 형제는 독립적으로 구현 가능해야 한다. 의존이 있으면 부모를 재분해해야 한다. / **Axiom A3.** DEPENDS_ON between children of the same parent violates the axiom. Siblings must be independently implementable. |
| **교차 Span 의존 (Cross-Span dependency)** | 다른 부모의 자식끼리는 DEPENDS_ON 가능. 단, 비순환이어야 함. / DEPENDS_ON between children of different parents is allowed, provided it remains acyclic. |

### 6.4 SEQUENCED_WITH: Hoare Triple Chaining (Hoare 트리플 연쇄)

Contract 간 순차 합성을 기록한다. 파이프라인 검증에 사용.

Records sequential composition between Contracts. Used for pipeline verification.

```
{P1} f1 : A→B {Q1},  {P2} f2 : B→C {Q2},  Q1 ⊢ P2
────────────────────────────────────────────────────
         {P1} f2∘f1 : A→C {Q2}
```

- k1의 후조건(postcondition)이 k2의 전조건(precondition)을 함의(entail)해야 한다.
- k1's postcondition must entail k2's precondition.
- 이는 범주론적 사상 합성(categorical morphism composition)이 **아니다** — 항등(identity)이나 결합법칙(associativity)을 증명하지 않는다. 실용적 파이프라인 검증.
- This is **not** categorical morphism composition — no identity or associativity proof. Practical pipeline verification.
- 비선형 파이프라인(OK/NG 경로, 병렬 검사)에는 EXPLORES_VIA + 조건부 SEQUENCED_WITH를 사용한다.
- For non-linear pipelines (OK/NG paths, parallel inspection), use EXPLORES_VIA + conditional SEQUENCED_WITH.

### 6.5 카디널리티 요약 테이블 (Cardinality Summary)

| 관계 (Relation) | 카디널리티 (Cardinality) | 제약 (Constraint) |
|:--------------:|:---------------------:|:-----------------:|
| DECOMPOSES_TO | N : N | 비순환 DAG |
| EXPLORES_VIA | N : N | 비순환 DAG, strategy 속성 필수 |
| DEPENDS_ON | N : N | 전이적, 비순환, 형제 간 금지 |
| CRYSTALLIZES_TO | 1 : 1 (단사/injective) | AtomicSpan → Twin 유일 매핑 |
| HAS_CONTRACT | 1 : 1 (함수적/functional) | Twin → Contract |
| HAS_TASK | 1 : 1 (함수적) | Twin → Task |
| MATERIALIZES | 1 : 1 (함수적) | Contract → SourceCode |
| INFORMED_BY | N : N | 제약 없음 (D4 밀도 권장) |
| FULFILLS_REQUIREMENT | N : N | 제약 없음 |
| INVOLVES | N : N | role 속성 필수 |
| APPROVED_BY | N : N | executor ≠ reviewer |
| SEQUENCED_WITH | N : N | Q1 ⊢ P2 (후조건→전조건 함의) |

---

## §7 Axioms (공리) — A1~A4

공리 위반 = APT가 아니다. 검증 쿼리(V1~V6)로 감지된다.

Axiom violation = not APT. Detected by validation queries (V1-V6).

### A1: ContractOnlyAtST (Contract는 ST에서만)

**Formal:** ∀k ∈ 𝕂 : HAS_CONTRACT⁻¹(k) ⊆ 𝕋

**EN:** Every Contract must be owned by a SemanticTwin. No other entity type may hold a Contract. This ensures that Contracts only exist in the ST world, not floating freely or attached to Spans directly.

**KR:** 모든 Contract는 SemanticTwin이 소유해야 한다. 다른 엔티티 유형은 Contract를 보유할 수 없다. 이는 Contract가 ST 세계에만 존재하도록 보장하며, Span에 직접 연결되거나 자유롭게 떠다니는 것을 방지한다.

**검증 (Validation):**
```cypher
// V1: Contract의 소유자가 Twin이 아닌 경우 감지
MATCH (x)-[:HAS_CONTRACT]->(c) WHERE NOT x:SemanticTwin RETURN 'A1', x.name
```

### A2: RecursiveDecomposition + Termination (재귀 분해 + 종료)

**Formal:** ¬C(s) ⇒ |D(s)| ≥ config.min_children. All paths terminate.

**EN:** If a Span is not yet crystallized (C(s) is false), it must be decomposed into at least `min_children` (default 2) sub-Spans. All decomposition paths must eventually terminate at AtomicSpans. This prevents infinite decomposition and ensures progress. A Span that is neither atomic nor decomposed is a violation.

**KR:** Span이 아직 결정화되지 않았으면(C(s)가 거짓), 최소 `min_children`(기본값 2)개의 하위 Span으로 분해되어야 한다. 모든 분해 경로는 결국 AtomicSpan에서 종료되어야 한다. 이는 무한 분해를 방지하고 진행을 보장한다. 원자적이지도 않고 분해되지도 않은 Span은 위반이다.

**검증 (Validation):**
```cypher
// V3: 자식이 1개뿐인 비원자 Span (분기 인수 위반)
MATCH (s:AptSpan)-[:DECOMPOSES_TO]->(c) WHERE NOT s:AtomicSpan
WITH s, count(c) AS k WHERE k = 1 RETURN 'A2', s.name

// V4: 리프이면서 원자가 아닌 Span (종료 위반)
MATCH (l:AptSpan) WHERE NOT (l)-[:DECOMPOSES_TO]->() AND NOT l:AtomicSpan
RETURN 'A2', l.name
```

### A3: SiblingIndependence (형제 독립성)

**Formal:** ∀sᵢ, sⱼ ∈ D(p) : sᵢ ≠ sⱼ ⇒ independent(sᵢ, sⱼ). Per-parent in DAG.

**EN:** All siblings (children of the same parent) must be independent — there must be no DEPENDS_ON path between them, checked transitively. This is evaluated per-parent because in a DAG, a Span can have multiple parents with different sibling sets. If siblings have dependencies, the parent must be re-decomposed to eliminate the coupling. This ensures parallel implementability.

**KR:** 같은 부모의 모든 형제는 독립적이어야 한다 — 전이적으로 검사했을 때 DEPENDS_ON 경로가 없어야 한다. DAG에서 Span이 여러 부모를 가질 수 있으므로, 부모 기준으로 평가한다. 형제 간 의존이 있으면 부모를 재분해하여 결합을 제거해야 한다. 이는 병렬 구현 가능성을 보장한다.

**검증 (Validation):**
```cypher
// V2: 형제 간 DEPENDS_ON 감지
MATCH (p)-[:DECOMPOSES_TO]->(a), (p)-[:DECOMPOSES_TO]->(b)
WHERE a <> b AND (a)-[:DEPENDS_ON]->(b)
RETURN 'A3', a.name, b.name
```

### A4: CrystallizationFrontierUniqueness (결정화 프론티어 유일성)

**Formal:** CRYSTALLIZES_TO = sole SP→ST bridge.

**EN:** CRYSTALLIZES_TO is the **only** relation that crosses from the SP world (Spans) to the ST world (Twins). No other relation type may connect AptSpan directly to SemanticTwin. This creates a clean, auditable boundary — the "crystallization frontier" — between planning and specification. All information must pass through this single bridge.

**KR:** CRYSTALLIZES_TO는 SP 세계(Span)에서 ST 세계(Twin)로 교차하는 **유일한** 관계이다. 다른 관계 유형은 AptSpan을 SemanticTwin에 직접 연결할 수 없다. 이는 계획과 명세 사이에 깨끗하고 감사 가능한 경계 — "결정화 프론티어"를 만든다. 모든 정보는 이 단일 다리를 통과해야 한다.

**검증 (Validation):**
```cypher
// V5: CRYSTALLIZES_TO 이외의 SP→ST 엣지 감지
MATCH (s:AptSpan)-[r]->(t:SemanticTwin)
WHERE type(r) <> 'CRYSTALLIZES_TO'
RETURN 'A4', s.name
```

---

## §8 Dual Guidance (이중 가이드)

### 8.1 Soft vs Hard 테이블

| 구분 (Category) | Soft (SP 세계) | Hard (ST + SCW 세계) |
|:--------------:|:--------------:|:-------------------:|
| **내용 (Content)** | 설명(descriptions), KG 링크, 자연어 | 타입이 있는 Contract + TDD |
| **강제 여부 (Enforced?)** | 아니오. 가이드라인, 권장 사항. | **예.** 위반 시 진행 불가. |
| **예시 (Example)** | "이 Span은 인증을 다룬다" | `input: Credentials, output: AuthToken, pre: valid_format, post: token.expiry > now` |
| **검증 (Validation)** | D4 링크 밀도 (soft 권장) | V1~V6 공리 위반 (hard 차단) |

### 8.2 LLM ≈ Denoiser (LLM은 잡음 제거기와 유사)

LLM은 Soft 가이드에서 유용한 신호를 추출하는 **잡음 제거기(denoiser)** 와 유사하다(유비). Soft 설명은 모호하고 중복이 있지만, LLM이 이를 처리하여 구조화된 정보로 변환한다. 단, 이 유비는 LLM의 작동 방식에 대한 정밀한 기술적 주장이 **아니다**.

LLM is analogous to a **denoiser** extracting useful signal from Soft guidance. Soft descriptions are ambiguous and redundant, but LLM processes them into structured information. This analogy is **not** a precise technical claim about LLM operation.

### 8.3 통합: 타입 강제에 의한 자동 해결 (Integration: Auto-Resolved by Type Enforcement)

Soft→Hard 전환(SP→ST)에서 통합(integration) 문제는 **타입 강제(type enforcement)** 에 의해 대부분 자동으로 해결된다. Contract의 input_type과 output_type이 구체적이면, 인터페이스 불일치가 컴파일/테스트 시점에 드러난다.

Integration issues at the Soft→Hard transition (SP→ST) are mostly auto-resolved by **type enforcement**. When Contract input_type and output_type are concrete, interface mismatches surface at compile/test time.

### 8.4 유일한 병목: Contract 품질 (Sole Bottleneck: Contract Quality)

타입 강제 덕분에 통합 문제는 자동 해결되므로, **유일한 병목은 Contract 품질**이다. 잘못된 전조건, 불완전한 후조건, 모호한 타입은 시스템 전체에 파급된다.

Thanks to type enforcement, integration issues are auto-resolved, making **Contract quality the sole bottleneck**. Wrong preconditions, incomplete postconditions, or vague types propagate throughout the system.

### 8.5 의미 손실에 관하여 (On Semantic Loss)

Soft→Hard 전환은 **의미 손실(semantic loss)** 을 수반한다. 이는 비트겐슈타인(Wittgenstein)의 언어 게임 전환과 유사하다 — 자연어의 풍부한 맥락이 형식 언어로 전환될 때 일부가 사라진다. **Task(D3)** 가 이 손실을 부분적으로 보존한다: Task는 자연어 스캐폴딩으로서, Contract의 형식적 명세 옆에 의미적 맥락을 유지한다.

The Soft→Hard transition involves **semantic loss**, analogous to Wittgenstein's language game switch — rich context of natural language partially disappears when converted to formal language. **Task (D3)** partially preserves this loss: as NL scaffolding, Task maintains semantic context alongside Contract's formal specification.

---

## §9 Design Principles (설계 원칙) — D1~D10

설계 원칙 위반은 품질을 저하시키지만 APT를 깨뜨리지는 않는다(공리 위반과 다름).

Design Principle violations degrade quality but do not break APT (unlike Axiom violations).

| # | 원칙 (Principle) | 기본값 (Default) | 설정 가능 (Configurable) |
|---|-----------------|:--------------:|:---------------------:|
| D1 | **HyperedgeHub** | on | No |
| D2 | **HarnessAxisMapping** | — | No |
| D3 | **TaskAsScaffolding** | — | No |
| D4 | **DenseBeforeContract** | 5 | **Yes** |
| D5 | **SingleFileProjection** | 500 lines | **Yes** |
| D6 | **ContextBudget** | 50K/20K/8K | **Yes** |
| D7 | **ProgressiveDisclosure** | — | No |
| D8 | **PhaseTransitionCompaction** | — | No |
| D9 | **GenerativeFlowOrdering** | — | No |
| D10 | **NFR as First-Class** | — | **Yes** |
| D11 | **KnowledgeAcquisitionLoop** | on | **Yes** |

### D1: HyperedgeHub (하이퍼엣지 허브)

CrystallizationEvent를 **이분 발생 허브(bipartite incidence hub)** 로 사용한다. 이 허브는 atom, twin, task, contract, source를 INVOLVES 엣지로 연결하여, 결정화 시점의 모든 관련 엔티티를 하나의 이벤트 노드에서 조회할 수 있게 한다. 속성 그래프에서 하이퍼엣지를 인코딩하는 표준 기법이다.

Uses CrystallizationEvent as a **bipartite incidence hub**. This hub connects atom, twin, task, contract, and source via INVOLVES edges, enabling queries from a single event node to all related entities at crystallization time.

### D2: HarnessAxisMapping (하네스 축 매핑)

각 세계(World)에 역할을 매핑한다: SA=Inform(정보 제공), SP=Constrain(제약), ST=Verify(검증), SCW=Autonomous(bounded)(제한된 자율). 에이전트의 자율성이 단계마다 달라진다: SA에서는 정보를 받고, SP에서는 제약을 받으며, ST에서는 검증을 수행하고, SCW에서는 Contract 범위 내에서 자율적으로 구현한다.

Maps roles to each World: SA=Inform, SP=Constrain, ST=Verify, SCW=Autonomous(bounded). Agent autonomy varies by phase.

### D3: TaskAsScaffolding (Task는 스캐폴딩)

Task는 자연어 스캐폴딩이며 Contract는 형식 명세이다. 둘은 **같지 않다.** Task는 "왜 이것을 하는가", "어떤 맥락인가"를 설명하고, Contract는 "무엇을 입력하고 무엇을 출력하는가"를 형식적으로 정의한다. Task가 있어야 Soft→Hard 전환에서의 의미 손실을 최소화한다(§8.5 참조).

Task is NL scaffolding; Contract is formal spec. They are **not the same**. Task explains "why" and "context"; Contract formally defines "what input, what output". Task minimizes semantic loss in Soft→Hard transition (see §8.5).

### D4: DenseBeforeContract (Contract 전 밀도 확보)

Crystallization 전에 links(S) ≥ config.min_informed_by (기본값 5)를 충족해야 한다. 이는 충분한 지식 연결(INFORMED_BY 엣지)이 있어야 의미 있는 Contract를 작성할 수 있다는 원칙이다. 스파스한 Span은 V16 쿼리가 감지한다.

Before crystallization, links(S) ≥ config.min_informed_by (default 5). Sufficient knowledge links (INFORMED_BY edges) are needed before writing a meaningful Contract. Sparse Spans are detected by V16.

### D5: SingleFileProjection (단일 파일 투영)

AtomicSpan은 하나의 파일로 투영되어야 하며, 그 파일의 복잡도가 임계값(기본 500줄) 이하여야 한다. complexity_metric은 "lines", "cyclomatic", "halstead" 중 선택 가능하다. 임계값 초과 시 SP에서 재분해한다.

AtomicSpan must project to a single file whose complexity is below threshold (default 500 lines). Metric selectable: "lines", "cyclomatic", "halstead". Exceeding threshold triggers re-decomposition in SP.

### D6: ContextBudget (컨텍스트 예산)

깊이별 토큰 예산: depth_0=50K, depth_1=20K, depth_2+=8K. 에이전트가 한 번에 로드하는 맥락의 크기를 제한한다. 이는 **공학적 휴리스틱(engineering heuristic)** 이며, 인지과학적 주장이 아니다. KG가 확장된 마음(extended mind)으로서 기억을 대신하므로, 에이전트는 제한된 컨텍스트 윈도우 내에서 작업한다.

Token budget per depth: depth_0=50K, depth_1=20K, depth_2+=8K. Limits context loaded at once. This is an **engineering heuristic**, not a cognitive science claim. KG as extended mind substitutes for memory.

### D7: ProgressiveDisclosure (점진적 공개)

L1 meta(2K 토큰) → L2 structure(5K 토큰) → L3 detail(8K 토큰). 에이전트에게 정보를 점진적으로 공개한다. 먼저 메타 정보(프로젝트 개요, 현재 단계)를 주고, 다음으로 구조(Span 트리, Contract 목록)를, 마지막으로 상세(전체 Contract 내용, 코드)를 제공한다.

L1 meta (2K tokens) → L2 structure (5K tokens) → L3 detail (8K tokens). Information is progressively disclosed to agents. First meta (project overview, current phase), then structure (Span tree, Contract list), finally detail (full Contract content, code).

### D8: PhaseTransitionCompaction (단계 전이 압축)

단계 경계(SP→ST, ST→SCW)에서 컨텍스트를 압축한다. 이전 단계의 상세 정보를 요약으로 대체하여, 새 단계에서 맥락 윈도우를 효율적으로 사용한다. 예를 들어, ST에 진입할 때 SP의 분해 과정 상세는 "분해 완료, 5개 AtomicSpan 생성"으로 압축된다.

Compresses context at phase boundaries (SP→ST, ST→SCW). Replaces detail from previous phases with summaries. For example, entering ST compresses SP decomposition details to "decomposition complete, 5 AtomicSpans generated".

### D9: GenerativeFlowOrdering (생성적 흐름 순서)

**생성적(generative):** SA→SP→ST→SCW (전진). 자연스러운 구축 순서.
**재구성적(reconstructive):** SCW→ST→SP (역진). 기존 코드에서 Contract와 Span을 추론하는 Bottom-Up Ascent(§37)에 사용.

**Generative:** SA→SP→ST→SCW (forward). Natural build order.
**Reconstructive:** SCW→ST→SP (reverse). Used in Bottom-Up Ascent to infer Contracts and Spans from existing code.

### D10: NFR as First-Class (NFR을 일급 시민으로)

비기능 요구사항(latency, memory, accuracy, hardware)을 Contract의 `nfr_*` 필드에 포함한다. NFR은 후회하며 추가하는 것이 아니라 Contract 작성 시점에 명시한다. 환경별 변형(`nfr_env_dev`, `nfr_env_prod`)도 지원한다. 확률적 테스트(stochastic tests)로 NFR을 검증한다.

Non-functional requirements (latency, memory, accuracy, hardware) are included in Contract `nfr_*` fields. NFR is specified at Contract authoring time, not added as an afterthought. Environment-specific variants (`nfr_env_dev`, `nfr_env_prod`) are supported. Stochastic tests verify NFR.

### D11: KnowledgeAcquisitionLoop (지식 획득 루프)

분해 전에 자동으로 KG 내부와 웹에서 지식을 검색하여 Span의 INFORMED_BY 링크를 보강한다. 7가지 검색 트리거(링크 부족, C(S) v/t/i/s 실패, 수동)에 따라 kg_internal → kg_cross_project → web 순서로 검색한다. 검색 결과는 KnowledgeNode로 생성되어 INFORMED_BY로 연결된다. config.knowledge_acquisition에서 활성화/비활성화 및 임계값을 설정한다.

Automatically searches KG internal and web before decomposition to enrich Span's INFORMED_BY links. 7 search triggers (sparse links, C(S) v/t/i/s failures, manual) search in order: kg_internal → kg_cross_project → web. Results become KnowledgeNode connected via INFORMED_BY. Configured under config.knowledge_acquisition.

---

> **다음 파일 (Next):** Operations, Structural Patterns, Infrastructure, Practical Reference — 후속 파일에서 다룸.
> [← index.md](index.md)
