---
name: example-apt-sp-after-v27-migration
kg_ref: ATOM_Skill_apt_sp
version: "27.0.0"
channel: stable
description: >
  apt-sp Phase 2 SemanticPyramid — v27 A6.1 magic externalization 적용 후 예시.
  본문에 magic number inline 0개. cfg.X 마커로만 참조.
  # KG: rfc-apt-v26-A6.1-magic-selective-externalization-2026-04-30
---

# apt-sp v27 — N-ary 분해와 sweet spot

## D(S) 재귀 분해 단위

각 Span은 *vibe coding sweet spot* 안에서 atomic이라야 한다:

- 하한: `{{cfg.vibe_coding_sweet_min}}` 줄 (현재 200)
- 상한: `{{cfg.vibe_coding_sweet_max}}` 줄 (현재 500)

상한 초과 시 D(S) 재귀 분해 강제. 하한 미만은 sibling 통합 권장.

## Naesengmoon 적대 검증 게이트

SP→ST 전환 시 `{{cfg.lens_count_constitutional}}`-lens 적대 검증 (현재 9) 만장일치 PASS 필수. 부분 PASS = 차단.

## ST decision area scope

ST Cover Scope = `{{cfg.st_decision_areas}}` 영역 (현재 8) — AST/Workflow/DesignPattern/ProjectStructure/DataFlow/Algorithm/Store/ClassDesign 모두 결정 의무.

## Contract 기본 필드

Contract DTO 기본 `{{cfg.contract_default_fields}}` 필드 (v2에서 nine canonical axis로 확장).

---

# Drift Check (resolver --validate 시)

✓ markers found: 5 (vibe_coding_sweet_min/max, lens_count_constitutional, contract_default_fields, st_decision_areas)
✓ KG 모두 존재 (5 core)
✓ bare inline number 0개 (괄호 안 "(현재 N)"은 reader-facing 안내, 검사 제외)
✓ orphan cfg field 0개

→ RFC A6.1 ACCEPTED 검증 PASS.
