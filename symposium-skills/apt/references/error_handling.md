# apt — Error Handling

> **Lazy-load reference for `apt` skill.**
> Loaded *only when* the orchestrator enters the relevant phase/gate.
> Parent skill: [`../SKILL.md`](../SKILL.md). Repo CHANGELOG: [`../../CHANGELOG.md`](../../CHANGELOG.md).
> Refactor source: PROM 16 F6.1 Progressive Disclosure (2026-04-29).
> KG: `lesson-prom16-skillver-progressive-disclosure-drift-2026-04-29`.

---

## 9. Error Handling

### 9.1 When Critic Disagrees with Design Agent

```
IF critic verdict = REJECT (>= 1 BLOCKER):
  1. Design agent reviews BLOCKER findings
  2. For ground_truth_testable findings: run ground truth command
     - If ground truth CONFIRMS: fix the issue, re-submit
     - If ground truth CONTRADICTS: finding dismissed (log override)
  3. For non-testable findings: present to sigma_oracle with both perspectives
  4. sigma_oracle decides: fix it | dismiss with reason | escalate
  5. Log decision as AptDecisionLog

IF critic verdict = CONDITIONAL_PASS (PERFORMANCE findings):
  1. Design agent reviews PERFORMANCE findings
  2. Run benchmarks if applicable
  3. sigma_oracle decides: fix now | accept with tech debt | escalate
  4. Log decision

IF critic verdict = PASS (only DESIGN_DEBT + NITPICK):
  1. Log findings as tech debt
  2. Proceed to sigma_oracle for final approval
  3. sigma_oracle may still RETURN for any reason
```

### 9.2 When Ground Truth Fails

```
IF cargo test fails:
  1. BLOCK gate immediately
  2. Fix the failing tests
  3. Re-run cargo test
  4. Only proceed when ALL tests pass
  5. Re-run adversarial round (critic sees updated code)

IF cargo build fails:
  1. BLOCK gate immediately
  2. Fix compilation errors
  3. Re-run from step 1

IF WebSearch contradicts design decision:
  1. Log the contradiction as AptFeedback (severity: BLOCKER)
  2. Present to sigma_oracle with evidence
  3. sigma_oracle decides: change approach | accept with justification
```

### 9.3 When sigma_oracle Does Not Respond

```
IF sigma_oracle prompt sent and no response in current context:
  1. DO NOT PROCEED
  2. DO NOT auto-approve
  3. Re-state the question clearly
  4. List what needs approval:
     - The proposal summary
     - Critic findings (count + severities)
     - Ground truth results
  5. Wait for human response
  6. If conversation continues on different topic: remind about pending approval
```

### 9.4 When Adversarial Round Reaches Max Iterations

```
IF adversarial_rounds >= max_adversarial_rounds (3):
  1. Log all findings from all rounds
  2. Escalate to sigma_oracle with full history
  3. sigma_oracle decides:
     - APPROVE with remaining findings as accepted debt
     - RETURN to earlier phase (SP/ST)
     - ABORT the span entirely
  4. Log decision with all context
```

### 9.5 When KAL Cannot Satisfy Density Requirements

```
IF KAL runs 3+ times and density still not met:
  1. Log current state (what types are missing, what ratio is)
  2. Present to sigma_oracle:
     "Density requirements not met after 3 KAL iterations.
      Current: {count} links, {types} source types, {ratio} ratio.
      Required: 5 links, 3 types, 2:1 ratio.
      Options: (a) override with justification, (b) manual knowledge entry, (c) abort span"
  3. sigma_oracle decides
  4. Log decision as AptDecisionLog with override_reason if applicable
```

### 9.6 When Critic and Design Agent Both Wrong (Meta-Failure)

```
IF sigma_oracle detects both agents converged on wrong approach:
  1. sigma_oracle provides correction
  2. Log as AptFeedback category="FalseNegative" (validation missed real issue)
  3. Reset to earlier phase if needed
  4. Record in KG for future training (KG as persistent weight space -- D24)
  5. Consider rotating both models for next round
```

---



## 13. Parallel Execution (D12)

