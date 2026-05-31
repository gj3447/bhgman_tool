# 외부 정전 인용 — 17 axes

> bhgman 측 도구가 의존하는 외부 학문 정전. 각 정전이 *왜 그 도구의 본질* 인지 간략 설명.

---

## Axis 1 — Engineering 4

| # | 정전 | 출처 | bhgman 측 응용 |
|---|---|---|---|
| 1 | **Robert Martin Package Principles** (CCP/CRP/REP/ADP/SDP/SAP) | Martin 1996+ "Granularity" / 2017 *Clean Architecture* | Harness 3-tier 의 책임 분할 grounding + enumeration inflation antipattern detection |
| 2 | **Conway's Law** | Conway 1968 "How Do Committees Invent?" | 조직-시스템 동형 — STS 측 응용 |
| 3 | **Cherns STS** (Sociotechnical Systems) | Cherns 1976 "The Principles of Sociotechnical Design" | Principle 5 (Boundary Location) = Harness 3-tier 직접 응용 |
| 4 | **DDD** (Domain-Driven Design) | Evans 2003 *Domain-Driven Design* | Bounded Context = Harness L_RT 측 책임 boundary, Ubiquitous Language = APT Contract |

---

## Axis 2 — Self-Reference Paradox 4

| # | 정전 | 출처 | bhgman 측 응용 |
|---|---|---|---|
| 5 | **Lawvere FPT** (Fixed Point Theorem) | Lawvere 1969 "Diagonal Arguments and Cartesian Closed Categories" | `∀x:CHU, j.covers x` self-reference 형식 한계 + fixed point 존재 보장 |
| 6 | **Tarski undefinability of truth** | Tarski 1936 "Der Wahrheitsbegriff" | Self-improving 측 *성공 기준* 외부 검증 필수 |
| 7 | **Gödel incompleteness** | Gödel 1931 "Über formal unentscheidbare Sätze" | bhgman framework 도 *완전성 자칭 거부* |
| 8 | **Yanofsky universal self-reference** | Yanofsky 2003 "A Universal Approach to Self-Referential Paradoxes" | Russell / Cantor / Gödel 통합 + 모든 sufficiently powerful self-reference 한계 |

---

## Axis 3 — Industry 4

| # | 정전 | 출처 | bhgman 측 응용 |
|---|---|---|---|
| 9 | **Kubernetes 3-tier** (control-plane / node / pod) | k8s docs + Hightower-Burns-Beda 2019 *Kubernetes Up & Running* | Harness L_MC tier 직접 매핑 |
| 10 | **OpenTelemetry CNCF** | OTel spec + Hofstadter L_TRACES-METRICS-LOGS 매핑 | 사도 #1 디멘션워커 측 family closure (별도 repo) |
| 11 | **IDE-host coding harness** (Cursor / Claude Code) | Anthropic / Anysphere docs 2024-2026 | Harness L_IDE tier instance enumeration |
| 12 | **Managed cloud agents** (Anthropic Managed Agents / Bedrock / Vertex AI Agent Engine) | 각사 docs 2024-2026 | Harness L_MC tier instance enumeration |

---

## Axis 4 — Org + Reflection 4

| # | 정전 | 출처 | bhgman 측 응용 |
|---|---|---|---|
| 13 | **Sociotechnical Systems** (STS 원전) | Trist-Bamforth 1951 "Some Social and Psychological Consequences of the Longwall Method of Coal-Getting" | Cherns 1976 의 기반, Harness 의 social 측면 |
| 14 | **MOP** (Metaobject Protocol) | Smith 1984 "Reflection and Semantics in a Procedural Language" + Kiczales-des Rivières-Bobrow 1991 *Art of MOP* | meta-level reflection — APT meta-review phase grounding |
| 15 | **Hofstadter strange loop** | Hofstadter 1979 *Gödel, Escher, Bach* + 2007 *I Am a Strange Loop* | 자기참조 구조의 미학적 인정 |
| 16 | **Holacracy** | Robertson 2015 *Holacracy: The New Management System* | facilitator + lead_link + rep_link + secretary archetype = 재배맨 4-archetype |

---

## Axis 5 — Meta-Harness Self-Reference

