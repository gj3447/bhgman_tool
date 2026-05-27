# eureka (유레카) — 창조(귀납→추상)

> 정명 2026-05-27 (`eureka-l8-rectification-2026-05-27`): formerly `longinus_l8_induction`
> ("Longinus Layer-8 induction" = 2026-05-26 commander-split 이전 작명). induction은 유레카의
> 본령이라 정명, drift부(`ged_drift_detector`/`nightly_drift_check`)는 `engine/longinus_drift`로 분리.

유레카 induction — pattern detection over L1-L7 ReferenceSite KG → `:AbstractClass` + `:GENERALIZES` super-node crystallization. 비행기맨 #4 LegionCommander, 창조(구체→추상 축).

## Spec sources

- **Contract**: `SYMPOSIUM/THEORY/LONGINUS/CONTRACT_AbstractClass_v1_2026-05-20.md`
- **ActionPlan**: KG `plan-prom16lag-l8-induction-2026-05-20`
- **PROM 16 cycle**: `prom16-longinus-abstract-grouping-2026-05-20` (16 findings)
- **PROM 8 schema**: `prom8-l8-abstractclass-schema-2026-05-20` (8 findings)
- **PROM 8 GED τ**: `prom8-ged-drift-tau-2026-05-20` (8 findings)
- **DecisionLog**: `decision-log-blanket-proceed-l8-install-2026-05-20`

## 7-stage pipeline (GraphRAG-mirrored)

1. **Extract** — L1-L7 ReferenceSite → `:Candidate` (not `:Canonical`)
2. **Community** — `gds.leiden` multi-γ ∈ {0.5, 1.0, 2.0}
3. **Summarize** — per-community Haiku summary via 재배맨 SOP
4. **Induce** — `:AbstractClass` + `(AbstractClass)-[:GENERALIZES]->(member)` (option A 방향)
5. **Naesengmoon Gate** — `/tlb <candidate> --lens constitutional` before MERGE
6. **Hybrid retrieval** — BM25 + vector + community-summary RRF
7. **Drift loop** — nightly Leiden + community hypergraph bipartite GED >τ → re-induction

## Modules

- `models.py` — `AbstractClass`, `GeneralizesEdge` Pydantic v2 schemas
- `validator.py` — application-side required-fields enforcement (APOC trigger BLOCKED on Community Edition without admin role; fallback per `seed-hookinstall-t_abstractclass_required_fields-2026-05-20`)
- `quality_gate.py` — silhouette ≥ 0.50 (Rousseeuw 1987) AND modularity Q ≥ 0.30 (Newman 2006) + FCA stability σ ≥ 0.50 (Roth-Obiedkov-Kourie 2008) when applicable + Goodhart cap P ≤ 0.90 (Zaveri 2016)
- `ged_drift_detector.py` — community hypergraph bipartite GED (Riesen-Bunke 2009 LSAPE) + 2-phase τ (cold-start absolute 0.25 / steady-state q90) + triple-AND gate (nGED + NMI + silhouette)
- `induction_operators/`:
  - `fca.py` — Galois lattice extent/intent (Ganter-Wille 1999), iceberg pruning
  - `amie3.py` — Horn rule mining stub (Lajus-Galárraga-Suchanek 2020)
  - `leiden_llm.py` — GraphRAG hierarchical Leiden + LLM summarization stub (Edge 2024)
- `pipeline.py` — 7-stage orchestrator

## Status

- **2026-05-20 init**: scaffold + tests for validator/quality_gate/ged_drift
- **bake-off**: FCA functional, AMIE3 + Leiden-LLM stubs pending implementation
- **APOC trigger**: blocked on admin access (`seed-hookinstall-t_abstractclass_required_fields-2026-05-20`)
- **30-day GED baseline**: prototype 가동 후 부산물로 자동 수집

## KG anchors

- `contract-abstractclass-schema-propose-2026-05-20` (CANONICAL_DELEGATED)
- `config-ged-drift-tau-propose-2026-05-20` (CANONICAL_DELEGATED)
- `hub-longinus-reference`
