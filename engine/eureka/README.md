# eureka (유레카) — 창조(귀납→추상)

> 정명 2026-05-27 (`eureka-l8-rectification-2026-05-27`): formerly `longinus_l8_induction`
> ("Longinus Layer-8 induction" = 2026-05-26 commander-split 이전 작명). induction은 유레카의
> 본령이라 정명. drift부(`ged_drift_detector`/`nightly_drift_check`)는 `engine/longinus_drift`로,
> 실현부(추상→구체)는 dual인 `engine/hades`로 분리됐다.

유레카 induction — KG/코드의 경향·반복 패턴을 귀납·가추로 묶어 *없던 상위 추상 개념*을 induce(PROPOSE).
비행기맨 #4 LegionCommander, 동사 **창조(구체→추상↑)**. 정반대 극 = 오캄(빼기), dual = 하데스(실현, 추상→구체↓).

**경계**: 유레카는 **PROPOSE까지만**. 실현(materialize, Extract Superclass/MERGE)은 하데스가 받는다 (auto-commit 금지).

## Spec sources

- **canonical**: `eureka-canonical-2026-05-26`
- **design synthesis**: `consensus-eureka-design-synthesis-2026-05-27` (SF1-4 — fidelity/oracle 설계)
- **academic grounding**: `consensus-eureka-academic-grounding-2026-05-26` (C5 anti-unification, FCA Ganter-Wille)
- **engine impl**: `consensus-eureka-engine-impl-2026-05-26` (c6 materialize danger → 하데스로)
- **bottom-up builder**: `consensus-eureka-bottomup-builder-2026-05-27`
- **formal-cathedral self-check**: `formal-cathedral-detection-2026-05-27` (우아함 ≠ 진실, oracle 실측 강제)
- **SKILL**: `SYMPOSIUM/SKILLS/eureka/SKILL.md` (프로토콜), 본 엔진 = 정본

## 사이클 (DETECT→GENERALIZE→SCORE→PROPOSE→JUSTIFY)

`pipeline.py`가 7-stage orchestrator. stage 2/3/6/7은 `NotImplementedStage`(injectable) — Leiden/요약/retrieval/drift는
`PipelineConfig`로 주입한다. 핵심 경로(KG backend, dogfood)는 stage 1·4·4.5·4.7·4.8·5·5.5.

| stage | 역할 | 모듈 | gate 종류 |
|---|---|---|---|
| 1 Extract | ReferenceSite → `:Candidate` (pure relabel) | `pipeline.stage_1_extract` | — |
| 2 Community | Leiden multi-γ (injectable) | `induction_operators/leiden_llm.py` (stub) | — |
| 3 Summarize | per-community Haiku (injectable, 재배맨 SOP) | (inject) | — |
| 4 Induce | FCA concept (extent, intent) | `induction_operators/fca.py` | — |
| 4.5 Quality | FCA stability / 압축 | `quality_gate.py` | HARD |
| **4.7 Oracle** | **나생문 oracle 불변식** (extent recount/intent/acyclic/stability) | `oracle_lens.py` | **HARD (pre-gate)** |
| 4.8 Fidelity | consilience witness (형성에 안 쓴 관계로도 cohere?) | `fidelity_gate.py` | SOFT (warn만) |
| **4.9 Creative** | structural candidate → divergent semantic proposals → independent critic receipts | `creative.py` (opt-in) | **HARD for semantic proposal** |
| 5 Naesengmoon | surviving `:AbstractClass` → `VERDICT_PENDING` | `pipeline.stage_5_naesengmoon_gate` | — |
| 5.5 Validate | pre-merge required-fields | `validator.py` | HARD |

`run_from_kg(run_cypher, config)` = stage_0(KG-EXTRACT) → 전체. `formal_context_builder.build_formal_context`가
**3 pre-filter**(①bulk 노드 제외 ②hub degree-cap ③독립 facet)로 KG에서 formal context를 빌드 후 `run()`.
naive FCA(전체 KG 그냥)는 bulk 노이즈 + hub 오염 = garbage (실측 확증). 실측 oracle: 321 obj / avg_intent 3.63 → 비자명 concept.

## Modules

- `pipeline.py` — 7-stage orchestrator + `run_from_kg`. stage 2/3/6/7 = `NotImplementedStage` (DI 주입점)
- `formal_context_builder.py` — `build_formal_context` (CypherRunner, FormalContextConfig). stage_0 KG-EXTRACT, 3 pre-filter
- `induction_operators/`:
  - `fca.py` — Galois lattice extent/intent (Ganter-Wille 1999), iceberg pruning, stability σ. **pipeline-wired** (stage_4 default `method='fca'`)
  - `amie3.py` — Horn rule mining (Lajus-Galárraga-Suchanek 2020), AMIE 3.5.1 Java subprocess
  - `leiden_llm.py` — GraphRAG hierarchical Leiden + LLM summary **stub** (Edge 2024). gds.leiden 인프라 의존
  - `registry.py` — InductionMethod 이름 registry (OCP, induced→required-field 검증용)
