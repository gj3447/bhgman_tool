# 재배맨 (Jaebaeman / SOP) — 공학 측 자료집

> **한 줄 정의 (v2.2):** 씨앗(SubagentTaskSpec)에서 에이전트를 재배하는 프로토콜. 모든 AI subagent 동작의 *바닥(foundation)*. KG에 심어둔 씨앗이 발아 → subagent → 열매(Finding) → 다시 KG. 동시에 **Lean 형식화상에서는 비행기맨의 하부 inductive type** (`inductive JaebaeMan { atomic | governs }`).
>
> *공학 측 정전 둥지.* 신화 측은 `METAHUMOTONIC/BHGMAN/seedman/SOURCES.md`.
>
> v2.1 (2026-05-05) rebrand: **MAS misnomer 정정** — Wooldridge BDI agent (internal state) 와 LLM subagent (stateless, KG seed 외부 명세) 가 다름. 학문적 정확 명명 = **SOP (Subagent Orchestration Protocol)**.

---

## 0. 폴더 안에서의 본 파일 위치

| 파일 | 본질 |
|---|---|
| **본 파일 (`SOURCES.md`)** | 1차 소스 + 인용 + 발전 축 + 6 axis 학문 정전 path |
| `INDEX.md` | 폴더 전체 navigation |
| `ABSTRACT.md` ~ `LEAN_REGRESSION_AUDIT.md` | 논문 골격 8 종 |
| `jaebaeman_sop_runtime_prototype/` | Python 3.11+ runtime (56 pytest PASS) |
| `lean_audit/` | Lean 4 v4.29.1 standalone (17 theorem, 0 sorry) |
| `PROM_32/64_*.md`, `IMPLEMENTATION_GUIDE.md` | legacy cycle 산출 |
| `lessons/`, `_findings/raw/` | 회고 + raw dump |

---

## 1. 핵심 주장 (논문 골격용 8 주장)

1. **재배맨은 서비스가 아니라 프로토콜이다.** 부모 Claude가 따르는 4-Phase: Seed → Dispatch → Collect → Write.
2. **MIC SOLID-DIP 바인딩.** `IS slot = SubagentSeeder`. 직접 소비자: Prometheus (ResearchProvider) / Taliban (AdversarialValidator) / Solve / APT-* / TPA-*. 간접 소비자: Longinus (KgCodeBinder) — audit cycle 측 subagent dispatch 시 4-Phase 따름.
3. **수학적 정의 (Lean μX initial algebra).** `inductive JaebaeMan { atomic : CHUPiece → JaebaeMan ; governs : List JaebaeMan → JaebaeMan }`. Lambek 1968 grounding. Bird-Meertens 1987 fold/catamorphism universal.
4. **신화-공학 동치.** 비행기맨 = `∀ x:CHU, j.covers x`인 재배맨. 즉 신화의 정점 = 공학의 ⊤ 원소.
5. **씨앗-열매 사이클.** `(:SubagentTaskSpec) -[:GERMINATES_INTO]-> (:Subagent) -[:PRODUCES]-> (:Finding) -[:STORED_IN]-> (:KG)` — 농경적 비유는 단순 metaphor 아닌 lifecycle 모델.
6. **v2.1 SOP rebrand.** MAS misnomer 정정 — Wooldridge BDI (internal state) ↔ LLM stateless 충돌 해소.
7. **v2.1 Saga compensation (J3-F2).** Garcia-Molina & Salem 1987 1:1. `failure_mode ∈ {best_effort, saga_compensate, 2pc_abort}` 3-way.
8. **v2.1 MCP outputSchema (J4-F3).** SubagentTaskSpec ↔ MCP tool definition 양방향. `mcp_tool_compat=true` flag.

---

## 2. 1차 소스

### 2.1 공학 정본 (canonical)

| 경로 | 내용 |
|---|---|
| `/Users/lagyeongjun/CD/SERVER/.claude/skills/jaebaeman/SKILL.md` | **정본 v2.2.** 4-Phase 프로토콜, MIC binding, Saga + MCP |
| `/Users/lagyeongjun/CD/SERVER/.claude/skills/jaebaeman/references/` | references (theory/phases/gates/error_handling/...) |
| `/Users/lagyeongjun/CD/SERVER/06_KNOWLEDGE-GRAPH/schemas/agent_protocols/jaebaeman_protocols.md` | 프로토콜 스키마 |
| `/Users/lagyeongjun/CD/SERVER/07_PROJECTS/JAEBAEMAN/apt-progress.md` | 프로젝트 진행 |