### 13.1 Five Rules

| Rule | Description |
|------|-------------|
| SameLayer | Same parent's children = all parallel (A3 guarantees independence) |
| ParentChild | Parent decomposition complete -> then children. Vertical = sequential. |
| CrossBranch | Independent branches may be in different phases simultaneously. |
| AtomicIndependent | Sibling becomes AtomicSpan -> proceeds to PH4 independently. |
| LayerGateFirst | All children created -> RefinementGate -> then descend. |

### 13.2 SharedType (D14-D16)

Parent Span defines boundary types shared between children BEFORE children enter ST.

```
(Parent)--DEFINES_SHARED_TYPE-->(World:SharedType)<--OUTPUTS_TYPE--(CT_WorldGen)
                                       ^
                              INPUTS_TYPE
                                       |
                                (CT_Renderer)
```

- One type = one node (D14). MERGE only.
- Parent defines first (D15). Children reference only.
- SEQUENCED_WITH auto-derived (D16). From OUTPUTS_TYPE -> INPUTS_TYPE pairs.

### 13.3 Visibility Scope (D13)

| Phase | Can See | Cannot See |
|-------|---------|-----------|
| SP decomposition | Parent description + sibling names | Sibling internals, other branches |
| ST crystallization | Self + parent + SharedType | Sibling Contract internals |
| SCW implementation | Self Contract + target_file | Sibling source code |
| Integration | Sibling input/output_type | Sibling internal logic |

### 13.4 Layer Gates

| Gate | When | On Fail |
|------|------|---------|
| LayerDecomposition | After all children created | Delete children + re-decompose |
| CrystallizationEntry | Before PH4 entry | Remove AtomicSpan + back to PH3 |
| ContractComplete | Before PH5 entry | Contract draft + /apt-st |
| Fulfillment | After PH5 implementation | Re-implement / back to PH4/PH3 |
| Integration | After all siblings complete | Contract modification or re-decompose |

**v17**: Each layer gate ALSO requires adversarial round completion (V28).

### 13.5 Parallel Validation (V18-V20)

| V# | Target | Severity |
|----|--------|:--------:|
| V18 | Duplicate SharedType | P1 |
| V19 | Orphan SharedType (no references) | P3 |
| V20 | Producer without consumer | P2 |

---

## 14. Error Handling Philosophical Grounding (2026-05-11 추가)

> Cross-ref: `THEORY/APT/PHILOSOPHICAL_FOUNDATIONS.md` §3 (Lakatos research programme) + §10 (Hegel Aufhebung) + APT_Cycle_Functor.lean (`apt_cycle_lakatos_progressive` PASS) + `lesson-midnight-preliminary-inflation-anti-pattern-2026-05-11`.
> **iter 105 갱신**: 17 APT Lean files / 156 theorems Mathlib-free 0 sorry — 9-tier architecture. Per-error-handling-mechanism explicit Lean theorem cite:
> - **Lakatos hard core protection** (refutation 시 program abort) → `APT_Lakatos_Progressive.lean:apt_lakatos_complete` 4-component bijection (hard core / belt / positive / negative heuristic)
> - **Lakatos protective belt adjustment** (auxiliary hypothesis 변형) → `APT_Lakatos_Progressive.lean:strong_consequence_is_progressive` (testable + corroboration ≥ 50)
> - **Lakatos ad-hoc rescue detection** (rescue without testable consequence ⇒ degenerating) → `APT_Lakatos_Progressive.lean:pure_ad_hoc_is_degenerating` 형식
> - **Hegel Aufhebung error→Lesson 격상** (cancel + preserve + elevate) → `APT_Hegel_Aufhebung.lean:apt_full_aufhebung_coverage` + `synthesis_preserves_valid` + `synthesis_cancels_invalid`
> - **Maturana autopoiesis self-organization** (Lesson → Pattern Library extension) → `APT_Maturana_Autopoiesis.lean:apt_full_autopoietic_coverage` (4 properties: self-org/self-maintenance/closure/coupling)
> - **Midnight PRELIMINARY inflation anti-pattern** (lesson-midnight-preliminary-inflation-anti-pattern-2026-05-11) → `APT_Lakatos_Progressive.lean:preliminary_inflation_violates_lakatos` (formal lesson) + `APT_Architecture_Master.lean:apt_completion_session_perfect` (이 session 자체 100% file_change_ratio + 0 PRELIMINARY 형식 증명)
> - **HR20 Anti-Theater (mode collapse)** → `APT_Lakatos_Progressive.lean:mode_collapse_implies_anti_theater` + `APT_Adversarial_Triple.lean:mode_collapse_no_refutation`
>
> Error handling 가 *왜* 단순 retry 가 아닌 progressive feedback loop 인지 학문 grounding.

