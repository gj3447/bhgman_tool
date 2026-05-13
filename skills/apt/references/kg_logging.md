# apt — Kg Logging

> **Lazy-load reference for `apt` skill.**
> Loaded *only when* the orchestrator enters the relevant phase/gate.
> Parent skill: [`../SKILL.md`](../SKILL.md). Repo CHANGELOG: [`../../CHANGELOG.md`](../../CHANGELOG.md).
> Refactor source: PROM 16 F6.1 Progressive Disclosure (2026-04-29).
> KG: `lesson-prom16-skillver-progressive-disclosure-drift-2026-04-29`.

---

## 8. KG Logging Procedures (MANDATORY)

### 8.1 AptDecisionLog Node (Every Gate Transition)

```cypher
CREATE (dl:AptDecisionLog {
  id: randomUUID(),
  gate_type: $gate_type,
  span_name: $span_name,
  decision: $decision,
  decided_by: $decided_by,
  decided_at: datetime(),
  adversarial_verdict: $adversarial_verdict,
  adversarial_findings_count: $findings_count,
  adversarial_blockers: $blocker_count,
  ground_truth_pass: $ground_truth_pass,
  ground_truth_details: $ground_truth_details,
  evidence_summary: $evidence_summary,
  override_reason: $override_reason
})
WITH dl
MATCH (s:AptSpan {name: $span_name})
MERGE (dl)-[:TARGETS]->(s)
RETURN dl.id, dl.gate_type, dl.decision
```

**gate_type values**: `DensityCheck`, `C_S_sigma`, `RefinementGate`, `FulfillmentGate`, `IntegrationGate`

**decision values**: `PASS`, `RETURN`, `ESCALATE`, `BLOCKED`, `OVERRIDE`

### 8.2 AptFeedback Node (Every Adversarial Finding)

```cypher
MERGE (fb:AptFeedback {name: $finding_id})
SET fb.category = $category,
    fb.severity = $severity,
    fb.status = 'open',
    fb.description = $claim,
    fb.evidence = $evidence,
    fb.suggestion = $suggestion,
    fb.ground_truth_testable = $ground_truth_testable,
    fb.ground_truth_result = $ground_truth_result,
    fb.gate_type = $gate_type,
    fb.critic_model = $critic_model,
    fb.created_at = datetime(),
    fb.created_by = 'adversarial-critic',
    fb.target_span = $target_span,
    fb.target_contract = $target_contract
WITH fb
OPTIONAL MATCH (s:AptSpan {name: $target_span})
FOREACH (_ IN CASE WHEN s IS NOT NULL THEN [1] ELSE [] END |
  MERGE (fb)-[:TARGETS]->(s)
)
RETURN fb.name, fb.severity, fb.status
```

### 8.3 Override/Skip Log (When Human Explicitly Allows)

```cypher
CREATE (ol:AptDecisionLog {
  id: randomUUID(),
  gate_type: $gate_type,
  span_name: $span_name,
  decision: 'OVERRIDE',
  decided_by: 'human',
  decided_at: datetime(),
  override_reason: $human_provided_reason,
  overridden_rule: $rule_id,
  adversarial_verdict: $original_verdict,
  adversarial_findings_count: $findings_count,
  adversarial_blockers: $blocker_count
})
WITH ol
MATCH (s:AptSpan {name: $span_name})
MERGE (ol)-[:TARGETS]->(s)
RETURN ol.id, ol.decision, ol.override_reason
```

**CRITICAL**: The `override_reason` MUST come from the human. The agent MUST NOT generate
a reason on behalf of the human. If the human says "skip", ask "Why?" and log their answer.

### 8.4 Query Open Feedback

```cypher
MATCH (fb:AptFeedback)
WHERE fb.status = 'open'
RETURN fb.category AS category,
       fb.severity AS severity,
       count(fb) AS open_count,
       collect(fb.name) AS items
ORDER BY
  CASE fb.severity
    WHEN 'BLOCKER' THEN 0
    WHEN 'PERFORMANCE' THEN 1
    WHEN 'DESIGN_DEBT' THEN 2
    WHEN 'NITPICK' THEN 3
  END
```

### 8.5 Query Decision Audit Trail

```cypher
// Full audit trail for a span
MATCH (dl:AptDecisionLog)-[:TARGETS]->(s:AptSpan {name: $span_name})
RETURN dl.gate_type, dl.decision, dl.decided_by, dl.decided_at,
       dl.adversarial_verdict, dl.adversarial_findings_count,
       dl.adversarial_blockers, dl.ground_truth_pass,
       dl.override_reason
ORDER BY dl.decided_at ASC
```

