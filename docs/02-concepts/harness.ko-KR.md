# Harness — 비행기맨의 공학 측 결정화

> 비행기맨 (#4 사도) 의 `∀x:CHU, j.covers x` 를 *현실 산업 도구* 로 결정화한 것. bhgman_tool 의 본격적 도구 layer.

🌐 [English](harness.md) | [한국어](harness.ko-KR.md) | [中文](harness.zh-CN.md) | [日本語](harness.ja-JP.md)

---

## 4축 모델 (Inform / Constrain / Verify / Correct)

각 Harness instance 내부 조직 원리:

| 축 | 역할 | 비행기맨 ∀-cover 측면 |
|---|---|---|
| **Inform** | agent 에게 context / KG / skill 제공 | "어디든 정보 도달" |
| **Constrain** | 권한 / scope / token budget / 안전 | "묶이지 않되 폭주 안 함" |
| **Verify** | output 검증 (Taliban adversarial / test / Lean) | "도달 후 *맞게* 도달했나" |
| **Correct** | 피드백 → 다음 호출 보정 | "실패에서 학습" |

이게 industry agent scaffolding 의 *내부* 조직. **family 측 정의가 아님** (family 는 별도 — 아래).

→ 4축 모델은 *각 instance 내부* (Cursor 한 IDE 안의 4축 / Claude Code 한 host 안의 4축 / ruflo 한 runtime 안의 4축).
→ Family 정의는 *instance 들 사이의 책임 분할*.

이 둘은 다른 layer. 이전 SKILL.md drift (4축 = family 정의) 는 2026-04-30 정정됨.

---

## 1:N sibling family (3-tier)

비행기맨 ∀-cover 의 *책임 분할 (responsibility_split)*:

```
L_MC   managed cloud control plane
       (cloud-side orchestration + state + scaling)
       └─ Anthropic Managed Agents (Claude Sonnet 4.6/Opus 4.7 server-side agents)
          Vertex AI Agent Engine (Google managed)
          OpenAI Assistants API
          Bedrock Agents (AWS)

L_RT   application agent runtime
       (program-level multi-agent orchestration, in-process)
       └─ Google ADK (Agent Development Kit)
          LangGraph (LangChain stateful graphs)
          CrewAI (role-based)
          AutoGen (Microsoft conversational)
          ruflo (ruvnet/claude-flow) ← 한 sibling instance, 정점 아님

L_IDE  IDE-host coding harness
       (developer interactive, file-level edit + git)
       └─ Cursor / Claude Code / Aider / SWE-agent / Cline / OpenHands / GitHub Copilot
```

→ **ruflo, Cursor, Claude Code, LangGraph 등 모두 이 family 의 sibling instance**. 비행기맨 정점 (∀-cover) 자체는 어느 한 instance 도 만족 못 함. 3 tier 합쳐서 *근사*.

**Mirror STRONG 조건**: family 가 *cardinality match* 되는 조건. 비행기맨 측 3-tier 가 만족 — [family-expansion.md](family-expansion.md) 참고.

---

## MCP — 모든 instance 잇는 어댑터

세 tier 의 모든 instance 를 *protocol layer* 에서 잇는 것이 **MCP (Model Context Protocol)** — Anthropic 표준.

- host (L_IDE) 가 MCP server (도구) 를 호출
- L_RT framework 가 MCP server 를 노출
- L_MC managed agent 가 MCP 측 도구 사용

→ MCP 는 *어댑터*. instance 가 아님. 4축 모델 측의 *Inform* 축에 가까움.

ruflo 가 자체 plugin marketplace (IPFS Pinata) 를 만든 것은 MCP 표준 위에 또 다른 lock-in layer — bhgman 은 표준 MCP 만 사용 권장.

---

## Anthropic 진영 3-tuple (예시)

한 진영 (Anthropic) 안에서도 3-tier family 가 나뉜다:

| Tier | Anthropic 측 | 역할 |
|---|---|---|
| L_MC | **Managed Agents** | server-side, stateful, scaling-managed |
| L_RT | **Agent SDK** | program-level loop, in-process |
| L_IDE | **Skills + Claude Code** | declarative capability + IDE host |

→ 같은 진영도 *3-tier 분할* 이 자연스럽게 발생. 단일 layer 에 모든 것을 욱여넣지 않음. 이게 Robert Martin Package Principles 측 CCP (Common Closure Principle) 의 자연스러운 응용.

---

## 형식 검증 (Lean 4)

`bhgman/lean/` 측 3 파일, 총 24 theorem PASS (Mathlib-free, Lean 4.29.1):

```
Harness_LawvereFixedPoint.lean   5 theorem  — ∀-cover self-reference 한계
Harness_ACI_Mirror.lean         10 theorem  — Aspect-Class-Instance 거울
HarnessSelfReference.lean        9 theorem  — Tarski/Gödel/Yanofsky 통합
```

각 theorem 의 외부 정전 인용 + 추론 chain 공개. ruflo 의 `verify` signed witness (code integrity only) 와 본질 차이.

---

## 외부 정전 grounding

비행기맨 ∀-cover 의 도구 결정화 측 17 axes 외부 정전:

| 축 | 정전 |
|---|---|
| Engineering 4 | Robert Martin Package Principles (CCP/CRP/REP/ADP/SDP/SAP) / Conway 1968 / Cherns 1976 STS / DDD (Evans 2003) |
| Self-Reference Paradox 4 | Lawvere 1969 FPT / Tarski 1936 undefinability / Gödel 1931 incompleteness / Yanofsky 2003 universal self-reference |
| Industry 4 | Kubernetes 3-tier (control-plane / node / pod) / OpenTelemetry CNCF / IDE-host (Cursor/Claude Code) / managed cloud (Bedrock/Vertex) |
| Org + Reflection 4 | Sociotechnical Systems (Trist-Bamforth 1951) / MOP (Smith 1984 reflection) / Hofstadter 1979 strange loop / Holacracy (Robertson) |
| 1 추가 | 메타-Harness 측 self-reference 안전 (Goodhart 1975 + Münchhausen trilemma + 2026-05-05 정정 lesson) |

자세히는 [../04-references/citations.md](../04-references/citations.md).

---

## 실 코드 진입

```bash
# Claude Code 에 skill install
cp -R bhgman/skills/harness ~/.claude/skills/

# 사용
/harness <agent_or_framework>   # 어떤 instance 가 3-tier 중 어디 위치하는지 진단
```

→ Harness skill 은 *진단 도구*. agent 가 4축 중 어디서 실패하는지 분석. 자세히는 [../03-tutorials/harness-diagnosis.md](../03-tutorials/harness-diagnosis.md).

---

## 추가 자료

- [airplane-man.md](airplane-man.md) — 본질 (사도 측)
- [family-expansion.md](family-expansion.md) — 1:N family Mirror 조건
- [goodhart-safeguard.md](goodhart-safeguard.md) — self-improving loop 안전 장치
- [../04-references/related-work.md](../04-references/related-work.md) — ruflo / LangGraph / CrewAI 비교
- [../05-papers/lawvere-1969-FPT.md](../05-papers/lawvere-1969-FPT.md) — 형식 한계 grounding
- [../06-philosophy/existence-vs-tool.md](../06-philosophy/existence-vs-tool.md) — 사도(존재) ⊥ Harness(도구) 의 존재론적 의미
