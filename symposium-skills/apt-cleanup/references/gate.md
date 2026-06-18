# apt-cleanup — Phase 6 Gate Cypher (Hook + override flow)

> **Lazy-load reference** — read when gate fail / override / escalation 시.
> Parent: [`../SKILL.md`](../SKILL.md).

---

## Gate Check Hook (Cypher)

### 1. 진입 체크 (SCW 완료 verify)

```cypher
// Phase 6 entry: 직전 SCW 가 fulfilled 상태여야
MATCH (cycle:AptCycle {name: $cycle_id})-[:HAS_PHASE]->(scw:AptPhase {name: 'SCW'})
WHERE scw.status = 'fulfilled'
RETURN scw.name AS scw_phase, scw.completed_at AS scw_done
// scw_done IS NULL → BLOCK Phase 6 entry
```

### 2. Ratchet 비교 (이전 N=5 사이클)

```cypher
MATCH (cur:CleanupRun {cycle_id: $current_cycle})
MATCH (prev:CleanupRun) WHERE prev.completed_at < cur.completed_at
WITH cur, prev ORDER BY prev.completed_at DESC LIMIT 5
WITH cur, collect(prev) AS history
WITH cur, history,
     reduce(m=0, p IN history | CASE WHEN p.fat_files_count > m THEN p.fat_files_count ELSE m END) AS prev_fat_max,
     reduce(m=0.0, p IN history | CASE WHEN p.duplication_ratio > m THEN p.duplication_ratio ELSE m END) AS prev_dup_max,
     reduce(m=0, p IN history | CASE WHEN p.vulture_dead_count > m THEN p.vulture_dead_count ELSE m END) AS prev_dead_max,
     reduce(m=0, p IN history | CASE WHEN p.lizard_loc_max > m THEN p.lizard_loc_max ELSE m END) AS prev_loc_max
RETURN
  cur.fat_files_count <= prev_fat_max  AS fat_ratchet_ok,
  cur.duplication_ratio <= prev_dup_max AS dup_ratchet_ok,
  cur.vulture_dead_count <= prev_dead_max AS dead_ratchet_ok,
  cur.lizard_loc_max <= prev_loc_max AS loc_ratchet_ok,
  cur.tach_cycles = 0 AS adp_ok,
  cur.deptry_issues = 0 AS deps_ok
```

### 3. Commit ratio (refactor:feature)

```cypher
// 이전 SCW 사이클의 git commit type 분포
MATCH (c:GitCommit) WHERE c.committed_at >= datetime() - duration('P14D')
WITH c.commit_type AS type, count(c) AS n
WITH collect({type: type, n: n}) AS dist
WITH dist,
     [d IN dist WHERE d.type = 'feat'][0].n AS feat_n,
     [d IN dist WHERE d.type = 'refactor'][0].n AS refactor_n
RETURN feat_n, refactor_n,
       toFloat(refactor_n) / (feat_n + 0.001) AS ratio,
       toFloat(refactor_n) / (feat_n + 0.001) >= 0.2 AS ratio_ok
```

### 4. Final gate verdict

```cypher
WITH $fat_ratchet_ok + $dup_ratchet_ok + $dead_ratchet_ok + $loc_ratchet_ok
     + $adp_ok + $deps_ok + $ratio_ok AS pass_count
RETURN
  pass_count = 7 AS gate_passed,
  CASE WHEN pass_count = 7 THEN 'PASS'
       WHEN pass_count >= 5 THEN 'NEEDS_REFACTOR'
       ELSE 'BLOCK'
  END AS verdict
```

---

## Decision logic

| pass_count | verdict | action |
|---|---|---|
| 7/7 | **PASS** | Phase 6 통과 → meta-review 진입 |
| 5-6/7 | **NEEDS_REFACTOR** | RefactorSpec 발아 + 사용자 보고. 다음 cycle 시작 가능하나 refactor 권고 |
| ≤4/7 | **BLOCK** | meta-review 진입 차단. 즉시 refactor 사이클 강제 |

