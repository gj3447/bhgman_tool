# occam — Gate Stack

> Lazy-load reference. Parent: [`../SKILL.md`](../SKILL.md). KG: `occam-kam-canonical-2026-05-26`, `consensus-occam-entropy-truth-2026-05-26`, `occam-quant-scoring-engine-2026-06-01`.
>
> 오캄의 *validation/fidelity gate stack* — 한 노드가 archive(SUPERSEDED) 후보로 통과하기까지 거치는 게이트들과, 각 게이트의 불변식·threshold·pass/fail 의미.
> 정전 모토: **"entropy selects, truth-guard gates"** (`consensus-occam-entropy-truth-2026-05-26`). entropy(C)가 *고르고*, truth-guard(G)가 *막는다*.

---

## 0. Gate 흐름 (overview)

한 후보 노드는 아래 순서로 게이트를 통과해야만 `SUPERSEDE`(archive 확정)에 도달한다. 어느 게이트든 막으면 σ=0 또는 더 약한 verdict로 강등된다.

```
NodeRecord ─► [G1 Twin Gate] ─► [G2 Entrenchment Gate] ─► [G3 σ Verdict Cascade] ─► [G4 dry-run Gate] ─► [G5 Covenant Assert] ─► write
                   │                    │                         │                                              │
                FLAG_ONLY           PROTECTED               VERIFY / KEEP                                  AssertionError
```

# src: engine/occam/scoring.py (score_node / _verdict), engine/occam/kg_adapter.py (apply_supersessions / build_supersede)

---

## 1. G1 — Twin Gate (machloket / Eilu va-Eilu)

**불변식**: 살아있는 twin(=후속 노드, successor)이 없으면 절대 supersede 하지 않는다. 대체물 없는 격리 = data loss.

# src: engine/occam/scoring.py `guard()` — `twin_gate = 1.0 if has_successor else 0.0`; `score_node` 안전 불변식 "has_successor=False → σ=0 (FLAG_ONLY)"
# src: engine/occam/occam.py `occam_pass` GROUP step — `if len(group) < 2: continue` (size>1, twin 존재 그룹만 후보화)
# src: KG `CONTRACT_OccamArchiveRecord_v1_2026-05-27` R2 "twin-required: 대체 active twin 없는 n=1 노드 archive 금지(대체물 없는 격리=data loss)"

| 결과 | 의미 |
|---|---|
| twin 있음 | 다음 게이트로 진행 |
| twin 부재 | σ=0, verdict=**FLAG_ONLY** — supersede 안 하고 `report.orphans`/`flagged`로 surface (판단은 사용자/Longinus) |

학문 근거: AGM contraction — 후속자 없이 믿음을 버리지 않는다 (Gärdenfors–Makinson 1988). # src: scoring.py module docstring

---

## 2. G2 — Entrenchment Gate (truth-guard, never-archive tier)

**불변식**: epistemic entrenchment `e=1.0`인 노드 tier는 σ=0 강제 → **PROTECTED**, 자동 archive 영구 차단.

`guard = (1 − e) · twin_gate` 이므로 e=1.0이면 G=0이고 σ = C·G = 0.

# src: engine/occam/scoring.py `_ENTRENCHMENT` 테이블 + `NEVER_ARCHIVE_TIERS`

| Tier | e (penalty) | archive 가능? |
|---|---|---|
| CANONICAL / LESSON / CONTRACT / VERDICT | **1.0** | ❌ never (PROTECTED) |
| PRINCIPLE | 0.8 | σ 최대 0.2 |
| ONTOLOGY_CLASS | 0.7 | σ 최대 0.3 |
| REFERENCE | 0.5 | σ 최대 0.5 |
| FINDING | 0.3 | σ 최대 0.7 |
| PLAIN (e.g. SourceCodeNode) | 0.0 | dedup 대상 (σ 최대 1.0) |

# src: scoring.py `_ENTRENCHMENT` dict (값 1:1)

