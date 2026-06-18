# apt — Validation

> **Lazy-load reference for `apt` skill.**
> Loaded *only when* the orchestrator enters the relevant phase/gate.
> Parent skill: [`../SKILL.md`](../SKILL.md). Repo CHANGELOG: [`../../CHANGELOG.md`](../../CHANGELOG.md).
> Refactor source: PROM 16 F6.1 Progressive Disclosure (2026-04-29).
> KG: `lesson-prom16-skillver-progressive-disclosure-drift-2026-04-29`.

---

## 10. Validation Commands (V1-V29)

### 10.1 Axiom Checks (P1 -- Critical)

| V# | Target | What It Checks |
|----|--------|---------------|
| V1 | A1: ContractOnlyAtST | Contract owner is SemanticTwin |
| V2 | A3: SiblingIndependence | No DEPENDS_ON between siblings |
| V5 | A4: FrontierUniqueness | CRYSTALLIZES_TO is sole SP->ST bridge |
| V6 | Cycle Detection | No cycles in DECOMPOSES_TO |
| V15 | Self-Approval | executor != reviewer |

### 10.2 Structural Checks (P2-P3)

| V# | Target | What It Checks | Severity |
|----|--------|---------------|:--------:|
| V3 | A2: BranchingFactor | Non-atomic Spans have >= 2 children | P2 |
| V4 | A2: Termination | All leaves are AtomicSpan | P3 |
| V7 | Injective CRYSTALLIZES_TO | 1 AtomicSpan -> 1 Twin | P2 |
| V8 | Functional HAS_CONTRACT | 1 Twin -> 1 Contract | P2 |
| V9 | Label Disjointness | No forbidden label combos | P2 |
| V10 | Duplicate Twin Names | Twin names are unique | P2 |
| V11 | Null Status | All core nodes have status | P3 |
| V12 | Orphan Contract | All Contracts owned by a Twin | P3 |
| V13 | Chain Completeness | atoms = twins = contracts | P2 |
| V14 | Hub Integrity | CrystallizationEvent has atom role | P3 |
| V16 | Sparse Links | INFORMED_BY >= 5 | P4 |
| V17 | Stale Lock | No locks held > 1 hour | P3 |

### 10.3 Parallel Execution Checks (P1-P3)

| V# | Target | What It Checks | Severity |
|----|--------|---------------|:--------:|
| V18 | Duplicate SharedType | No duplicate SharedType nodes | P1 |
| V19 | Orphan SharedType | All SharedTypes referenced | P3 |
| V20 | Producer without consumer | Every OUTPUTS_TYPE has matching INPUTS_TYPE | P2 |

### 10.4 Adversarial Validation Checks (v17 -- P1)

| V# | Target | What It Checks | Severity |
|----|--------|---------------|:--------:|
| V27 | Foundational Density | source_types >= 3, foundation:composite >= 2:1 | P1 |
| V28 | Adversarial Round Completion | Every gate passage has an adversarial round | P1 |
| V29 | Ground Truth Primacy | No unresolved ground-truth-testable findings | P1 |

### 10.5 V28: Adversarial Round Completion Query

```cypher
// V28: Every gate passage must have an adversarial round
MATCH (s:AptSpan)
WHERE s.status IN ['crystallized', 'fulfilled']
  AND NOT EXISTS {
    MATCH (s)<-[:TARGETS]-(dl:AptDecisionLog)
    WHERE dl.gate_type IN ['C_S_sigma', 'RefinementGate', 'FulfillmentGate']
      AND dl.adversarial_verdict IS NOT NULL
  }
RETURN s.name AS span_missing_adversarial,
  s.status AS current_status,
  "v17 VIOLATION: gate passed without adversarial round" AS reason
```

### 10.6 V29: Ground Truth Primacy Query

```cypher
// V29: No unresolved ground-truth-testable findings
MATCH (fb:AptFeedback)
WHERE fb.ground_truth_testable = true
  AND fb.ground_truth_result IS NULL
  AND fb.status <> 'resolved'
  AND fb.severity IN ['BLOCKER', 'PERFORMANCE']
RETURN fb.name AS finding,
  fb.gate_type AS gate,
  fb.description AS untested_claim,
  "v17 VIOLATION: ground-truth-testable finding not verified" AS reason
```