---

## CleanupRun 결과 기록

```cypher
MERGE (cr:AbstractNode:CleanupRun {name: 'cleanup-' + $cycle_id})
SET cr.cycle_id = $cycle_id,
    cr.fat_files_count = $fat,
    cr.duplication_ratio = $dup,
    cr.vulture_dead_count = $dead,
    cr.lizard_loc_max = $loc,
    cr.tach_cycles = $tach,
    cr.deptry_issues = $deps,
    cr.commit_ratio = $ratio,
    cr.gate_passed = $gate_passed,
    cr.verdict = $verdict,
    cr.recommendations = $recs,
    cr.completed_at = datetime()
WITH cr
MATCH (cycle:AptCycle {name: $cycle_id})
MERGE (cycle)-[:HAS_CLEANUP]->(cr)
WITH cr
// RefactorSpec 발아 (verdict=NEEDS_REFACTOR or BLOCK)
FOREACH (_ IN CASE WHEN $verdict <> 'PASS' THEN [1] ELSE [] END |
  MERGE (rs:RefactorSpec {name: 'refspec-' + $cycle_id})
  SET rs.recommendations = $recs,
      rs.severity = CASE WHEN $verdict = 'BLOCK' THEN 'CRITICAL' ELSE 'HIGH' END,
      rs.created_at = datetime()
  MERGE (cr)-[:RECOMMENDS]->(rs)
)
```

---

## Override flow (사용자 명시 skip)

```bash
/apt-cleanup --skip-gate --override-reason="hot-fix urgency, refactor scheduled in next sprint"
```

```cypher
MATCH (cr:CleanupRun {cycle_id: $cycle_id})
SET cr.gate_skipped = true,
    cr.skip_reason = $reason,
    cr.skip_authorized_by = $human_user,
    cr.skipped_at = datetime()
MERGE (adl:AptDecisionLog {name: 'adl-cleanup-skip-' + $cycle_id})
SET adl.action = 'CLEANUP_GATE_OVERRIDE',
    adl.cycle_id = $cycle_id,
    adl.human_reason = $reason,
    adl.severity = 'AUDIT'
MERGE (cr)-[:OVERRIDDEN_BY]->(adl)
```

→ override 는 *audit log* 영구 기록. 누적 override > 3 → meta-review 자동 alert.

---

## Escalation (반복 fail)

```cypher
// 최근 5 사이클 verdict 패턴
MATCH (cr:CleanupRun) WHERE cr.completed_at >= datetime() - duration('P7D')
WITH cr.verdict AS v ORDER BY cr.completed_at DESC LIMIT 5
WITH collect(v) AS recent_verdicts
WITH recent_verdicts,
     size([v IN recent_verdicts WHERE v = 'BLOCK']) AS blocks,
     size([v IN recent_verdicts WHERE v = 'NEEDS_REFACTOR']) AS needs_refactor
RETURN
  CASE
    WHEN blocks >= 3 THEN 'ESCALATE_TO_HUMAN — 3+ BLOCK in 5 cycles, structural decay'
    WHEN needs_refactor >= 5 THEN 'WARN — refactor backlog accumulating'
    ELSE 'OK'
  END AS status
```

---

## meta-review 통합

```cypher
// apt-meta-review Phase 5 trigger 시 cleanup history 검토
MATCH (cycle:AptCycle {name: $cycle_id})-[:HAS_CLEANUP]->(cr:CleanupRun)
RETURN cr.gate_passed, cr.verdict, cr.recommendations
```

- gate_passed=false → meta-review lesson 자동 추가 ("이번 사이클 cleanup gate fail")
- 누적 NEEDS_REFACTOR 패턴 → SKILL.md history 갱신

---

# KG: lesson-apt-phase6-cleanup-missing-2026-04-28
