# Lean 4 Verified Theorems — Index

> 50 theorems total in this repo (Harness 24 + Longinus 26). All Mathlib-free standalone, 0 sorry, verified with Lean 4.29.1.

---

## Build reproduction

```bash
# Prerequisite: Lean 4 (4.29+) via elan
curl https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh -sSf | sh

# Build all 5 files
cd bhgman_tool/lean
for f in *.lean; do
  echo "=== $f ==="
  lean "$f"
done
# Each file: exit 0, no error, no warning, 0 sorry
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

## Longinus side — 26 theorems

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

### `Longinus_HierarchicalMirror.lean` (~19 theorems)

External canon: **Longinus 7-Layer Reference Model** + **Sanfeliu-Fu 1983** (GED) + Hofstadter strange loop + family-expansion-pattern (SYMPOSIUM canon)

(Summary — full theorem list inline in the .lean file)

| Group | Theorems | Topics |
|---|---|---|
| L1-L7 layer correctness | ~7 | Each layer (AddressIndirection / Lifetime / TypePermission / SemioticBinding / DistributedIdentity / InformationCompression / AestheticIntentional) is well-formed and distinct |
| Reference Site composition | ~4 | Composing references across layers preserves invariants |
| Drift surjective mapping | ~4 | 5 drift types (Missing/Orphan/SigMismatch/PatternDiv/LabelRot) surjectively map onto 3 BX laws |
| Hierarchical mirror | ~4 | Longinus 7-layer mirrors apostle/tool/instance vertical hierarchy |

---

## Total verified count

| Source | Theorems | sorry |
|---|---|---|
| Harness_LawvereFixedPoint | 5 | 0 |
| HarnessSelfReference | 9 | 0 |
| Harness_ACI_Mirror | 10 | 0 |
| Longinus_ConfidenceSchema_GraphifyAbsorbed | 7 | 0 |
| Longinus_HierarchicalMirror | 19 | 0 |
| **TOTAL (this repo)** | **50** | **0** |

The broader SYMPOSIUM ecosystem holds **141+ Lean theorems** across APT/TPA cycles, sociological axiom formalization, and family-pattern verification. This repo contains *only the Harness + Longinus subset* relevant to the Airplane Man's tool layer.

---

## Why Mathlib-free?

Choice rationale:
1. **Reproducibility** — anyone with `lean` + `elan` can build, no Mathlib download (~1GB)
2. **Independence** — no dependency on Mathlib's evolving API
3. **Self-contained proofs** — every step inline, no hidden lemma library
4. **Goodhart resistance** — *we don't optimize for theorem count*. Each theorem is a *checkpoint*, not a competitive metric.

Trade-off accepted:
- Some proofs are longer than they'd be with Mathlib
- Limited reuse of generic algebraic infrastructure
- Cannot directly invoke `Mathlib.CategoryTheory.*`

For SYMPOSIUM's `lean-mathlib-functor-actual-build` future sprint, parallel Mathlib-tracked versions are planned (`MIND/lean_formalization/temporal_arc_with_mathlib/`).

---

## Per-theorem citation table

| Theorem | Primary citation |
|---|---|
| Lawvere FPT theorems (1-5) | Lawvere 1969 |
| Self-reference unification (6-14) | Yanofsky 2003 + Russell 1901 / Cantor 1891 / Tarski 1936 / Gödel 1931 / Lawvere 1969 |
| ACI Mirror (15-24) | Smith 1984 + Kiczales et al. 1991 + Hofstadter 1979 + Cherns 1976 |
| Confidence schema (25-31) | Foster-Pierce-Walker 2007 + Frege 1892 + graphify 2026 |
| Longinus 7-Layer mirror (32-50) | (composite — see `Longinus_HierarchicalMirror.lean` header) |

See [citations.md](citations.md) for full bibliographic detail.

---

## Cross-references

- [citations.md](citations.md) — 17 external canonical axes
- [related-work.md](related-work.md) — Industry comparisons + absorption record
- [../02-concepts/airplane-man.md](../02-concepts/airplane-man.md) §Lean formalization
- [../02-concepts/harness.md](../02-concepts/harness.md) §Formal verification
- [../05-papers/](../05-papers/) — Each cited canon in summary form
