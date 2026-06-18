# apt — Gates

> **Lazy-load reference for `apt` skill.**
> Loaded *only when* the orchestrator enters the relevant phase/gate.
> Parent skill: [`../SKILL.md`](../SKILL.md). Repo CHANGELOG: [`../../CHANGELOG.md`](../../CHANGELOG.md).
> Refactor source: PROM 16 F6.1 Progressive Disclosure (2026-04-29).
> KG: `lesson-prom16-skillver-progressive-disclosure-drift-2026-04-29`.

---

### 3.2 Gate Sequence at Each Transition

Every transition follows this EXACT sequence. No steps may be skipped.

#### PH3 (SP Decomposition) Gate Sequence:

```
1. KG Density Check (D21)
   - Query INFORMED_BY count
   - If < 5: BLOCK --> run KAL
   - Check source type diversity
   - If < 3 types: BLOCK --> diversify via KAL
   - Check foundation:composite ratio
   - If < 2:1: BLOCK --> acquire more foundational sources

2. C(S) Predicate Evaluation (cheap rejection first)
   - v (complexity <= 500 lines)
   - tau (concrete I/O types)
   - iota (testable assertions)
   - delta (decomposition diseconomy)
   - sigma_auto (automated check)

3. Adversarial Round (C_S_sigma)
   - Spawn adversarial-critic agent (sonnet model)
   - Critic receives: decomposition plan, INFORMED_BY links, span context
   - Critic MUST produce >= 3 findings
   - If < 3 findings: re-run with STRONGER prompt (see Section 7.2)
   - Each finding logged as AptFeedback node in KG
   - WebSearch evidence MUST be cited for each design decision

4. Ground Truth Verification
   - KAL link density verified (automated)
   - Architecture pattern WebSearch completed
   - tau banned-type check executed

5. sigma_oracle (HUMAN)
   - Present to human: proposal + critic findings + ground truth results
   - BLOCK until human responds
   - Human decides: APPROVE | RETURN(reason) | ESCALATE
   - Decision logged as AptDecisionLog node in KG

6. Log to KG
   - Create AptDecisionLog node with full audit trail
   - Link to span, critic findings, ground truth results
```

#### PH4 (ST Crystallization) Gate Sequence:

```
1. Contract Completeness Check
   - input_type defined
   - output_type defined
   - acceptance_tests defined
   - postconditions falsifiable

2. Adversarial Round (RefinementGate)
   - Spawn adversarial-critic agent (sonnet model)
   - Critic receives: contract draft, task description, test sketch
   - Critic MUST produce >= 3 findings
   - If < 3 findings: re-run with STRONGER prompt
   - Each finding logged as AptFeedback node in KG
   - WebSearch evidence MUST be cited for design decisions

3. Ground Truth Verification
   - tau_check 5/5 passes
   - Postcondition falsifiability test passes
   - WebSearch for API compatibility, prior art

4. sigma_oracle (HUMAN)
   - Present to human: contract + critic findings + ground truth
   - BLOCK until human responds
   - Decision logged as AptDecisionLog node in KG

5. Log to KG
```

#### PH5 (SCW Implementation) Gate Sequence:

```
1. Implementation Completion
   - Code written following TDD (RED -> GREEN -> REFACTOR)
   - MATERIALIZES relationship created

2. Ground Truth Verification (MANDATORY -- runs FIRST)
   - cargo test: MUST pass (all tests green)
   - cargo build --release: MUST compile
   - cargo clippy -- -D warnings: MUST pass
   - If any fail: BLOCK -- fix before proceeding

3. Adversarial Round (FulfillmentGate)
   - Spawn adversarial-critic agent (sonnet model)
   - Critic receives: implemented code, contract, test results, coverage
   - Critic MUST produce >= 3 findings
   - If < 3 findings: re-run with STRONGER prompt
   - Each finding logged as AptFeedback node in KG
   - Ground-truth-testable findings get auto-verified (D23)

4. FulfillmentGate 13/13 Check
   - Checks 1-11: unchanged from v14
   - Check 12: Adversarial Critic review PASS -- no unresolved BLOCKERs
   - Check 13: Ground truth primacy verified -- all factual claims validated

5. sigma_oracle (HUMAN)
   - Present to human: code + test results + critic findings + coverage
   - BLOCK until human responds
   - Decision logged as AptDecisionLog node in KG

6. Log to KG
```

