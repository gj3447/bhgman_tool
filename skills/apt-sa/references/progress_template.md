# apt-progress.md Initial Format (SA Phase-Specific)

> SA 완료 시점에 *반드시 생성*해야 하는 세션 연속성 파일. 다음 phase가 cold-context로 진입해도 즉시 작업 재개 가능.

---

## 표준 템플릿

```markdown
# APT Progress: {project_name}

## Anchor: {sa_name}
## Domain: {domain}
## Status: active
## Work Kind: {NEW|EXTEND|MAINTENANCE}                      ← A15 분류 결과
## Phase Activation Matrix: {FULL|SHORT_CIRCUIT|SKIP_TO_ST_DRIFT}  ← A15 라우팅
## Created: {datetime ISO 8601}
## Last Updated: {datetime ISO 8601}
## Context Budget: total={total}K, per_span={per_span}K

---

### Completed Spans
(none yet)

### In Progress
- {current_span}: SA complete, ready for SP

### Blocked
(none)

### KG Stats
- SemanticAnchor: {sa_name}
- L1 Spans: {count}
- INFORMED_BY links: {count}
- A15 work_kind: {work_kind}

### Next Steps
1. SP Phase: {first_branch} 분해 시작
2. 각 L1 Span에 INFORMED_BY >= {cfg.density_min_informed_by} 확보
3. (MAINTENANCE인 경우) ST drift detection 모드 — SP 우회

### Session Log
- [{datetime}] SA Phase: anchor {sa_name} {created|reused|branched}
- [{datetime}] A15 work_kind: {NEW|EXTEND|MAINTENANCE}, matrix: {mode}
- [{datetime}] L1 Spans 발견: {count} (from KG L1 query)
- [{datetime}] Context Budget 할당: total={total}, per_span={per_span}
```

---

## 필드 의무

| 필드 | mandatory | 비어있을 때 효과 |
|---|---|---|
| `Anchor` | yes | SA 진입 미완료 — V-SA3 트리거 |
| `Domain` | yes | 도메인 미정 → SP 분해 시 INFORMED_BY 후보 식별 불가 |
| `Status` | yes | `active`/`archived`/`suspended` 중 하나. NULL 금지 |
| `Work Kind` | yes (v27 A15) | 분류 누락 → V-SA5 트리거 |
| `Phase Activation Matrix` | yes (v27 A15) | matrix 미지정 → SP에서 자동 추론 (위험) |
| `Context Budget` | yes | 미할당 → V-SA4 트리거 |
| `Created` / `Last Updated` | yes | ISO 8601 UTC. timezone 누락 시 검증 실패 |
| KG Stats `INFORMED_BY links` | optional at SA, mandatory at SP→ST gate | SP가 알아서 채움 |

---

## Phase Transition 시 압축

SA → SP 핸드오프 시 apt-progress.md의 *Session Log* 절은 압축:
- 보존: 마지막 3개 entry (created/work_kind 분류/L1 발견)
- 제거: KG 탐색 candidate 비교 entry, 폐기된 routing 후보 entry

자세한 압축 규약은 [_common/phase_transition_compaction.md](../../_common/phase_transition_compaction.md).

---

## 파일 위치 컨벤션

```
<project_root>/
├── apt-progress.md                  ← canonical (git 추적)
├── apt-progress.{timestamp}.md      ← phase 종료 시 snapshot (gitignore 옵션)
└── ...
```

`apt-progress.md`는 *git tracked*. 매 phase 전환 시 commit하여 history 유지. 세션 재개 시 `git log apt-progress.md` 로 reconstruction 가능.

---

## anti-pattern

[_common/error_pattern_template.md](../../_common/error_pattern_template.md) 양식:

### E-SA-Progress-1: apt-progress.md 미생성
**Context:** SA Phase 완료 표시했지만 apt-progress.md 파일 없음.
**Lesson:** 세션 연속성 = SA 핵심 산출. 파일 없으면 다음 세션 cold-start 시 KG 풀-탐색 필요.
**Guard:** SA → SP 핸드오프 체크리스트 #6 — 파일 존재 확인 cypher (filesystem hook via `apt-progress-md-exists.sh`).

### E-SA-Progress-2: Last Updated 갱신 누락
**Context:** SA에서 L1 Span 추가/Context Budget 변경했지만 `Last Updated` 갱신 안 함.
**Lesson:** stale 파일 → 다음 phase가 옛 상태로 재개. drift 가능.
**Guard:** apt-progress 수정 시 자동 `## Last Updated: $(date -u +%FT%TZ)` 갱신 (sed 또는 pre-commit hook).

### E-SA-Progress-3: Work Kind 누락 (v27 A15)
**Context:** Work Kind / Phase Activation Matrix 필드 비어있음.
**Lesson:** A15 라우팅이 phase 활성화 전체 결정. 미기재 → SP가 잘못 추론 → MAINTENANCE인데 FULL 진입.
**Guard:** SA 종료 cypher가 `created_via_work_kind` 속성 SA에 SET 필수 (V-SA5).

# KG: APT_SA_progress_template_canonical
