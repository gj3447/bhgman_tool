---
name: tpa
version: 0.4
description: >
  TPA orchestrator — APT 역순 사이클 순수 디스패처. 실제 로직은 4 sub-skill에.
  /tpa <path> 또는 /tpa --audit <anchor> 또는 /tpa --status.
  # KG: ATOM_Skill_tpa_orchestrator_v04, TPA_methodology_v04
---

<!-- KG: TASK_AS_TPA_orchestrator_pure, CONTRACT_AS_TPA_orchestrator_pure -->

## Dispatch Table

| Input | Action |
|---|---|
| `/tpa <path>` | `/tpa-tcw <path>` → `/taliban` → `/tpa-tt` → `/taliban` → `/tpa-tp` → `/taliban` → `/tpa-ta` |
| `/tpa --audit <anchor>` | `/tpa-ta --audit <anchor>` (drift 재감사만) |
| `/tpa --status` | `MATCH (e:TPA_Execution) WHERE e.phase_current <> 'COMPLETE' RETURN e ORDER BY e.started_at DESC LIMIT 5` |

## 4 Sub-Skill (phase 로직은 각자)

- `/tpa-tcw` — Phase 1/4 (시작, pre-gate 없음)
- `/tpa-tt` — Phase 2/4 (TCW gate 후)
- `/tpa-tp` — Phase 3/4 (TT gate 후)
- `/tpa-ta` — Phase 4/4 (TP gate 후, 최종 anchor)

Hook (`apt-gate-check.sh`)가 phase 순서 강제.

## Migration

v0.3 → v0.4 가이드: `MIGRATION_v0.3_to_v0.4.md` 참조. 기존 `/tpa <path>` 호출 동작 유지.
