# Prometheus (프로메테우스) — 공학 측 자료집

> **한 줄 정의 (v6.1, 2026-05-05 Hegel reframe):** 단방향 *"지식 선행"* 이 아니라 *지식-행동 자가운동 spiral*. "바로 고치지 마, 먼저 불(지식) 훔쳐와" 는 thesis-antithesis-synthesis 순환의 첫 thesis 일 뿐. 그리스어 *先見者*. 행동 전 지식 확보를 강제하되, 행동이 antithesis 발현 조건.
>
> *공학 측 정전 둥지.* 신화 측은 `METAHUMOTONIC/BHGMAN/prometheus/SOURCES.md` (BHGMAN 비행기맨 prometheus 위상). 본 폴더는 industry / 학문 정전 / production runtime PoC.

---

## 0. 폴더 안에서의 본 파일 위치

| 파일 | 본질 |
|---|---|
| **본 파일 (`SOURCES.md`)** | 1차 소스 + 인용 + 발전 축 + 학문 정전 path |
| `INDEX.md` | 폴더 전체 navigation |
| `ABSTRACT.md` ~ `LEAN_REGRESSION_AUDIT.md` | 논문 골격 8 종 |
| `prom_cycle_runtime_prototype/` | production runtime PoC (Python 3.11+, 53 pytest PASS) |
| `PROM_*_REPORT.md` | /prom cycle 실측 보고서 |
| `lessons/` | cycle 회고 |
| `_findings/raw/` | raw ResearchFinding JSON |

---

## 1. 핵심 주장 (논문 골격용 8 주장)

1. **불 = 지식**. 신화에서 프로메테우스가 인간에게 준 것은 불. 본 방법론에서 그 불은 *행동 이전의 지식*. v6.1 부터는 그 지식이 *행동의 antithesis 와 함께* 자가운동.
2. **나쁜 패턴 vs 좋은 패턴**.
   - 나쁜: 문제 → 즉시 삽질 → 실패 → cascade.
   - 좋은: 문제 → Lesson 즉시 기록 → KG 조회 → 부모 Pre-fetch → N 병렬 subagent → Finding 수렴 → 씨앗 결정화 → 계획 → 실행.
3. **N-파라미터화** (`/prometheus <N> <problem>`). N=3 (간단), N=16 (4×4 axis), N=100 (TOE급). Amdahl ceiling N=100 (cfg slot).
4. **MIC slot**: `IS=ResearchProvider`, `USES=SubagentSeeder` (재배맨/SOP) + `FEEDS_BINDING→ATOM_Skill_longinus` (Longinus 에 KG 공급). v5 부터 SKILL.md prompt 본문이 KG 씨앗 (axis/sub-axis/matrix-template) 으로 lift. *프로메테우스 → 롱기누스 closure*: `FullFindingRecord.sourceKgBindings` ↔ `Longinus.ReferenceSite` isomorphism (Schema `schema-prom-long-isomorphism-2026-05-12`).
5. **9+1 단계 사이클** (v5+ 결정): Step 0~7 + 2 부분 step (2.5, 3.3, 3.5, 4.7, 6.5). JSON 계약 (FullFindingRecord / TerseFindingRecord), 부모 UNWIND 배치 write, W3C PROV provenance.
6. **Gate fail-closed** (v4 부터): 8 Cypher Gate (G0/G1/G3/G3.5/G4/G4.7/G5/G6.5). 권장 아닌 강제 — `GateBlockedError` raise.
7. **Filesystem dispersion** (v6 신설): KG ↔ FS 거울. L1 (docs) / L2 (axis-split MD) / L3 (jsonl) / L4 (KG) / L5 (MinIO) / L6 (UpperWorldRef) / L7 (skill crystallization).
8. **Hegel spiral reframe** (v6.1, 2026-05-05): 단방향 "knowledge first" 의 OODA / Lean Startup 충돌 해소. 자가운동 (Begriff Selbstbewegung) framework. hot-fix latency-critical 시 KG-skip + post-hoc lesson 허용.

---

## 2. 1차 소스 (공학 측)

### 2.1 공학 정본 (canonical)

