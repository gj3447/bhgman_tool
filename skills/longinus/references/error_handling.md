# longinus — Error Handling

> Lazy-load reference. Parent: [`../SKILL.md`](../SKILL.md).

## 1. AST Parser Failure (G1)

```
IF parser_output empty OR parser unavailable:
  1. parser binary 재설치 시도
  2. 다른 parser 로 fallback (tree-sitter standalone)
  3. grep 단독 사용 금지 — TR4 강제
  4. 최후: Lesson LG_GrepOnlyHarvest 후보 + manual review
```

## 2. Manifest Assertion Fail (G2 — TR5 mirror)

```
IF union(harvested_files) != manifest_files:
  1. set difference 계산: missing = manifest - union
  2. missing files 분석:
     - directory boundary 누락? → file-level partition으로 재분배
     - feature-gated #[cfg]? → 동등 스캔 명시
  3. 보충 agent 출격
  4. 재검증
```

## 3. SHA256 Drift Detection

```
IF baseline != current sha256:
  1. file vs KG mtime 비교
  2. file 이 newer → KG sync
  3. KG 가 newer → file regenerate (sigma_oracle)
  4. 둘 다 변경 → BX PutPut → sigma_oracle
  5. Drift 통계 갱신 + DriftReport
```

## 4. ReferenceSite Missing (G4)

```
IF Contract has no :ReferenceSite:
  1. AST 에서 정확한 file:line 찾음
  2. SHA256 baseline 생성
  3. 7-Layer ReferenceSite 결정화
  4. BOUND_TO edge 생성
  5. TR_LongiusBindingMissing 위반 lesson 결정 (이미 있는 위반)
```

## 5. Coverage Ratio Below Threshold (G7)

```
IF coverage_ratio < 0.8 (default tpa_drift_coverage_ratio_min):
  1. SemanticAnchor.status = 'SUSPENDED' SET 자동 (V9)
  2. Drift 분포 분석:
     - Missing 다수 → 코드 삭제됨 (의도?)
     - Orphan 다수 → 새 코드 미매핑
     - SigMismatch 다수 → API 변경
  3. sigma_oracle: 4 옵션 (RESCAN / ACCEPT_SUSPENDED / DOWNGRADE_THRESHOLD / ABORT)
```

## 6. BX Law Violation (G6)

```
IF GetPut violated (KG 갱신 → code 미반영):
  1. file regenerate from KG (default if KG canonical)
  2. 또는 KG revert (사용자 verdict)

IF PutGet violated (code edit → KG 미반영):
  1. KG sync from file (default)
  2. 또는 file revert (사용자 verdict)

IF PutPut violated (concurrent edit unmerged):
  1. 자동 머지 시도 (conflict-free 인 경우)
  2. conflict → sigma_oracle (위험 — 자동 회피)
  3. 2-way merge log + Lesson
```

## 7. Reverse Orphan Surge (G8)

```
IF reverse_orphan_count / total_symbols > 0.2:
  1. Pattern Library refresh 후보 surface
  2. ResearchProvider 호출 (unknown pattern 탐색)
  3. 사용자 verdict: 새 영역 인정 OR Pattern Library 확장
  4. Lesson 자동 (recovery 가 놓친 영역)
```

## 8. Common Failure Modes

| 증상 | 원인 | 처방 |
|------|------|------|
| sha256 drift 누적 | daemon 비활성화 | launchd plist 활성화 |
| ReferenceSite missing 다수 | TR12 미적용 | TPA ST phase 재실행 |
| coverage 항상 < 0.8 | Pattern Library stale | audit + canonicalization |
| BX PutPut 빈발 | concurrent edit 환경 | branch policy 강화 |
| L7 (crate/script) 누락 | v3.1 신규 schema 미사용 | Crate node 결정화 |

# KG: ATOM_Skill_longinus, fw-longinus-references-apt-parity-2026-05-06
