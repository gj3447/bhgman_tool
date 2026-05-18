---
name: tpa
version: 0.3
description: TPA 방법론 — APT의 완전한 역순 사이클. 기존 소스코드를 출발점으로 역방향으로 KG 재구성. 레거시 흡수 / 드리프트 탐지 / 리뷰 / 온보딩. Invoke when /tpa <path> 또는 새 외부 repo 분석 / drift 감사 / 코드 → KG 역바인딩. v0.3: 8 gap lesson 반영 — 각 phase 진입시 SubagentSeeder taskspec 조회 필수, 종료시 AdversarialValidator gate 자동, DriftReport coverage threshold, ConventionalContract 라벨 분리, pattern 검증 전략 매핑, FulfillmentGate.
---

## 🔗 MIC Binding (SOLID-DIP)

**ROLE**: External-ingestion mirror (APT 역순).
**USES slots**: ResearchProvider · AdversarialValidator · MetaVerifier · KgCodeBinder · SubagentSeeder

```cypher
MATCH (mic:MethodologyIntegrationContract {name:'MIC_v1'})-[:HAS_SLOT]->(s:MethodologySlot)
RETURN s.name, s.currentConcrete, s.invocation
```

**진짜 호출은 항상 MIC slot 경유.** 본문 concrete 이름은 현재 스냅샷.

# KG: MIC_v1, lesson-apt-not-truly-jaebaeman-2026-04-14, TPA_methodology

---

# /tpa — Tracing · Pattern · Anchor (APT 역순)

> **원칙**: "기존 코드가 스스로 무엇인지 말하게 하라. KG에서 먼저 답을 가정하지 말 것."
> APT는 생성(의도→코드), TPA는 해석(코드→의도). 둘이 짝 이뤄 drift 0 닫음.

**KG 방법론 노드**: `TPA_methodology` (v0.3 — 8 gap 해결)
**4 Phase**: TCW → TT → TP → TA (APT의 SCW/ST/SP/SA 거울)
**파일럿 기록**: `TPA_exec_aider_coders_2026-04-14` (v0.1), `TPA_exec_aider_full_2026-04-14` (v0.2 audit)

---

## 입력 형식

```
/tpa <path>                       # 경로 분석 → 4 phase 실행
/tpa --audit <anchor>             # 기존 SemanticAnchor drift 감사
/tpa --status                     # 실행 중/미완 목록
```

---

## v0.3 핵심 개선 (8 gap 반영)

| gap | 해결 |
|---|---|
| 01 Prometheus 미적용 | TCW unknown_dirs>0 시 `ResearchProvider.invocation` 자동 호출 |
| 02 재배맨 bypass | 각 phase **진입시 첫 동작**: 해당 phase taskspec 조회 강제 |
| 03 ConventionalContract 라벨 | TT phase가 독립 `:ConventionalContract` 노드 생성 |
| 04 88-Naesengmoon 범위 매핑 | TP phase: 패턴 카테고리별 검증 전략 테이블 |
| 05 FulfillmentGate 누락 | 각 phase 종료시 체크리스트 통과 강제 |
| 06 DriftReport threshold | coverage < 0.8 → `status='SUSPENDED'` |
| 07 treasure coverage gate | taskspec에 `treasure_coverage_min` 필드 |
| 08 Naesengmoon phase-gate | 각 phase 종료마다 `AdversarialValidator.invocation` 자동 |

---

## 5대 신기 (MIC Slot) 적용 매트릭스

각 phase가 어느 slot을 **강제 호출**해야 하는지:

| Phase | SubagentSeeder | ResearchProvider | KgCodeBinder | MetaVerifier | AdversarialValidator |
|---|---|---|---|---|---|
| TCW | **진입시** (taskspec) | unknown 발견시 자동 | 파일 기록 | — | 종료시 |
| TT | **진입시** | giant method 만날 때 | Contract 기록 | (선택) | 종료시 |
| TP | **진입시** | 모르는 패턴 | — | pattern 카테고리별 | 종료시 |
| TA | **진입시** | — | SourceBinding | drift 검증 | **최종 gate** |

---

## 4 Phase 정밀화

### Phase 1: TCW — Target Code World (SCW 거울)

**질문**: "이 코드에 실제로 존재하는 것은 무엇인가?"

**진입 의식 (gap02 해결)** — 반드시 먼저:
```cypher
MATCH (ts:SubagentTaskSpec {name:'taskspec-tpa-TCW', skill:'tpa'})
RETURN ts.checkItems, ts.cypherQueries, ts.expectedOutcome, ts.treasure_coverage_min
```

**실행**:
- Glob 대상 파일, LOC 계산, pub 심볼 추출 (tree-sitter 권장)
- InheritanceTree 1급 필드 (FB02)
- architectural_guess 조기 출력 (FB01)

**Unknown 발동 (gap01)**:
```cypher
-- unknown_dirs 비어있지 않으면 ResearchProvider 자동
MATCH (s:MethodologySlot {name:'ResearchProvider'})
RETURN s.invocation AS auto_call_for_each_unknown
```
각 unknown에 대해 `{invocation} <unknown>` 호출. 결과는 KnowledgeNode로 저장 + TCW_Result에 INFORMED_BY.