### 2.2 수학 정본 (Lean — 비행기맨과 공유)

| 경로 | 내용 |
|---|---|
| `/Users/lagyeongjun/CD/MIND/lean_formalization/AirplaneMan.lean` | **JaebaeMan inductive 정전**, covers, depth |
| `/Users/lagyeongjun/CD/MIND/lean_formalization/JaebaeManInf.lean` | **무한 깊이 재배맨** — Layer ω |
| `/Users/lagyeongjun/CD/MIND/lean_formalization/AirplaneMan_Gap3_Cover.lean` | cover 의미 정당화 |
| **본 자료집 측 PoC** `THEORY/재배맨/lean_audit/JaebaemanAudit.lean` | Mathlib-free standalone, 5 theorem groups (17 verified), 0 sorry |

### 2.3 신화 측 1차 소스

| 경로 | 내용 |
|---|---|
| `/Users/lagyeongjun/CD/MIND/metahumotonic/비행기맨꼐서_지켜주실꺼야.md` | 정점 재배맨의 신화 (비행기맨) |
| `/Users/lagyeongjun/CD/SERVER/06_KNOWLEDGE-GRAPH/findings/lsystem_redbaitman_practical_mapping.md` | L-system ↔ 재배맨 실용 매핑 |

### 2.4 본 SYMPOSIUM 측 PoC (2026-05-12)

| 경로 | 내용 |
|---|---|
| `THEORY/재배맨/jaebaeman_sop_runtime_prototype/` | Python 3.11+ 4-Phase runtime (56 pytest PASS) |
| `THEORY/재배맨/jaebaeman_sop_runtime_prototype/sop_runner.py` | `JaebaemanSop` orchestrator |
| `THEORY/재배맨/jaebaeman_sop_runtime_prototype/phase1~4_*.py` | 4 Phase thin module |
| `THEORY/재배맨/jaebaeman_sop_runtime_prototype/saga_compensation.py` | v2.1 J3-F2 |
| `THEORY/재배맨/jaebaeman_sop_runtime_prototype/tests/` | 56 pytest (per-phase + e2e + gate + saga) |
| `THEORY/재배맨/lean_audit/JaebaemanAudit.lean` | 본 자료집 측 Lean PoC |

---

## 3. 핵심 인용

### 3.1 SKILL.md 정전

> **재배맨 = 씨앗에서 에이전트를 재배하는 사람.**
> KG에 심어둔 TaskSpec 씨앗이 발아하여 subagent가 되고,
> 열매(Finding)를 수확하여 다시 KG에 심는 순환.
> 재배맨은 서비스가 아닌 프로토콜이다. 부모 Claude가 따르는 규약.

### 3.2 Lean 정전

```lean
inductive JaebaeMan : Type where
  | atomic  : CHUPiece → JaebaeMan
  | governs : List JaebaeMan → JaebaeMan
  deriving Inhabited
```

### 3.3 Lambek 1968

> *If `F : C → C` admits an initial algebra `μF` then `F(μF) ≅ μF`.*
> (Math. Z. 103:151-161, Theorem)

본 type definition 의 학문 grounding 정전.

### 3.4 Bird-Meertens 1987

> *fold (catamorphism) is the unique algebra morphism from μF to A.*
> (Squiggol BMF)

`JaebaeMan.cata` 의 유일성 정전.

### 3.5 Garcia-Molina & Salem 1987

