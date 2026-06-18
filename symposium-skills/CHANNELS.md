# SYMPOSIUM/SKILLS Release Channels

> Plan-6 phase 1 (consensus seed `cg-skillver-trunk-feature-flag-progressive`).
> Skill Creator 2.0 통합 시 4-mode pipeline (Create/Eval/Improve/Benchmark) 자동화.

## Channel 정의

| Channel        | 의미                              | 호환성 보장        | breaking change 정책 |
|----------------|-----------------------------------|--------------------|----------------------|
| `experimental` | 실험 단계, RFC/PoC                | 없음               | 자유                 |
| `beta`         | 안정성 검증, prerelease ring      | 시도 (best-effort) | 사전 공지 후만       |
| `stable`       | 운영 채택 채널 (default)          | SemVer 보장        | Major bump 시에만    |

## Kill-switch

experimental + beta는 환경 변수로 비활성화 (Anthropic 공식 패턴, finding D33):

```bash
export CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS=1
```

설정 시 stable channel만 로드 — CI/prod 환경 권장.

## Channel 전환 절차

```
experimental --[7일 + eval 통과 + manifest-check OK]--> beta
beta         --[14일 + 외부 consumer ≥1 + breaking 0건]--> stable
stable       --[regression 즉시]--> beta (역방향 강등)
```

## Frontmatter 필드

```yaml
---
name: prom
kg_ref: ATOM_Skill_prom_alias
version: 3
channel: stable          # experimental | beta | stable (default: stable)
---
```

`channel:` 누락 시 `stable`로 간주 (점진 도입).

## Validator 검증

`skill-validator.sh --manifest-check`가 channel 필드도 frontmatter ↔ MANIFEST 일치 검증.

## 현재 상태 (2026-04-26 v26.0.0)

27/27 skills = `stable` (5대 무기 v22~v26 모두 운영 채택 단계).

# KG: cg-skillver-trunk-feature-flag-progressive-2026-04-26, ATOM_SkillsChannelPolicy_v1
