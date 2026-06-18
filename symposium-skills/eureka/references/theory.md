# eureka — Theory

> Lazy-load reference. Parent: [`../SKILL.md`](../SKILL.md).
> KG: `eureka-canonical-2026-05-26` (`:LegionCommander:CanonicalName`), `consensus-eureka-academic-grounding-2026-05-26` (16 RF).
> 유레카 = 비행기맨 #4 군단장. 동사 = **발견·창조** (concrete→abstract↑). 하데스(abstract→concrete↓)의 dual.
> # src: THEORY/유레카/PROM_16_EUREKA_ACADEMIC_REPORT.md, KG eureka-canonical-2026-05-26

이 도구는 *경향·반복 패턴을 하나의 새 개념(KG 노드 / 코드 추상클래스·공유함수)으로 묶어 창조*한다.
아래 정전들이 그 다섯 축(논리 → 과학철학 → 인지 → 수학 → 코드)을 각각 grounding한다. 한 줄:
**가추(논리) → 발견의 맥락(과학철학) → 통찰·개념형성(인지) → colimit/ILP/FCA(수학) → anti-unification·리팩터링(코드).**
# src: THEORY/유레카/PROM_16_EUREKA_ACADEMIC_REPORT.md §"유레카 학문축 한 줄"

---

## 1. 논리 심장 — abduction + colligation

| 정전 | 한 줄 | 왜 유레카를 grounding |
|------|-------|----------------------|
| **Peirce, abduction (가추법)** | 관찰에서 *새 개념을 도입하는 유일한* 추론 (연역=적용, 귀납=일반화와 환원불가) | 유레카의 논리적 핵심 — "새 개념을 만든다"는 동사 자체가 가추 |
| **Whewell, colligation / consilience** | 흩어진 사실에 새 conception을 *superinduce*해 묶음; 다른 클래스 사실까지 묶이면(consilience) 그 개념이 참이라는 검증 | "반복 패턴을 하나의 개념으로 묶기"의 역사적 정전 + held-out 검증 원리 |
| Carnap 귀납논리(확률), Mill's methods(대조) | 보강 — 귀납의 확률적/대조적 형식화 | 가추 위의 정량 보강 |

# src: KG finding_eu_A1_abduction_canon (cite: plato.stanford.edu/entries/abduction/peirce.html), finding_eu_A2_whewell_mapping (cite: plato.stanford.edu/entries/whewell/)
> consilience는 엔진의 `fidelity_gate.py`로 실현된다 — 추상이 *형성에 안 쓴* witness 관계로도 cohere하면 PASS (§6 참조).

---

## 2. 과학철학 경계 — 발견 vs 정당화

**Reichenbach (1938) — 발견의 맥락 (context of discovery) / 정당화의 맥락 (context of justification)** + Popper 반증.

- **유레카 = 발견의 맥락** (가설·개념 생성). **나생문 = 정당화의 맥락** (검증).
- 이 분리가 엔진의 **아키텍처 계약**으로 박혀 있다: 유레카는 *PROPOSE만*, **auto-commit 금지**.
  실제 `config.py never_auto_commit=true`, `anti_unify.propose_template` note: "PROPOSE only … auto-commit 금지".
- # src: KG finding_eu_A4_discovery_vs_justification (cite: plato.stanford.edu/entries/scientific-discovery/), eureka-canonical-2026-05-26, engine/eureka/anti_unify.py:98, THEORY/유레카/EUREKA_ENGINE_DESIGN.md §"엔진 범위"

---

## 3. 인지과학 — 개념형성 + 통찰

| 정전 | 한 줄 | 유레카 매핑 |
|------|-------|------------|
| Rosch 프로토타입 / exemplar / theory-theory (병렬), Bruner attainment, cognitive economy | 개념형성의 세 경쟁 이론 + 인지 경제성 | "어떻게 개념이 형성되는가"의 인지 정전 |
| **통찰(Aha)**: 게슈탈트 재구조화(Köhler/Wertheimer) + Metcalfe warmth 불연속 + Kounios-Beeman 우반구 무의식 선처리→의식 'Aha' | 통찰은 점진 아닌 *재구조화*; warmth가 불연속 점프 | 유레카 결정화 순간(아르키메데스 "유레카!") 그 자체 |
| Gentner 구조사상 (structure-mapping) | 2단계: 매핑(기존 관계 정렬) + **schema-induction**(공통 골격을 새 개념으로 추출) | 경계: schema-induction=유레카 / 매핑=롱기누스 |

