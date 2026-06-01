# bhgman_tool docs

> **비행기맨 (#4 사도) 의 *공학적 결정화 (Harness)* 도구 모음.**
> 본 repo = **도구 layer**. *비행기맨 본질 + 12사도 framework + 메타휴모토닉* 은 별도 (예정 repo / SYMPOSIUM 측).

---

## 어디서 시작하지?

| 처음? | 가야 할 곳 |
|---|---|
| **즉시 사용** 하고 싶다 | [01-quickstart.md](01-quickstart.md) |
| **비행기맨이 어떤 존재인가** | [02-concepts/airplane-man.md](02-concepts/airplane-man.md) |
| **Harness 도구 측** | [02-concepts/harness.md](02-concepts/harness.md) |
| **CHU 와 관계** (짧음) | [02-concepts/chu-type-theory.md](02-concepts/chu-type-theory.md) |
| **family 결정화** | [02-concepts/family-expansion.md](02-concepts/family-expansion.md) |
| **Goodhart 안전 장치** | [02-concepts/goodhart-safeguard.md](02-concepts/goodhart-safeguard.md) |
| **외부 정전 인용** | [04-references/citations.md](04-references/citations.md) |
| **ruflo / LangGraph / CrewAI 와 비교** | [04-references/related-work.md](04-references/related-work.md) |
| **논문 요약** | [05-papers/](05-papers/) |
| **철학적 함의** | [06-philosophy/](06-philosophy/) |
| **본질 / 메타휴모토닉 hint** | [07-metahumotonic-trace.md](07-metahumotonic-trace.md) |

---

## 한 줄 정의

```
bhgman (본질, 별도)          : 비행기맨 (#4 사도, ∀x:CHU, j.covers x)
                                 ↓ 결정화
bhgman_tool (이 repo)         : Harness 도구 + 사용자 가용
                                 ↓ 외부 layer
SYMPOSIUM (정전 본문)         : 12사도 framework / 5무기 / APT-TPA cycle / 메타휴모토닉

본 repo 측 산출물:
  Lean 4 verified theorem      : 89 standalone (Harness 24 + Longinus 21 + Measurement 26 + Occam 10 + Seed 8); tree 105
  Python runtime               : engine/longinus_drift_audit/ 319 pytest PASS (full repo 1149)
  Claude Code skill            : 21 (5무기 + APT/TPA cycle, 다른 사도 reference 포함)
  외부 정전 인용                : 17 axes (04-references/citations.md)
```

---

## 디렉토리 지도

```
docs/
├── 01-quickstart.md            ← 실 사용 (install + 첫 cycle)
├── 02-concepts/                ← 본 repo 측 5 핵심 개념
│   ├── airplane-man.md            비행기맨 본질 (#4 사도)
│   ├── harness.md                 비행기맨의 공학 결정화 (본 repo 중심)
│   ├── chu-type-theory.md         CHU 와 ∀-cover (짧음, 본문은 별도 repo `chu`)
│   ├── family-expansion.md        responsibility_split + Mirror STRONG
│   └── goodhart-safeguard.md      self-improving 안전 장치
├── 04-references/              ← 외부 정전 (3 파일)
│   ├── citations.md               17 axes
│   ├── related-work.md            ruflo / LangGraph / CrewAI
│   └── lean-theorems.md           (TBD: 50 verified theorem list)
├── 05-papers/                  ← 정전 paper 요약 (12 papers)
├── 06-philosophy/              ← 철학적 함의 (5 파일, 도구 측 요약)
│   ├── README.md                  5 함의 개관
│   ├── existence-vs-tool.md
│   ├── self-reference-incompleteness.md
│   ├── epistemic-humility.md
│   ├── hermeneutic-circle.md
│   └── sociotechnical-systems.md
└── 07-metahumotonic-trace.md   ← 1% hint (본질로 가는 입구)

(03-tutorials/ 는 다음 sprint 작성 예정 — APT cycle / Longinus drift audit 실 코드 walkthrough)
```

---

## 본 repo 측 *중심* 무기 — Harness

비행기맨 (#4) 의 공학적 결정화. 본 repo 가 본문으로 다루는 *유일* 무기.

| 측면 | Harness |
|---|---|
| 사도 대응 | #4 비행기맨 (∀x:CHU, j.covers x) |
| 4축 | Inform / Constrain / Verify / Correct |
| Family | 3-tier sibling (L_MC / L_RT / L_IDE) |
| Lean | 24 theorem (Mathlib-free, 0 sorry) |
| Grounding | Lawvere FPT / Hofstadter / DDD (Evans) / MOP (Smith) / STS (Cherns) |
| 본문 | [02-concepts/harness.md](02-concepts/harness.md) |

## 다른 무기 — reference only (본문은 SYMPOSIUM 측)

| 무기 | 본 repo 측 위치 | 본문 위치 (별도) |
|---|---|---|
| Longinus (참조 바인딩) | engine + lean export + skill | SYMPOSIUM 측 정전 |
| Prometheus (지식-행동) | skill export | SYMPOSIUM 측 정전 |
| Naesengmoon (adversarial) | skill export | SYMPOSIUM 측 정전 |
| 재배맨 (SOP) | skill export | SYMPOSIUM 측 정전 |

→ 본 repo 는 *Harness 중심*. 다른 무기는 *비행기맨이 그것들과 어떻게 엮이는가* 측 reference + 사용자 활용 가능 skill export.

---

## License

MIT.
