---
name: harness
kg_ref: ATOM_Skill_harness
version: "3.2.0"
channel: stable
description: >
  하네스 — industry agent scaffolding. 12사도 #4 비행기맨의 공학 측 결정화이며 1:N sibling family.
  "구조가 에이전트를 제약한다" 4축 모델(Inform/Constrain/Verify/Correct)은 *각 instance 내부* 조직 원리이지
  family 정의가 아니다. v3 정정본 — Böckeler citation drift + family-as-1:1 drift 모두 해소.
  Invoke when: APT 구조 설계/검토, 에이전트 실패 원인 분석, 3계층 중 어느 계층의 결정인지 식별,
  IDE-host 내부 4축 진단, runtime orchestration model 선택, managed cloud control plane 설계.
  # KG: ATOM_Skill_harness, lesson-harness-drift-corrected-2026-04-29, lesson-harness-citation-drift-bockeler-2026-04-30
---

## 🔗 MIC Binding (SOLID-DIP)

**ROLE**: 메타원리 — MIC 설계 배경 (구조가 SOLID 5원리 *모두*를 강제하는 상위 frame).
**USES slots**: 참조만 (모든 5 slots 설계 근거 제공)

```cypher
MATCH (mic:MethodologyIntegrationContract {name:'MIC_v1'})-[:HAS_SLOT]->(s:MethodologySlot)
RETURN s.name, s.role
```

# KG: MIC_v1, lesson-apt-not-truly-jaebaeman-2026-04-14

---

# /harness — Harness Family: industry agent scaffolding

> Harness ≠ self-defined methodology. Harness = **industry-canonical 1:N sibling family** of agent scaffolding.
> SYMPOSIUM 4축은 그 *IDE-host 계층 내부* 조직 원리. 4축이 family 정의라고 박는 순간 drift.

