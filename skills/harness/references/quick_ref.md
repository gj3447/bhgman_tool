# harness — Quick Ref

> Parent: [`../SKILL.md`](../SKILL.md).

## Decision Tree

```
"I need to..."
    |
    +-- "...diagnose an instance" → harness-diagnostician <instance>
    +-- "...compare 4 instances" → harness-diagnostician comparison_mode [...]
    +-- "...find tier siblings" → KG: MATCH (h:HarnessProfile {tier: $t})
    +-- "...check anti-patterns" → KG: MATCH (apl:HarnessAntiPatternLog)
    +-- "...understand 4-axis model" → references/theory.md §3
```

## 3-Tier Cheat Sheet

| Tier | Examples |
|------|----------|
| L_MC | Cursor / Claude Code / Aider / SWE-agent / Cline / OpenHands |
| L_RT | Google ADK / LangGraph / CrewAI / AutoGen |
| L_IDE | Anthropic Managed Agents / OpenAI Assistants / Vertex AI Agent Engine |

## 4-Axis Score (0-3)

| Axis | 0 | 3 |
|------|---|---|
| Inform | 없음 | Progressive Disclosure + KG-first |
| Constrain | 없음 | full PreToolUse + tool whitelist + dynamic context |
| Verify | 없음 | ground truth (compiler+test+adversarial+sigma_oracle) |
| Correct | 없음 | Lesson → ActionPlan → re-execute + drift detection |

## Family-Relation Mirror Position

| Tier | Hyperedge Position |
|------|-------------------|
| L_MC | apex (VerticalAxisHyperedge[1]) |
| L_RT | substrate ([2]) |
| L_IDE | end ([3]) |

비행기맨(#4) 만 STRONG mirror — 다른 무기는 N/A 가능.

## Common BLOCK Causes

| Symptom | Cause | Fix |
|---------|-------|-----|
| 한 instance 로 결론 | HR_Family1to1 | sibling 검색 강제 |
| Bockeler citation | HR_BockelerCitationDrift | family-expansion-pattern-canonical-2026-04-30 만 |
| MCP = framework | HR_MCPRoleConfusion | adapter 정의 |
| score 4축 모두 0 | tier 재확인 | tier_evidence 강화 |

# KG: ATOM_Skill_harness, fw-harness-references-apt-parity-2026-05-06
