# taliban — Theory

> Lazy-load reference. Parent: [`../SKILL.md`](../SKILL.md). KG: `taliban-grounding`, `fw-taliban-references-apt-parity-2026-05-06`.

---

## 1. GAN-D Mechanism

Naesengmoon = APT/TPA의 *면역 시스템*. GAN의 D(iscriminator) 역할.

| GAN | Naesengmoon |
|-----|---------|
| Generator | Design Agent (APT) / Recovery Agent (TPA) |
| Discriminator | **Naesengmoon** (LensSet 적대적 검증) |
| Loss | findings count + severity + evidence |
| Mode Collapse | rubber-stamp 발견 (5+ rounds nitpick-only) |
| Nash Equilibrium | sigma_oracle (HUMAN) tie-break |
| Regularization | Anti-Rubber-Stamp 10 techniques |

---

## 2. LensSet 플러거블 (v3 + v0.8)

| LensSet | lensCount | 용도 |
|---------|-----------|------|
| `constitutional-9-full` | 9 | **default** — 산출물(Span/Contract/Code) 검증 |
| `mathematical` | 113 | Distributed pattern math 검증 (88-Naesengmoon) |
| `solid` | 5 | SOLID 원칙 빠른 검증 |
| `longinus` | n | 코드↔KG 바인딩 정합성 |
| (custom KG nodes) | varies | 사용자 정의 LensSet |

```cypher
MATCH (ls:LensSet) WHERE ls.deprecated <> true
RETURN ls.name, ls.lensCount, ls.scope, ls.description
ORDER BY ls.lensCount DESC
```

---

## 3. Pirsig Holistic Synthesis (v0.8 ensemble UNION)

같은 Concern은 max(weight) lens가 cover. 단일 LensSet 검증 폐기 (v0.8.A1):

```
ensemble_coverage_score = sum(max(cv.weight) per Concern across used_lensets) / 9.0
APPROVE if ensemble_coverage_score >= 0.8 (default)
```

KG: `rfc-taliban-v08-concern-coverage-2026-05-04`, `lesson-taliban-v08-single-lensset-insufficient-2026-05-04`.

Single-LensSet 가 모두 borderline/fail (Phase 2 discovery) → ensemble UNION이 정전.

---

## 4. Anti-Rubber-Stamp Techniques (10)

| # | Technique | 검출 |
|---|-----------|------|
| 1 | Model separation | 같은 weights = bias 전염 |
| 2 | Min finding count (≥3) | lazy approval |
| 3 | Core assumption challenge | surface critique |
| 4 | Anti-checklist (10-item) | incomplete review |
| 5 | Falsifiability requirement | vague handwaving |
| 6 | Ground truth cross-check | phantom bugs |
| 7 | Severity distribution audit | nitpick-only theater |
| 8 | Historical finding rate | gaming the minimum |
| 9 | Blind review | authority anchoring |
| 10 | Rotation (5+ rounds) | adaptation/overfitting |

---

## 5. RTI / FVR (Random-Tactical-Insertion / Forced-Verdict-Rotation)

- **RTI**: critic prompt에 무작위 attack vector 삽입 → adaptation 차단
- **FVR**: N rounds 후 verdict 강제 rotation (REJECT 가 너무 오래 안 나오면 critic 의심)

---

## 6. 5 Verdict Categories

| Verdict | 의미 | 다음 |
|---------|------|------|
| `APPROVED` | 모든 기준 통과 + evidence cited | gate pass |
| `APPROVED_PENDING_EXTERNAL_D20` | 자체-executor 보완 + sigma_oracle 동의 | 최종 gate, external retest 필요 |
| `REJECTED` | ≥1 BLOCKER 미해결 | re-design / re-recover |
| `CONDITIONAL_PASS` | PERFORMANCE finding 만 | sigma_oracle 결정 |
| `SUPERSEDED` | 후속 VR 가 대체 | gate query에서 제외 |

---

## 7. 재배맨 SubagentTaskSpec 자동 출격

```cypher
MATCH (ts:SubagentTaskSpec {skill:'taliban', lensset:$lensset_name})
RETURN ts.checkItems, ts.parallelism_min, ts.cypherQueries
```

부모 인라인 critic 금지. 반드시 subagent 1개 이상 독립 출격 (TR11 / D20 / executor != reviewer).

---

## 8. Mathematical Sampler (113-lens)

```cypher
MATCH (sampler:TalibanMathematicalSampler {name:'taliban-mathematical-sampler-poc-2026-05-06'})
RETURN sampler.modes, sampler.taxonomy, sampler.codes
-- modes: ['full','sample','min','custom']
-- taxonomy: 13 domain (LL/LO/AL/AN/TO/...)
-- codes: 'LL.1' ~ 'IC.9' canonical lens code
```

KG-grounded codes (synthetic 아님). 비용 가드: `MathematicalSamplingPolicy` slot rate=0.30 default.

---

## 9. References

- `../SKILL.md` — protocol
- KG: `lakatos-progressive-vs-rescue-test-canonical-2026-05-06`, `taliban-mathematical-sampler-poc-2026-05-06`, `MIC_v1.AdversarialValidator` slot
- 사이블: `../prometheus/references/theory.md` (Step 4 distinguishability), `../jaebaeman/references/theory.md` (subagent dispatch)

# KG: ATOM_Skill_taliban, fw-taliban-references-apt-parity-2026-05-06
