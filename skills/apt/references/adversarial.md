# apt — Adversarial

> **Lazy-load reference for `apt` skill.**
> Loaded *only when* the orchestrator enters the relevant phase/gate.
> Parent skill: [`../SKILL.md`](../SKILL.md). Repo CHANGELOG: [`../../CHANGELOG.md`](../../CHANGELOG.md).
> Refactor source: PROM 16 F6.1 Progressive Disclosure (2026-04-29).
> KG: `lesson-prom16-skillver-progressive-disclosure-drift-2026-04-29`.

---

## 7. Anti-Bypass Mechanisms

### 7.1 Detection Rules

| # | Bypass Attempt | Detection | Response |
|---|---------------|-----------|----------|
| 1 | Critic returns < 3 findings | Count check | Re-run with stronger prompt (Section 7.2) |
| 2 | Same model for design and critique | Model comparison | BLOCK -- switch critic model |
| 3 | No human response to sigma_oracle | Response check | BLOCK and re-ask. Never assume approval. |
| 4 | Agent tries to auto-approve sigma | Config check | BLOCKED by allow_agent_sigma: false |
| 5 | Gate transition without adversarial round | KG audit (V28) | BLOCK -- run adversarial round |
| 6 | Ground-truth-testable claim not tested | KG audit (V29) | BLOCK -- run ground truth command |
| 7 | Critic produces only NITPICK findings 5+ times | Severity distribution | Rotate critic model + alert |
| 8 | Design agent ignores PERFORMANCE findings | Diff comparison | Escalate to sigma_oracle |
| 9 | All findings dismissed by ground truth 3+ times | Override history | Review critic prompt for hallucination |
| 10 | sigma_oracle approves without reviewing findings | Cannot detect automatically | Include findings summary in approval prompt |

### 7.2 Stronger Prompt for Insufficient Findings

When the critic returns fewer than 3 findings, re-invoke with this escalated prompt:

```markdown
# ESCALATED ADVERSARIAL REVIEW

Your previous review produced only {N} findings. The minimum is 3.
This is NOT acceptable. You MUST find at least 3 issues.

Mandatory deep-dive checklist:
1. Re-read EVERY line of the artifact. What could go wrong at runtime?
2. What happens with EMPTY input? NULL input? MAXIMUM-SIZE input?
3. What concurrent access patterns could cause race conditions?
4. What happens if a DEPENDENCY changes its API?
5. What error handling is MISSING?
6. What SECURITY implications exist?
7. What PERFORMANCE characteristics are unverified?
8. Does this violate ANY APT axiom (A1-A4)?
9. Is every postcondition ACTUALLY TESTABLE with concrete assertions?
10. What would a HOSTILE code reviewer say about this?

You MUST produce at least 3 findings. If you still cannot, produce 3 NITPICK
findings with documented evidence of thorough review methodology.
```

### 7.3 Model Separation Enforcement

| Design Agent | Acceptable Critic | Rationale |
|-------------|------------------|-----------|
| opus | sonnet or haiku | Different weights = different biases |
| sonnet | haiku or opus | Cross-tier critique |
| Any model | Same model, different temperature | INSUFFICIENT -- same weights |
| Any model | Same model, different prompt only | INSUFFICIENT -- framing contagion |

**v17 enforcement**: Before spawning critic, check that critic_model != design_model.
If they match, BLOCK and log error.

**Lite Mode exception**: When only one model is available, the same model MAY serve as
critic but MUST use the full D22.3 template AND all anti-rubber-stamp techniques are
MANDATORY. This exception must be logged as AptDecisionLog with reason.

### 7.4 Anti-Rubber-Stamp Techniques (10)

| # | Technique | Mechanism | Detects |
|---|-----------|-----------|---------|
| 1 | Model separation | Different model weights | Confirmation bias contagion |
| 2 | Minimum finding count | Hard minimum of 3 | Lazy approval |
| 3 | Core assumption challenge | 1+ finding must target core assumption | Surface-only critique |
| 4 | Anti-checklist | 10-item checklist critic must address | Incomplete review |
| 5 | Falsifiability requirement | Every finding must be testable/verifiable | Vague handwaving |
| 6 | Ground truth cross-check | ground_truth_testable findings auto-verified | Phantom bugs |
| 7 | Severity distribution audit | >80% NITPICK across 5+ rounds = flag | Nitpick-only rubber-stamp |
| 8 | Historical finding rate | Track findings-per-round; alert if always 3 | Gaming the minimum |
| 9 | Blind review | Critic does not see previous sigma_oracle decisions | Anchoring to authority |
| 10 | Rotation | Critic model rotated after 5+ consecutive rounds | Adaptation/overfitting |

