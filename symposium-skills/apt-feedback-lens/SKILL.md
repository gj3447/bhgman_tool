---
name: apt-feedback-lens
kg_ref: ATOM_Skill_apt_feedback_lens
version: "1.0.0"
channel: stable
canonical_name: apt-feedback-lens
aliases: [apt-4axis-lens, harness-4axis-lens]
description: >
  APT 피드백 4축 (Inform/Constrain/Verify/Correct) — Böckeler 2축(Guides/Sensors) 의 SYMPOSIUM
  fine-grained 분해를 invokable Naesengmoon LensSet 으로 결정화. Harness SKILL.md 본문에서
  *진단-only* 로 죽어있던 4축을 `lensset-apt-4axis` KG-resident LensSet 으로 격상.
  Tier 한정: **L_IDE 계층만** (L_RT는 orchestration model, L_MC는 control plane 이 진짜 frame).
  parent_skill: Harness (분리 motivation, Phase 2 from lesson-harness-drift-corrected-2026-04-29).
  resolves_via: Naesengmoon `/taliban <target> --lens apt-4axis`.
  Invoke when: APT phase gate 측 L_IDE 4축 health 명시 검증 필요,
  '엉뚱한 방향 / Gold Plating / 틀린 코드 통과 / 같은 버그 재발' 증상 진단,
  /tlb <target> --lens apt-4axis 호출.
  # KG: ATOM_Skill_apt_feedback_lens, ATOM_Skill_harness, ATOM_Skill_taliban, lensset-apt-4axis, lesson-harness-drift-corrected-2026-04-29
---

## 🔗 MIC Binding

**ROLE**: `AdversarialValidator` slot 의 LensSet plugin (`--lens apt-4axis`).
**parent_skill**: `harness` (4축 정전 owner, Böckeler 2축 fine-grained 분해의 출처).
**resolves_via**: `taliban` (LensSet protocol owner — pluggable lens dispatch).
**MIC slot**: `MIC_v1.FeedbackLens` RESOLVES_TO `lensset-apt-4axis` RESOLVED_BY `apt-feedback-lens`.

# KG: MIC_v1.FeedbackLens, lensset-apt-4axis

---

## 1. 4축 정의 — Böckeler 2축의 fine-grained 분해 (L_IDE 계층 한정)

