# Family-Expansion Pattern — 비행기맨 측 1:N 결정화

> 비행기맨 측 ∀-cover 가 industry 측에서 *어떻게 분해* 되는가. 더 일반화된 family-expansion-pattern 정전 (12사도 전체에 적용) 은 별도 — SYMPOSIUM `family-expansion-pattern-canonical-2026-04-30` (:StructuralPattern).

---

## 1:N family 가 default

비행기맨 ∀-cover 는 *직접 구현 불가능* (현실 agent 유한). 따라서 sibling family 로 분해. 1:1 매핑 (예: "비행기맨 = Cursor 만") 은 drift.

```
isAirplaneMan(j) ≜ ∀x:CHU, j.covers x

도구 측 결정화:
∀-cover  ↘  family(L_MC, L_RT, L_IDE)    [3-tier sibling]
```

---

## 6 sub-type (family 내부 이질성)

family-expansion-pattern 의 sub-type 6종 (SYMPOSIUM 정전):

| sub-type | 정의 | 비행기맨 측 적용? |
|---|---|---|
| **responsibility_split** | 책임 분할 — CCP/CRP 준수 | ✅ Harness 3-tier 가 만족 |
| **domain_decomposition** | 지식 영역 심화 (AND-conjunctive) | ❌ (다른 사도 — ICE 6-family) |
| **protocol_sequence** | 순차 stack | ❌ (다른 사도 — 스페이스걸) |
| **algorithm_variants** | 구현 대안 (OR-disjunctive) | ❌ (다른 사도 — 깊바존 GC) |
| **temporal_stage** | 시간 단계 | ❌ (다른 사도 — HOH 천국) |
| **concept_space** | 개념 분광 | ❌ (다른 사도 — 예수 7-Family) |

→ 비행기맨 측은 **responsibility_split** 만 적용. 이것이 STRONG Mirror 조건의 *유일* 충족 case (cardinality match + responsibility split 동시).

다른 사도의 family sub-type 본문은 SYMPOSIUM 측 정전 / 각 사도별 repo.

---

## Mirror 조건 (STRONG vs PARTIAL vs NOT)

**Mirror** 는 사도 측 family 구조와 그 사도가 참여한 *relation hyperedge* 위치 구조의 1:1 대응.

비행기맨 STRONG Mirror 증거:
```
Harness 3-tier (L_MC / L_RT / L_IDE)
↔
VerticalAxisHyperedge {#4 apex / #8 substrate / #10 end}
                       ↕ orchestration / execute / leaf
1:1 mirror (role-level position match)
```

→ 비행기맨은 *Mirror STRONG 만족 첫 instance*. 다른 사도들은 cardinality mismatch / sub-type 이질 (예수 7-folder, OM 4-tier, 깊바존 GC 3-tier — 정확한 mirror 아님).

자세히는 SYMPOSIUM 측 `family-relation-mirror-hypothesis-2026-04-30` 또는 비행기맨 측 [airplane-man.md](airplane-man.md) §family.

---

## Anti-pattern (대조)

ruflo (industry instance) 측 anti-pattern:
- 100+ agent / 32 plugin / 314 MCP tool **flat enumeration** — sub-type 어느 것도 만족 안 함
- responsibility_split 위반 (모두 같은 layer)
- → SYMPOSIUM ErrorPattern: `errorpattern-enumeration-inflation-no-responsibility-split-2026-05-13`

비행기맨 측 Harness 3-tier 는 *명시적 책임 분할* (L_MC / L_RT / L_IDE 의 책임이 겹치지 않음) — Robert Martin CCP 직접 응용.

---

## 추가 자료

- [airplane-man.md](airplane-man.md) — 비행기맨 본질
- [harness.md](harness.md) — 도구 측 결정화
- [goodhart-safeguard.md](goodhart-safeguard.md) — flat enumeration 의 위험
- [../04-references/related-work.md](../04-references/related-work.md) — ruflo 측 anti-instance