### 8.6 Resolve Feedback

```cypher
MATCH (fb:AptFeedback {name: $finding_id})
SET fb.status = 'resolved',
    fb.resolved_at = datetime(),
    fb.resolved_by = $agent,
    fb.resolution = $resolution
RETURN fb.name, fb.status, fb.resolution
```

### 8.7 Adversarial Round Trajectory Record (for KG persistence)

```python
# v17 trajectory record -- saved to KG after each adversarial round
trajectory_record = {
    "gate": "FulfillmentGate",
    "span_name": "SpanName",
    "critic_model": "sonnet",
    "design_model": "opus",
    "findings_count": 4,
    "blockers": 1,
    "performance": 1,
    "design_debt": 1,
    "nitpick": 1,
    "ground_truth_overrides": 0,
    "verdict": "REJECT",
    "resolution": "fixed blocker, re-passed",
    "ground_truth_results": {
        "cargo_test": "PASS (12/12)",
        "cargo_clippy": "PASS (0 warnings)",
        "coverage": 0.87
    },
    "sigma_oracle_decision": "APPROVE",
    "sigma_oracle_is_human": True,
    "timestamp": "2026-03-26T12:00:00Z"
}
```

---



## 14. Feedback System

### 14.1 Categories (10)

| # | Category | When to Use |
|---|----------|-------------|
| 1 | Bug | Code defect, postcondition violation |
| 2 | Confusion | Spec ambiguity, interpretation divergence |
| 3 | Missing | Missing Span, Contract, or test |
| 4 | Improvement | Feature enhancement request |
| 5 | Violation | Axiom or Principle violation detected |
| 6 | Conflict | Contradiction between Contracts or Spans |
| 7 | FalsePositive | Validation flagged normal as violation |
| 8 | FalseNegative | Validation missed a real violation |
| 9 | PerformanceDrift | Performance metric below baseline |
| 10 | SLABreach | SLA exceeded |

### 14.2 Record Feedback

```cypher
MERGE (fb:AptFeedback {name: $title})
SET fb.category = $category,
    fb.severity = $severity,
    fb.status = 'open',
    fb.description = $description,
    fb.created_at = datetime(),
    fb.created_by = $agent,
    fb.target_span = $target_span,
    fb.target_contract = $target_contract
WITH fb
OPTIONAL MATCH (s:AptSpan {name: $target_span})
FOREACH (_ IN CASE WHEN s IS NOT NULL THEN [1] ELSE [] END |
  MERGE (fb)-[:TARGETS]->(s)
)
RETURN fb.name, fb.status
```

Record feedback **immediately** when you discover a problem. Even minor confusion
accumulates into major APT violations.

### 14.3 Anti-Pattern: Adversarial Theater (v17)

| # | Anti-Pattern | Symptom | Detection | Prevention |
|---|-------------|---------|-----------|------------|
| 18 | Adversarial Theater | Critic produces exactly 3 NITPICK findings every round | Severity distribution audit, historical finding rate | Model rotation, sigma_oracle meta-review |

---

## 15. KG Logging Philosophical Grounding (2026-05-11 추가)

> Cross-ref: `THEORY/APT/PHILOSOPHICAL_FOUNDATIONS.md` §6 (Friston FEP) + `producer-reviewer-triple-canonical-2026-05-10` + `mcp-quadruple-canonical-multi-grounding-2026-05-10` (W3C PROV-DM in MCP cross-canon).
> **iter 104 갱신**: 17 APT Lean files / 156 theorems Mathlib-free 0 sorry — 9-tier architecture. Per-KG-logging-mechanism explicit Lean theorem cite:
> - **Friston active inference 5-component bijection** (KAL→prior / Contract→prediction / SCW→action / Validation→error / KGLog→posterior) → `APT_Friston_FEP.lean:apt_active_inference_complete` + `low_prediction_error_implies_pass` + `high_prediction_error_implies_block`
> - **Lesson Bayesian update** (`wrongAssumption ↔ truth` symmetric pair) → `APT_Friston_FEP.lean:lesson_nonempty_complete` + `apt_majority_lesson_autopoietic` (closure ≥ 50%)
> - **Tarski metalanguage** (KG = APT 의 외부 truth predicate) → `APT_Tarski_Metalanguage.lean:apt_tarski_compliant` + `apt_has_metalanguage` (object language vs metalanguage 명확 distinction)
> - **W3C PROV-DM 6 relations** (wasGeneratedBy / used / wasInformedBy / wasAttributedTo / wasAssociatedWith / actedOnBehalfOf) → `mcp-quadruple-canonical-multi-grounding-2026-05-10` hyperedge (cross-canon Lean 후보)
> - **Maturana autopoietic closure** (Lesson → Pattern Library extension) → `APT_Maturana_Autopoiesis.lean:apt_full_autopoietic_coverage` + `pure_self_feedback_full_closure` + `apt_completion_pure_autopoietic`
> - **Anti-Theater (V18 mode collapse)** → `APT_Adversarial_Triple.lean:mode_collapse_no_refutation` (Goodfellow GAN-D detect)
>
> KG logging 가 *왜* APT cycle 전체 entry 의 정전적 mechanism인지 학문 grounding.

