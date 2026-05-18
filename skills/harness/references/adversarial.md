# harness — Adversarial

> Lazy-load reference. Parent: [`../SKILL.md`](../SKILL.md).

## 1. Diagnosis Adversarial Surface

Harness diagnosis 는 *external evidence* 의존:
- Vendor docs 가 marketing fluff vs technical fact 구분
- Score 가 cherry-picked evidence 인가?
- Tier 분류가 self-serving (예: "우리 framework 는 L_IDE 다" 가벼운 분류)?

## 2. Anti-Bypass for Diagnosis

| # | Bypass | 검출 | 처방 |
|---|--------|------|------|
| 1 | 한 instance 로 family 결정 | sibling 검색 누락 | HR_Family1to1 |
| 2 | tier 잘못 분류 | responsibility boundary 재확인 | HR_TierConfusion |
| 3 | evidence-free score | V4 audit | BLOCK + 재조사 |
| 4 | Bockeler citation 사용 | citation grep | family-expansion-pattern-canonical-2026-04-30 fallback |
| 5 | MCP = framework | adapter 정의 강제 | HR_MCPRoleConfusion |
| 6 | 4축 한 축만 max score | distribution skew | balanced score 강제 |
| 7 | Lakatos rescue 가설 받아들임 | 4-criterion 강제 | DEGENERATING 표시 |

## 3. Critic Input Context (Naesengmoon)

Harness 진단 결과를 Naesengmoon critic 이 검증 시 받는 컨텍스트:
- HarnessProfile (tier + 4-axis score + evidence per axis)
- Anti-pattern detection list
- Family-Relation Mirror position
- Sibling instances (다른 tier)
- Lakatos test result (PROGRESSIVE / DEGENERATING)

## 4. Multi-Instance Comparison Adversarial Mode

```
harness-diagnostician comparison_mode [Cursor, Claude Code, Aider, Cline]
```

비교 자체가 adversarial:
- 각 vendor 의 self-promotion bias 차단 (cross-instance evidence 강제)
- Score 절대값 보다 distribution shape 더 중요
- 한 vendor 가 모든 axis max 면 의심 (cherry-picked evidence)

## 5. Lakatos PROGRESSIVE 입증

1:N family hypothesis 는 4 distinguishability test 통과 (theory.md §7):

| Test | 1:1 | 1:N (Harness 정전) |
|------|-----|---------|
| theory_laden_anomaly | 인정 | 인정 |
| independent_testable_consequence | 약 | 강 (per-tier) |
| excess_empirical_content | 적음 | 많음 (sibling) |
| principled_grounding | 약 | 강 (CHU 거울) |

→ 1:N 가 PROGRESSIVE. 1:1 은 DEGENERATING (rescue 가설).

KG: `lakatos-progressive-vs-rescue-test-canonical-2026-05-06`.

## 6. Family Drift Specific to Harness

자주 보이는 drift kinds:
- "Cursor 가 가장 강력한 harness" → HR_Family1to1 (다른 tier 검토 안 함)
- "Claude Code = LangGraph" → HR_TierConfusion (L_MC vs L_RT)
- "Verify = test 만" → HR_AxisMonopoly (adversarial / ground truth 무시)
- "MCP 는 framework 같은 것" → HR_MCPRoleConfusion (adapter 정의)

## 7. The Human as Meta-Discriminator

Harness diagnosis 는 *value judgment* 측면 강함:
- "강한 harness" 정의가 user goal 의존
- sigma_oracle 가 "이 instance 가 우리 use case 에 best" 결정
- diagnostician agent 는 *evidence* 만 제공, *recommendation* 은 사용자

# KG: ATOM_Skill_harness, fw-harness-references-apt-parity-2026-05-06