---



## 12. Gate Evidence Table (v17)

```
Gate Evidence Table (v17):
+---------------+--------------------------------------------------------------+
| Transition    | Required Evidence                                            |
+---------------+--------------------------------------------------------------+
| -> PH3 (SP)  | SA exists AND root span created                              |
| SP internal   | KAL complete AND INFORMED_BY >= 5                            |
|               | v17: source_types >= 3 AND foundation:composite >= 2:1       |
|               | v17: DensityCheck logged in KG                               |
+---------------+--------------------------------------------------------------+
| -> PH4 (ST)  | C(S) auto pass AND sigma_oracle approved                     |
|               | v17: AdversarialRound(C_S_sigma) -- no BLOCKERs             |
|               | v17: WebSearch evidence cited for design decisions           |
|               | v17: sigma_oracle is HUMAN (allow_agent_sigma: false)        |
|               | v17: AptDecisionLog created in KG                            |
+---------------+--------------------------------------------------------------+
| -> PH5 (SCW) | tau_check 5/5 AND impact_tests defined                       |
|               | v17: AdversarialRound(RefinementGate) -- no BLOCKERs        |
|               | v17: WebSearch evidence for API choices                      |
|               | v17: sigma_oracle is HUMAN                                   |
|               | v17: AptDecisionLog created in KG                            |
+---------------+--------------------------------------------------------------+
| PH5 -> DONE  | FulfillmentGate 13/13 AND coverage AND NFR                   |
|               | v17: cargo test PASS (MANDATORY before anything else)        |
|               | v17: cargo clippy PASS                                       |
|               | v17: AdversarialRound(FulfillmentGate) completed             |
|               | v17: Ground truth primacy verified (all claims tested)       |
|               | v17: sigma_oracle is HUMAN                                   |
|               | v17: AptDecisionLog created in KG                            |
+---------------+--------------------------------------------------------------+
| -> PH6       | AptFeedback created (category + severity)                    |
+---------------+--------------------------------------------------------------+
```

---



## 23. Approval Gates Table (v17)

| Gate | Who | SLA | On Timeout |
|------|-----|-----|------------|
| sigma_auto (v,tau,iota,delta) | automated | instant | N/A |
| sigma_oracle | **HUMAN (LOCKED)** | 0 (immediate) | BLOCK -- re-ask |
| Adversarial Critic | automated (sonnet) | <= 60s per round | ESCALATE -- critic timeout = gate blocked |
| Ground truth (compiler/test) | automated | <= 300s | BLOCK -- ground truth must complete |
| DensityCheck | automated | <= 30s | BLOCK -- KAL must complete |

---

## 24. Gate Philosophical Grounding (2026-05-11 추가)

> Cross-ref: `THEORY/APT/PHILOSOPHICAL_FOUNDATIONS.md` §3 (Lakatos) + §6 (Friston FEP) + APT_Cycle_Functor.lean (`apt_cycle_lakatos_progressive` PASS) + APT_AtomicSpan_MDL.lean (`mdl_minimum_at_sweet` PASS).
> **iter 102 갱신**: 17 APT Lean files / 156 theorems Mathlib-free 0 sorry — 9-tier architecture. Per-gate explicit Lean theorem cite:
> - **DensityCheck (PH3)** = Solomonoff prior loading + Kolmogorov MDL (`APT_AtomicSpan_MDL.lean:sweet_in_canonical_range`)
> - **C(S)_sigma (PH3)** = Lakatos hard core protection + 5 predicates (`APT_Lakatos_Progressive.lean:apt_lakatos_complete` 4-component bijection)
> - **RefinementGate (PH4)** = Lakatos protective belt adjustment + Hegel Aufhebung (`APT_Hegel_Aufhebung.lean:apt_full_aufhebung_coverage` cancel/preserve/elevate)
> - **FulfillmentGate 13/13 (PH5)** = Lakatos progressive shift + Friston gate decision + Beck TDD GREEN (`APT_Lakatos_Progressive.lean:apt_cycle_progressive` PROM 16 0.81 PASS + `APT_Friston_FEP.lean:low_prediction_error_implies_pass` + `APT_TDD_Beck_RGR.lean:green_phase_all_pass`)
> - **Adversarial Round (PH5)** = Goodfellow GAN-D + Pirsig LensSet UNION + Bacchelli-Bird V15 (`APT_Adversarial_Triple.lean:apt_v17_review_valid` + `apt_taliban_lens_134` + `mode_collapse_no_refutation`)
> - **OODA tempo (all gates)** = Boyd 1976 + APT v17 SLA (`APT_OODA_Boyd.lean:apt_ooda_production_bound = 390s` v17 SLA upper bound)
> - **All gates ground truth** = Curry-Howard cargo test = proof check (`APT_Curry_Howard.lean:cargo_pass_implies_proof`)
>
> Gate 가 *왜* 그 위치에서 trigger 되는가의 학문 grounding.

