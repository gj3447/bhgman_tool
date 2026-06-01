/-
  Measurement_MetricScale.lean — Phase 1 of 4-phase Lean 4 formalization

  PROM 16 7CMD MEASUREMENT GROUNDING A3S3 P3 / A4S3.
  Mathlib-free skeleton — pluggable into Mathlib for full proofs later.

  KG: 7cmd-measurement-driven-conditional-dispatch-2026-05-30,
      mitigation-lean4-metricscale-phase1-2026-05-30
  Parent: hades-canonical-2026-05-27

  Goal of Phase 1:
    1. Define Stevens 1946 four scale types as inductive datatype.
    2. Define valid operations as a set (membership relation).
    3. Prove monotonicity: nominal ⊂ ordinal ⊂ interval ⊂ ratio (with respect to valid_ops).
    4. Provide phantom-typed metric so the type checker prevents invalid op application.
-/

namespace Measurement.MetricScale

/-- Stevens (1946) measurement scale taxonomy. -/
inductive Scale where
  | nominal  : Scale
  | ordinal  : Scale
  | interval : Scale
  | ratio    : Scale
  deriving DecidableEq, Repr

/-- Statistical / arithmetic operation tags. -/
inductive Op where
  | count : Op
  | mode : Op
  | entropy : Op
  | median : Op
  | percentile : Op
  | minOp : Op
  | maxOp : Op
  | mean : Op
  | sd : Op
  | ratio : Op    -- division
  | pct : Op
  | geomean : Op
  deriving DecidableEq, Repr

/-- Valid operations per Stevens scale (Stevens 1946 + Hand 2004). -/
def validOp : Scale → Op → Prop
  | Scale.nominal,  Op.count     => True
  | Scale.nominal,  Op.mode      => True
  | Scale.nominal,  Op.entropy   => True
  | Scale.ordinal,  Op.count     => True
  | Scale.ordinal,  Op.mode      => True
  | Scale.ordinal,  Op.entropy   => True
  | Scale.ordinal,  Op.median    => True
  | Scale.ordinal,  Op.percentile => True
  | Scale.ordinal,  Op.minOp     => True
  | Scale.ordinal,  Op.maxOp     => True
  | Scale.interval, Op.count     => True
  | Scale.interval, Op.mode      => True
  | Scale.interval, Op.entropy   => True
  | Scale.interval, Op.median    => True
  | Scale.interval, Op.percentile => True
  | Scale.interval, Op.minOp     => True
  | Scale.interval, Op.maxOp     => True
  | Scale.interval, Op.mean      => True
  | Scale.interval, Op.sd        => True
  | Scale.ratio,    Op.count     => True
  | Scale.ratio,    Op.mode      => True
  | Scale.ratio,    Op.entropy   => True
  | Scale.ratio,    Op.median    => True
  | Scale.ratio,    Op.percentile => True
  | Scale.ratio,    Op.minOp     => True
  | Scale.ratio,    Op.maxOp     => True
  | Scale.ratio,    Op.mean      => True
  | Scale.ratio,    Op.sd        => True
  | Scale.ratio,    Op.ratio     => True
  | Scale.ratio,    Op.pct       => True
  | Scale.ratio,    Op.geomean   => True
  | _, _ => False

/-- Decidability of validOp. -/
instance : Decidable (validOp s op) := by
  cases s <;> cases op <;> simp [validOp] <;> infer_instance

/-- Monotonicity: nominal-valid → ordinal-valid. -/
theorem nominal_subset_ordinal (op : Op) (h : validOp Scale.nominal op) :
    validOp Scale.ordinal op := by
  cases op <;> first | exact h | (simp [validOp] at h)

/-- Monotonicity: ordinal-valid → interval-valid. -/
theorem ordinal_subset_interval (op : Op) (h : validOp Scale.ordinal op) :
    validOp Scale.interval op := by
  cases op <;> first | exact h | (simp [validOp] at h)

/-- Monotonicity: interval-valid → ratio-valid. -/
theorem interval_subset_ratio (op : Op) (h : validOp Scale.interval op) :
    validOp Scale.ratio op := by
  cases op <;> first | exact h | (simp [validOp] at h)

/-- Composed monotonicity: nominal ⊂ ratio. -/
theorem nominal_subset_ratio (op : Op) (h : validOp Scale.nominal op) :
    validOp Scale.ratio op :=
  interval_subset_ratio op (ordinal_subset_interval op (nominal_subset_ordinal op h))

/-- A Metric is a value paired with its Stevens scale type at the type level. -/
structure Metric (s : Scale) where
  value : Float

namespace Metric

/-- Cast metric up the scale hierarchy (nominal → ordinal → interval → ratio).
    Allowed by Stevens lemma — a stronger scale admits all weaker operations. -/
def upcast {s₁ s₂ : Scale} (h : ∀ op, validOp s₁ op → validOp s₂ op)
    (m : Metric s₁) : Metric s₂ :=
  ⟨m.value⟩

/-- A typed operation can be applied to a Metric iff validOp s op. -/
class Applicable (s : Scale) (op : Op) : Prop where
  proof : validOp s op

end Metric

/-- Stevens 1946 incidence: count is always valid for any scale. -/
theorem count_always_valid (s : Scale) : validOp s Op.count := by
  cases s <;> simp [validOp]

/-- Stevens 1946 incidence: mean is invalid for nominal / ordinal. -/
theorem mean_invalid_nominal : ¬ validOp Scale.nominal Op.mean := by
  simp [validOp]

theorem mean_invalid_ordinal : ¬ validOp Scale.ordinal Op.mean := by
  simp [validOp]

/-- Stevens 1946 incidence: pct (ratio division) is invalid for non-ratio scales. -/
theorem pct_only_ratio (s : Scale) (h : validOp s Op.pct) : s = Scale.ratio := by
  cases s <;> first | rfl | (simp [validOp] at h)

end Measurement.MetricScale
