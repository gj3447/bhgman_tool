# eureka — KG Logging Schema

> Lazy-load reference. Parent: [`../SKILL.md`](../SKILL.md).
> What eureka writes/reads to/from Neo4j: node labels, key properties, edges, extraction Cypher.
> KG: `eureka-canonical-2026-05-26` (`:LegionCommander`, verb=창조/induce, concrete→abstract↑).
> 핵심 경계: 유레카는 **PROPOSE까지만** — auto-commit 금지, 실현(materialize)은 dual=하데스.
> # src: bhgman_tool/engine/eureka/README.md L8-11

---

## 1. Node label written: `:AbstractClass`

L8-induced abstract category over L1-L7 ReferenceSite member nodes. Emitted by
`stage_5_naesengmoon_gate` (status flip) and gated by `validator.gate_before_merge` before any MERGE.
# src: engine/eureka/induction_models.py L42-43 (docstring), pipeline.py L282-286, L346-356

### Required properties
# src: engine/eureka/induction_models.py L45-50; CONTRACT_AbstractClass_v1 §1 (THEORY/LONGINUS/CONTRACT_AbstractClass_v1_2026-05-20.md L12-21)

| field | type | note |
|---|---|---|
| `name` | string (≤128) | `ac_<method>_<cycle_id>_<NNNN>` auto-gen, or kebab-case slug. Validated: must start `ac_`/`AC_` or be alnum-slug. # src: induction_models.py L60-71; name builder pipeline.py L129 `f"ac_{tag}_{cycle_id}_{i:04d}"` |
| `summary` | string (≤240) | `"{METHOD} concept: {intent_summary}"`. # src: pipeline.py L132-136 |
| `inductionMethod` | string (registry-validated, NOT closed enum) | open via `registry.register_method` (OCP). 5 default names below. # src: induction_models.py L26-31, L73-84 |
| `cycleId` | string | e.g. `eureka-academic-grounding-2026-05-26`. # src: induction_models.py L48 |
| `createdAt` | datetime (UTC) | # src: induction_models.py L49; pipeline.py L126 `dt.datetime.now(dt.timezone.utc)` |
| `status` | enum (below) | default `PROPOSED`. # src: induction_models.py L50 |

`InductionMethod` values: `fca` (default) / `amie3` / `leiden-llm` / `manual` / `unknown`.
# src: induction_models.py L26-31

`AbstractClassStatus` values: `PROPOSED` / `VerdictPending` / `CANONICAL` / `CANONICAL_DELEGATED` / `REJECTED`.
Note the on-disk string for VERDICT_PENDING is `"VerdictPending"` (not screaming-case). # src: induction_models.py L34-40

### Optional / induced-only properties
# src: induction_models.py L52-58; CONTRACT_AbstractClass_v1 §1 선택 properties (L23-33)

| field | type | populated when |
|---|---|---|
| `extent` | list[str] | FCA Galois extent (member node names). **Required** if inductionMethod is automated. # src: induction_models.py L52, L86-103 |
| `intent` | list[str] | FCA Galois intent (`facet:value` attribute strings). **Required** when automated. # src: induction_models.py L53 |
| `stabilityScore` | float [0,1] | Roth-Obiedkov-Kourie 2008 concept stability. **Required** when automated. # src: induction_models.py L54, L86-103 |
| `silhouette` | float [-1,1] | Rousseeuw 1987 (clustering inductions). # src: induction_models.py L55 |
| `modularity` | float [-0.5,1] | Newman 2006 (community inductions). # src: induction_models.py L56 |
| `gamma` | float (>0) | Leiden γ-resolution. # src: induction_models.py L57 |
| `provenance` | dict | ReferenceSite v1 7-tuple reuse (sourceId/sourcePath/line_range/sha256/sha256_baseline/kg_anchor/last_validated). # src: induction_models.py L58; CONTRACT_AbstractClass_v1 L33 |

**Model invariant**: if `inductionMethod` is an automated inducer (per `registry.is_automated`),
then `extent`, `intent`, `stabilityScore` MUST all be non-null, else schema rejected.
# src: induction_models.py L86-103

**Actual KG instance** (only one extant, an autonomous-propose smoke test):
node `ac_l8_smoke_test_2026-05-20_v1` carries labels
`[:VerdictPending, :VerdictProposal, :AbstractClass]` with extra keys
`smoke_test`, `depth`, `preliminary_autonomous_propose`, `user_verdict_trigger_required`.
This shows VERDICT_PENDING `:AbstractClass` co-labels `:VerdictProposal` and uses the
preliminary-autonomous-propose pattern (per memory `feedback_preliminary_autonomous_propose_pattern`).
# src: live Neo4j MATCH (a:AbstractClass) — read 2026-06-02

---

## 2. Edge written: `(:AbstractClass)-[:GENERALIZES]->(member)`

Direction = **option A**: src=AbstractClass (general), tgt=member (specific).
Confirmed empirically 2026-05-20 over 181 sample edges
(Semaphore→Mutex / CategoryTheory→TypeTheory / Stokes'→Green's all general→specific).
# src: induction_models.py L106-111; CONTRACT_AbstractClass_v1 §2 (L39-47)

One edge is emitted per member in the concept's extent. # src: pipeline.py L144-153

### Edge properties
# src: engine/eureka/induction_models.py L113-118; CONTRACT_AbstractClass_v1 §2 (L49-58)

