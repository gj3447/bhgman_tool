---
name: eureka
kg_ref: eureka-canonical-2026-05-26
version: "1.0.0"
channel: stable
provenance: AI_DERIVED_FROM_USER_PRIMARY  # 동사 "창조한다" = 사용자 정전(비행기맨 #4 군단장). 엔진=공학 결정화.
description: >
  유레카(Eureka) 방법론 — 비행기맨 #4 산하 군단장 동사 **"창조한다"**(구체→추상↑).
  KG/코드의 경향·반복 패턴을 귀납·가추로 묶어 *새 추상 개념*을 induce(PROPOSE). 아르키메데스 "찾았다!".
  `/eureka` == 유레카 해줘. `/prom`이 지식수집 동사이듯 `/eureka`는 개념창조 동사.
  사용법: `/eureka` (SYMPOSIUM KG dogfood) · `/eureka --kg <facet1>×<facet2>` · `/eureka --code <path>`.
  CLI: `bhgman-tool eureka` (KG 패턴→추상 induce, **PROPOSE only·write 없음** — covenant, 실현은 하데스).
  경계: PROPOSE까지만 — 실현(추상→구체, Extract Superclass/MERGE)은 dual인 **하데스**(hades-canonical). auto-commit 금지.
  엔진 정본: `bhgman_tool/engine/eureka/` (formal_context_builder + pipeline.run_from_kg + fidelity_gate + anti_unify). CLI=`engine/cli/main.py` eureka verb.
  induction operator **bake-off**: `PipelineConfig.method` = `fca`(default, Galois lattice) | `amie3`(Horn rule mining, Java, `amie3_adapter`가 FormalConcept으로 통일). GraphRAG stage 2/3/6/7 = `stages.py`(Leiden gds-degrade / 결정론 summarize·RRF·drift).
  # KG: eureka-canonical-2026-05-26, consensus-eureka-design-synthesis-2026-05-27,
  #     eureka-formal-context-smoketest-2026-05-27, formal-cathedral-detection-2026-05-27
---

## 📚 References (lazy-load)

상세 지식은 `references/`에 분리 — 필요 시 로드 (2026-06-02 기존 이론/엔진/KG에서 수확):
- [`theory.md`](references/theory.md) — 학문 grounding 5축 (가추·colligation / Reichenbach 발견맥락 / 통찰·개념형성 / colimit·ILP·FCA / Plotkin anti-unification)
- [`phases.md`](references/phases.md) — 파이프라인 스테이지별 책무 + 안티패턴
- [`gates.md`](references/gates.md) — 품질/oracle(HARD)/fidelity(SOFT) 게이트 스택 + 임계값
- [`kg_logging.md`](references/kg_logging.md) — AbstractClass/FormalConcept Cypher MERGE 스키마
- [`quick_ref.md`](references/quick_ref.md) — 한 장 치트시트

---

## 🔗 MIC / 군단장

**동사**: 창조한다 (구체→추상↑). **dual**: 하데스(추상→구체↓, 실현). **정반대 극**: 오캄(빼기/subtractive).
**경계** (bihaenggiman-7commander-boundaries): colimit 생성(+1)=유레카 / morphism=롱기누스 / 정리=오캄 / 검증=나생문.

---

## 왜 유레카인가

흩어진 것들을 보다가 **"아! 이것들 다 같은 거잖아!"** 하고 *없던 상위 개념을 찾아내는* 동사.
단 — **대부분의 "유레카!" 외침은 가짜다**(apophenia, premature abstraction). 그래서 유레카는 항상 *게이트와 짝*이다:
외침(유레카 PROPOSE) → 검증(나생문 oracle). 외침만으론 부족 (`naesengmoon-oracle-formal-cathedral-smasher`).

---

## 사이클 (DETECT→GENERALIZE→SCORE→PROPOSE→JUSTIFY)

> 엔진 정본 = `bhgman_tool/engine/eureka/`. 본 SKILL은 프로토콜만 (drift 방지, /prom 패턴).

