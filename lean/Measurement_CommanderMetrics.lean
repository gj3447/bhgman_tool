/-
  Measurement_CommanderMetrics.lean — Phase 2 of 4-phase formalization

  Assign each 7-commander metric its Stevens scale type.
  Mirrors STEVENS_SCALE registry in bhgman_tool/engine/legion/measurement.py.
-/

import Measurement_MetricScale

namespace Measurement.CommanderMetrics

open Measurement.MetricScale

/-- 7 LegionCommanders. -/
inductive Commander where
  | prometheus | eureka | longinus | occam | naesengmoon | jaebaeman | hades
  deriving DecidableEq, Repr

/-- Each (commander, metricName) pair has a fixed Stevens scale type. -/
def scaleOf : Commander → String → Option Scale
  -- Prometheus
  | Commander.prometheus, "research_finding_count"  => some Scale.ratio
  | Commander.prometheus, "external_grounding_ratio" => some Scale.ratio
  -- Eureka — colimit_termination_depth ORDINAL (A3S3 bug fix)
  | Commander.eureka, "binding_density"             => some Scale.ratio
  | Commander.eureka, "novelty_score"               => some Scale.ratio
  | Commander.eureka, "colimit_termination_depth"   => some Scale.ordinal
  -- Longinus
  | Commander.longinus, "sha256_drift_count"        => some Scale.ratio
  | Commander.longinus, "reference_orphan_count"    => some Scale.ratio
  | Commander.longinus, "kg_node_unbound_count"     => some Scale.ratio
  -- Occam — archival_reason_category NOMINAL (A3S3 bug fix)
  | Commander.occam, "supersession_confidence"      => some Scale.ratio
  | Commander.occam, "dead_node_count"              => some Scale.ratio
  | Commander.occam, "twin_status_score"            => some Scale.ratio
  | Commander.occam, "archival_reason_category"     => some Scale.nominal
  -- Naesengmoon — lens_count ORDINAL (A1S3+A3S3 bug fix)
  | Commander.naesengmoon, "claim_confidence_mean"  => some Scale.ratio
  | Commander.naesengmoon, "lens_disagreement_ratio" => some Scale.ratio
  | Commander.naesengmoon, "RTI_FVR_pass_rate"      => some Scale.ratio
  | Commander.naesengmoon, "lens_count"             => some Scale.ordinal
  -- Jaebaeman
  | Commander.jaebaeman, "subagent_collect_drift"   => some Scale.ratio
  | Commander.jaebaeman, "seed_freshness_score"     => some Scale.ratio
  | Commander.jaebaeman, "dispatch_intent_completeness" => some Scale.interval
  -- Hades
  | Commander.hades, "spec_ambiguity_score"         => some Scale.interval
  | Commander.hades, "TDD_GREEN_failure_count"      => some Scale.ratio
  | Commander.hades, "binding_completeness"         => some Scale.ratio
  -- Unknown metric → none
  | _, _                                            => none

/-- 3 bug fixes registered in 2026-05-30 verified at type level. -/
theorem naesengmoon_lens_count_is_ordinal :
    scaleOf Commander.naesengmoon "lens_count" = some Scale.ordinal := rfl

theorem occam_archival_category_is_nominal :
    scaleOf Commander.occam "archival_reason_category" = some Scale.nominal := rfl

theorem eureka_colimit_depth_is_ordinal :
    scaleOf Commander.eureka "colimit_termination_depth" = some Scale.ordinal := rfl

/-- A dispatched operation is valid iff its metric has a scale AND op is valid for that scale. -/
def dispatchValid (c : Commander) (metric : String) (op : Op) : Prop :=
  match scaleOf c metric with
  | some s => validOp s op
  | none   => False

/-- Stevens scale-type gate enforcement — mean on ordinal/nominal is forbidden. -/
theorem lens_count_mean_blocked :
    ¬ dispatchValid Commander.naesengmoon "lens_count" Op.mean := by
  unfold dispatchValid
  rw [naesengmoon_lens_count_is_ordinal]
  exact mean_invalid_ordinal

theorem archival_category_mean_blocked :
    ¬ dispatchValid Commander.occam "archival_reason_category" Op.mean := by
  unfold dispatchValid
  rw [occam_archival_category_is_nominal]
  exact mean_invalid_nominal

/-- Sanity: ratio ops permitted on ratio-scale metrics. -/
theorem supersession_confidence_pct_allowed :
    dispatchValid Commander.occam "supersession_confidence" Op.pct := by
  unfold dispatchValid
  simp [scaleOf, validOp]

end Measurement.CommanderMetrics
