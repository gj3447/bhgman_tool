# 오답노트 피드백 루프 (TPA Lesson Feedback Loop)

> # KG: ATOM_Skill_tpa_orchestrator_v10, TPA_methodology_v10

## 목적

TPA는 **남의 코드를 분석해서 우리 프로젝트의 교훈을 얻는** 방법론.
분석 자체가 목적이 아니라, **분석 결과가 우리 코드를 개선하는** 것이 목적.

## 루프 7단계

```
① TPA 분석 (TCW→ST→SP→TA)
     ↓
② 발견 분류
     ↓
③ 오답노트 기록 (Lesson KG 노드)
     ↓
④ 개선 계획 (ActionPlan)
     ↓
⑤ 적용 (APT /apt-scw)
     ↓
⑥ 검증 (Naesengmoon Gate)
     ↓
⑦ Lesson resolved=true
```

## 발견 4유형

### 1. Similarity (구조적 동형)
두 프로젝트에서 같은 패턴이 다른 구현으로 존재.
→ 더 나은 구현을 선택하거나 통합 기회.

```cypher
MERGE (sim:Similarity {name:'sim-<name>'})
SET sim.source_project=$source, sim.target_project=$target,
    sim.pattern=$pattern, sim.confidence=$conf
```

### 2. QualityGap (품질 격차)
타겟이 우리보다 더 나은 점.
→ 즉시 Lesson 생성 (TR10).

```cypher
MERGE (gap:QualityGap {name:'gap-<name>'})
SET gap.dimension=$dim, gap.our_level=$ours, gap.their_level=$theirs,
    gap.improvement_action=$action
MERGE (gap)-[:TRIGGERS]->(l:Lesson {name:'lesson-tpa-gap-<name>'})
SET l.category='quality-gap', l.problem=$dim + ' 차이',
    l.truth=$theirs + ' 방식이 더 우수', l.solution=$action,
    l.severity='HIGH', l.resolved=false, l.createdAt=datetime()
```

### 3. NovelPattern (신규 패턴)
타겟에만 있는 패턴으로 우리도 도입하면 좋은 것.
→ confidence ≥ 0.8이면 ActionPlan에 추가.

```cypher
MERGE (np:NovelPattern {name:'NP_<name>'})
SET np.description=$desc, np.applicability=$app, np.confidence=$conf
```

### 4. AntiPattern (안티패턴)
피해야 할 것. 우리 코드에도 있으면 즉시 Lesson.

```cypher
MERGE (ap:AntiPattern {name:'AP_<name>'})
SET ap.description=$desc, ap.consequence=$con, ap.alternative=$alt
// 우리 코드에서 동일 패턴 검색
// 발견 시 Lesson 생성
```

## ActionPlan 자동 생성

TPA TA 완료 시 (또는 QualityGap 발견 시 즉시):

```cypher
MERGE (p:ActionPlan {name:'plan-<project>-quality-from-<target>-<date>'})
SET p.status='PROPOSED', p.project=$project,
    p.improvements=[$improvement_list],
    p.priority=$priority, p.createdAt=datetime()
MERGE (analysis)-[:DERIVED_FROM]->(p)
```

## 루프 종료 조건

- 모든 HIGH/CRITICAL QualityGap의 Lesson이 resolved=true
- ActionPlan의 모든 improvement가 구현+검증 완료
- Naesengmoon Gate APPROVED

## 피드백 루프 ↔ 5대 본질

| 루프 단계 | 본질 (MIC Slot) |
|---|---|
| ① 분석 | 전체 (TCW/ST/SP/TA) |
| ② 발견 | ResearchProvider (unknown 리서치) |
| ③ 기록 | KgCodeBinder (Longinus 바인딩) |
| ④ 계획 | (orchestrator 판단) |
| ⑤ 적용 | SubagentSeeder (재배맨 병렬) |
| ⑥ 검증 | AdversarialValidator (Naesengmoon) |
| ⑦ 해소 | KgCodeBinder (resolved 마킹) |

---

## v1.1 Schema Extensions (2026-04-18)

