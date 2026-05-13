# prometheus — Adversarial

> Lazy-load reference. Parent: [`../SKILL.md`](../SKILL.md).

## 1. Adversarial Surface for Prometheus

Prometheus 의 critic 은 *findings 자체*를 attack:
- axis matrix completeness
- finding evidence robustness
- Lakatos progressive vs rescue distinction
- dedup correctness
- dispersion gate compliance

GAN-D 메커니즘은 Taliban 측 (G6 위에서). 본 섹션은 Taliban critic 이 prom cycle 검증 시 받는 컨텍스트.

## 2. Anti-Bypass for Prometheus Cycles

| # | Bypass | 검출 | 처방 |
|---|--------|------|------|
| 1 | axis matrix N undercount | dimension count | G2 강제 |
| 2 | dedup_hash skip | hash null check | G5 강제 |
| 3 | hot-fix justification missing | reason check | G1 PR_KGSkipWithoutJustification |
| 4 | dispersion gate skip | post-hoc audit | G6.5 강제 |
| 5 | Lakatos rescue 가설을 PROGRESSIVE 라고 표시 | 4-criterion test 결과 | G6 강제 |
| 6 | UNWIND 안 쓰고 N+1 write | transaction count | G7 강제 |
| 7 | Lesson pair incomplete (truth or wrongAssumption only) | schema check | G7.5 강제 |

## 3. Stronger Prompt for Prometheus Cycle Audit

```markdown
# ESCALATED PROMETHEUS CYCLE AUDIT

이전 review 에서 N findings 만 발견. 최소 3 mandatory.

추가 검사:
1. axis matrix 가 진짜 N covering 가? sub_axis 가 trivial 분할이 아닌가?
2. 각 finding 에 dedup_hash 존재? 같은 axis/sub_axis 다른 claim 충돌?
3. 모든 ResearchFinding 의 canonical_doc_path 가 실제 file 가리킴? G6.5 통과?
4. Lakatos 4-criterion 각각 evidence 인용? rescue 가설 covering 시도 흔적?
5. KG-skip (hot-fix) 했다면 justification 가 사람-제공? agent-generated?
6. UNWIND single transaction 사용? N+1 write 흔적?
7. Lesson 의 wrongAssumption ↔ truth pair 둘 다 채워짐?

3 finding 미만 = 검증 부실 = REJECTED.
```

## 4. Mode Collapse Specific to Prometheus

| Signal | Threshold | Action |
|--------|-----------|--------|
| 5+ cycles 모두 PROGRESSIVE verdict | 5 cycles | DEGENERATING test rigor 검토 |
| dedup_collision_count = 0 across 10 cycles | 10 cycles | dedup detection 미작동 의심 |
| hot-fix override 빈도 > 20% | runtime | KG-first discipline 약화 |
| Lesson resolved=true 0 across 30 days | time | feedback loop 단절 |

## 5. The Human as Meta-Discriminator

Prometheus critic 도 hallucinate 가능. sigma_oracle (HUMAN) 가 catch:
- 모든 axis 가 fabricate (실제 외부 source 없음)
- evidence 가 plausible 하지만 verifiable 안 함 (link rot 등)
- Lakatos test 가 자기 가설 보존 위해 criterion 선택적 적용

→ `allow_agent_sigma=false` LOCKED (v17 mirror, 모든 무기 공통).

# KG: ATOM_Skill_prometheus, fw-prometheus-references-apt-parity-2026-05-06
