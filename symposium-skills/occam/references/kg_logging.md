# occam — KG Logging (Cypher MERGE/SET schema)

> Lazy-load reference. Parent: [`../SKILL.md`](../SKILL.md).
> Doc purpose: the Cypher schema occam **reads** (dedup candidate selection) and **writes** (supersede/archive). Every claim is grounded in engine code or actual KG node shapes.
> THEORY: no dedicated occam theory dir — harvest is engine + KG only (honest note).
> covenant (코드로 강제): **archive-only, no DELETE/DETACH/REMOVE**. # src: engine/occam/kg_adapter.py:25-26, SKILL.md:13

---

## 1. READ — node selection (SourceCodeNode dedup)

occam's PRIMARY input is a Cypher `MATCH` over `:SourceCodeNode`, not a filesystem scan.
# src: SKILL.md:27-29 ("KG node-dedup이 PRIMARY"), engine/occam/kg_adapter.py:38-49

```cypher
-- _FETCH_ALL (scope=None)
MATCH (s:SourceCodeNode)
WHERE s.sha256 IS NOT NULL AND s.lineCount IS NOT NULL AND s.sourcePath IS NOT NULL
  AND (s.status IS NULL OR s.status <> 'SUPERSEDED')   -- skip already-archived
RETURN s.name AS name, s.sourcePath AS source_path,
       s.sha256 AS sha256, s.lineCount AS line_count
```
```cypher
-- _FETCH_SCOPED (scope=<label|path substring>)  adds:
WHERE s.sourcePath CONTAINS $scope AND ...
```
# src: engine/occam/kg_adapter.py:31-49 (`_REQUIRED`, `_NOT_ALREADY_ARCHIVED`, `_FETCH_ALL`, `_FETCH_SCOPED`, `fetch_cypher`)

**Read constraints / invariants:**
- Required props for a node to be considered: `sha256`, `lineCount`, `sourcePath` (all NOT NULL). Rows missing any are defensively skipped. # src: kg_adapter.py:32, 52-66 (`parse_node_records`)
- Already-`SUPERSEDED` nodes are excluded — "아카이브된 과거를 재-아카이브하지 않는다" (dogfood lesson 2026-05-27). # src: kg_adapter.py:30-31
- **dedup key = sourcePath, NOT name** — `INDEX.md`/`SOURCES.md` share a basename across folders = different files. `normalize_path` unifies abs (`/Users/.../bhgman_tool/X`) ↔ rel (`bhgman_tool/X`) lineages by keeping text after the `bhgman_tool/` marker. # src: SKILL.md:31-39, engine/occam/occam.py:31-39
- **R5 read-filter** (active-read default): bare-name `MATCH` should append `WHERE NOT (n:OCCAM_SLICED OR n:ARCHIVED)` so archived nodes don't leak into normal sweeps. # src: KG `CONTRACT_OccamArchiveRecord_v1_2026-05-27`.rules (R5, `cypher-archived-filter-protocol-2026-05-19`)

---

## 2. WRITE — supersede (engine schema, archive-only)

The engine writes exactly one parameterized statement per candidate. dry-run is the default; a write only fires when `apply=True` AND a `write_cypher` runner is supplied.
# src: engine/occam/kg_adapter.py:77-103, 117-149; occam_runner.py:104

```cypher
MATCH (stale:SourceCodeNode {name: $stale_name})
MATCH (current:SourceCodeNode {name: $current_name})
WHERE stale <> current                         -- block self-supersession (no-op for exact-dup同名)
SET stale.status          = 'SUPERSEDED',
    stale.supersededBy    = $current_name,
    stale.supersededReason = $reason,
    stale.supersededAt    = datetime(),
    stale.occamPass       = 'occam'
MERGE (stale)-[:SUPERSEDED_BY]->(current)      -- reversible: original node preserved + edge
RETURN stale.name AS superseded, current.name AS current
```
# src: engine/occam/kg_adapter.py:77-88 (`_SUPERSEDE_CYPHER`)

**Params** (built by `build_supersede`): `stale_name`, `current_name`, `reason` (from `SupersessionCandidate.stale/current/reason`). # src: kg_adapter.py:98-103