**보수성 정리**: 온톨로지 클래스(e=0.7)는 완전 stale·중복이어도 σ 최대 = 1·(1−0.7) = 0.3 → 절대 auto-SUPERSEDE 불가, 항상 최대 VERIFY. # src: engine/occam/SCORING_THEORY.md §1 "보수성 정리"

학문 근거: AGM epistemic entrenchment (Gärdenfors–Makinson 1988). # src: scoring.py docstring

---

## 3. G3 — σ Verdict Cascade (candidacy × guard)

게이트를 통과한 후보는 연속 점수 **σ = candidacy(C) · guard(G) ∈ [0,1]** 를 받고 threshold로 verdict가 갈린다.

### candidacy C — "entropy selects" (3 독립 obsolescence 증거의 noisy-OR)

```
C = 1 − (1−r)(1−s)(1−d)          (noisy-OR, Pearl 1988 — 한 신호만 강해도 C↑)
```

| 성분 | 공식 | 경계 | 학문 근거 |
|---|---|---|---|
| redundancy r | 동일 sha twin=1.0, 아니면 line-count 겹침 비율 (`lo/hi`) | [0,1] | MDL (Rissanen 1978) / Kolmogorov·Solomonoff — "compressible = clutter" |
| staleness s | `1 − 2^(−age/halflife)`, age=halflife→0.5, age=0→0 | [0,1) | 망각곡선 (Ebbinghaus 1885), 지수감쇠 |
| deadness d | `2^(−invocation/scale)`, inv=0→1.0 | (0,1] | 사용기반 (`lesson-occam-needs-invocation-log-2026-05-28`) |

# src: engine/occam/scoring.py `staleness()` / `deadness()` / `candidacy()` / engine/occam/occam.py `_redundancy()`

### verdict threshold (KG `dt-occam-*` grounded)

# src: engine/occam/scoring.py `ScoringConfig` (theta_supersede / theta_keep) + `_verdict()`
# src: KG `dt-occam-naesengmoon-confidence` (threshold=0.7), `dt-occam-twin-status-score-grounded` (threshold=0.8), `dt-occam-dead-node-count-grounded` (threshold=10)

| 조건 | verdict | 의미 |
|---|---|---|
| `e ≥ 1.0` (먼저 판정) | **PROTECTED** | never-archive tier (G2) |
| `has_successor = False` | **FLAG_ONLY** | twin 부재 (G1) |
| `σ ≥ θ_supersede = 0.7` | **SUPERSEDE** | archive 후보 확정 |
| `θ_keep ≤ σ < θ_supersede` (0.3 ≤ σ < 0.7) | **VERIFY** | 회색지대 → 나생문(Naesengmoon) dispatch |
| `σ < θ_keep = 0.3` | **KEEP** | 손대지 않음 |

`ScoringConfig.__post_init__` 가 `0 ≤ θ_keep ≤ θ_supersede ≤ 1`, `halflife_days > 0`, `invocation_scale > 0` 를 강제 (위반 시 ValueError). # src: scoring.py `ScoringConfig.__post_init__`

### Lean-증명 안전 불변식 (score_node)

1. `σ ∈ [0,1]` (`score_le_scale`) 2. `e ∈ NEVER_ARCHIVE → σ=0` (`protected_score_zero`) 3. `has_successor=False → σ=0` (`no_successor_zero`) 4. σ는 r·s·d로 단조 증가, e로 단조 감소 (`score_antitone_entrench`).
# src: engine/occam/scoring.py `score_node` docstring "안전 불변식" + engine/occam/SCORING_THEORY.md §3 (lean/Occam_SupersessionScore.lean, Mathlib-free, 6 증명 + 4 #decide sanity)

---

## 4. G4 — dry-run Gate (default-safe)

**불변식**: write_cypher가 있어도 `dry_run=True`(기본)면 실행하지 않는다 — planned cypher만 반환.

