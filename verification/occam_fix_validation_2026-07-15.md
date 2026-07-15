# Occam fix validation — 73b89aa 라이브 substrate 실측 (2026-07-15)

> 사후검증: P4 occam 수정(`73b89aa`: `:N` line-anchor disk-존재 판정 + str/DateTime 크래시 봉합)이
> **라이브 airo KG(309,202노드)에서 실제로 precision을 회복시켰는지** dry-run 실측.
> **가정 아님 — 측정.** KG write = **0** (apply=false, write_cypher=None, read-only guard).
> 선행 falsifier: `SYMPOSIUM/verification/falsifier_occam_dedupe_2026-07-15.md` (수정 전 precision 1.7% + full-scan 크래시).

## 결론 (한 줄)

**교차병목 3개 전부 실측 해소됨.** disk-orphan precision **4.1%(census)/1.7%(falsifier sample) → 100%**,
full-scan 크래시 **재현→해소**, `:N` false-orphan **94건 → 0건**. false-negative 회귀 없음
(진짜 orphan 4건 그대로 검출). KG 변경 0.

## 측정 세팅 (재현 가능)

| 항목 | 값 |
|---|---|
| 라이브 KG | airo `bolt://10.147.17.7:55200` (309,202 nodes, SourceCodeNode 2,630) |
| 접속 우회 | uv cpython-3.14 socket이 ZT `feth` 인터페이스에서 `EHOSTUNREACH` (nc/system-py는 정상). `socat TCP-LISTEN:127.0.0.1:15200 → 10.147.17.7:55200` loopback relay 경유 |
| 코드 (after) | `GIT/harden-bhgman_tool` @ `73b89aa` (fixed), `engine/occam/` |
| 코드 (before) | git worktree @ `73b89aa^`(`cbdde0f`) — `_disk_key` 부재, `recency_key` 무-str() |
| 실행 | `run_occam(run_cypher, write_cypher=None, scope='bhgman_tool', apply=False, repo_root='/Users/lagyeongjun/CD/bhgman_tool')` |
| repo_root | `/Users/lagyeongjun/CD/bhgman_tool` (falsifier와 동일) |
| write 가드 | run_cypher가 write-clause(`\b(CREATE\|MERGE\|DELETE\|DETACH\|REMOVE\|SET\|DROP)\b`) 검출 시 raise. 실행 cypher 2개/run, 전부 read (`all_reads_only=True`) |

**동일 라이브 스냅샷**에서 before/after 코드만 교체(둘 다 scanned=273 in-scope). KG drift 통제됨.

## 실측 결과

### 1. disk-orphan precision (핵심)

독립 오라클: 각 flag된 orphan의 KG경로 → `:N` strip → 실파일 `os.path.isfile` (occam 자체
disk_paths 집합에 의존하지 않는 별도 resolver). precision = 진짜부재 / 전체flag.

| | flag된 orphan | 진짜부재(true) | 실존(false-positive) | **precision** |
|---|---|---|---|---|
| **BEFORE** (census, 98전수) | 98 | 4 | 94 | **4.1%** |
| BEFORE (falsifier sample 60) | 60 | 1 | 59 | 1.7% |
| **AFTER** (census, 4전수) | 4 | 4 | 0 | **100%** |

- census(4.1%)와 falsifier sample(1.7%)은 소표본 분산 내 일치 — 둘 다 "수정 전 ≈96–98% false-positive" 확증.
- 표본 요건 충족: before는 전수 98(≥50), after는 전 4건(총량 4).

### 2. full-scan 크래시 (str/DateTime 봉합)

`run_occam(scope=None, repo_root=None)` = 전체 SourceCodeNode dedup(`_pick_current` → `_current_rank` tuple `>`).

| | 결과 |
|---|---|
| **BEFORE** | **CRASH** `TypeError: '>' not supported between instances of 'str' and 'DateTime'` (falsifier와 동일) |
| **AFTER** | **OK** — scanned=2265, dup_groups=8, superseded_candidates=8, 무크래시 |

→ `recency_key` str() 강제(occam_models.py) 실효 확인.

### 3. `:N` false-orphan 해소 (핵심 fix)

| | `:N` 앵커 보유 flag | 그중 base 파일 실존(=`:N`발 false-orphan) |
|---|---|---|
| **BEFORE** | 95 / 98 | **94** |
| **AFTER** | 1 / 4 | **0** |

→ `_disk_key`(normalize_path + `:N` strip, disk-존재 판정 전용) 실효 확인.
AFTER의 유일한 `:N` 보유 flag = `evolve_loop_max_experiment.py:19` — **`:N` 떼도 base 파일이
진짜 부재**라 정당하게 orphan. **fix가 `:N` 노드를 맹목 억제하지 않음**(false-negative 방어).

### 4. false-negative 회귀 없음 (집합 동일성)

**AFTER의 4 orphan == BEFORE의 진짜부재 4 orphan** (집합 완전일치, diff 양쪽 공집합):

```
engine/longinus_drift_audit/tests/conftest.py     (ABSENT, dir 존재/파일 없음)
engine/efficacy/evolve_loop_max_experiment.py:19  (ABSENT, 파일 전삭제)
engine/eureka/tests/conftest.py                    (ABSENT)
engine/longinus_drift/tests/conftest.py            (ABSENT)
```

→ 독립 `ls` 재확인: 4건 전부 disk 부재. fix는 94 false-positive만 제거, 진짜 4건은 보존.

### BEFORE `:N` false-orphan 표본 (fix가 걷어낸 것들 — 전부 base 파일 실존)

```
engine/cli/commands.py:250   → EXISTS engine/cli/commands.py   (:250,:818 = 같은 파일 다른 심볼)
engine/cli/commands.py:818   → EXISTS engine/cli/commands.py
engine/eureka/oracle_lens.py:12  → EXISTS engine/eureka/oracle_lens.py
engine/jaebaeman/planner.py:14   → EXISTS engine/jaebaeman/planner.py
engine/jaebaeman/ab_compare.py:6 → EXISTS engine/jaebaeman/ab_compare.py
engine/efficacy/drift_oracle.py:13 → EXISTS engine/efficacy/drift_oracle.py
```

## KG write = 0 (검증)

- 양 run: `apply=False`, `write_cypher=None`, `dry_run=True`, `applied=0`, `planned_cyphers=0`, `all_reads_only=True`, cyphers_executed=2(전부 read).
- 라이브 재확인: 총노드 309,202 → 309,202 (불변), 최근 15분 supersede write = 0.
- covenant archive 조차 안 함 (순수 측정).

## 판정

**수정 전(1.7% sample / 4.1% census) → 수정 후 100%.** 교차병목3(occam full-KG 크래시 / `:N`
disk-stat robustness / — KG `:N`은 정당 앵커라 데이터 건드림 아님) 중 **occam 측 2개(#1 크래시, #3 `:N`
robustness) 라이브에서 실측 해소.** precision 회복은 데이터 재작성 없이 순수 코드 fix로 달성 —
`:N` 심볼 앵커(정당한 KG 데이터)를 보존하면서 disk-존재 판정만 파일-단위로 교정한 것이 핵심.
남은 4 orphan은 진짜 삭제 파일(conftest 재구조화 + evolve_loop 실삭제)이라 longinus escalate 대상으로 정당.

**단서**: 라이브 MCP 서버 프로세스는 in-memory 구코드 → `mcp__bhgman-tool__occam_dedupe`는 서버
리로드 전까지 여전히 98 반환(본 검증은 fixed 코드 직접 실행). 배포 반영은 서버 재시작 필요.