**FulfillmentGate TCW (gap05)**:
- [ ] 파일 100% 스캔 (skipped_files=0)
- [ ] unknown_dirs 전부 ResearchProvider 처리 (outstanding=0)
- [ ] architectural_guess 필드 채움
- [ ] taskspec.checkItems 전부 pass
- [ ] TCW_Result 노드 + PHASE_OUTPUT 엣지

**종료 (gap08)**:
```cypher
MATCH (s:MethodologySlot {name:'AdversarialValidator'})
RETURN s.invocation AS gate_call
-- {gate_call} TPA_TCW_<target>
```

---

### Phase 2: TT — Target Twin (ST 거울)

**질문**: "각 심볼이 지키고 있는 암묵적 계약은 무엇인가?"

**진입**: `taskspec-tpa-TT` 조회.

**Contract 분류 (gap03 해결)**:
```cypher
-- 명시 interface/trait → AptContract
MERGE (c:AptContract:AbstractNode {name:$name})
SET c.declared_in=$file, c.type='explicit'

-- 암묵 convention → ConventionalContract (독립 노드 라벨)
MERGE (cc:ConventionalContract:AbstractNode {name:$name})
SET cc.inferred_from=$signatures, cc.type='implicit',
    cc.implementors=$subclasses
```

**LOC > 100 메서드**는 AtomicSpan 아님 → TP phase로 deferred.

**FulfillmentGate TT**:
- [ ] 각 Contract에 precondition/postcondition 필드
- [ ] `AptContract` vs `ConventionalContract` 라벨 명확히 분리
- [ ] giant_methods_deferred 목록 TP로 전달
- [ ] 종료 AdversarialValidator gate

---

### Phase 3: TP — Target Pyramid (SP 거울)

**질문**: "이 심볼들이 모여 어떤 패턴/구조를 이루는가?"

**진입**: `taskspec-tpa-TP` 조회 + Pattern Library (51 nodes) 존재 확인.

**패턴 검증 전략 매핑 (gap04 해결)**:

| Pattern Category | Verification Strategy | Tool (MIC slot) |
|---|---|---|
| Distributed (CRDT/BFT/HotStuff/Kademlia 등) | 수학 속성 (commute/assoc/idempotent/safety) | MetaVerifier (88-Naesengmoon) |
| Structural (Facade/Adapter/Composite 등) | AST 시그니처 매칭 (wrapping/delegation) | KgCodeBinder + grep |
| Behavioral (Strategy/Observer/Command 등) | 메서드 호출 그래프 (polymorphic dispatch) | KgCodeBinder + call graph |
| Creational (Factory/Builder/Singleton 등) | 생성 지점 추적 (instantiation trace) | KgCodeBinder + grep |
| PL (DuckTyping/TypeClass/Monad 등) | 언어 기능 존재 확인 | ResearchProvider (lang docs) |

**confidence 규칙**:
```cypher
-- ≥ 0.7 → INSTANCE_OF, < 0.7 → RESEMBLES
MERGE (src)-[r:INSTANCE_OF {confidence:$c, evidence:$ev, strategy:$verified_by}]->(p:DesignPattern)
WHERE $c >= 0.7
-- else
MERGE (src)-[r:RESEMBLES {confidence:$c}]->(p)
```

**모르는 패턴 만나면** ResearchProvider 자동.

**FulfillmentGate TP**:
- [ ] MECE check (leaf span 중복/누락 없음)
- [ ] 모든 INSTANCE_OF 엣지에 confidence + evidence + strategy
- [ ] Distributed 카테고리는 MetaVerifier 수학 검증 완료
- [ ] orphan span 없음
- [ ] 종료 AdversarialValidator gate

---

### Phase 4: TA — Target Anchor (SA 거울)

**질문**: "이 구조는 어디에 속하는가?"

**진입**: `taskspec-tpa-TA` 조회.

**라우팅** (apt-sa 2-A/B/C 재사용):
- 2-A 신규 / 2-B 재사용 / 2-C 브랜치

**Longinus 전수 바인딩** (KgCodeBinder):
- TCW 파일 목록의 **모든** pub 심볼에 SourceBinding
- Longinus coverage = bound / total

**DriftReport (gap06 해결)**:
```cypher
-- coverage < 0.8 이면 SUSPENDED
MERGE (dr:DriftReport {name:'DRIFT_' + $anchor + '_' + $date})
SET dr.coverage_ratio = $bound / $total,
    dr.status = CASE WHEN ($bound / toFloat($total)) < 0.8 THEN 'SUSPENDED' ELSE 'VALID' END,
    dr.missing = $m, dr.orphan = $o, dr.signature_mismatch = $s,
    dr.pattern_divergence = $p, dr.label_rot = $l
```

**Drift 5종**:
| 종류 | 조건 | 심각도 |
|---|---|---|
| Missing | KG에 없는 pub symbol | MEDIUM |
| Orphan | KG엔 있는데 코드 없음 | HIGH |
| SignatureMismatch | Contract vs 실제 시그니처 | CRITICAL |
| PatternDivergence | 주장 속성과 실제 코드 불일치 | CRITICAL |
| LabelRot | 주석 KG ref의 대상 노드 삭제됨 | LOW |

