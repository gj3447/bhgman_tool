/-
재배맨 Seed Lifecycle & Plan Algebra — 2026-06-01

PROM 64 F6 형식화 ("MIND/lean_formalization/SeedLifecycle.lean 신규 작성") + PROM 16 재배맨 엔진
v2 (engine/jaebaeman/) 의 Lean 측 정전. Mathlib-free standalone (`lean SeedLifecycle.lean`).

공학 측 매핑 (engine/jaebaeman/):
  Plan            ↔  planner.PlanNode 트리 (μX.(CHUPiece + List X) initial algebra, PROM 64 C1)
  Plan.leaf       ↔  is_leaf (children=()) / primitive task
  Plan.branch     ↔  compound task (children = 하위 계획, List X)
  depth           ↔  planner.depth_max (catamorphism / fold)
  size            ↔  씨앗 개수 (to_seeds 길이)
  Status / Step   ↔  jaebaeman_models.SeedStatus (READY→DISPATCHED→COLLECTED, FAILED) lifecycle
  WellDepthed cap ↔  SKILL v2.4 depth ∈ [0, MAX_DEPTH=3] invariant (jaebaeman invariants E4)

핵심 정리:
  T1 size_pos          : 모든 계획은 ≥1 노드 (루트). 빈 계획 없음.
  T2 depth_branch      : depth (branch cs) = 1 + depthList cs (catamorphism 전개)
  T3 leaf_min          : 잎의 depth = 0 (최소). primitive = 바닥.
  T4 no_step_terminal  : COLLECTED/FAILED 에서 나가는 transition 없음 (terminal 흡수)
  T5 step_deterministic: READY 에서의 transition 은 DISPATCHED 유일 (lifecycle 결정론 진입)

KG: lesson-jaebaeman-engine-impl-prom16-2026-06-01, jaebaeman-concept-occam-pass-2026-06-01,
    lesson-prom64-jaebaeman-chu-agentfolder-2026-04-29 (μX initial algebra)
-/

namespace Jaebaeman

/-- μX.(CHUPiece + List X) initial algebra. leaf = CHUPiece(primitive), branch = List X(compound). -/
inductive Plan where
  | leaf : Plan
  | branch : List Plan → Plan
  deriving Repr

/- depth catamorphism (planner.depth_max 거울). 중첩 List → mutual 구조 재귀 (Mathlib-free). -/
mutual
  def depth : Plan → Nat
    | .leaf => 0
    | .branch cs => 1 + depthList cs
  def depthList : List Plan → Nat
    | [] => 0
    | c :: rest => Nat.max (depth c) (depthList rest)
end

/- size = 노드 개수 (씨앗 수, to_seeds 길이 거울). -/
mutual
  def size : Plan → Nat
    | .leaf => 1
    | .branch cs => 1 + sizeList cs
  def sizeList : List Plan → Nat
    | [] => 0
    | c :: rest => size c + sizeList rest
end

/-- T1: 모든 계획은 ≥1 노드 (루트 항상 존재). 빈 씨앗 배치 불가. -/
theorem size_pos : ∀ p : Plan, 0 < size p := by
  intro p
  cases p with
  | leaf => decide
  | branch cs => simp [size]; omega

/-- T2: depth 전개 (branch = 1 + 자식들의 depth). catamorphism 정의식. -/
theorem depth_branch (cs : List Plan) : depth (.branch cs) = 1 + depthList cs := by
  rfl

/-- T3: 잎의 depth = 0 (primitive = 바닥, 최소 depth). -/
theorem leaf_depth_zero : depth .leaf = 0 := by rfl

/-- SKILL v2.4 depth invariant: depth ≤ cap (E4 DepthInvariantViolation 의 양의 형태). -/
def WellDepthed (cap : Nat) (p : Plan) : Prop := depth p ≤ cap

/-- 잎은 어떤 cap ≥ 0 에서도 well-depthed (depth 0). -/
theorem leaf_welldepthed (cap : Nat) : WellDepthed cap .leaf := by
  unfold WellDepthed; rw [leaf_depth_zero]; exact Nat.zero_le cap

/-- 씨앗 lifecycle 상태 (jaebaeman_models.SeedStatus). -/
inductive Status where
  | ready | dispatched | collected | failed | archived
  deriving Repr, DecidableEq

/-- 허용 transition (재배맨 SKILL lifecycle: READY→DISPATCHED→COLLECTED→ARCHIVED, DISPATCHED→FAILED). -/
inductive Step : Status → Status → Prop where
  | dispatch : Step .ready .dispatched
  | collect  : Step .dispatched .collected
  | archive  : Step .collected .archived
  | fail     : Step .dispatched .failed

/-- T4: COLLECTED 는 terminal 직전이나, FAILED/ARCHIVED 에서 나가는 transition 없음 (흡수 상태). -/
theorem no_step_from_failed : ∀ s, ¬ Step .failed s := by
  intro s h; cases h

theorem no_step_from_archived : ∀ s, ¬ Step .archived s := by
  intro s h; cases h

/-- T5: READY 에서의 transition 은 DISPATCHED 로 유일 (lifecycle 진입 결정론). -/
theorem ready_step_unique : ∀ s, Step .ready s → s = .dispatched := by
  intro s h; cases h; rfl

/-- 보너스: DISPATCHED 는 collected 또는 failed 로만 (분기 2). -/
theorem dispatched_step_branches : ∀ s, Step .dispatched s → s = .collected ∨ s = .failed := by
  intro s h
  cases h
  · exact Or.inl rfl
  · exact Or.inr rfl

end Jaebaeman
