# eureka — Quick Ref (cheatsheet)

> Lazy-load reference. Parent: [`../SKILL.md`](../SKILL.md).
> Commander #4-군단장 비행기맨 산하. 동사 **창조한다** (구체→추상↑); dual = 하데스(실현, 추상→구체↓); 정반대 극 = 오캄(빼기).
> # src: SKILL.md frontmatter + §"🔗 MIC / 군단장"; engine/eureka/README.md L1-11
> KG: `eureka-canonical-2026-05-26` (`:AbstractNode:CanonicalName:LegionCommander`, verified) # src: KG node query

---

## 1. Invocation

| form | meaning | src |
|------|---------|-----|
| `/eureka` | SYMPOSIUM KG dogfood (run_from_kg) | SKILL.md frontmatter L11 |
| `/eureka --kg <facet1>×<facet2>` | KG induction over a facet pair | SKILL.md frontmatter L11 |
| `/eureka --code <path>` | code backend (anti_unify) | SKILL.md frontmatter L11 |
| `bhgman-tool eureka` | CLI — KG dogfood, **PROPOSE only, no write** | cli/parser.py L252-261; cli/commands.py L983 |
| `bhgman-tool eureka --local` | bundled neo4j-free KG (`~/.bhgman/kg.json`) | cli/parser.py L256-260 |

**Covenant**: PROPOSE까지만 — auto-commit 금지. 실현(materialize, Extract Superclass/MERGE)은 dual인 **하데스**(`hades-canonical-2026-05-27`)가 받는다.
# src: SKILL.md frontmatter L12-13; cli/commands.py L984,1011-1013

CLI returns exit 2 if Neo4j unavailable ("eureka reads KG to build a formal context — no live connection to scan"). # src: cli/commands.py L989-995

---

## 2. Cycle: DETECT → GENERALIZE → SCORE → PROPOSE → JUSTIFY

엔진 정본 = `engine/eureka/` (SKILL = 프로토콜만, drift 방지). `pipeline.py` = 7-stage orchestrator + `run_from_kg`.
# src: SKILL.md §사이클 L36-37; engine/eureka/README.md L23-26

| stage | role | module | gate |
|-------|------|--------|------|
| 0 KG-EXTRACT | build formal context (3 pre-filter) | `formal_context_builder.build_formal_context` | — |
| 1 Extract | ReferenceSite → `:Candidate` (pure relabel) | `pipeline.stage_1_extract` | — |
| 2 Community | Leiden multi-γ (injectable) | `induction_operators/leiden_llm.py` (stub) | — |
| 3 Summarize | per-community digest (injectable, 재배맨 SOP) | `stages.SummarizeStage` | — |
| 4 Induce | FCA concept (extent, intent) | `induction_operators/fca.py` (`induce_fca`) | — |
| 4.5 Quality | FCA stability / 압축 | `quality_gate.evaluate` | **HARD** |
| 4.7 Oracle | 나생문 oracle 불변식 (KG, executable) | `oracle_lens.kg_oracle_gate` | **HARD (pre-gate)** |
| 4.8 Fidelity | consilience witness (held-out 관계로 cohere?) | `fidelity_gate.run_fidelity_for_members` | SOFT (warn만) |
| 5 Naesengmoon | `:AbstractClass` → `VERDICT_PENDING` | `pipeline.stage_5_naesengmoon_gate` | — |
| 5.5 Validate | pre-merge required-fields | `validator.gate_before_merge` | **HARD** |
| 6/7 | hybrid-retrieval / drift-loop (injectable) | `stages.HybridRetrievalStage` / `DriftLoopStage` | — |
# src: engine/eureka/README.md L28-39; pipeline.py L304-360 (run), L363-378 (run_from_kg)

핵심 경로(KG backend, dogfood) = stage 1·4·4.5·4.7·4.8·5·5.5. stage 2/3/6/7 = `NotImplementedStage` (DI 주입점), `wire_default_stages(run_cypher)`로 주입. # src: engine/eureka/README.md L25-26,76; pipeline.py L77-103,289-302

**Induction operator bake-off** (`PipelineConfig.method`): `fca` (default, Galois lattice) | `amie3` (Horn rule mining, Java subprocess via `amie3_adapter`) | `leiden-llm` (gds.leiden stub). 모두 FormalConcept shape로 정규화 → 후단 동일 처리. # src: SKILL.md frontmatter L15; pipeline.py L51-62,157-198

---