| 경로 | 내용 |
|---|---|
| `/Users/lagyeongjun/CD/SERVER/.claude/skills/prometheus/SKILL.md` | **정본 v6.1.** 9+1 단계 사이클, MIC binding, 재배맨 SubagentSeeder 결합, 8 Gate, Hegel spiral |
| `/Users/lagyeongjun/CD/SERVER/.claude/skills/prom/SKILL.md` | `/prom` thin alias |
| `/Users/lagyeongjun/CD/SERVER/.claude/skills/prometheus/references/theory.md` | 이론 측 보조 |
| `/Users/lagyeongjun/CD/SERVER/.claude/skills/prometheus/references/phases.md` | 9+1 단계 상세 |
| `/Users/lagyeongjun/CD/SERVER/.claude/skills/prometheus/references/gates.md` | Gate 검증 query |
| `/Users/lagyeongjun/CD/SERVER/.claude/skills/prometheus/references/kg_logging.md` | KG write 패턴 |
| `/Users/lagyeongjun/CD/SERVER/.claude/skills/prometheus/references/error_handling.md` | 오류 대응 |
| `/Users/lagyeongjun/CD/SERVER/.claude/skills/prometheus/references/adversarial.md` | Step 7 Naesengmoon 자동 출격 |
| `/Users/lagyeongjun/CD/SERVER/.claude/skills/prometheus/references/validation.md` | 검증 패턴 |
| `/Users/lagyeongjun/CD/SERVER/.claude/skills/prometheus/references/quick_ref.md` | quick reference |

### 2.2 본 SYMPOSIUM 측 PoC

| 경로 | 내용 |
|---|---|
| `THEORY/PROMETHEUS/prom_cycle_runtime_prototype/` | Python 3.11+ runtime (2026-05-11 시공, 53 pytest PASS) |
| `THEORY/PROMETHEUS/prom_cycle_runtime_prototype/cycle_runner.py` | `PrometheusCycle` orchestrator |
| `THEORY/PROMETHEUS/prom_cycle_runtime_prototype/kg_client.py` | `KgClient` ABC + Mock + Neo4j |
| `THEORY/PROMETHEUS/prom_cycle_runtime_prototype/step*.py` | 각 step thin module |
| `THEORY/PROMETHEUS/prom_cycle_runtime_prototype/tests/` | 53 pytest (per-step + e2e) |

### 2.3 진행 RFC

| RFC | 경로/KG | 상태 |
|---|---|---|
| `rfc-prom-filesystem-dispersion-2026-04-29` | KG | IMPLEMENTED (v6.0) |
| `rfc-prometheus-v7-explicit-fetch-engine-2026-05-05` | KG | IMPLEMENTED (본 PoC 2026-05-11) |

### 2.4 88-lens 검증

| 경로 | 내용 |
|---|---|
| `/Users/lagyeongjun/CD/SERVER/05_DOCS/research/harness-88lens/PROMETHEUS_88LENS_FINAL_REPORT.md` | 88-lens 검증 결과 |
| `/Users/lagyeongjun/CD/SERVER/05_DOCS/research/harness-88lens/PROMETHEUS_88LENS_JUDGMENT_REPORT.md` | 88-lens judgment |

### 2.5 Refactor 측

| 경로 | 내용 |
|---|---|
| `/Users/lagyeongjun/CD/SERVER/07_PROJECTS/prometheus-refactor/` | 리팩터 진행 |
| `/Users/lagyeongjun/CD/SERVER/07_PROJECTS/prometheus-refactor/behavior-specs/spec_n_parser.md` | N-parser spec |
| `/Users/lagyeongjun/CD/SERVER/07_PROJECTS/prometheus-refactor/behavior-specs/spec_taskspec_migration.md` | taskspec 마이그레이션 |

---

## 3. 핵심 인용

### 3.1 SKILL.md 본문

> **프로메테우스(Prometheus) = 그리스어 "먼저 생각하는 자(先見者)".**
> 신에게서 불(지식)을 훔쳐 인간에게 준 타이탄.
> 행동 전에 지식을 확보하는 것이 본 방법론의 핵심.

> **IS slot**: `ResearchProvider`
> **USES slots**: SubagentSeeder (haiku 병렬 리서치 taskspec)
> 미래에 다른 리서치 메커니즘으로 교체 시 `MIC_v1.ResearchProvider.currentConcrete` SET만.

> *프로메테우스는 코카서스 산에 묶여 매일 간을 쪼이는 벌을 받았다.
> 그래도 불을 훔쳐온 것은 후회하지 않았다. 지식의 가치는 그만한 값어치가 있다.*

### 3.2 Hegel 1807 Phänomenologie §125

> *Das Wahre ist das Ganze. Das Ganze aber ist nur das durch seine Entwicklung sich vollendende Wesen.*

(Miller tr. p.79) — *진리는 전체다. 전체란 다름 아닌 그 발전을 통해 자기를 완성하는 본질.*

v6.1 reframe 의 정확한 grounding. 단방향 "지식 선행" interpretation 은 자가운동 *partial view*.

### 3.3 Amdahl 1967 AFIPS

> $S(N) = 1 / ((1-p) + p/N)$

speedup ceiling 의 정량 도출. N=100 가 random ceiling 아닌 *Amdahl ceiling* 임 — `cfg.prometheus_n_max = 100` 의 학문적 근거.

### 3.4 Lakatos 1978

> A research programme is progressive if its theoretical growth anticipates its empirical growth.

