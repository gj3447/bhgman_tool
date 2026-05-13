# taliban — Validation

> Lazy-load reference. Parent: [`../SKILL.md`](../SKILL.md). Sibling: [`./gates.md`](./gates.md).

## V1-V14 — Taliban Adversarial Invariants

| V# | Target | Severity |
|----|--------|:--------:|
| V1 | Every VR has USED_LENS edge | P1 |
| V2 | LensSet.lensCount >= 9 (default) | P1 |
| V3 | LensSet.deprecated <> true | P1 |
| V4 | findings_count >= 3 (Anti-Rubber-Stamp #2) | P1 |
| V5 | evidence non-empty for APPROVED | P1 (HR11 mirror) |
| V6 | provenance != 'inline' | P1 (TR11 mirror) |
| V7 | parent_model != critic_model | P1 (#1 model separation) |
| V8 | severity distribution not 100% NITPICK | P2 (#7 audit) |
| V9 | Distributed pattern → SP-MetaVerify VR exists | P1 (TPA-측) |
| V10 | ensemble UNION coverage >= 0.8 | P2 (v0.8.A1) |
| V11 | RTI random vector injected | P3 |
| V12 | FVR consecutive verdict pattern check | P3 |
| V13 | model rotation after 5+ rounds | P3 |
| V14 | not always exactly 3 findings (gaming check) | P3 (#8 audit) |

## V4 Cypher (Adversarial Round Completion mirror)

```cypher
MATCH (vr:ValidationResult)
WHERE NOT EXISTS { MATCH (vr)-[:USED_LENS]->(:LensSet) }
RETURN vr.name AS missing_lens_edge, 'TR1 / V1 violation' AS reason
```

## Quick Health Check

V1, V2, V4, V5, V6, V7 (P1). 최소.

## Events

| Event | Payload | When |
|-------|---------|------|
| TalibanInvocationStarted | `{target, lens, parent_model}` | G0 |
| LensSetResolved | `{lens, lensCount, deprecated}` | G1 |
| AdversarialRoundCompleted | `{vr, findings_count, blockers, verdict}` | G6 |
| ModeCollapseDetected | `{round, signal}` | G5 audit |
| ModelRotated | `{from, to, reason}` | G5 #10 |
| RTIVectorInjected | `{round, vector}` | G5.5 |
| FVRRotationForced | `{from_verdict, to_verdict}` | G5.5 |

## TC

| # | Clarification |
|---|--------------|
| TC1 | Adversarial 은 hostility 가 아니라 structured opposition |
| TC2 | Lite Mode (single model) 는 anti-rubber-stamp 모두 mandatory |
| TC3 | Foundation:composite ratio 는 per-Span, per-KG 아님 |
| TC4 | allow_agent_sigma=false 는 v17 LOCKED — config override 불가 |
| TC5 | ensemble UNION 은 단일 LensSet 평가 폐기 의미 (Phase 2 discovery) |

# KG: ATOM_Skill_taliban, fw-taliban-references-apt-parity-2026-05-06
