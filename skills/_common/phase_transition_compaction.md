# Phase Transition Compaction (Cross-Skill Shared)

> APT phase 전환 시점에 *이전 phase 작업 결과*를 압축하여 *다음 phase 컨텍스트로 전달*하는 규약. Context Rot 방지 + KG 정전 보장.

---

## 원칙

- **보존**: 다음 phase가 필수로 필요한 *최소 결정 결과*만.
- **제거**: KG 탐색 과정, 후보 비교, 의사결정 로그, 폐기된 대안. (KG에는 PROV 형태로 남음.)
- **새 컨텍스트**: 압축 요약 + 최근 5개 접근 파일 + 다음 phase 진입 명령.

---

## phase별 전환 매트릭스

### SA → SP

| 보존 | 제거 |
|---|---|
| 앵커 이름, 설명, domain, status | KG 탐색 과정 (Step 1 cypher 결과) |
| L1 Span 목록 (name + description) | 후보 앵커 비교 표 |
| Context Budget 할당 결과 | A15 work_kind 분류 추론 과정 |
| 라우팅 결정 (NEW/EXTEND/MAINTENANCE) | 폐기된 앵커 라우팅 후보 |

체크리스트는 [apt-sa/references/handoff_to_sp.md](../apt-sa/references/handoff_to_sp.md).

### SP → ST

| 보존 | 제거 |
|---|---|
| 모든 AtomicSpan name + description | 분해 후보 비교 (어떤 분해를 택했는가의 과정) |
| 각 AtomicSpan의 INFORMED_BY 링크 ≥ N 충족 사실 | RefinementGate 통과 과정 (cypher 출력) |
| C(S) 5 술어 PASS 결과 | EXPLORES_VIA 미선택 대안 |
| s_oracle 승인 사실 (executor != reviewer) | Confluence 감지 과정 |
| Span Boundary (allowed_paths / forbidden_patterns) | 깊은 트리의 중간 노드 detail |

체크리스트는 [apt-sp/references/handoff_to_st.md](../apt-sp/references/handoff_to_st.md).

### ST → SCW

| 보존 | 제거 |
|---|---|
| Contract 7 필드 (input/output/pre/post/semantic_meaning/target_file/status) | Contract draft 단계의 수정 이력 (KG amendment에 보존) |
| NFR 환경별 변형 (`nfr_env_{dev,staging,prod}`) | tau_check before/after 추론 과정 |
| Task의 acceptance_criteria + impact_tests 경로 | SEQUENCED_WITH 검토 과정 |
| CrystallizationEvent hub의 4 role 연결 | HardwareContext 후보 비교 |
| Contract status='Active' 확인 사실 | Twin lifecycle 중간 상태 (draft→crystallized 등) |

### SCW → 다음 사이클 (또는 PH6 피드백)

| 보존 | 제거 |
|---|---|
| FulfillmentGate 7 checks 결과 (각 PASS/FAIL) | 구현 중간 시도 (TDD red→green→refactor 모든 cycle) |
| ContractMaterialized Kafka event 발행 사실 | AntiPattern AP1-AP9 회피 과정 |
| AptTestRun 노드 (CI/local 결과) | Gap Resolution Thompson Sampling 시도 결과 |
| AptFeedback 생성 사실 (있다면) | 폐기된 candidate (GapCandidate.status='rejected') |
| Source 파일 KG ref comment 적재 사실 | 평가 cycle 중간 metric (mean/std 등은 KG에 보존, 컨텍스트엔 최종만) |

---

## 압축 cypher 패턴

phase 종료 시 KG에 PhaseTransitionEvent 노드 생성:

```cypher
MERGE (pte:PhaseTransitionEvent {name:'PTE_'+$cycle_id+'_'+$from_phase+'_to_'+$to_phase})
SET pte.cycle_id = $cycle_id,
    pte.from_phase = $from_phase,
    pte.to_phase = $to_phase,
    pte.timestamp = datetime(),
    pte.preserved_keys = $preserved,     -- 위 표의 "보존" 키 목록
    pte.context_snapshot = $snapshot,    -- 압축된 요약 (JSON string)
    pte.dropped_count = $dropped_count   -- 제거된 detail 개수
WITH pte
MATCH (prev:Phase {name:$from_phase}), (next:Phase {name:$to_phase})
MERGE (prev)-[:HANDS_OFF_TO {via:pte.name}]->(next)
```

---

## anti-pattern

- **E-PTC1: 전부 보존** — 압축 안 함. 다음 phase에 노이즈 + Context Rot. → 매트릭스 강제.
- **E-PTC2: 보존 누락** — 다음 phase가 필요한 키 누락. 재로딩 비용 → KG에서 다시 cypher.
- **E-PTC3: silent 압축** — PhaseTransitionEvent 없이 압축. 추적 불가 → cypher 강제.

---

## Academic Grounding

Phase Transition Compaction은 *소프트웨어 공학 + 정보이론*의 결정화:

### 1. Brooks's Law (Mythical Man-Month, 1975)

> Brooks, F. P. (1975/1995). *The Mythical Man-Month: Essays on Software Engineering*. Addison-Wesley.

핵심: 후기 프로젝트에 인력 추가하면 *느려진다* — communication overhead가 quadratic.

→ phase 전환 시 *모든 컨텍스트* 다음 phase에 전달 = brookes communication overhead 폭주. *보존-제거 매트릭스*로 communication path를 *명시적으로 좁힘*.

### 2. Conway's Law (Conway 1968)

> Conway, M. E. (1968). *How do committees invent?*. Datamation, 14(5), 28-31.

핵심: 시스템 구조 = 그것을 만든 조직의 소통 구조와 동형 (isomorphic).

→ APT의 4-phase 분리 자체가 *소통 구조*. phase 간 핸드오프는 *Conway 동형 boundary*. boundary가 명확할수록 system architecture도 명확.

### 3. Information-Theoretic Compression (Shannon 1948)

> Shannon, C. E. (1948). *A Mathematical Theory of Communication*. Bell System Technical Journal, 27.

핵심: 정보 압축은 *redundancy* 제거 + *entropy* 보존. lossless / lossy 구분.

→ Phase Transition Compaction = *lossy compression*. KG에 PROV로 보존 (lossless), 다음 phase에 전달은 lossy. KG가 정전, context는 hot cache.

### 4. Lampson Hints (Lampson 1983)

> Lampson, B. W. (1983). *Hints for Computer System Design*. IEEE Software, 1(1), 11-28.

원칙 9: "When in doubt, leave it out" (의심스러우면 빼라).
원칙 16: "Make it fast, rather than general or powerful" (빠르게, 그것이 일반적·강력함보다 우선).

→ 압축 매트릭스의 "제거" 컬럼은 Lampson #9 적용. 다음 phase가 *진짜* 필요한지 불확실하면 제거 (KG는 보존).

### 통합

Brooks + Conway = *구조적 boundary* 정당화 (왜 phase 분리)
Shannon = *압축 합리성* (KG=lossless, context=lossy)
Lampson = *실용 결정* (제거 컬럼 룰)

→ Phase Transition Compaction은 *4 학문이 동시에 권장*하는 패턴.

# KG: APT_PhaseTransition_canonical, lesson-context-rot-prevention-handoff