> 출처: `tpa-exec-mcp-superassistant-2026-04-18` self-feedback (21 MethodologyGap → Naesengmoon 15/5/2 → 8 Lesson cluster).
> # KG: work-buffer-2026-04-18-tpa-mcp-sa-feedback

v1.0 Contract schema `{signature, pre, post, error_mode}`는 generic/SPA 백엔드에 맞춰져 있어 브라우저 확장·이중 번들·DOM 부작용·타입 소거 코드에서 약점이 드러남. v1.1부터 다음 슬롯을 **선택적으로** 추가 (기존 호출은 그대로 유효).

### 1. DOM-Side-Effect slot (ST Contract)
- 목적: `!important` 인라인 스타일, className 토글, element 삽입/제거가 실제 inter-component 계약인 경우 명시.
- 형식: `dom_side_effects: [{target: "html|body|shadowRoot|selector", op: "style-set|class-toggle|append|remove", property?, value?, important?}]`
- 발동: `document.*.style.setProperty`, `classList.*`, `appendChild`, `createPortal` 호출 감지 시.
- 근거: lesson-tpa-side-effect-contracts-2026-04-18 (CRITICAL)

### 2. Cross-Bundle-Write slot (ST Contract)
- 목적: IIFE 번들 ↔ React 번들 등 **서로 import 불가능한** 두 번들이 `window.*` / `CustomEvent`로 주고받는 암묵 계약.
- 형식: `cross_bundle: {writes: ["window.X"], reads: ["window.Y"], via: "window|CustomEvent|postMessage"}`
- 발동: manifest 파일 리스트를 `format:'iife' | entry:content` 별로 분할 후 각 번들 내 `window.*=` 할당 교차 매칭.
- 근거: lesson-tpa-side-effect-contracts-2026-04-18, DesignPattern `Dual-Bundle-Window-IPC`

### 3. Temporal-Contract slot (ST Contract)
- 목적: `setTimeout(_, 500)`, `requestAnimationFrame`, `debounce(_, 2000)` 같은 타이밍 의존이 정합성을 좌우할 때.
- 형식: `temporal: {delay_ms?, delay_unit: "setTimeout|rAF|debounce|throttle", rationale?, race_risk?}`
- 집계: 클래스 단위 Temporal-Dependency Graph를 그려 순서 가정(A가 B보다 먼저 resolve) 표시.
- 근거: lesson-tpa-temporal-and-lifecycle-blindness-2026-04-18

### 4. initialization_mode tag (TCW Symbol)
- 목적: pub symbol이 **eager**(모듈 로드 시 즉시 인스턴스화) vs **lazy**(factory deferred) vs **on-demand**(hostname match 시 materialize)인지 구분.
- 형식: TCW symbol JSON에 `"initialization_mode": "eager"|"lazy"|"on-demand"` 1 필드 추가.
- 추론: factory 클로저(`{create: () => new X()}`) 안이면 lazy, 모듈 scope `const x = new X()`이면 eager.
- 근거: lesson-tpa-temporal-and-lifecycle-blindness-2026-04-18

### 5. silent_degradation slot (ST Contract)
- 목적: 예외를 던지지 않지만 **증명 가능하게 틀린 결과**를 반환하는 경로. `error_mode`와 orthogonal.
- 형식: `silent_degradation: {condition, wrong_result, documented: bool}`
- 예: `async isSupported()` 를 sync 자리에서 호출하여 `return true` fallback 하는 경우.
- 근거: lesson-tpa-temporal-and-lifecycle-blindness-2026-04-18

### 6. execution_context field (ST Contract)
- 목적: Chrome Extension 생태계에서 동일 TS 코드가 서로 다른 런타임 컨텍스트(SW/content-script/page/extension-page)에서 실행될 때 사용 가능한 API 집합이 다름.
- 형식: `execution_context: "service-worker"|"content-script"|"page-context"|"extension-page"|"node"|"any"`
- 발동: chrome.runtime.*, chrome.storage.*, DOM, postMessage 호출 조합으로 추론. 불확실 시 `"any"`.
- 근거: lesson-tpa-extension-blindspot-2026-04-18 (downgraded → LOW지만 필드는 유지)