### 10.7 Quick Health Check

Run V1, V2, V5, V6, V15, V28, V29 (all P1 severity). These are the minimum checks.

Full query definitions for V1-V20: see `references/apt_reference.md` (SS31).

---



## 24. Events (v17)

| Event | Payload | When |
|-------|---------|------|
| SpanDecomposed | `{span, children, executor}` | After SP decomposition |
| CrystallizationCompleted | `{atom, twin, contract, hub}` | After ST crystallization |
| FulfillmentCompleted | `{contract, source, tests}` | After SCW implementation |
| FeedbackCreated | `{feedback, category, severity}` | When feedback recorded |
| **AdversarialRoundCompleted** | `{gate, span, critic_model, findings_count, blockers, verdict, ground_truth_pass}` | After each adversarial round |
| **GroundTruthOverride** | `{finding_id, gate, original_severity, ground_truth_result, action}` | When ground truth contradicts/confirms critic |
| **GateDecisionLogged** | `{decision_log_id, gate_type, decision, decided_by}` | After every gate decision logged to KG |

---



## 25. Clarifications (v17)

| # | Clarification |
|---|--------------|
| C36 | Adversarial rounds are not code review. They challenge assumptions and completeness. Both may occur. |
| C37 | Ground truth primacy does NOT apply to design decisions. sigma_oracle is supreme for design. |
| C38 | The critic agent is not an enemy. Adversarial = structured opposition, not hostility. |
| C39 | Lite Mode uses self-critique with full D22.3 template. Weaker but still required. |
| C40 | Foundation:composite ratio is per-Span, not per-KG. |
| **C41** | **v17: allow_agent_sigma: false is LOCKED. No configuration can change this. Agent cannot self-approve.** |
| **C42** | **v17: Every gate transition creates an AptDecisionLog node. No silent transitions allowed.** |
| **C43** | **v17: If adversarial critic returns < 3 findings, it is re-run with escalated prompt before proceeding.** |
| **C44** | **v17: Override of any HARD RULE requires explicit human reason logged in KG. Agent cannot generate the reason.** |

---



## 26. Project-Specific Invariants

Each SemanticAnchor may define domain invariants:
```cypher
MATCH (sa:SemanticAnchor {name: $project})-[:HAS_INVARIANT]->(inv)
RETURN inv.name, inv.description, inv.check_query
```

---

## 27. Validation Philosophical Grounding (2026-05-11 추가)

> Cross-ref: `THEORY/APT/PHILOSOPHICAL_FOUNDATIONS.md` §9 (Gödel + Tarski + Hofstadter 한계) + APT_Cycle_Functor.lean (`apt_self_application_bounded` PASS Russell+max_depth=1) + `gongri-set-theory-foundation-quintuple-canonical-2026-05-11`.
> **iter 103 갱신**: 17 APT Lean files / 156 theorems Mathlib-free 0 sorry — 9-tier architecture. Per-validation-source explicit Lean theorem cite (5 external verdict source ensemble formal):
> - **Source 1: Naesengmoon LensSet UNION** (constitutional 9 / mathematical 113 / solid 5 / longinus 7 = 134 axes) → `APT_Adversarial_Triple.lean:apt_taliban_lens_134` + `coverage_81_meets_precondition` (PROM 16 PRECONDITION_FULLY_MET threshold)
> - **Source 2: Ground Truth (compiler/test)** → `APT_Curry_Howard.lean:cargo_pass_implies_proof` (Curry-Howard cargo test = proof check) + `APT_TDD_Beck_RGR.lean:green_phase_all_pass` (Beck GREEN phase invariant)
> - **Source 3: HUMAN sigma_oracle (allow_agent_sigma=false LOCKED)** → `APT_Adversarial_Triple.lean:apt_v17_review_valid` (V15 + Bacchelli-Bird mandatory)
> - **Source 4: Lakatos external evidence (testable consequence + corroboration)** → `APT_Lakatos_Progressive.lean:apt_cycle_progressive` (PROM 16 0.81 corroboration PASS) + `pure_ad_hoc_is_degenerating` + `strong_consequence_is_progressive`
> - **Source 5: Lean Mathlib-free 0 sorry exit 0** → `APT_Curry_Howard.lean:exit_zero_no_sorry_implies_proven` (lean exit 0 + 0 sorry = proven proposition)
> - **Tarski metalanguage requirement** → `APT_Tarski_Metalanguage.lean:apt_tarski_compliant` + `apt_has_metalanguage` + `five_sources_pairwise_distinct`
> - **5-source ensemble complete** → `APT_Tarski_Metalanguage.lean:apt_v17_ensemble_complete` (formal cardinality + completeness)
>
> Validation 가 *왜* 외부 verdict 의존인지 학문 grounding.

