---
name: hades
kg_ref: hades-canonical-2026-05-27
version: "1.0.0"
channel: stable
provenance: AI_DERIVED_FROM_USER_PRIMARY  # 동사 "실현한다" = 사용자 정전(비행기맨 #4 7번째 군단장, 2026-05-27 신설).
description: >
  하데스(Hades) 방법론 — 비행기맨 #4 산하 7번째 군단장 동사 **"실현한다"**(추상→구체↓). 유레카(구체→추상↑)의 dual.
  유레카가 PROPOSE하고 fidelity/judgment gate를 통과한(ACCEPTED) 추상을 *구체 KG 구조/소스코드로 실현*(materialize). TDD GREEN.
  `/hades` == 하데스 해줘. `/eureka`(창조)가 올린 걸 `/hades`(실현)가 내린다 — 수직축 양방향.
  사용법: `/hades <concept>` (ACCEPTED 추상 realize) · `/hades --code <template> <sites>`.
  CLI: `bhgman-tool hades [--concept X] [--apply]`. **dry-run 기본**(c6 위험), --apply만 실현. neo4j 부재 시 fetch cypher 출력.
  어원: 하계(下界=KG+소스코드 구체층)의 신. 추상을 하계로 내려보내 코드로 실현. 하네스(場)와 발음 쌍둥이지만 別 존재.
  **위험**: materialize = "가장 위험"(engine-impl c6). dry_run 기본 + ACCEPTED만 + reversibility-first + ≤5 site rollout.
  엔진 정본: `bhgman_tool/engine/hades/` (hades.py realize_kg_abstraction/realize_code_template + hades_runner[fetch ACCEPTED→realize e2e] + hades_models). CLI=`engine/cli/main.py` hades verb.
  # KG: hades-canonical-2026-05-27, eureka-canonical-2026-05-26 (dual), consensus-eureka-engine-impl-2026-05-26 (c6)
---

## 📚 References (lazy-load)

상세 지식은 `references/`에 분리 — 필요 시 로드 (2026-06-02 엔진/KG에서 수확):
- [`phases.md`](references/phases.md) — fetch_accepted → characterization-gate → MERGE(realize)/undo 스테이지 + 안티패턴
- [`kg_logging.md`](references/kg_logging.md) — AbstractClass status=CANONICAL realizedBy=hades + INSTANCE_OF Cypher 스키마
- [`quick_ref.md`](references/quick_ref.md) — 한 장 치트시트

---

## 🔗 MIC / 군단장

**동사**: 실현한다 (추상→구체↓). **dual**: 유레카(창조, 구체→추상↑) — 둘이 수직축 양방향 완성.
**형식**: Galois γ(concretization, Cousot) / anamorphism·unfold(Lambek-Wadler) / refinement calculus(Wirth/Back/Morgan) / TDD GREEN.
**경계**:
- vs **유레카**: 유레카=추출·귀납·발상(↑), 하데스=실현·연역·벼림(↓). 같은 수직축 정반대 방향.
- vs **재배맨**: 재배맨=출격(누가 일할지 분배·orchestration), 하데스=실현(실제 코드 써냄). 재배맨이 출격시킨 일꾼이 하데스 동사 수행. 분배≠써냄.
- vs **하네스**: 하네스=바닥/場(코드 써지는 장소, 수동 scaffold), 하데스=그 場에 코드 써내리는 능동 행위. 場 ≠ 場에서의 실현.

---

## 핵심 — 실현은 위험하다, 그래서 게이트 통과분만

유레카가 "찾았다!"(PROPOSE)해도 대부분 가짜라 게이트가 거른다. 하데스는 그 **살아남은(ACCEPTED) 것만** 구체로 실현.
materialize = engine-impl c6 "가장 위험"(우연 결합 영구화 / 100+ site 분산 장애 / 확산 후 비가역). 그래서 4 가드:

1. **ACCEPTED만**: PROVISIONAL/REJECTED 거부 (유레카 PROPOSE→fidelity→judgment→ACCEPTED 후에만 하데스).
2. **dry_run 기본**: PLANNED(계획)만 방출, auto-apply 금지. apply는 명시 + 검증 후.
3. **reversibility-first**: 모든 plan에 undo (KG=supersede / code=inline-back). 되돌릴 수 없으면 실현 안 함.
4. **≤5 site 점진 rollout**: 코드 materialize는 한 번에 ≤5 site (분산 장애 차단). 초과 시 배치 분할.

---

## 사이클 (realize)

> 엔진 정본 = `bhgman_tool/engine/hades/hades.py`. 본 SKILL은 프로토콜만.

| backend | 함수 | 실현 | undo |
|---|---|---|---|
| KG | `realize_kg_abstraction(concept, verdict, members, dry_run=True)` | concept→CANONICAL + 멤버 INSTANCE_OF | concept→SUPERSEDED + edge DELETE |
| code | `realize_code_template(concept, lgg_template, sites, max_sites=5)` | Extract Superclass/shared-fn (PLANNED only) | site별 inline-back |

코드 backend은 **항상 dry-run PLANNED** — 실제 apply는 characterization test gate(behavior 동등 증명) 후 별 절차.

---

## What NOT To Do

| 금지 | 이유 |
|---|---|
| PROVISIONAL/REJECTED 실현 | gate 미통과 — ACCEPTED만 |
| auto-apply (dry_run 무시) | materialize 가장 위험. 명시+검증 후만 |
| undo 없는 실현 | reversibility-first covenant 위반 |
| >5 site 일괄 refactor | 분산 장애. 점진 rollout |
| 하데스가 추상 *발견* | 그건 유레카 동사 (하데스=실현만) |
| 하데스가 *출격/분배* | 그건 재배맨 동사 (하데스=실제 써냄만) |

# KG: ATOM_Skill_hades, hades-canonical-2026-05-27, eureka-canonical-2026-05-26 (dual)

---

## Measurement & Conditional Dispatch (2026-05-30 추가)

사용자 정전 정정 2026-05-30 (`user-verdict-7cmd-need-based-conditional-dispatch-2026-05-30`): 7군단장 측 *고정 USES edge* retract → *measurement-driven conditional dispatch*. 본 commander도 `measure()` + `decide_dispatch()` API를 따른다.

### 본 commander metric & threshold

- 정전 SPEC: `SYMPOSIUM/THEORY/00_공통/7CMD_NEED_BASED_DISPATCH_SPEC.md` §3 Table
- 구현: `bhgman_tool/engine/legion/measurement.py` — 본 commander의 hadesMeasurement class
- KG: `:MeasurementFunction` + `:DispatchThreshold` nodes (parent: `7cmd-measurement-driven-conditional-dispatch-2026-05-30`)

### Stevens scale type & 학문 grounding

각 metric의 Stevens 1946 scale type (nominal/ordinal/interval/ratio)을 `:MeasurementFunction.scale` field에 기록.
Goodhart drift (1975) mitigation은 Naesengmoon meta-check 또는 cycle-end invocation-log empirical reconcile (`lesson-occam-proxy-strength-needs-empirical-spot-check-2026-05-28`).

### Dispatch 정전

`measure()` → threshold-gated need detection → 다른 commander conditional invocation (Hades realization pattern universalized, parent `hades-canonical-2026-05-27`).
고정 USES는 *historical provenance only* (`:DispatchEvent` runtime record).

# KG: 7cmd-measurement-driven-conditional-dispatch-2026-05-30, user-verdict-7cmd-need-based-conditional-dispatch-2026-05-30, hades-canonical-2026-05-27, mf-hades-*
