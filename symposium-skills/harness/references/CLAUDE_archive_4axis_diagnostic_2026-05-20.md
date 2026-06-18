# Harness SKILL.md §2.3 archive — 4축 진단 프로토콜 (L_IDE 한정)

> **archived 2026-05-20** by `prom16-harness-v3-impl-2026-05-20` cycle.
> Source: `SKILLS/harness/SKILL.md` v3.2.0 L81-114 (§2.3).
> Motivation: invokable LensSet 측 분리 (Phase 2 from `lesson-harness-drift-corrected-2026-04-29`).
> Successor: `~/.claude/skills/apt-feedback-lens/SKILL.md` (invokable `lensset-apt-4axis`).
> Longinus L4 forward binding: `rs-harness-4axis-archive-2026-05-20` ReferenceSite.

---

## 2.3 4축 진단 프로토콜 (L_IDE 내부 한정)

에이전트가 **L_IDE 계층에서** 실패했을 때, 4축 중 어디가 약한지 진단:

| 증상 | 약한 축 | 처방 |
|------|---------|------|
| 엉뚱한 방향으로 구현 | Inform | KG 보강, docs 추가, 프로메테우스 발동 |
| 범위 초과 / Gold Plating | Constrain | Contract 경계 강화, Span 재분해 |
| 틀린 코드가 통과됨 | Verify | Naesengmoon lens 추가, 테스트 강화 |
| 같은 버그 재발 | Correct | Feedback loop 점검, Lesson 기록 |

> ⚠️ **L_IDE 외 계층에서 4축 진단을 자동 적용하지 말 것.** L_RT는 orchestration model 선택, L_MC는 control plane이 진짜 frame.

```cypher
// L_IDE 4축 건강도 (기존 v2 프로토콜 그대로)
MATCH (anchor:SemanticAnchor {name: $project})
OPTIONAL MATCH (anchor)-[:HAS_SPAN*]->(s)
WITH anchor, count(s) as span_count
OPTIONAL MATCH (ct:AptContract) WHERE ct.name STARTS WITH 'CT_' + $project
WITH anchor, span_count, count(ct) as contract_count,
     sum(CASE WHEN ct.status = 'fulfilled' THEN 1 ELSE 0 END) as fulfilled
OPTIONAL MATCH (vr:ValidationResult) WHERE vr.project = $project
WITH anchor, span_count, contract_count, fulfilled,
     count(vr) as validations,
     sum(CASE WHEN vr.verdict = 'REJECTED' THEN 1 ELSE 0 END) as rejections
OPTIONAL MATCH (fb:AptFeedback) WHERE fb.name STARTS WITH 'FB_' + $project
WITH span_count, contract_count, fulfilled, validations, rejections,
     count(fb) as feedbacks,
     sum(CASE WHEN fb.status = 'resolved' THEN 1 ELSE 0 END) as resolved_fb
RETURN span_count AS inform_density,
       contract_count AS constrain_total, fulfilled AS constrain_fulfilled,
       validations AS verify_total, rejections AS verify_rejections,
       feedbacks AS correct_total, resolved_fb AS correct_resolved
```

---

## Reuse pointer

본 archive 의 진단 protocol + Cypher 측 `~/.claude/skills/apt-feedback-lens/SKILL.md` §3 측 직접 inline 으로 옮겨졌다 (invokable form). 본 archive 측 history/audit trail 용 cold-storage.

# KG: ATOM_Skill_harness, ATOM_Skill_apt_feedback_lens, lensset-apt-4axis, lesson-harness-drift-corrected-2026-04-29, prom16-harness-v3-impl-2026-05-20, rs-harness-4axis-archive-2026-05-20
