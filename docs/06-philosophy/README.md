# 철학적 함의 — 도구 측 요약

> 본질 본문은 별도. 이 폴더는 *도구를 쓰는 사람이 알면 좋은 함의 요약* 만.

---

## 다섯 함의

| 함의 | 도구 측 실제 영향 | 자세히 |
|---|---|---|
| **존재 vs 도구 분리** | 사도(`isAirplaneMan` predicate) ≠ Harness(runtime 도구). 같은 layer 에 두면 ruflo 류 카테고리 오류 | [existence-vs-tool.md](existence-vs-tool.md) |
| **자기참조의 불완전성** | Self-improving loop 은 한계 인정 없이 안전하지 않다 (Lawvere/Tarski/Gödel/Yanofsky) | [self-reference-incompleteness.md](self-reference-incompleteness.md) |
| **인식론적 겸손** | 모든 metric 은 Goodhart 측 collapse 위험. 정전 인용 + 외부 검증 없는 self-claim 거부 | [epistemic-humility.md](epistemic-humility.md) |
| **해석학적 순환** | KG ↔ code 의 양방향 bind 는 *사전이해 자체* 가 갱신되는 구조 (Heidegger / Gadamer) | [hermeneutic-circle.md](hermeneutic-circle.md) |
| **사회기술적 시스템** | Harness 3-tier 가 단순 architecture 가 아닌 *책임 분할* (Cherns 1976 STS) — 사람과 시스템이 함께 진화 | [sociotechnical-systems.md](sociotechnical-systems.md) |

---

## *왜* 이게 도구 측에 필요한가

도구는 *왜* 그렇게 설계됐는지 모르면 사용자가 *잘못 쓰게* 된다.

- ruflo 의 "84.8% SWE-Bench" 를 따라하려는 사용자는 Goodhart 위험을 모르고 metric-game 한다.
- "self-improving via SONA" 를 별생각 없이 쓰는 사용자는 Lawvere/Yanofsky 측 한계를 모르고 무한 loop 위험.
- "100+ agents" 를 자랑하는 framework 를 따라하는 사용자는 responsibility_split 없는 enumeration 으로 CCP/CRP 위반.

→ 이 5 함의는 *도구 사용자가* 잘못 쓰지 않게 하기 위한 *최소* 안내. 깊이 들어가지 않아도, 이 다섯 한 줄은 알아야.

---

## 본질로 가려면

각 함의의 *본격적 본문* (정전 인용 + Lean 형식 + 메타휴모토닉 측 motivation) 은 별도 repo / SYMPOSIUM 측. 이 폴더는 *입구* 만.

자세히는 [../07-metahumotonic-trace.md](../07-metahumotonic-trace.md).