**Covenant enforcement (code-level):** `build_supersede` upper-cases the cypher and asserts none of `("DELETE","DETACH","REMOVE")` appear, raising `AssertionError` if a future edit reintroduces a destructive token. There is **no delete function** anywhere in the package. # src: kg_adapter.py:26, 94-97; occam_models.py:36 (`action="SUPERSEDED_BY"` fixed)

**Write nodes/edges produced:**
| element | label / type | key props set | meaning |
|---|---|---|---|
| stale node (mutated) | `:SourceCodeNode` | `status='SUPERSEDED'`, `supersededBy`, `supersededReason`, `supersededAt`, `occamPass` | the archived old lineage |
| edge | `(:SourceCodeNode)-[:SUPERSEDED_BY]->(:SourceCodeNode)` | — | points stale → current (cardinality-1) |

Confirmed against live KG: 81 `:SourceCodeNode` with `status='SUPERSEDED'` + 87 `:SUPERSEDED_BY` edges; e.g. `l8ind-models.py` → `supersededBy='l8ind-induction_models.py'`. # src: KG count query (read_neo4j_cypher, 2026-06-02)

---

## 3. WRITE — detection modes (what becomes a candidate)

`occam_pass` is pure (no IO); the runner feeds it KG rows + optional disk truth, then `apply_supersessions` writes §2 cypher per candidate. # src: engine/occam/occam_runner.py:88-105

| mode | trigger | confidence | action |
|---|---|---|---|
| 1 same-path dup | ≥2 nodes share `normalize_path` | HIGH if disk sha matches current, else MEDIUM (max line_count = keep) | supersede |
| 2 sha-move | identical `sha256`, different normalized path, one path absent on disk | HIGH (content-identical to live twin) | supersede |
| 3 disk-orphan | normalized path absent on disk AND no same-sha live twin | — | **flag-only** in `OccamReport.orphans` — NOT auto-superseded (machloket / Eilu va-Eilu) |
# src: engine/occam/occam.py:5-16 (module docstring), 63-127 (`_detect_sha_moves`, `_detect_disk_orphans`), 166-234 (`occam_pass`)

- **PICK_CURRENT**: disk-sha match ⇒ HIGH; else `max(line_count)` heuristic ⇒ MEDIUM. # src: occam.py:48-54 (`_pick_current`), occam_models.py:12-14 (`Confidence`)
- **GUARD (twin-only)**: a path group with `len < 2` is never touched; single nodes are left alone. # src: occam.py:189-191
- Modes 2/3 require `disk_paths` (from `scan_disk_paths`, `followlinks=True` to honor symlinked `skills/*`). Without it, only mode-1 runs (caller-behavior-preserving). # src: occam_runner.py:42-67, occam.py:208-214

---

## 4. WRITE — ontology-layer hygiene (DL consistency)

Per `verdict-user-occam-gains-ontology-hygiene-responsibility-2026-05-27`, occam also audits the formal-ontology layer. `ontology_pass` is pure surface-detection — same covenant (no delete). # src: engine/occam/ontology.py:1-32, 319-360; KG `verdict-user-occam-gains-ontology-hygiene-responsibility-2026-05-27` (`:Verdict`)

**Node records it reads** (caller materializes from KG):
- `OntologyClassRecord`: `name`, `parents` (subClassOf), `disjoint_with` (disjointWith), `status`, `age_days`, `invocation_count`, `tier`, `redundancy`, `has_successor`. # src: ontology.py:68-81
- `OntologyInstanceRecord`: `name`, `types` (rdf:type). # src: ontology.py:83-89

**6 DL checks** (Baader *DL Handbook* + W3C OWL 2 DL grounding): `SUBSUMPTION_CYCLE`, `DANGLING_PARENT`, `DANGLING_TYPE`, `PUNNING`, `UNSATISFIABLE_CLASS`, `DISJOINTNESS_VIOLATION`. Consistency = absence of checks 1/5/6; 2/3/4 are integrity/hygiene warnings. # src: ontology.py:14-31, 49-65, 204-279

