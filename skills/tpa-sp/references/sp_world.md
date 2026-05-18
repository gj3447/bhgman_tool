# SP World Reference (TPA-side)

> TPA v1.1 SP Phase 상세. Mirror sibling: `apt-sp/references/sp_world.md` (forward direction — design decomposition).
> 이 문서는 *역방향* SP: 추출된 Contract 집합에서 *DesignPattern*을 인식한다.

---

## 1. Phase Identity

**SP = TargetPyramid** — ST에서 추출한 Contract들이 모여 형성하는 *상위 패턴*을 식별하고 라이브러리에 매칭한다.

| 질문 | 답 |
|------|----|
| pre-gate | ST VR APPROVED via Hook |
| post-gate | Naesengmoon 9-lens VR + Pattern Library precondition + Distributed → SP-MetaVerify VR |
| 결정 | `INSTANCE_OF` (confidence ≥ 0.7) / `RESEMBLES` (< 0.7) / 매칭 안 함 (< 0.4) |
| 위임 | giant method (TCW에서 deferred) → 패턴 분류 후 분해/Contract 화 결정 |

---

## 2. Pattern Library Precondition

```cypher
MATCH (p:DesignPattern) RETURN count(p) AS n
// 기대: n ≥ 38 (GoF23 + Distributed10 + PL5 baseline)
// 권장: n ≥ 51 (canonical)
// 실제: tpa-pattern-library-audit-iter2-2026-05-06 = 57 patterns post-canonicalization
```

Library 미달 시 BLOCK + ResearchProvider 호출 (`/prom 16 "missing patterns by category"`).

---

## 3. 카테고리별 검증 전략

| Category | Verification Strategy | Tool (MIC slot) |
|----------|----------------------|-----------------|
| **Structural** (Facade/Adapter/Composite/Decorator/Proxy/Bridge/Flyweight) | AST 시그니처 매칭 (wrapping/delegation pattern) | KgCodeBinder + grep |
| **Behavioral** (Strategy/Observer/Command/State/Iterator/Visitor/...) | 메서드 호출 그래프 (polymorphic dispatch) | KgCodeBinder + call graph |
| **Creational** (Factory/Builder/Singleton/AbstractFactory/Prototype) | 생성 지점 추적 | KgCodeBinder + grep |
| **Distributed** (CRDT/BFT/HotStuff/Kademlia/Raft/Paxos/Vector_Clock/HLC/Merkle_Tree/LWW/Gossip) | **수학 속성 검증 강제** (commute/assoc/idempotent/safety/liveness) | **MetaVerifier (88-Naesengmoon mathematical lens)** |
| **PL** (DuckTyping/TypeClass/Monad/Continuation/Arrow) | 언어 기능 존재 확인 | ResearchProvider (lang docs) |
| **Architectural** | 모듈 의존 그래프 + 데이터 흐름 | KgCodeBinder + Longinus |

---

## 4. INSTANCE_OF 판정 — 필수요소 체크리스트

**"이름이 비슷하다" ≠ INSTANCE_OF.** 패턴별 필수요소 *전부* 충족해야 한다 (TR2 evidence + TR_PatternHallucination 차단).

| Pattern | 필수요소 (전부 충족 시 INSTANCE_OF) |
|---------|---------------------------------|
| **Strategy** | (a) 런타임 교환 가능 (b) 같은 인터페이스 (c) 클라이언트 코드 변경 없이 전략 교체 |
| **State** | (a) 상태별 행동 차이 (b) 상태 객체가 dispatch (c) context가 상태에 위임. 단순 enum ≠ State. |
| **Observer** | (a) 동적 등록/해제 (b) 이벤트 broadcast (c) subject가 observer 구체 타입 모름 |
| **Builder** | (a) consuming self 또는 &mut self 메서드 체인 (b) build() 최종 생성 |
| **Facade** | (a) 복잡한 서브시스템 위임 (b) 자체 로직 최소 (직접 오케스트레이션 = Mediator) |
| **Factory** | (a) 생성 로직 분리 (b) 반환 타입이 trait/interface (concrete 아님) |
| **Adapter** | (a) 기존 인터페이스 변환 (b) 원본 코드 수정 없음 |
| **Composite** | (a) 개별/집합 동일 인터페이스 (b) 재귀 구조 |
| **CRDT** | (a) commute (b) assoc (c) idempotent — *세 속성 모두* 88-Naesengmoon 수학 검증 통과 |
| **Raft / Paxos** | (a) safety (b) liveness 88-Naesengmoon 수학 검증 |

**판정 절차**:
1. 필수요소 *전부* 확인 (코드에서 evidence 인용)
2. 전부 충족 → confidence ≥ 0.7 → INSTANCE_OF 결정화
3. 일부만 충족 → confidence < 0.7 → RESEMBLES 결정화
4. 이름만 비슷 → confidence < 0.4 → 매칭하지 않음 (filter out)

---

## 5. INSTANCE_OF / RESEMBLES 결정화

```cypher
// INSTANCE_OF (≥ 0.7 + checklist 통과)
MERGE (src)-[r:INSTANCE_OF {
    confidence: $c,
    evidence: $ev,
    strategy: $verified_by,                        // 'AST' | 'CallGraph' | 'MathProperty' | 'LangFeature'
    checklist_pass: true,
    matched_required_elements: $matched_list,      // ["element1", "element2", ...]
    recovered_from_execution: $exec_name
}]->(p:DesignPattern {name: $pattern_name})

// RESEMBLES (< 0.7 또는 일부 element 미충족)
MERGE (src)-[r:RESEMBLES {
    confidence: $c,
    evidence: $ev,
    matched_elements: $matched,
    missing_elements: $missing,                    // 어떤 필수요소가 부족한지 명시
    recovered_from_execution: $exec_name
}]->(p:DesignPattern {name: $pattern_name})
```