### Friston Free Energy Principle ↔ KG Logging = Bayesian update

```
APT cycle = active inference loop (Friston 2010):
  ┌─────────────────────────────────────────┐
  │ prior → prediction (SA + SP + ST) Contract │
  │           ↓                                 │
  │ action (SCW) — TDD execution                │
  │           ↓                                 │
  │ prediction error (Taliban verdict + VR)     │
  │           ↓                                 │
  │ KG LOGGING — :Lesson + :ValidationResult    │
  │           ↓                                 │
  │ Bayesian update — model 갱신 (next prior)   │
  └─────────────────────────────────────────┘
```

| Friston FEP component | APT KG logging entry |
|---|---|
| **prior** (model 사전 분포) | KG :SemanticAnchor + Pattern Library + 5무기 substrate |
| **prediction** (expected) | :Contract v2 9-axis + :AptDecisionLog gate_intent |
| **action** | :ValidationResult execution + cargo test pass |
| **prediction error** (surprise) | :Lesson `wrongAssumption ↔ truth` symmetric pair |
| **Bayesian update** | KG MERGE + :EXPLAINED_BY edge + :GENERALIZES :Lesson |

**Friston 함의**: KG logging *없으면* free energy 측정 ✗ → active inference loop 깨짐 → APT cycle = blind. 그래서 v17 mandatory KG logging 모든 decision = *active inference completeness* enforcement.

### W3C PROV-DM ↔ KG Logging = provenance recording

> W3C PROV-DM 2013 (provenance data model) — 6 relations: wasGeneratedBy / used / wasInformedBy / wasAttributedTo / wasAssociatedWith / actedOnBehalfOf.

| W3C PROV | APT KG logging |
|---|---|
| **wasGeneratedBy** | :Lesson - GENERATED_BY → :APTCycle |
| **used** | :APTCycle - USED → :Contract / :Pattern / :SemanticAnchor |
| **wasInformedBy** | :Lesson - INFORMED_BY → :Verdict (external) |
| **wasAttributedTo** | :Decision - ATTRIBUTED_TO → :SkillVersion / :Agent |
| **wasAssociatedWith** | :APTCycle - ASSOCIATED_WITH → :User / :Agent |
| **actedOnBehalfOf** | :Subagent - ACTED_ON_BEHALF_OF → :ParentClaude |

**W3C PROV 함의**: APT KG logging = 산업 표준 provenance recording 의 instantiation. SLSA L1-L4 supply chain provenance 기반 동일 정전 (Longinus 7-Layer cross-canon `longinus-7layer-hierarchical-reference-triple-canonical-2026-05-11`).

### Tarski undefinability 회피 ↔ KG = external metalanguage

> APT methodology object language ✗ truth predicate (Tarski 1936) → metalanguage mandatory.

```
APT methodology = object language (자기 truth ✗)
KG = metalanguage (외부 truth predicate)
  - :ValidationResult = APT 의 truth verdict (외부)
  - :Lesson `truth` field = correction 정전화
  - :SemanticAnchor = grounding (앵커)
```

KG 가 APT 의 *외부 metalanguage* 로 작용 — Tarski 회피 mechanism의 산업 instantiation.

### Anti-Theater (v17) ↔ Producer-Reviewer triple-canonical (Cross-Canon)

§14.3 Anti-Pattern 18 = `producer-reviewer-triple-canonical-2026-05-10` Cross-Canon Hyperedge 의 KG logging 측 instantiation. Goodfellow GAN-D mode collapse + Bacchelli-Bird empirical + revfactory Phase 2 pattern 4 = 3 정전 합치점.

KG: `apt-philosophical-quadruple-canonical-2026-05-11` (Aristotle + Hegel + Lakatos + Friston) + `producer-reviewer-triple-canonical-2026-05-10` + `mcp-quadruple-canonical-multi-grounding-2026-05-10` (W3C PROV-DM 정전)

---
