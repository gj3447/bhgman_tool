# Lean 4 Verified Theorems — Index

> **71 theorems** in the 13 standalone Mathlib-free files (Harness 24 / Longinus 21 / Measurement 26), **0 proof-position `sorry`**, Lean 4. A separate Mathlib-sister proof (`apt_functor_with_mathlib/`, 16 theorems, needs `lake` + Mathlib) brings the `lean/` tree total to **87**. The broader SYMPOSIUM ecosystem holds **141+** (see [Total verified count](#total-verified-count)).

Reproduce the headline counts on a fresh clone:

```bash
# top-level theorem/lemma declarations across the whole lean/ tree → 87
grep -rcE '^(theorem|lemma) ' lean/ | awk -F: '{s+=$2} END{print s}'
# the 13 standalone (Mathlib-free) files only → 71
grep -cE '^(theorem|lemma) ' lean/*.lean | awk -F: '{s+=$2} END{print s}'
# proof-position sorry → 0 (every `sorry` token in the tree is in a comment/docstring)
grep -rEn '(:=|by) +sorry' lean/*.lean | wc -l
```

---

## Build reproduction

```bash
# Prerequisite: Lean 4 (4.29+) via elan
curl https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh -sSf | sh

# Build all 13 standalone files (Mathlib-free, fast, no lake)
cd bhgman_tool/lean
for f in *.lean; do
  echo "=== $f ==="
  lean "$f"
done
# Each file: exit 0, no error, 0 proof-position sorry

# The Mathlib-sister (16 theorems) builds separately and needs Mathlib:
cd apt_functor_with_mathlib && lake build   # 628/628 jobs, 0 sorry
```

---

## Harness side — 24 theorems

### `Harness_LawvereFixedPoint.lean` (5 theorems)

External canon: **Lawvere 1969** (Diagonal Arguments and Cartesian Closed Categories)

| # | Theorem | Statement (informal) |
|---|---|---|
| 1 | `lawvere_diagonal_existence` | Self-application `t(j)(j)` is well-formed in cartesian closed categories |
| 2 | `fixed_point_existence` | Surjective `α : A → A^B` + endo `t : A → A` ⇒ ∃ fixed point |
| 3 | `airplane_man_has_fixed_point` | The `∀x:CHU, j.covers x` predicate admits a fixed point in CHU |
| 4 | `fixed_point_is_open` | The fixed point is *not closed under further computation* (limit acknowledged) |
| 5 | `self_cover_consistent` | `j.covers j` is consistent (not paradoxical) but undecidable in general |

### `HarnessSelfReference.lean` (9 theorems)

External canon: **Yanofsky 2003** + Tarski 1936 + Gödel 1931 + Russell 1901 + Cantor 1891

| # | Theorem | Statement (informal) |
|---|---|---|
| 1 | `russell_instance` | Self-reference + negation ⇒ contradiction (formalized as untyped pair) |
| 2 | `cantor_instance` | No surjective `CHU → P(CHU)` (consequence: ∀-cover is not set-theoretic) |
| 3 | `godel_instance` | Framework's own consistency is *not* provable within itself |
| 4 | `tarski_instance` | Apostle cannot define its own success criterion internally |
| 5 | `lawvere_instance` | Self-application admits fixed points (so `j.covers j` is always meaningful) |
| 6 | `yanofsky_unification` | All 5 instances share the structural lemma |
| 7 | `bhgman_self_limit_accepted` | bhgman *explicitly* accepts the obstruction (not a bug) |
| 8 | `external_verifier_required` | Self-verification requires Naesengmoon-style external lens |
| 9 | `framework_incompleteness` | Renouncing completeness is *necessary* under Yanofsky |

### `Harness_ACI_Mirror.lean` (10 theorems)

External canon: **Smith 1984** (Reflection and Semantics in a Procedural Language) + Kiczales et al. 1991 (MOP) + Hofstadter 1979 (strange loop)

| # | Theorem | Statement (informal) |
|---|---|---|
| 1 | `aci_aspect_definition` | Aspect = abstract role independent of class/instance |
| 2 | `aci_class_definition` | Class = type-level grouping of instances |
| 3 | `aci_instance_definition` | Instance = runtime particular |
| 4 | `aci_three_layer_distinct` | Aspect / Class / Instance occupy distinct ontological layers |
| 5 | `aci_no_layer_collapse` | Confusing layers yields category error (Heidegger Seinsvergessenheit) |
| 6 | `mirror_aspect_to_apostle` | Harness Aspect mirrors apostle's ∀-cover predicate type |
| 7 | `mirror_class_to_tier` | Harness Class mirrors family tier (L_MC / L_RT / L_IDE) |
| 8 | `mirror_instance_to_runtime` | Harness Instance mirrors industry runtime (Cursor / ruflo / ADK / ...) |
| 9 | `aci_responsibility_split` | 3-layer mirrors Cherns Principle 5 (Boundary Location) |
| 10 | `aci_strong_mirror_condition` | STRONG mirror requires cardinality match + responsibility_split |

---

## Longinus side — 21 theorems

### `Longinus_ConfidenceSchema_GraphifyAbsorbed.lean` (7 theorems)

External canon: **Foster-Pierce-Walker 2007** (BX Lens Laws) + **Frege 1892** (Sense vs Reference) + **graphify** (industry instance 2026, EXTRACTED/INFERRED/AMBIGUOUS schema)

| # | Theorem | Statement (informal) |
|---|---|---|
| 1 | `ambiguous_unique_human_gate` | AMBIGUOUS is the *unique* confidence tier requiring human verdict |
| 2 | `sinn_bedeutung_non_collapse` | `sourceId` (Sinn) ↔ `sourcePath` (Bedeutung) cannot collapse |
| 3 | `trust_strict_order` | EXTRACTED (2) > INFERRED (1) > AMBIGUOUS (0) strict order |
| 4 | `bx_getput` | Foster-Pierce-Walker GetPut law for ReferenceSite |
| 5 | `bx_putget` | Foster-Pierce-Walker PutGet law for ReferenceSite |
| 6 | `ambiguous_in_list_forces_preliminary` | Any AMBIGUOUS in aggregate ⇒ PRELIMINARY label forced |
| 7 | `goodhart_safeguard_confidence_not_scalar` | Confidence enum cannot collapse to scalar (Goodhart resistance) |

### `Longinus_HierarchicalMirror.lean` (10 theorems)

External canon: **Longinus 7-Layer Reference Model** + **Sanfeliu-Fu 1983** (GED) + Hofstadter strange loop + family-expansion-pattern (SYMPOSIUM canon)

| # | Theorem | Statement (informal) |
|---|---|---|
| 1 | `layer_l1_least` | L1 (AddressIndirection) is the least element of the 7-layer order |
| 2 | `layer_l7_greatest` | L7 (AestheticIntentional) is the greatest element |
| 3 | `project_total` | The layer projection is total over all reference sites |
| 4 | `hierarchical_mirror_validity` | Longinus 7-layer mirrors the apostle/tool/instance vertical hierarchy |
| 5 | `projection_partition` | Layer projection partitions reference sites (no overlap) |
| 6 | `mirror_strength_iter7_promotion` | iter-7 promotion strengthens the mirror condition |
| 7 | `drift_5_covers_3laws` | 5 drift types (Missing/Orphan/SigMismatch/PatternDiv/LabelRot) cover the 3 BX laws |
| 8 | `ged_severity_total` | GED severity ordering is total |
| 9 | `sevenlayer_composition_chain` | Composing references across the 7 layers preserves invariants |
| 10 | `mirror_strength_iter8_stays_strong` | iter-8 keeps the mirror STRONG (no regression) |

### `Longinus_RefinementSoundness.lean` (4 theorems)

External canon: **Pierce TAPL 2002 §8/§15** (type soundness = Progress + Preservation) + refinement types §22

| # | Theorem | Statement (informal) |
|---|---|---|
| 1 | `progress` | A non-terminal ReferenceSite state always takes a step (no stuck states) |
| 2 | `preservation_trust_noninc` | Trust is monotone *non-increasing* under drift-resolution steps |
| 3 | `soundness` | Progress ∧ Preservation (Pierce soundness for the drift state machine) |
| 4 | `no_silent_promotion` | Corollary: no step raises trust (Goodhart safeguard at the dynamics level) |

---

## Measurement side — 26 theorems

Stevens 1946 measurement-theory formalization of the legion's commander metrics, composition safety, and threshold-derivation invariants. (`Measurement_Phase5_DerivationSoundness.lean` carries decision *examples* via `decide`/`native_decide` rather than `theorem`/`lemma`, so it contributes 0 to the count.)

### `Measurement_MetricScale.lean` (8 theorems)

External canon: **Stevens 1946** (On the Theory of Scales of Measurement)

| # | Theorem | Statement (informal) |
|---|---|---|
| 1 | `nominal_subset_ordinal` | Valid-op set is monotone: nominal ⊂ ordinal |
| 2 | `ordinal_subset_interval` | ordinal ⊂ interval |
| 3 | `interval_subset_ratio` | interval ⊂ ratio |
| 4 | `nominal_subset_ratio` | Composed transitivity nominal ⊂ ratio |
| 5 | `count_always_valid` | Counting is valid on every scale |
| 6 | `mean_invalid_nominal` | Mean is invalid on a nominal scale |
| 7 | `mean_invalid_ordinal` | Mean is invalid on an ordinal scale |
| 8 | `pct_only_ratio` | Percentage/division is valid only on a ratio scale |

### `Measurement_CommanderMetrics.lean` (6 theorems)

| # | Theorem | Statement (informal) |
|---|---|---|
| 1 | `naesengmoon_lens_count_is_ordinal` | Lens count is an ordinal-scale metric |
| 2 | `occam_archival_category_is_nominal` | Archival category is nominal |
| 3 | `eureka_colimit_depth_is_ordinal` | Colimit depth is ordinal |
| 4 | `lens_count_mean_blocked` | Taking a mean of lens counts is blocked (scale violation) |
| 5 | `archival_category_mean_blocked` | Mean of archival categories is blocked |
| 6 | `supersession_confidence_pct_allowed` | Supersession-confidence percentage is allowed (ratio scale) |

### `Measurement_CompositionSafety.lean` (4 theorems)

| # | Theorem | Statement (informal) |
|---|---|---|
| 1 | `empty_chain_valid` | An empty commander chain is valid |
| 2 | `invalid_step_kills_chain` | One invalid step invalidates the whole chain |
| 3 | `chain_exceeds_max_depth_invalid` | A chain over `MAX_DISPATCH_DEPTH` is invalid |
| 4 | `lens_count_mean_chain_blocked` | Scale violation propagates through composition |

### `Measurement_Contract_MonoidIdentity.lean` (3 theorems)

External canon: contract-dual coupling-threshold (SYMPOSIUM canon `consensus-prom16-contract-dual-coupling-threshold-2026-05-27`)

| # | Theorem | Statement (informal) |
|---|---|---|
| 1 | `contract_identity_at_coupling_zero` | At coupling=0 the contract degenerates to the monoid identity ε |
| 2 | `threshold_forced_by_monoid_uniqueness` | The coupling=0 threshold is *forced* by monoid uniqueness, not tuned |
| 3 | `epsilon_is_identity_zero_coupling` | ε is the identity element at zero coupling (sanity) |

### `Measurement_Prometheus_ShannonRatify.lean` (3 theorems)

External canon: **Shannon 1948** (information content)

| # | Theorem | Statement (informal) |
|---|---|---|
| 1 | `prom_16_is_4_bit` | PROM 16 = 4 bits of dispatch information |
| 2 | `matrix_product_equals_standard` | The axis×sub-axis matrix product equals the standard count |
| 3 | `threshold_is_minimum_4bit` | The dispatch threshold is the minimum 4-bit cut |

### `Measurement_Phase4_EmpiricalValidation.lean` (2 theorems)

| # | Theorem | Statement (informal) |
|---|---|---|
| 1 | `empty_batch_valid` | An empty validation batch is vacuously valid |
| 2 | `batch_invalid_if_head_invalid` | A batch is invalid if its head record is invalid |

---

## Total verified count

| Source | Theorems | sorry |
|---|---|---|
| Harness_LawvereFixedPoint | 5 | 0 |
| HarnessSelfReference | 9 | 0 |
| Harness_ACI_Mirror | 10 | 0 |
| Longinus_ConfidenceSchema_GraphifyAbsorbed | 7 | 0 |
| Longinus_HierarchicalMirror | 10 | 0 |
| Longinus_RefinementSoundness | 4 | 0 |
| Measurement_MetricScale | 8 | 0 |
| Measurement_CommanderMetrics | 6 | 0 |
| Measurement_CompositionSafety | 4 | 0 |
| Measurement_Contract_MonoidIdentity | 3 | 0 |
| Measurement_Prometheus_ShannonRatify | 3 | 0 |
| Measurement_Phase4_EmpiricalValidation | 2 | 0 |
| **Standalone subtotal (13 files, Mathlib-free)** | **71** | **0** |
| apt_functor_with_mathlib/APTFunctorFactorization (Mathlib-sister, needs `lake`) | 16 | 0 |
| **`lean/` tree total** | **87** | **0** |

The broader SYMPOSIUM ecosystem holds **141+ Lean theorems** across APT/TPA cycles, sociological axiom formalization, and family-pattern verification. This repo contains *only the Harness + Longinus + Measurement subset* relevant to the Airplane Man's tool layer — the 141+ figure is the **ecosystem** count, not this repo's.

---

## Why Mathlib-free?

Choice rationale (applies to the 13 standalone files; the sister proof opts into Mathlib deliberately):

1. **Reproducibility** — anyone with `lean` + `elan` can build, no Mathlib download (~1GB)
2. **Independence** — no dependency on Mathlib's evolving API
3. **Self-contained proofs** — every step inline, no hidden lemma library
4. **Goodhart resistance** — *we don't optimize for theorem count*. Each theorem is a *checkpoint*, not a competitive metric.

Trade-off accepted:

- Some proofs are longer than they'd be with Mathlib
- Limited reuse of generic algebraic infrastructure
- Cannot directly invoke `Mathlib.CategoryTheory.*` (the sister proof exists precisely to discharge the Mathlib-tracked version)

---

## Per-file citation table

| File | Primary citation |
|---|---|
| Harness_LawvereFixedPoint | Lawvere 1969 |
| HarnessSelfReference | Yanofsky 2003 + Russell 1901 / Cantor 1891 / Tarski 1936 / Gödel 1931 / Lawvere 1969 |
| Harness_ACI_Mirror | Smith 1984 + Kiczales et al. 1991 + Hofstadter 1979 + Cherns 1976 |
| Longinus_ConfidenceSchema_GraphifyAbsorbed | Foster-Pierce-Walker 2007 + Frege 1892 + graphify 2026 |
| Longinus_HierarchicalMirror | Longinus 7-Layer model + Sanfeliu-Fu 1983 + family-expansion-pattern |
| Longinus_RefinementSoundness | Pierce TAPL 2002 §8/§15/§22 |
| Measurement_* | Stevens 1946 (+ Shannon 1948 for ShannonRatify; contract-dual canon for MonoidIdentity) |

See [citations.md](citations.md) for full bibliographic detail.

---

## Cross-references

- [citations.md](citations.md) — external canonical axes
- [related-work.md](related-work.md) — Industry comparisons + absorption record
- [../02-concepts/airplane-man.md](../02-concepts/airplane-man.md) §Lean formalization
- [../02-concepts/harness.md](../02-concepts/harness.md) §Formal verification
- [../05-papers/](../05-papers/) — Each cited canon in summary form
