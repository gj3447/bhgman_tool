# apt — Quick Ref

> **Lazy-load reference for `apt` skill.**
> Loaded *only when* the orchestrator enters the relevant phase/gate.
> Parent skill: [`../SKILL.md`](../SKILL.md). Repo CHANGELOG: [`../../CHANGELOG.md`](../../CHANGELOG.md).
> Refactor source: PROM 16 F6.1 Progressive Disclosure (2026-04-29).
> KG: `lesson-prom16-skillver-progressive-disclosure-drift-2026-04-29`.

---

## 16. Auto Mode (Restricted in v17)

Auto Mode is available but with MANDATORY adversarial gates at every transition.
sigma_oracle is STILL HUMAN even in auto mode -- the agent handles KAL, decomposition,
and ground truth automatically, but BLOCKS at each sigma_oracle checkpoint.

### 16.1 Auto Mode Algorithm (v17 Modified)

```
ALGORITHM AutoMode_v17(project_name, description):
  // PH1-PH2: SA
  INVOKE /apt-sa with {project_name, description}
  WAIT for SA + RootSpan creation

  // PH3-PH6: Loop until all spans materialized
  WHILE true:
    unfinished = QUERY all non-materialized AtomicSpans
    IF unfinished is empty: BREAK

    FOR EACH span IN unfinished (parallel, max 4):
      phase = detect_phase(span)

      IF phase = 'PH3':
        // v17: Density check FIRST
        density = DensityCheck(span)
        IF NOT density.pass: AUTO_KAL(span)  // automatic
        // Decompose
        INVOKE /apt-sp with {span}
        // v17: Adversarial round (automatic)
        critic = AdversarialRound(decomposition, "C_S_sigma")
        // v17: BLOCK for human sigma_oracle
        PRESENT {proposal, critic.findings, ground_truth} to HUMAN
        WAIT for HUMAN response  // CANNOT SKIP

      ELIF phase = 'PH4':
        INVOKE /apt-st with {span}
        // v17: Adversarial round
        critic = AdversarialRound(contract, "RefinementGate")
        PRESENT to HUMAN
        WAIT for HUMAN response

      ELIF phase = 'PH5':
        INVOKE /apt-scw with {span}
        // v17: Ground truth FIRST
        RUN cargo test -- MUST PASS
        // v17: Adversarial round
        critic = AdversarialRound(code, "FulfillmentGate")
        PRESENT to HUMAN
        WAIT for HUMAN response

      ELIF phase = 'PH6':
        feedback = get_feedback(span)
        IF feedback.returns < max_returns_per_span:
          route_feedback(feedback)
        ELSE:
          PAUSE "Max returns reached. Human review needed."

    // Validate after each round
    violations = RUN V1-V6 + V28 + V29
    IF violations > 0: PAUSE "Violation detected."

  // Final validation
  RUN V1-V29 (full health check)
  RETURN "All spans materialized. Project complete."
```

### 16.2 When to Use Auto Mode

| Scenario | Auto Mode? | Why |
|----------|:----------:|-----|
| Simple project (CRUD, CLI) | Maybe | Human sigma still required at every gate |
| Tutorial / Hello World | Maybe | Lower risk but gates still enforced |
| Complex domain project | No | Manual control recommended |
| Production-critical | No | Full manual mode essential |

### 16.3 Guardrails

- V1-V6 + V28 + V29 axiom checks after every round
- max_returns_per_span prevents infinite feedback loops
- sigma_auto still runs even in auto mode
- PAUSE on axiom violation -> human must resolve before continuing
- sigma_oracle is ALWAYS HUMAN even in auto mode (HR2)

---



## 20. Quick Reference -- Decision Tree

```
"I need to..."
    |
    +-- "...start a new project"
    |       -> /apt-sa (create SemanticAnchor, bootstrap context)
    |
    +-- "...break down a feature"
    |       -> /apt-sp (density check -> decompose -> adversarial -> sigma_oracle)
    |
    +-- "...write a contract/spec"
    |       -> /apt-st (crystallize -> adversarial -> sigma_oracle)
    |
    +-- "...implement code"
    |       -> /apt-scw (TDD -> cargo test -> adversarial -> sigma_oracle)
    |
    +-- "...check APT compliance"
    |       -> /apt (run V1-V29 including V28/V29 adversarial checks)
    |
    +-- "...find what phase I'm in"
    |       -> /apt (phase detection query, Section 2)
    |
    +-- "...report a problem"
    |       -> /apt (feedback system, Section 14)
    |
    +-- "...see adversarial history"
    |       -> /apt (decision audit trail query, Section 8.5)
    |
    +-- "...override a gate"
    |       -> HUMAN must provide reason. Logged as AptDecisionLog (Section 8.3)
    |
    +-- "...understand the methodology"
    |       -> Read references/apt_core.md
    |
    +-- "...check infrastructure setup"
    |       -> Read references/apt_infra.md
    |
    +-- "...see validation details"
            -> Read references/apt_reference.md
```