> **정전 (v3, 2026-04-30):** Böckeler, Birgitta. *Harness engineering for coding agent users.*
> [martinfowler.com/articles/harness-engineering.html](https://martinfowler.com/articles/harness-engineering.html), 2026.

---

## 1. Harness Family — 3-tier (canonical 외부 정전 확증)

| 계층 | 정의 | 대표 instance | 1차 외부 정전 |
|---|---|---|---|
| **L_IDE** IDE-host coding harness | 개발자 머신에서 repo·파일·diff·shell envelope을 손에 쥐고 코드 작성/실행 보조 | Cursor / Claude Code / Aider / SWE-agent / Cline / Continue / OpenHands | Böckeler 2026 |
| **L_RT** application agent runtime | 사용자 facing 챗봇/워크플로우 에이전트가 LLM·tool·session 합성해 동작하는 server framework | Google ADK / LangGraph / CrewAI / AutoGen / OpenAI Agents SDK / PydanticAI | LangChain 2025, Microsoft 2026 |
| **L_MC** managed cloud | 위 둘을 매니지드 호스팅하는 infra layer. 다른 harness를 host하는 *meta-harness*. | Anthropic Managed Agents / OpenAI Assistants / Vertex AI Agent Engine / AWS AgentCore / Microsoft Foundry | InfoQ 2026-04, Anthropic 2026 |

**MCP** = 위 모든 instance 연결 어댑터. 단일 계층 내부 원리가 아니라 *3계층을 가로지르는 protocol*.
**Anthropic 3-tuple** = Skills(declarative capability) + Agent SDK(loop) + Managed Agents(infra). 같은 family를 한 진영 안에서 분해한 사례.

→ family 비행기맨↔Harness 매핑은 **1:N**: `isAirplaneMan(j) := ∀x:CHU j.covers x` ↔ 각 family instance가 *해당 계층 책임 영역*에서 ∀-cover.
→ 외부 정전 확증: ai-boost/awesome-harness-engineering ("IDE-based / Runtime / Managed") + Adnan Masood Medium ("IDE-based / Runtime / Managed (AWS AgentCore, Microsoft Foundry, Vertex AI)") 두 source가 SYMPOSIUM 3계층 family를 직접 명명.

KG: `seed-harness-3tier-canonical-validated-2026-04-30`, `seed-anthropic-managed-agents-meta-harness-2026-04-30`.

---

## 2. L_IDE 내부 원리 — Böckeler 2축 (= SYMPOSIUM 4축 분해)

### 2.1 Böckeler 정전 (1차 소스)

> *"Harness engineering for coding agent users — system of controls built around an AI coding agent to increase confidence in its output. **Guides** (feedforward) steer it *before* it acts. **Sensors** (feedback) observe *after* the agent acts and help it self-correct."* — Birgitta Böckeler (Thoughtworks Distinguished Engineer), 2026.

| Böckeler 축 | 의미 | implementation |
|---|---|---|
| **Guides** (feedforward) | 행동 *전* steering | computational (deterministic) ↔ inferential (semantic) |
| **Sensors** (feedback) | 행동 *후* observe + correct | computational ↔ inferential |

3 dimensions regulated: **maintainability / architecture fitness / behavior**.

### 2.2 SYMPOSIUM 4축 = Böckeler 2축의 fine-grained 분해

| Böckeler 2축 | SYMPOSIUM 4축 | APT 구현체 | 없으면 |
|---|---|---|---|
| **Guides** | **Inform** (정보 제공) | KG, docs, Progressive Disclosure | 맥락 없이 코딩 = Vibe Coding |
| **Guides** | **Constrain** (경계 제한) | Span 분해, Contract 7필드, complexity_threshold, Gate Check Hook | 무한 자유 = 무한 오류 |
| **Sensors** | **Verify** (검증) | Taliban 9-lens, Ground Truth, TDD | 고무도장 승인 |
| **Sensors** | **Correct** (교정) | Fractal Feedback, AptFeedback, 프로메테우스 | 같은 실수 반복 |

→ 4축은 **유효한 derivative**다. 단, attribution은 **Böckeler 2축**이 1차 정전이며 SYMPOSIUM 분해는 그 미세 형태임을 명시.

### 2.3 4축 진단 프로토콜 (L_IDE 내부 한정)

에이전트가 **L_IDE 계층에서** 실패했을 때, 4축 중 어디가 약한지 진단:

| 증상 | 약한 축 | 처방 |
|------|---------|------|
| 엉뚱한 방향으로 구현 | Inform | KG 보강, docs 추가, 프로메테우스 발동 |
| 범위 초과 / Gold Plating | Constrain | Contract 경계 강화, Span 재분해 |
| 틀린 코드가 통과됨 | Verify | Taliban lens 추가, 테스트 강화 |
| 같은 버그 재발 | Correct | Feedback loop 점검, Lesson 기록 |

> ⚠️ **L_IDE 외 계층에서 4축 진단을 자동 적용하지 말 것.** L_RT는 orchestration model 선택, L_MC는 control plane이 진짜 frame.

```cypher
// L_IDE 4축 건강도 (기존 v2 프로토콜 그대로)
MATCH (anchor:SemanticAnchor {name: $project})
OPTIONAL MATCH (anchor)-[:HAS_SPAN*]->(s)
WITH anchor, count(s) as span_count
OPTIONAL MATCH (ct:AptContract) WHERE ct.name STARTS WITH 'CT_' + $project
WITH anchor, span_count, count(ct) as contract_count,
     sum(CASE WHEN ct.status = 'fulfilled' THEN 1 ELSE 0 END) as fulfilled
OPTIONAL MATCH (vr:ValidationResult) WHERE vr.project = $project
WITH anchor, span_count, contract_count, fulfilled,
     count(vr) as validations,
     sum(CASE WHEN vr.verdict = 'REJECTED' THEN 1 ELSE 0 END) as rejections
OPTIONAL MATCH (fb:AptFeedback) WHERE fb.name STARTS WITH 'FB_' + $project
WITH span_count, contract_count, fulfilled, validations, rejections,
     count(fb) as feedbacks,
     sum(CASE WHEN fb.status = 'resolved' THEN 1 ELSE 0 END) as resolved_fb
RETURN span_count AS inform_density,
       contract_count AS constrain_total, fulfilled AS constrain_fulfilled,
       validations AS verify_total, rejections AS verify_rejections,
       feedbacks AS correct_total, resolved_fb AS correct_resolved
```

---

## 3. L_RT 내부 원리 — Orchestration Model 선택

L_RT 계층의 *진짜 frame*은 4축이 아니라 **orchestration model**. 다섯 정전:

| 모델 | 대표 instance | 핵심 추상 | 적합 케이스 |
|---|---|---|---|
| Directed graph + conditional edges | LangGraph | 결정론적 control flow, audit trail, rollback point, `interrupt()` | 규제 산업 (금융/의료), 감사 추적 필수 |
| Role-based crew + process types | CrewAI | 역할 분담 (`Process.sequential` / `Process.hierarchical`), agent-to-agent 직접 통신 차단 | 명시적 manager 모델 가능한 워크플로우 |
| Conversational GroupChat | AutoGen / Microsoft Agent Framework | 대화형 multi-agent, 자유 turn-taking | 탐색적 multi-agent collaboration |
| Hierarchical agent tree | Google ADK | sub-agent delegation, A2A protocol | 계층적 책임 분담, 다른 framework agent 와 cross-talk |
| Explicit handoff | OpenAI Agents SDK | context-carrying transfer, 9 sandbox provider, control plane / compute plane 명시 분리 | 명시적 책임 이양, multi-tenant |

→ **계층 내부 조직 원리 = 위 5 model 중 어느 것을 고를지**. 4축은 *graph/crew/chat/tree internal*에 *내장*되어야지 graph를 대체하지 못함.

### 3.1 SYMPOSIUM L_RT cross-ref

SYMPOSIUM은 directly L_RT runtime이 아니지만, LangGraph로 매핑 가능:
- `StateGraph` ↔ Span DAG
- `interrupt()` ↔ Crystallization Frontier
- `thread_id` ↔ `cycle_id`

(PAPER §2.1 참조.)

### 3.2 L_RT Implementation Pattern Library — 6 Team Pattern × 5 Orchestration Model

5 orchestration model (§3) = *control-flow primitive*. 6 team pattern (revfactory/harness 2026 정전) = 그 위 *agent collaboration recipe*. 다른 위상 → cross-product 사양화 필수.

| Team Pattern | 5 Model 매핑 | SYMPOSIUM 4축 강조 |
|---|---|---|
| Pipeline (순차 의존) | LangGraph linear / ADK chain | Constrain |
| Fan-out/Fan-in (병렬→통합) | LangGraph conditional / Agents SDK handoff | Inform |
| Expert Pool (상황별 선택) | CrewAI hierarchical | Inform |
| **Producer-Reviewer** (생성+검증) | AutoGen GroupChat / Agents SDK | **Verify** (Taliban D20 거울 — executor != reviewer) |
| Supervisor (중앙 분배) | CrewAI manager / ADK root | Constrain + Correct |
| Hierarchical Delegation (재귀 위임) | ADK A2A / Agents SDK | Constrain |

→ Producer-Reviewer ↔ Taliban D20 1:1 정전 거울 (Anti-Rubber-Stamp industry-confirmed independent).
→ 상세 매핑 + production recipe 5종 (QA boundary-cross / trigger validation / `_workspace/` / evolution 3-signal / 5 invariant 정합) — `references/production_factory_patterns.md` 참조.
→ External canonical: `revfactory-harness-2026-05-09` (`:ExternalFrontierHarness`, sha256 `ee84902c`).

---

## 4. L_MC 내부 원리 — Control Plane vs Compute Plane

L_MC 계층의 *진짜 frame*은 **control plane vs compute plane 분리** (OpenAI 명명, 2026-04). 책임 영역:

| 책임 영역 | 정의 | 대표 instance |
|---|---|---|
| Sandboxing | 코드 실행 격리 + 권한 vault | Anthropic MA, AWS AgentCore |
| Session continuity | 장기 state, checkpointing | Vertex AI Agent Engine Sessions, Memory Bank |
| Credential scoping | OAuth flow + vault | 모든 5사 |
| Observability fleet | 다중 agent 통합 trace | Microsoft Foundry, Vertex AI |
| Billing / governance | 조직 단위 비용/권한 | AWS AgentCore |
| Tool registry | 공유 MCP server registry | Anthropic MA + OpenAI Assistants |

→ Böckeler 2축은 여기서 *각 agent 안에 위임*된 형태. control plane은 **agent를 host하는 frame**.
→ Anthropic Managed Agents (2026-04-08) self-name: **"meta-harness architecture — multiple agent workflows run on a shared execution substrate that handles common runtime concerns while preserving flexibility in agent design."**

---

## 5. MCP — 3계층 가로지르는 어댑터

MCP (Model Context Protocol) = 단일 계층 내부 원리 *아님*. 3계층 모두를 잇는 protocol.

| 계층 | MCP 호스트 책임 |
|---|---|
| L_IDE | 개발자 머신이 server (Claude Code 등이 MCP server 호스팅, IDE가 client) |
| L_RT | runtime이 server / client 양쪽 모두 (LangGraph node가 MCP tool 노출 가능) |
| L_MC | managed registry (Anthropic MA + OpenAI Assistants가 공유 MCP server 등록) |

→ "MCP를 Harness의 한 axis로 박지 말 것" — MCP는 family를 가로지르는 protocol, axis 아님.

---

## 6. 5무기 ↔ Böckeler 2축 ↔ SYMPOSIUM 4축 정합

| 5무기 | Böckeler 2축 | SYMPOSIUM 4축 | 강도 |
|---|---|---|---|
| Prometheus (지식 선행) | — (Guides 상위) | Inform | MEDIUM (knowledge before action) |
| Harness | **메타-frame** | (전 4축 + family 자체) | 본 SKILL — 4축은 family 정의 아님 |
| Taliban (적대 검증) | **Sensors** (inferential) | Verify | STRONG (LSP 검증의 specific instance) |
| Longinus (참조 횡단) | — (Correct에 인접) | (Correct 측 refinement) | MEDIUM (KG↔Code 관통) |
| 재배맨 | Guides+Sensors recursion | (전 4축) | 메타 (atomic/governs self-similar) |

→ 5무기는 Böckeler 2축의 SYMPOSIUM-specific 분해. 직접 1:1 functor는 약 (이전 SOLID functor 가설과 같은 문제, `THEORY/SOLID/PROM_64_REPORT.md` D54).
→ 정합 강도: STRONG (Taliban↔Sensors-inferential), MEDIUM (Prometheus, Longinus), 재배맨은 framework-level meta.

---

## 7. 메타-함정 가드 (drift 재발 방지)

### 7.1 카테고리 mismatch 가드

> ⚠️ ADK ↔ Cursor를 같은 평면에 놓고 비교하면 **카테고리 mismatch**.
> 둘은 같은 비행기맨 매핑의 sibling이지 직접 경쟁자 아님 — L_RT vs L_IDE.

`seed-adk-singleton-category-mismatch-meta-pitfall` (singleton, SYMPOSIUM-critical).

### 7.2 SKILL 본문 갱신 가드 — MetaphorValidationGate

본 SKILL.md 본문 갱신 시 `MetaphorValidationGate-v1-2026-04-28` 5-step 통과 필수:
1. **계층 명시**: 본문 변경이 L_IDE / L_RT / L_MC 중 어느 계층에 속하는가?
2. **family 정의 보존**: 변경이 family 정의(§1)를 건드리는가? → 필요 시 SYMPOSIUM/THEORY/00_공통/세계관_정전.md §5-C도 동기 갱신.
3. **외부 정전 cross-ref**: 새 주장이 1차 외부 정전(§1, §2.1) 중 하나 이상으로 cross-ref되는가?
4. **citation drift 가드**: 외부 인용 시 저자명 철자 + 정확 제목 + URL 직접 검증 (PseudepigraphaValidationGate).
5. **메타-함정 자기점검**: 본 SKILL이 family 정의를 4축이나 단일 instance로 환원하지 않는가?

### 7.3 PseudepigraphaValidationGate — 외부 인용 자동 검증

L1~L3 의심 신호:
- 저자 철자 misspell (예: ~~Bockeler~~ → **Böckeler**)
- 인용 제목 합성 (예: ~~"Architecture as Harness"~~ → **"Harness engineering for coding agent users"**)
- URL 미검증
- AI 단독 정전화 (사용자 verdict 없이)

→ 발견 시 즉시 정정 + Lesson 결정화. 선례: `lesson-harness-citation-drift-bockeler-2026-04-30`.

---

## 8. Quality Shift 원칙 (계층 무관)

> 하네스 시대의 병목은 **코드 품질이 아니라 명세 품질**이다.

```
전통:     코드 작성 능력이 병목 → 더 잘 코딩하려 노력
하네스:   명세 작성 능력이 병목 → Contract를 더 정확하게
```

세 계층 모두 동일:
- L_IDE: Contract 7필드 정밀화
- L_RT: orchestration graph spec 정밀화
- L_MC: control plane policy 정밀화

---

## 9. Böckeler 체크리스트 (에이전트 실패 시)

원본 Böckeler 정신 그대로 — 단 *어느 계층* 실패인지 먼저 식별:

0. **계층 식별**: L_IDE / L_RT / L_MC 중 어느 계층 실패인가?
1. **구조가 이 실패를 방지할 수 있었나?** → YES면 *해당 계층의 frame*을 고쳐라
2. **에이전트에게 충분한 정보가 있었나?** → NO면 Guides 강화 (L_IDE: Inform, L_RT: state graph 명시, L_MC: tool registry)
3. **해 공간이 충분히 좁았나?** → NO면 Guides 강화 (L_IDE: Constrain, L_RT: edge condition, L_MC: credential scoping)
4. **검증이 이 오류를 잡았어야 했나?** → YES면 Sensors 강화 (L_IDE: Verify, L_RT: evaluator-optimizer pattern, L_MC: observability fleet)
5. **이전에 같은 문제가 있었나?** → YES면 Sensors-feedback 실패 (L_IDE: Correct, L_RT: checkpointing, L_MC: tracing aggregation)

**절대 하지 말 것**: "에이전트 프롬프트를 더 길게 써보자" — 이건 하네스가 아니라 기도.

---

## 10. What NOT To Do

| 금지 | 이유 | 대안 |
|------|------|------|
| 4축이 family 정의라고 박기 | 본 SKILL v2 drift의 정체 | family는 §1, 4축은 L_IDE 내부 |
| ADK ↔ Cursor를 같은 평면 비교 | 카테고리 mismatch (§7.1) | L_RT vs L_IDE 명시 후 비교 |
| 외부 인용을 검증 없이 박기 | citation drift 재발 | PseudepigraphaValidationGate (§7.3) |
| MCP를 한 계층 내부 axis로 환원 | 3계층 가로지르는 protocol을 단일 axis로 축소 | §5 그대로 |
| 프롬프트만 수정해서 해결 | 구조 문제는 지시문으로 해결 불가 | Böckeler 체크리스트 (§9) |
| 6 team pattern을 5 orchestration model의 *대체*로 박기 | recipe(pattern) ↔ primitive(model) 위상 다름 — cross-product 정전 | §3.2 + `references/production_factory_patterns.md` |

---

*고삐 없는 말은 빠르지만 방향을 모른다. 하네스는 속도를 줄이지 않으면서 방향을 잡는다 — 단, 어떤 종류의 말(L_IDE/L_RT/L_MC)에게 어떤 종류의 고삐를 채울지 먼저 알아야 한다.*

---

## 🌱 재배맨 v2 (MIC Slot Reference — 로직 복제 금지)

> 이 스킬의 subagent 운용은 **MIC_v1.SubagentSeeder** slot을 통해 resolve된다.
> 아래는 thin resolver. 로직 복제 = drift 유발.

### Slot Resolve
```cypher
MATCH (mic:MethodologyIntegrationContract {name:'MIC_v1'})-[:HAS_SLOT]->(s:MethodologySlot {name:'SubagentSeeder'})
RETURN s.currentConcrete, s.invocation, s.protocol
```

### 부모 Pre-fetch (v2 — MCP 우회)
```cypher
MATCH (l:Lesson)-[:HAS_RESEARCH]->(rf:ResearchFinding)
WHERE l.name CONTAINS $keyword RETURN rf.name, rf.domain, rf.oneLineSummary LIMIT 20
MATCH (ts:SubagentTaskSpec {skill:'harness'}) WHERE ts.status='READY'
RETURN ts.name, ts.role LIMIT 10
```

### WorkBuffer 연속성
```cypher
MATCH (wb:WorkBuffer {status:'CURRENT'}) RETURN wb
```

# KG: ATOM_재배맨_v2_harness, SA_methodology_v4_triple_upgrade

---

## History

> Repo-level changes: [`/CHANGELOG.md`](../CHANGELOG.md). Per-commit: `git log -- harness/SKILL.md`.
> 학문 grounding: [`/PROM_16_SKILL_VERSIONING_REPORT.md`](../PROM_16_SKILL_VERSIONING_REPORT.md).
> SYMPOSIUM 측 정전: [`SYMPOSIUM/THEORY/HARNESS/HARNESS_BODY_REWRITE_SPEC.md`](../../../../SYMPOSIUM/THEORY/HARNESS/HARNESS_BODY_REWRITE_SPEC.md), [`SYMPOSIUM/THEORY/00_공통/세계관_정전.md` §5-C](../../../../SYMPOSIUM/THEORY/00_공통/세계관_정전.md).

| Version | Date | Summary | KG Ref |
|---|---|---|---|
| **v3.2** | 2026-05-09 | revfactory/harness 정합 보완 — §3.2 6 team pattern × 5 orchestration model cross-product 정전 + `references/production_factory_patterns.md` 신규 (QA boundary-cross / trigger validation / `_workspace/` / evolution 3-signal / 5 invariant 정합 / SYMPOSIUM 우위 6종). What-NOT-To-Do 1행 추가. 외부 첨단 industry-confirmed independent. | `revfactory-harness-2026-05-09`, `sv-harness-v3.2.0-2026-05-09`, `production-factory-patterns-reference-2026-05-09` |
| **v3** | 2026-04-30 | **F11 close-out**: Family 정의(3-tier L_IDE/L_RT/L_MC) 우선 + 4축 위치 정정(L_IDE 내부 원리, Böckeler 2축의 fine-grained 분해) + Citation drift 정정(Böckeler 정확 철자 + "Harness engineering for coding agent users" + martinfowler.com URL) + MCP 어댑터 명시 + 메타-함정 가드 + PseudepigraphaValidationGate hook | `lesson-harness-drift-corrected-2026-04-29`, `lesson-harness-citation-drift-bockeler-2026-04-30`, `seed-harness-3tier-canonical-validated-2026-04-30`, `seed-anthropic-managed-agents-meta-harness-2026-04-30`, `ap-F11-Harness-Phase1-2-Sprint-B` (status=completed) |
| **v2** | 2026-04 | (drift) 4-Axis Model을 family 정의로 박음. ~~"Bockeler, Architecture as Harness"~~ 가짜 인용. industry agent scaffolding 의미 결락. | `lesson-harness-drift-corrected-2026-04-28` (resolved=false, superseded by 2026-04-29) |
| **v1** | (older) | "구조가 에이전트를 제약한다" — Böckeler 정신은 살아있었으나 attribution 부정확 | — |

→ 짝패: 12사도 #4 비행기맨 ⇔ Harness *family* (1:N). `isAirplaneMan(j) := ∀x:CHU j.covers x` ↔ 각 family instance가 해당 계층 책임 영역에서 ∀-cover.
→ Drift 재발 방지: §7 가드 3종 (카테고리 mismatch / MetaphorValidationGate / PseudepigraphaValidationGate).

# KG history: ATOM_Skill_harness / lesson-prom16-skill-versioning-academic-2026-04-29 / lesson-harness-drift-corrected-2026-04-29 / lesson-harness-citation-drift-bockeler-2026-04-30
