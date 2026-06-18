# eureka — Gates

> Lazy-load reference. Parent: [`../SKILL.md`](../SKILL.md).
> KG: `eureka-canonical-2026-05-26`, `consensus-eureka-design-synthesis-2026-05-27`.
> The validation/quality/fidelity gate stack between PROPOSE and MATERIALIZE. Eureka *proposes*; the gates decide.

---

## 0. Where gates sit in the pipeline

Eureka induces candidate abstractions (`:AbstractClass`, status `PROPOSED`) and then **stops** — it never auto-commits; MATERIALIZE (abstract→concrete) is Hades' verb, not Eureka's.
The gate stack is everything between induction (stage 4) and the merge boundary (stage 5.5).
`# src: THEORY/유레카/EUREKA_ENGINE_DESIGN.md §"엔진 범위" + engine/eureka/pipeline.py run()`

```
4-induce → 4.5 quality → 4.7 oracle(HARD) → 4.8 fidelity(SOFT) → 5 naesengmoon(judgment) → 5.5 pre-merge validator
```
`# src: engine/eureka/pipeline.py:304-360 run()`

**fail-fast order is load-bearing**: oracle (executable) runs *before* fidelity, because "빌드/테스트 깨지면 의미검증 무의미하므로 선(先) gate" — a malformed concept makes semantic checks meaningless.
`# src: engine/eureka/oracle_lens.py:5; consensus-eureka-design-synthesis-2026-05-27 .hard_truth (C3 "oracle을 fidelity 앞 fail-fast")`

---

## 1. Stage 4.5 — Quality gate (statistical, HARD)

Compression + cluster stability before any promotion. Pure function over up-to-4 scalar metrics; first failing scalar fails the report.
`# src: engine/eureka/quality_gate.py evaluate()`

| metric | threshold | citation | applies when |
|--------|-----------|----------|--------------|
| silhouette s̄ | ≥ 0.50 | Rousseeuw 1987 | cluster-based induction |
| modularity Q | ≥ 0.30 | Newman 2006 PNAS | community-based induction |
| FCA concept stability σ | ≥ 0.50 | Roth-Obiedkov-Kourie 2008 | formal context applicable |
| AMI | ≥ 0.50 | Vinh-Epps-Bailey 2010 | supervised re-runs |
| **Goodhart cap** | **> 0.95 ⇒ REJECT** | Zaveri 2016 | any metric (artifact guard) |

`# src: engine/eureka/quality_gate.py:1-23 (SILHOUETTE_MIN/MODULARITY_MIN/FCA_STABILITY_MIN/AMI_MIN/GOODHART_CAP)`
`# src: KG seed-prom16lag-cons-quality-gate-silhouette-modularity-2026-05-20 .description (verbatim threshold+citation match)`

Pass/fail semantics:
- A `None` metric is **skipped** (not failed) — only provided metrics constrain.
- **all-`None` ⇒ FAIL** ("no quality metric provided") — a concept must justify itself by at least one statistic.
- The Goodhart cap is two-sided in spirit: too-high (>0.95) is rejected as a suspected artifact, not celebrated.
`# src: engine/eureka/quality_gate.py:44-83 evaluate()`

In the wired pipeline, only `fca_stability=avg_stability` (mean over induced ACs) is fed; FAIL returns the run immediately (`return pr`).
`# src: engine/eureka/pipeline.py:326-336`

> Note: the canonical FCA-stability *floor* drifted. The 2026-05-20 seed and the IMPL report cite σ ≥ 0.30–0.40 (Kuznetsov); the shipped `quality_gate.py` hard-codes `FCA_STABILITY_MIN = 0.50`. `# src: quality_gate.py:20 vs KG seed-...-2026-05-20 .description ("σ ≥ 0.40") vs THEORY/유레카/PROM_16_EUREKA_IMPL_REPORT.md:20 ("stability index ≥0.3~0.4")`

---

## 2. Stage 4.7 — Oracle gate (executable, HARD GATE)

The 나생문 *oracle lens-class*: verification by **actually running a tool**, not by LLM judgment. This is the compiler-나생문 family — TDD's test is exactly this (RED = `passed=False`).
`# src: engine/eureka/oracle_lens.py:1-7; engine/naesengmoon/oracle_lens.py:1-6 (shared primitive)`

**HARD GATE semantics**: on FAIL, reject without debate, and **short-circuit at the first FAIL**. A FAIL blocks entry to the judgment lens (stage 5).
`# src: engine/naesengmoon/oracle_lens.py:65-78 run_oracle_gate(); engine/eureka/pipeline.py:338-340`