---



## 21. When to Use Each Skill

| Situation | Skill | Why |
|-----------|-------|-----|
| New project / no SA | `/apt-sa` | Bootstrap identity first |
| "Implement feature X" (unknown phase) | `/apt` -> detect phase -> delegate | Don't assume phase |
| "Plan the architecture for Y" | `/apt-sp` directly | Clearly SP work |
| "Write the contract for Z" | `/apt-st` directly | Clearly ST work |
| "Code the function for W" | `/apt-scw` directly | Clearly SCW work |
| "Check APT compliance" | `/apt` validation | Run V1-V29 |
| "Where does this feature go?" | `/apt` + KG query | Phase detection |
| "Audit the KG" | `/apt` validation | Full health check |
| "What phase am I in?" | `/apt` phase detection | Per-branch detection |
| "Review adversarial history" | `/apt` + Section 8.5 query | Decision audit trail |

---



## 22. Core Concepts Summary

### 22.1 Axioms (violation = not APT)

- **A1: ContractOnlyAtST** -- Contracts owned only by SemanticTwin
- **A2: RecursiveDecomposition + Termination** -- min 2 children, all paths end at AtomicSpan
- **A3: SiblingIndependence** -- no DEPENDS_ON between siblings
- **A4: CrystallizationFrontierUniqueness** -- CRYSTALLIZES_TO is the sole SP->ST bridge

### 22.2 Key Design Principles (D1-D24)

| Principle | Description |
|-----------|-------------|
| D1 | HyperedgeHub -- CrystallizationEvent as bipartite incidence hub |
| D3 | TaskAsScaffolding -- Task (NL) != Contract (formal spec) |
| D4 | DenseBeforeContract -- links(S) >= 5 before crystallization |
| D5 | SingleFileProjection -- AtomicSpan -> 1 file <= 500 lines |
| D9 | GenerativeFlowOrdering -- SA->SP->ST->SCW forward; reverse for Bottom-Up Ascent |
| D10 | NFR as First-Class -- latency, memory, accuracy in Contract nfr_* fields |
| D11 | KnowledgeAcquisitionLoop -- auto-search KG + web before decomposition |
| D12 | ParallelExecution -- sibling parallel, parent-child sequential |
| D14 | OneTypeOneNode -- one SharedType = one KG node |
| D15 | ParentDefinesInterfaceTypes -- parent defines boundary types before children ST |
| D16 | SequencingFromSharedType -- SEQUENCED_WITH auto-derived from types |
| D17 | SA as Index -- SA connected to everything, retroactive OK |
| **D20** | **AdversarialValidation -- every gate includes adversarial round** |
| **D21** | **FoundationalDensityPrinciple -- source diversity + foundation:composite ratio** |
| **D22** | **AdversarialCriticAgent -- model separation + anti-rubber-stamp** |
| **D23** | **GroundTruthPrimacy -- compiler > agent > intuition for facts** |
| **D24** | **GAN-ContextAnalogy -- theoretical foundation for adversarial layer** |

### 22.3 Crystallization Predicate C(S)

C(S) = v AND tau AND iota AND delta AND sigma (ALL must pass, cheap rejection first)

### 22.4 KG Reference Convention

All code files MUST include:
```
# KG: TASK_xxx -- links to SemanticTask node
# KG: CT_xxx -- links to AptContract node
```

---

## 23. Quick Reference Philosophical Index (2026-05-11 추가)