---



## 15. Mode Collapse Detection (D24)

### 15.1 Detection Signals

| Signal | Threshold | Action |
|--------|-----------|--------|
| Exactly 3 findings (minimum) for 5+ consecutive rounds | 5 rounds | Alert: critic may be rubber-stamping |
| Same NITPICK-only verdict for 3+ consecutive rounds | 3 rounds | Rotate critic model |
| Design agent does not modify artifact after PERFORMANCE findings | 2 rounds | Escalate to sigma_oracle |
| All findings dismissed by ground truth override | 3 rounds | Review critic prompt for hallucination |
| sigma_oracle approves without reading critic findings | 1 occurrence | Alert (meta-discriminator failure) |

### 15.2 The Human as Meta-Discriminator

sigma_oracle remains essential even with automated adversarial rounds. The adversarial system
can itself fail (both agents converge on a shared blind spot). The human detects meta-level
failures that no amount of automated adversarial rounds can catch.

This is why `allow_agent_sigma: false` is LOCKED in v17.

### 15.3 Context Window as Shared Weight Space

```
Session-scoped:  Context Window  <-->  GAN weights during one training run
Persistent:      Knowledge Graph  <-->  GAN weights saved to checkpoint

AdversarialRound findings --> KG:AptFeedback nodes
  = saving validated knowledge (like checkpoint saving)

Next session loads KG findings --> context
  = loading pretrained weights for continued training
```

---

## 16. Adversarial Round Philosophical Grounding (2026-05-11 추가)

> Cross-ref: `THEORY/APT/PHILOSOPHICAL_FOUNDATIONS.md` §6 (Friston FEP) + §7 (Whitehead actual occasion concrescence) + `producer-reviewer-triple-canonical-2026-05-10` + `THEORY/TALIBAN/SOURCES.md` (Goodfellow GAN-D + Pirsig holistic + Bacchelli-Bird empirical).
> **iter 106 갱신**: 17 APT Lean files / 156 theorems Mathlib-free 0 sorry — 9-tier architecture. **CROSS-CANON Lean grounding**: producer-reviewer-triple-canonical hyperedge 형식 증명 = `APT_Adversarial_Triple.lean` (234L, 9 theorems first-try PASS). Per-canon explicit Lean theorem cite:
> - **Goodfellow 2014 GAN-D minimax** (mode collapse anti-pattern detect) → `APT_Adversarial_Triple.lean:mode_collapse_no_refutation` + `APT_Lakatos_Progressive.lean:mode_collapse_implies_anti_theater` (HR20 dual proof)
> - **Pirsig 1991 Lila MoQ holistic synthesis** (LensSet UNION coverage) → `APT_Adversarial_Triple.lean:apt_taliban_lens_134` (constitutional 9 + math 113 + solid 5 + longinus 7 = 134 axes formal cardinality) + `coverage_81_meets_precondition` (PROM 16 PRECONDITION_FULLY_MET 81% threshold formal)
> - **Whitehead 1929 concrescence** (multiple prehensions → unified satisfaction) → `APT_Whitehead_Concrescence.lean:apt_adversarial_well_formed` (adversarial round = actual occasion instance) + `four_concrescence_components_distinct` + `concrescence_total_preserved`
> - **Bacchelli-Bird 2013 MSR empirical** (executor != reviewer) → `APT_Adversarial_Triple.lean:apt_v17_review_valid` + `same_agent_invalid` (V15 + allow_agent_sigma=false LOCKED formal)
> - **Cross-Canon Hyperedge formal** (3 canon convergence) → `APT_Adversarial_Triple.lean:producer_reviewer_hyperedge_complete` (4-property formal) + `three_canon_distinct` (3 canon contributions distinct)
> - **Multi-parent sub-axis** (Aristotle Final + Friston FEP combined) → `APT_Adversarial_Triple.lean:adversarial_multi_parent_sub_axis` (NOT separate canon — engineering instantiation)
>
> Adversarial round 가 *왜* 단일 critic 이 아닌 LensSet UNION ensemble 인지 학문 grounding.

