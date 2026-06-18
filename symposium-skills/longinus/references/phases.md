# longinus — Phases

> Lazy-load reference. Parent: [`../SKILL.md`](../SKILL.md).

## Binding Mode Phases

```
[/longinus <mode> <target>]
   ↓
Phase 0: Pre-flight + mode resolution
Phase 1: AST + manifest assertion (TR4 + TR5 mirror)
Phase 2: Symbol harvesting
Phase 3: KG matching (forward + reverse)
Phase 4: ReferenceSite creation (7-Layer)
Phase 5: SHA256 baseline
Phase 6: BX Lens Laws audit
Phase 7: Drift Report (5 kind)
Phase 8: Reverse Orphan Scan (v3.1)
Phase 9: Naesengmoon --lens longinus gate
   ↓
[Verdict + Lesson candidates]
```

## Phase 0 — Pre-flight

**Modes**:
- `forward` — KG → code (Contract X 의 ReferenceSite 생성)
- `reverse` — code → KG (KG-unmapped symbols 찾기)
- `drift` — sha256 baseline 비교
- `crate` — binary artifact (L7) binding
- `audit` — full sweep (모든 mode)

## Phase 1 — AST + Manifest

**책무**:
- 언어별 parser 적용 (rust-analyzer / tree-sitter / pyright / go/parser)
- manifest = sorted file list
- assertion: union(harvested) == manifest (TR5)

**Anti-pattern**: grep 단독 (TR4 violation, LG_GrepOnlyHarvest).

## Phase 2 — Symbol Harvesting

```cypher
MERGE (sym:CodeSymbol {name: $qualified_name})
SET sym.kind = $kind, sym.visibility = $vis, sym.file = $file, sym.line = $line,
    sym.signature = $sig, sym.parsed_with = $parser
```

**Visibility filter**: pub only (default), public OR all (config).

## Phase 3 — KG Matching

**Forward** (KG → code):
```cypher
MATCH (kg) WHERE kg.sourcePath IS NOT NULL
OPTIONAL MATCH (sym) WHERE sym.file + ':' + toString(sym.line) = kg.sourcePath
WITH kg WHERE NOT exists(sym)
RETURN kg.name AS forward_orphan
```

**Reverse** (code → KG):
```cypher
MATCH (sym) WHERE NOT EXISTS { MATCH (sym)<-[:BOUND_TO]-() }
RETURN sym.name AS reverse_orphan
```

## Phase 4 — ReferenceSite Creation (7-Layer)

```cypher
MERGE (rs:ReferenceSite {name: 'RS_' + $contract + '_' + $sym})
SET rs.l1_kg_node = $kg, rs.l2_contract = $contract, rs.l3_code_symbol = $sym,
    rs.l4_file_line = $file_line,                  // mandatory
    rs.l5_line_range = $range,
    rs.l6_sha256 = $hash,
    rs.l7_crate_or_script = $crate,
    rs.layer_completeness = $bitmask
```

**Required**: L4 (file:line) 필수.

## Phase 5 — SHA256 Baseline

**For files** (not directories):
- Calculate sha256 of file content
- SET `rs.l6_sha256` and `rs.l6_sha256_baseline_at`
- For directories: SET `rs.status = 'DIRECTORY_SKIP'`

## Phase 6 — BX Lens Laws Audit

**검사**:
- GetPut: KG.updated_at > file.mtime (not allowed)
- PutGet: file.mtime > KG.updated_at (KG sync needed)
- PutPut: 두 source 동시 변경 (sigma_oracle)

## Phase 7 — Drift Report (5 Kind)

```cypher
MERGE (dr:DriftReport {name: 'DR_' + $exec + '_' + $date})
SET dr.missing = $m, dr.orphan = $o, dr.sigmismatch = $s,
    dr.patterndiv = $p, dr.labelrot = $l,
    dr.coverage_ratio = (1.0 * (total - sum) / total)
```

**Invariant**: coverage_ratio >= 0.8 OR anchor.status = 'SUSPENDED'.

## Phase 8 — Reverse Orphan Scan (v3.1)

```cypher
MATCH (sym:CodeSymbol)
WHERE NOT EXISTS { MATCH (sym)<-[:BOUND_TO]-() }
MERGE (ro:ReverseOrphan {name: 'RO_' + sym.name})
SET ro.code_symbol = sym.name, ro.detected_at = datetime()
```

## Phase 9 — Naesengmoon --lens longinus

```
Use the taliban-ensemble-critic agent with --lens longinus
```

LensSet 'longinus' 가 종합 검증.

# KG: ATOM_Skill_longinus, fw-longinus-references-apt-parity-2026-05-06