**evidence 누락 → TR_PatternHallucination (HR11 거울)**. Hook이 SP gate에서 차단.

---

## 6. Distributed 패턴 → MetaVerifier 자동 호출

INSTANCE_OF edge가 `category='Distributed'` 패턴으로 생성되는 *즉시*:

```
역할: 88-Naesengmoon MetaVerifier (agentId=M<idx>)
TaskSpec: MATCH (ts:SubagentTaskSpec {name:'taskspec-88taliban-distributed'}) RETURN *
Target: 매칭한 Distributed DesignPattern (CRDT / BFT / HotStuff / Kademlia / Raft / Paxos / Vector_Clock / HLC / Merkle_Tree / LWW)
검증할 수학 속성: commute / assoc / idempotent / safety / liveness (패턴별 상이)
출력: ValidationResult {phase:'SP-MetaVerify', verdict:$v, math_properties:[...]}
```

FulfillmentGate Cypher:
```cypher
MATCH (sp:TPA_SP_Result {name: $sp_name})-[:MATCHED_PATTERN]->(p:DesignPattern {category:'Distributed'})
WITH count(p) AS dp_count
OPTIONAL MATCH (exec)-[:HAS_VALIDATION]->(vr:ValidationResult {phase:'SP-MetaVerify', verdict:'APPROVED'})
RETURN dp_count, count(vr) AS mv_count,
  CASE WHEN dp_count = 0 OR mv_count > 0 THEN 'PASS' ELSE 'FAIL — MetaVerifier required' END AS gate
```

`FAIL` → SP phase 전체 verdict=REJECTED → `/tpa-ta` Hook gate 차단 → TR_DistributedNameOnly 위반.

---

## 7. NovelPattern 처리

라이브러리에 없는 신규 패턴 발견 시:

```cypher
MERGE (np:NovelPattern:AbstractNode {name: 'NP_' + $domain + '_' + $pattern_name})
SET np.description = $desc,
    np.evidence = $ev,
    np.category = $cat,                        // architectural_novel | language_novel | domain_novel
    np.first_observed_in = $target,
    np.discovered_at = datetime(),
    np.candidate_for_library = true
MERGE (sp:TPA_SP_Result)-[:IDENTIFIES_NOVEL]->(np)
```

NovelPattern은 즉시 Pattern Library 추가 *안 함*. Lesson 통해 사용자 verdict + 88-Naesengmoon math (Distributed인 경우) 후 결정.

---

## 8. ResearchProvider 호출 (모르는 패턴)

```cypher
MATCH (s:MethodologySlot {name:'ResearchProvider'})
RETURN s.invocation
-- {invocation} <unknown_pattern_name>
```

결과는 `:KnowledgeNode` + SP Result에 `INFORMED_BY` 엣지.

---

## 9. TPA_SP_Result 결정화

```cypher
MERGE (sp:TPA_SP_Result:AbstractNode {name: 'SP_' + $target_id + '_' + $date})
SET sp.sourcePath = $target,
    sp.totalPatterns = $io_n + $res_n,
    sp.instanceOf_count = $io_n,
    sp.resembles_count = $res_n,
    sp.novelPatterns = $novel_n,
    sp.distributed_metaverified = $mv_n,
    sp.checklist_pass_rate = $pass_rate,            // checklist_pass=true 비율
    sp.created_at = datetime()
MERGE (exec)-[:PHASE_OUTPUT {order:3}]->(sp)
```

---

## 10. FulfillmentGate SP (7 checks)

1. [ ] Pattern Library count ≥ 38 (pre-check 통과)
2. [ ] MECE check: leaf span 중복/누락 없음
3. [ ] 모든 INSTANCE_OF 엣지에 confidence + evidence + strategy + checklist_pass=true
4. [ ] Distributed 카테고리는 SP-MetaVerify VR APPROVED 보유
5. [ ] NovelPattern은 `:NovelPattern` 라벨 + category 지정
6. [ ] orphan span 없음
7. [ ] TPA_SP_Result + PHASE_OUTPUT order=3 엣지 + sourcePath/sourceId SET

---

## 11. Common Failure Modes

| 증상 | 원인 | 처방 |
|------|------|------|
| INSTANCE_OF 다수, checklist_pass=true 비율 낮음 | TR_PatternHallucination (이름만 매칭) | 모두 RESEMBLES로 downgrade, lesson 생성 |
| Distributed pattern matched, no SP-MetaVerify VR | TR_DistributedNameOnly | 88-Naesengmoon auto-fire 후 재실행 |
| confidence ≥ 0.7 인데 evidence empty | HR11 위반 | BLOCK + lesson |
| novel patterns 폭증 (>5/cycle) | Library stale OR 진짜 신규 도메인 | references/error_handling.md §6 (Library audit) |
| SP-MetaVerify FAIL | 수학 속성 미충족 (실제 false positive) | INSTANCE_OF 제거 + RESEMBLES로 + lesson |

---

## 12. References

- `../tpa/references/phases.md` §3
- `../tpa/references/error_handling.md` §4 (Distributed no MetaVerify), §6 (Library drought)
- `../tpa/references/validation.md` V8 (checklist), V12 (Lesson on discovery)
- `../tpa/references/adversarial.md` Anti-rubber-stamp #11-#14
- `../apt-sp/references/sp_world.md` (mirror — forward direction, span decomposition)

# KG: ATOM_Skill_tpa_sp, tpa-pattern-library-audit-iter2-2026-05-06, fw-tpa-references-apt-parity-2026-05-06