### Tarski 1936 Undefinability ↔ 자기 truth 정의 ✗

```
APT 가 자기 자신의 *truth predicate* 정의 시도 → Tarski 정전 위반:
  - object language (APT methodology) cannot define its own truth predicate
  - metalanguage (외부 verdict) mandatory
  
∴ APT validation = *외부 verdict ensemble* 정전 mandatory
```

**3 외부 verdict source** (Tarski 회피 mechanism):
1. **Naesengmoon LensSet UNION** (constitutional 9 / mathematical 113 / solid 5 / longinus 7) — adversarial validation
2. **Lakatos external evidence** — testable consequence + corroboration ratio
3. **사용자 sigma_oracle** — HUMAN HARD LOCK (allow_agent_sigma: false LOCKED in v17)

### Gödel 1931 Incompleteness ↔ APT consistency 증명 ✗

```
APT 가 자기 자신의 *consistency* 증명 시도 → Gödel 1st incompleteness 위반:
  - sufficiently expressive system cannot prove its own consistency
  
대안: Lean 4 형식화 (Mathlib-free 0 sorry) → *partial* consistency only
  - 25+ Lean files: APT_Cycle_Functor.lean (9) + APT_AtomicSpan_MDL.lean (7) + Harness 3 + 12사도 7 등
  - Total 16+ APT-측 verified theorems = bounded consistency proof
```

### Hofstadter 1979 Strange Loop ↔ M(M) self-application 한계

```
APT 가 자기 자신을 meta-tier 에서 봄 = strange loop (recognized)
  
SYMPOSIUM 응답:
  - max_depth=1 invariant (`apt_self_application_bounded` Lean PASS)
  - Russell paradox 회피 (BHGMAN/harness/ 빈 폴더 = canonical instance)
  - apt-meta-review self_application_forbidden (recursive APT(APT(APT)) ✗)
```

### Validation = 외부 verdict ensemble 의 정전적 mechanism

| validation source | role | grounding |
|---|---|---|
| Naesengmoon LensSet UNION | adversarial 9-113 lens UNION coverage | Pirsig 1991 holistic + Goodfellow 2014 GAN-D |
| Ground Truth (compiler/test) | mechanical verification | Curry-Howard 1934/1969 (proposition-as-type) |
| HUMAN sigma_oracle | irreducible verdict | Tarski undefinability 회피 mandatory |
| Lakatos external evidence | progressive vs degenerating | Lakatos 1970 + apt-hardening-master-plan-2026-05-06 PROGRESSIVE_CONFIRMED 4/4 |
| Lean PASS | partial formal verification | Curry-Howard + Mathlib-free 0 sorry |

**핵심**: APT validation = *완전 ✗* (Gödel + Tarski + Hofstadter 한계). 5 external verdict source ensemble 만 progressive bounded validation 가능.

KG: `gongri-set-theory-foundation-quintuple-canonical-2026-05-11` (Cantor + Russell-Whitehead + Zermelo + Gödel + Tarski 5-canonical) + `apt-philosophical-foundations-2026-05-11` §9

---
