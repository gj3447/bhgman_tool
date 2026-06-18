---
name: apt-magic-resolve
kg_ref: ATOM_Skill_apt_magic_resolve
version: "1.0.0"
channel: stable
canonical_name: apt-magic-resolve
description: >
  APT v26 A6 Resolve-Only directive 책무 — magic number / lens count / contract field count
  를 SKILL.md prose hardcode 가 아닌 KG `MethodologyConfig` slot resolve 로만 해결.
  Treasure 교체 시 KG 노드만 수정, SKILL.md 본문 무수정.
  Migrated 2026-05-22: body 본 skill 안에 이전 완료 (was at apt/SKILL.md §v26 A6).
  Invoke when: skill 안 magic number resolve, MethodologyConfig 조회, A6 compliance 검증.
  # KG: ATOM_Skill_apt_magic_resolve, APT_v26_A6_2026-04-21, MethodologyConfig_default_v26, lesson-apt-v26-a6-skill-resolve-only-2026-04-25
---

## 🎛 v26 A6 Resolve-Only Directive

> APT skill family 의 모든 magic number / lens count / contract field count 는 KG `MethodologySlot` 조회로만 해결. Direct prose edit 금지 — KG 노드만 수정.

```cypher
// Config resolve (magic number 대체)
MATCH (cfg:MethodologyConfig {name:'MethodologyConfig_default_v26'}) RETURN cfg.{field}
// LensSet resolve (deprecated lens 차단)
MATCH (ls:LensSet {name:$lensName}) WHERE ls.deprecated <> true RETURN ls.lensCount, ls.minCritics
// ContractSchema resolve (ST phase)
MATCH (slot:MethodologySlot {name:'ContractSchema'})-[:RESOLVES_TO]->(schema) RETURN schema.fields
```

**Resolve targets**: `vibe_coding_sweet_min/max` · `vibe_coding_hard_max` · `lens_min_critics_constitutional` · `min_findings_per_lens` · `span_depth_max` · `context_budget_l1_avg`.

# KG: APT_v26_A6_2026-04-21, MethodologyConfig_default_v26, MIC_v1

---

## ✅ Migration Status (2026-05-22)

- **Status**: MIGRATED (was `SCAFFOLD_BODY_MIGRATION_PENDING` 2026-05-22 morning).
- **Source**: was at `SKILLS/apt/SKILL.md` lines 25-40 (`§🎛 v26 A6 Resolve-Only Directive`).
- **Migrated by**: user lead "둘다 ㄱ" + "apt-magic-resolve body migration first" 2026-05-22.
- **Closes (partial)**: `challenge-apt-fix2-srp-label-mislabel-2026-05-22` SCAFFOLDED_BODY_MIGRATION_PENDING → 1/4 책무 본문 분해 완료.
- **Cascade plan**: 다음 migration 순서 = apt-autoflow-guard → apt-lens-enforce → apt-orchestrator.

## 책무 boundary

본 skill 의 변경 이유 (SRP single reason for change) = **KG MethodologyConfig schema 변경**. magic number 의 cfg 값 변경 시 본 skill 의 cypher snippet 만 영향 (SKILL.md prose hardcode 없음). 다른 책무 (phase orchestration / lens enforce / autoflow guard) 변경 시 본 skill 무영향.

# KG: scaffold-apt-skill-decomposition-2026-05-22, migration-apt-magic-resolve-body-2026-05-22
