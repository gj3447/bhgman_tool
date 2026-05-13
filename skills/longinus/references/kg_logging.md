# longinus — KG Logging

> Lazy-load reference. Parent: [`../SKILL.md`](../SKILL.md).

## 1. ReferenceSite (7-Layer Schema)

```cypher
MERGE (rs:ReferenceSite:AbstractNode {name: 'RS_' + $contract + '_' + $sym})
SET rs.l1_kg_node = $kg_node,
    rs.l2_contract = $contract,
    rs.l3_code_symbol = $sym,
    rs.l4_file_line = $file + ':' + toString($line),
    rs.l5_line_range = $line_range,
    rs.l6_sha256 = $sha256,
    rs.l6_sha256_baseline = $sha256,
    rs.l6_sha256_baseline_at = datetime(),
    rs.l6_sha256_current = $sha256,
    rs.l7_crate_or_script = $crate,
    rs.layer_completeness = $completeness_bitmask,
    rs.bound_at = datetime()
MATCH (c {name: $contract})
MERGE (c)-[:BOUND_TO]->(rs)
```

## 2. DriftReport (5 kind table)

```cypher
MERGE (dr:DriftReport:AbstractNode {name: 'DR_' + $exec + '_' + $date})
SET dr.exec_name = $exec,
    dr.missing = $missing_n,
    dr.orphan = $orphan_n,
    dr.sigmismatch = $sig_n,
    dr.patterndiv = $patt_n,
    dr.labelrot = $label_n,
    dr.total_recovered = $total,
    dr.coverage_ratio = (1.0 * ($total - sum_drifts) / $total),
    dr.measured_at = datetime()
MERGE (exec:TPA_Execution {name: $exec})-[:HAS_DRIFT_REPORT]->(dr)
```

## 3. ReverseOrphan

```cypher
MERGE (ro:ReverseOrphan:AbstractNode {name: 'RO_' + $sym})
SET ro.code_symbol = $sym,
    ro.sourcePath = $file + ':' + toString($line),
    ro.detected_in_execution = $exec,
    ro.detected_at = datetime(),
    ro.lesson_candidate = true
```

## 4. SHA256DaemonRun (production audit)

```cypher
CREATE (run:SHA256DaemonRun {
  triggered_at: datetime(),
  total_ref_sites: $total,
  baseline_count: $baseline_n,
  drift_count: $drift_n,
  file_missing_count: $missing_n,
  directory_skip_count: $dir_skip_n,
  duration_ms: $duration,
  triggered_by: 'launchd|manual'
})
```

## 5. BXLawViolationLog

```cypher
CREATE (v:BXLawViolation {
  ref_site: $ref_site,
  law: $law,                                              // GetPut|PutGet|PutPut
  baseline_state: $baseline,
  current_state: $current,
  resolution: $resolution,                                // KG_revert|file_revert|merge|pending
  detected_at: datetime()
})
```

## 6. Audit Queries

```cypher
// Drift trend (last 30 days)
MATCH (dr:DriftReport) WHERE dr.measured_at >= datetime() - duration('P30D')
WITH dr.measured_at.day AS day, avg(dr.coverage_ratio) AS avg_coverage
ORDER BY day RETURN day, avg_coverage

// SHA256 daemon health
MATCH (run:SHA256DaemonRun) WHERE run.triggered_at >= datetime() - duration('PT24H')
RETURN run.triggered_at, run.drift_count, run.duration_ms ORDER BY run.triggered_at DESC LIMIT 24
```

# KG: ATOM_Skill_longinus, longinus-sha256-daemon-canonical-2026-05-06, fw-longinus-references-apt-parity-2026-05-06
