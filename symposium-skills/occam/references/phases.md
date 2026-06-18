# occam — Phases (per-stage responsibilities + anti-patterns)

> Lazy-load reference. Parent: [`../SKILL.md`](../SKILL.md).
> Engine 정본: `bhgman_tool/engine/occam/`. KG: `occam-kam-canonical-2026-05-26`, `consensus-occam-entropy-truth-2026-05-26`.
> covenant 전역 (모든 stage): **archive-only, 삭제 0, dry-run 기본, twin 있는 superseded만.**
> # src: bhgman_tool/engine/occam/occam.py docstring + occam_runner.py + SKILL.md "사이클" 표

---

## 0. Pipeline overview

end-to-end orchestration = `run_occam(run_cypher, write_cypher, scope, apply, disk_truth, repo_root)`:
**fetch (KG) → scan_disk → occam_pass (순수 분류) → score (σ) → apply (supersede)**.
read/write IO는 `kg_adapter`, 분류는 `occam.py`, scoring은 `scoring.py`. runner는 orchestration만.
# src: occam_runner.py:run_occam (line 88-105) + module docstring "fetch(KG) → occam_pass(순수 분류) → apply(supersede)"

---

## 1. FETCH — KG SourceCodeNode 조회 (PRIMARY)

`fetch_source_nodes(run_cypher, scope)` → `NodeRecord[]`. cypher가 PRIMARY, filesystem 보조.
- scope=None → `_FETCH_ALL`, scope=문자열 → `sourcePath CONTAINS $scope`. # src: kg_adapter.py:fetch_cypher (line 45-49)
- 필수 필드 게이트: `sha256 IS NOT NULL AND lineCount IS NOT NULL AND sourcePath IS NOT NULL`. # src: kg_adapter.py:_REQUIRED (line 32)
- **이미 SUPERSEDED된 노드는 제외** — `(s.status IS NULL OR s.status <> 'SUPERSEDED')`. 아카이브된 과거를 재-아카이브하지 않는다. # src: kg_adapter.py:_NOT_ALREADY_ARCHIVED (line 30-31, "dogfood 교훈 2026-05-27")
- 결손 row는 방어적 skip (`parse_node_records`). # src: kg_adapter.py:parse_node_records (line 52-66)

**anti-pattern (이 stage)**:
- **filesystem만 스캔** → 본령(중복·낡은 KG 노드)을 놓침. KG cypher dedup이 본령. # src: SKILL.md "핵심 — KG node-dedup이 PRIMARY"; KG: lesson-occam-must-query-kg-node-dedup-not-just-filesystem-2026-05-27
- **SUPERSEDED 재조회** → 이미 아카이브된 노드를 다시 후보화 (re-archive 회귀). FETCH WHERE 절이 차단.

---

## 2. SCAN_DISK — 디스크 실존 경로 집합 (optional, move/orphan 탐지 활성)

`scan_disk_paths(repo_root)` → `frozenset[normalize_path]`. `occam_pass(disk_paths=)`에 주입.
repo_root=None이면 same-path 중복(mode-1)만; 주면 sha-이동(mode-2)+disk-orphan(mode-3) 추가.
# src: occam_runner.py:scan_disk_paths (line 42-67) + run_occam (line 102)

