# eureka — Phases (per-stage responsibilities + anti-patterns)

> Lazy-load reference. Parent: [`../SKILL.md`](../SKILL.md). KG: `eureka-canonical-2026-05-26`, `eureka-formal-context-smoketest-2026-05-27`.
> 동사 = **창조한다** (구체→추상↑). dual = 하데스 (추상→구체↓). 엔진 정본 = `bhgman_tool/engine/eureka/`.
> 모든 stage covenant: **PROPOSE only — write/auto-commit 금지.** 실현(materialize)은 하데스.
> # src: ../SKILL.md frontmatter, engine/eureka/pipeline.py docstring

---

## 0. 두 사이클: SKILL phase vs engine stage

유레카에는 두 층의 단계 표현이 있다 — SKILL의 5-phase 개념 사이클과, engine의 8-stage 실행 파이프라인.

| SKILL phase | engine stage(s) | # src |
|---|---|---|
| DETECT | stage_0 KG-EXTRACT, stage_1 extract, stage_2 community | `../SKILL.md` 사이클 표 + `pipeline.py:run_from_kg/stage_1_extract` |
| GENERALIZE | stage_3 summarize, stage_4 induce | `pipeline.py:stage_4_induce` + `stages.py:SummarizeStage` |
| SCORE | stage_4.5 quality → 4.7 oracle (HARD) → 4.8 fidelity (SOFT) | `pipeline.py:stage_4_7_oracle_gate/stage_4_8_fidelity_gate` |
| PROPOSE | stage_5 naesengmoon-gate, stage_5.5 pre-merge-validator | `pipeline.py:stage_5_naesengmoon_gate` + `validator.gate_before_merge` |
| JUSTIFY | (handoff) stage_6 hybrid-retrieval, stage_7 drift-loop | `pipeline.py:run` tail + `stages.py` |

GraphRAG 체인 (Edge 2024): community → summarize → (induce) → retrieval / drift. 각 stage의 dict payload가 context에 merge되어 다음 stage가 산출을 잇는다.
# src: stages.py docstring + pipeline.py:_try_run_stage (`context.update(result.payload)`)

---

## 1. DETECT — 입력 context 구성 (stage 0/1/2)

**책임**: KG/코드에서 추상화 후보(반복·경향 패턴)를 끌어모은다.

- **stage_0 KG-EXTRACT** (`formal_context_builder.build_formal_context`): KG → FCA formal context `dict[object, frozenset[attr]]`. attribute = `"facet:value"`.
- **stage_1 extract** (`pipeline.stage_1_extract`): L1-L7 ReferenceSite → `:Candidate`. pure relabel.
- **stage_2 community** (`stages.LeidenCommunityStage`): gds.leiden 군집화. `project(UNDIRECTED)→stream→drop`. gds 부재 시 degrade (비치명적).
# src: formal_context_builder.py:1-17, pipeline.py:115-117, stages.py:71-99

**핵심 진실 (실측 확증)**: 알고리즘이 아니라 *입력 context 구성*이 레버리지. naive FCA = garbage. 3 pre-filter가 garbage↔signal을 가른다 — ① bulk-exclude (`KG_AI`/`Comment`/`OCCAM_SLICED`/`ARCHIVED` label 제외) ② hub degree-cap (facet 차수 > cap = mega-hub 제외, default cap=4) ③ independent facets (상관 동의어-묶음 금지, 직교 facet만, e.g. `ALIGNS_WITH_AXIS × USES_ABSTRACT_DOMAIN`).
# src: formal_context_builder.py:1-31, FormalContextConfig(hub_degree_cap=4, min_facets_per_object=2)

**Code backend DETECT**: clone detection (≥3 유사 조각, Rule of Three).
# src: ../SKILL.md 사이클 표 row 1

### Anti-patterns
- **naive FCA (전체 KG 그냥 입력)** → bulk 노이즈 + mega-hub 오염 = garbage (실측). 3 pre-filter 필수.
  # src: formal_context_builder.py:3-11, KG `eureka-formal-context-smoketest-2026-05-27`
- **상관 동의어 facet** (evidence/normativity/artifact 같이 묶기) → tautological concept (Goodhart). 직교 facet만.
  # src: formal_context_builder.py:8-10
