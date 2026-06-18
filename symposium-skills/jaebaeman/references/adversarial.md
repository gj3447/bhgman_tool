# jaebaeman — Adversarial

> Lazy-load reference. Parent: [`../SKILL.md`](../SKILL.md).

## 1. SOP Adversarial Surface

재배맨 SOP 가 *infrastructure* 이지만 적대적 검증 가능 angle:
- seed_bundle 9-field 가 진짜 9 인가? (schema audit)
- intent_N == actual_N 가 진짜 검증되었나? (post-dispatch)
- subagent provenance 가 'inline' 안 박혔나? (TR11)
- DispatchHyperedge cardinality_match 가 진짜 true 인가? (referential integrity)

## 2. Anti-Bypass for SOP

| # | Bypass | 검출 | 처방 |
|---|--------|------|------|
| 1 | inline critic | subagent_count = 0 | JB_InlineCritic |
| 2 | MCP 자동 상속 가정 | pre-fetch 누락 | JB_MCPInheritanceAssumption (GH#13605) |
| 3 | self-check skip | intent_N != actual_N | JB_SelfCheckSkip (GH#29181) |
| 4 | dedup_hash skip | hash null | JB_DedupSkipped |
| 5 | sequential dispatch | message structure | JB_SequentialDispatch (SUB-OPTIMAL) |
| 6 | cardinality mismatch | edge count | JB_HyperedgeCardinalityMismatch |
| 7 | N+1 write | transaction count | JB_NPlus1Write |
| 8 | inline provenance | VR.provenance check | JB_InlineProvenance |

## 3. Critic Input Context (Naesengmoon)

Naesengmoon critic 이 SOP cycle 검증 시 받는 컨텍스트:
- SubagentTaskSpec (seed canonical)
- DispatchHyperedge (cardinality, dispatch_pattern)
- Seed bundle audit (9 fields present?)
- Self-check log (intent vs actual)
- Dedup detection result
- Provenance chain (W3C PROV)

## 4. SOPViolationLog 추적

```cypher
MATCH (v:SOPViolationLog) WHERE v.detected_at >= datetime() - duration('P30D')
RETURN v.pattern, count(v), collect(v.cycle_id)[0..5]
ORDER BY count(v) DESC
```

→ 빈도 높은 violation 패턴이 framework drift 후보.

## 5. The Holacracy Mirror as Self-Adversarial

4 archetype (facilitator/lead_link/rep_link/secretary) 가 *서로 책임 검증*:

| Archetype | Validates |
|-----------|-----------|
| facilitator (Phase 1) | seed_bundle 9-field invariant |
| lead_link (Phase 2) | intent_N == actual_N self-check |
| rep_link (Phase 3) | FullFindingRecord schema + dedup |
| secretary (Phase 4) | UNWIND batch + cardinality match |

→ 각 archetype 이 *next archetype* 의 input 검증 (chain audit).

## 6. Wooldridge BDI Comparison (Anti-Drift)

자주 발생하는 drift: "재배맨 = MAS / multi-agent system / BDI agent"

→ 정정 (lesson-jaebaeman-rebrand-SOP-2026-05-05):

| Wooldridge BDI Agent (1995) | 재배맨 SOP |
|----------------------------|-----------|
| Beliefs (internal state) | **부재** |
| Desires (goals) | **부재** |
| Intentions (plans) | **부재** |
| Reactive (env perceive) | **부재** |
| Persistent | **부재** (1회 실행 후 종료) |

→ 학문적 정확명: SOP. 한국어 alias 유지.

## 7. The Human as Meta-Discriminator

SOP 자체 adversarial 의 한계:
- 4 archetype 도 같은 weights (instances of Claude) → 공통 bias 가능
- sigma_oracle 가 cycle 자체 적절성 결정
- "이 dispatch 가 실제로 N=8 만큼 가치 있나?" 판단

# KG: ATOM_Skill_jaebaeman, fw-jaebaeman-references-apt-parity-2026-05-06