**anti-pattern (이 stage)**:
- **symlink 미추적** → 살아있는 파일이 false-orphan으로 잡힘. `followlinks=True` 필수 (`bhgman_tool/skills/*`는 SYMPOSIUM/SKILLS 심볼릭 링크 = 정전화). # src: scan_disk_paths docstring (line 47-48)
- **realpath 기반 dedup** → 동일 실디렉터리의 여러 symbolic alias 중 한쪽을 통째 skip → KG가 저장한 symbolic path가 false-orphan. (self-dogfood 2026-05-28: skills/* 83 file false-orphan.) symbolic path는 그대로 walk, cycle은 depth 가드. # src: scan_disk_paths docstring (line 49-53)
- **과대포함 기피** → 확장자 무관 전부 포함이 의도. 과대포함은 occam을 더 보수적으로만 만든다 (false-orphan 차단 > true-orphan 누락). # src: scan_disk_paths inline comment (line 64-65)

---

## 3. OCCAM_PASS — 순수 분류 (3 탐지 모드)

`occam_pass(nodes, disk_truth, disk_paths, score_meta, scoring_config)` → `OccamReport`.
KG/IO 없는 순수 함수. SKILL 사이클의 SELECT→GROUP→PICK_CURRENT→GUARD→SUPERSEDE 5단계가 여기 산다. # src: occam.py:occam_pass (line 166-234); SKILL.md "사이클 (occam_pass)" 표

| mode | 탐지 | confidence | 동작 |
|------|------|-----------|------|
| **1 same-path 중복** | `normalize_path`로 abs/rel lineage 통합 후 size>1 그룹 | disk sha 일치=HIGH, 없으면 max line_count=MEDIUM | stale → SupersessionCandidate |
| **2 sha-이동** (disk_paths 필요) | 동일 sha·다른 정규화경로 = 파일 이동, KG 옛 경로 잔존 | HIGH (content-identical) | 디스크에 없는 경로 노드를 live twin으로 supersede |
| **3 disk-orphan** (disk_paths 필요, **flag-only**) | 디스크에 경로 없고 동일-sha live twin도 부재 | — | `report.orphans`로 surface, **auto-supersede 안 함** (machloket/Eilu va-Eilu) |
# src: occam.py module docstring (line 5-15) + _detect_sha_moves (line 63-102) + _detect_disk_orphans (line 105-127)

내부 단계 (mode-1):
- **PICK_CURRENT** `_pick_current`: disk sha 일치 노드 = HIGH keep; 없으면 max line_count = MEDIUM keep. # src: occam.py:_pick_current (line 48-54)
- **GUARD**: `len(group) < 2` (twin 없음)이면 `continue` — 단독 노드는 손대지 않음. # src: occam.py:occam_pass (line 189-190)
- **SUPERSEDE**: stale → `SupersessionCandidate(action="SUPERSEDED_BY")`. delete 함수 자체가 없음. # src: occam_models.py:SupersessionCandidate (line 27-39)

**anti-pattern (이 stage)**:
- **bare name으로 supersede** → 다른 폴더 같은 basename = 다른 파일 (over-match 재앙, lesson 2회 재발). dedup key는 타입별: SourceCodeNode=**sourcePath**(name 아님!), ReferenceDocument/WebSourcePage=url, Directory=path, AbstractNode canon=name. # src: SKILL.md dedup-key 표 + "over-match 금지"; KG: lesson-occam-must-query-kg-node-dedup-not-just-filesystem-2026-05-27
- **disk-orphan 자동 supersede** → machloket 위반. live twin 없는 orphan은 flag-only, 판단은 사용자/Longinus. # src: occam_models.py:OccamReport docstring (line 44-49)
- **전부 live거나 전부 orphan인 sha-그룹 처리** → mode-2는 (live AND orphan) 둘 다 있을 때만. 전부 live=디스크 사본 보존, 전부 orphan=mode-3로. # src: occam.py:_detect_sha_moves (line 80-82)

---

## 4. SCORE — supersession σ ∈ [0,1] (선택, score_meta 주입 시)

`score_node(meta, config)` → `SupersessionScore`. 후보별 *얼마나 안전하게 아카이브 가능한가*를 연속값으로. enum(HIGH/MEDIUM = disk sha 확정도)을 대체하지 않고 정밀화 (σ = 아카이브 안전도).
정전 grounding: "entropy selects, truth-guard gates". # src: scoring.py module docstring (line 1-36); KG: consensus-occam-entropy-truth-2026-05-26

- **candidacy C** (선별, "entropy selects") = noisy-OR of 3 신호: redundancy r (MDL/Kolmogorov), staleness s (Ebbinghaus 지수감쇠), deadness d (invocation 사용기반). `C = 1 − (1−r)(1−s)(1−d)` (Pearl 1988). # src: scoring.py:candidacy (line 158-160)
- **guard G** (거부권, "truth-guard gates") = `(1−e)·twin_gate`. entrenchment e (AGM Gärdenfors–Makinson 1988); canonical/lesson/contract/verdict = e=1.0 ⇒ G=0 ⇒ never archive. # src: scoring.py:guard + _ENTRENCHMENT (line 64-77, 168-171)
- **σ = C · G**. verdict: σ≥0.7 SUPERSEDE / 0.3≤σ<0.7 VERIFY (나생문 dispatch) / σ<0.3 KEEP / e=1.0 PROTECTED / twin 부재 FLAG_ONLY. # src: scoring.py:_verdict (line 211-223); 임계 = dt-occam-naesengmoon-confidence (θ=0.7)

**anti-pattern (이 stage)**:
- **canonical tier 아카이브** → e=1.0 → σ=0 강제 (PROTECTED). never-archive 코어 위반 차단은 점수에 박혀 있다. # src: scoring.py:NEVER_ARCHIVE_TIERS (line 77) + score_node 불변식 (line 180-184)
- **twin/후속 없이 supersede** → has_successor=False → σ=0 (FLAG_ONLY). AGM contraction은 후속자 없이 믿음을 버리지 않는다. # src: scoring.py:guard (line 168-171) + docstring (line 21-23)
- **magic number 산포** → 모든 자유 파라미터는 `ScoringConfig` 한 곳 (halflife 90d, invocation_scale 3, θ_supersede 0.7, θ_keep 0.3). # src: scoring.py:ScoringConfig (line 88-103)

---

## 5. APPLY — supersede write (covenant 강제)

`apply_supersessions(report, write_cypher, dry_run)` → `ApplyResult`. **dry_run 기본** — write_cypher 있어도 dry_run=True면 실행 안 함, planned cypher만 반환.
# src: kg_adapter.py:apply_supersessions (line 117-149)

- supersede cypher = `SET stale.status='SUPERSEDED' + supersededBy/Reason/At + MERGE (stale)-[:SUPERSEDED_BY]->(current)`. 원본 노드 보존 = reversible. # src: kg_adapter.py:_SUPERSEDE_CYPHER (line 77-88)
- self-supersession 차단: `WHERE stale <> current` (exact-dup 동명 no-op). # src: kg_adapter.py:_SUPERSEDE_CYPHER (line 80)
- **covenant 코드 강제**: `build_supersede`가 write cypher에 `DELETE/DETACH/REMOVE` 토큰 있으면 `AssertionError`. 향후 cypher 편집 시 회귀 차단. # src: kg_adapter.py:FORBIDDEN_TOKENS + build_supersede assert (line 25-26, 91-103)

**anti-pattern (이 stage)**:
- **delete** → covenant 위반. archive(SUPERSEDED)만. delete 함수 자체가 엔진에 부재. # src: SKILL.md "What NOT To Do"; kg_adapter.py docstring (line 6-9)
- **dry-run 건너뛰고 바로 write** → dry_run=True가 기본. `--apply` 명시 시에만 write. CLI도 dry-run 기본 (`(dry-run — pass --apply to write SUPERSEDED; reversible via status+edge)`). # src: cli/commands.py:cmd_occam (line 591, 625-629)

---

## 6. ONTOLOGY pass — DL 정합성 + scored 위생 (별도 entrypoint)

`ontology_pass(classes, instances, config)` → `OntologyReport`. 사용자 verdict로 추가된 책무: 단순 dedup을 넘어 형식 온톨로지 / Description Logic 정합성. # src: ontology.py module docstring (line 1-32); KG: verdict-user-occam-gains-ontology-hygiene-responsibility-2026-05-27

6 DL 검사 (Baader DL Handbook + OWL 2 DL grounding):
1. SUBSUMPTION_CYCLE — subClassOf는 DAG여야 (C ⊑ … ⊑ C 순환).
2. DANGLING_PARENT — 존재하지 않는 상위 클래스 subClassOf.
3. DANGLING_TYPE — 존재하지 않는 클래스를 rdf:type.
4. PUNNING — 같은 이름이 OntologyClass ∧ OntologyInstance.
5. UNSATISFIABLE_CLASS — disjoint 두 클래스의 공통 하위 (⊥).
6. DISJOINTNESS_VIOLATION — 한 instance가 disjoint 두 클래스의 type.
# src: ontology.py:ViolationKind (line 49-55) + docstring (line 14-21)

정합성(consistency) = 1·5·6 부재 ⇒ DL-consistent; 2·3·4는 무결성/위생 경고 (분리). 위생: superseded/stale 온톨로지 노드는 `score_node`로 σ 매겨 supersession 후보화 (§4와 동일 scoring 재사용). # src: ontology.py docstring (line 23-25) + _hygiene_scoring (line 292-313)

**anti-pattern (이 stage)**:
- **inconsistency와 무결성 경고 혼동** → 1·5·6만 정합성을 깨고, 2·3·4는 hygiene 경고. `is_consistent`는 `_INCONSISTENCY_KINDS`만 본다. # src: ontology.py:_INCONSISTENCY_KINDS (line 58-65) + is_consistent (line 108-111)
- **active 노드를 위생 대상화** → active·사용중·중복없음·신선 = 위생 대상 아님; SUPERSEDED도 제외 (재아카이브 금지). # src: ontology.py:_is_hygiene_candidate (line 285-289)

---

## 7. SEMANTIC_DEDUP pass — 임베딩 near-duplicate (sha256-blind 보완)

`run_semantic_dedup(items, embed_fn, threshold, ...)` → `SemanticDedupReport`. occam.py가 byte-동일 중복만 보는 자리를, 패러프레이즈된 Lesson·다시 쓴 Finding을 cosine ≥ θ(기본 0.95)로 surface. # src: semantic_dedup.py module docstring (line 1-17); KG: rf-semdist-occam-2026-06-01

- 결정론: embed_fn 주입식(테스트=fake, 실전=sentence-transformers 768d). keep/drop tiebreak 결정론 (weight 큰 쪽 유지, 동률이면 id 작은 쪽). # src: semantic_dedup.py:_pick_keep_drop (line 56-61)
- **PROPOSE만**: 클러스터 transitive 자동해소 안 함, 쌍만 surface (human/verdict gate). # src: semantic_dedup.py docstring (line 11-12)
- 동일 covenant: dry-run 기본, archive-only, FORBIDDEN_TOKENS assert. cypher 키는 allowlist(`name/findingId/id`)로 주입 차단. # src: semantic_dedup.py:_KEY_ALLOWLIST + plan_supersession (line 31-32, 98-111)

**anti-pattern (이 stage)**:
- **cluster transitive 자동해소** → 쌍만 PROPOSE, 자동 클러스터 병합 금지 (human gate). # src: semantic_dedup.py docstring (line 11-12)
- **임의 키 prop으로 supersede** → cypher 주입. `_KEY_ALLOWLIST` 밖의 key는 `ValueError`. # src: semantic_dedup.py:plan_supersession (line 99-101)

---

## 8. Legion handoff — VERIFY escalation

occam이 legion `CommanderStage("occam", "정리", ("run_cypher",), ("hygiene",), _run_hygiene)`로 조립될 때, σ가 회색지대(VERIFY)면 oracle gate는 주입식으로 나생문에 escalate (legion은 occam/oracle_lens에 hard-import 결합 안 함). occam의 oracle_lens는 정본 `engine/naesengmoon/oracle_lens.py`의 back-compat re-export (정의 없음, drift 불가). # src: legion/commanders.py:_run_hygiene (line 157-180) + CommanderStage (line 291); occam/oracle_lens.py docstring (line 1-9)

---

## 9. References

- Engine 정본: `bhgman_tool/engine/occam/{occam,occam_runner,occam_models,kg_adapter,scoring,ontology,semantic_dedup,oracle_lens}.py`
- `../SKILL.md` (사이클 / 가드 / What NOT To Do 표)
- KG: `occam-kam-canonical-2026-05-26`, `consensus-occam-entropy-truth-2026-05-26`, `verdict-user-occam-gains-ontology-hygiene-responsibility-2026-05-27`, `occam-pass-kg-wide-2026-05-27`, `dt-occam-naesengmoon-confidence`, `lesson-occam-must-query-kg-node-dedup-not-just-filesystem-2026-05-27`, `rf-semdist-occam-2026-06-01`
- 사이블: `../longinus/references/theory.md` (format gold-standard)

# KG: ATOM_Skill_occam, occam-kam-canonical-2026-05-26
