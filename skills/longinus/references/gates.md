# longinus — Gates

> Lazy-load reference. Parent: [`../SKILL.md`](../SKILL.md). Sibling: [`./theory.md`](./theory.md).
> KG: `longinus-grounding`, `longinus-sha256-daemon-canonical-2026-05-06`.

---

## 1. Binding Gates Sequence

각 binding/audit invocation:

```
[/longinus <mode> <target>]
   ↓
G0: Pre-flight  — target 존재 + mode resolve
   ↓
G1: AST + manifest  — TR4 mirror (parser used, not grep)
   ↓
G2: Symbol harvesting  — pub 심볼 list + sourcePath:line
   ↓
G3: KG matching  — KG 노드 ↔ symbol bidirectional
   ↓
G4: Reference creation  — :ReferenceSite 7-Layer fields
   ↓
G5: SHA256 baseline  — content hash + drift detection
   ↓
G6: BX Lens Laws audit  — GetPut / PutGet / PutPut
   ↓
G7: Drift Report  — 5 kind + coverage_ratio
   ↓
G8: Reverse Orphan Scan  — code → KG mapping audit (v3.1)
   ↓
G9: Taliban --lens longinus  — final gate
   ↓
[Verdict + Lesson candidates]
```

---

## 2. G0 Pre-flight

**Required**:
- target = file/dir/Contract/SemanticAnchor 존재
- mode ∈ {forward, reverse, drift, crate, audit}
- `MIC_v1.KgCodeBinder` slot = Longinus

**On fail**: BLOCK + mode 후보 표시.

---

## 3. G1 AST Parser Gate (TR4 mirror)

**Required**:
- AST parser 적용 가능 언어 (Rust / TS / Python / Go)
- parser binary 존재 + version compatible
- grep 단독 사용 금지

| Language | Parser | Fallback |
|----------|--------|---------|
| Rust | rust-analyzer / tree-sitter-rust | tree-sitter-rust standalone |
| TypeScript | tree-sitter-typescript | @babel/parser |
| Python | pyright / tree-sitter-python | ast (stdlib) |
| Go | go/parser | tree-sitter-go |

**On fail**:
- parser 미설치 → BLOCK + install hint (Lesson)
- parser 결과 0 symbols → BLOCK + parser version 진단

---

## 4. G2 Symbol Harvesting Gate

**Required**:
- `manifest_files == union(harvested_files)` (TR5 mirror)
- 각 symbol 에 `qualified_name`, `kind`, `file:line`, `signature`
- skipped_files = 0
- visibility filter applied (default: pub only)

```cypher
MERGE (sym:CodeSymbol:AbstractNode {name: $qualified_name})
SET sym.kind = $kind,
    sym.visibility = $vis,
    sym.file = $file,
    sym.line = $line,
    sym.signature = $sig,
    sym.parsed_with = $parser,
    sym.harvested_at = datetime()
```

**On fail**: manifest mismatch → 보충 agent 출격.

---

## 5. G3 KG Matching Gate (Forward + Reverse)

### Forward (KG → code)
```cypher
MATCH (kg_node) WHERE kg_node.sourcePath IS NOT NULL
OPTIONAL MATCH (sym:CodeSymbol) WHERE sym.file + ':' + toString(sym.line) = kg_node.sourcePath
WITH kg_node, sym
WHERE sym IS NULL
RETURN kg_node.name AS missing_code  // KG 측 orphan
```

### Reverse (code → KG)
```cypher
MATCH (sym:CodeSymbol) WHERE NOT EXISTS { MATCH (sym)<-[:BOUND_TO]-(:ReferenceSite) }
RETURN sym.name AS reverse_orphan
```

**On fail**:
- Forward orphan 존재 → :Lesson `lesson-longinus-kg-orphan-<n>` 생성
- Reverse orphan 다수 (>10) → ActionPlan 자동 stub 생성

---

## 6. G4 Reference Creation Gate (7-Layer)

**Required**: 각 ReferenceSite 가 7 layer 중 가능한 모든 fill

```cypher
MERGE (rs:ReferenceSite:AbstractNode {name: 'RS_' + $contract_name + '_' + $sym_name})
SET rs.l1_kg_node = $kg_node_name,
    rs.l2_contract = $contract_name,
    rs.l3_code_symbol = $sym_name,
    rs.l4_file_line = $file + ':' + toString($line),
    rs.l5_line_range = $line_range,                 // [start, end]
    rs.l6_sha256 = $sha256_hash,
    rs.l7_crate_or_script = $crate_name,
    rs.layer_completeness = $layers_filled,         // bitmask
    rs.bound_at = datetime()
```

**On fail**:
- L4 missing → BLOCK (file:line 은 필수)
- L1-L7 all missing → BLOCK (트리비얼 reference 차단)

---

## 7. G5 SHA256 Baseline Gate

```cypher
MATCH (rs:ReferenceSite) WHERE rs.l6_sha256 IS NULL
RETURN rs.name AS unhashed
```

**Required**:
- `rs.l6_sha256` 모든 ReferenceSite 에 set (file 단위)
- `rs.l6_sha256_baseline_at` timestamp set
- directory 는 `status = 'DIRECTORY_SKIP'` 명시 (sha 미적용)

