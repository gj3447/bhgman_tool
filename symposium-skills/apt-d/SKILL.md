---
name: apt-d
kg_ref: ATOM_Skill_apt_d
version: "0.1.0-draft"
channel: experimental
description: >
  APT-D variant orchestrator — **SIBLING VARIANT** of /apt v27 (NOT replacement).
  5-axis coherent package per `rfc-apt-d-variant-coherent-package-2026-05-14`:
  M1 continuous depth (instead of 5-predicate atomicity) +
  M2 score function (instead of binary AtomicSpan gate) +
  M3 shared-object sibling (Naesengmoon M1 equivocation resolved) +
  M4 smooth ODE transitions (instead of discrete SA→SP→ST→SCW) +
  M5 forward-reverse symmetric (APT+TPA unified).
  29 Lean theorem formal floor (G1 9 APT_Diffusion_Foundation + G2 6 APT_Flow_Matching + G3 14 APT_Structural_Refinement, all Mathlib-free PASS exit 0).
  Honest load-bearing limitation: shared-object sibling assumes UNIFIED artifact.
  Multi-file boundary forces back to v28-like decomposition.
  Invoke when: single-artifact problem + continuous metric available + smooth transition required.
  Reject when: multi-file refactor (use /apt v27 instead).
  # KG: ATOM_Skill_apt_d, rfc-apt-d-variant-coherent-package-2026-05-14
  # KG: lesson-fixagent-k01-patch-recurrence-2026-05-14 (motivating)
  # KG: taliban-a3-axiom-relaxation-2026-05-14 (REJECT verdict → APT-D branch)
---

## 🚧 Draft Status (S2 scaffold, 2026-05-14)

This skill is **EXPERIMENTAL** — `channel: experimental`, NOT production. Production users should use `/apt` (v27 stable).

