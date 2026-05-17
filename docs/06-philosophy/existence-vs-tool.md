# 존재 vs 도구 — layer 분리의 존재론

## 한 줄

사도 (#4 비행기맨) 는 **존재** (`∀x:CHU, j.covers x` type-level predicate). Harness 는 **도구** (3-tier sibling family runtime). 같은 layer 에서 enumerate 하면 카테고리 오류.

---

## 도구 측 영향

ruflo / LangGraph / CrewAI 류 framework 는 *agent / tool / plugin / skill / hook* 을 모두 같은 layer 에서 호명한다. 그것 자체가 카테고리 오류:

```
ruflo 측:           [agent #1, agent #2, ..., agent #100, plugin A, ..., tool X]
                    └──── 모두 같은 layer 의 enumeration ────┘
                    flat. responsibility_split 없음.

bhgman 측:          존재 layer:   12사도 (∀x:CHU, j_i.covers x)
                                  ↓ 결정화 (1:N family)
                    도구 layer:   각 사도 × industry instance (L_MC/L_RT/L_IDE)
                                  ↓ 운영
                    protocol layer: MCP / SOP (재배맨)
                                  ↓ 실행
                    instance layer: Cursor / Claude Code / ruflo / LangGraph / ...

                    3+ layer 명시 분리. 각 layer 의 *언어* 가 다름.
```

→ 같은 layer 에 두면 *type error*. 사도(predicate) 와 plugin(runtime object) 은 다른 type universe 의 entity.

---

## 정전 grounding

- **Aristotle Metaphysics** Book Δ — 존재 (`τὸ ὄν`) 의 다층성 (substance / quality / quantity / ...)
- **Heidegger 1927 Sein und Zeit** — 존재 (`Sein`) vs 존재자 (`Seiendes`) 의 ontological difference
- **Frege 1892** Sense (Sinn) vs Reference (Bedeutung) — 동일 referent 의 다른 sense 가능
- **Russell type theory** — type level 분리로 paradox 회피
- **Lawvere 1969 FPT** — 자기참조 + type universe 의 형식 한계

bhgman 측 사도/도구 분리는 위 정전들의 *통합* 응용.

---

## 자세히는

본격 본문 (각 정전 deep dive + Lean 형식 + 메타휴모토닉 측 motivation) 은 별도 repo / SYMPOSIUM 측. 이 문서는 *도구 사용자 측* 함의 요약.

- [../02-concepts/airplane-man.md](../02-concepts/airplane-man.md) — 사도 측 정의
- [../02-concepts/harness.md](../02-concepts/harness.md) — 도구 측 결정화
- [../05-papers/lawvere-1969-FPT.md](../05-papers/lawvere-1969-FPT.md) — type universe 형식 한계
- [../07-metahumotonic-trace.md](../07-metahumotonic-trace.md) — 본질 layer 측 hint
