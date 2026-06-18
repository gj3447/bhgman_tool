# occam — Quick Reference (cheatsheet)

> Lazy-load reference. Parent: [`../SKILL.md`](../SKILL.md). One-page invocation + cycle + files + KG anchors + gotchas.
> KG: `occam-kam-canonical-2026-05-26`, `consensus-occam-entropy-truth-2026-05-26`.
> 동사 = **정리한다** (현재→과거↓, archive). 유레카(쌓기/+1)의 정반대 극 (빼기/−, subtractive). 어원: William of Ockham 면도날.

---

## 1. Invocation

```bash
bhgman-tool occam                       # KG 전체 SourceCodeNode dedup, dry-run 기본
bhgman-tool occam --scope <label|path>  # sourcePath CONTAINS <scope> 만
bhgman-tool occam --apply               # SUPERSEDED write (reversible). 생략 = dry-run
bhgman-tool occam --no-disk-scan        # KG-only (mode-1 same-path dedup). 기본은 disk 스캔 ON
bhgman-tool occam --local               # neo4j-free local KG (~/.bhgman/kg.json)
bhgman-tool occam --semantic --label ResearchFinding --threshold 0.75 --limit 200
```
`# src: engine/cli/parser.py:128-167 (p_oc subparser)` · `# src: engine/cli/commands.py:591 cmd_occam`

- neo4j 부재 시 fetch cypher를 stdout 출력 + exit 2 → 부모 Claude가 MCP로 실행. `# src: commands.py:598-608`
- slash alias: `/occam` (KG 전체 dedup, dry-run 기본). `# src: ../SKILL.md frontmatter`

---

## 2. Cycle — `occam_pass` 5 steps

순수 분류 함수 (KG/IO 없음). `# src: engine/occam/occam.py:166 occam_pass`

| # | 단계 | 내용 | src |
|---|---|---|---|
| 1 | SELECT | KG SourceCodeNode 조회 (타입별 key). cypher PRIMARY, disk sha 보조 | `kg_adapter.py:45 fetch_cypher` |
| 2 | GROUP | `normalize_path`로 abs/rel lineage 통합 → `size>1` (twin 존재) 그룹만 | `occam.py:34 normalize_path` |
| 3 | PICK_CURRENT | disk sha 일치 = HIGH / 없으면 `max line_count` = MEDIUM = keep | `occam.py:48 _pick_current` |
| 4 | GUARD | twin 없으면 손대지 않음. false-positive (다른 파일/타입 충돌) 배제 | `occam.py:208-214` |
| 5 | SUPERSEDE | stale → `status='SUPERSEDED'` + `SUPERSEDED_BY` edge + reason. **삭제 0** | `kg_adapter.py:77-103` |

End-to-end: `run_occam(run_cypher, write_cypher, scope, apply, repo_root)` = fetch → occam_pass → apply. `# src: occam_runner.py:88`

### 3 detection modes (disk-aware)
`# src: occam.py:5-15 (module docstring)`
1. **same-path 중복** (mode-1, always): abs/rel lineage 통합 후 같은 normalized path 그룹.
2. **sha-이동** (mode-2, needs `disk_paths`): 동일 sha·다른 경로 = 파일 이동. 디스크에 없는 쪽을 live twin으로 supersede (HIGH). `# src: occam.py:63 _detect_sha_moves`
3. **disk-orphan** (mode-3, flag-only): 경로 디스크 부재 + 동일-sha live twin도 부재 → `report.orphans`로 surface만, supersede 안 함 (machloket / Eilu va-Eilu). `# src: occam.py:105 _detect_disk_orphans`

---

## 3. Scoring — σ ∈ [0,1]  (`scoring.py`)

`σ = candidacy(C) · guard(G)`. "entropy selects, truth-guard gates" 정량화. `# src: scoring.py:177 score_node` · `# src: engine/occam/SCORING_THEORY.md §1`

**candidacy C** = noisy-OR of 3 obsolescence 신호 (`C = 1 − (1−r)(1−s)(1−d)`, Pearl 1988):
- `r` redundancy — 동일 sha twin = 1.0, 아니면 line-count 겹침 비율 (MDL / Rissanen 1978). `# src: occam.py:130 _redundancy`
- `s` staleness — `1 − 2^(−age/halflife)`, age=halflife→0.5 (Ebbinghaus 망각곡선). `# src: scoring.py:144`
- `d` deadness — `2^(−invocation/scale)`, inv=0→1.0 (사용기반). `# src: scoring.py:153`

**guard G** = `(1−e) · twin_gate` (거부권):
- `e` entrenchment — AGM (Gärdenfors–Makinson 1988). canonical/lesson/contract/verdict = **e=1.0 ⇒ G=0 ⇒ never archive**. `# src: scoring.py:65-77 _ENTRENCHMENT`
- twin_gate — 살아있는 후속 부재 ⇒ gate=0 ⇒ σ=0 (FLAG_ONLY). `# src: scoring.py:168 guard`

**verdict** (threshold KG `dt-occam-naesengmoon-confidence` grounded): `# src: scoring.py:211 _verdict`
- σ ≥ 0.7 → **SUPERSEDE** / 0.3 ≤ σ < 0.7 → **VERIFY** (나생문 dispatch) / σ < 0.3 → **KEEP**
- e=1.0 → **PROTECTED** / twin 부재 → **FLAG_ONLY**
- 보수성 정리: 온톨로지 클래스 (e=0.7) σ 최대 = 0.3 → 절대 auto-SUPERSEDE 불가, 항상 VERIFY. `# src: SCORING_THEORY.md §1`

Lean mirror: `lean/Occam_SupersessionScore.lean` (Mathlib-free), 6 안전 불변식 (`protected_score_zero`, `no_successor_zero`, `score_antitone_entrench` 등). `# src: SCORING_THEORY.md §3`