## 3. The leverage is the INPUT, not the algorithm

하드진실 #1 (실측 확증, `eureka-formal-context-smoketest-2026-05-27`): naive FCA(전체 KG 그냥) = garbage (상관 facet tautology + mega-hub 오염 + bulk 노이즈). `build_formal_context`의 **3 pre-filter**가 garbage↔signal을 가른다:

1. **bulk-exclude** — `KG_AI / Comment / OCCAM_SLICED / ARCHIVED` label 제외 (`DEFAULT_BULK_LABELS`).
2. **hub degree-cap** — facet 차수 > `hub_degree_cap` (default 4) 인 mega-hub 제외 (전 concept 오염원).
3. **independent facets** — 상관 동의어-묶음 금지, 직교 facet만. default = `ALIGNS_WITH_AXIS × USES_ABSTRACT_DOMAIN` (`DEFAULT_FACET_RELS`).

object는 ≥`min_facets_per_object` (default 2) facet을 가져야 (1-facet = trivial). 실측 oracle: 321 obj / avg_intent 3.63 → 비자명 concept.
# src: formal_context_builder.py L1-16,28-42,44-62; pipeline.py L368-372

---

## 4. Gates (헛 "유레카!" 차단)

대부분의 "유레카!" 외침은 가짜(apophenia, premature abstraction) → 외침(PROPOSE) 은 항상 게이트와 짝.
# src: SKILL.md §왜 유레카인가 L29-31

- **Rule of Three** (≥3 instance, Metz): premature abstraction 차단. code backend `propose_template(min_instances=3)`. # src: SKILL.md §가드 L62; anti_unify.py L69-79
- **Quality gate (4.5, HARD)**: silhouette s̄≥0.50 (Rousseeuw 1987) / modularity Q≥0.30 (Newman 2006) / FCA stability σ≥0.50 (Roth-Obiedkov-Kourie 2008) / AMI≥0.50 (Vinh 2010) / **Goodhart cap 0.95** — >0.95 = suspect artifact, reject. # src: quality_gate.py L3-9,18-22,60-70
- **Oracle gate (4.7, HARD pre-gate)**: `kg_oracle_gate` checkable 불변식 — ① `|extent| ≥ min_extent` ② intent 비어있지 않음 ③ acyclic (`name ∉ extent`) ④ `stability ≥ min_stability`. 첫 FAIL short-circuit. FAIL → 판단렌즈(stage_5) 진입 차단. # src: oracle_lens.py L44-93; pipeline.py L210-254,338-340
- **Fidelity gate (4.8, SOFT)**: Whewell consilience — 추상이 *형성에 안 쓴* held-out witness 관계(default `IN_CATEGORY/RELATED_TO/SAME_TRADITION/ABOUT/CLASSIFIED_AS/CONTAINS`)로도 cohere해야. per-witness `top_share ≥ 0.30`, ensemble `k≥2` passing = PASS, 아니면 SOFT_WARN→judgment (block 안 함). thin/tautological 추상이 여기서 흩어져 잡힘. # src: fidelity_gate.py L8-12,26-50,94-119
- **formal-cathedral self-check**: JUSTIFY = 나생문 `/tlb <candidate> --lens formal-cathedral` (escalate-to-oracle, rubber-stamp 금지). 우아함 ≠ 진실, oracle 실측 강제. # src: SKILL.md §사이클 L45; engine/eureka/README.md L20,68

JUSTIFY 통과분만 살아남음. 실현(materialize)은 하데스가 받음 (유레카 아님). # src: SKILL.md §사이클 L47

---

## 5. Code backend (anti_unify, Plotkin LGG)

N개 코드 조각의 *최소 일반화* (least general generalization, Plotkin 1970): 같은 위치 모두 일치=고정, 불일치=fresh 변수(hole `·N`) = 추상클래스/공유함수 템플릿.
- `propose_template(snippets, min_instances=3)` → status ∈ `PROPOSED / REJECTED / INSUFFICIENT`.
- 가드: 토큰 길이 불일치 → REJECTED (LGG 불가, SP decompose 위임); `hole_ratio > 0.5` → REJECTED (over-generalization).
- **dry-run 템플릿만** — 실제 Extract Superclass(코드 써냄)는 하데스.
# src: anti_unify.py L1-12,37-99

---

## 6. Key academic anchors