### Goodfellow 2014 GAN-D ↔ APT critic = D in G/D minimax

```
APT (G producer) vs Critic (D adversarial):
  - G goal: contract fulfillment
  - D goal: failure mode discovery
  - Equilibrium: progressive shift (Lakatos)
  - Mode collapse 회피 mandatory:
      - 동일 finding 반복 ✗
      - exactly 3 NITPICK 반복 ✗ (v17 Anti-Theater detect)
      - severity distribution audit
```

| Goodfellow GAN-D | APT critic mechanism |
|---|---|
| **D objective**: maximize log D(real) + log(1−D(fake)) | Critic finding 다양성 maximize (LensSet UNION coverage) |
| **G objective**: minimize log(1−D(G(z))) | Producer contract 위반 회피 |
| **Mode collapse** | Anti-Theater (§14.3 V18) — exactly 3 NITPICK per round detect |
| **Nash equilibrium** | progressive shift — testable consequence 누적 |

### Pirsig 1991 Lila ↔ holistic synthesis = LensSet UNION coverage

> Pirsig 1974/1991 Metaphysics of Quality — 단일 lens ≠ truth, multiple lens UNION 만 holistic synthesis.

```
APT critic = Taliban LensSet UNION (4 sets):
  - constitutional 9-axis (정전 위반 detect)
  - mathematical 113-axis (formal property)
  - solid 5-axis (SRP/OCP/LSP/ISP/DIP)
  - longinus 7-axis (reference binding integrity)

UNION coverage ≥ 0.81 mandatory (PROM 16 PRECONDITION_FULLY_MET 정전)
```

**Pirsig 함의**: 단일 lens = static quality 만 capture, dynamic quality 누락. 4 LensSet UNION = static + dynamic 통합.

### Whitehead 1929 Concrescence ↔ Adversarial round = actual occasion 의 prehension

> Whitehead Process and Reality — actual occasion 은 *prehension* (felt grasping) 통해 self-create.

| Whitehead | APT adversarial round |
|---|---|
| **prehension** (positive) | critic 가 producer artifact 를 grasp (citation + evidence) |
| **prehension** (negative) | critic 가 무관 detail 배제 |
| **concrescence** | finding ensemble → verdict synthesis |
| **satisfaction** | gate PASS verdict (final synthesis 완성) |

**Whitehead 함의**: adversarial round 의 multiple finding 이 단일 verdict 로 concrescence — actual occasion 의 self-organization mechanism instantiation.

### Bacchelli-Bird 2013 empirical ↔ Code review effectiveness

> Bacchelli-Bird MSR 2013 — code review effectiveness empirical study: critic ≠ author, focus 분산 mandatory, 명확 finding output.

| Bacchelli-Bird | APT v17 |
|---|---|
| **executor != reviewer** | V15 mandatory (allow_agent_sigma: false LOCKED) |
| **multiple reviewer perspectives** | LensSet UNION (4 sets) |
| **finding diversity required** | Anti-Theater detect (exactly 3 NITPICK ✗) |
| **explicit verdict output** | AptDecisionLog mandatory (V28) |

### Cross-Canon Hyperedge: Producer-Reviewer Triple-Canonical

> `producer-reviewer-triple-canonical-2026-05-10` (:Hyperedge:CrossCanonGrounding):
>   1. Goodfellow 2014 GAN-D minimax
>   2. Bacchelli-Bird 2013 MSR empirical
>   3. revfactory Phase 2 pattern 4 (industry frontier)
>
> ⇒ APT v17 adversarial round = 3 정전 합치점의 산업 instantiation.

KG: `apt-philosophical-quadruple-canonical-2026-05-11` (Aristotle + Hegel + Lakatos + Friston) + `producer-reviewer-triple-canonical-2026-05-10` + `apt-error-pattern-HR20-anti-theater-2026-05-06` (mode collapse counter)

---
