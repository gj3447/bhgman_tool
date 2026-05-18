# 해석학적 순환

## 한 줄

KG ↔ code 의 양방향 binding 은 *사전이해 자체* 가 갱신되는 구조 — Heidegger / Gadamer.

---

## 도구 측 영향

Longinus 7-Layer Reference Model 측 *bidirectional binding* (KG ↔ source code) 는 한 번 박고 끝이 아니다. drift 가 발생하면 *KG 측* 도 *code 측* 도 둘 다 진화한다. 이게 해석학적 순환 (hermeneutische Zirkel) 의 framework 구현.

```
사전이해 (KG 측 lesson / Contract)
    ↓
구체 해석 (코드 작성 + ReferenceSite 박기)
    ↓
새 발견 (drift / Goodhart 위험 / Mirror 조건 위반)
    ↓
사전이해 갱신 (KG 측 lesson update / Pattern 정전 격상)
    ↺  (다시 위로)
```

→ 이건 *bug* 가 아닌 *feature*. 사전이해와 해석이 *상호 변형* 되는 게 framework 의 본질.

---

## ruflo 측 대조

ruflo 측 SONA "self-learning" + ReasoningBank 도 *학습* 한다. 하지만:

| | ruflo SONA | bhgman 해석학적 순환 |
|---|---|---|
| 학습 대상 | metric optimization (성공 패턴 store) | 사전이해 (KG :Lesson, Contract) |
| 학습 방향 | scalar metric 측 converge | symmetric pair (`wrongAssumption ↔ truth`) 양쪽 갱신 |
| 외부 검증 | 자체 ReasoningBank | Naesengmoon adversarial + Lean 형식 |
| 해석학적 순환 | 부재 (one-way 측 metric optimize) | 명시적 (사전이해 ↔ 해석 양방향) |

---

## 정전 grounding

- **Heidegger 1927 Sein und Zeit §32** — Vorhabe / Vorsicht / Vorgriff (사전소유 / 사전시점 / 사전이해)
- **Gadamer 1960 Wahrheit und Methode** — fusion of horizons (Horizontverschmelzung)
- **Schleiermacher** — 부분 ↔ 전체 순환
- **Dilthey** — Geisteswissenschaften 측 해석학적 방법론
- **BX Lens** (Foster-Pierce-Walker 2007) — bidirectional transformation 형식

Longinus 7-Layer 측 BX Lens Laws (GetPut/PutGet/PutPut) 가 해석학적 순환의 *형식 등가물*. KG 측 사전이해 = state, code 측 작성 = view. Lens 가 둘을 *consistent* 하게 양방향 유지.

---

## 도구 측 실 적용

1. **Drift detection daemon** (Longinus, [../03-tutorials/longinus-drift-audit.md](../03-tutorials/longinus-drift-audit.md))
   - KG ref ↔ code 불일치 자동 감지
   - drift 발견 시 *둘 다* 갱신 옵션 제공

2. **APT meta-review phase** ([../02-concepts/apt-tpa-cycles.md](../02-concepts/apt-tpa-cycles.md))
   - 의심/피드백 → 사전이해 갱신
   - SKILL.md 패치 + MATERIALIZES 갱신

3. **Confidence schema** (EXTRACTED / INFERRED / AMBIGUOUS)
   - AMBIGUOUS 측 human review trigger
   - 해석학적 순환의 *명시적 entry point*

---

## 자세히는

- [../02-concepts/harness.md](../02-concepts/harness.md) §4-axis Correct
- [../05-papers/foster-pierce-walker-2007-bx-lens.md](../05-papers/foster-pierce-walker-2007-bx-lens.md) — BX Lens 형식
- [../03-tutorials/longinus-drift-audit.md](../03-tutorials/longinus-drift-audit.md) — 실 코드 실행
