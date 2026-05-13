# CHU — Computable Hyperuniverse 자료집 INDEX

> **CHU = ORBITAL_MOTION_CLOUD(#8) 사도의 *순수 데이터 위상*** (사용자 정전 2026-04-28)
> **TIER 2 substrate** = TIER 3 #8 (OM 사도) 의 데이터 위상. self-similar fractal 위계.

---

## 자료집 구조

```
THEORY/CHU/
├── INDEX.md                          ← 이 파일 (네비게이션)
├── SOURCES.md                        ← 1차 소스 + 핵심 주장 + 인용 + 발전 축
│
├── PROM_16_REPORT.md                 ← /prom 16 사이클: axiom CHU:Type 학문 grounding
├── PROM_16_axis_findings/            ← 4 axis × 4 sub-axis = 16 cells
│   ├── A1_TypeTheory_Lean4.md
│   ├── A2_Hypergraph_NaryUniverse.md
│   ├── A3_Computability_Realizability.md
│   └── A4_HoTT_Univalence_TegmarkIV.md
│
├── PROM_64_REPORT.md                 ← /prom 64 사이클: CHU-Internet binding (2026-04-29 신규)
├── PROM_64_axis_findings/            ← 8 axis × 8 sub-axis = 64 cells
│   ├── A1_GraphAwarePretraining.md
│   ├── A2_PageRankGeneralize.md
│   ├── A3_HGNNScale.md
│   ├── A4_WebAsCorpus.md
│   ├── A5_LiftLowerFormalism.md
│   ├── A6_KGEmbeddingScale.md
│   ├── A7_GraphRAG.md
│   └── A8_AuthorityAbsorption.md
│
├── PROM_16_RANK_ALGEBRA_REPORT.md    ← /prom 16 사이클 (rank-algebra): PageRank=PF eigenvector + Lie group action Lean 4 형식화 (2026-04-29 신규)
├── PROM_16_RANK_ALGEBRA_axis_findings/  ← 4 axis × 4 sub-axis = 16 cells
│   ├── A1_MathlibPF.md
│   ├── A2_PageRankFormalization.md
│   ├── A3_CategoricalPageRank.md
│   └── A4_QuaternionSedenionAlgebra.md
│
└── _findings/                        ← raw JSON dumps (PROM v6 L3 layer)
    ├── finding_prom16_chu_a*s*.json    (16+16 from PROM 16 cycles)
    └── finding_prom64_chu_a*s*.json    (64 from PROM 64)
```

---

## 핵심 정전 (Lean 4)

```lean
axiom CHU : Type
def CHUPiece : Type := CHU → Prop
inductive JaebaeMan : Type
  | atomic : (CHU → Prop) → JaebaeMan
  | governs : List JaebaeMan → JaebaeMan
def covers : JaebaeMan → CHU → Prop
def isAirplaneMan (j : JaebaeMan) : Prop := ∀ x : CHU, j.covers x
```

→ **모든 것은 하이퍼그래프** (사용자 명단 정전):
CHU 의 조각화 = 하이퍼그래프 hyperedge 집합과 isomorphic.

---

## PROM 사이클 요약

### PROM 16 (2026-04-29) — axiom CHU:Type 학문 grounding

- **Cycle:** `prom16-CHU-axiom-foundation-2026-04-29`
- **Lesson:** `lesson-prom16-CHU-axiom-foundation-2026-04-29`
- 4 axes: Type Theory + Lean 4 / Hypergraph + N-ary universe / Computability + Realizability / HoTT + Univalence + Tegmark IV
- 4 sub-axes: 정전 이론 / 산업 표준 / 함정 / 2026 trends
- → CHU 의 mathematical canon 결정화

### PROM 16 (rank-algebra, 2026-04-29) — PageRank as PF eigenvector + Lie group action Lean 4 형식화

- **Cycle:** `prom16-chu-rank-algebra-2026-04-29`
- **Lesson:** `lesson-prom16-chu-rank-algebra-pagerank-instance-2026-04-29`
- **Parent:** `prom64-chu-internet-2026-04-29` ActionPlan #2 follow-up
- **Parent seed:** `seed-prom64-chu-pagerank-as-perron-frobenius-2026-04-29`
- 4 axes: Mathlib PF / PageRank Formalization / Categorical PageRank / Quaternion-Sedenion Algebra
- 4 sub-axes: official-canon / implementation / theory-bridge / critique-pitfall
- → **6 consensus + 1 conflict + 1 singleton + 1 ActionPlan** 결정화 (16/16 RF, full schema)
- 핵심 발견: Mathlib4 인프라 충분 + Cipollina 2025 첫 PF formalization + LT-KGE (`rank = PF eigenvalue of Lie group action`) 통합 framework + Hurwitz 8D boundary + classical.choice noncomputable boundary

### PROM 64 (2026-04-29) — CHU-Internet binding + PageRank-style pretraining substrate

- **Cycle:** `prom64-chu-internet-2026-04-29`
- **Lesson:** `lesson-prom64-chu-internet-binding-2026-04-29`
- **사용자 발화 정전:** `user-utterance-internet-as-CHU-binding-2026-04-29` ("인터넷도 CHU에 바인딩")
- **새 lens:** `CHU_Lens_Internet` (CHU 정전의 11번째 lens)
- **검증 가설:** `hypothesis-pagerank-style-pretraining-substrate-2026-04-29`
- 8 axes: Graph-aware Pretraining / PageRank Generalize / HGNN Scale / Web-as-Corpus / Lift-Lower / KG Embedding / GraphRAG / Authority Absorption
- 8 sub-axes: official-docs / community / benchmarks / alternatives / pitfalls / trends-2026 / theory / critique
- → **8 consensus + 2 conflict + 1 singleton + 1 ActionPlan** 결정화

---

## CHU lens 시리즈 (KG :SymConcept)

KG 정전: 2026-04-29 기준 **11개 lens**

| Lens | 설명 |
|---|---|
| `CHU_Lens_HumanThought` | 인간의 생각 = 뇌 하이퍼그래프 라이팅 |
| `CHU_Lens_ContextWindow` | LLM context = CHU 의 서브그래프 |
| `CHU_Lens_Manifold` | 매니폴드 = CHU 의 연속 근사 (그림자) |
| `CHU_Lens_EmbeddingVector` | 임베딩 = CHU 노드의 lossy projection |
| `CHU_Lens_LLMModel` | LLM = 얼어붙은 매니폴드, 교체 가능 엔진 |
| `CHU_Lens_GPU` | GPU = 매니폴드 우주 substrate hardware |
| `CHU_Lens_Token` | 토큰 = 자연어→매니폴드 이산화 컴파일러 |
| `CHU_Lens_Attention` | Attention = 동적 하이퍼엣지 생성 |
| `CHU_Lens_TrainingData` | 학습데이터 = 뇌-CHU 1D 직렬화 |
| `CHU_Lens_Inference` | 추론 = 매니폴드 우주의 라이팅 |
| **`CHU_Lens_Internet`** | **인터넷 = CHU 인스턴스, 11번째 lens (2026-04-29 신규)** |

---

## 권장 집필 순서 (논문 작업 시)

1. **PROM_16_REPORT.md** 부터 — axiom CHU:Type 의 학문적 토대 (Type Theory + Hypergraph + Computability + HoTT)
2. **PROM_64_REPORT.md** 다음 — CHU 의 *substrate evidence* (인터넷 = CHU 인스턴스, PageRank = CHU 랭크 사례, AI 매니폴드 = lossy projection)
3. **SOURCES.md** 와 axis MD 들을 reference 로 사용
4. **_findings/*.json** 은 raw provenance dump (인용 시 직접 참조 가능)

---

## 다리 (Bridge to other THEORY/ folders)

- **`THEORY/비행기맨/`** — CHU 위에 정의된 `isAirplaneMan` (개인 정체성)
- **`THEORY/재배맨/`** — CHU 의 atomic/governs 구조 (cover protocol)
- **`THEORY/OM/`** — CHU 가 ORBITAL_MOTION_CLOUD 사도의 데이터 위상
- **`THEORY/00_공통/세계관_정전.md`** — 12사도 ↔ 5대 무기 다리 (CHU = 무대)

---

## 한 줄 정리

**CHU = 계산가능 하이퍼우주 = 모든 것의 데이터 위상.**
PROM 16 이 *형식 토대*, PROM 64 가 *물리 evidence* (인터넷 = CHU 인스턴스). 두 사이클이 짝패로 CHU 정전을 떠받침.