The primitive (`OracleLens`/`OracleVerdict`/`run_oracle_gate`/`subprocess_runner`) lives in the 나생문 package and is shared by occam + eureka (dedup 2026-06-01). `OracleLens.verify()` runs `command`, `passed = (exit==0)`.
`# src: engine/naesengmoon/oracle_lens.py:50-62; engine/eureka/oracle_lens.py:8-28; KG wqi-extract-shared-naesengmoon-oracle-primitive-2026-05-27`

Two backends, asymmetric risk — the eureka module defines both:

### (a) KG backend — `kg_oracle_gate()` (always runs on candidate concepts)
Deterministic **well-formedness invariants** ("is the abstraction formally well-formed?"), the analog of compile/test. checkable only — semantic validity is the judgment lens' job. First FAIL short-circuits.

| # | check | kind | FAIL condition |
|---|-------|------|----------------|
| 1 | extent recount | `recount` | `len(extent) < min_extent` (claimed support not real) |
| 2 | schema | `schema` | empty `intent` (degenerate concept) |
| 3 | acyclic | `acyclic` | `name ∈ extent` (self-referential = cycle) |
| 4 | recount/stability | `recount` | `stabilityScore < min_stability` (claimed stability not real) |

`# src: engine/eureka/oracle_lens.py:44-93 kg_oracle_gate(); defaults min_extent=2, min_stability=0.5`
Pipeline passes `min_extent=config.fca_min_extent`, `min_stability=config.fca_min_stability`.
`# src: engine/eureka/pipeline.py:221-223`

### (b) shell backend — `default_eureka_lenses()` (opt-in, code-materialize path)
checkable CODE lenses: an abstraction must pass lint + test.
- `ruff check <target>` (kind `typecheck`)
- `pytest -q <target>` (kind `test`)
`# src: engine/eureka/oracle_lens.py:31-41`

Activated only when `config.oracle_lenses` is non-empty; runner defaults to `subprocess_runner`. Recorded as pipeline step `4.7b-naesengmoon-oracle-gate(shell)`.
`# src: engine/eureka/pipeline.py:237-254`

> Boundary warning baked into source: the shell lenses are for the **code** materialize path (Extract Superclass etc.); the KG induction path must use `kg_oracle_gate` — "둘은 다른 backend (위험도 비대칭)". `# src: engine/eureka/oracle_lens.py:36-37`

---

## 3. Stage 4.8 — Fidelity gate (consilience, SOFT)

Downstream-utility check, distinct from quality(compression/stability) and oracle(invariants). Measures **Whewell consilience**: a true abstraction should cohere even on relations *not used to form it*.
`# src: engine/eureka/fidelity_gate.py:1-16; KG finding_eu_A2_whewell_mapping ("consilience=다른 클래스 사실까지 묶이면 그 개념이 참이라는 증거")`

**SOFT verdict — never blocks.** FAIL = `SOFT_WARN` → escalate to the judgment lens (stage 5); it is *not* a hard reject. In the pipeline, stage 4.8 always records `ok=True` and only counts `soft_warns`.
`# src: engine/eureka/fidelity_gate.py:6,48-49; engine/eureka/pipeline.py:257-279 stage_4_8_fidelity_gate()`

Mechanism (`assess_fidelity`):
- **witness relations** = held-out rels not used in the formal context: `IN_CATEGORY, RELATED_TO, SAME_TRADITION, ABOUT, CLASSIFIED_AS, CONTAINS`.
- per-witness `top_share = (max members sharing one target) / extent`.
- a witness **passes** if `top_share ≥ min_top_share` (default 0.30).
- ensemble **PASS** if `witnesses_passing ≥ min_witnesses_passing` (default 2 = ≥2 independent signals cohere).
`# src: engine/eureka/fidelity_gate.py:26-41 (DEFAULT_WITNESS_RELS, FidelityConfig), :94-119 assess_fidelity()`

Anti-Goodhart rationale: every proxy is Goodhart (SF3) ⇒ no single metric, ensemble k witnesses. Thin/tautological abstractions (defined only by their forming facets) scatter across witnesses and surface as `SOFT_WARN`.
`# src: engine/eureka/fidelity_gate.py:10-12; KG consensus-eureka-design-synthesis-2026-05-27 .hard_truth_3 ("모든 proxy Goodhart(SF3) … ensemble k≥3")`

