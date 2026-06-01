/-
  Occam_SupersessionScore.lean — 오캄 정량 supersession score σ 안전 불변식 형식화.

  Python: engine/occam/scoring.py (score_node). 거기 σ = candidacy · guard ∈ [0,1].
  여기선 [0,1] 실수를 0..SCALE 정수 basis-point로 mirror (Mathlib-free, 결정가능 산술).

  형식화 대상 = 안전 불변식 (load-bearing safety theorems):
    1. score_le_candidacy   — σ ≤ candidacy mass (아카이브 점수는 후보신호를 넘지 않음)
    2. score_le_scale       — σ ≤ SCALE (경계, [0,1] 유지)
    3. protected_score_zero — entrenchment = SCALE (canonical tier) ⇒ σ = 0 (never archive)
    4. no_successor_zero    — twin/후속 부재 ⇒ σ = 0 (machloket / Eilu va-Eilu, flag only)
    5. score_antitone_entrench — entrenchment ↑ ⇒ σ ↓ (truth-guard 보호 단조성)
    6. candidacy_le_scale   — noisy-OR candidacy ∈ [0, SCALE]

  학문 정전: AGM epistemic entrenchment (Gärdenfors–Makinson 1988) = guard.
            noisy-OR evidence combination (Pearl 1988) = candidacy.

  KG: occam-kam-canonical-2026-05-26, consensus-occam-entropy-truth-2026-05-26,
      dt-occam-naesengmoon-confidence
-/

namespace Occam.Score

/-- [0,1] 을 1000 basis-point 정수로. (Python σ ∈ [0,1] ↔ Lean 0..SCALE) -/
def SCALE : Nat := 1000

theorem scale_pos : 0 < SCALE := by decide

/-- truth-guard: G = (SCALE − e) · twin_gate. e=SCALE(canonical) 또는 twin 부재 ⇒ 0. -/
def guard (entrench : Nat) (twin : Bool) : Nat :=
  if twin then SCALE - entrench else 0

/-- supersession score σ = candidacy · guard / SCALE (basis-point 재정규화). -/
def score (candidacy entrench : Nat) (twin : Bool) : Nat :=
  candidacy * guard entrench twin / SCALE

/-- noisy-OR candidacy C = SCALE − (SCALE−r)(SCALE−s)(SCALE−d)/SCALE². (Pearl 1988) -/
def candidacy (r s d : Nat) : Nat :=
  SCALE - (SCALE - r) * (SCALE - s) * (SCALE - d) / (SCALE * SCALE)

-- ── guard 성질 ────────────────────────────────────────────────────────────────

theorem guard_le_scale (e : Nat) (twin : Bool) : guard e twin ≤ SCALE := by
  unfold guard
  cases twin with
  | true  => simp
  | false => simp

/-- canonical tier (e=SCALE) ⇒ guard = 0. -/
theorem guard_zero_at_full_entrench (twin : Bool) : guard SCALE twin = 0 := by
  unfold guard
  cases twin with
  | true  => simp
  | false => simp

/-- twin 부재 ⇒ guard = 0. -/
theorem guard_zero_no_twin (e : Nat) : guard e false = 0 := by
  unfold guard; simp

-- ── 핵심 안전 정리 ────────────────────────────────────────────────────────────

/-- (3) PROTECTED: entrenchment = SCALE ⇒ σ = 0. canonical/lesson/contract/verdict never archive. -/
theorem protected_score_zero (c : Nat) (twin : Bool) : score c SCALE twin = 0 := by
  unfold score
  rw [guard_zero_at_full_entrench]
  simp

/-- (4) machloket: 후속자(twin) 없으면 σ = 0. flag-only, supersede 금지. -/
theorem no_successor_zero (c e : Nat) : score c e false = 0 := by
  unfold score
  rw [guard_zero_no_twin]
  simp

/-- (1) σ ≤ candidacy mass: 아카이브 점수는 raw candidacy 를 넘지 못함. -/
theorem score_le_candidacy (c e : Nat) (twin : Bool) : score c e twin ≤ c := by
  unfold score
  have hg : guard e twin ≤ SCALE := guard_le_scale e twin
  calc c * guard e twin / SCALE
      ≤ c * SCALE / SCALE := Nat.div_le_div_right (Nat.mul_le_mul_left c hg)
    _ = c := by rw [Nat.mul_div_cancel _ scale_pos]

/-- (2) 경계: candidacy ≤ SCALE ⇒ σ ≤ SCALE ([0,1] 유지). -/
theorem score_le_scale (c e : Nat) (twin : Bool) (hc : c ≤ SCALE) :
    score c e twin ≤ SCALE :=
  Nat.le_trans (score_le_candidacy c e twin) hc

/-- (5) truth-guard 단조성: entrenchment 가 클수록 σ 는 같거나 작다. -/
theorem score_antitone_entrench (c e₁ e₂ : Nat) (twin : Bool) (h : e₁ ≤ e₂) :
    score c e₂ twin ≤ score c e₁ twin := by
  unfold score
  apply Nat.div_le_div_right
  apply Nat.mul_le_mul_left
  unfold guard
  cases twin with
  | true  => show SCALE - e₂ ≤ SCALE - e₁; exact Nat.sub_le_sub_left h SCALE
  | false => show (0 : Nat) ≤ 0; exact Nat.le_refl 0

-- ── candidacy 경계 (noisy-OR ∈ [0, SCALE]) ────────────────────────────────────

/-- (6) noisy-OR candidacy 는 SCALE 를 넘지 않음. -/
theorem candidacy_le_scale (r s d : Nat) : candidacy r s d ≤ SCALE := by
  unfold candidacy
  exact Nat.sub_le SCALE _

-- ── 수치 sanity (Python decay/deadness mirror, basis-point) ────────────────────

/-- guard at canonical = 0 (concrete). -/
example : guard SCALE true = 0 := by decide
/-- guard at plain tier (e=0), twin → 전체 통과. -/
example : guard 0 true = SCALE := by decide
/-- 완전중복(c=SCALE)·plain(e=0)·twin → σ = SCALE (SUPERSEDE 상한). -/
example : score SCALE 0 true = SCALE := by decide
/-- ontology_class tier(e=700) 완전후보(c=SCALE) → σ = 300 (VERIFY 영역, auto-supersede 불가). -/
example : score SCALE 700 true = 300 := by decide

end Occam.Score
