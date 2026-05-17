# SKILLS/_common/ — Cross-Skill Shared References

> APT phase skill (apt-sa/-sp/-st/-scw) + apt-cleanup + apt-meta-review가 공통으로 참조하는 cross-cutting 패턴 단일 소스.
>
> **원칙**: phase-specific 내용은 각 skill의 `references/`에 두고, phase 간 공통 개념만 여기 둔다. drift 방지 위해 *한 곳만 갱신*.

---

## 파일 목록

| 파일 | 다루는 개념 | 참조 phase |
|---|---|---|
| `progressive_disclosure.md` | L1/L2/L3 lazy load 패턴 + 토큰 예산 분리 | 모든 phase |
| `context_budget.md` | depth별 토큰 예산 공식 (cfg slot) + Context Rot 방지 | sa, sp, st, scw |
| `phase_transition_compaction.md` | phase 간 핸드오프 시 압축 규약 | sa→sp, sp→st, st→scw |
| `validation_query_pattern.md` | V-XX1/2/3 검증 쿼리 작성 템플릿 + naming convention | 모든 phase |
| `error_pattern_template.md` | E-XX1/2/3 에러 사례 기록 템플릿 (Context/Lesson/Guard) | 모든 phase |
| `contract_lifecycle_fsm.md` | AptContract 상태 머신 (Draft→Active→Fulfilled→Amended/Archived) + Kafka 이벤트 | st, scw |
| `kafka_event_convention.md` | Kafka payload 표준 형식 (event_type/timestamp/correlation_id/agent/payload) | 모든 phase |

---

## 참조 방법

phase SKILL.md 본문에서:

```markdown
> Progressive Disclosure 3-tier는 [_common/progressive_disclosure.md](../_common/progressive_disclosure.md) 참조.
> SA 고유 라우팅은 [references/sa_specific_routing.md](references/sa_specific_routing.md).
```

phase references/*.md 안에서:

```markdown
> 본 에러 사례 형식은 [_common/error_pattern_template.md](../../_common/error_pattern_template.md)의 Context/Lesson/Guard 3절 양식을 따름.
```

---

## 갱신 규약

- *공통 개념이 진화*하면 본 폴더만 수정 → 모든 phase가 자동으로 최신 버전 참조 (drift 0).
- *phase 고유 변형*이 등장하면 phase references/에 별도 파일 + 본문에 "변형 사유" 명시.
- *변형이 phase 3개 이상에서 반복*되면 다시 본 폴더로 끌어올림 (refactor to _common).

# KG: ATOM_Skill_apt_common_refs, ad-symposium-monorepo-git-mirror-dgx-runtime-2026-05-11
