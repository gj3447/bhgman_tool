---
name: 88-taliban
kg_ref: ATOM_Skill_88taliban
version: "3.0.0"
channel: stable
description: >
  `/taliban --lens mathematical`의 짧은 별칭(alias).
  `/88-taliban <target>` == `/taliban <target> --lens mathematical`.
  수학적 렌즈 113개로 임의 대상을 적대적 검증.
  실제 로직은 /taliban SKILL.md를 그대로 따른다. 본문 복제 없음 (drift 방지).
  # KG: ATOM_Skill_88taliban, alias-of-taliban
---

# /88-taliban — `/taliban --lens mathematical` 별칭

> **이 스킬은 thin alias다.** 모든 로직은 `/taliban` 프레임워크에 있다.
> 본문 복제 = drift 유발. 하지 마라.

## 사용법

```
/88-taliban <target> [--depth quick|standard|deep]
```

**동일 명령:**
```
/taliban <target> --lens mathematical [--depth quick|standard|deep]
```

## 실행

1. `/taliban` SKILL.md 로드
2. `--lens mathematical` 자동 설정
3. 나머지 전부 Naesengmoon 프레임워크 프로토콜 따름

## MIC Binding

**IS slot**: `MetaVerifier` (MIC_v1.currentConcrete = "88-Naesengmoon")
→ 실체는 Naesengmoon 프레임워크 + LensSet:mathematical

# KG: ATOM_Skill_88taliban, alias-of-taliban, lensset-mathematical