# src: engine/occam/kg_adapter.py `apply_supersessions` — `if dry_run or write_cypher is None: ... return ApplyResult(dry_run=True, applied_count=0)`
# src: engine/occam/semantic_dedup.py `run_semantic_dedup` — `do_write = apply and write_cypher is not None`; 백엔드 미지원 시 except로 PROPOSE degrade

| 모드 | 동작 |
|---|---|
| dry-run (default) | `planned_cyphers`만, write 0 |
| `--apply` + write_cypher | supersede write 실행 (reversible: status flag + edge) |

---

## 5. G5 — Covenant Assert Gate (archive-only, hard)

**불변식**: write cypher에 `DELETE` / `DETACH` / `REMOVE` 토큰이 있으면 `AssertionError`로 차단. 오캄은 *삭제하지 않고 격리만* 한다.

# src: engine/occam/kg_adapter.py `FORBIDDEN_TOKENS = ("DELETE","DETACH","REMOVE")` + `build_supersede` assert
# src: engine/occam/semantic_dedup.py 동일 `FORBIDDEN_TOKENS` + `plan_supersession` assert
# src: KG `CONTRACT_OccamArchiveRecord_v1_2026-05-27` R1 "no-delete: 오캄은 DELETE 안 함, 격리만. 완전삭제는 별도 user verdict"

supersede write 형태 (reversible): `SET stale.status='SUPERSEDED', supersededBy, supersededReason, supersededAt, occamPass` + `MERGE (stale)-[:SUPERSEDED_BY]->(current)`. 원본 노드 보존 = 복원 가능. self-supersession은 `WHERE stale <> current`로 차단. # src: engine/occam/kg_adapter.py `_SUPERSEDE_CYPHER`

추가 read-time 위생: 이미 `status='SUPERSEDED'`인 노드는 fetch에서 제외 (아카이브된 과거 재-아카이브 금지, dogfood 교훈). # src: engine/occam/kg_adapter.py `_NOT_ALREADY_ARCHIVED`

Archive record 필수 shape (C2/C3/C4): log-layer 라벨(`:OCCAM_SLICED` exact-dup / `:ARCHIVED` superseded) + `valid_to`(bitemporal close, active=NULL) + `occam_archived_at/by` + `occam_archive_reason` enum(`exact_duplicate`/`superseded_concept`/`stale_lineage`/`dead_code`) + active-twin pointer + `restorable=true`. # src: KG `CONTRACT_OccamArchiveRecord_v1_2026-05-27` mandatory_fields

---

## 6. Ontology DL Consistency Gate (`ontology.py`)

단순 dedup을 넘어 **형식 온톨로지 / Description Logic 정합성** 검사. 𝒮ℛ𝒪ℐ𝒬(D) = OWL 2 DL 기반.

# src: engine/occam/ontology.py `ViolationKind` / `ontology_pass` / `OntologyReport.is_consistent`

| # | 검사 | 종류 |
|---|---|---|
| 1 | SUBSUMPTION_CYCLE — subClassOf DAG 위반 (C ⊑ … ⊑ C) | 논리 비정합 |
| 2 | DANGLING_PARENT — 없는 상위 클래스 subClassOf | 무결성 경고 |
| 3 | DANGLING_TYPE — 없는 클래스 rdf:type | 무결성 경고 |
| 4 | PUNNING — class ∧ instance 동명 (라벨충돌) | 무결성 경고 |
| 5 | UNSATISFIABLE_CLASS — 두 disjoint 상위의 공통 하위 ⇒ ⊥ | 논리 비정합 |
| 6 | DISJOINTNESS_VIOLATION — instance가 disjoint 두 type | 논리 비정합 |

**pass/fail 의미**: `is_consistent` = inconsistency 종류(1·5·6) 위반이 0. 2·3·4는 무결성/위생 경고로 정합성과 분리. # src: engine/occam/ontology.py `_INCONSISTENCY_KINDS` + `OntologyReport.is_consistent`

