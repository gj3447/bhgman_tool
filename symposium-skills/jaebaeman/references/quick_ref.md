# jaebaeman — Quick Ref

> Parent: [`../SKILL.md`](../SKILL.md).

## Decision Tree

```
"I need to..."
    |
    +-- "...dispatch N subagents" → 재배맨 SOP 4-stage 따라
    +-- "...implement subagent in agent file" → use 4 archetype agents:
    |     - facilitator (Phase 1 Seed)
    |     - lead_link (Phase 2 Dispatch)
    |     - rep_link (Phase 3 Collect)
    |     - secretary (Phase 4 Write)
    +-- "...register new TaskSpec" → references/kg_logging.md §1
    +-- "...debug dispatch truncation" → references/error_handling.md §3
    +-- "...check anti-pattern history" → KG: MATCH (v:SOPViolationLog) ORDER BY v.detected_at DESC
```

## SOP 4-Stage Cheat Sheet

| Stage | Holacracy | Agent |
|-------|-----------|-------|
| G0-G2 Seed + Pre-fetch | facilitator | `facilitator` |
| G3-G4 Dispatch + Self-check | lead_link | `lead_link` |
| G5-G6 Collect + Dedup | rep_link | `rep_link` |
| G7-G8 Write + Hyperedge | secretary | `secretary` |

## Seed Bundle 9-Field

```
agent_id / task_spec_name / axis / sub_axis / parent_intent /
cypher_queries / expected_outcome / treasure_coverage_min / provenance
```

## GitHub Issues 정전

| GH# | 의미 |
|-----|------|
| GH#13605 | MCP server 비상속 — parent pre-fetch 필수 |
| GH#29181 | dispatch self-check (intent vs actual count) |

## Common BLOCK Causes

| Symptom | Cause | Fix |
|---------|-------|-----|
| TaskSpec 없음 | seed unplanted | G0.5 New Seed |
| MCP 자동 가정 | JB_MCPInheritanceAssumption | parent pre-fetch |
| intent_N != actual_N | JB_SelfCheckSkip | GH#29181 audit |
| sequential dispatch | JB_SequentialDispatch | single-message multi-call |
| inline provenance | JB_InlineCritic | force subagent |

# KG: ATOM_Skill_jaebaeman, fw-jaebaeman-references-apt-parity-2026-05-06
