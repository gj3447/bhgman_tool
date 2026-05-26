/-
  Longinus_RefinementSoundness.lean
  ---------------------------------
  Pierce-style refinement-type SOUNDNESS (Progress + Preservation) for the
  Longinus drift-resolution dynamics. Closes the "citation-without-proof" gap
  (audit-apt-theoretical-basis-efficacy-2026-05-26 #5): longinus SKILL.md cites
  refinement types (Pierce TAPL 2002) but the core soundness theorem pair was
  never formalized — only BX lens laws (see Longinus_ConfidenceSchema_*) existed.

  Model
  -----
  A ReferenceSite, viewed as a refinement-typed value, evolves under
  drift-resolution. We give it a small-step operational semantics and prove the
  two halves of Pierce type soundness:

    * PROGRESS     : a well-formed non-terminal state can always take a step
                     (the resolver never gets "stuck").
    * PRESERVATION : every step preserves the longinus refinement invariant
                     — trust is monotone non-increasing (drift may DEMOTE or
                     TERMINATE confidence, never SILENTLY PROMOTE it). This is
                     the Goodhart safeguard lifted to the dynamics level.

  SOUNDNESS = Progress ∧ Preservation (Pierce TAPL §8 / §15 pattern).

  Mathlib-free standalone (Lean 4, core only). 0 sorry.

  HONEST SCOPE (audit caveat): this proves soundness of the *abstract* longinus
  refinement model. Whether the Python engine (engine/longinus_drift_audit/)
  faithfully implements this model is a separate model–code adequacy question
  (Longinus L-layer binding), NOT discharged here.

  KG: audit-apt-theoretical-basis-efficacy-2026-05-26 (#5 citation-proof gap),
      longinus-confidence-schema-3tier-2026-05-13
-/

namespace LonginusRefinementSoundness

/-- 3-tier confidence (mirrors Longinus_ConfidenceSchema_GraphifyAbsorbed). -/
inductive Confidence : Type
  | EXTRACTED
  | INFERRED
  | AMBIGUOUS
  deriving DecidableEq, Repr

/-- Trust scalar: EXTRACTED(2) > INFERRED(1) > AMBIGUOUS(0). -/
def trust : Confidence → Nat
  | .EXTRACTED => 2
  | .INFERRED  => 1
  | .AMBIGUOUS => 0

/-- Refinement-typed reference state under drift resolution.
    `bound`   : sha256 baseline matches, confidence c.
    `drifted` : sha256 mismatch detected, confidence c (subject to demotion).
    `resolved`: terminal — rebound clean or quarantined to human gate. -/
inductive RS : Type
  | bound    (c : Confidence)
  | drifted  (c : Confidence)
  | resolved
  deriving Repr

/-- Terminal (value) states. -/
def isValue : RS → Bool
  | .resolved => true
  | _         => false

/-- Trust of a state (terminal = 0). -/
def stateTrust : RS → Nat
  | .bound c   => trust c
  | .drifted c => trust c
  | .resolved  => 0

/-- Small-step drift-resolution semantics.
    detect    : a bound site is found drifted (sha256 mismatch).
    demoteEI  : drifted EXTRACTED loses trust → INFERRED.
    demoteIA  : drifted INFERRED loses trust → AMBIGUOUS.
    quarantine: drifted AMBIGUOUS must go to the human gate → resolved.
    rebind    : a bound site is re-verified clean → resolved. -/
inductive Step : RS → RS → Prop
  | detect    (c : Confidence) : Step (.bound c)              (.drifted c)
  | demoteEI                    : Step (.drifted .EXTRACTED)  (.drifted .INFERRED)
  | demoteIA                    : Step (.drifted .INFERRED)   (.drifted .AMBIGUOUS)
  | quarantine                  : Step (.drifted .AMBIGUOUS)  .resolved
  | rebind    (c : Confidence) : Step (.bound c)              .resolved

/-- **PROGRESS**: every non-terminal state can take a step (no stuck states). -/
theorem progress (s : RS) (h : isValue s = false) : ∃ s', Step s s' := by
  cases s with
  | bound c => exact ⟨.drifted c, .detect c⟩
  | drifted c =>
      cases c with
      | EXTRACTED => exact ⟨.drifted .INFERRED, .demoteEI⟩
      | INFERRED  => exact ⟨.drifted .AMBIGUOUS, .demoteIA⟩
      | AMBIGUOUS => exact ⟨.resolved, .quarantine⟩
  | resolved => simp [isValue] at h

/-- **PRESERVATION**: every step preserves the refinement invariant —
    trust is monotone non-increasing (no silent promotion under drift). -/
theorem preservation_trust_noninc (s s' : RS) (h : Step s s') :
    stateTrust s' ≤ stateTrust s := by
  cases h with
  | detect c   => exact Nat.le_refl _      -- trust c ≤ trust c (drift keeps tier, defers demotion)
  | demoteEI   => decide                   -- 1 ≤ 2
  | demoteIA   => decide                   -- 0 ≤ 1
  | quarantine => decide                   -- 0 ≤ 0
  | rebind c   => exact Nat.zero_le _      -- 0 ≤ trust c

/-- **SOUNDNESS** (Pierce TAPL): Progress ∧ Preservation combined —
    any non-terminal refinement state can always make progress, and that
    progress never silently promotes trust. -/
theorem soundness (s : RS) (h : isValue s = false) :
    ∃ s', Step s s' ∧ stateTrust s' ≤ stateTrust s := by
  obtain ⟨s', hstep⟩ := progress s h
  exact ⟨s', hstep, preservation_trust_noninc s s' hstep⟩

/-- Corollary (no-silent-promotion, the Goodhart-at-dynamics safeguard):
    there is NO step that increases trust. -/
theorem no_silent_promotion (s s' : RS) (h : Step s s') :
    ¬ (stateTrust s < stateTrust s') := by
  have hle := preservation_trust_noninc s s' h
  omega

end LonginusRefinementSoundness

/-
  Verification summary (Mathlib-free, 0 sorry)
  --------------------------------------------
    progress                   — Pierce Progress: non-value ⇒ ∃ step (no stuck)
    preservation_trust_noninc  — Pierce Preservation: step ⇒ trust non-increasing
    soundness                  — Progress ∧ Preservation (TAPL §8/§15)
    no_silent_promotion        — corollary: no step raises trust (Goodhart safeguard)

  Closes audit #5 citation-proof gap for refinement-type soundness.
  Residual: model–code adequacy (Python engine ⊨ this model) NOT proven here.
-/