**Status fields**:
- `formal_floor`: 29 Lean theorems PASS (Mathlib-free) ✓ — G1 APT_Diffusion_Foundation 9 + G2 APT_Flow_Matching 6 + G3 **APT_Structural_Refinement** 14. (Prior commit 997196b mis-identified G3 as `APT_TPA_Dual.lean` — that's a sibling file, NOT in RFC §3.3. RFC was always correct. Self-correction logged: `lesson-aptd-drift-correction-self-correction-2026-05-14`.)
- `runtime`: NOT implemented (skill scaffold only)
- `dogfood`: 0 cycles run on real codebase
- `migration_plan`: per RFC §6 (NOT yet executed)

**Open per RFC honest_limitation_load_bearing**:
> shared-object sibling ontology assumes unified artifact; multi-file boundary forces APT-D back to v28-like decomposition. §4 toy example deliberately picks single-artifact case to dodge.

→ APT-D 는 **single-artifact / single-file refactor** 에 한정. multi-file 은 `/apt` 로 redirect.

---

## 🎛 5-axis coherent package (RFC §3)

| Axis | APT v27 (discrete) | APT-D (continuous) | external canon |
|------|--------------------|--------------------|----------------|
| **M1 depth** | 5-predicate C(S) gate (binary AtomicSpan) | continuous depth metric d ∈ [0,1] (diffusion grounding) | Ho et al. 2020 DDPM; Song et al. 2021 score-based generative |
| **M2 score** | binary AtomicSpan / non-Atomic | ∇log p_t(x) score function (Song-Ermon 2019) | Hyvärinen 2005 score matching |
| **M3 sibling** | Naesengmoon LensSet UNION (constitutional/longinus/solid/...) | shared-object sibling (same x, different t) — Naesengmoon M1 equivocation 해소 | Hutchinson trace estimator |
| **M4 transitions** | discrete SA→SP→ST→SCW phases | smooth ODE dx/dt = f(x,t) (DDIM / probability flow ODE) | Song 2021 SDE ↔ ODE bijection |
| **M5 symmetry** | APT (forward, design→code) ≠ TPA (reverse, code→design) | unified — diffusion forward + reverse process | Anderson 1982 reverse-time SDE |

각 axis 의 Lean 결정화: `MIND/lean_formalization/APT_Diffusion_Foundation.lean` (G1) + `APT_Flow_Matching.lean` (G2) + `APT_TPA_Dual.lean` (G3).

---

## 📍 Invocation pattern

```
/apt-d <problem>     # variant cycle (single-artifact)
/apt-d --reverse <code>   # M5 reverse mode (TPA-mirror)
/apt-d --score <span>     # M2 score evaluation
/apt-d --check-applicable <problem>   # gate check: applicable or redirect to /apt
```

### Applicability gate (decline if violated)

```cypher
// PRE-INVOCATION CHECK
MATCH (cfg:MethodologyConfig {name:'APT_D_Applicability_v0.1'})
RETURN cfg.single_artifact_required,    // = true
       cfg.continuous_metric_available, // = true
       cfg.smooth_transition_admissible // = true
```

→ 3개 중 하나라도 false 면 `/apt` 로 redirect.

---

## 🔬 Formal floor — 29 Lean theorem reference (RFC §3 verified)

> **self-correction 2026-05-14**: prior commit 997196b claimed "RFC drift: 29→24" — that was a *meta-drift*. The correct G3 file is `APT_Structural_Refinement.lean` (14 theorems), NOT `APT_TPA_Dual.lean` (9 theorems, separate sibling file in M5 symmetry context). RFC §3 was always correct: G1 9 + G2 6 + G3 14 = 29. Lesson: `lesson-aptd-drift-correction-self-correction-2026-05-14` (memory feedback_check_state_first violated *twice* — once when claiming "29 unverified", second when "correcting" with wrong file reference).


### G1 — Diffusion Foundation (9 theorem, `APT_Diffusion_Foundation.lean`)

- T1 `forward_process_well_defined`
- T2 `reverse_process_exists` (Anderson 1982)
- T3 `score_function_pointwise`
- T4 `ddim_eta_zero_deterministic`
- T5 `flow_matching_equivalence`
- T6 `marginal_consistency`
- T7 `boundary_t0_recovers_data`
- T8 `boundary_tT_recovers_prior`
- T9 `langevin_steady_state`

### G2 — Flow Matching (6 theorem, `APT_Flow_Matching.lean`)

- T10 `conditional_flow_matching_unbiased`
- T11 `ot_flow_minimizes_displacement`
- T12 `coupling_independence`
- T13 `linear_interpolant_kinetic`
- T14 `score_to_flow_conversion`
- T15 `flow_to_score_conversion`

### G3 — Structural Refinement (14 theorem, `APT_Structural_Refinement.lean`, Yao 2023 ToT + Madaan 2023 Self-Refine + Bai 2022 Constitutional)

- S1 `tot_branching_terminates` — SP descent termination
- S2 `tot_leaf_size_one` — AtomicSpan boundary
- S3 `tot_empty_branch_size` — vacuous boundary
- S4 `self_refine_monotone_improvement` — FixAgent/RefineAgent monotone
- S5 `self_refine_invalid_critique_no_guarantee` — honest invalid-critique limit
- S6 `constitutional_principles_compose` — Constitutional lens composition
- S7 `apt_sp_is_tot_with_kg_pruning` — SP = ToT + KG pruning
- S8 `apt_atomic_maps_to_leaf` — AtomicSpan ↔ ToT leaf
- S9 `apt_fix_agent_is_self_refine` — FixAgent = Self-Refine
- S10 `apt_fix_agent_improves_when_valid` — RefineAgent guarantee
- S11 `apt_taliban_squad_constitutional` — TalibanSquad lens UNION
- S12 `taliban_lens_names_distinct` — lens distinctness
- S13 `apt_structural_canon_complete` — 3-canon hyperedge complete
- S14 `apt_three_canon_distinct` — pairwise distinct

**Build**: `cd MIND/lean_formalization && lean APT_Structural_Refinement.lean APT_Diffusion_Foundation.lean APT_Flow_Matching.lean` → 29/29 PASS exit 0 (2026-05-14 재확인).

**Sibling file (NOT in RFC §3 G1/G2/G3)**: `APT_TPA_Dual.lean` (9 theorem T16-T24) provides M5 forward-reverse mirror in a separate independent file. *Optional* additional formal evidence, not part of the 29-theorem RFC §3 backbone.

---

## ⚠️ Load-bearing limitations

### L1 — single-artifact only

multi-file refactor 에서 shared-object sibling 가정 (M3) 깨짐. each file becomes its own diffusion process → APT v27 decomposition 으로 fallback.

### L2 — continuous metric availability

M1 depth metric d ∈ [0,1] 측정 가능해야 적용. 정성적 problem (예: "이 코드 좋니?") 은 score function 정의 불가 → /apt redirect.

### L3 — runtime missing

S2 scaffold 단계 (2026-05-14). runtime resolver / gate / executor 모두 미구현. dogfood = 0 cycle. production 사용 금지.

### L4 — meta-test status

본 SKILL 자체가 *Claude 가 design + Claude 가 invoke* → K-01 patch-level recurrence risk. RFC level 에서는 mitigation `mitigation-fixagent-rubberstamp-section8-2026-05-14` 적용 (3-prong rotation/fuzzing/cap). SKILL level 에서는 별도 cold-context sample test 필요 (sprint plan: `EMPIRICAL_TEST_SPRINT_2026-05-14.md`).

---

## 🔗 Cross-ref

- **RFC**: `THEORY/APT/rfc/rfc-apt-d-variant-coherent-package-2026-05-14.md`
- **Lean**: `MIND/lean_formalization/APT_Diffusion_Foundation.lean`, `APT_Flow_Matching.lean`, `APT_TPA_Dual.lean`
- **KG node**: `rfc-apt-d-variant-coherent-package-2026-05-14` (:MethodologyRFC, PRELIMINARY)
- **Parent skill**: `/apt` (v27 stable, this skill is sibling)
- **Motivating lesson**: K-01 patch-level recurrence + Naesengmoon A3 axiom relaxation REJECT verdict

---

## 🛣 Migration plan (per RFC §6)

1. ✅ S1 RFC draft (2026-05-14, commit 499bca9)
2. 🚧 S2 SKILL scaffold (this file, 2026-05-14)
3. ⏳ S3 runtime implementation (resolver / gate / executor)
4. ⏳ S4 cold-context dogfood (3-5 single-artifact case)
5. ⏳ S5 PROVISIONAL → CANONICAL_VARIANT promotion (user verdict gate)
6. ⏳ S6 channel: experimental → stable

**S3 entrance criterion**: empirical test sprint (`EMPIRICAL_TEST_SPRINT_2026-05-14.md`) 의 sample-of-N=5 결과 + RFC honest_limitation_load_bearing 완화 OR 명시적 scope 좁힘.

# KG: ATOM_Skill_apt_d (PRELIMINARY)
# Authority: delegated_via_2026-05-14_blanket_proceed
# Parent RFC: rfc-apt-d-variant-coherent-package-2026-05-14
# memory: feedback_blanket_proceed_authorization_pattern, feedback_auto_crystallization_default, feedback_theoretical_depth_over_line_count