- `amie3_adapter.py` — **amie3 pipeline-wiring** (2026-05-27): context→triples + Horn rule→FormalConcept 어댑터 + `induce_via_amie3`(Java 주입식). `PipelineConfig(method='amie3')`로 선택. 보수적(high-PCA·Rule of Three).
- `stages.py` — **stage 2/3/6/7 구현체** (2026-05-27): `LeidenCommunityStage`(gds.leiden, 인프라-degrade) / `SummarizeStage`(결정론 digest) / `HybridRetrievalStage`(lexical RRF) / `DriftLoopStage`(partition Jaccard vs τ). `wire_default_stages(run_cypher)`로 주입. pipeline이 stage payload를 context로 체인(GraphRAG).
- `induction_models.py` — `AbstractClass`, `GeneralizesEdge`, `InductionMethod`, `AbstractClassStatus` (Pydantic v2)
- `oracle_lens.py` — `kg_oracle_gate` (KG 결정론 불변식) + `run_oracle_gate`/`subprocess_runner` (shell oracle, opt-in). 나생문 2 lens-class 중 oracle(실행) 렌즈
- `fidelity_gate.py` — `run_fidelity_for_members` (Whewell consilience, SOFT). 형성에 안 쓴 witness 관계로 cohere 측정
- `anti_unify.py` — Plotkin LGG anti-unification (**code backend**). 불일치=hole, hole_ratio≤0.5 + Rule of Three. PROPOSE(dry-run)만
- `quality_gate.py` — FCA stability + 압축 점수 (silhouette/modularity/Goodhart cap)
- `creative.py` — opt-in bounded abductive loop. Contrastive association → divergent proposal → deterministic echo/paraphrase/baseline gates → distinct-model critic → content-addressed `ValidationReceipt`. Receipt가 `PROVIDER_DIVERSE` / `MODEL_DIVERSE_SAME_PROVIDER` / `CORRELATED_SAME_MODEL`을 명시해 모델 다양성과 완전한 독립성을 혼동하지 않는다. Candidate body and receipts remain first-class pipeline artifacts; pipeline receipt-bound acceptance는 검증 가능하지만 CLI는 외부 verdict ingress가 생길 때까지 `VERDICT_PENDING`만 쓴다.
- `validator.py` — `gate_before_merge` application-side required-fields enforcement
- `protocols.py` — `Stage`/`StageResult`/`NotImplementedStage`/`InductionOperator` protocols (DI 경계)

## 가드 (헛 "유레카!" 차단)

- **Rule of Three** (≥3 instance): apophenia / premature abstraction 차단
- **oracle HARD gate**: well-formed 아니면 reject (extent/intent/acyclic/stability)
- **fidelity SOFT gate**: thin이면 SOFT_WARN (block 안 함, 판단렌즈 escalate)
- **formal-cathedral self-check**: 우아함에 속지 말고 oracle 실측 — *외침 ≠ 진실*
- **auto-commit 금지**: PROPOSE만. 실현은 하데스 + 사용자/나생문 gate
- **자기승인 금지**: proposer와 critic의 provider+model fingerprint가 같으면 receipt는 REJECT. `--accept`는 외부 human/Naesengmoon verdict ingress가 구현될 때까지 항상 fail-closed(rc=2); `--creative --apply`도 `VERDICT_PENDING`까지만 쓴다.
- **bounded intuition**: 최대 round/model-call/no-progress 예산; 같은 후보 반복은 `EXHAUSTED`, 무한 ideation 금지.

## Status

- **2026-05-27**: Phase 0-3 완료 — formal_context_builder → run_from_kg → fidelity_gate(4.8 wire) → anti_unify(code backend PoC). 나생문 oracle KG backend 재조정.
- **2026-07-15**: semantic creative in-memory slice 구현. `contracts/`의 durable journal/FSM/replay/release control plane은 `DESIGN_TARGET`이며 아직 런타임 conformance를 주장하지 않는다.
- **tests**: `uv run pytest -q engine/eureka` → 160 passed, 1 skipped (FCA / oracle / fidelity / creative loop / pipeline / anti_unify / formal_context / run_from_kg / quality_gate / validator / amie3)
- **CLI**: `bhgman-tool eureka --json`은 full candidate envelope, `--creative`는 AgentClient semantic loop. 빈 KG/0후보는 `NO_CANDIDATE` + nonzero exit. dry-run 기본, `--apply`는 pending만.
- **stage 2/3/6/7**: `stages.py` 구현체 제공(`wire_default_stages`). Leiden은 gds 인프라-gated(degrade), summarize/RRF/drift는 결정론 완성. pipeline context-threading으로 체인.
- **bake-off**: FCA(default) + AMIE3 둘 다 pipeline-wired(`method` 선택). amie3는 Java subprocess(어댑터 변환). Leiden-LLM stub은 gds.leiden 인프라 대기.

## KG anchors (Longinus-bound 2026-05-27)

- 코드 ↔ KG 바인딩: 전 모듈 `-[:REALIZES]->eureka-canonical-2026-05-26` (`longinus-binding-2026-05-27` pass)
- `formal_context_builder.py -[:IMPLEMENTS]-> eureka-formal-context-smoketest-2026-05-27`
- `oracle_lens.py -[:IMPLEMENTS]-> naesengmoon-wired-ensemble-upgrade-2026-05-27`
- `anti_unify.py -[:IMPLEMENTS]-> consensus-eureka-academic-grounding-2026-05-26`
- dual: 실현은 `engine/hades` (`hades-canonical-2026-05-27`)
