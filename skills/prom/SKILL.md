---
name: prom
kg_ref: ATOM_Skill_prom_alias
version: "3.0.0"
channel: stable
provenance: AI_DERIVED_FROM_USER_PRIMARY  # SKILL.md = AI engineering; underlying methodology = user-primary mythology (12 apostles + 5 weapons). Per PseudepigraphaValidationGate-v1-2026-04-30.
description: >
  `/prometheus`의 짧은 별칭(alias). `/prom <N> <problem>` == `/prometheus <N> <problem>`.
  사용법: `/prom 16 "문제"`, `/prom 100 "TOE"`, `/prom "간단한 문제"`.
  Invoke when: `/prometheus`를 빨리 치고 싶을 때. 프로메테우스 방법론 트리거와 동일.
  실제 로직(8단계 사이클, N-파라미터화, JSON 계약, UNWIND 배치, 충돌 탐지)은
  /prometheus SKILL.md를 그대로 따른다. 본문 복제 없음 (drift 방지).
  # KG: ATOM_Skill_prometheus, alias-of-prometheus
---

# /prom — `/prometheus` alias

> `/prom`은 `/prometheus`의 짧은 별칭이다. 로직 중복 없음.

## 사용법

```
/prom 3 "간단한 문제"      → N=3 (== /prometheus 3 ...)
/prom 16 "중간 문제"       → N=16 (4×4 axis 교차)
/prom 100 "TOE"            → N=100 (10×10 axis 교차)
/prom "문제만"              → auto_estimate (3~20)
```

## 실행 지침

`$ARGUMENTS`를 그대로 `/prometheus` SKILL.md의 Step 0으로 넘겨 처리한다.

**본문(Step 0 ~ Step 7, 재배맨 바인딩 등)은**:
`/Users/lagyeongjun/CD/SERVER/.claude/skills/prometheus/SKILL.md`

Claude는 본 skill 진입 시 **즉시 `/prometheus` SKILL.md를 Read**하여 전체 사이클을 실행한다. `/prom`은 라우팅 단축어일 뿐, 별도 로직 없음.

## 왜 별칭만 분리했나

- **DRY**: SKILL.md 본문 복제 시 drift 발생 → 단일 정본 유지
- **Claude Code 규약**: 슬래시 커맨드 = skill 디렉토리명 1:1 → `/prom`을 위해 최소 디렉토리 필요
- **얇은 래퍼**: 40줄 이내 유지

# KG: ATOM_Skill_prometheus
