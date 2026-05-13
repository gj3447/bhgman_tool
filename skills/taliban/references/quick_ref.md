# taliban — Quick Ref

> Parent: [`../SKILL.md`](../SKILL.md). Sibling: [`./theory.md`](./theory.md), [`./gates.md`](./gates.md).

## Decision Tree

```
"I need to..."
    |
    +-- "...validate a Span/Contract/Code" → /tlb <target> (default constitutional 9-lens)
    +-- "...meta-validate a methodology" → /88-taliban <skill> (mathematical 113-lens)
    +-- "...SOLID quick check" → /taliban <target> --lens solid
    +-- "...binding integrity check" → /taliban <target> --lens longinus
    +-- "...ensemble UNION coverage" → APT_GATE_VERSION=v08-A1 + /taliban
    +-- "...check open feedback" → KG: MATCH (fb:TalibanFeedback {status:'open'})
    +-- "...mode collapse history" → KG: MATCH (mc:ModeCollapseLog) ORDER BY mc.detected_at DESC
```

## LensSet Cheat Sheet

| LensSet | lensCount | Use |
|---------|-----------|-----|
| `constitutional-9-full` | 9 | default — artifact validation |
| `mathematical` | 113 | methodology meta-verification (88-Taliban) |
| `solid` | 5 | SOLID 빠른 검증 |
| `longinus` | n | KG↔code binding integrity |
| (custom KG) | varies | user-defined |

## Verdict Cheat Sheet

| Verdict | When |
|---------|------|
| APPROVED | findings ≥ 3, coverage ≥ 0.8, 0 BLOCKER |
| APPROVED_PENDING_EXTERNAL_D20 | self-executor + sigma_oracle consent |
| REJECTED | ≥1 unresolved BLOCKER OR coverage < 0.8 |
| CONDITIONAL_PASS | PERFORMANCE only |
| SUPERSEDED | replaced by newer VR |

## Anti-Rubber-Stamp 10 Index

1. Model separation
2. Min findings ≥ 3
3. Core assumption challenge
4. Anti-checklist (10-item)
5. Falsifiability
6. Ground truth cross-check
7. Severity distribution audit
8. Historical finding rate
9. Blind review
10. Rotation

## Common BLOCK Causes

| Symptom | Cause | Fix |
|---------|-------|-----|
| findings = 0 + APPROVED | TL_RubberStamp | escalated prompt + rotation |
| lensCount < 9 | TL_LensSetIncomplete | constitutional-9-full fallback |
| inline provenance | TL_InlineProvenance | force subagent dispatch |
| coverage < 0.8 | ensemble UNION 부족 | LensSet 확장 |

# KG: ATOM_Skill_taliban, fw-taliban-references-apt-parity-2026-05-06
