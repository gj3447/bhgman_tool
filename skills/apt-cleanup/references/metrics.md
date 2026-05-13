# apt-cleanup — CleanupRun KG schema + metric collection

> **Lazy-load reference** — read when metric 분석 / dashboard 작성 시.
> Parent: [`../SKILL.md`](../SKILL.md).

---

## CleanupRun KG schema

```cypher
CREATE CONSTRAINT cleanup_run_unique IF NOT EXISTS
FOR (cr:CleanupRun) REQUIRE cr.name IS UNIQUE;

(:CleanupRun {
  name: String,                    // PK 'cleanup-{cycle_id}'
  cycle_id: String,                // FK to AptCycle
  // Tool metrics
  tach_cycles: Int,                // ADP violation count (target: 0)
  complexipy_max: Int,             // max function complexity
  complexipy_ratchet_passed: Bool,
  lizard_loc_max: Int,             // max function LOC
  lizard_ccn_max: Int,             // max CCN
  fat_func_count: Int,             // function > 50 LOC or CCN > 10
  fat_files_count: Int,            // file > 500 LOC
  fat_files: [String],             // file paths
  duplication_ratio: Float,        // 0.0 - 1.0
  vulture_dead_count: Int,         // dead code units
  vulture_delta: Int,              // delta vs prev cycle
  deptry_issues: Int,              // unused/missing deps
  // Commit metrics
  commit_ratio: Float,             // refactor:feature
  feat_commits: Int,
  refactor_commits: Int,
  // Gate verdict
  gate_passed: Bool,
  verdict: String,                 // PASS | NEEDS_REFACTOR | BLOCK
  pass_count: Int,                 // 0-7 (7 metrics)
  // Recommendations
  recommendations: [String],
  // Override
  gate_skipped: Bool,
  skip_reason: String,
  skip_authorized_by: String,
  // Provenance
  completed_at: DateTime,
  duration_ms: Int,
  hostname: String
})
```

### 관계

```cypher
(cycle:AptCycle)-[:HAS_CLEANUP]->(cr:CleanupRun)
(cr)-[:RECOMMENDS]->(rs:RefactorSpec)
(cr)-[:OVERRIDDEN_BY]->(adl:AptDecisionLog)
(cr)-[:USED_TOOL]->(t:CleanupTool)   // tach/complexipy/lizard/vulture/deptry
```

---

## Metric collection script (`bin/apt-cleanup-collect.py` 후보)

```python
#!/usr/bin/env python3
"""
apt-cleanup Phase 6 metric collector.
Usage: apt-cleanup-collect.py <cycle_id> [--target=path]
"""
import json, subprocess, sys, time, os, socket
from pathlib import Path

cycle_id = sys.argv[1]
target = Path(os.environ.get("CLEANUP_TARGET", "."))

start = time.time()

# Tool 1: tach
tach_proc = subprocess.run(["tach", "check", "--root", str(target)],
                           capture_output=True, text=True)
tach_cycles = tach_proc.stdout.count("cycle")

# Tool 2: complexipy
complexipy_proc = subprocess.run(
    ["complexipy", str(target), "--ratchet", "--check"],
    capture_output=True, text=True
)
complexipy_max = int(complexipy_proc.stdout.split("max=")[-1].split()[0]) if "max=" in complexipy_proc.stdout else 0
complexipy_passed = complexipy_proc.returncode == 0

# Tool 3: lizard
lizard_proc = subprocess.run(["lizard", str(target), "-X"],
                             capture_output=True, text=True)
lizard_data = json.loads(lizard_proc.stdout) if lizard_proc.stdout.strip().startswith("[") else []
fat_funcs = [f for f in lizard_data if f.get("nloc", 0) > 50 or f.get("cyclomatic_complexity", 0) > 10]
lizard_loc_max = max((f.get("nloc", 0) for f in lizard_data), default=0)
lizard_ccn_max = max((f.get("cyclomatic_complexity", 0) for f in lizard_data), default=0)

# Fat files (>500 LOC)
fat_files = []
for py_file in target.rglob("*.py"):
    if py_file.is_file():
        loc = sum(1 for _ in py_file.open(encoding="utf-8", errors="ignore"))
        if loc > 500:
            fat_files.append(str(py_file.relative_to(target)))

# Tool 4: vulture
vulture_proc = subprocess.run(
    ["vulture", str(target), "--min-confidence", "80"],
    capture_output=True, text=True
)
vulture_count = vulture_proc.stdout.count("\n")

# Tool 5: deptry
deptry_proc = subprocess.run(["deptry", str(target)],
                             capture_output=True, text=True)
deptry_issues = deptry_proc.stdout.count("DEP00")

# Commit ratio (last 14 days)
git_proc = subprocess.run(
    ["git", "log", "--since=14.days", "--pretty=%s"],
    capture_output=True, text=True, cwd=target
)
commits = git_proc.stdout.splitlines()
feat_n = sum(1 for c in commits if c.startswith("feat"))
refactor_n = sum(1 for c in commits if c.startswith("refactor"))
ratio = refactor_n / max(feat_n, 1)

# Gate verdict
checks = {
    "adp": tach_cycles == 0,
    "deps": deptry_issues == 0,
    "complexipy_ratchet": complexipy_passed,
    "fat_func_acceptable": len(fat_funcs) <= int(os.environ.get("CLEANUP_FAT_FUNC_THRESHOLD", "10")),
    "fat_files_acceptable": len(fat_files) == 0,
    "vulture_acceptable": vulture_count <= int(os.environ.get("CLEANUP_DEAD_THRESHOLD", "20")),
    "ratio_ok": ratio >= 0.2,
}
pass_count = sum(checks.values())
verdict = "PASS" if pass_count == 7 else ("NEEDS_REFACTOR" if pass_count >= 5 else "BLOCK")

duration_ms = int((time.time() - start) * 1000)

# Output JSON (parent picks up + Cypher write)
result = {
    "cycle_id": cycle_id,
    "tach_cycles": tach_cycles,
    "complexipy_max": complexipy_max,
    "complexipy_ratchet_passed": complexipy_passed,
    "lizard_loc_max": lizard_loc_max,
    "lizard_ccn_max": lizard_ccn_max,
    "fat_func_count": len(fat_funcs),
    "fat_files_count": len(fat_files),
    "fat_files": fat_files,
    "vulture_dead_count": vulture_count,
    "deptry_issues": deptry_issues,
    "commit_ratio": ratio,
    "feat_commits": feat_n,
    "refactor_commits": refactor_n,
    "checks": checks,
    "pass_count": pass_count,
    "verdict": verdict,
    "gate_passed": pass_count == 7,
    "duration_ms": duration_ms,
    "hostname": socket.gethostname(),
}
print(json.dumps(result, indent=2))
```