---

## 4. Key files (`engine/occam/`, 16 py)

| file | 역할 | src |
|---|---|---|
| `occam.py` | 코어 dedup 분류 (순수 함수, IO 없음) | occam.py:1 |
| `occam_runner.py` | end-to-end: fetch → pass → apply + `scan_disk_paths` | occam_runner.py:88 |
| `kg_adapter.py` | read(`fetch_cypher`/`fetch_source_nodes`) + write(`build_supersede`/`apply_supersessions`) | kg_adapter.py:1 |
| `occam_models.py` | value objects: `NodeRecord` / `SupersessionCandidate` / `OccamReport` / `Confidence` | occam_models.py:1 |
| `scoring.py` | σ 정량 scoring + verdict | scoring.py:1 |
| `ontology.py` | DL 정합성 6검사 (SUBSUMPTION_CYCLE / PUNNING / UNSATISFIABLE_CLASS 등) | ontology.py:1 |
| `semantic_dedup.py` | 임베딩 cosine near-dup (sha-blind paraphrase 중복) | semantic_dedup.py:1 |
| `oracle_lens.py` | 나생문 oracle 렌즈 thin re-export (정본 = `engine/naesengmoon/oracle_lens.py`) | oracle_lens.py:1 |

---

## 5. Covenant — archive-only (코드로 강제)

`# src: kg_adapter.py:6-9 (docstring)` · `# src: CONTRACT_OccamArchiveRecord_v1_2026-05-27 (KG)`

- **R1 no-delete**: `FORBIDDEN_TOKENS = ("DELETE","DETACH","REMOVE")` — write cypher에 있으면 `build_supersede`가 `AssertionError`로 차단. occam.py·kg_adapter에 delete 함수 부재. `# src: kg_adapter.py:26,95-97`
- **R2 twin-required**: 대체 active twin 없는 n=1 노드 archive 금지 (twin 없으면 σ=0). `# src: CONTRACT rules R2`
- **R3 truth-centered**: recency 아님, entropy/MDL redundant clutter만. `# src: CONTRACT rules R3`
- **R4 reversible**: provenance만으로 active 복원 가능 (label 제거 + valid_to=null). `# src: CONTRACT rules R4`
- **dry-run 기본**: `apply_supersessions(..., dry_run=True)` 기본 — write_cypher 있어도 planned만 반환. `# src: kg_adapter.py:117-137`
- supersede cypher = `SET status='SUPERSEDED' + supersededBy/Reason/At` + `MERGE (stale)-[:SUPERSEDED_BY]->(current)`, 원본 보존. self-supersession `stale <> current` 가드. `# src: kg_adapter.py:77-88`

### Archive record shape (mandatory 7 fields)
`# src: CONTRACT_OccamArchiveRecord_v1_2026-05-27.mandatory_fields (KG)`
log-layer 라벨 `:OCCAM_SLICED`(exact-dup) 또는 `:ARCHIVED`(superseded) + `valid_to` (bitemporal close, active = NULL) + `occam_archived_at` / `occam_archived_by` / `occam_archive_reason` [enum: exact_duplicate / superseded_concept / stale_lineage / dead_code] + active twin 포인터 (`occam_active_twin_name` 또는 `SUPERSEDED_BY` edge) + `restorable=true`.

---

## 6. Gotchas (lesson-grounded)

| 함정 | 교훈 | KG |
|---|---|---|
| filesystem만 스캔 | 본령(KG node-dedup) 놓침. cypher dedup이 PRIMARY | `lesson-occam-must-query-kg-node-dedup-not-just-filesystem-2026-05-27` |
| bare name으로 supersede | 다른 폴더 같은 basename = 다른 파일 (over-match 재앙, 2회 재발). dedup key는 타입별: SourceCodeNode=sourcePath, Ref/Web=url, Directory=path, canon=name | SKILL.md §핵심 |
| invocation을 KG mention proxy로 추정 | `n.name CONTAINS sk` 카운트는 양방향 false positive. `~/.claude/projects/<proj>/*.jsonl` tool_use 블록 grep으로 실측 | `lesson-occam-proxy-strength-needs-empirical-spot-check-2026-05-28` |
| symlink 따라 안 감 → live 파일이 false-orphan | `scan_disk_paths`는 `followlinks=True` + depth 가드 (realpath dedup 안 함; symbolic alias 공존이 정전 패턴) | `# src: occam_runner.py:42-67` |
| 이미 SUPERSEDED 노드 재-아카이브 | read cypher가 `s.status <> 'SUPERSEDED'` 필터 (dogfood 교훈) | `# src: kg_adapter.py:31` |
| 낡은것 정리를 유레카로 | 죽은중복=오캄(archive) vs 반복패턴→추상=유레카(추상화). 치우면 오캄, 올리면 유레카 | SKILL.md §What NOT To Do |

---

## 7. References

- `../SKILL.md` · `engine/occam/SCORING_THEORY.md` · `engine/occam/README.md`
- KG: `occam-kam-canonical-2026-05-26` (`:LegionCommander`), `consensus-occam-entropy-truth-2026-05-26`, `CONTRACT_OccamArchiveRecord_v1_2026-05-27`, `dt-occam-naesengmoon-confidence` (`:DispatchThreshold`), `occam-quant-scoring-engine-2026-06-01` (`:OccamScoringModel`), `verdict-user-occam-gains-ontology-hygiene-responsibility-2026-05-27`
- 사이블: `../longinus/references/theory.md` (binding), `../naesengmoon/` (oracle 렌즈 정본)

# KG: ATOM_Skill_occam (planned), occam-kam-canonical-2026-05-26, occam-pass-kg-wide-2026-05-27