### 7. type_params + ContractGap marker (ST)
- `type_params: [{name, constraint?}]` — `EventEmitter<TEvents>`, `createStorage<D>` 같은 generic의 파라미터 목록.
- `contract_gap: true` + `gap_reason: "type-is-any" | "closure-returned-shape" | "unresolved-generic"` — 시그니처만으로 Contract 유도 불가. 사용처 스캔을 요구하는 마커.
- 근거: lesson-tpa-type-erasure-recovery-2026-04-18 (TOP SOLID)

### 8. state_ownership + layering_audit (SP 후처리)
- `state_ownership`: 동일 논리 엔티티(예: plugin registration)가 **2개 이상**의 저장소(Map, Zustand, IndexedDB...)에 동시 write되면 `source_of_truth` 와 `mirrors[]` 지정.
- `layering_audit`: 모듈이 자신보다 상위 레이어(예: store)에서 하위 레이어(예: infrastructure context) 객체를 **생성**하거나 import하면 `violation` 플래그.
- 근거: lesson-tpa-state-ownership-and-layering-2026-04-18 (TOP SOLID)

### 9. workspace_resolver step (TCW Phase 1 시작 전)
- 목적: pnpm/Turbo 모노레포 `@scope/*` path alias를 **AST 순회 전에** resolve.
- 구현: 각 package의 `tsconfig.json` `paths` + root `package.json` `workspaces` 읽어 alias→실경로 맵 작성.
- 효과: cross-package Contract 의존 그래프가 올바르게 이어짐.
- 근거: lesson-tpa-monorepo-workspace-awareness-2026-04-18

### 10. 새 DesignPattern 5종 (SP library)
KG에 MERGE됨. 매칭 우선순위는 기존 51패턴 다음.

| 이름 | 카테고리 | 판별 신호 |
|---|---|---|
| `Shadow-DOM-Encapsulation` | Infrastructure | `attachShadow({mode})` + inner Tailwind 삽입 + React mount |
| `Content-Script-Injection` | Infrastructure | `chrome.runtime.getURL` + `document.head.appendChild(script)` + 다단계 fallback |
| `Build-Config-Composer` | Infrastructure | HOF that `deepmerge(base, partial)` + env-conditional plugins |
| `Dual-Bundle-Window-IPC` | Distributed | `format:'iife'` 번들 + 다른 번들이 `window.*` 읽기 |
| `Facade-over-Self-Deprecation-Layer` | Structural | 같은 모듈에서 class API + flat backward-compat API 동시 export + 공유 singleton |

### 적용 지침
- **기존 sub-skill (/tpa-tcw, /tpa-st, /tpa-sp, /tpa-ta)의 본문은 수정하지 않음.** 이 파일을 참조로만 추가.
- ST가 출력하는 JSON에 위 slot을 발견 시 포함 — 없으면 생략(하위 호환).
- Naesengmoon `--lens constitutional` 검증 시 슬롯 타당성도 체크 대상.
- v1.1 → v1.2는 자체 자기-피드백 사이클이 쌓이면 진행.

### 열린 큐 (ActionPlan — WorkBuffer에 보관)
- `ap-tpa-ext-pattern-lib-2026-04-18` — 5 새 패턴 priority bump, SP confidence 기준 재조정
- `ap-tpa-side-effect-slot-2026-04-18` ← **이 증보로 명세 완료. 구현은 TCW/ST AST 스캐너 업데이트 필요**
- `ap-tpa-jsx-cfg-pass-2026-04-18` — JSX-Shape + Rules-of-Hooks CFG (미구현)
- `ap-tpa-temporal-lifecycle-2026-04-18` — ← 명세 완료. 구현 대기
- `ap-tpa-pattern-library-v2-2026-04-18` — PubSub↔Observer disambiguation heuristic (미구현)
- `ap-tpa-type-recovery-2026-04-18` — ← 명세 완료. 구현 대기
- `ap-tpa-state-layering-audit-2026-04-18` — ← 명세 완료. 구현 대기
- `ap-tpa-workspace-resolver-2026-04-18` — ← 명세 완료. 구현 대기