### Lakatos progressive shift ↔ Error handling = research programme adjustment

```
APT error handling ≠ exception catch + retry
APT error handling = Lakatos protective belt adjustment:
  ┌────────────────────────────────────────┐
  │ error detected (refutation)            │
  │      ↓                                 │
  │ classify: hard core vs protective belt │
  │      ↓                                 │
  │ if hard core: PROGRAM_ABORT (degenerating)│
  │ if belt: AUXILIARY_HYPOTHESIS adjust    │
  │      ↓                                 │
  │ testable consequence 검증               │
  │      ↓                                 │
  │ Lesson 결정화 (KG MERGE)                │
  └────────────────────────────────────────┘
```

| Lakatos | APT error handling |
|---|---|
| **hard core refutation** | Contract v2 9-axis violation → cycle abort + cleanup |
| **protective belt adjustment** | SP decomposition revision, retry with new sub-task |
| **ad-hoc rescue detection** | rescue without testable consequence → ALERT halt |
| **progressive shift** | error → Lesson → 다음 cycle 의 정전 grounding 강화 |
| **degenerating shift** | 동일 error 반복 + ad-hoc rescue 누적 → research programme abandon |

### Hegel Aufhebung ↔ Error 의 Lesson 격상

| Hegel | APT error handling |
|---|---|
| thesis | initial assumption (executor의 wrongAssumption) |
| antithesis | external verdict (compiler/critic/사용자 truth) |
| synthesis | Lesson 결정화 (`wrongAssumption ↔ truth` symmetric pair) |

**Hegel 함의**: error 는 *negation* 이 아닌 *Aufhebung* — 폐기 + 보존 + 격상. wrongAssumption 자체도 KG 에 보존 (negative provenance) — 미래 동일 패턴 회피.

### Maturana-Varela autopoiesis ↔ Error self-correction = system 의 self-organization

> Maturana-Varela 1980 autopoiesis: 자기-조직 system = *자기 자신을 produce* 하는 cycle.

```
APT cycle = autopoietic system:
  - Lesson 생성 → 다음 cycle 의 Pattern Library extension
  - error 가 system 자기 self-organization 에 contribute
  - system 외부 input 만 의존 ✗ (closed under error feedback)
```

**Maturana 함의**: APT error handling 은 self-organizing — 실패가 자체 적응 mechanism (Lakatos hard core 보호).

### Anti-Pattern 정전: Midnight PRELIMINARY Inflation (2026-05-11 lesson)

> `lesson-midnight-preliminary-inflation-anti-pattern-2026-05-11` (HIGH severity) — autoloop "idle ✗" spec 만 으로 PRELIMINARY-only KG inflation 발생.

| anti-pattern | corrective action |
|---|---|
| autoloop firing 마다 file change ✗ | file_change_ratio mandatory 1차 metric |
| PRELIMINARY-only KG node 누적 | max 3 PRELIMINARY per iter |
| user verdict gate bypass | trigger condition 명시 mandatory |
| heretwork (헛작업) 패턴 | priority order: file change → cross-link → lesson closure |

ALERT halt threshold: **file_change_ratio < 0.5 in 5 consecutive iter** → cron auto-halt + Lesson generate.

KG: `apt-philosophical-quadruple-canonical-2026-05-11` (Aristotle + Hegel + Lakatos + Friston) + `lesson-midnight-preliminary-inflation-anti-pattern-2026-05-11`

---

---