---

## Dashboard query (Neo4j)

### 사이클별 trend

```cypher
MATCH (cr:CleanupRun)
WHERE cr.completed_at >= datetime() - duration('P30D')
RETURN cr.cycle_id, cr.completed_at,
       cr.tach_cycles, cr.fat_files_count,
       cr.vulture_dead_count, cr.commit_ratio,
       cr.verdict
ORDER BY cr.completed_at DESC
```

### Verdict 분포 (최근 N 사이클)

```cypher
MATCH (cr:CleanupRun)
WHERE cr.completed_at >= datetime() - duration('P30D')
RETURN cr.verdict AS verdict, count(cr) AS n
ORDER BY n DESC
```

### Top fat files (전체 history)

```cypher
MATCH (cr:CleanupRun)
UNWIND cr.fat_files AS f
RETURN f AS file_path, count(cr) AS appeared_in_cycles, max(cr.lizard_loc_max) AS max_loc
ORDER BY appeared_in_cycles DESC LIMIT 20
```

### Refactor:feature ratio history

```cypher
MATCH (cr:CleanupRun)
WHERE cr.completed_at >= datetime() - duration('P90D')
RETURN cr.cycle_id, cr.commit_ratio, cr.refactor_commits, cr.feat_commits
ORDER BY cr.completed_at DESC
```

### RefactorSpec backlog

```cypher
MATCH (rs:RefactorSpec)
WHERE rs.severity IN ['HIGH', 'CRITICAL']
  AND NOT EXISTS { (rs)-[:RESOLVED_BY]->() }
RETURN rs.name, rs.severity, size(rs.recommendations) AS rec_count, rs.created_at
ORDER BY rs.severity DESC, rs.created_at ASC LIMIT 20
```

---

## Visualization (예시)

```
Cycle      | tach | fat_files | vulture | ratio | verdict
-----------|------|-----------|---------|-------|--------
cycle-N    |   0  |     0     |   12    | 0.25  | PASS
cycle-N-1  |   0  |     1     |   15    | 0.18  | NEEDS_REFACTOR
cycle-N-2  |   0  |     1     |   14    | 0.21  | PASS
cycle-N-3  |   1  |     2     |   18    | 0.10  | BLOCK   ← refactor cycle 강제
cycle-N-4  |   0  |     0     |   10    | 0.30  | PASS
```

---

## 통합: meta-review trigger

```cypher
// meta-review (Phase 5) 진입 시 호출
MATCH (cycle:AptCycle {name: $cycle_id})-[:HAS_CLEANUP]->(cr:CleanupRun)
WITH cr
WHERE NOT cr.gate_passed
MATCH (cycle:AptCycle {name: $cycle_id})
MERGE (l:Lesson {name: 'lesson-cleanup-fail-' + $cycle_id})
SET l.problem = 'Phase 6 cleanup gate fail: ' + cr.verdict,
    l.severity = CASE WHEN cr.verdict = 'BLOCK' THEN 'HIGH' ELSE 'MEDIUM' END,
    l.recommendations = cr.recommendations,
    l.cycle_id = $cycle_id
MERGE (cycle)-[:DISCOVERED_LESSON]->(l)
```

---

# KG: lesson-apt-phase6-cleanup-missing-2026-04-28
