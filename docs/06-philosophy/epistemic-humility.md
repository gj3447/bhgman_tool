# 인식론적 겸손

## 한 줄

모든 metric 은 Goodhart 측 collapse 위험. 정전 인용 + 외부 검증 없는 self-claim 거부.

---

## 도구 측 영향

ruflo 측 "84.8% SWE-Bench solve rate" 류 자기 측정은 *겸손* 의 반대 — 자기 metric 을 자기 claim 의 근거로 쓴다.

bhgman 측 도구는 다음 invariant 강제:

1. **모든 quantitative claim 측 외부 정전 인용 mandatory**
   - "X 가 좋다" 가 아니라 "X 가 [Robert Martin Package Principles] 측 CCP 를 만족"
2. **모든 self-claim 측 외부 verifier 통과 mandatory**
   - Naesengmoon LensSet adversarial gate (executor != reviewer 강제)
   - Lean 4 형식 검증 (가능 시)
3. **모든 success 측 비-자명 case 만 Lesson 으로 결정화**
   - "잘 됐다" 가 아니라 *왜* 잘 됐는지 + 외부 verdict + symmetric pair (wrongAssumption ↔ truth)
4. **모든 failure 측 RootCause 명시 + Lesson generalization**
   - rubber-stamp verdict (passed without evidence) 거부

---

## 정전 grounding

- **Goodhart 1975** — "When a measure becomes a target, it ceases to be a good measure"
- **Strathern 1997** — "Improving Ratings: Audit in the British University System" (Goodhart 통속화)
- **Popper falsifiability** — claim 은 *반증 가능* 해야 과학적
- **Hume problem of induction** — past performance 가 future 보장 아님
- **Wittgenstein TLP 7** — "Whereof one cannot speak, thereof one must be silent"
- **Münchhausen trilemma** — 근거의 무한 후퇴 한계 인정

각 정전이 bhgman 도구 측 *어떤 invariant* 로 결정화되는지는 별도 본문 (예정).

---

## 도구 사용자 측 5 행동 권고

1. **자기 framework 의 metric 측 자랑 거부** — Goodhart 위험 인정
2. **"100+ X" 류 enumeration inflation 거부** — responsibility_split 없으면 무의미
3. **외부 정전 인용 없는 claim 측 ad-hoc 의심** — Lakatos degenerating signature
4. **success bias 회피** — 잘 된 case 도 *왜* 잘 됐는지 RootCause 분석
5. **자기 framework 한계 명시** — 모든 framework 가 한계 가짐 (Gödel)

---

## 자세히는

- [self-reference-incompleteness.md](self-reference-incompleteness.md) — 한계 인정의 형식 grounding
- [../02-concepts/goodhart-safeguard.md](../02-concepts/goodhart-safeguard.md) — 안전 장치 메커니즘
- [../05-papers/goodhart-1975.md](../05-papers/goodhart-1975.md) — 원본 + Strathern 1997
- [../07-metahumotonic-trace.md](../07-metahumotonic-trace.md) — 본질 측 *왜* 겸손이 framework 의 본질인지