v4 → v5 → v6 → v6.1 → v7 RFC 시리즈 모두 *novel content* 누적 → progressive problemshift (`LEAN_REGRESSION_AUDIT §4` T4).

---

## 4. 학문 정전 정확 인용 (4+1 axis)

> 상세 grounding 은 `AXIS_DEEP_GROUNDING.md`. 본 절은 인용 path 만.

### 4.1 A. 정보이론

- **Solomonoff 1964** *Information and Control* 7(1):1-22 — universal prior, induction.
- **Kolmogorov 1965** *Problems Inform. Transmission* 1(1):1-7 — $K(x) = \min\{|p| : U(p) = x\}$.
- **Chaitin 1969** *JACM* 16:145 — algorithmic information.
- **Rissanen 1978** *Automatica* 14:465 — MDL principle.
- **Grünwald 2007** *The Minimum Description Length Principle* MIT Press — two-part code, ch.5.
- **Tishby, Pereira, Bialek 1999** *Allerton Conf.* — Information Bottleneck.
- **Friston 2010** *Nat Rev Neurosci* 11:127 — Free Energy Principle.
- **Parr, Pezzulo, Friston 2022** *Active Inference* MIT Press — Expected Free Energy, exploration vs exploitation.

### 4.2 B. Search Algorithm

- **Auer, Cesa-Bianchi, Fischer 2002** *Machine Learning* 47:235 — UCB1 regret bound.
- **Coulom 2006** — MCTS.
- **Silver et al. 2016** *Nature* 529:484 — AlphaGo PUCT.
- **Knuth-Moore 1975** *AI* 6:293 — α-β pruning bound.

### 4.3 C. Pipeline

- **Petri 1962** PhD Diss. Univ. Bonn — Petri net firing rule.
- **Reisig 2013** *Understanding Petri Nets* Springer.
- **Lakatos 1976** *Proofs and Refutations* Cambridge UP.
- **Lakatos 1978** *Methodology of Scientific Research Programmes* Cambridge UP — hard core / protective belt.
- **Callon 1986** — OPP (Obligatory Passage Point), Actor-Network Theory.
- **Latour 1987** *Science in Action* Harvard UP.

### 4.4 D. Amdahl

- **Amdahl 1967** *AFIPS* 30:483 — original.
- **Gustafson 1988** *CACM* 31(5):532 — re-evaluation.
- **Hill, Marty 2008** *IEEE Computer* 41(7):33 — multicore era.

### 4.5 E. (+1) Hegel + Process Philosophy

- **Hegel 1807** *Phänomenologie des Geistes* §125 (Miller p.79) — Begriff Selbstbewegung.
- **Hegel 1812** *Wissenschaft der Logik* — Aufhebung.
- **Whitehead 1929** *Process and Reality* — concrescence Pt II Ch.X.
- **Boyd 1976** *Patterns of Conflict* — OODA loop.
- **Ries 2011** *The Lean Startup* — Build-Measure-Learn.

---

## 5. Industry 비교 (10 방법론)

> 상세 표는 `COMPARISON_METHODOLOGIES.md` 1.1~1.5 + § 5 OODA/Lean Startup.

| 측면 | Prometheus | RAG | Self-RAG | AutoGPT | ReAct | Toolformer | DSPy | Reflexion | Voyager | OODA | Lean Startup |
|---|---|---|---|---|---|---|---|---|---|---|---|
| KG-first | ✅ | △ | △ | ❌ | ❌ | ❌ | △ | △ | △ | — | △ |
| Parallel N=1~100 | ✅ | ❌ | △ | ❌ | ❌ | ❌ | △ | ❌ | ❌ | ❌ | ❌ |
| Gate fail-closed | ✅ | ❌ | △ | ❌ | ❌ | ✅ | △ | △ | ✅ | ❌ | △ |
| Idempotent merge | ✅ | △ | ❌ | ❌ | ❌ | △ | △ | ❌ | △ | — | ❌ |
| Hegel spiral | ✅ | ❌ | ❌ | ❌ | △ | ❌ | ❌ | △ | ❌ | △ | △ |
| **Total** | **5/5** | 0.5 | 1.0 | 0 | 0 | 1.0 | 1.0 | 0.5 | 1.5 | — | 0.5 |

Prometheus 만이 5축 모두 hard-positive — *novel methodology*.

---

## 6. 논문 작성 시 발전 가능 축 (8)