위생(stale/dup 클래스)은 §3 σ로 점수화 → 같은 covenant(삭제 0, twin 없으면 flag, SUPERSEDED 재처리 금지) 유지. active·사용중·중복없음·신선 클래스는 위생 대상에서 제외. # src: engine/occam/ontology.py `_is_hygiene_candidate` / `_hygiene_scoring`

학문 근거: Baader et al. *The Description Logic Handbook* (2003/2007); W3C OWL 2 (2012); Gruber (1993); Guarino (1998). # src: engine/occam/ontology.py docstring grounding

---

## 7. Semantic Near-Duplicate Gate (`semantic_dedup.py`)

sha256-blind 사각지대(패러프레이즈된 Lesson·다시 쓴 Finding)를 임베딩 cosine으로 메운다.

# src: engine/occam/semantic_dedup.py `find_near_duplicates` / `run_semantic_dedup`

- **threshold**: cosine `≥ θ` (default `θ=0.95`) 쌍만 near-duplicate 후보. # src: semantic_dedup.py `find_near_duplicates(threshold=0.95)`
- **결정론**: keep/drop은 weight 큰 쪽(내용 많음/최신) 유지, 동률이면 id 작은 쪽 유지. # src: `_pick_keep_drop`
- **PROPOSE만**: 클러스터 transitive 자동해소 안 함 — 쌍만 surface (human/verdict gate). # src: semantic_dedup.py module docstring
- **key allowlist** (cypher 주입 차단): `name` / `findingId` / `id` 만 허용, 아니면 ValueError. # src: `_KEY_ALLOWLIST` + `plan_supersession`
- G4 dry-run + G5 covenant assert 동일 적용. # src: `run_semantic_dedup` + `plan_supersession`

스케일: 현재 O(N²) pairwise; 대규모는 KG native vector index(kNN) 후속. # src: semantic_dedup.py docstring

---

## 8. Oracle Gate (compiler-Naesengmoon)

판단렌즈(LLM)로 PASS 불가한 주장은 컴파일러/오라클 실측으로 escalate. occam의 `oracle_lens`는 정본(`engine/naesengmoon/oracle_lens.py`)의 thin re-export — primitive(`OracleLens`/`OracleVerdict`/`run_oracle_gate`)는 occam·eureka 중복분이 정본 나생문 패키지로 추출됨(오캄 dedup 자기적용). # src: engine/occam/oracle_lens.py (re-export, 정의 없음)

VERIFY verdict(§3 회색지대)는 이 oracle/Naesengmoon dispatch로 넘어간다. # src: scoring.py `_verdict` (VERIFY) + SKILL.md "오캄→나생문 GATE로 USES"

---

## 9. References

- 엔진 정본: `bhgman_tool/engine/occam/` — `occam.py` (occam_pass / twin gate), `scoring.py` (σ verdict cascade / entrenchment), `ontology.py` (DL consistency), `kg_adapter.py` + `semantic_dedup.py` (covenant assert + dry-run), `oracle_lens.py` (oracle gate)
- `engine/occam/SCORING_THEORY.md` (이론 grounding + Lean 6 불변식)
- `../SKILL.md` (프로토콜)
- KG: `occam-kam-canonical-2026-05-26`, `consensus-occam-entropy-truth-2026-05-26`, `occam-quant-scoring-engine-2026-06-01` (`:OccamScoringModel`), `verdict-user-occam-gains-ontology-hygiene-responsibility-2026-05-27`, `CONTRACT_OccamArchiveRecord_v1_2026-05-27`, `dt-occam-naesengmoon-confidence` (0.7), `dt-occam-twin-status-score-grounded` (0.8), `dt-occam-dead-node-count-grounded` (10)
- 사이블: `../longinus/references/theory.md` (format gold-standard)

# KG: ATOM_Skill_occam, occam-kam-canonical-2026-05-26, occam-quant-scoring-engine-2026-06-01