# src: KG finding_eu_B1_concept_formation_canon (cite: en.wikipedia.org/wiki/Prototype_theory), finding_eu_B2_insight_mapping (cite: nature.com/articles/s44159-023-00257-x), finding_eu_B4_analogy_boundary (cite: Gentner s15516709cog0702_3)

---

## 4. 수학 — 수렴정리 (최강 grounding)

**ILP predicate invention ⇔ FCA 개념격자 ⇔ 범주론 colimit (왼쪽수반 F⊣Δ)** — "같은 구성의 다른 언어".

- 개념창조의 수학 = 인스턴스들의 **colimit** (가장 일반적 추상).
- 단 **colimit ⊊ eureka**: colimit은 Eureka Phase2(합성) sub-step. Phase1(novelty/귀납) + Phase2(colimit/concrescence) composite. (사용자 verdict 2026-05-29~30)
- 알고리즘 실현: **FCA** (Ganter–Wille 1999 fundamental theorem, extent/intent Galois closure)가 엔진의 KG 백엔드.
- # src: KG finding_eu_C1_ilp_fca_cat_canon (cite: arxiv.org/abs/2102.10556), eureka-canonical-2026-05-26 props colimit_subsumption_2026_05_29 / composite_functor_2026_05_30 (left adjoint to Hades + colimit-creating, Whitehead concrescence), engine/eureka/induction_operators/fca.py:1-9

추가 정전 (library learning): **DreamCoder** (wake-sleep 라이브러리학습) + Lenat **AM/EURISKO** (수학개념 자동발견; EURISKO ≈ Eureka) + LILO. compression-as-abstraction.
# src: KG finding_eu_C2_library_learning_mapping (cite: arxiv.org/abs/2006.08381)

---

## 5. 코드 기제 — anti-unification + 리팩터링

| 정전 | 한 줄 | 유레카 매핑 |
|------|-------|------------|
| **Plotkin (1970) anti-unification / 최소일반화 (LGG)** | 불일치 하위항을 fresh 변수로 치환 → N 조각의 *가장 구체적 공통 추상* 계산 | 유레카 **코드 추상의 형식 연산 그 자체** — `anti_unify.py`로 직접 구현 |
| Fowler/Opdyke 리팩터링 (Extract Method/Superclass/Template Method) + DRY (Hunt&Thomas) + GoF | 반복 = 빠진 추상 신호; 반복 해법→명명된 추상 | 코드 측 유레카의 SE 정전. 단 *적용(Extract)* = 하데스 (materialize), 유레카는 템플릿 제안까지 |

# src: KG finding_eu_D2_antiunification_mapping (cite: ijcai.org/proceedings/2023/0736.pdf — babble e-graph+AU POPL'23), finding_eu_D1_refactoring_canon (cite: refactoring.com/catalog/), engine/eureka/anti_unify.py:1-12

엔진 매핑 (이론 = 알고리즘):
```
Plotkin LGG     → anti_unify.py        (token-seq least general generalization, hole=·N)
FCA Galois      → induction_operators/fca.py   (extent/intent closure, stability)
Ganter-Wille    → formal_context_builder.py    (KG → formal context, 3 pre-filter)
AMIE 3.5.1      → induction_operators/amie3.py  (Lajus-Galárraga-Suchanek 2020, PCA conf)
Leiden          → induction_operators/leiden_true.py (Traag-Waltman-vanEck 2019)
```
# src: engine/eureka/{anti_unify,formal_context_builder}.py, induction_operators/{fca,amie3,leiden_true}.py 모듈 docstring

---

## 6. 게이트 정전 (함정 → 방어)

유레카는 *없는 패턴을 발명*(apophenia)하고 *성급한 추상*(Sandi Metz: "잘못된 추상이 중복보다 비싸다")으로 무너진다. 정전이 곧 게이트다.

