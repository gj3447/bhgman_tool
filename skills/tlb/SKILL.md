---
name: tlb
kg_ref: ATOM_Skill_tlb_alias
version: "2.0.0"
channel: stable
description: >
  `/taliban`의 짧은 별칭(alias). `/tlb <target>` == `/taliban <target>`.
  사용법: `/tlb SPAN_xxx`, `/tlb CONTRACT_yyy`, `/tlb --lens solid 대상`.
  Invoke when: 적대적 검증 빠르게 실행. 나생문 방법론과 동일.
  실제 로직(렌즈셋 플러거블 + 재배맨 SubagentTaskSpec 씨앗 기반 자동 출격)은
  /taliban SKILL.md를 그대로 따른다. 본문 복제 없음 (drift 방지).
  # KG: ATOM_Skill_taliban, alias-of-taliban
---

# /tlb — `/taliban` alias

> `/tlb`는 `/taliban`의 짧은 별칭이다. 로직 중복 없음.

## 사용법

```
/tlb <target>                    → 기본 constitutional 9-lens 검증
/tlb <target> --lens mathematical → 113-lens 수학적 메타 검증
/tlb <target> --lens solid        → SOLID 5-lens 검증
/tlb <target> --lens <any>        → KG에 등록된 임의 렌즈셋
```

## 실행 지침

`$ARGUMENTS`를 그대로 `/taliban` SKILL.md로 넘겨 검증 사이클 실행.

**본문**: `/Users/lagyeongjun/CD/SERVER/.claude/skills/taliban/SKILL.md`

Claude는 본 skill 진입 시 **즉시 `/taliban` SKILL.md를 Read**하고, `--lens` 파라미터에 맞는 LensSet의 재배맨 SubagentTaskSpec 씨앗을 KG에서 조회하여 병렬 출격.

# KG: ATOM_Skill_taliban, alias-of-taliban
