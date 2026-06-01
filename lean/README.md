# bhgman_tool — Lean 4 formalizations

> Two layers of formal verification: **Mathlib-free standalone** (14 files, 89 theorem) + **Mathlib sister project** (16 theorem, 0 sorry, `lake build` PASS).

## Layout

```
lean/
├── README.md                              ← this file
│
├── HarnessSelfReference.lean              ← standalone (Mathlib-free)
├── Harness_ACI_Mirror.lean                ← standalone
├── Harness_LawvereFixedPoint.lean         ← standalone
├── Longinus_ConfidenceSchema_GraphifyAbsorbed.lean  ← standalone
├── Longinus_HierarchicalMirror.lean       ← standalone
├── Longinus_RefinementSoundness.lean      ← standalone (Pierce soundness)
├── Measurement_*.lean  (6 files)          ← standalone (Stevens 1946 measurement theory)
├── Occam_SupersessionScore.lean           ← standalone (σ supersession score, Pearl 1988)
├── SeedLifecycle.lean                     ← standalone (재배맨 seed lifecycle)
│
└── apt_functor_with_mathlib/              ← Mathlib sister project (Wave 7 P3-D absorbed 2026-05-14)
    ├── lakefile.toml                      ← Mathlib v4.30.0-rc2 dep
    ├── lean-toolchain                     ← leanprover/lean4:v4.30.0-rc2
    ├── APTFunctorFactorization.lean       ← 393 LOC, 16 theorem, 0 sorry, lake build PASS
    └── README.md                          ← project-specific build instructions
```

## Two layers

### Layer 1: Mathlib-free standalone (14 files, 89 theorem)

- **Build**: `lean <file.lean>` per file, no toolchain manager needed beyond `elan`.
- **CI**: built by `.github/workflows/ci.yml` `lean` job (matrix per file).
- **Purpose**: lightweight verification of core Harness + Longinus invariants without Mathlib dependency.
- **Theorems**: Lawvere fixed-point + self-reference (HarnessSelfReference, 9 theorem), ACI mirror (Harness_ACI_Mirror, 10 theorem), Lawvere FP (Harness_LawvereFixedPoint, 5 theorem), Longinus hierarchical mirror + refinement soundness (21), Measurement-theory invariants (Stevens 1946, 26), Occam supersession score σ (Pearl 1988, 10), Seed lifecycle (재배맨, 8). Full index: [../docs/04-references/lean-theorems.md](../docs/04-references/lean-theorems.md).
- **Origin**: SYMPOSIUM `MIND/lean_formalization/*.lean` Mathlib-free files (absorbed Wave 6).

### Layer 2: Mathlib sister (`apt_functor_with_mathlib/`)

- **Build**: `cd apt_functor_with_mathlib && lake update && lake exe cache get && lake build`
- **CI**: built by `.github/workflows/lean-build.yml` (weekly schedule + manual dispatch + push to `lean/**`).
- **Purpose**: APT FunctorFactorization formalization using `Mathlib.CategoryTheory.Category` + `Mathlib.CategoryTheory.Functor` + `Mathlib.Data.Finset.Card` — replaces 12 abstract `SmallCategory`/`SmallFunctor` proofs (standalone) with canonical Mathlib lemmas (`Functor.id_comp`, `Functor.comp_id`, `Functor.assoc`, `Finset.card_le_card`).
- **Stats** (2026-05-14): 12 theorem + 4 aux + 5 Preorder instance + 4 Mono lemma — **0 sorry**, `lake build` PASS (628/628 jobs), Azure cache hit (8294 olean, no local Mathlib recompile), `.lake` 6.9 GB.
- **Origin**: SYMPOSIUM `MIND/lean_formalization/apt_functor_with_mathlib/` — Wave 7 P3-D absorbed 2026-05-14 (sorry 19→0 PASS, Lakatos PROGRESSIVE_CONFIRMED).

## Build artifact policy

- `.lake/` directories are **gitignored** (root `.gitignore` includes `.lake/`).
- CI rebuilds Mathlib sister using Azure mathlib-cache (`lake exe cache get`) — local 6.9 GB build artifacts not checked in.
- Standalone .lean files compile in seconds; Mathlib sister compiles in ~3 min with cache hit, ~30 min cold.

## Verification reproduction

### Standalone (any of 14 files)

```bash
cd bhgman_tool/lean
lean HarnessSelfReference.lean       # expects exit 0
lean Harness_ACI_Mirror.lean         # expects exit 0
lean Harness_LawvereFixedPoint.lean  # expects exit 0
lean Longinus_HierarchicalMirror.lean
lean Longinus_ConfidenceSchema_GraphifyAbsorbed.lean
```

### Mathlib sister

```bash
cd bhgman_tool/lean/apt_functor_with_mathlib
lake update          # fetch Mathlib v4.30.0-rc2 + 9 transitive deps (~1 min)
lake exe cache get   # Azure cache 8294 olean (~30s, critical fast path)
lake build           # ~10s (project-only, Mathlib cached)
```

## KG references

- `span-bhgman-mathlib-sister-absorption-wave7-2026-05-14` — P3-D absorption (this README)
- `apt-functor-mathlib-sister-skeleton-2026-05-14` — sister `:LeanProject` BUILD PASS status
- `APT_essence_canonical_2026-05-14` — primary essence
- `span-essence-S-functor-2026-05-14` — sprint seed (sorry 19→0 PASS)
- `lean-mathlib-functor-actual-build-2026-04-30` — `:FutureSprint` **RESOLVED** by this absorption
- `apt-hardening-master-plan-2026-05-06` — 10/10 PROGRESSIVE_CONFIRMED PLATEAU
- `lesson-prom16-harness-grounding-reinforcement-2026-05-10` — Harness 3 PASS source (24 theorem, 0 sorry)

## Lakatos verdict (Mathlib sister)

**PROGRESSIVE_CONFIRMED** — Mathlib-backed sister fully verified.
- Excess content over standalone: 12 abstract structure-invariant proof fields → 6 reductions to canonical Mathlib theorems (`Functor.id_comp` / `Functor.comp_id` / `Functor.assoc` / `Finset.card_le_card`) + Preorder auto-Category.
- 0 sorry, `lake build` PASS (628/628), Azure cache hit (Mathlib compile = zero cost).
- Eq-discrete Preorder pattern + temporal_arc_with_mathlib v1.1 pattern reused.
- PRELIMINARY → CONFIRMED escalation: per `feedback_auto_crystallization_default.md`, auto-progression allowed; user verdict trigger optional.