> Cross-ref: `THEORY/APT/PHILOSOPHICAL_FOUNDATIONS.md` (11 axes 4-layer integration) + `THEORY/APT/COMPARISON_METHODOLOGIES.md` (5 methodology compare) + `apt-philosophical-quadruple-canonical-2026-05-11` (4-canonical hyperedge).
> **iter 107 갱신**: 17 APT Lean files / 156 theorems Mathlib-free 0 sorry — 9-tier architecture (1 FOUNDATIONAL + 4 explicit canonical + 6 sub-axis + 1 CAPSTONE + 2 ENGINEERING + 1 LIMIT + 1 CROSS-CANON + 1 META). 모든 학문 정전 mapping 이 *formal Lean evidence* 보유 — references files 마다 explicit per-mechanism Lean theorem cite (phases.md §12 / gates.md §24 / validation.md §27 / kg_logging.md §15 / error_handling.md §14 / adversarial.md §16). Quick reference 의 *1줄 mapping* 들이 모두 Lean PASS 정전과 1:1 대응.
>
> Phase / Gate / Validation / Error / Adversarial 의 학문 정전 1줄 mapping.

### APT 7-Phase ↔ Aristotle 4 causes (Lean PASS `apt_aristotle_complete` + Hegel Lean PASS `hegel_spiral_returns`)

| APT phase | Aristotle cause | role |
|---|---|---|
| **PH1 SemanticAnchor (SA)** | Material (Hyle) | substrate — what is to be made |
| **PH2 SemanticPyramid (SP)** | Formal (Eidos) | shape decomposition |
| **PH3 SemanticTwin (ST)** | Formal (Eidos) | crystallized contract form |
| **PH4 SourceCodeWorld (SCW)** | Efficient (Kinoun) | execution agent (TDD) |
| **PH5 Validation** | Final (Telos) | telos / fulfillment verification |
| **PH6 MetaReview** | Meta (Reflexive) | self-application max_depth=1 |
| **PH7 Cleanup** | Meta (Reflexive) | system reset for next cycle |

### APT Gate ↔ Lakatos research programme (Lean PASS `apt_cycle_lakatos_progressive` + dedicated `apt_cycle_progressive` PROM 16 0.81 PASS in APT_Lakatos_Progressive.lean)

| Gate | Lakatos role | trigger |
|---|---|---|
| DensityCheck | positive heuristic | INFORMED_BY ≥ 5 + sources ≥ 3 |
| C(S)_sigma | hard core protection | Contract v2 9-axis violation = abort |
| RefinementGate | protective belt | C(S) 5-predicate fail = re-decompose |
| FulfillmentGate 13/13 | progressive shift | testable consequence + Lean PASS |
| MetaReview | rescue detection | ad-hoc rescue without testable consequence ✗ |
| Cleanup ratchet | positive heuristic | LOC / cyclomatic / cycle / dead code / module 향상 방향 |

### APT Validation ↔ Tarski + Gödel + Hofstadter (limit acknowledgement)

