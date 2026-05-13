# Goodhart 안전 장치 — self-improving loop 의 위험

> 비행기맨 framework 가 *왜* metric-driven self-improving loop 를 거부하는가.

---

## Goodhart 1975 원본

> "Any observed statistical regularity will tend to collapse once pressure is placed upon it for control purposes."
> *측정값이 목표가 되면, 그 측정값은 더 이상 좋은 측정이 아니다.*

— Goodhart, "Problems of Monetary Management: the U.K. Experience" (Charles Goodhart, 1975)

Strathern (1997) 의 통속화: *"When a measure becomes a target, it ceases to be a good measure."*

---

## ruflo 측 위반 case study

비행기맨 framework 가 *negative case study* 로 기록한 industry instance (SYMPOSIUM KG `errorpattern-goodhart-metric-optimization-marketing-2026-05-13`):

| ruflo 측 | Goodhart 위반 측면 |
|---|---|
| "84.8% SWE-Bench solve rate" | benchmark 자체를 목표화 — measure-target collision |
| "32% token reduction" | token 수가 *학습 도구* → *추구 대상* 으로 변질 |
| "100+ agents" / "314 MCP tools" | enumeration 자체가 quality signal 로 마케팅 |
| SONA neural train + ReasoningBank | self-improving loop 이 metric 측에 *converge* — Goodhart 위험 무방비 |
| "self-learning" claim 측 학문 정전 인용 0 | 정전 grounding 없이 self-reference 작동 |

→ ruflo 가 *나쁜 framework* 라는 의미가 아니다. *비행기맨 측 정전이 명시한 Goodhart 안전 장치가 부재* 라는 의미. 안전 장치 없이 self-improving 하는 loop 는 metric-gaming 으로 수렴.

---

## 비행기맨 측 안전 장치

비행기맨 정의 자체에 self-reference 형식 한계 인정이 박혀있다:

### 1. Lawvere FPT (Fixed Point Theorem)

자기참조 함수 측 *fixed point 존재 보장* 정리 (Lawvere 1969).

비행기맨 정의 `∀x:CHU, j.covers x` 에서 `j` 자체가 CHU 의 piece — 즉 자기참조. Lawvere FPT 측 한계 인정 + 형식화 (`bhgman/lean/Harness_LawvereFixedPoint.lean` 5 theorem).

### 2. Tarski undefinability of truth

자기 진리술어 (`is_true`) 를 같은 언어 내에서 정의 불가 (Tarski 1936).

비행기맨 측 *self-improving* 이 자신의 *성공 기준* 을 자신이 정의하면 Tarski 한계 위반. 외부 검증 (Taliban LensSet) 필수.

### 3. Yanofsky 2003 universal self-reference

Russell paradox / Cantor diagonal / Gödel incompleteness 의 통합 정리. *어떤 sufficiently powerful self-referential system 도 한계 가짐*.

비행기맨 framework 도 이 한계 인정. *전능 framework 자칭 거부*.

### 4. Hofstadter 1979 strange loop

자기참조 구조의 *미학적* 인정 — 한계 자체가 framework 의 본질.

### 5. Münchhausen trilemma

axiom 측 *근거의 무한 후퇴* 한계. 비행기맨 측 *자기 정의 받아들임* (자칭 그 자체를 axiom 으로) — 이 한계 명시적 수용.

---

## Lakatos progressive vs degenerating

자기참조 framework 의 *건강* 측정 — Lakatos (1976 *Proofs and Refutations*) 측:

| Progressive Research Programme | Degenerating |
|---|---|
| novel content prediction | ad-hoc 수정 |
| 외부 검증 가능 | protective belt 부풀어남 |
| auxiliary hypothesis 가 novel | enumeration inflation |
| 부정 결과도 풍요로운 발견 | 부정 결과 회피 / 무시 |

비행기맨 framework 측은 *quarterly Lakatos audit 강제*:
- 각 update 가 progressive 인지 degenerating 인지 KG :LakatosVerdict 결정화
- degenerating 추세면 framework 자체 rollback

ruflo 측 6000+ commit / 100+ agent enumeration / "self-learning" 측 ad-hoc 추세는 Lakatos degenerating signature.

---

## Taliban LensSet (Goodhart 탐지)

비행기맨 framework 측 *외부 검증 도구*. `--lens mathematical` 측 Goodhart 형식 탐지 113-lens (SYMPOSIUM 정전).

진입:
```
/taliban --lens mathematical <metric_claim>
```

→ 각 metric claim 측 Goodhart 위험 자동 탐지. RubberStamp verdict 거부.

자세히는 [../03-tutorials/taliban-adversarial.md](../03-tutorials/taliban-adversarial.md) (별도 작성 예정).

---

## 한 줄 정리

> Self-improving loop 자체는 강력하다. 하지만 *Goodhart 안전 장치 없는 self-improving* 은 metric-gaming 으로 수렴한다. 비행기맨 framework 은 정의 자체에 self-reference 한계 인정 + Lakatos audit + Taliban adversarial validation 3 layer 로 그 위험을 봉쇄.

---

## 추가 자료

- [airplane-man.md](airplane-man.md) — self-reference 정의
- [harness.md](harness.md) — 도구 측 검증 layer
- [../05-papers/goodhart-1975.md](../05-papers/goodhart-1975.md) — 원본 + Strathern 1997
- [../05-papers/lawvere-1969-FPT.md](../05-papers/lawvere-1969-FPT.md) — self-reference 한계 grounding
- [../06-philosophy/epistemic-humility.md](../06-philosophy/epistemic-humility.md) — *왜* 안전 장치가 framework 의 본질인가