**FulfillmentGate TA (최종)**:
- [ ] coverage_ratio ≥ 0.8 (아니면 SUSPENDED 명시)
- [ ] 모든 drift 종류 측정됨 (skipped=0)
- [ ] SemanticAnchor + Root Span + SourceBinding 체인
- [ ] `AdversarialValidator.invocation` **전체 결과** gate 통과

---

## Treasure Coverage Thresholds (gap07)

각 taskspec은 `treasure_coverage_min` 필드 필수:

```cypher
MATCH (ts:SubagentTaskSpec {skill:'tpa'})
RETURN ts.name, ts.treasure_coverage_min
-- 예:
-- taskspec-tpa-TCW → {KgCodeBinder:0.95, ResearchProvider:1.0}  (파일 95% 바인딩, unknown 100% 리서치)
-- taskspec-tpa-TA  → {KgCodeBinder:0.80, AdversarialValidator:1.0}
```

미만이면 phase FAIL.

---

## 트리거 시나리오

| 트리거 | 범위 | 속도 |
|---|---|---|
| Git hook post-commit | 변경 파일 (TCW+TT+drift) | 초 |
| Agent onboarding | 전체 풀 4 phase | 분 |
| Audit on demand | 특정 anchor sub-tree | 중간 |

---

## KG SubagentTaskSpec 재배맨 패턴

```cypher
-- 세션 진입 시 진행중 TPA 복구
MATCH (exec:TPA_Execution) WHERE exec.phase_current <> 'COMPLETE'
RETURN exec.name, exec.phase_current, exec.started_at ORDER BY exec.started_at DESC LIMIT 5

-- 씨앗 목록
MATCH (ts:SubagentTaskSpec {skill:'tpa'})
WHERE ts.status STARTS WITH 'READY'
RETURN ts.name, ts.phase, ts.treasure_coverage_min
```

### Subagent 출격 (3줄 — KG가 본체)
```
역할: {ts.displayName}  (agentId=D<idx>)
TaskSpec 조회: MATCH (ts:SubagentTaskSpec {name:'<spec_name>'}) RETURN ts.*
Target: $TARGET. Phase: {TCW|TT|TP|TA}.
출력: FullFindingRecord JSON (provenance='재배맨-tpa').
```

---

## Example — aider/coders TPA 실행 (reference)

`TPA_exec_aider_coders_2026-04-14`

- **TCW**: 37 py files, 6923 LOC, 18 classes. Arch guess = Strategy+Template+ParallelHierarchy
- **TT**: `CoderStrategy` ConventionalContract (get_edits/apply_edits 공유), 18 implementors
- **TP**: Strategy(0.95), Template(0.90), ParallelHierarchy(0.85) INSTANCE_OF
- **TA**: SemanticAnchor `aider_coders` (2-A 라우팅), DriftReport baseline
- **Feedback**: FB01-05 (v0.3 gap 해결의 씨앗)

재현:
```cypher
MATCH (e:TPA_Execution {name:'TPA_exec_aider_coders_2026-04-14'})-[r]->(n)
RETURN e.name, type(r), n.name, labels(n) LIMIT 30
```

---

## What NOT to Do

| 금지 | 이유 | 대안 |
|---|---|---|
| Pattern library 없이 TP 진입 | 중복 노드 생성 | 38 노드 사전 시드 (Phase 3 진입 pre-check) |
| AST 없이 regex만 | 주석/문자열 오인식 | tree-sitter 또는 언어별 ast |
| confidence 없이 INSTANCE_OF | rubber-stamp | ≥0.7 + evidence + verification strategy |
| AdversarialValidator gate 없이 phase 이동 | 오류 누적 | 각 phase 종료마다 자동 |
| Convention과 Apt Contract 섞기 | ontology 오염 | 독립 노드 라벨 |
| coverage < 0.8에 drift=0 claim | false baseline | `status='SUSPENDED'` 명시 |
| unknown_dirs 있는데 ResearchProvider skip | 지식 공백 | unknown 건별 자동 호출 |
| taskspec 조회 없이 phase 실행 | 재배맨 bypass, 컨텍스트 오염 | phase 진입 첫 동작 강제 |

---

## References

- Methodology: `TPA_methodology` (v0.3)
- Integration: `MIC_v1` — 5 MethodologySlot 동적 참조
- Pattern Library: 51 `DesignPattern` nodes (GoF+분산+PL)
- TaskSpecs: `taskspec-tpa-{TCW,TT,TP,TA}` (4 씨앗)
- Prior executions: `TPA_exec_aider_coders_2026-04-14`, `TPA_exec_aider_full_2026-04-14`
- Gap lessons (v0.3 입력): `lesson-tpa-gap-01~08-2026-04-14`
- Mirror: `APT_v24` (MIRRORS 관계)

# KG: TPA_methodology (v0.3), MIC_v1, lesson-tpa-gap-01~08
