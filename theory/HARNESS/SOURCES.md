# Harness (하네스) — 자료집

> **한 줄 정의 (정정본 2026-04-29):** Harness = **industry agent scaffolding**. 비행기맨(#4)의 공학 측 결정화이며 **1:N sibling family** (3계층 — IDE-host coding harness / application agent runtime / managed cloud). "구조가 에이전트를 제약한다" 4축 모델(Inform/Constrain/Verify/Correct)은 *각 instance 내부* 조직 원리이지 family 정의 아님.

> ✅ **Drift 정정 결정화 (2026-04-29)** — KG `lesson-harness-drift-corrected-2026-04-29` resolved=true (RESOLVED_BY_CYCLE → `lesson-prom16-google-adk-2026-04-29`). 이전 2026-04-28 lesson 및 `bhgman_harness_drift_resolution_v1_2026-04-28.md` 6-Phase plan은 PROM16 ADK 사이클로 흡수·승계됨.
> 짝패: **12사도 #4 비행기맨** ⇔ Harness family. `isAirplaneMan(j) := ∀x:CHU, j.covers x` ↔ 각 family instance가 *해당 계층 책임 영역*에서 ∀-cover.
> 신화 측 미러: [`../../METAHUMOTONIC/BHGMAN/`](../../METAHUMOTONIC/BHGMAN/) — n-ary hyperedge {#4, #8, #10}와 정합. BHGMAN/harness/ 빈 폴더 = 자기참조 모순 인지 흔적 (1:N family를 1:1로 박으려던 압박이 만든 공허).
> 정전 위치: [`THEORY/00_공통/세계관_정전.md` §5-C](../00_공통/세계관_정전.md). 3계층 family 표 + MCP 어댑터 + Anthropic 3-tuple.
> KG: `lesson-harness-drift-corrected-2026-04-29` (resolved), `lesson-5dae-wonso-metaphor-drift-20260428` (RESOLVES_FROM), `MetaphorValidationGate-v1-2026-04-28` (VALIDATED_BY), `seed-adk-not-ide-coding-harness`, `seed-adk-singleton-category-mismatch-meta-pitfall`.

---

## 핵심 주장 (논문 골격용)

1. **Harness의 어원**: 말에 씌우는 고삐. 말(에이전트)의 *능력*은 살리되 **방향**을 제한한다.
2. **반-프롬프트엔지니어링**: 전통적 접근은 "에이전트를 더 똑똑하게" — 본 방법론은 "구조가 에이전트를 신뢰 가능하게."
3. **4-Axis 모델**: Inform / Constrain / Verify / Correct. 모든 phase 게이트는 이 4축으로 분해된다.
4. **Quality Shift (code → spec)**: 품질 측정의 객체가 코드에서 사양으로 이동.
5. **MIC: 철학 레이어.** 본인은 slot이 아닌 모든 5 slot의 설계 근거 제공자.
6. **Out-of-band 출처**: 사상의 뿌리는 `apt-docs/theories/05_harness_theory.md` (MinIO). 본 SKILL은 요약/운영체.

---

## 1차 소스

| 경로 | 내용 |
|---|---|
| `/Users/lagyeongjun/CD/SERVER/.claude/skills/harness/SKILL.md` | **정본 v2.** 4-Axis Model, Architecture-as-Harness, Quality Shift |
| `/Users/lagyeongjun/CD/SERVER/05_DOCS/research/harness-88lens/HARNESS_PROPERTIES_ANALYSIS.md` | 속성 분석 |
| `/Users/lagyeongjun/CD/SERVER/05_DOCS/research/harness-88lens/HARNESS_PROPERTIES_88_2ND_JUDGMENT_REPORT.md` | 88 속성 2차 판정 |
| `/Users/lagyeongjun/CD/SERVER/05_DOCS/research/harness-88lens/HARNESS_88_QUICK_REFERENCE.md` | 빠른 참조 |
| `/Users/lagyeongjun/CD/SERVER/05_DOCS/research/harness-88lens/HARNESS_88_DELIVERABLES_INDEX.md` | 산출물 색인 |
| `/Users/lagyeongjun/CD/SERVER/05_DOCS/references/harness-engineering-fowler.md` | Martin Fowler "harness engineering" 참조 (실제 저자는 **Böckeler**, 호스팅이 martinfowler.com) |
| https://martinfowler.com/articles/harness-engineering.html | **Böckeler 원문** (1차 정전) — Guides+Sensors framework |
| https://github.com/ai-boost/awesome-harness-engineering | 커뮤니티 정전 — 11 design primitives + 3 deployment models (IDE-based/Runtime/Managed = SYMPOSIUM 3계층 family와 정확 일치) |
| https://www.anthropic.com/engineering/building-effective-agents | Anthropic 정전 — workflow/agent 구분, 7 building-block patterns |
| https://blog.dailydoseofds.com/p/the-anatomy-of-an-agent-harness | Avi Chawla "Anatomy" — 11 components |
| https://www.morphllm.com/agent-engineering | MorphLLM IMPACT framework + 4-stage Read/Plan/Act/Observe |
| https://medium.com/@adnanmasood/agent-harness-engineering-the-rise-of-the-ai-control-plane-938ead884b1d | Adnan Masood "Control Plane" — fleet-level orchestration 정의 |
| `/Users/lagyeongjun/CD/SERVER/07_PROJECTS/APT/harness-engineering-apt-analysis.md` | APT-harness 분석 |

## 핵심 인용

> ⚠️ **Citation drift 정정 (2026-04-30)** — 기존 SKILL.md `Bockeler, "Architecture as Harness"` 인용은 이중 부정확. 실제 정전: Birgitta **Böckeler** (Thoughtworks Distinguished Engineer), **"Harness engineering for coding agent users"** ([martinfowler.com/articles/harness-engineering.html](https://martinfowler.com/articles/harness-engineering.html), 2026). Framework는 **Guides ↔ Sensors × Computational ↔ Inferential × {maintainability, architecture fitness, behavior}** — SYMPOSIUM 4축은 Böckeler 2축의 fine-grained 분해. 자세한 정정 명세: [`HARNESS_BODY_REWRITE_SPEC.md`](./HARNESS_BODY_REWRITE_SPEC.md) §0.

SKILL.md (v2 drift 본문 — 재작성 대기):
> **에이전트가 실패하면 에이전트를 고치지 마라. 구조를 고쳐라.**
> — ~~Bockeler, "Architecture as Harness"~~ (위 정정 참조)
>
> Harness = 말에 씌우는 고삐. 말(에이전트)의 능력을 제거하지 않으면서 **방향을 제한**한다.
>
> 전통적 접근: 프롬프트 엔지니어링, 파인튜닝 → "에이전트를 더 똑똑하게"
> 하네스 접근: 구조적 제약 → "에이전트를 더 신뢰 가능하게"

Böckeler 원문 핵심 인용 (정전):
> "Harness engineering for coding agent users — system of controls built around an AI coding agent to increase confidence in its output. Guides (feedforward) steer it *before* it acts. Sensors (feedback) observe *after* the agent acts and help it self-correct."
> — Birgitta Böckeler (Thoughtworks), 2026

## 논문 작성 시 발전 가능 축

- **(a) 4축의 직교성 검증**: Inform/Constrain/Verify/Correct가 실제로 직교 basis인지 — 의존성 그래프 분석.
- **(b) 안전과 능력의 trade-off**: 고삐가 너무 짧으면 말이 못 달림. APT의 sweet spot 정량화.
- **(c) 신뢰와 위임**: "구조적 신뢰" 개념의 인식론. 사람이 에이전트를 신뢰하는 게 아니라, 사람이 구조를 신뢰하고 구조가 에이전트를 신뢰함.
- **(d) Architecture as Harness 원전**: Bockeler, Fowler 인용 추적 — `harness-engineering-fowler.md` 참조.
- **(e) 12사도와의 관계**: Harness는 도구. 그러나 12사도들이 그 위에서 작동하는 *터*이다 — 도구가 어떻게 전제(presupposition)가 되는가.
- **(f) 비행기맨 ↔ Harness**: 비행기맨은 모든 CHU를 덮는다 (∀x.j.covers x). 그 cover 자체가 "구조의 제약". 신화-공학 다리.

---

## SOLID cross-link (2026-04-27 추가, `THEORY/SOLID/PROM_64_REPORT.md`)

### Harness ↔ OCP 매핑 가설 = WEAK (D54 결론)

D54 (`finding_solid_D54_connections_theory`)는 5무기↔5SOLID functor 가설을 검증했다. Harness↔OCP 매핑은 **WEAK**:
- OCP는 "확장에 열림, 수정에 닫힘" — 단일 원리.
- Harness는 "구조가 에이전트를 제약한다" — *4축 모두*(Inform/Constrain/Verify/Correct)를 포괄. ISP/LSP territory도 포함.
- → Harness가 OCP보다 *광범*하다. 1:1 functor 아님.

**재매핑 후보**: Harness = 메타원리 (구조가 SOLID 5원리 *모두*를 강제하는 상위 frame). OCP는 Harness의 Constrain 축 한 항목.

### Harness 4축 ↔ SOLID 5원리 비교 (구조적 비대칭)

| Harness 축 | 대응 SOLID 원리 후보 | 강도 |
|---|---|---|
| Inform | (없음 — Prometheus 영역) | — |
| Constrain | OCP + ISP + LSP | 강 (3:1) |
| Verify | LSP (Naesengmoon이 instrumentation) | 약 |
| Correct | (없음 — APT meta-review 영역) | — |

→ **결론**: Harness 4축 = SOLID 5원리의 *상위 frame*이지 *대응*이 아님. SOLID는 Harness Constrain 축의 한 lens.

### SOLID 안티패턴 10대 (D44) ↔ Harness "구조 실패" 사례

`finding_solid_D44_alternatives_pitfalls`: god-component, system-to-system 커플링, tag explosion, Interface 폭증, DI Hell, Lasagna Layer, Speculative Generality, FactoryFactory, Manager/Util 폭증, abstract-for-abstract.

→ Harness 관점 재해석: **이들은 모두 "에이전트(개발자) 실패"가 아니라 "구조 실패"**. 안티패턴 발생 시 개발자를 다시 교육하는 것이 아니라 *type system/언어 제약/architecture rule*을 손봐야 한다.

→ **Harness 5번 원칙 인스턴스**: "에이전트가 실패하면 에이전트를 고치지 마라. 구조를 고쳐라." — SOLID 안티패턴 10대는 모두 이 원칙의 적용 대상.

### 비직교성 (SOLID C2 vs Harness 4축 직교성)

`SOLID PROM_64 C2`: 5원리는 비직교 — SRP↔ISP, OCP↔DIP 개념 중복. *수학적 기저가 아니라 기억술적 묶음*.

→ **Harness 4축 발전 축 (a)**의 강한 cross-reference: 만약 SOLID 5원리가 비직교라면 Harness 4축도 의심해야 한다. 동일 차원 분석을 SOLID와 동시 수행 권장.

### KG refs

- `lesson-prom64-solid-architecture-principles-2026-04-27` (resolved=true)
- `finding_solid_D54_connections_theory` (golden, 5무기↔SOLID functor 가설)
- `finding_solid_D44_alternatives_pitfalls` (안티패턴 10대)
- `finding_solid_D15_principle_critique` (5원리 비직교성)
- `lesson-solid-lensset-design-2026-04-16` (Naesengmoon LensSet에 SOLID 5렌즈 등록 후보)

---

## ADK PROM16 cross-link (2026-04-29 추가, `THEORY/ADK/PROM_16_REPORT.md`)

### 3계층 정전화 (D16 발신)

`finding_D16_adk_harness_trends`가 industry agent scaffolding을 **3계층 매트릭스**로 분기:

| 계층 | 정의 | 대표 instance |
|---|---|---|
| **IDE-host coding harness** | 개발자 머신에서 repo·파일·diff·shell envelope를 손에 쥐고 코드 작성/실행 보조 | Cursor / Claude Code / Aider / SWE-agent / Cline / Continue |
| **application agent runtime** | 사용자 facing 챗봇/워크플로우 에이전트가 LLM·tool·session 합성해 동작하는 server framework | Google ADK / LangGraph / CrewAI / AutoGen |
| **managed cloud** | 위 둘을 매니지드 호스팅하는 infra layer (운영 비용·모니터링·세션 영속화 흡수) | Anthropic Managed Agents / OpenAI Assistants / Vertex AI Agent Engine |

→ **Harness drift 정정의 진짜 산출**: 위 5번 발전 축 "(e) 12사도와의 관계 — Harness는 도구"는 *3계층 모두를 가로지르는 메타-frame*이라는 점이 ADK PROM16에서 확증. drift였던 self-defined 4축 methodology는 이 3계층 *각 계층 내부*의 조직 원리이지 계층 자체의 정의가 아님.

### 외부 referent 라인업

drift 정정의 1차 소스로 다음을 정전화 (`lesson-harness-drift-corrected-2026-04-29` solution 후보):

| 진영 | instance | 1차 소스 |
|---|---|---|
| Cursor | IDE 통합 (model-native) | https://www.cursor.com/ |
| Claude Code | CLI/IDE coding harness | https://docs.claude.com/en/docs/claude-code/overview |
| Aider | terminal git-aware coding | https://aider.chat/ |
| SWE-agent | autonomous repo-level coding | https://github.com/SWE-agent/SWE-agent |
| **Google ADK** | application agent runtime | `THEORY/ADK/` (PROM_16_REPORT 2026-04-29) |
| LangGraph | declarative state graph | https://www.langchain.com/langgraph |
| CrewAI | role-based crew | https://www.crewai.com/ |
| AutoGen | conversational multi-agent | https://github.com/microsoft/autogen |
| **Anthropic Skills+Agent SDK+Managed Agents** | 3-tuple capability/loop/infra | https://www.anthropic.com/news/claude-skills |
| MCP | 위 모든 instance 연결 어댑터 (호스트 책임 정반대) | https://modelcontextprotocol.io/ |

### 사이블링 instance 인식 (D13/D15/D16 consensus)

> 사용자가 ADK ↔ Cursor를 *같은 평면에 놓고 비교*하는 것 자체가 메타-함정 (D15만 명시 — singleton, SYMPOSIUM-critical).
> 두 결정화는 **같은 비행기맨(#4) 매핑의 sibling**이지 직접 경쟁자 아님. 책임 층위가 다름.

→ Harness drift 정정의 핵심 인식 — Harness skill body가 *3계층 중 어느 계층의 조직 원리*를 다루는지 명시되지 않으면 drift 재발.

### KG refs (ADK)

- `lesson-prom16-google-adk-2026-04-29` (resolved=true, 16/16 finding)
- `seed-adk-not-ide-coding-harness` (consensus seed, SYMPOSIUM 결정화 핵심)
- `seed-adk-singleton-category-mismatch-meta-pitfall` (singleton, 메타-함정)
- `finding_D13_adk_harness_official` / `finding_D15_adk_harness_pitfalls` / `finding_D16_adk_harness_trends`
- `lesson-prom16-adk-symposium-decryststallization-2026-04-29` (success Lesson)

---

## 신화 측 짝패 cross-ref (BHGMAN)

> 본 자료집은 *공학 측* 정전 둥지. 신화 측 자료집은 `BHGMAN/harness/` (의도적 비움 — self-reference 모순 인지 흔적). 양쪽 분리 정전 (CLAUDE.md spec).

| 파일 | 내용 |
|---|---|
| `METAHUMOTONIC/BHGMAN/harness/README.md` | 비행기맨 harness 위상 신화 측 (의도적 비움 + cross-ref 표) |
| 본 파일 | 공학 측 자료집 (industry / 학문 정전) |

### BHGMAN 측 cross-ref 표 섹션 (2026-05-09 결정화)

`BHGMAN/harness/README.md` 의 cross-ref 표 (line 30+ 부근, KG: `formal-grounding-harness-bhgman-2026-05-09`):

- **1:N sibling family 3-tier** (PROM 16 ADK 2026-04-29): IDE-host coding harness / application agent runtime / managed cloud
- **Anthropic 3-tuple**: Skills (declarative capability) + Agent SDK (loop) + Managed Agents (infra)
- **MCP adapter role inversion**: 호스트 책임 정반대 (위 모든 instance 연결 어댑터)
- **4-Layer autonomous stack** (PROM 32 2026-04-30): L1 권한 settings.json / L2 PreToolUse hook / L3 Stop hook / L4 durable CLAUDE.md
- **Family-Relation Mirror STRONG (unique)**: 3-tier (L_MC/L_RT/L_IDE) ↔ VerticalAxisHyperedge {#4 apex / #8 substrate / #10 end} — responsibility_split + cardinality match (유일 STRONG mirror, 비행기맨 #4 only)

→ 신화 측 의도적 비움 + cross-ref 표 ↔ 공학 측 industry 정전 의 *짝패*. BHGMAN/harness/ 빈 폴더 = 1:N family 를 1:1 로 박으려던 압박이 만든 공허, drift 정정 후 인지 흔적 보존.

---

## 형식적 grounding (2026-05-10 PROM 16 추가, 12 axes)

> PROM 16 cycle `prom16-harness-grounding-2026-05-10` 16/16 STRONG/PROGRESSIVE verdict.
> 5 위상 grounding asymmetry 해소 — Harness BHGMAN axes 5 (모두 SYMPOSIUM 내부 derive) → **5 + 12 = 17 axes** (외부 학문 정전 + industry frontier).
> KG: 16 finding-prom16-harness-{axis}-2026-05-10 + 16 GROUNDS_AXIS_FOR edges.

### A. Engineering Canonical (4 axes)

#### A1 — Böckeler 2026
**1차 정전**: Böckeler, Birgitta. (2026). "Harness engineering for coding agent users." *martinfowler.com*. Thoughtworks Distinguished Engineer.

**Framework**: Guides (feedforward) ↔ Sensors (feedback), each × Computational (deterministic) ↔ Inferential (LLM-as-judge) = 2-axis × 2-implementation = 4-cell matrix.

**Harness 매핑**: SYMPOSIUM 4축 (Inform/Constrain/Verify/Correct) = Böckeler 2축 fine-grained 분해 — Inform↔Guides+Computational, Constrain↔Guides+Inferential, Verify↔Sensors+Computational, Correct↔Sensors+Inferential (CANDIDATE bijection, user verdict gate).

KG: `finding-prom16-harness-A1-bockeler-2026-05-10` (PROMOTE_STRONG)

#### A2 — Conway's Law (1968)
**1차 정전**: Conway, Melvin E. (1968). "How Do Committees Invent?" *Datamation* 14(4): 28-31.

**Quote**: "[O]rganizations which design systems are constrained to produce designs which are copies of the communication structures of these organizations."

**Formal**: STRUCTURE(System) ≅ STRUCTURE(Organization) — homomorphism (Conway 원본) / isomorphism (Yourdon-Constantine 1979 강화).

**Harness 매핑**: 1:N sibling family 3-tier 가 *임의 분류* 아닌 Conway homomorphism 의 industry instance — 산업 조직 자체 1:N 분화 (각 vendor IDE/SDK/Cloud 팀 별도 통신 cluster). Anthropic 3-tuple = Anthropic 내부 3팀 (DX/Eng/CloudOps) reflection.

**Inverse Conway Maneuver** (Skelton-Pais 2019 *Team Topologies*): SYMPOSIUM Harness family 의 *의도적* 설계 = 원하는 system architecture 먼저 정하고 *방법론 조직* 통신 구조를 그것에 맞춤.

KG: `finding-prom16-harness-A2-conway-1968-2026-05-10` (STRONG, 4 empirical validation: MacCormack 2012 / Nagappan 2008 / Herbsleb 1999 / Cataldo 2008)

#### A3 — Bell's Law of Computer Classes (1972/2008)
**1차 정전**: Bell, Gordon. (2008). "Bell's Law for the Birth and Death of Computer Classes." *CACM* 51(1): 86-94. DOI 10.1145/1327452.1327453.

**Quote**: "Roughly every decade a new, lower priced computer class forms based on a new programming platform, network, and interface resulting in new usage and the establishment of a new industry."

**Class-defining tuple**: (platform, network, interface, price_point). Succession = REPLACEMENT_WITH_RESIDUAL_COEXISTENCE.

**Harness 매핑** (POST_HOC + PARTIAL PREDICTIVE LIFT):
- L_IDE (~2023, $0-20/mo seat) ↔ Workstation 1980 analog
- L_RT (~2024, $cents/task) ↔ Web client-server 1990
- L_MC (~2025, $/session) ↔ Cloud 2006
- **Lakatos PROGRESSIVE_PROBLEM_SHIFT**: 10년 cadence falsified (LLM era 2-3년) → substrate-half-life-coupled cadence parameterization. Hard core (bifurcation tuple) preserved.
- **Predictive consequence**: L_4 tier 2027-2028 birth — on-device (Apple Intelligence/Gemini Nano) / edge-IoT / browser-WASM.

KG: `finding-prom16-harness-A3-bell-law-1972-2008-2026-05-10` (MEDIUM_STRONG_POST_HOC_PROGRESSIVE_SHIFT)

#### A4 — Aspect-Oriented Programming (Kiczales 1997)
**1차 정전**: Kiczales, G. et al. (1997). "Aspect-Oriented Programming." *ECOOP'97*, LNCS 1241, pp. 220-242. ECOOP Test-of-Time Award 2017.

**Abstractions**: cross-cutting concern, join-point, pointcut, advice, aspect, weaver.

**Harness 매핑** (PROGRESSIVE_REFINEMENT — **MCP IS A PROTOCOL, NOT AN ASPECT**):
- 4-of-6 STRONG match: join-point (MCP tool invocation event) / pointcut (settings.json hook matcher) / advice (PreToolUse/PostToolUse/Stop hook) / weaver (host runtime hooks engine, runtime not compile-time)
- 2-of-6 MEDIUM: aspect (MCP server is *capability module*, not aspect-with-its-own-pointcuts) / weaver (dynamic per-session, not static AspectJ)
- **Critique**: Filman-Friedman 2000 quantification + obliviousness 부분만족, fragile pointcut problem present (filesystem MCP `read_file` vs `read_text_file` 실제 instance), MCP Spec §Security explicit non-obliviousness (user consent required, security feature)
- **Refinement**: "MCP-as-bus + hooks-as-aspect" 정전 framing — aspect = (hook config + advice script) bundle, NOT MCP server itself. Mitigation: semantic pointcut over Longinus L1-L3 references (KG kg_ref binding).

KG: `finding-prom16-harness-A4-aop-kiczales-1997-2026-05-10` (PROGRESSIVE_REFINEMENT)

### B. Self-Reference Paradox (4 axes)

→ 본 자료집의 BHGMAN 짝패 측 (`METAHUMOTONIC/BHGMAN/harness/SOURCES.md`) 참조. 4 axes 학문 정전:

- **B1 Russell Paradox 1903** — isomorphism score 0.92 STRONG_FORMAL
- **B2 Lawvere Fixed-Point 1969** — Cantor branch, 1:1 ∀-cover *수학적으로* impossible (1:N family forced)
- **B3 Yanofsky 2003** — 6-tuple universal scheme, 12 paradox unified, upper bound proof
- **B4 Hofstadter Strange Loop 1979/2007** — BHGMAN/harness/ empty folder = canonical `:StrangeLoopRecognized` instance

KG: 4 finding-prom16-harness-B{1-4}-*-2026-05-10. Lean: `Harness_LawvereFixedPoint.lean` (243 lines, sha256 `aa867e6c...`, 0 sorry) + `HarnessSelfReference.lean` (284 lines, sha256 `56532557...`, 9 theorems 0 sorry).

### C. Industry Frontier 2026 (4 axes)

#### C1 — revfactory/harness 2026
**1차 정전**: Hwang, M. (2026). "Harness: Structured Pre-Configuration for Enhancing LLM Code Agent Output Quality." GitHub: revfactory/harness (Apache-2.0, 3.2k stars). sha256 `ee84902c...`, git `6400bf6`.

**Structure**: 8-phase workflow (Phase 0 Audit → 7 Evolution) + 6 team pattern (Pipeline / Fan-out-in / Expert Pool / Producer-Reviewer / Supervisor / Hierarchical Delegation).

**Harness 매핑** (PROGRESSIVE_INDEPENDENT_CONFIRM):
- 5/5 invariant drift = 0 (CLAUDE.md thin / 500-line / Progressive Disclosure / Pushy / Producer-Reviewer)
- 8 추가 alignment axes 발견 (3 STRONG: incremental QA / evolution 3-signal / team-size cognitive limit + 5 GAP)
- **Producer-Reviewer triple-canonical-grounding**: revfactory Phase 2 pattern 4 ↔ Naesengmoon D20 (HR11) ↔ Goodfellow 2014 GAN minimax — `producer-reviewer-triple-canonical-2026-05-10` :Hyperedge:CrossCanonGrounding 결정화

KG: `finding-prom16-harness-C1-revfactory-2026-05-10` (STRONG)

#### C2 — Anthropic 3-tuple (Skills / Agent SDK / Managed Agents)
**1차 정전**: Anthropic. (2026). Skills + Agent SDK + Managed Agents official docs (code.claude.com / platform.claude.com / claude.com/blog).

**Harness 매핑** (MEDIUM_PARTIAL — verdict pending):
- isomorphism 1.5:3 비대칭 (Skills cross-cutting, IDE-host AND SDK 양쪽 작동)
- **`context: fork` = 재배맨 SOP exact isomorphism** — substrate Anthropic 측 외부 grounding 발견
- Managed Agents $0.08/h session = Bell's Law class evidence (가격 abstraction = 새 compute class 1차 marker)
- agentskills.io = 32 도구 채택 open standard (March 2026, Gemini CLI / JetBrains Junie / AWS Kiro / Block Goose)

KG: `finding-prom16-harness-C2-anthropic-skills-2026-05-10` (verdict pending OQ12)

#### C3 — Cursor 3.0 (Background Agents + Composer + Rules)
**1차 정전**: Cursor 2026 docs / blog (Background Agents Feb 2026 launch / Composer 4x faster / `.cursor/rules/*.mdc` declarative system).

**Harness 매핑** (PROGRESSIVE_EXTERNAL_GROUNDING):
- 4/5 axiom feature 직접 confirm
- **Codebase Index 5-step pipeline** (AST chunk → custom embedding → Turbopuffer vector DB → hierarchical hash tree → semantic retrieval +12.5% accuracy) = Longinus L4 + L6 production validation + **L8 SEMANTIC_VECTOR extension propose** (OQ2)
- **L_IDE.control_plane_locality** sub-axis 발견 (cloud vs local fractal Harness)
- KG-bound manifest = SYMPOSIUM 우위 over Cursor apm.yml

KG: `finding-prom16-harness-C3-cursor-2026-05-10` (PROGRESSIVE)

#### C4 — SWE-agent ACI + Aider/OpenHands/Cline (Open-Source L_IDE 4-instance)
**1차 정전**:
- Yang et al. (2024). "SWE-agent: Agent-Computer Interfaces Enable Automated Software Engineering." NeurIPS 2024 (oral). arXiv:2405.15793.
- Aider (Paul Gauthier 2024-, https://aider.chat).
- Wang et al. (2024). "OpenHands: An Open Platform for AI Software Developers as Generalist Agents." ICLR 2025. arXiv:2407.16741.
- Cline (VS Code extension, 58k stars Apache 2.0).

**ACI 4 design principles** (Yang 2024 NeurIPS): P1 Simple / P2 Compact / P3 Concise feedback / P4 Guardrails.

**Harness 매핑**: ACI 4 principles ↔ Harness 4축 (Inform/Constrain/Verify/Correct) **bijection** — Princeton academic grounding of SYMPOSIUM 4-axis model.

**Autonomy spectrum 4-instance**: Cline (LOW) → Aider (MEDIUM) → SWE-agent (HIGH) → OpenHands (FULL). L_IDE 단일 tier 의 internal subdivision = fractal Harness pattern.

KG: `finding-prom16-harness-C4-swe-aider-2026-05-10` (STRONG). Lean: `Harness_ACI_Mirror.lean` (184 lines, sha256 `0af43e04...`, 10 theorems 0 sorry).

### D. Organizational + Reflection Form (4 axes)

#### D1 — Holacracy Constitution (Robertson 2007/2015/2021)
**1차 정전**: Robertson, Brian J. (2015). *Holacracy: The New Management System for a Rapidly Changing World*. Henry Holt. + Constitution v5.0 (2021, holacracyone/Holacracy-Constitution).

**Harness 매핑** (STRONG_DIRECT_4_OF_4):
- 재배맨 v2 4-archetype (facilitator / lead_link / rep_link / secretary) ↔ Holacracy v5 4 core role (Facilitator / Circle Lead / Circle Rep / Secretary) **1:1 STRONG mirror**
- Harness 1:N family ↔ Holacracy super/sub/sibling circle hierarchy STRUCTURAL_HOMEOMORPHISM
- Lesson cycle 5-step ↔ tension processing 5-step PROCESS_ISOMORPHISM (둘 다 reject consensus AND reject single veto — HR11 anti-rubber-stamp 정전 grounding)
- Sociocracy lineage (Endenburg 1970s, Boeke 1945) deeper ancestral grounding

KG: `finding-prom16-harness-D1-holacracy-2026-05-10` (STRONG_DIRECT)

#### D2 — Sociotechnical Systems (Trist & Bamforth 1951)
**1차 정전**: Trist, E. L. & Bamforth, K. W. (1951). "Some Social and Psychological Consequences of the Longwall Method of Coal-Getting." *Human Relations* 4(1): 3-38.

**Joint optimization**: Technical Subsystem T (tools/devices/procedures) + Social Subsystem S (people/relationships/values) co-designed. Cherns 1976 "Principles of Sociotechnical Design" 9 principles canonical.

**Harness 매핑** (META_FRAME_ADEQUATE_PRIMARY):
- L_IDE/L_RT/L_MC ↔ T-subsystem (3 layer)
- 사용자/팀/조직 ↔ S-subsystem
- **MCP = Cherns P5 (Boundary Location) instance** — engineering instantiation of socio-technical boundary translator
- Mumford 1983 ETHICS + Baxter-Sommerville 2011 software domain extension chain

KG: `finding-prom16-harness-D2-sociotechnical-trist-1951-2026-05-10` (META_FRAME_ADEQUATE_PRIMARY)

#### D3 — Domain-Driven Design (Evans 2003)
**1차 정전**: Evans, Eric. (2003). *Domain-Driven Design: Tackling Complexity in the Heart of Software*. Addison-Wesley. ISBN 978-0321125217.

**Patterns**: Bounded Context / Ubiquitous Language / Context Map / Anticorruption Layer / Open Host Service / Published Language / Customer-Supplier / Conformist.

**Harness 매핑** (STRONG_INSTANCE_OF_4_OF_4 BC invariant PASS):
- L_IDE/L_RT/L_MC = 3 distinct Bounded Context (model_consistency / language_unambiguity / team_ownership / translation_required_at_boundary 4/4 PASS)
- **MCP = OpenHostService ∧ PublishedLanguage combined** (Evans 2003 explicit endorsement: "OHS frequently combined with PL")
- **HR_TierConfusion = Evans Ch.14 model splintering instance** (3 sub-types map to 3 specific Evans violations)
- responsibility_split STRONG mirror grounding — Evans BC partition-by-responsibility 정전

KG: `finding-prom16-harness-D3-ddd-evans-2003-2026-05-10` (STRONG_INSTANCE_OF)

#### D4 — Computational Reflection (Smith 1982/1984)
**1차 정전**:
- Smith, Brian Cantwell. (1982). "Reflection and Semantics in a Procedural Language." Ph.D. dissertation, MIT EECS / MIT TR-272.
- Smith, B.C. (1984). "Reflection and Semantics in Lisp." POPL 1984. doi:10.1145/800017.800513.
- Maes, Pattie. (1987). "Concepts and Experiments in Computational Reflection." OOPSLA 1987.
- Kiczales, G., des Rivières, J., Bobrow, D.G. (1991). *The Art of the Metaobject Protocol*. MIT Press.

**Reflection Hypothesis** (Smith 1982): meta-circular interpreter operates on causally-connected self-representation. **3-Lisp** infinite reflective tower with REIFY/REFLECT operators.

**Harness 매핑** (PROGRESSIVE_GROUNDING):
- meta-tier (Harness 자체) ↔ Smith L_{n+1} interpreter / object-tier (Cursor / ADK / Anthropic MA) ↔ L_n object-level program
- Harness 3-tier = Smith reflective tower의 finite truncation (L_3=managed cloud, 다른 substrate)
- **MCP = MOP** (Metaobject Protocol Kiczales-des Rivières-Bobrow 1991) — open-implementation interface
- **재배맨 SOP = causal connection mechanism** (FD3): Pre-fetch reifies seed, Dispatch reflects to subagent, Collect reifies findings, Write reflects to KG
- **4축 = Tanter 2×2 reflection taxonomy** (read/write × structural/behavioural): Inform = read+structural / Constrain = write+structural / Verify = read+behavioural / Correct = write+behavioural

KG: `finding-prom16-harness-D4-smith-reflection-1982-2026-05-10` (PROGRESSIVE_GROUNDING)

### Lakatos cumulative verdict

**PROGRESSIVE_CONFIRMED_MULTI_CANONICAL** — 16/16 axes 모두 STRONG/PROGRESSIVE. 핵심 발견:
- MCP 재분류 multi-grounding: protocol (RFC2119) NOT aspect / OHS+PL combined (Evans) / MOP (Smith) / Cherns P5 boundary translator (STS)
- Family-Relation Mirror STRONG_UNIQUE multi-canonical grounding: Conway homomorphism + STS responsibility-split + DDD partition-by-responsibility = *조건부 정리* 다중 입증
- 재배맨 substrate causal connection: Anthropic `context: fork` 외부 isomorphism + Holacracy 4-archetype 1:1 mirror + Smith reflection FD3 mechanism

# KG: 16 finding-prom16-harness-{axis}-2026-05-10 + lesson-prom16-harness-grounding-reinforcement-2026-05-10 (resolved=true) + ConsensusReport-prom16-harness-grounding-2026-05-10 (16/0/0) + 16 GROUNDS_AXIS_FOR edges + 5 NovelPattern + 12 OpenQuestion + 1 HR20 ErrorPattern + 3 LeanFormalization (711 lines, 24 theorems, 0 sorry total)

# KG: formal-grounding-harness-bhgman-2026-05-09 (신화 측 형식적 grounding 결정화 2026-05-09)
