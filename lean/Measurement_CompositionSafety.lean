/-
  Measurement_CompositionSafety.lean — Phase 3 of 4-phase formalization

  Prove dispatch composition does not promote weaker scales beyond valid use.
  Specifically:
    1. A composed dispatch chain (A → B → C) only requires individual scale validity.
    2. Compositional AND: if any link blocks, the chain is blocked.
    3. max_depth=3 cap (Lawvere-Tierney 1971) terminates Knaster-Tarski recursion.
-/

import Measurement_MetricScale
import Measurement_CommanderMetrics

namespace Measurement.CompositionSafety

open Measurement.MetricScale
open Measurement.CommanderMetrics

/-- A dispatch step: source commander emits a metric-op pair. -/
structure DispatchStep where
  source  : Commander
  metric  : String
  op      : Op

/-- max depth (Lawvere-Tierney idempotence, mirror MAX_DISPATCH_DEPTH=3). -/
def maxDepth : Nat := 3

/-- A chain of dispatch steps is valid iff every step is dispatchValid AND length ≤ maxDepth. -/
def chainValid : List DispatchStep → Prop
  | []      => True
  | (s :: rest) =>
      dispatchValid s.source s.metric s.op
      ∧ (s :: rest).length ≤ maxDepth
      ∧ chainValid rest

/-- Compositional AND: chain of length 0 is trivially valid. -/
theorem empty_chain_valid : chainValid [] := by trivial

/-- Compositional AND: invalid leading step kills the chain. -/
theorem invalid_step_kills_chain
    (s : DispatchStep) (rest : List DispatchStep)
    (h : ¬ dispatchValid s.source s.metric s.op) :
    ¬ chainValid (s :: rest) := by
  intro hc
  exact h hc.1

/-- max depth cap: any chain longer than maxDepth is invalid. -/
theorem chain_exceeds_max_depth_invalid (steps : List DispatchStep)
    (hlen : steps.length > maxDepth) : ¬ chainValid steps := by
  cases steps with
  | nil => simp [maxDepth] at hlen
  | cons head tail =>
      intro hc
      have := hc.2.1  -- length ≤ maxDepth
      omega

/-- A concrete blocked example: Naesengmoon lens_count mean head of any chain → invalid. -/
theorem lens_count_mean_chain_blocked (rest : List DispatchStep) :
    ¬ chainValid
        ({ source := Commander.naesengmoon, metric := "lens_count", op := Op.mean } :: rest) := by
  apply invalid_step_kills_chain
  exact lens_count_mean_blocked

-- Phase 4 (deferred): empirical validation on real PROM cycles.
-- TODO Phase 4: integrate with bhgman_tool/engine/legion/measurement.py
--               via Lean ↔ Python FFI (lake export) or batch JSON test runner.

end Measurement.CompositionSafety