- **gds.leiden을 DIRECTED projection으로** → 실패. leiden은 UNDIRECTED projection 선행 필수 (실 infra 검증).
  # src: stages.py:6-8, project_cypher(orientation="UNDIRECTED")
- **apophenia** (무작위에서 패턴 봄) / 확증편향 → spurious 개념 발명. 비용 비대칭 (false-positive 싸 보임).
  # src: KG `finding_eu_B3_bias_pitfalls` (https://en.wikipedia.org/wiki/Apophenia)

---

## 2. GENERALIZE — 추상 induce (stage 3/4)

**책임**: 모인 후보를 *없던 상위 개념*으로 묶는다 (Whewell colligation — 흩어진 사실에 새 conception을 superinduce).
# src: KG `finding_eu_A2_whewell_mapping` (https://plato.stanford.edu/entries/whewell/)

- **stage_3 summarize** (`stages.SummarizeStage`): per-community 결정론 digest (LLM-free, 정렬 고정 = 재현 가능).
- **stage_4 induce** (`pipeline.stage_4_induce`): induction operator dispatch via `PipelineConfig.method`:
  - `fca` (default): FCA Galois closure concept (Ganter-Wille 1999), extent/intent, idempotent. batch ≤ 500 nodes; 초과 시 fallback. # src: induction_operators/fca.py:1-9, MAX_BATCH=500
  - `amie3`: Horn rule mining (Java subprocess, `amie3_adapter`가 Horn rule → FormalConcept으로 통일).
  - `leiden-llm`: gamma_sweep resolution.
  세 operator 모두 `FcaResult(FormalConcept)` shape로 정규화 → 후단(quality/oracle/fidelity/gate) 동일 처리.
# src: pipeline.py:157-198, stages.py:summarize_community

**Code backend GENERALIZE**: `anti_unify.py` Plotkin LGG (least general generalization) — 같은 위치 일치=고정, 불일치=fresh 변수(hole). N 인스턴스의 가장 구체적 공통 추상.
# src: anti_unify.py:1-9 (Plotkin 1970), KG `finding_eu_D2_antiunification_mapping`

### Anti-patterns
- **구조(토큰 길이) 불일치인데 LGG 강행** → `anti_unify` returns None; 단순 LGG 불가, SP decompose에 위임 (클론 아님).
  # src: anti_unify.py:46-48
- **abduction/induction을 *정당화*로 혼동** → 발견(유레카)과 정당화(나생문)는 별개 맥락 (Reichenbach 1938). 유레카는 발견의 맥락(가설 생성)일 뿐, 그 자체가 진리 보증 아님.
  # src: KG `finding_eu_A4_discovery_vs_justification`, `finding_eu_A3_induction_pitfalls`
- **wrong inductive bias / 추상 level mismatch** → no-free-lunch + bias-variance. architecture-domain 정렬 필요.
  # src: KG `finding_eu_C3_overfit_pitfalls` (https://arxiv.org/abs/2304.05366)

---

## 3. SCORE — 3-gate cascade (stage 4.5 / 4.7 / 4.8)

**책임**: induce된 후보가 *진짜* 추상인지 측정. 3 gate가 서로 다른 것을 본다.

| stage | gate | 종류 | 본다 | # src |
|---|---|---|---|---|
| 4.5 | quality | (FAIL→return) | 압축·안정성 metric vs 학문 threshold | `quality_gate.py` |
| 4.7 | oracle (kg_oracle_gate) | **HARD** | well-formed 불변식 (checkable only) | `oracle_lens.py` |
| 4.8 | fidelity | **SOFT** | downstream 효용 (Whewell consilience) | `fidelity_gate.py` |

**4.5 quality** thresholds (per `seed-prom16lag-cons-quality-gate-silhouette-modularity-2026-05-20`): silhouette s̄ ≥ 0.50 (Rousseeuw 1987) / modularity Q ≥ 0.30 (Newman 2006) / FCA stability σ ≥ 0.50 (Roth-Obiedkov-Kourie 2008) / AMI ≥ 0.50 (Vinh 2010) / Goodhart cap 0.95 (> 0.95 = reject as artifact). FAIL → pipeline `return` (진행 중단).
# src: quality_gate.py:3-23, pipeline.py:326-336

