# 7-commander efficacy sweep — honest scoreboard

Run 2026-06-02 against the **real KG** (`bolt://100.64.0.3:7687`, 1738 `SourceCodeNode`,
460 with `disk_present`+`invocation_count` backfilled, 322 under `bhgman_tool/`). Every
cell passed — or honestly failed — the same 3-falsifier preflight
(`engine/efficacy/falsifier.py`: circularity / signal-absent / signal-inverted). Numbers
are reproduced by the commands shown; no value is hand-authored.

## Scoreboard

| commander | verb | verdict | number | oracle (independent of the commander?) |
|---|---|---|---|---|
| **occam** | 정리 | **MEASURED** | AUC **0.602** (pos 77 / neg 242) | `disk_present` — filesystem, not occam's label. ✅ non-circular |
| **longinus** | 연결 | **MEASURED** | ON **0.932** vs naive OFF 0.705, **Δ+0.227, perm p<1e-4**; false-kill 1.000→0.333 | injected disk mutations (20 seeds) + 101 independent drift events. ✅ |
| **naesengmoon** | 검증 | **MEASURED** | mutation catch-rate **0.600** (6/10; escapes 4 boundary/sign mutants) | injected code mutants on `engine/occam/scoring.py`. ✅ |
| **jaebaeman** | 출격 | **MEASURED** | dispatch fidelity **1.000** (2588/2596, 8 pending, 0 error) | run-record telemetry (correctness, not AUC). operational. |
| **hades** | 실현 | **MEASURED** | realization **0.839** (141/168 source modules test-reached) | static import-reachability + pytest GREEN. ✅ non-circular. operational/state. |
| **prometheus** | 획득 | **MEASURED** | groundedness: sourcing **0.077** (946/12356), verifiability **0.931** (881/946 external), self-cite **0.001** (1/946) | `urlparse` URL-structure classification — not prometheus's judgment. ✅ non-circular. verifiability/precision-floor, NOT novelty. |
| occam (registry) | 정리 | UNMEASURABLE | AUC 0.476 | KG `status` label is **73% occam-authored** → circular + inverted. |
| eureka | 발견·창조 | UNMEASURABLE | n/a | no reuse-timeseries corpus. |

Reproduce:

```bash
export NEO4J_URI=bolt://100.64.0.3:7687 NEO4J_USER=neo4j NEO4J_PASSWORD=…
uv run python -m engine.efficacy.run_all_commanders      # AUC-gate table (occam + registry sweep)
uv run python -m engine.efficacy.run_kg_efficacy          # occam disk-oracle, AUC 0.602
uv run python -m engine.efficacy.longinus_ab_experiment   # longinus ON/OFF Δ+0.227
uv run python -m engine.efficacy.drift_oracle             # 101 independent drift events
uv run python -m engine.efficacy.mutation_oracle          # naesengmoon catch 0.600
uv run python -m engine.efficacy.dispatch_telemetry       # jaebaeman fidelity 1.000
uv run python -m engine.efficacy.scale_curve              # operational scale to 100k
uv run python -m engine.efficacy.hades_oracle             # hades realization 0.839 + unrealized list
uv run python -m engine.efficacy.prometheus_oracle        # prometheus groundedness (sourcing/verifiability/self-cite)
```

## What moved (vs the prior open items)

The ultracode-vs-legion run (`THEORY/efficacy_ab_ultracode_vs_legion/RESULTS.md`) left two
holes. Both are partly closed:

1. **"synthetic & tiny fixtures — external validity unproven."**
   occam is now measured on the **real KG (319 nodes, not a 6–15-node toy)**: AUC 0.602,
   circularity 0.000, availability 1.000. And `scale_curve` shows the longinus classifier
   holding **0.920 from N=100 to N=100 000**, where the base-LLM context **overflows at
   100k ($5.58/solve)** while the engine stays at 0.04 s. External validity is no longer
   *zero*; it is *modest-but-real* for occam and *operational* for longinus at scale.

2. **"only ~1.3 of 7 commanders tested."**
   Now **6 of 7** carry a number from an oracle the commander did **not** author:
   occam (disk), longinus (injected mutation), naesengmoon (code mutants), jaebaeman
   (dispatch telemetry), hades (test-reachability + pytest GREEN), **prometheus
   (URL-structure groundedness)**.

3. **hades oracle built (2026-06-02).** `hades_oracle.py` — the 168 git-tracked source
   modules are the "specs to realize"; a module is *realized* when a test reaches it
   (static import graph) and the suite is GREEN. The oracle (import edges + pytest) is not
   authored by hades → circularity 0. Result: **realization 0.839 (141/168)**; the 27
   unrealized are CLI entry-points, bench scripts, mcp_server thin wrappers, and nightly
   jobs — code that genuinely lacks unit tests (an actionable list, not a failure).
   *Caveat:* this is realization **completeness** (operational/state), not a cognitive
   win — there is no hades-built-vs-naive-built counterfactual, because code generation is
   inherently LLM (no cheap deterministic baseline like longinus's sha-compare).

4. **prometheus oracle built (2026-06-02).** `prometheus_oracle.py` classifies every
   `ResearchFinding.citation_url` by URL *structure* (`urlparse`, not prometheus's
   judgment → circularity 0): external / self / text / empty. It sharpens the old
   "grounding 0.006" into two honest layers and **partly refutes the self-citation
   critique**: the real limit is **no-source (92.3%, 11410/12356)**, *not* self-citation
   (1/946 ≈ 0.1%); and of findings that *do* cite, **93.1% are real external URLs**
   (881 arxiv/doi/wiki/other). *Caveat:* this is groundedness/verifiability (a precision
   floor), **not novelty** — and liveness (HTTP 200) is not checked, so it is an *upper
   bound*. Real cognitive novelty (a fact a base-LLM can't recall) still needs a base-LLM
   recall-delta on the dgx-local model — that remains OPEN.

## What is still honestly open

- **1 commander (eureka) remains UNMEASURABLE** — no abstraction→reuse timeseries corpus.
  An eureka-extracted abstraction's *fan-in over time* (how many sites later reuse it) is
  the natural oracle, but the reuse edges/timestamps are not collected. That is the last
  real measurement debt.
- **prometheus novelty is still open even though groundedness is now measured** — the
  built oracle proves findings are *externally sourced*, not that they are *non-obvious*.
  base-LLM recall-delta (dgx-local) is the missing counterfactual.
- **The positive longinus Δ is vs a *naive no-tracking* baseline**, on *injected* mutations.
  It is **not** a cognitive win over a base-LLM given equal tool budget — that controlled
  test (`project_bhgman_ab_falsifier_2026_05_30`) still reads ~0; longinus's value there is
  operational (scale / reproducibility / audit). Both are true; do not collapse them.
- **occam AUC 0.602 is modest** — real signal, but a long way from a clean separator. The
  twin-redundancy signal is weak; age/invocation carry most of it.

# KG: efficacy-measurement-line-2026-06-01, efficacy-occam-sigma-ab-2026-06-01,
#     7cmd-measurement-driven-conditional-dispatch-2026-05-30, project_bhgman_ab_falsifier_2026_05_30