### Gate trigger = Lakatos progressive vs degenerating decision point

| Lakatos component | APT gate | trigger |
|---|---|---|
| **Hard core protection** | Contract v2 9-axis violation | refutation 시 cycle abort (RGR cleanup) |
| **Protective belt adjustment** | SP decomposition revision | C(S) 5-predicate fail → 재분해 (auxiliary hypothesis 변형) |
| **Positive heuristic** | Phase 6 Cleanup ratchet (5-tier) | LOC ratchet / cyclomatic complexity / dependency cycle / dead code / module boundary 향상 방향 |
| **Negative heuristic** | Hard Rules HR1-HR19 | 19 :AptErrorPattern - 절대 위반 금지 |
| **Progressive shift detection** | Step 6 ensemble VR coverage 0.83 + Lakatos test 4/4 | testable consequence 추가 시 PASS |
| **Degenerating shift detection** | ad-hoc rescue 검출 | rescue without testable consequence → ALERT |

### Friston Free Energy Principle ↔ Gate as prediction error minimization

```
gate_trigger(span)
  = | predicted_state(span) - actual_state(span) |
  = prediction_error 측정
  
  if prediction_error < threshold: GATE_PASS (free energy minimal)
  if prediction_error > threshold: GATE_BLOCK (high surprise → re-prediction needed)
```

**Friston 함의**: APT gate 가 *active inference* loop 의 inference step. predictionError 가 free energy 측정 — gate 통과 = 자기-조직 system 의 free energy 최소화.

### Hegel Aufhebung ↔ Gate transition = synthesis

| Hegel | APT gate transition |
|---|---|
| thesis | gate 진입 시 span 의 "이렇게 만든다" |
| antithesis | gate critic (Naesengmoon LensSet) 의 "정말?" |
| synthesis | gate PASS verdict — thesis + antithesis 통합 |

**Hegel 함의**: gate fail = synthesis 미도달 → cycle 재진행 (paralysis-by-analysis 회피). gate PASS = Aufhebung (지양 — 폐기 + 보존 + 격상 동시).

### Kolmogorov + MDL ↔ Gate 의 information-theoretic basis

| Kolmogorov | APT gate |
|---|---|
| K(span) > MDL_threshold | LOC ratchet trigger (vibe_coding_sweet 200-500 outside = K(content) explosion) |
| K(structure) > sub_threshold | dependency cycle detect (K(structure) explosion) |
| K(content | structure) > sub_threshold | duplication detect (Lizard / vulture) |

**Kolmogorov 함의**: APT gate threshold = MDL minimum 부근. Lean APT_AtomicSpan_MDL `mdl_minimum_at_sweet` theorem PASS — Sweet (200-500 LOC) ⇒ MDL ≤ 600 formal proof.

### Per-AtomicSpan v0.8-A1 gate = 진정한 progressive enforcement

**Quote** (PROM 16 결과): "13/13 active production PASS at 0.81 ensemble UNION coverage" — *PRECONDITION_FULLY_MET* 정전. gate 가 *방법론 자체에 적용* 되는 자기-검증 (M(M) self-application).

KG: `apt-philosophical-quadruple-canonical-2026-05-11` (Aristotle + Hegel + Lakatos + Friston) + `lean-apt-atomic-span-mdl-2026-05-11` (7 theorems Kolmogorov + Solomonoff + MDL formal)

---