**4.7 oracle (HARD)** — 컴파일러나생문 family, KG backend 결정론 불변식. 첫 FAIL에서 short-circuit:
1. extent recount: |extent| ≥ min_extent (주장한 support 실제 성립?)
2. schema: intent non-empty (empty intent = degenerate concept)
3. acyclic: name ∉ extent (self-referential = cycle)
4. stability: stabilityScore ≥ min_stability
FAIL → 판단렌즈(stage_5) 진입 차단. (선先 gate: 빌드/well-formedness 깨지면 의미검증 무의미.)
# src: oracle_lens.py:44-93, pipeline.py:338-340

**4.8 fidelity (SOFT)** — Whewell consilience. 추상은 *형성에 안 쓴* witness 관계(`IN_CATEGORY`/`RELATED_TO`/`SAME_TRADITION`/...)로도 cohere해야 진짜. per-witness top_share ≥ 0.30, ensemble k ≥ 2 witness 통과 = PASS. FAIL = SOFT_WARN → 판단렌즈로 escalate (hard reject 아님). `fidelity_runner` 없으면 skip(opt-out).
# src: fidelity_gate.py:1-16,36-42, pipeline.py:257-279

**Code backend SCORE**: hole_ratio ≤ 0.5 + Rule of Three.
# src: anti_unify.py:propose_template, ../SKILL.md 사이클 표 row 3

### Anti-patterns
- **단일 proxy metric** → 모든 proxy는 Goodhart. 단일 metric 금지, ensemble k ≥ 2 witness.
  # src: fidelity_gate.py:5-6 (SF3)
- **metric > Goodhart cap (0.95)를 "완벽한 추상"으로 채택** → suspect artifact, reject.
  # src: quality_gate.py:60-71
- **oracle를 LLM 논증으로 대체** → oracle는 checkable(문법·빌드·타입·테스트·수치)만. 의미적 타당성은 판단렌즈 몫. 둘을 섞으면 안 됨.
  # src: oracle_lens.py:5-6
- **표면구조 overfit** (spurious ≠ causal) → held-out witness 검증으로 거른다.
  # src: KG `finding_eu_C3_overfit_pitfalls`, fidelity_gate.py (held-out 관계)

---

## 4. PROPOSE — 후보 결정화 (stage 5 / 5.5)

**책임**: 살아남은 추상을 *후보로만* 표시. covenant: write/auto-commit 금지.

- **stage_5 naesengmoon-gate** (`stage_5_naesengmoon_gate`): 각 AbstractClass status → `VERDICT_PENDING` (model_copy, 비파괴).
- **stage_5.5 pre-merge-validator** (`validator.gate_before_merge`): MERGE 전 ac/edge payload 검증. 예외 시 `return` (중단).
- 결과 KG label: `:CandidateAbstraction` PRELIMINARY/VERDICT_PENDING.
# src: pipeline.py:282-286, 346-356, ../SKILL.md 사이클 표 row 4

**Code backend PROPOSE**: LGG 템플릿 (dry-run). `propose_template` status ∈ PROPOSED/REJECTED/INSUFFICIENT.
# src: anti_unify.py:69-99

### Anti-patterns
- **유레카가 직접 materialize** (Extract Superclass / MERGE / 코드 써냄) → 그건 하데스 동사 (추상→구체). 유레카는 PROPOSE까지만.
  # src: anti_unify.py:6-8 ("실제 Extract Superclass = 하데스"), ../SKILL.md frontmatter covenant
- **over-generalization** (hole_ratio > 0.5) → reject. 너무 많은 hole = 빈 템플릿.
  # src: anti_unify.py:33-34, propose_template:86-90
- **premature abstraction** ("잘못된 추상은 중복보다 비싸다", Sandi Metz) → sunk-cost + 조건문 지옥 + 의존자 전체 오염. Rule of Three (3번째 인스턴스에서 추출), 둘이면 중복 택(되돌리기 쉬움).
  # src: anti_unify.py:69-79 (Rule of Three guard), KG `finding_eu_D3_overabstraction_pitfalls` (https://sandimetz.com/blog/2016/1/20/the-wrong-abstraction)