> Drift note: the design-synthesis spec mandates **ensemble k ≥ 3**; the shipped default is `min_witnesses_passing = 2`. SOFT gate, so it warns rather than blocks, but the floor is below spec. `# src: fidelity_gate.py:40 vs KG consensus-eureka-design-synthesis-2026-05-27 .fidelity_scope ("single-proxy 금지 ensemble k≥3")`

Empty extent ⇒ `passed=False, "empty extent"`.
`# src: engine/eureka/fidelity_gate.py:140-141 run_fidelity_for_members()`

---

## 4. Stage 5 — Naesengmoon judgment lens (status transition)

After the executable gates, surviving ACs flip `PROPOSED → VerdictPending` — the LLM/human judgment lens (soundness / overfit / wrong-abstraction Metz) takes over. Eureka itself emits nothing past `VERDICT_PENDING`.
`# src: engine/eureka/pipeline.py:282-287 stage_5_naesengmoon_gate(); engine/eureka/induction_models.py:34-40 AbstractClassStatus; THEORY/유레카/EUREKA_ENGINE_DESIGN.md §5 JUSTIFY`

Status enum (the only legal AC states): `PROPOSED / VerdictPending / CANONICAL / CANONICAL_DELEGATED / REJECTED`.
`# src: engine/eureka/induction_models.py:34-40`

---

## 5. Stage 5.5 — Pre-merge validator (schema, HARD)

Last gate before any MERGE. Application-side because the APOC trigger `t_abstractclass_required_fields` is BLOCKED on Neo4j Community Edition without admin role.
`# src: engine/eureka/validator.py:1-6`

`gate_before_merge(acs, edges)` validates every payload through Pydantic v2 (`AbstractClass` / `GeneralizesEdge`) and raises `SchemaViolation` on the **first** failure (fail-fast); caller decides skip-vs-abort.
`# src: engine/eureka/validator.py:34-45; engine/eureka/pipeline.py:349-356`

Schema invariants enforced here:
- `name` must be kebab-case slug or `ac_<elementId>_<size>_<rev>`.
- `inductionMethod` must be **registry-registered** (OCP plugin check) — unknown method rejected.
- automated inducers (`is_automated`) **require non-null** `extent, intent, stabilityScore`.
- `GeneralizesEdge`: `confidence` required when `induced=true`; bounded `[0,1]`.
`# src: engine/eureka/induction_models.py:60-103 (AbstractClass validators), :120-133 (GeneralizesEdge validators)`

---

## 6. Gate-stack summary table

| stage | gate | kind | on FAIL | threshold source |
|-------|------|------|---------|------------------|
| 4.5 | quality | HARD, statistical | return run | quality_gate.py (Rousseeuw/Newman/Roth/Vinh/Zaveri) |
| 4.7a | oracle KG | HARD, executable | short-circuit, block stage 5 | oracle_lens.py kg_oracle_gate |
| 4.7b | oracle shell | HARD, opt-in | short-circuit | oracle_lens.py default_eureka_lenses |
| 4.8 | fidelity | **SOFT**, consilience | SOFT_WARN → escalate | fidelity_gate.py FidelityConfig |
| 5 | judgment | status transition | VerdictPending (human/LLM) | pipeline.py stage_5 |
| 5.5 | pre-merge validator | HARD, schema | SchemaViolation (fail-fast) | validator.py + induction_models.py |

`# src: engine/eureka/pipeline.py run() + the five gate modules above`

---

## 7. References

- `../SKILL.md`
- Engine: `bhgman_tool/engine/eureka/{pipeline,quality_gate,oracle_lens,fidelity_gate,validator,induction_models,formal_context_builder}.py`, shared primitive `bhgman_tool/engine/naesengmoon/oracle_lens.py`
- THEORY: `THEORY/유레카/EUREKA_ENGINE_DESIGN.md`, `THEORY/유레카/PROM_16_EUREKA_IMPL_REPORT.md`
- KG: `eureka-canonical-2026-05-26`, `consensus-eureka-design-synthesis-2026-05-27`, `seed-prom16lag-cons-quality-gate-silhouette-modularity-2026-05-20`, `wqi-extract-shared-naesengmoon-oracle-primitive-2026-05-27`, ResearchFinding `{cycle_id:"eureka-academic-grounding-2026-05-26"}` (16)
- Sibling: `../longinus/references/theory.md` (binding), `../../THEORY/나생문/` (oracle vs judgment lens-class)