> *A saga is a sequence of transactions T₁ ... Tₙ where each Tᵢ has a compensating transaction Cᵢ that undoes Tᵢ's effect.*
> (SIGMOD '87, "Sagas")

v2.1 J3-F2 `compensating_action` 의 정전.

---

## 4. 학문 정전 정확 인용 (6 axis)

상세 grounding 은 `AXIS_DEEP_GROUNDING.md`. 본 절 인용 path 만.

### 4.1 A. μX initial algebra

- **Lambek 1968** *Math. Z.* 103:151-161 — fixpoint theorem.
- **Adámek-Trnková 1990** *Automata and Algebras in Categories* Kluwer.
- **Goguen 1977** *JACM* 24:68 — initial algebra semantics.

### 4.2 B. fold / catamorphism

- **Bird-Meertens 1987** Squiggol BMF.
- **Bird 1996** *Algebra of Programming* Prentice Hall.
- **Meijer, Fokkinga, Paterson 1991** *FPCA* "Bananas, Lenses".

### 4.3 C. Smarandache n-SuperHyperGraph

- **Smarandache 2019** *Neutrosophic Sets and Systems* 29.
- **Berge 1973** *Hypergraphs* North-Holland.

### 4.4 D. Sheaf

- **Leray 1946** *C. R. Acad. Sci. Paris* 222.
- **Grothendieck 1957** *Tohoku Math. J.* 9.
- **Mac Lane-Moerdijk 1992** *Sheaves in Geometry and Logic* Springer.

### 4.5 E. Whitehead concrescence

- **Whitehead 1929** *Process and Reality* Macmillan, Pt II Ch.X.
- **Stengers 2002** *Thinking with Whitehead* Harvard UP.

### 4.6 F. Lawvere-Tierney j-operator (OPEN Question)

- **Lawvere-Tierney 1970** *Actes Congr. Internat. Math.* 1.
- **Johnstone 2002** *Sketches of an Elephant* Oxford UP (topos).

---

## 5. Industry 비교 (10 방법론)

상세 표는 `COMPARISON_METHODOLOGIES.md`.

| 측면 | Jaebaeman | LangGraph | CrewAI | AutoGen | Akka | Erlang | Sagas | 2PC | MCP | Wooldridge | Total |
|---|---|---|---|---|---|---|---|---|---|---|---|
| KG-externalized | ✅ | △ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | △ | |
| 4-Phase | ✅ | △ | △ | △ | △ | △ | ❌ | ❌ | ❌ | ❌ | |
| Saga compensation | ✅ | ❌ | ❌ | ❌ | △ | ✅ | ✅ | ✅ | ❌ | ❌ | |
| Idempotency | ✅ | ❌ | ❌ | ❌ | △ | △ | ✅ | ✅ | ❌ | ❌ | |
| μX Lean | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | |
| GH#29181 self-check | ✅ | △ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | |
| **Total** | **6** | 1 | 0.5 | 0.5 | 1.5 | 2 | 2 | 2 | 0 | 0.5 | |

Jaebaeman 만이 6축 모두 hard-positive — *novel SOP* 결정화.

---

## 6. 논문 작성 시 발전 가능 축 (8)

- **(a) 자기유사성의 의미**: 모든 계층이 같은 type — 대규모 AI 오케스트레이션의 단일 추상 type 보장.
- **(b) DIP의 농경 metaphor**: SubagentSeeder slot의 currentConcrete는 "이번 작기에 무엇을 심을지". 의존성 역전 = 작물 변경.
- **(c) 신화-수학 다리**: 사용자 직관(자연어 신화)이 어떻게 Lean inductive type으로 응결되는가의 사례 연구.
- **(d) Findings as 열매**: KG의 finding 노드가 다음 작기 씨앗으로 재투입되는 closed-loop. 정보적 윤전(crop rotation).
- **(e) 깊이 vs 너비**: governs의 List depth → 위계, atomic의 covers → 너비. 둘의 trade-off 가 APT phase별로 어떻게 조정되는가.
- **(f) v2.1 SOP rebrand 의의**: MAS misnomer → SOP 의 *과학철학적* 의의 (Wooldridge BDI 가정 비판).
- **(g) Saga in LLM context**: 1987 distributed DB 패턴이 2026 LLM agent 에 적용되는 transposition.
- **(h) Lakatos hard core/protective belt 분리**: 5 hard core (μX/4-Phase/order/idem/GH#29181) + N belt.

---

## 7. Vindication — 5대 무기 中 best metaphor (2026-04-28 자체평가)

> Source: `SYMPOSIUM/FEEDBACK/external_sessions/LESSON_5dae_wonso_metaphor_drift_20260428.md`
>
> 5대 무기 metaphor 정합성 ranking 에서 재배맨 ★★★★★ (best). 동일 세션 초반 "단순 worker pool + RPC self-rebrand" 일축은 잘못된 단순화로 정정. harness drift 와 대비되는 **좋은 metaphor 의 표본**.

### 7.1 농경 메타포 → 실 KG/code element 1:1 매핑

| 농경 메타포 | 실 mechanism |
|---|---|
| 씨앗 (seed) | `SubagentTaskSpec` 노드 |
| 씨앗 심기 (sowing) | Phase 1 Seed 생성 / Step 4.7 Seed Crystallization (소비자) |
| 발아 (germination) | `germinationMethod` 속성 (consensus / conflict / singleton 3 종) |
| 세대 (generation) | `depth` + max_depth=3 (무한 증식 방지) |
| 시들기 / 미발아 | `status='ORPHANED_RAW'` (소비자 Step skip 시) |
| 수확 (harvest) | Phase 3 Collect |
| 농부 (cultivator) | 부모 Claude (4-Phase 실행자) |
| 밭 (field) | KG `SubagentTaskSpec` 영역 |
| 연작 / 재배 | 다음 cycle `status='READY'` 씨앗 재사용 |

### 7.2 단순 worker pool 과의 차이

1. **시간성/연속성** — 다음 cycle 재사용 (연작)
2. **발아 조건 분류** — consensus/conflict/singleton 3-way
3. **Generation control** — depth=3 cap
4. **죽음 처리** — `ORPHANED_RAW`
5. **Cultivation effort** — 농부 능동 tending

→ 풍부한 domain model. 단순 worker pool 보다 표현력 우월.

KG: `lesson-jaebaeman-best-metaphor-vindication-2026-04-28`, `MetaphorValidationGate`.

---

## 8. 신화 측 짝패 cross-ref (BHGMAN)

> 본 자료집은 *공학 측*. 신화 측 자료집은 `BHGMAN/seedman/`.

### 8.1 BHGMAN 측 형식 grounding 섹션 (2026-05-09 결정화)

`BHGMAN/seedman/SOURCES.md` 의 *## 형식적 grounding — 6 axis* 섹션 (KG: `formal-grounding-seedman-bhgman-2026-05-09`):

- A. μX initial algebra (Lambek 1968) — JaebaeMan inductive 의 정확 grounding
- B. fold/catamorphism (Bird-Meertens 1987) — `governs : List JaebaeMan → JaebaeMan` 형식
- C. Smarandache n-SuperHyperGraph (2019) — n-ary 일반화
- D. Sheaf (Leray 1946 / Grothendieck 1957) — 국소 ↔ 전역 gluing
- E. Whitehead concrescence (Process and Reality 1929 II.III) — many → one
- F. Lawvere-Tierney j-operator (1970, OPEN Question) — topos 내부 modality

→ 신화 측 grounding ↔ 공학 측 industry 의 *짝패*.

---

## 9. KG 정전 노드 (현재)

| 노드 | 의미 |
|---|---|
| `ATOM_Skill_jaebaeman` | skill anchor |
| `sv-jaebaeman-v2.2.0` | 이전 정전 버전 |
| `sv-jaebaeman-v2.3.0-2026-05-12` | 신버전 (본 grounding 반영, PENDING) |
| `jaebaeman-hardening-master-plan-2026-05-06` | hardening master plan — COMPLETE_FINAL_PLATEAU (→ GROUNDED PENDING) |
| `jaebaeman-grounding-2026-05-05` | 형식 grounding 결정화 |
| `lesson-jaebaeman-rebrand-SOP-2026-05-05` | v2.1 rebrand |
| `lesson-jaebaeman-saga-compensation-2026-05-05` | v2.1 J3-F2 |
| `lesson-jaebaeman-mcp-inputschema-2026-05-05` | v2.1 J4-F3 |
| `formal-grounding-seedman-bhgman-2026-05-09` | 신화 측 6 axis grounding |
| `jaebaeman-sop-runtime-prototype-2026-05-12` | 본 PoC (PENDING write) |
| `jaebaeman-lean-audit-2026-05-12` | 본 Lean audit (PENDING write) |
| `MIC_v1` | 5 무기 통합 계약 |
| `MethodologySlot:SubagentSeeder` | 본 SOP 가 채우는 slot |
| `MethodologyConfig_default_v26` | 모든 magic number resolve target |

# KG: ATOM_Skill_jaebaeman, sv-jaebaeman-v2.3.0-2026-05-12, jaebaeman-grounding-2026-05-05