| # | 단계 | KG backend | code backend |
|---|---|---|---|
| 1 | **DETECT** | `formal_context_builder.py` — 3 pre-filter(①bulk 제외 ②hub degree-cap ③독립 facet). 노드×facet | clone detection (≥3 유사 조각, Rule of Three) |
| 2 | **GENERALIZE** | `induce_fca` — FCA concept (extent, intent) | `anti_unify.py` — Plotkin LGG (불일치=hole) |
| 3 | **SCORE** | quality(압축, silhouette/MDL) → **oracle**(kg_oracle_gate 불변식, HARD) → **fidelity**(consilience witness, SOFT) | hole_ratio≤0.5 + Rule of Three |
| 4 | **PROPOSE** | `:CandidateAbstraction` PRELIMINARY/VERDICT_PENDING (auto-commit 금지) | LGG 템플릿 (dry-run) |
| 5 | **JUSTIFY** | **나생문** `/tlb <candidate> --lens formal-cathedral` (escalate-to-oracle, rubber-stamp 금지) | 〃 |

→ JUSTIFY 통과분만 살아남음. 실현(materialize)은 **하데스**가 받음 (유레카 아님).

### 실행 (KG backend, dogfood)

```
1. formal_context = build_formal_context(neo4j_runner, FormalContextConfig())   # 3 pre-filter
2. pr = run_from_kg(neo4j_runner, PipelineConfig(cycle_id=..., fidelity_runner=...))
3. 각 PROPOSED :CandidateAbstraction → /tlb --lens formal-cathedral 자체검증
4. 보고: 후보 + gate verdict (oracle/fidelity/math) + 살아남은 것
```

---

## 가드 (헛 "유레카!" 차단)

- **Rule of Three** (≥3 instance): apophenia / premature abstraction 차단 (Metz).
- **oracle HARD gate**: well-formed 아니면 reject (kg_oracle_gate: extent/intent/acyclic/stability).
- **fidelity SOFT gate**: 형성에 안 쓴 witness 관계로도 cohere하나(Whewell consilience). thin이면 SOFT_WARN.
- **formal-cathedral self-check**: 우아함에 속지 말고 oracle 실측. **외침≠진실**.
- **auto-commit 금지**: PROPOSE만, 실현은 하데스 + 사용자/나생문 gate.

---

## What NOT To Do

| 금지 | 이유 |
|---|---|
| 게이트 없이 "찾았다!" 결정화 | apophenia — 대부분 가짜 |
| naive FCA (전체 KG 그냥) | bulk 노이즈 + hub 오염 = garbage (실측 확증) |
| 상관 동의어 facet | tautological concept (Goodhart) |
| 유레카가 materialize | 그건 하데스 동사 (추상→구체) |
| 수치 anchor 없이 보고 | filter param durable 기록 필수 (formal-cathedral가 잡음) |

# KG: ATOM_Skill_eureka, eureka-canonical-2026-05-26, eureka-formal-context-smoketest-2026-05-27

---

## Measurement & Conditional Dispatch (2026-05-30 추가)

사용자 정전 정정 2026-05-30 (`user-verdict-7cmd-need-based-conditional-dispatch-2026-05-30`): 7군단장 측 *고정 USES edge* retract → *measurement-driven conditional dispatch*. 본 commander도 `measure()` + `decide_dispatch()` API를 따른다.

### 본 commander metric & threshold

- 정전 SPEC: `SYMPOSIUM/THEORY/00_공통/7CMD_NEED_BASED_DISPATCH_SPEC.md` §3 Table
- 구현: `bhgman_tool/engine/legion/measurement.py` — 본 commander의 eurekaMeasurement class
- KG: `:MeasurementFunction` + `:DispatchThreshold` nodes (parent: `7cmd-measurement-driven-conditional-dispatch-2026-05-30`)

### Stevens scale type & 학문 grounding

각 metric의 Stevens 1946 scale type (nominal/ordinal/interval/ratio)을 `:MeasurementFunction.scale` field에 기록.
Goodhart drift (1975) mitigation은 Naesengmoon meta-check 또는 cycle-end invocation-log empirical reconcile (`lesson-occam-proxy-strength-needs-empirical-spot-check-2026-05-28`).

### Dispatch 정전

`measure()` → threshold-gated need detection → 다른 commander conditional invocation (Hades realization pattern universalized, parent `hades-canonical-2026-05-27`).
고정 USES는 *historical provenance only* (`:DispatchEvent` runtime record).

# KG: 7cmd-measurement-driven-conditional-dispatch-2026-05-30, user-verdict-7cmd-need-based-conditional-dispatch-2026-05-30, hades-canonical-2026-05-27, mf-eureka-*