| limit | APT response |
|---|---|
| Tarski undefinability | 5 external verdict source ensemble (Taliban + Ground Truth + HUMAN + Lakatos external + Lean) |
| Gödel incompleteness | partial consistency only — **20 APT Lean files / 179 theorems Mathlib-free 0 sorry** (iter 31 4-canonical milestone + iter 47 CAPSTONE meta-integration with Lakatos defense in depth claim resistance = 4 + iter 55 FOUNDATIONAL Curry-Howard meta-theorem + iter 62 ENGINEERING #1 Beck TDD RGR = APT SCW PH4 + iter 70 ENGINEERING #2 Evans DDD + Conway 1968 = APT SP PH3 semantic + iter 77 LIMIT Tarski 1936 metalanguage = honest limitation acknowledgement + iter 85 CROSS-CANON Goodfellow + Pirsig + Bacchelli-Bird = producer-reviewer-triple-canonical hyperedge formal + iter 93 META-ARCHITECTURE Architecture Master meta-meta proof + iter 109 ENGINEERING #3 Wirth 1971 stepwise refinement = APT SP PH3 algorithmic instance + iter 117 METAPHYSICAL Plato Phaedo eidos + Frege Begriffsschrift = APT ST PH3 metaphysical grounding + Aristotle Formal 3-sibling cluster + iter 125 META v2 update Architecture Master v2 = v1 16/149 → v2 19/172 progression formal proof) |
| Hofstadter strange loop | max_depth=1 invariant (Lean PASS `apt_self_application_bounded`) |

### APT Error Handling ↔ Hegel Aufhebung + Maturana autopoiesis

| concept | APT mechanism |
|---|---|
| Aufhebung (지양) | Lesson `wrongAssumption ↔ truth` symmetric pair (폐기 + 보존 + 격상) |
| autopoiesis | Lesson → Pattern Library extension (self-organization closure) |
| anti-PRELIMINARY-inflation | file_change_ratio mandatory + ALERT halt < 0.5 in 5 iter |

### APT KG Logging ↔ Friston FEP + W3C PROV-DM

| concept | APT mechanism |
|---|---|
| Friston active inference | KG = prior update mechanism (prediction error → Bayesian update) |
| W3C PROV-DM 6 relations | wasGeneratedBy / used / wasInformedBy / wasAttributedTo / wasAssociatedWith / actedOnBehalfOf |
| Tarski metalanguage | KG = APT 의 외부 truth predicate (`:ValidationResult` + `:Lesson` 정전화) |

### APT Adversarial ↔ Goodfellow GAN-D + Pirsig + Whitehead + Bacchelli-Bird

| concept | APT mechanism |
|---|---|
| Goodfellow minimax | Producer-Critic adversarial = Lakatos progressive equilibrium |
| Pirsig Lila holistic | LensSet UNION (constitutional 9 + mathematical 113 + solid 5 + longinus 7) |
| Whitehead concrescence | finding ensemble → verdict synthesis (actual occasion satisfaction) |
| Bacchelli-Bird MSR | executor != reviewer (V15 + allow_agent_sigma: false LOCKED) |

### APT 4-Canonical Cross-Canon Hyperedge

> `apt-philosophical-quadruple-canonical-2026-05-11` (:Hyperedge:CrossCanonGrounding):
>   1. **Aristotle 4 causes** (Material/Formal/Efficient/Final) → APT 7-phase mapping
>   2. **Hegel 1807 Phänomenologie** (Aufhebung 자가운동) → APT cycle progressive
>   3. **Lakatos 1970 research programme** (hard core + protective belt) → APT gate hierarchy
>   4. **Friston 2010 FEP** (active inference) → APT KG logging Bayesian update
>
> ⇒ APT methodology = 4 정전 합치점의 산업 instantiation. (Lean **20 APT files / 179 theorems Mathlib-free 0 sorry / lean exit 0**: APT_Cycle_Functor (9 Aristotle) + APT_Hegel_Aufhebung (12 Hegel) + APT_Lakatos_Progressive (9 Lakatos) + APT_Friston_FEP (8 Friston) + APT_AtomicSpan_MDL (7 Kolmogorov+Solomonoff) + APT_TPA_Dual (9 Mac Lane) + APT_MetaReview_Bounded (14 Russell+Lawvere+Yanofsky+Hofstadter) + APT_OODA_Boyd (9 Boyd) + APT_Maturana_Autopoiesis (8 Maturana sub-axis) + APT_Whitehead_Concrescence (10 Whitehead sub-axis) + APT_Quadruple_Canonical_Integration (8 CAPSTONE meta-integration with Lakatos defense in depth) + APT_Curry_Howard (7 FOUNDATIONAL meta-theorem — proposition↔type underlies all) + APT_TDD_Beck_RGR (11 ENGINEERING #1 — Beck 2003 RGR = APT SCW PH4 instance) + APT_DDD_Conway_BoundedContext (11 ENGINEERING #2 — Evans DDD + Conway 1968 = APT SP PH3 semantic instance) + APT_Tarski_Metalanguage (8 LIMIT constraint — Tarski 1936 undefinability + KG metalanguage + 5 verdict source ensemble) + APT_Adversarial_Triple (9 CROSS-CANON grounding — Goodfellow GAN + Pirsig Lila + Bacchelli-Bird MSR = producer-reviewer-triple-canonical hyperedge formal) + APT_Architecture_Master (7 META v1 proof — meta-meta level entire 16-Lean structure formally well-formed) + APT_Wirth_StepwiseRefinement (9 ENGINEERING #3 — Wirth 1971 stepwise refinement = APT SP PH3 algorithmic instance, sibling DDD Bounded Context) + APT_Plato_Frege_Eidos (7 METAPHYSICAL sub-axis — Plato Phaedo eidos + Frege Begriffsschrift = APT ST PH3 metaphysical grounding, 3-sibling Aristotle Formal cluster: DDD/Wirth/Plato-Frege) + **APT_Architecture_Master_v2 (7 META v2 update — v1 16/149 frozen iter 93 → v2 19/172 iter 125 progression formal proof)**)

KG: `apt-philosophical-quadruple-canonical-2026-05-11` + `apt-philosophical-foundations-2026-05-11` + `apt-comparison-methodologies-2026-05-11` + `lean-apt-cycle-functor-2026-05-11` + `lean-apt-atomic-span-mdl-2026-05-11`

---