Stale/redundant classes get σ-scored (`score_node`) → `SUPERSEDE` candidates vs `VERIFY`/`FLAG_ONLY` (machloket). `SUPERSEDED` classes are excluded (no re-archive). # src: ontology.py:285-313 (`_is_hygiene_candidate`, `_hygiene_scoring`)

---

## 5. The hand-cypher archive Contract (CONTRACT_OccamArchiveRecord_v1)

There are **two real archive shapes in the KG**. The §2 engine shape (`status='SUPERSEDED'` + `:SUPERSEDED_BY`) is the automated path. The Contract below is the broader hand-cypher covenant occam passes followed before the engine — also live in the KG (e.g. nodes labeled `:OCCAM_SLICED`/`:ARCHIVED` with `occam_archived_at`/`supersededReason`). # src: KG `CONTRACT_OccamArchiveRecord_v1_2026-05-27` (`:Contract:AbstractNode`); live node sample (occamPass `occam-full-kg-2026-05-28`, 15 nodes)

**mandatory_fields** for an archived node (per the Contract):
1. log-layer label `:OCCAM_SLICED` (exact-dup/redundant) **or** `:ARCHIVED` (superseded version) — C2 binary active/log split.
2. `valid_to` [timestamp] — bitemporal close; active = `valid_to IS NULL` (C4).
3. `occam_archived_at` — slice timestamp.
4. `occam_archived_by` — which pass/cycle (provenance: who).
5. `occam_archive_reason` [enum: `exact_duplicate` / `superseded_concept` / `stale_lineage` / `dead_code`].
6. active-twin pointer: exact-dup → `occam_active_twin_name` property; concept supersession → `:SUPERSEDED_BY` edge → new version (cardinality-1 + who/when/why).
7. `restorable=true` — reversible against misjudgment.
# src: KG `CONTRACT_OccamArchiveRecord_v1_2026-05-27`.mandatory_fields

**Rules:** R1 no-delete (full delete needs separate user verdict) · R2 twin-required (n=1 node with no replacement = data-loss, never archive) · R3 truth-centered (entropy/MDL redundancy, NOT recency) · R4 reversible (provenance alone restores) · R5 read-filter (§1) · R6 node-body-too (edge/label alone misses node-reading sweeps; concept supersession must also fix prose). # src: KG `CONTRACT_OccamArchiveRecord_v1_2026-05-27`.rules

---

## 6. Provenance fields & cross-cutting invariants

- `occamPass` / `occam_archived_by` records which run did the archiving (live values seen: `'occam'`, `occam-full-kg-2026-05-28`). # src: kg_adapter.py:86, KG node sample
- `OccamReport` carries no delete field — `candidates`, `orphans` (flag-only), `scanned_nodes`, `groups_with_dups`, `notes`. # src: engine/occam/occam_models.py:42-63
- `ApplyResult.dry_run` defaults `True`; planned cyphers are returned without execution when no `write_cypher` runner is given. # src: kg_adapter.py:106-137
- Neo4j-absent CLI path emits the fetch cypher for the parent Claude to run via MCP. # src: SKILL.md:12, occam_runner.py:5-9

---

## 7. References

- Engine: `bhgman_tool/engine/occam/{kg_adapter,occam,occam_models,occam_runner,ontology,oracle_lens}.py`
- SKILL: `../SKILL.md`
- KG nodes (read 2026-06-02): `occam-kam-canonical-2026-05-26` (`:LegionCommander`), `verdict-user-occam-gains-ontology-hygiene-responsibility-2026-05-27` (`:Verdict`), `CONTRACT_OccamArchiveRecord_v1_2026-05-27` (`:Contract`), `occam-pass-kg-wide-2026-05-27` (`:OccamReport`)
- Cross-skill: `../longinus/references/theory.md` (SourceCodeNode 7-tuple it dedups), `../naesengmoon/` (oracle_lens re-export, GATE)

# KG: occam-kam-canonical-2026-05-26, CONTRACT_OccamArchiveRecord_v1_2026-05-27, occam-pass-kg-wide-2026-05-27, lesson-occam-must-query-kg-node-dedup-not-just-filesystem-2026-05-27