| field | type | required | note |
|---|---|---|---|
| `confidence` | float [0,1] | required when `induced=true` | = concept stability (FCA σ / PCA / silhouette). # src: induction_models.py L113, L130-134; pipeline.py L147 |
| `method` | string (registry-validated) | required | induction operator name. # src: induction_models.py L114, L120-128 |
| `communityId` | str | nullable | only for Leiden community inductions. # src: induction_models.py L115 |
| `cycleId` | string | required | # src: induction_models.py L116 |
| `createdAt` | datetime (UTC) | required | # src: induction_models.py L117 |
| `induced` | bool | required | true = L8 induction result; pre-L8 manual = false. # src: induction_models.py L118 |

**Eilu va-Eilu coexistence**: `:IS_A` (instance-of) / `:SUBCLASS_OF` (RDFS child→parent) /
`:GENERALIZES` (L8 induced, general→specific) all coexist on the same node pair — erase forbidden.
Only `:GENERALIZES` with `induced=true` is L8/eureka origin.
# src: CONTRACT_AbstractClass_v1 §3 (L62-70)

> Read-back caveat: legacy `:GENERALIZES` edges in the live KG carry **empty property keys**
> (`method`/`induced` = null) — these predate the L8 contract and are NOT eureka-emitted.
> Filter on `induced=true` to read only eureka output. # src: live Neo4j MATCH ()-[:GENERALIZES]->() — read 2026-06-02

---

## 3. Read path — formal context extraction (stage_0 KG-EXTRACT)

`build_formal_context(run_cypher, cfg)` reads the KG into an FCA formal context
`dict[object_name, frozenset["facet:value"]]` before induction. Naive whole-KG FCA = garbage
(correlated-facet tautology + mega-hub pollution + bulk noise), so **3 pre-filters** gate signal↔garbage.
# src: engine/eureka/formal_context_builder.py L1-17 (docstring); README.md L40-42

Extraction Cypher (`build_extraction_cypher`):
```cypher
MATCH (o)-[r]->(v)
WHERE type(r) IN $facet_rels                              -- ③ independent orthogonal facets only
  AND v.name IS NOT NULL
  AND NONE(l IN labels(o) WHERE l IN $bulk_labels)        -- ① bulk-exclude noise labels
WITH o, count(DISTINCT v) AS facet_deg,
     collect(DISTINCT type(r) + ':' + v.name) AS attrs
WHERE facet_deg <= $hub_cap AND size(attrs) >= $min_facets  -- ② hub degree-cap, ③ ≥2 facets
RETURN o.name AS object, attrs AS attributes
```
# src: formal_context_builder.py L44-62

`FormalContextConfig` defaults (empirical, not magic numbers):
- `facet_rels = ("ALIGNS_WITH_AXIS", "USES_ABSTRACT_DOMAIN")` — first viable independent facet pair
- `bulk_labels = {"KG_AI", "Comment", "OCCAM_SLICED", "ARCHIVED"}` — measured noise labels
- `hub_degree_cap = 4`, `min_facets_per_object = 2`
# src: formal_context_builder.py L29-42

Returned metadata: `objects`, `avg_intent`, `facet_rels`, `bulk_excluded`, `hub_cap`.
Empirical oracle on real KG: 321 objects / avg_intent 3.63 → non-trivial concepts.
# src: formal_context_builder.py L88-96; pipeline.py L371 (run_from_kg docstring)

`attribute = "facet:value"` (facet prefix preserved → becomes AbstractClass `intent`).
# src: formal_context_builder.py L12, L51

---

## 4. Gates between read and write (what blocks a MERGE)

Pipeline order: 1-extract → 2-community → 3-summarize → 4-induce → 4.5-quality →
4.7-oracle → 4.8-fidelity → 5-naesengmoon → 5.5-pre-merge-validator.
# src: engine/eureka/pipeline.py L304-360; README.md L28-39

- **4.5 Quality (HARD)** `quality_gate.evaluate`: silhouette ≥0.50 / modularity ≥0.30 /
  fca_stability ≥0.50 / ami ≥0.50, and Goodhart cap >0.95 = reject as artifact.
  FAIL → pipeline returns, no write. # src: quality_gate.py L18-22, L60-71; pipeline.py L327-336
- **4.7 Oracle (HARD pre-gate)** `oracle_lens.kg_oracle_gate` — deterministic well-formedness on
  each candidate: extent recount (|extent| ≥ min_extent) / non-empty intent / acyclic (name ∉ extent) /
  stability ≥ min_stability. First FAIL short-circuits, no write. # src: oracle_lens.py L44-93; pipeline.py L338-341
- **4.8 Fidelity (SOFT)** consilience witness — warns only, never blocks. # src: pipeline.py L257-279
- **5 Naesengmoon** flips status `PROPOSED → VerdictPending` (LLM judgment lens deferred to user verdict).
  # src: pipeline.py L282-286
- **5.5 Pre-merge validator (HARD)** `validator.gate_before_merge` runs Pydantic schema validation on
  the AbstractClass + GeneralizesEdge batch (application-side, because APOC trigger
  `t_abstractclass_required_fields` is BLOCKED on Neo4j Community without admin). Raises `SchemaViolation`.
  # src: validator.py L1-46; CONTRACT_AbstractClass_v1 §4 (L74-78)

---

## 5. References

- engine: `bhgman_tool/engine/eureka/{induction_models,formal_context_builder,validator,oracle_lens,quality_gate,pipeline}.py`, `README.md`
- contract: `SYMPOSIUM/THEORY/LONGINUS/CONTRACT_AbstractClass_v1_2026-05-20.md`
- KG nodes: `eureka-canonical-2026-05-26`, `t_abstractclass_required_fields`,
  ResearchFinding cycle `eureka-academic-grounding-2026-05-26` (16 findings)
- 사이블: `../longinus/references/theory.md` (ReferenceSite 7-tuple, format gold-standard)

# KG: eureka-canonical-2026-05-26, contract-abstractclass-schema-canonical-2026-05-20