논리=Peirce 가추(abduction, 새 개념 도입하는 유일 추론) + Whewell colligation/consilience. 과학철학 경계 = Reichenbach 1938 발견의 맥락(유레카) vs 정당화의 맥락(나생문). 수학 = ILP predicate invention ⇔ FCA 개념격자 (Ganter-Wille 1999) ⇔ 범주론 colimit. 코드 = Plotkin 1970 anti-unification + Fowler 리팩터링. 경계 = 유레카(generative, 개념↑) vs 오캄(subtractive, 중복↓), 둘 다 MDL/Kolmogorov. 함정 = apophenia / underdetermination / premature abstraction (Metz Rule of Three).
# src: PROM_16_EUREKA_ACADEMIC_REPORT.md C1-C6 + 함정 (16/16 ResearchFinding verified)

---

## 7. Gotchas

- **PROPOSE only** — eureka never writes/merges. 잊고 materialize하면 그건 하데스 동사 침범. # src: SKILL.md §What NOT To Do L77; cli/commands.py L984
- **naive FCA = garbage** — 3 pre-filter 없이 전체 KG 던지면 bulk 노이즈 + hub 오염. # src: SKILL.md §What NOT To Do L75; formal_context_builder.py L3-5
- **상관 동의어 facet 금지** — tautological concept (Goodhart). 직교 facet만. # src: SKILL.md §What NOT To Do L76; formal_context_builder.py L9-11
- **수치 anchor 없이 보고 금지** — filter param (hub_cap / facet_rels / thresholds) durable 기록 필수 (formal-cathedral가 잡음). # src: SKILL.md §What NOT To Do L78
- **FCA batch ≤ 500** — context size > `MAX_BATCH` (500) → `fallback_reason` 세팅, AMIE3/Leiden로 위임. # src: induction_operators/fca.py L5-9,18,99-107
- **stage 2/3/6/7 미주입 시 NotImplementedStage** — recorded but non-fatal; Leiden은 gds.leiden 인프라-gated (degrade). # src: pipeline.py L289-302; engine/eureka/README.md L51,76

---

## 8. Files

| concern | path |
|---------|------|
| protocol (SKILL) | `../SKILL.md` |
| engine 정본 | `bhgman_tool/engine/eureka/` (README.md = 모듈 지도) |
| KG-EXTRACT + 3 pre-filter | `engine/eureka/formal_context_builder.py` |
| orchestrator | `engine/eureka/pipeline.py` (`run`, `run_from_kg`) |
| FCA operator | `engine/eureka/induction_operators/fca.py` |
| oracle HARD gate | `engine/eureka/oracle_lens.py` (`kg_oracle_gate`) |
| quality HARD gate | `engine/eureka/quality_gate.py` |
| fidelity SOFT gate | `engine/eureka/fidelity_gate.py` |
| code backend (LGG) | `engine/eureka/anti_unify.py` |
| CLI verb | `engine/cli/parser.py` L252-261, `engine/cli/commands.py` L983 |

---

## 9. KG anchors

- `eureka-canonical-2026-05-26` — commander 정본 (`:AbstractNode:CanonicalName:LegionCommander`) # src: KG query verified
- `eureka-formal-context-smoketest-2026-05-27` — 3 pre-filter 실측 근거 # src: formal_context_builder.py L1-16
- `consensus-eureka-design-synthesis-2026-05-27` — SF1-4 fidelity/oracle 설계 # src: README.md L16; fidelity_gate.py L3
- `consensus-eureka-academic-grounding-2026-05-26` — C5 anti-unification, FCA Ganter-Wille # src: README.md L17; anti_unify.py L10
- `consensus-eureka-bottomup-builder-2026-05-27` # src: README.md L19
- `formal-cathedral-detection-2026-05-27` — 우아함 ≠ 진실, oracle 실측 강제 # src: README.md L20
- `hades-canonical-2026-05-27` — dual (실현, materialize) # src: SKILL.md frontmatter L13; README.md L85
- `7cmd-measurement-driven-conditional-dispatch-2026-05-30` — measure() + decide_dispatch() # src: SKILL.md §Measurement L86-104
- ResearchFinding cycle `eureka-academic-grounding-2026-05-26` (16, verified) — `MATCH (rf:ResearchFinding {cycle_id:'eureka-academic-grounding-2026-05-26'}) RETURN rf` # src: ACADEMIC_REPORT L46; KG count verified

# KG: ATOM_Skill_eureka, eureka-canonical-2026-05-26, eureka-formal-context-smoketest-2026-05-27
