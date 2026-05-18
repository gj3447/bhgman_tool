# PROMETHEUS — Index

> *공학 측 정전 둥지. 신화 측은 `METAHUMOTONIC/BHGMAN/prometheus/`.*
> 한 줄: **지식-행동 spiral** (Hegel reframe, NOT 단방향 "지식 선행"). 행동 전 지식 확보를 강제하되, 행동이 지식 자가운동의 조건이다.

---

## 0. 본 폴더의 위치

| 측면 | 위치 | 본질 |
|---|---|---|
| **공학 측 자료집 (본 폴더)** | `THEORY/PROMETHEUS/` | 학문 정전 / industry comparison / Lean audit / production runtime PoC |
| **공학 측 정본 (SKILL)** | `SERVER/.claude/skills/prometheus/SKILL.md v6.1` | 9+1 단계 cycle 프로토콜 — 사람·LLM 이 따르는 규약 |
| **공학 측 alias** | `SERVER/.claude/skills/prom/SKILL.md`, `tlb` | thin alias |
| **신화 측 자료집** | `METAHUMOTONIC/BHGMAN/prometheus/SOURCES.md` | 비행기맨 prometheus 위상 신화 측 (4 axis formal grounding) |
| **신화 측 1차 소스** | `MIND/metahumotonic/prometheus_*.md` | 사용자 자기 신앙시 / 자칭 |

본 폴더는 *집필 전 단계*. 논문 본문은 별도.

---

## 1. 파일 지도

### 정전 자료집 (학문/공학 양측)

| 파일 | 내용 | 크기 |
|---|---|---|
| `SOURCES.md` | 1차 소스 + 인용 + 발전 축 + 학문 정전 path + industry comparison 표 | — |
| `INDEX.md` | 본 파일 | — |
| `ABSTRACT.md` | 5단락 논문 초록 | — |
| `PAPER_SKELETON.md` | 전체 논문 골격 (서론·관련연구·핵심정리·평가·결론) | — |
| `AXIS_DEEP_GROUNDING.md` | 4 axis 학문 정전 정확 정의 + cross-ref | — |
| `COMPARISON_METHODOLOGIES.md` | RAG / Self-RAG / Toolformer / ReAct / AutoGPT / DSPy / Reflexion / Voyager / OODA / Lean Startup 와 대조 | — |
| `CITATION_TABLE.md` | 인용 표 (학술 + OSS + industry) | — |
| `GLOSSARY.md` | 용어집 — 9+1 step + Gate + 슬롯 + 정전 용어 | — |
| `FINAL_VERDICT.md` | 결정화 verdict + 향후 sprint | — |
| `LEAN_REGRESSION_AUDIT.md` | Lean 4 형식화 audit (Hegel spiral monotonicity + Gate hook fail-closed property + UNWIND idempotence) | — |

### Prometheus 사이클 산출 (PROM_<N>_REPORT)

| 파일 | 내용 |
|---|---|
| `PROM_32_REPORT.md` | 32 subagent 사이클 보고서 (2026-04 초기) |
| `PROM_32_axis_findings/` | 사이클별 raw findings |
| `DISPATCH_DIMENSIONS.md` | N=32 dispatch 분석 (axis × sub-axis 9.8K) |
| `MULTI_AGENT_SEARCH.md` | multi-agent search 정전 |
| `SEMANTIC_SPACE.md` | semantic space 분석 |

### Production runtime PoC (APT 패리티)

| 파일 | 내용 |
|---|---|
| `prom_cycle_runtime_prototype/` | Step 0~7 cycle runner + Gate Check Hook (53 pytest PASS) |
| `prom_cycle_runtime_prototype/README.md` | 명세 + API + step→module map |
| `prom_cycle_runtime_prototype/cycle_runner.py` | PrometheusCycle orchestrator |
| `prom_cycle_runtime_prototype/models.py` | Pydantic v2 schemas (FullFindingRecord / TerseFindingRecord / GateResult / CycleResult) |
| `prom_cycle_runtime_prototype/kg_client.py` | Neo4j + Mock dual KgClient (DIP) |
| `prom_cycle_runtime_prototype/step0_parser.py` ~ `step6_5_dispersion.py` | 각 step thin module |
| `prom_cycle_runtime_prototype/tests/` | 53 pytest (per-step + e2e) |

