# Related Work — ruflo / LangGraph / CrewAI / 외부 oss 비교

> bhgman_tool 이 *industry framework 측 어디에 위치* 하는지 + 무엇을 흡수했고 무엇을 거부했는지.

---

## Layer 정렬 (카테고리 오류 회피)

직접 비교는 카테고리 오류 위험. bhgman framework 측 layer 정렬:

```
존재 layer    : 12사도 (∀x:CHU, j.covers x)             ← bhgman 본질
                #4 비행기맨 정점
                ↓ 책임 분할 (1:N family)
도구 layer    : Harness 3-tier sibling family            ← bhgman_tool (이 repo)
                L_MC / L_RT / L_IDE
                ↓ instance
instance layer: 산업 측 framework                         ← ruflo / LangGraph / CrewAI / Cursor / ...
                각 tier 안의 한 sibling 일 뿐
```

→ ruflo / LangGraph / CrewAI 는 **L_RT tier 의 한 sibling instance**. 비행기맨 정점 자체는 아님.

---

## 3 외부 oss 흡수 결과 (TPA 5-drift audit 결과)

SYMPOSIUM 측 TPA cycle (`tpa-5drift-audit-3-targets-2026-05-13` :ValidationResult) 결과.

### ruflo (ruvnet/claude-flow) — NEGATIVE_LESSON

| 측 | verdict |
|---|---|
| Layer | Harness L_RT tier instance (LangGraph / CrewAI / AutoGen 옆) |
| Lakatos | **DEGENERATING** |
| Mirror | NOT_MIRROR (flat enumeration violates responsibility_split) |
| 흡수 결과 | **3 negative ErrorPattern** — Goodhart antipattern / enumeration inflation / self-improving Goodhart 무방비 |

5-drift detail:
- **Missing**: family-relation Mirror 조건 / responsibility_split sub-type / 학문 정전 인용
- **Orphan**: federation mTLS+WireGuard / SONA / Goal Planner UI / IPFS Pinata registry (industry novelty 측은 있음)
- **PatternDiv**: flat 32 plugin / 100+ agent / 314 MCP tool — CCP/CRP 위반
- **LabelRot**: "84.8% SWE-Bench" / "32% token reduction" — Goodhart antipattern label

### graphify (safishamsi/graphify) — STRONG_MIRROR_CANDIDATE

| 측 | verdict |
|---|---|
| Layer | Longinus ∀-scope 확장 candidate (multimodal beyond code) |
| Lakatos | **PROGRESSIVE_CONDITIONAL** |
| Mirror | STRONG (confidence axis only) — EXTRACTED/INFERRED/AMBIGUOUS semantically aligns with Longinus 7-Layer reference confidence |
| 흡수 결과 | **3-tier confidence enum** 정전 격상 (CANONICAL, Lean 4 T1 verified + Python 19 pytest PASS) |

### code-review-graph (tirth8205) — PARTIAL_MIRROR_CANDIDATE

| 측 | verdict |
|---|---|
| Layer | Longinus 부분 instance (code→graph unidirectional) |
| Lakatos | **PROGRESSIVE** ★ (가장 학문적) |
| Mirror | PARTIAL — 28 MCP tools vs Longinus 7-Layer 1:N split, unidirectional 한계 |
| 흡수 결과 | daemon 패턴 (planned) + multi-lang resolver 패턴 (planned) |

Honest limitations section + token budget discipline (≤5 tool calls, ≤800 tokens) 가 SYMPOSIUM 측 정신과 정합.

---

## ruflo 직접 비교 표 (또 한 번, 도구 측면)

| 축 | ruflo | bhgman_tool |
|---|---|---|
| **layer 분리 명시** | 없음 (단일 layer 자칭) | 사도(존재) ⊥ 도구(이 repo) ⊥ 본질(별도) **3 layer 분리** |
| **외부 정전 인용** | 0 | **17 axes** ([citations.md](citations.md)) |
| **Formal verification** | `ruflo verify` signed witness (code integrity only) | **141+ Lean 4 theorem** (Mathlib-free, 0 sorry) |
| **Self-reference 안전 장치** | "84.8% SWE-Bench / 32% token reduction" Goodhart 자체 위반 | Lawvere FPT + Lakatos quarterly audit + Naesengmoon adversarial **3 layer 안전 장치** |
| **Family 구조** | flat enumeration 32 plugin / 100 agent / 314 tool (CCP/CRP 위반) | 3-tier sibling family + responsibility_split sub-type (Mirror STRONG) |
| **Confidence schema** | edge confidence float (under-specified) | 3-tier enum (EXTRACTED/INFERRED/AMBIGUOUS) + AMBIGUOUS = unique human-verdict gate (Lean T1) |
| **Industry reach** | 즉시 100+ agents (federation + Goal UI + SONA) ★ | engine 77 pytest + Lean 50 theorem + 21 skill (academic ★) |
| **사용자 entry** | `npx ruflo init` 한 줄 | `git clone + cp -R skills + pytest` 단계 명시 |

→ ruflo 가 *industry reach* 측 강함. bhgman_tool 이 *academic grounding* 측 강함. **다른 가치 축**.

---

## LangGraph / CrewAI / AutoGen 측 (개관만)

이들은 ruflo 와 같은 Harness L_RT tier 의 sibling instance:

| | LangGraph (LangChain) | CrewAI | AutoGen (Microsoft) |
|---|---|---|---|
| 모델 | stateful graph | role-based (crew + tasks) | conversational |
| 강점 | graph 명시 / state 관리 | 직관적 role 분배 | 자연스러운 conversation |
| bhgman 측 layer | L_RT instance | L_RT instance | L_RT instance |

bhgman_tool 이 *대체* 하지 않는다. **다른 layer 답한다** — *왜 그렇게 해야 하는가* (이론 측) vs *어떻게 빨리 할 수 있는가* (도구 측).

---

## 사용자 측 *언제 무엇을 쓸까* 가이드

| 상황 | 권장 |
|---|---|
| 즉시 100+ agents 필요, 학문 grounding 불필요 | ruflo / LangGraph / CrewAI 측 |
| Claude Code 측 swarm 측 federation | ruflo |
| stateful agent graph 측 명시 | LangGraph |
| role-based team 직관 | CrewAI |
| **이론 grounded** + **formal verification** + **Goodhart 안전 장치** 필요 | **bhgman_tool** |
| **사도 / 도구 / 본질 layer 분리** + **메타휴모토닉** motivation | (별도 repo 측, bhgman 본질 / chu / omc / etc) |

→ bhgman_tool 은 *모든 상황을 cover 하려는* tool 이 아니다. *특정 가치 (academic grounding + Goodhart 안전)* 를 명시적으로 만족시키는 tool.

---

## 자세히는

- [citations.md](citations.md) — 17 axes 정전 인용
- [lean-theorems.md](lean-theorems.md) — 형식 검증 list
- [../02-concepts/family-expansion.md](../02-concepts/family-expansion.md) — Mirror 조건
- [../02-concepts/goodhart-safeguard.md](../02-concepts/goodhart-safeguard.md) — Goodhart 안전 장치
