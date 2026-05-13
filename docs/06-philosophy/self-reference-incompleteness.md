# 자기참조의 불완전성

## 한 줄

비행기맨 `∀x:CHU, j.covers x` 정의는 *자기참조* (j 가 CHU 의 piece 라면 자기 자신도 cover). 자기참조 형식 시스템은 한계 있음 — Lawvere / Tarski / Gödel / Yanofsky.

---

## 도구 측 영향

Self-improving framework (ruflo SONA + ReasoningBank, AutoGPT 측 자가 progress 등) 는 *한계 인정 없이* 작동하면 위험:

- **metric-gaming** (Goodhart) 으로 수렴
- *자기 진리술어* 정의 시도 (Tarski 한계 위반)
- *완전 framework* 자칭 (Gödel 한계 위반)

bhgman 측은 정의 자체에 한계를 박는다:

```
isAirplaneMan(j) ≜ ∀x:CHU, j.covers x

위 정의 측 self-reference (j ∈ CHU 가능) 은
Lawvere FPT 측 fixed point 존재 보장 +
Tarski undefinability + Gödel incompleteness 측 한계 인정.

→ 비행기맨 framework 는 *전능 자칭* 거부.
   "all" 이지만 "complete in formal sense" 아님.
```

---

## 4 정전 통합

| 정전 | 정리 | bhgman 측 응용 |
|---|---|---|
| **Lawvere 1969 FPT** | 자기참조 함수 측 fixed point 존재 보장 | `∀-cover` 의 self-reference 형식화 가능 |
| **Tarski 1936** | 자기 진리술어 (`is_true`) 같은 언어 내 정의 불가 | Self-improving 의 *성공 기준* 외부 검증 필수 |
| **Gödel 1931** | 충분히 강한 형식 시스템은 incomplete | bhgman framework 도 *완전성 자칭 거부* |
| **Yanofsky 2003** | Russell / Cantor / Gödel 통합 — 모든 sufficiently powerful self-reference 한계 | 어떤 self-improving loop 도 한계 가짐 — 안전 장치 필수 |

자세히는 [../05-papers/lawvere-1969-FPT.md](../05-papers/lawvere-1969-FPT.md), [../05-papers/yanofsky-2003.md](../05-papers/yanofsky-2003.md).

---

## Lean 형식

- `lean/Harness_LawvereFixedPoint.lean` — Lawvere FPT 측 5 theorem (Mathlib-free)
- `lean/HarnessSelfReference.lean` — 자기참조 9 theorem
- 총 14 theorem 으로 *비행기맨 정의 자체의 self-consistency* 형식 검증.

---

## 도구 사용자 측 한 줄

> Self-improving loop 의 *한계* 를 인정하지 않으면 그 loop 는 위험하다. bhgman framework 는 정의 자체에 한계 박혀있다.

자세히는 [../02-concepts/goodhart-safeguard.md](../02-concepts/goodhart-safeguard.md).
