# TPA Migration Guide: v0.4 → v1.0

> # KG: ATOM_Skill_tpa_orchestrator_v10

## 변경 요약

| 항목 | v0.4 | v1.0 |
|---|---|---|
| SKILL.md | 31줄 순수 디스패처 | 300줄+ 풀 orchestrator |
| Hard Rules | 없음 | TR1-TR15 (APT HR 역분석) |
| Configuration | 없음 | tpa-config.yaml |
| Phase Detection | 없음 | Cypher 자동 감지 |
| Flow Control | 단순 순차 | 분기별 독립 + gate |
| Feedback Loop | 없음 | 오답노트 7단계 루프 |
| Post-gate Reflection | 없음 | 필수 (TR9) |
| 5대 본질 참조 | MIC 언급만 | 상세 매핑 + 참조 테이블 |
| References | 1 파일 | 4 파일 (hard_rules, feedback_loop, phase_detection, shared_template) |
| `--lessons` 명령 | 없음 | 신규 |

## 하위 호환

- `/tpa <path>` 호출 동작 100% 유지
- `/tpa --audit <anchor>` 유지
- `/tpa --status` 유지
- 신규: `/tpa --lessons <target>`

## Sub-Skill 영향

각 sub-skill (tpa-tcw/tt/tp/ta)에 추가 필요:
1. Post-gate reflection 섹션 (TR9)
2. Lesson 자동 생성 로직 (TR10)
3. version 업데이트: 0.4 → 1.0

## KG 업데이트 필요

```cypher
// TPA v1.0 orchestrator 노드 갱신
MERGE (skill:AbstractNode {name:'ATOM_Skill_tpa_orchestrator_v10'})
SET skill.version='1.0', skill.description='TPA v1.0 — APT v24 역분석, 5대 본질 참조, 오답노트 피드백 루프',
    skill.updatedAt=datetime()

// 기존 v0.4 노드 아카이브
MATCH (old {name:'ATOM_Skill_tpa_orchestrator_v04'})
SET old.status='ARCHIVED', old.supersededBy='ATOM_Skill_tpa_orchestrator_v10'
```

## 백업

- `_backup_v03/SKILL.md` — v0.3 원본
- `_backup_v04_SKILL.md` — v0.4 원본