---

## 5. JUSTIFY — 외부 검증 handoff (stage 6 / 7)

**책임**: PROPOSE된 후보를 유레카 *밖*에서 검증 (발견의 맥락 → 정당화의 맥락 전환).

- **JUSTIFY gate**: `/tlb <candidate> --lens formal-cathedral` — 나생문 escalate-to-oracle, rubber-stamp 금지. 우아함에 속지 말고 oracle 실측. **외침 ≠ 진실.**
- **stage_6 hybrid-retrieval** (`stages.HybridRetrievalStage`): 2-채널 (lexical community-summary RRF + native vector dim768). 채널 granularity 다르므로 강제 융합 안 하고 둘 다 보고 (정직). vector 채널은 runner+index+query_embedding 다 있을 때만 활성.
- **stage_7 drift-loop** (`stages.DriftLoopStage`): partition 안정도 (best-match Jaccard 평균). prev 대비 < τ(0.75)면 re-induction 신호.
# src: ../SKILL.md 사이클 표 row 5 + 가드, stages.py:149-232, KG `finding_eu_A4_discovery_vs_justification`

### Anti-patterns
- **게이트 없이 "찾았다!" 결정화** → 대부분의 "유레카!"는 가짜 (apophenia). 유레카는 항상 게이트와 짝: 외침(PROPOSE) → 검증(나생문 oracle).
  # src: ../SKILL.md "왜 유레카인가", `naesengmoon-oracle-formal-cathedral-smasher`
- **나생문 self-check를 rubber-stamp** → formal-cathedral lens는 판단렌즈 논증으로 PASS 불가, 가장 싼 oracle falsifier 강제.
  # src: ../SKILL.md 가드, `formal-cathedral-detection-2026-05-27`
- **vector 채널 강제 융합** → granularity(community vs node) 다름. 둘 다 보고가 정직. 미populate면 빈 채널 degrade.
  # src: stages.py:149-155, 168-177

---

## 6. 경계 (다른 군단장과)

- **유레카 vs 오캄**: 둘 다 MDL/Kolmogorov 최소화하나 *반대 방향*. 유레카 = generative (개념 C 생성, N이 참조, one-to-many↑); 오캄 = subtractive (중복 삭제, many-to-one↓). N≫1이면 유레카, N≈1이면 오캄. clone 경계: 활성 call site ≥2 / Type-1·2 / 동시 편집 / 교차모듈 = ABSTRACT(유레카); 12mo dormant / 0 coverage / 0 ref / superseded = ARCHIVE(오캄).
  # src: KG `finding_eu_C4_mdl_boundary`, `finding_eu_D4_clone_boundary`, anti_unify.py:7
- **유레카 vs 롱기누스**: colimit 생성(+1 노드) = 유레카 / morphism(엣지) = 롱기누스.
  # src: ../SKILL.md MIC 섹션, `bihaenggiman-7commander-boundaries`
- **유레카 vs 나생문**: 새 노드 = 유레카 / 검증 = 나생문 (JUSTIFY handoff).
  # src: ../SKILL.md 경계

---

## 7. References

- engine: `bhgman_tool/engine/eureka/{pipeline,stages,anti_unify,formal_context_builder,fidelity_gate,quality_gate,oracle_lens,protocols}.py`, `induction_operators/{fca,amie3}.py`
- `../SKILL.md` (5-phase 사이클 + 가드 + What NOT To Do)
- KG: `eureka-canonical-2026-05-26`, `eureka-formal-context-smoketest-2026-05-27`, `consensus-eureka-design-synthesis-2026-05-27`, `formal-cathedral-detection-2026-05-27`, ResearchFinding cycle `eureka-academic-grounding-2026-05-26` (16 findings: A1-A4 abduction/Whewell/Reichenbach, B1-B4 concept-formation, C1-C4 ILP/FCA/MDL, D1-D4 refactoring/Plotkin/Metz)
- 사이블: `../longinus/references/theory.md` (binding), `../taliban/SKILL.md` (oracle lens)

# KG: ATOM_Skill_eureka, eureka-canonical-2026-05-26