> **정전 출처**: Böckeler, Birgitta. *Harness engineering for coding agent users.* [martinfowler.com/articles/harness-engineering.html](https://martinfowler.com/articles/harness-engineering.html), 2026.

| Böckeler 2축 | SYMPOSIUM 4축 | coreQuestion | APT 구현체 | failure 증상 |
|---|---|---|---|---|
| **Guides** (feedforward) | **Inform** | 행동 *전* context 충분히 제공되는가? | KG / docs / Progressive Disclosure / 프로메테우스 발동 grounding | 엉뚱한 방향으로 구현 |
| **Guides** (feedforward) | **Constrain** | 경계 명시 + Gate enforce 작동하는가? | Span 분해 / Contract 7필드 / complexity_threshold / Gate Check Hook | Gold Plating / 범위 초과 |
| **Sensors** (feedback) | **Verify** | 행동 *후* ground-truth check 통과하는가? | Naesengmoon LensSet UNION coverage / TDD RED-GREEN / Lean sorry=0 / executor!=reviewer | 고무도장 / 틀린 코드 통과 |
| **Sensors** (feedback) | **Correct** | Lesson 결정화 + feedback loop 닫혔는가? | Fractal Feedback / AptFeedback / Prometheus lesson / `:Lesson` + `:EXPLAINED_BY` edge | 같은 버그 재발 |

> ⚠️ **L_IDE 외 계층 자동 적용 금지.** L_RT 는 orchestration model 선택 (LangGraph/CrewAI/AutoGen/ADK/Agents SDK), L_MC 는 control plane vs compute plane 분리 가 진짜 frame.

---

## 2. Invoke

### Single-lens dispatch
```
/taliban <target> --lens apt-4axis
```
cardinality=4, UNANIMOUS_PASS aggregation. 4 lens 모두 PASS 시 LensSet APPROVED.

### Ensemble stack (with constitutional)
```
/taliban <target> --lens constitutional --lens apt-4axis
```
v0.8.A1 ensemble pattern 측 추가 LensSet 으로 plug.

---

## 3. L_IDE 4축 health Cypher (자동 진단)

```cypher
MATCH (anchor:SemanticAnchor {name: $project})
OPTIONAL MATCH (anchor)-[:HAS_SPAN*]->(s)
WITH anchor, count(s) AS span_count
OPTIONAL MATCH (ct:AptContract) WHERE ct.name STARTS WITH 'CT_' + $project
WITH anchor, span_count, count(ct) AS contract_count,
     sum(CASE WHEN ct.status = 'fulfilled' THEN 1 ELSE 0 END) AS fulfilled
OPTIONAL MATCH (vr:ValidationResult) WHERE vr.project = $project
WITH anchor, span_count, contract_count, fulfilled,
     count(vr) AS validations,
     sum(CASE WHEN vr.verdict = 'REJECTED' THEN 1 ELSE 0 END) AS rejections
OPTIONAL MATCH (fb:AptFeedback) WHERE fb.name STARTS WITH 'FB_' + $project
WITH span_count, contract_count, fulfilled, validations, rejections,
     count(fb) AS feedbacks,
     sum(CASE WHEN fb.status = 'resolved' THEN 1 ELSE 0 END) AS resolved_fb
RETURN span_count AS inform_density,
       contract_count AS constrain_total, fulfilled AS constrain_fulfilled,
       validations AS verify_total, rejections AS verify_rejections,
       feedbacks AS correct_total, resolved_fb AS correct_resolved
```

→ 각 축 density 측 anchor 별 baseline 대비 deviation 측 약점 식별.

---

## 4. 학문 grounding

| underwriting canon | 위치 | 강도 |
|---|---|---|
| **Tanter 2003 OOPSLA — Partial Behavioral Reflection 2x2** (structural × behavioural × introspection × intercession) | PRIMARY (4축 ↔ 2x2 cell hypothesis) | STRONG (PROM_16 D4 finding) |
| **Smith 1982 — MCP/MOP reflective tower** | PRIMARY (instance-internal reflective concern) | STRONG (D4) |
| **Böckeler 2026 — Guides/Sensors** | PRIMARY (2축 → 4축 derivative) | DIRECT (martinfowler.com) |
| **SWE-Aider 2026 — ACI 4 principles** | bijection cross-ref | STRONG (PROM_16 C4) |
| Cockburn 2005 — Hexagonal Ports-and-Adapters | SECONDARY (apt-feedback-lens=adapter, APT core=port) | MEDIUM |
| Martin SOLID SRP | metaphor only (evolution rate separation) | TERTIARY |
| Cherns 1976 — STS Principle 6 Boundary Location | cross-domain mirror | TERTIARY |

→ **terminology canonical**: "4축은 *instance-internal organizing principle* (Tanter 2x2 reflective taxonomy cell), NOT family axis".

# KG: finding-prom16-harness-D4-smith-reflection-1982-2026-05-10, finding-prom16-harness-C4-swe-aider-2026-05-10, finding_prom16_hv3_B1

---

## 5. What NOT To Do

| 금지 | 이유 |
|---|---|
| L_RT 또는 L_MC 에 4축 자동 적용 | category mismatch (Harness §7.1) |
| 4축을 family 정의로 박기 | v2 drift 재발 |
| cardinality=4 외 다른 cardinality 강제 | naesengmoon-canonical-2026-05-19 N중=N independent lens 1:1 |
| inline parent execution | naesengmoon-inline-bypass-jaebaeman-sop-2026-05-19 위반 — canonical agent 측 dispatch |

---

## History

| Version | Date | Summary | KG Ref |
|---|---|---|---|
| **v1.0.0** | 2026-05-20 | initial — Harness SKILL.md §2.3 4축 진단 protocol 측 별도 invokable LensSet 측 분리 (Phase 2 from `lesson-harness-drift-corrected-2026-04-29`). Tanter 2x2 PRIMARY grounding (D4 finding). | `ATOM_Skill_apt_feedback_lens`, `lensset-apt-4axis`, `prom16-harness-v3-impl-2026-05-20` |

# KG history: lesson-harness-drift-corrected-2026-04-29 (motivation Phase 2), prom16-harness-v3-impl-2026-05-20 (implementation cycle)