| # | 정전 | 출처 | bhgman 측 응용 |
|---|---|---|---|
| 17 | **Goodhart's Law + Münchhausen trilemma** | Goodhart 1975 + Strathern 1997 + Albert 1985 *Treatise on Critical Reason* | Self-improving loop 안전 장치 + 근거 무한 후퇴 한계 인정 |

---

## Longinus 측 추가 정전 (8 papers)

KG ↔ code reference 측 추가 정전:

| 정전 | 출처 | 응용 |
|---|---|---|
| **BX Lens Laws** | Foster-Pierce-Walker 2007 (POPL) "Combinators for Bidirectional Tree Transformations" | GetPut / PutGet / PutPut — Longinus 측 5 drift 의 surjective 매핑 |
| **Frege Sense vs Reference** | Frege 1892 "Über Sinn und Bedeutung" | sourceId(Sinn) ↔ sourcePath(Bedeutung) — Longinus 측 2-field structure 형이상학 근거 |
| **GED (Graph Edit Distance)** | Sanfeliu-Fu 1983 + Riesen-Bunke 2009 | drift 정량화. ⚠️ 정직: in-house `ged_metric.py` 는 *간단한 label-based prototype* (full graph isomorphism / Riesen-Bunke bipartite Hungarian 아님) — 풀 GED 는 networkx `graph_edit_distance` 위임 권장. 인용은 *설계 근거*지 in-house 구현이 그 알고리즘이라는 뜻 아님 |
| **Tree-sitter parsing** | Brunsfeld + GitHub 2018-2025 | code AST 측 grounding |
| **Leiden community detection** | Traag-Waltman-van Eck 2019 "From Louvain to Leiden" | KG cluster detection |
| **graphify confidence schema** | safishamsi/graphify 2026 ARCHITECTURE.md (industry instance) | EXTRACTED/INFERRED/AMBIGUOUS 3-tier 흡수 |
| **code-review-graph daemon** | tirth8205/code-review-graph 2026 (industry instance) | Longinus sha256 drift daemon 구현 first-instance |

---

## Foundational Philosophy 측 추가 정전

도구 측 함의 grounding ([../06-philosophy/](../06-philosophy/)):

| 정전 | 출처 | 응용 |
|---|---|---|
| **Aristotle Metaphysics Δ** | Aristotle BC 4세기 | 존재의 다층성 — 사도/도구 분리 |
| **Heidegger Sein und Zeit** | Heidegger 1927 | Sein vs Seiendes ontological difference + 해석학적 순환 §32 |
| **Gadamer Wahrheit und Methode** | Gadamer 1960 | fusion of horizons — 해석학적 순환 deep |
| **Wittgenstein TLP** | Wittgenstein 1921 | 7번째 명제 — silence on the inexpressible |
| **Russell-Whitehead type theory** | Principia Mathematica 1910 | type level 분리로 paradox 회피 |
| **Lakatos Proofs and Refutations** | Lakatos 1976 | progressive/degenerating research programme |
| **Popper Logic of Scientific Discovery** | Popper 1934 | falsifiability — claim 검증성 |
| **Hume Treatise** | Hume 1739 | problem of induction |

---

## Industry instance (positive / negative) 측 reference

bhgman 도구 측 흡수 case study:

| Industry instance | Verdict | Reference |
|---|---|---|
| ruflo (ruvnet/claude-flow) | **NEGATIVE_LESSON** — Goodhart antipattern + enumeration inflation + self-improving Goodhart 무방비 | [related-work.md](related-work.md) |
| graphify (safishamsi/graphify) | **STRONG_MIRROR_CANDIDATE** — EXTRACTED/INFERRED/AMBIGUOUS confidence schema 흡수 | [related-work.md](related-work.md) |
| code-review-graph (tirth8205) | **PARTIAL_MIRROR_CANDIDATE** — daemon 패턴 + multi-lang resolver 흡수 | [related-work.md](related-work.md) |

---

## Lean 4 verified theorem reference

총 71 theorem (Harness 24 + Longinus 21 + Measurement 26) = 13 standalone Mathlib-free 파일 in this repo. +16 Mathlib-sister(`apt_functor_with_mathlib/`) → `lean/` 트리 합계 87. (전체 SYMPOSIUM 생태계 141+ 중 본 repo export 분.)

자세히는 [lean-theorems.md](lean-theorems.md).