| 함정 정전 | 한 줄 | 엔진 게이트 |
|-----------|-------|------------|
| **Hume 귀납 정당화 불가 + underdetermination** | 유한 데이터→무한 설명, 귀납은 형식 정당화 없음 | auto-commit 금지 (Reichenbach 분리) |
| **apophenia / pareidolia / clustering illusion** | 무작위에서 거짓 패턴 발명 | Rule of Three (≥3 인스턴스), stability index |
| **Sandi Metz, premature abstraction** | sunk-cost + 조건문 지옥 + 의존자 전체 오염 | `rule_of_three_min=3`, reversible materialize |
| **MDL-optimal ≠ 쓸모있는 추상 (Goodhart)** | 순수 MDL은 "low-entropy인데 기능적 필수"를 죽임 | `quality_gate.GOODHART_CAP=0.95` (>0.95=artifact reject) + semantic-fidelity gate |
| **Whewell consilience** | 안 본 인스턴스/관계로도 cohere해야 진짜 | `fidelity_gate.py` — witness 관계(facet 제외) top_share ≥0.30, ensemble k≥2 (Goodhart 회피 = 단일 metric 금지) |

품질 임계 정전 (`quality_gate.py`): silhouette s̄≥0.50 (Rousseeuw 1987) / modularity Q≥0.30 (Newman 2006 PNAS) / FCA stability σ≥0.50 (Roth-Obiedkov-Kourie 2008) / AMI≥0.50 (Vinh-Epps-Bailey 2010).
# src: KG finding_eu_A3_induction_pitfalls (cite: plato.stanford.edu/entries/abduction/), finding_eu_B3_bias_pitfalls (cite: en.wikipedia.org/wiki/Apophenia), finding_eu_C3_overfit_pitfalls (cite: arxiv.org/abs/2304.05366), finding_eu_D3_overabstraction_pitfalls (cite: sandimetz.com/blog/2016/1/20/the-wrong-abstraction), engine/eureka/{quality_gate,fidelity_gate}.py

---

## 7. 군단장 경계 (3 직교 분리)

| 경계 | 분리 | grounding |
|------|------|-----------|
| 유레카 vs **나생문** | 발견 ↔ 정당화 | Reichenbach (finding_eu_A4) |
| 유레카 vs **오캄** | generative 압축(개념↑, one-to-many) ↔ subtractive 압축(중복↓, many-to-one). 살아있는 반복 ↔ 죽은 stale | MDL/Kolmogorov 같은 척도 *반대 방향* (finding_eu_C4, cite arxiv 1005.2364). 판정 신호: git dormancy / test coverage / call-graph in-degree (finding_eu_D4) |
| 유레카 vs **롱기누스** | schema 추출(새 개념 reify) ↔ 매핑/연결(기존 정렬) | Gentner 구조사상 2단계 (finding_eu_B4). colimit=유레카 / morphism(edge)=롱기누스 |
| 유레카 vs **하데스** | 후보 생산(구체→추상↑) ↔ 실현(추상→구체↓, materialize) | dual functor; 유레카는 stage 0-5에서 멈춤(전부 reversible) |

# src: THEORY/유레카/PROM_16_EUREKA_ACADEMIC_REPORT.md §"경계 재확인", eureka-canonical-2026-05-26 props yinyang / hades_dual_boundary, engine/eureka/oracle_lens.py (JUSTIFY=나생문 oracle+판단 2 lens-class)

---

## 8. References

- `../SKILL.md`
- THEORY: `../../../THEORY/유레카/PROM_16_EUREKA_ACADEMIC_REPORT.md`, `PROM_16_EUREKA_IMPL_REPORT.md`, `EUREKA_ENGINE_DESIGN.md`
- ENGINE: `bhgman_tool/engine/eureka/` — `anti_unify.py`, `formal_context_builder.py`, `fidelity_gate.py`, `quality_gate.py`, `oracle_lens.py`, `induction_operators/{fca,amie3,leiden_true,leiden_llm}.py`
- KG: `eureka-canonical-2026-05-26`, `consensus-eureka-academic-grounding-2026-05-26` (16 RF, `MATCH (rf:ResearchFinding {cycle_id:'eureka-academic-grounding-2026-05-26'}) RETURN rf`), `consensus-eureka-design-synthesis-2026-05-27`, `consensus-eureka-bottomup-builder-2026-05-27`, `eureka-formal-context-smoketest-2026-05-27`
- 사이블: `../longinus/references/theory.md` (binding dual), `../taliban/references/theory.md` (justification gate)

# KG: eureka-canonical-2026-05-26, consensus-eureka-academic-grounding-2026-05-26
