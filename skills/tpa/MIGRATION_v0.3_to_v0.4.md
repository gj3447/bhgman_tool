<!-- KG: TASK_AS_TPA_migration_md, CONTRACT_AS_TPA_migration_md -->

# TPA v0.3 → v0.4 Migration Guide

**변경 요약**: 모놀리식 `/tpa` SKILL.md (309줄) → APT 거울 구조 (4 sub-skill + pure orchestrator ≤50줄).

## 왜 바뀌었나

v0.3의 `lesson-tpa-surface-scan-shortcut-2026-04-15` (HIGH, unresolved) — Puter TPA 실행을 20분만에 끝내는 shortcut 가능. 원인: **구조적 강제 부재**. SKILL.md에 규칙만 적혀있고 phase gate 강제 없음.

v0.4 = **규칙을 구조로 변환**:
- 4 독립 sub-skill 파일
- `apt-gate-check.sh` Hook이 phase 순서 물리적 차단
- KG `ValidationResult{phase:TCW/TT/TP/TA}` 없이 다음 phase 진입 불가

## 4 Phase ↔ 4 Sub-skill 매핑

| TPA Phase | v0.3 위치 | v0.4 위치 | 거울 APT |
|---|---|---|---|
| **TCW** (TargetCodeWorld) | `/tpa` SKILL.md §Phase1 | `.claude/skills/tpa-tcw/SKILL.md` | `/apt-scw` |
| **TT** (TargetTwin) | `/tpa` SKILL.md §Phase2 | `.claude/skills/tpa-tt/SKILL.md` | `/apt-st` |
| **TP** (TargetPyramid) | `/tpa` SKILL.md §Phase3 | `.claude/skills/tpa-tp/SKILL.md` | `/apt-sp` |
| **TA** (TargetAnchor) | `/tpa` SKILL.md §Phase4 | `.claude/skills/tpa-ta/SKILL.md` | `/apt-sa` |

## 사용자 워크플로우 호환성 (Backward Compat)

**기존 사용자 `/tpa <path>` 호출은 계속 동작.** deprecation 없음.

v0.4 `/tpa` orchestrator는 다음을 수행:
1. 인자 파싱 (`<path>` 또는 `--audit <anchor>` 또는 `--status`)
2. 4 sub-skill로 순차 위임: `/tpa-tcw` → `/tpa-tt` → `/tpa-tp` → `/tpa-ta`
3. 각 phase 종료 시 `/taliban` gate 통과 확인

개별 phase 직접 호출도 가능 (고급 사용):
- `/tpa-tcw <path>` (처음)
- `/tpa-tt` (TCW 통과 후)
- `/tpa-tp` (TT 통과 후)
- `/tpa-ta` (TP 통과 후)

## 제거된 항목

- v0.3 SKILL.md의 phase 내부 로직 → 각 sub-skill로 이동 (동일 로직 유지)
- `"tpa --status"` 플래그 → orchestrator에서 구현 (동작 동일)

## Hook 변경

`.claude/hooks/apt-gate-check.sh`에 3 case 추가:
- `tpa-tt` → TCW Gate 확인
- `tpa-tp` → TT Gate 확인
- `tpa-ta` → TP Gate 확인

tpa-tcw는 시작 스킬이라 pre-gate 없음.

## 호환성 체크리스트

- [x] 기존 `/tpa <path>` 호출 동작 유지
- [x] 기존 `TPA_Execution` KG 노드 구조 무변경
- [x] 기존 `lesson-tpa-*` 노드 무변경 (단, `resolvedByPhase` 속성 추가)
- [x] `TPA_methodology.version` 0.3 → 0.4, `prior_versions=[0.3]` 보존
- [x] v0.3 tpa/SKILL.md는 `_backup_v03` 백업 (선택)

## 롤백 절차 (비상 시)

```bash
# v0.3으로 롤백
cp .claude/skills/tpa/_backup_v03/SKILL.md .claude/skills/tpa/SKILL.md
# Hook 롤백 (git checkout)
git checkout HEAD~1 -- .claude/hooks/apt-gate-check.sh
# KG methodology version
MATCH (m:Methodology {name:'TPA_methodology'}) SET m.version='0.3'
```

## 질문?

- `lesson-tpa-surface-scan-shortcut-2026-04-15` KG 노드에서 v0.4가 어떻게 해결했는지 확인
- `TPA_Skill_v04_Structural_Rebuild` SemanticAnchor에서 8 L1 span 확인
