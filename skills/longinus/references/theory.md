# longinus — Theory

> Lazy-load reference. Parent: [`../SKILL.md`](../SKILL.md). KG: `longinus-grounding`, `longinus-sha256-daemon-canonical-2026-05-06`.

---

## 1. 7-Layer Reference Model (v3)

KG의 의미 계층을 소스코드까지 *관통(貫通)*시키는 참조 모델. 각 layer는 KG↔code 바인딩의 다른 추상화 수준.

| Layer | 이름 | Reference Type | 용도 |
|-------|------|---------------|------|
| L1 | KG_NODE | node identity | KG 내부 reference |
| L2 | CONTRACT_BINDING | contract → code | spec 형식 매핑 |
| L3 | CODE_SYMBOL | symbol identity | pub fn / struct / class |
| L4 | FILE_LINE | sourcePath: file:line | concrete 위치 |
| L5 | LINE_RANGE | line_range [start,end] | multi-line region |
| L6 | SHA256 | hash invariant | content drift 검출 |
| L7 | CRATE_SCRIPT | crate / script identity | binary artifact level |

각 ReferenceSite 가 L1-L7 중 일부를 fill. 누락 layer = 특정 종류의 drift 가능성.

---

## 2. BX Lens Laws (Bidirectional Transformation)

| Law | 정의 | 위반 |
|-----|------|------|
| **GetPut** | get(put(s, v)) = v | KG 갱신 → code 미반영 = drift |
| **PutGet** | put(s, get(s)) = s | code edit → KG 미반영 = drift |
| **PutPut** | put(put(s, v1), v2) = put(s, v2) | concurrent edit conflict |

L4-L7 reference 가 모두 BX-conformant 여야 한다 (Foster 2007 lenses theory).

---

## 3. Refinement Types (v3 branded types)

```rust
type CrystallizedContract = Contract & { status: 'CRYSTALLIZED' }
type BoundContract = CrystallizedContract & { reference_site: ReferenceSite }
type VerifiedContract = BoundContract & { sha256_invariant_holds: true }
```

각 Refinement 단계 위반 → 다른 종류의 Lesson:
- non-crystallized → APT phase order violation
- crystallized but unbound → TR_LongiusBindingMissing
- bound but sha256 drift → TR_DriftSilenced (Longinus daemon detection)

---

## 4. GED Drift 정량화 (Graph Edit Distance)

```
drift_score = ged(KG_state_t0, KG_state_t1) / max_possible_ged
```

Edit operations:
- Node add/remove (weight 1.0)
- Edge add/remove (weight 0.7)
- Property change (weight 0.3)

Threshold: `tpa_drift_coverage_ratio_min` (0.8 → drift_score < 0.2). 초과 시 SemanticAnchor SUSPENDED.

---

## 5. Reverse Orphan Scan (v3.1 신규)

KG → code 만 검사하면 *unused KG nodes*는 발견되지만 *unmapped code symbols*는 사각지대.

Reverse scan:
```cypher
MATCH (sym:CodeSymbol)
WHERE NOT EXISTS { MATCH (sym)-[:HAS_CONTRACT|MATCHED_BY]->() }
RETURN sym.name, sym.sourcePath
-- 결과: code 에 있지만 KG 매핑 없는 심볼
```

각 reverse orphan = Lesson 후보 (recovery 가 놓친 영역).

---

## 6. Crate / Script-level Binding (v3.1)

L7 추가 — binary artifact level.

```cypher
MERGE (c:Crate:AbstractNode {name: $crate_name})
SET c.workspace_root = $ws_root,
    c.cargo_toml = $cargo_path,
    c.target_artifact = $artifact_path,
    c.sha256 = $artifact_sha,
    c.last_built_at = datetime()
MERGE (c)-[:CONTAINS_SYMBOL]->(sym:CodeSymbol)
```

Script-level: shell scripts / Python entrypoints — 동일 schema, type='script'.

---

## 7. SHA256 Daemon (canonical 2026-05-06)

`SYMPOSIUM/SKILLS/bin/longinus_sha256_daemon.py` — production template.

| 산출 | 의미 |
|------|------|
| `BASELINE` | 정상 sha256 일치 (91.2% baseline) |
| `DRIFT` | sha256 mismatch — content 변경 감지 |
| `DIRECTORY_SKIP` | directory aggregation reference (sha 미적용) |
| `FILE_MISSING` | path 자체 없음 (Missing drift) |

`com.symposium.longinus-sha256-daemon.plist` — launchd 1h interval. KG: `longinus-sha256-daemon-canonical-2026-05-06`.

---

## 8. Taliban --lens longinus

binding-validation 전용 LensSet. critic 이 받는 컨텍스트:
- ReferenceSite 누락 노드 list
- sha256 drift 검출 list
- reverse orphan scan 결과
- BX law 위반 case (PutPut conflict 등)

---

## 9. References

- `../SKILL.md`
- KG: `longinus-grounding`, `longinus-sha256-daemon-canonical-2026-05-06`, `fw-longinus-sha256-daemon-2026-05-06`, `MIC_v1.KgCodeBinder` slot
- 사이블: `../taliban/references/theory.md` (lens), `../prometheus/references/theory.md` (G6.5 dispersion gate)

# KG: ATOM_Skill_longinus, fw-longinus-references-apt-parity-2026-05-06 (planned)
