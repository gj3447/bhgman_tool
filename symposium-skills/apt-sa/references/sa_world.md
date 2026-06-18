# SA World Reference — REDIRECTED (2026-05-11 PD v3 split)

> 이 파일은 PD v3 refactor (2026-05-11)로 split되었음. 본문은 다음 경로로 이동:

| 옛 섹션 | 새 위치 |
|---|---|
| §1 Progressive Disclosure 3단계 | [`../../_common/progressive_disclosure.md`](../../_common/progressive_disclosure.md) |
| §2 Context Budget 할당 공식 | [`../../_common/context_budget.md`](../../_common/context_budget.md) |
| §3 apt-progress.md 초기 포맷 템플릿 | [`progress_template.md`](progress_template.md) |
| §4 SA → SP 핸드오프 체크리스트 | [`handoff_to_sp.md`](handoff_to_sp.md) |
| §5 SA 관련 에러 사례 (E-SA1/2/3) | [`routing_decisions.md`](routing_decisions.md) 의 anti-pattern 절 + [`../../_common/error_pattern_template.md`](../../_common/error_pattern_template.md) |
| §6 SA 관련 Validation Queries (V-SA1-4) | [`routing_decisions.md`](routing_decisions.md) 의 검증 query 절 + [`../../_common/validation_query_pattern.md`](../../_common/validation_query_pattern.md) |

---

### 왜 split?

- 단일 파일 → drift 시 모든 phase가 영향. 4 phase의 *_world.md가 *동일 개념을 중복 정의*하던 상태.
- _common/ 추출 → drift 가능성 0 (한 곳만 갱신).
- routing_decisions / progress_template / handoff_to_sp → SA 고유 내용만 보존, phase-local refactor 시 cross-phase 영향 없음.

### KG 정전

- `ad-symposium-monorepo-git-mirror-dgx-runtime-2026-05-11` ArchitectureDecision
- `sv-apt-sa-v27.3.0-2026-05-11` SkillVersion bump (PD v3 split 반영)

# KG: ATOM_apt_sa_world_redirected