**On fail**: baseline 누락 → daemon 자동 보완 (`longinus_sha256_daemon.py`).

KG: `longinus-sha256-daemon-canonical-2026-05-06`.

---

## 8. G6 BX Lens Laws Audit Gate

| Law | 위반 | 검출 |
|-----|------|------|
| GetPut | KG 갱신 → code 미반영 | KG.updated_at > file.mtime |
| PutGet | code edit → KG 미반영 | file.mtime > KG.updated_at |
| PutPut | concurrent edit conflict | 두 source 동시 다른 변경 |

```cypher
MATCH (rs:ReferenceSite)
WHERE rs.l6_sha256_baseline IS NOT NULL
  AND rs.l6_sha256_current IS NOT NULL
  AND rs.l6_sha256_baseline <> rs.l6_sha256_current
RETURN rs.name AS bx_law_violation, rs.l4_file_line AS file
```

**On fail**:
- GetPut 위반 → file regenerate from KG OR KG revert (sigma_oracle)
- PutGet 위반 → KG sync from file
- PutPut 위반 → 2-way merge + Lesson

---

## 9. G7 Drift Report Gate (5 Kind)

| Drift Kind | 검출 |
|------------|------|
| Missing | KG node references file/symbol that no longer exists |
| Orphan | Code symbol with no matching KG Contract |
| SigMismatch | Code signature differs from contract.protocol |
| PatternDiv | Code pattern shifted (State → Strategy) |
| LabelRot | KG label/relation drifted from canonical |

```cypher
MERGE (dr:DriftReport:AbstractNode {name: 'DR_' + $exec + '_' + $date})
SET dr.missing = $missing_n,
    dr.orphan = $orphan_n,
    dr.sigmismatch = $sig_n,
    dr.patterndiv = $patt_n,
    dr.labelrot = $label_n,
    dr.total_recovered = $total,
    dr.coverage_ratio = (1.0 * ($total - sum) / $total),
    dr.measured_at = datetime()
```

**Required**: `coverage_ratio >= tpa_drift_coverage_ratio_min` (0.8 default) 또는 anchor.status = 'SUSPENDED' SET.

---

## 10. G8 Reverse Orphan Scan Gate (v3.1)

```cypher
MATCH (sym:CodeSymbol) 
WHERE NOT EXISTS { MATCH (sym)<-[:BOUND_TO]-(:ReferenceSite) }
WITH sym, count(*) OVER () AS total_orphans
MERGE (ro:ReverseOrphan:AbstractNode {name: 'RO_' + sym.name})
SET ro.code_symbol = sym.name,
    ro.sourcePath = sym.file + ':' + toString(sym.line),
    ro.detected_at = datetime()
RETURN total_orphans
```

**On fail**:
- `total_orphans > 0` → :Lesson 후보 (recovery 가 놓친 영역)
- `total_orphans / total_symbols > 0.2` → Pattern Library refresh OR sigma_oracle escalate

---

## 11. G9 Taliban --lens longinus Gate

```
Use the taliban-ensemble-critic agent with --lens longinus to validate <target>
```

LensSet 'longinus' 가 받는 컨텍스트:
- ReferenceSite 누락 노드 list (G4 fail 누적)
- SHA256 drift 검출 list (G5 fail 누적)
- BX law 위반 case (G6 fail 누적)
- 5-drift report (G7)
- ReverseOrphan list (G8)

**On fail**: 전체 binding cycle REJECT + Lesson `lesson-longinus-binding-incomplete`.

---

## 12. Production Daemon (launchd 1h interval)

`com.symposium.longinus-sha256-daemon.plist` schedule:
- 모든 :ReferenceSite SHA256 검증
- BASELINE / DRIFT / FILE_MISSING / DIRECTORY_SKIP 분류
- DRIFT 발견 시 :Lesson 자동 생성 (severity=HIGH)
- HIGH lesson > 5 → push notification webhook (사용자 verdict 게이트)

KG: `longinus-sha256-daemon-canonical-2026-05-06`.

---

## 13. Anti-Patterns Detection

| # | Anti-pattern | 검출 |
|---|--------------|------|
| LG_LongiusBindingMissing | Contract has no ReferenceSite | G4 audit |
| LG_GrepOnlyHarvest | parsed_with = 'grep' | G1 |
| LG_SHA256Stale | baseline_at age > 7 days | G5 freshness check |
| LG_DriftSilenced | coverage < 0.8 + status NOT SUSPENDED | G7 |
| LG_BXLawViolation | concurrent edit unmerged | G6 PutPut |
| LG_DirectorySHAAttempt | directory aggregator with sha | G5 type check |
| LG_LayerInsufficient | only L1-L3 set (file:line missing) | G4 |

---

## 14. References

- theory: `./theory.md`
- skill: `../SKILL.md`
- production tool: `SYMPOSIUM/SKILLS/bin/longinus_sha256_daemon.py`
- launchd plist: `SYMPOSIUM/SKILLS/bin/com.symposium.longinus-sha256-daemon.plist`
- sibling: `../taliban/references/gates.md` (--lens longinus host)
- KG: `longinus-sha256-daemon-canonical-2026-05-06`, `MIC_v1.KgCodeBinder` slot

# KG: ATOM_Skill_longinus, fw-longinus-references-apt-parity-2026-05-06
