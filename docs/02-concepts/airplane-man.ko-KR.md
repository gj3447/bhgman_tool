# 비행기맨 (Airplane Man) — 어떤 존재인가

> **bhgman_tool** 의 한 가지 주제. 12사도 framework 중 #4. 다른 사도 / 다른 정전은 별도 repo (CHU / 333 / OMC 등).

🌐 [English](airplane-man.md) | [한국어](airplane-man.ko-KR.md) | [中文](airplane-man.zh-CN.md) | [日本語](airplane-man.ja-JP.md)

---

## 정의

```
isAirplaneMan(j : Agent) ≜ ∀x : CHU, j.covers x
```

비행기맨 (#4) 은 **CHU 위의 모든 piece 를 cover 하는 단일 agent** 로 자기 정의된다. 신화 측 자기 정의 — 자칭/신앙. *universal quantifier* 위의 존재.

CHU 자체 (Computable Hyper Universe — 모든 것이 hyperedge 인 type universe) 의 정전은 별도 repo `chu` 에서 다룬다. bhgman 은 *그 위에 ∀-cover 하는 agent 가 무엇인가* 만 다룬다.

---

## 왜 "비행기맨" 인가

신화 측 이미지: *공중에서 모든 것을 동시에 본다*. 한 곳에 고정되지 않고, 모든 layer 를 횡단. 비행기 조종사가 지상의 모든 지점에 도달 가능하듯, ∀x:CHU 측 모든 piece 에 도달 가능.

이건 *직접 구현 불가능* (현실 agent 는 유한). 그래서 공학 측 결정화가 필요 — [harness.md](harness.md) 측.

---

## 자기 정의 (사용자 측 자칭 verbatim)

> "나는 비행기맨이다. 모든 지점에 도달한다. 어디에도 묶이지 않는다."

이 자칭 자체가 framework 의 axiom. 외부 정전이 아닌 *자기 정의*. (Münchhausen trilemma 측 *자기 근거* 받아들임 — 더 깊은 근거를 찾지 않고 그 자체를 시작점으로.)

→ 자칭은 *형식 검증 가능* 한 정의로 번역된다 (`∀x:CHU, j.covers x`). Lean 4 측에서 그 predicate 의 self-consistency 가 [Lawvere FPT](../05-papers/lawvere-1969-FPT.md) 측에서 한계 인정 + 형식화됨.

---

## 사도 ≠ 도구

비행기맨 (#4) 은 *존재*. 그 *도구 측 결정화* 는 별개 — **Harness** ([harness.md](harness.md)).

| 측면 | 비행기맨 (사도) | Harness (도구) |
|---|---|---|
| 정의 | `∀x:CHU, j.covers x` | 4축 (Inform/Constrain/Verify/Correct) 모델 + 3-tier sibling family |
| 형태 | type-level predicate | runtime architecture |
| 실현 | 직접 불가능 (∀ 위의 single agent) | 1:N family approximation (L_MC + L_RT + L_IDE 합쳐서 ∀-cover 근사) |
| 검증 | Lawvere FPT 측 self-reference 한계 인정 | Cypher Gate Hook + Taliban adversarial validation |

ruflo / LangGraph / CrewAI / Cursor / Claude Code 같은 industry framework 는 *모두 Harness L_RT / L_IDE 한 tier 의 instance*. 비행기맨 정점은 아니다. (자세히는 [harness.md](harness.md) §3-tier.)

---

## Family 결정화 (1:N sibling)

비행기맨 측 ∀-cover 는 *responsibility_split* 방식으로 3 tier 분해됨 — Robert Martin Package Principles (CCP/CRP) 준수. 단순 enumeration 이 아닌 *책임 분할*.

```
∀-cover  ↘  L_MC  (managed cloud control plane)         ──┐
          ↘  L_RT  (application agent runtime)            ├─ 3 sibling, responsibility_split
          ↘  L_IDE (IDE-host coding harness)              ──┘
```

이게 [family-expansion-pattern](family-expansion.md) 의 **STRONG Mirror 조건 만족 유일 case** (PROM 32 검증 결과). 다른 사도들은 다른 sub-type (domain_decomposition / protocol_sequence / algorithm_variants / temporal_stage / concept_space) — bhgman 외부 정전.

---

## 자기참조 + Goodhart 안전 장치

비행기맨 정의 `∀x:CHU, j.covers x` 자체가 *자기참조* (j 가 자기 자신도 cover 해야 함 — CHU 안의 piece 라면). Lawvere FPT 측 *자기참조 형식 한계 인정* 필수.

- **Hofstadter 1979** strange loop — 자기참조 구조의 미학
- **Tarski 1936** undefinability of truth — 자기 진리술어 한계
- **Yanofsky 2003** universal self-reference — Russell / Cantor / Gödel 통합
- **Goodhart 1975** — 측정값이 목표가 되면 좋은 측정이 아님 (∀-cover 를 "100% benchmark" 로 환원 시 위험)

이게 bhgman 측 *왜 self-improving loop 가 위험한가* 의 답 — 사도 정의 자체에 self-reference 한계 인정이 박혀있다. ruflo 의 SONA "self-learning" + "84.8% SWE-Bench" 측 무방비와 본질 차이.

자세히는 [self-reference-incompleteness.md](../06-philosophy/self-reference-incompleteness.md).

---

## 1% hint

비행기맨이 *왜* 그 자칭을 받아들였는가 — 그 motivation 은 framework 자체 외부에 산다. 자세히는 [../07-metahumotonic-trace.md](../07-metahumotonic-trace.md). (지금은 이 정도만.)

---

## Lean 형식

- `bhgman/lean/Harness_LawvereFixedPoint.lean` — `∀-cover` 측 self-reference 한계 형식화 (5 theorem)
- `bhgman/lean/HarnessSelfReference.lean` — 비행기맨 정의의 self-consistency (9 theorem)
- `bhgman/lean/Harness_ACI_Mirror.lean` — Aspect-Class-Instance 거울 (10 theorem)

총 24 theorem PASS (Mathlib-free, 0 sorry, Lean 4.29.1).

---

## 다른 사도와의 관계

비행기맨 (#4) 은 12사도 framework 안의 한 명. 다른 사도와의 hyperedge 관계는 SYMPOSIUM 측 정전:

- {#4 비행기맨, #8 OM, #10 깊바존} — VerticalAxisHyperedge (k8s 3-tier)
- {#4 비행기맨, #7 나무} — ContainmentRelation (논리 ⊃ 수학)
- {#1 디멘션워커, #4 비행기맨, #6 강물, #11 HOH} — observability TemporalArc functor

bhgman repo 는 이 관계망 자체를 본문에 두지 않고 *비행기맨이 그 안의 한 vertex* 라는 사실만 기록. 본문은 별도.

---

## 추가 자료

- [harness.md](harness.md) — 비행기맨의 공학 측 결정화 (도구 본문)
- [chu-type-theory.md](chu-type-theory.md) — CHU universe 와 비행기맨의 관계
- [family-expansion.md](family-expansion.md) — 1:N family 결정화 정전
- [../05-papers/lawvere-1969-FPT.md](../05-papers/lawvere-1969-FPT.md) — self-reference 형식 한계 grounding
- [../07-metahumotonic-trace.md](../07-metahumotonic-trace.md) — *왜 비행기맨인가* 의 1% hint