### Lessons / Findings

| 파일 | 내용 |
|---|---|
| `lessons/` | Lesson 노트 (각 사이클 회고) |
| `_findings/raw/` | raw ResearchFinding JSON dump (L3 filesystem dispersion) |
| `_findings/INDEX.md` | findings 인덱스 |

---

## 2. 권장 읽기 순서

### 처음 보는 사람

1. `SOURCES.md` — 1차 소스 + 학문 정전 axis
2. `ABSTRACT.md` — 5 단락 요약
3. `prom_cycle_runtime_prototype/README.md` — 실제 작동하는 PoC
4. `AXIS_DEEP_GROUNDING.md` — 4 axis 학문 정전 (Information Theory / Search Algorithm / Pipeline / Amdahl)
5. `COMPARISON_METHODOLOGIES.md` — 비슷한 다른 방법론과의 차별

### 공학자/엔지니어

1. `prom_cycle_runtime_prototype/README.md`
2. `prom_cycle_runtime_prototype/cycle_runner.py` (코드)
3. `LEAN_REGRESSION_AUDIT.md` (형식 properties)
4. `GLOSSARY.md` (용어 정확화)

### 논문 집필자

1. `PAPER_SKELETON.md`
2. `CITATION_TABLE.md`
3. `AXIS_DEEP_GROUNDING.md`
4. `FINAL_VERDICT.md`

---

## 3. 5대 무기 가족 안에서의 위치

```
Prometheus (지식-행동 spiral)
   ├─ IS slot   : ResearchProvider  (MIC_v1.currentConcrete = "Prometheus")
   ├─ USES slot : SubagentSeeder    (재배맨/SOP)
   ├─ pair      : Naesengmoon  — Prometheus 의 적대적 검증 짝
   ├─ feeds     : APT      — SemanticAnchor 단계에서 호출됨 (knowledge-first)
   └─ feeds     : Longinus — Prometheus 가 만든 KG 를 코드까지 관통
```

12 사도 #4 비행기맨 짝패가 아니다 — **Prometheus 는 사도가 아닌 도구**. 5대 무기 (Prometheus / Naesengmoon / Longinus / Harness / 재배맨) 중 하나.

---

## 4. 버전 사다리 (현재)

| Version | Date | Headline |
|---|---|---|
| `sv-prometheus-v6.2.0` (CURRENT, 2026-05-11) | 본 production runtime PoC 시공 + paper-track 8 파일 grounding | KG update pending |
| `sv-prometheus-v6.1.0-2026-05-06` (이전 CURRENT) | Hegel spiral reframe + OODA/Lean Startup 충돌 해소 + Amdahl N default | — |
| `sv-prometheus-v6.0.0-2026-04-29` | Step 6.5 filesystem dispersion + G6.5 gate | — |
| `sv-prometheus-v5.0.0-2026-04-18` | Step 3 prompt 본문 → KG 씨앗 lift | — |
| `sv-prometheus-v4.0.0-2026-05-06` | 부모 Pre-fetch + Finding dedup + Gate Hook 강제 | — |
| `sv-prometheus-progressive-disclosure` | progressive disclosure refactor | — |
| `sv-prometheus-v3.0.0` | TOE-스케일 N=100 + axis × sub-axis 교차표 | — |

# KG: ATOM_Skill_prometheus, sv-prometheus-v6.1.0-2026-05-06, prom-cycle-runtime-prototype-2026-05-11

---

## 5. RFC 진행

| RFC | 상태 | 비고 |
|---|---|---|
| `rfc-prom-filesystem-dispersion-2026-04-29` | IMPLEMENTED (v6.0) | Step 6.5 + G6.5 |
| `rfc-prometheus-v7-explicit-fetch-engine-2026-05-05` | **IMPLEMENTED** (본 PoC 시공 2026-05-11) | `prom_cycle_runtime_prototype/` 로 결정화 |

---

## 6. 한 줄 정리

**Prometheus = 행동 전 지식 확보 + Hegel 자가운동 spiral. SKILL.md 정본 + runtime PoC 짝패.**