- **(a) 신화의 윤리적 부담**: 프로메테우스는 불을 훔친 죄로 매일 간이 뜯기는 형벌. 방법론은 그 부담을 어떻게 처리하는가 — 부모 Claude 의 context budget 부담.
- **(b) Pre-fetch 정당화**: 왜 즉시 행동이 나쁜가 — 정보비대칭이 행동의 비용을 비대칭하게 키움 (Akerlof 1970 lemons market).
- **(c) N 병렬 vs 깊이**: haiku 100 병렬 subagent 의 axis × sub-axis 매트릭스 — 어떤 문제에서 어떤 N 이 옳은가 (Amdahl ceiling 도출).
- **(d) Finding 중복 탐지**: v4 부모 하계 Pre-fetch + Finding dedup — KG 의 의미적 중복 측정 (sha256 결정성 vs embedding 의미 dedup).
- **(e) 신화 ↔ 12사도**: 프로메테우스는 12사도가 아니다. 도구다. 사도(존재)와 도구(방법) 의 구분이 metahumotonic 윤리학에 갖는 의미.
- **(f) Hegel reframe (v6.1)**: 단방향 "지식 선행" 의 OODA/Lean Startup 충돌. 자가운동 framework 의 ad hoc rescue 아닌 *상위 framework* 격상.
- **(g) Filesystem dispersion (v6)**: KG-first 의 *외부 가시성* 측면. KG 152 nodes 풍부 ↔ filesystem 1 .md lean 불일치 해소.
- **(h) Lakatos hard core/protective belt 분리**: 5 hard core + N protective belt → progressive vs degenerating 판정 기준.

---

## 7. 신화 측 짝패 cross-ref (BHGMAN)

> 본 자료집은 *공학 측* 정전 둥지. 신화 측 자료집은 `METAHUMOTONIC/BHGMAN/prometheus/`. 양쪽 분리 정전 (CLAUDE.md spec).

| 파일 | 내용 |
|---|---|
| `METAHUMOTONIC/BHGMAN/prometheus/SOURCES.md` | 비행기맨 prometheus 위상 신화 측 자료집 |
| 본 파일 | 공학 측 자료집 (industry / 학문 정전) |

### 7.1 BHGMAN 측 형식적 grounding (2026-05-09 결정화)

`BHGMAN/prometheus/SOURCES.md` 의 *## 형식적 grounding — 4 axis 학문 정전 정확 정의* 섹션 (KG: `formal-grounding-prometheus-bhgman-2026-05-09`):

- **A. 정보이론**: Kolmogorov / Solomonoff / MDL / IB / Friston FEP / EFE
- **B. 검색 알고리즘**: UCB1 / MCTS / AlphaGo PUCT / α-β pruning
- **C. Pipeline**: Petri net / Lakatos
- **D. Amdahl**: 1967 speedup formula
- **+ Hegel Aufhebung**: §125 Phänomenologie 정확 형식

→ 신화 측 정전 grounding ↔ 공학 측 industry 정전 의 *짝패*. 정전 분리 + 결정화 결과 동기.

### 7.2 사용자 자기 신앙시 (1차)

| 경로 | 내용 |
|---|---|
| `MIND/metahumotonic/` (12사도_목록_업데이트.md 외) | 사용자 자칭 / 신앙시 |

→ 신화 측 1차 소스. AI 해석본은 `MIND/AI_MADE/`, AI 위서는 `MIND/metahumotonic_종교화/` 로 분리 (CLAUDE.md spec).

---

## 8. KG 정전 노드 (현재)

| 노드 | 의미 |
|---|---|
| `ATOM_Skill_prometheus` | skill anchor |
| `sv-prometheus-v6.1.0-2026-05-06` | 현재 정전 버전 (v6.2.0 격상 pending 2026-05-11) |
| `sv-prometheus-v6.2.0-2026-05-11` | 신버전 (본 SOURCES 보강 + PoC 시공 반영 PENDING) |
| `prometheus-hardening-master-plan-2026-05-06` | hardening master plan — COMPLETE_FINAL_PLATEAU (→ GROUNDED PENDING) |
| `rfc-prometheus-v7-explicit-fetch-engine-2026-05-05` | v7 RFC — IMPLEMENTED (본 PoC 2026-05-11) |
| `rfc-prom-filesystem-dispersion-2026-04-29` | v6 RFC — IMPLEMENTED |
| `prometheus-grounding-2026-05-05` | 형식 grounding 결정화 |
| `lesson-prometheus-hegel-spiral-reframe-2026-05-05` | v6.1 reframe lesson |
| `amdahl-analysis-prometheus-N-default-2026-05-05` | N ceiling 도출 |
| `formal-grounding-prometheus-bhgman-2026-05-09` | 신화 측 형식 grounding |
| `prom-cycle-runtime-prototype-2026-05-11` | 본 PoC anchor (PENDING write) |
| `MIC_v1` | 5 무기 통합 계약 |
| `MethodologyConfig_default_v26` | 모든 magic number resolve target |
| `FilesystemDispersionPolicy` (slot) | Step 6.5 정책 slot |
| `PromV5_FilesystemDispersion_v1` | currentConcrete policy |

# KG: ATOM_Skill_prometheus, sv-prometheus-v6.2.0-2026-05-11, prometheus-grounding-2026-05-05
