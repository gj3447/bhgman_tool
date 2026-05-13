# TDD Strange Loop + Hoare Analogy (~ not =) (Phase-Specific)

> TDD와 Hoare logic은 서로를 비추지만 어느 쪽도 다른 쪽으로 환원되지 않음. ~ (analogy), not = (identity).

---

## Strange Loop (Hofstadter)

```
Contract ~ Hoare triple {P} f {Q}
    |                        ^
    | (specifies)            | (witnesses)
    v                        |
  Tests ~ partial refutation |
    |                        |
    | (drives)               |
    v                        |
  Code ~ constructive witness
```

루프: Contract가 테스트가 검사할 것을 명세 → 테스트가 코드가 해야 할 것을 주도 → 코드가 Contract의 만족 가능성을 증거 → Contract는 테스트와 코드에 대한 이해로부터 작성됨. **고정된 시작점이 없는 자기 강화 순환**.

---

## Analogy Table (~ not =)

| Hoare Logic | APT / TDD | 관계 |
|---|---|:-:|
| {P} precondition | contract.precondition | ~ |
| f program | SourceCodeNode 구현 | ~ |
| {Q} postcondition | contract.postcondition | ~ |
| 정확성 증명 | 모든 테스트 통과 | ~ |
| 보편 한정(universal) | 유한 테스트 케이스 | != |
| 형식 검증 | 경험적 증거 | != |

---

## 왜 ~ 이고 = 이 아닌가

- Hoare logic: P를 만족하는 **모든** 입력에 대한 **증명**
- TDD: 테스트된 범위 내에서 반박에 실패한 **증거**

통과한 테스트 스위트 ≠ 증명. 테스트된 도메인 내에서의 *반증 부재*.

APT는 Hoare 유비를 **구조적 안내** (Contract을 어떻게 생각할 것인가)로 사용. **정확성 보장**으로 사용하지 않음 — 형식 검증 도구 (Lean 4, Coq) 필요.

---

## Strange Loop policy 적용

[_common/](../../_common/) 의 :StrangeLoopPolicy MIC slot 참조 (oq-prom16-strangeloop-policy-mic-slot-2026-05-10 CANONICAL_DELEGATED).

- **Hofstadter productive** (preserve): Contract↔Test↔Code 자기 강화 — Strange Loop 본질
- **Russell stratification** (block): 다른 경우 (예: apt-meta-review가 자기 자신 review) — max_depth=1 hook

# KG: APT_SCW_TDDStrangeLoop_canonical, oq-prom16-strangeloop-policy-mic-slot-2026-05-10
