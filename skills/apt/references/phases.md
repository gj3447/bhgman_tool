# apt — Phases

> **Lazy-load reference for `apt` skill.**
> Loaded *only when* the orchestrator enters the relevant phase/gate.
> Parent skill: [`../SKILL.md`](../SKILL.md). Repo CHANGELOG: [`../../CHANGELOG.md`](../../CHANGELOG.md).
> Refactor source: PROM 16 F6.1 Progressive Disclosure (2026-04-29).
> KG: `lesson-prom16-skillver-progressive-disclosure-drift-2026-04-29`.

---

## 4. Adversarial Round Protocol (D20 -- MANDATORY)

### 4.1 The Four Stages

Every adversarial round follows these four stages. None may be skipped.

```
AdversarialRound(artifact, gate_name):

  Stage A -- PROPOSE:
    Design Agent presents artifact for gate passage.
    Artifact = {decomposition plan | contract draft | implemented code}.

  Stage B -- ATTACK:
    Critic Agent (adversarial-critic agent, sonnet model) reviews artifact.
    Critic MUST produce minimum 3 findings (HARD requirement).
    Each finding classified: BLOCKER | PERFORMANCE | DESIGN_DEBT | NITPICK.
    Critic also runs:
      - WebSearch for counter-evidence (compatibility, prior art, known issues)
      - KG knowledge contradiction check
    IF findings < 3:
      Re-run with stronger prompt (see Section 7.2)
      IF still < 3 after re-run: log anomaly, proceed with what we have

  Stage C -- GROUND TRUTH:
    Execute objective validation appropriate to gate:
      C_S_sigma:       KAL link count, tau banned-type check, v complexity check
      RefinementGate:  tau_check 5/5, postcondition falsifiability test
      FulfillmentGate: cargo test, cargo clippy, coverage measurement
    Ground truth results are AUTHORITATIVE (D23).
    If ground truth contradicts critic finding: finding DISMISSED.
    If ground truth confirms critic finding: finding UPGRADED to BLOCKER.

  Stage D -- DECIDE:
    sigma_oracle (HUMAN -- always) receives:
      1. Design Agent's proposal
      2. Critic Agent's findings (with severity classifications)
      3. Ground truth results (pass/fail, coverage numbers)
    sigma_oracle decides: APPROVE | RETURN(with reason) | ESCALATE
    BLOCK until human responds. Do NOT proceed without human decision.

  AFTER DECISION:
    Log AdversarialRoundCompleted event
    Create AptDecisionLog node in KG
    Create AptFeedback nodes for each finding
```

### 4.2 How to Spawn the Adversarial Critic

The adversarial-critic is defined as a Claude agent at:
`.claude/agents/adversarial-critic.md`

To invoke the critic, use the agent subcommand or tool with the following context:

```
Invoke adversarial-critic agent with:
  - model: sonnet (MUST differ from design agent model)
  - input: the artifact being reviewed
  - context: relevant KG nodes, sibling spans, parent contract
  - gate_name: which gate this is for
  - instructions: follow D22.3 Adversarial Critic Prompt Template
```

The critic agent's system prompt enforces:
- Minimum 3 findings
- Severity classification (BLOCKER/PERFORMANCE/DESIGN_DEBT/NITPICK)
- Evidence for each finding (URL or reasoning)
- At least 1 alternative approach
- WebSearch for counter-evidence

### 4.3 Gate-Specific Adversarial Application

| Gate | What Critic Attacks | Ground Truth Source | When |
|------|--------------------|--------------------|------|
| C_S_sigma | Decomposition completeness, missing concerns, over/under-splitting | KAL link density, architecture pattern check, WebSearch | Before sigma_oracle in SP |
| RefinementGate | Contract ambiguity, untestable postconditions, missing edge cases | tau_check 5/5, eval-optimizer metrics, WebSearch | After Crystallize(), before PH5 entry |
| FulfillmentGate | Code correctness, missed requirements, regression risk, API misuse | `cargo test`, `cargo clippy`, compiler output, coverage | After implementation, before DONE |

### 4.4 Adversarial Critic Prompt Template (D22.3)

When invoking the adversarial-critic agent, ensure this template is part of the context:

```markdown
# Adversarial Critic Review

You are reviewing a {artifact_type} for APT gate passage: {gate_name}.



## 5. KG Density Check (D21 -- MANDATORY)

### 5.1 When to Run

BEFORE any SP decomposition begins. This is a prerequisite, not a post-check.

### 5.2 Three Requirements

| # | Requirement | Threshold | On Fail |
|---|------------|-----------|---------|
| 1 | Min INFORMED_BY links | >= 5 | BLOCK --> run KAL to acquire knowledge |
| 2 | Min source type diversity | >= 3 distinct types | BLOCK --> diversify via targeted KAL |
| 3 | Foundation:composite ratio | >= 2:1 | BLOCK --> acquire more foundational sources |

### 5.3 Source Types (Enumerated)

```
paper          - Academic paper, arXiv, journal
implementation - Existing codebase, library source
documentation  - Official docs, API reference, man pages
experiment     - Empirical test results, benchmarks, PoC outcomes
expert         - Domain expert knowledge, design rationale
specification  - RFC, W3C spec, language spec, protocol spec
prior_art      - Similar projects, case studies
```

### 5.4 Foundation vs. Composite Classification

```python
def classify_knowledge_node(node: dict) -> str:
    """Classify a KnowledgeNode as 'foundation' or 'composite'.

    Foundation: directly observed/measured/read from primary source.
    Composite: derived from combining multiple foundation nodes.
    """
    if node.get("derived_from") and len(node["derived_from"]) > 0:
        return "composite"
    if node.get("source_type") in ("paper", "specification", "experiment", "implementation"):
        return "foundation"
    if node.get("is_synthesis", False):
        return "composite"
    return "foundation"  # default to foundation for simple knowledge
```

### 5.5 Density Check Query

```cypher
// V27 (v15/v17): Foundational Density -- source type diversity + foundation ratio
MATCH (s:AptSpan {name: $target_span})-[:INFORMED_BY]->(k:KnowledgeNode)
WITH s,
  count(k) AS total_links,
  count(DISTINCT k.source_type) AS source_type_count,
  count(CASE WHEN k.classification = 'foundation' THEN 1 END) AS foundation_count,
  count(CASE WHEN k.classification = 'composite' THEN 1 END) AS composite_count
RETURN s.name AS span,
  total_links,
  source_type_count,
  foundation_count,
  composite_count,
  total_links >= 5 AS link_count_pass,
  source_type_count >= 3 AS diversity_pass,
  CASE WHEN composite_count = 0 THEN true
       ELSE foundation_count >= 2 * composite_count END AS ratio_pass
```

### 5.6 Density Check Procedure

```
PROCEDURE DensityCheck(span_name):
  1. Run density check query (Section 5.5)
  2. IF total_links < 5:
       LOG "BLOCKED: INFORMED_BY count {total_links} < 5"
       RUN KAL(span_name) -- broad search
       GOTO step 1
  3. IF source_type_count < 3:
       missing_types = REQUIRED_TYPES - existing_types
       LOG "BLOCKED: only {source_types} present, need 3+ types"
       RUN KAL(span_name, target_types=missing_types) -- targeted search
       GOTO step 1
  4. IF foundation_count < 2 * composite_count:
       LOG "BLOCKED: foundation:composite = {f}:{c}, need >= 2:1"
       RUN KAL(span_name, target_classification="foundation") -- foundational search
       GOTO step 1
  5. LOG "DENSITY CHECK PASSED"
  6. Create AptDecisionLog node:
       gate_type = "DensityCheck"
       decision = "PASS"
       evidence = {total_links, source_type_count, foundation_count, composite_count}
  7. RETURN PASS
```

### 5.7 KAL Search Triggers (7 Types)

| # | Condition | Search Type | Result |
|---|-----------|-------------|--------|
| 1 | links(S) < 5 | Broad KG search | Find related concepts, research, entities |
| 2 | C(S) v-fail (too complex) | Targeted: decomposition patterns | Find similar modules that were successfully split |
| 3 | C(S) t-fail (vague types) | Targeted: type definitions | Find concrete DTOs, schemas, API specs |
| 4 | C(S) i-fail (untestable) | Targeted: test examples | Find similar test patterns, assertion templates |
| 5 | C(S) d-fail (too small) | N/A | No search needed (merge upward) |
| 6 | C(S) s-fail (semantic gap) | Domain-specific search | Find domain papers, ontologies, standards |
| 7 | Manual trigger | User-specified | Custom query against KG or web |

### 5.8 KnowledgeNode Creation from KAL

```cypher
MERGE (k:KnowledgeNode {name: $name})
SET k.source = $source,
    k.source_type = $source_type,
    k.classification = $classification,
    k.content_summary = $summary,
    k.url = $url,
    k.confidence = $confidence,
    k.searched_at = datetime(),
    k.search_trigger = $trigger

WITH k
MATCH (s:AptSpan {name: $span_name})
MERGE (s)-[:INFORMED_BY {
  reason: $why,
  source: $search_source,
  linked_at: datetime(),
  auto_acquired: true
}]->(k)
```

### 5.9 Density Check in Lite Mode (JSON)

```python
def density_check(span: dict, config: dict) -> dict:
    """v17: Check foundational density requirements."""
    knowledge = span.get("informed_by", [])
    total = len(knowledge)
    source_types = set(k.get("source_type", "unknown") for k in knowledge)
    foundation = [k for k in knowledge if classify_knowledge_node(k) == "foundation"]
    composite = [k for k in knowledge if classify_knowledge_node(k) == "composite"]

    return {
        "total_links": total,
        "min_links_pass": total >= config.get("min_informed_by", 5),
        "source_types": list(source_types),
        "source_diversity_pass": len(source_types) >= 3,
        "foundation_count": len(foundation),
        "composite_count": len(composite),
        "ratio_pass": len(composite) == 0 or len(foundation) >= 2 * len(composite),
        "all_pass": (total >= config.get("min_informed_by", 5)
                     and len(source_types) >= 3
                     and (len(composite) == 0 or len(foundation) >= 2 * len(composite))),
    }
```

---



## 6. Ground Truth Primacy (D23 -- MANDATORY)

### 6.1 Authority Hierarchy

```
For FACTUAL claims (does code compile? do tests pass? is this API compatible?):

  AUTHORITATIVE (cannot be overridden by opinion):
    1. Compiler output (cargo build, rustc, gcc, tsc)
    2. Test execution results (cargo test, pytest, jest)
    3. Runtime behavior (browser execution, WASM execution)
    4. External evidence (WebSearch for API docs, compatibility tables)

  ADVISORY (informs decisions but cannot override authoritative sources):
    5. Critic Agent findings
    6. Design Agent claims

  LEAST AUTHORITATIVE for factual matters:
    7. Human intuition ("I think this should work")

For DESIGN/ARCHITECTURAL decisions:
  Human judgment (sigma_oracle) remains supreme.
  D23 does NOT apply to design decisions.
```

### 6.2 Ground Truth Override Rule

```
GroundTruthOverride(finding, ground_truth_result):
  IF finding.ground_truth_testable == true:
    test_result = RUN ground_truth_command(finding)
    IF test_result CONTRADICTS finding:
      finding.status = "OVERRIDDEN_BY_GROUND_TRUTH"
      finding.severity = "DISMISSED"
      LOG "Finding {finding.id} dismissed: ground truth contradicts critic"
    ELIF test_result CONFIRMS finding:
      finding.status = "CONFIRMED_BY_GROUND_TRUTH"
      IF finding.severity != BLOCKER:
        finding.severity = BLOCKER   # upgrade
      LOG "Finding {finding.id} upgraded to BLOCKER: ground truth confirms"
```

### 6.3 Per-Gate Ground Truth Requirements

| Gate | Ground Truth Required | Command / Method |
|------|----------------------|------------------|
| C_S_sigma (SP) | WebSearch evidence for each design decision | WebSearch + cite URL |
| C_S_sigma (SP) | KAL link density verified | Density check query |
| RefinementGate (ST) | WebSearch evidence for API choices | WebSearch + cite URL |
| RefinementGate (ST) | tau_check 5/5 passes | Automated type check |
| FulfillmentGate (SCW) | `cargo test` passes | `cargo test 2>&1` |
| FulfillmentGate (SCW) | `cargo build --release` compiles | `cargo build --release 2>&1` |
| FulfillmentGate (SCW) | `cargo clippy` clean | `cargo clippy -- -D warnings 2>&1` |
| FulfillmentGate (SCW) | Coverage measured | Coverage tool output |

### 6.4 Practical Application

| Claim Type | Ground Truth Source | Example |
|-----------|-------------------|---------|
| "This code compiles" | `cargo build 2>&1` | Compiler error on line 42 = AUTHORITATIVE |
| "Tests pass" | `cargo test 2>&1` | 3 tests fail = AUTHORITATIVE |
| "This API exists in version X" | WebSearch + official docs | Deprecated in v3 = AUTHORITATIVE |
| "This will be fast enough" | Benchmark execution | p99=500ms vs 100ms target = AUTHORITATIVE |
| "This is the right architecture" | NOT ground-truth-testable | sigma_oracle decides |
| "This decomposition is complete" | NOT ground-truth-testable | sigma_oracle decides |

### 6.5 FulfillmentGate Ground Truth Check (v17)

```python
def fulfillment_check_13_ground_truth(findings: list, test_results: dict) -> bool:
    """v17: Verify all ground-truth-testable claims have been validated.

    Returns False if any factual claim relies solely on agent opinion
    when a ground truth test was available but not run.
    """
    for finding in findings:
        if finding.get("ground_truth_testable") and not finding.get("ground_truth_result"):
            return False  # testable claim without actual test = FAIL
    # Also verify: test suite actually ran (not just claimed to pass)
    if not test_results.get("executed"):
        return False
    return True
```

---



## 11. Phase Transition Guards

### 11.1 Before /apt-sa

No prerequisite. This is the entry point for new projects.

### 11.2 Before /apt-sp

```cypher
MATCH (sa:SemanticAnchor {name: $project}) RETURN sa.name
MATCH (span:AptSpan {name: $target}) RETURN span.name, labels(span)
```

**v17 ADDITION**: Run Density Check (Section 5) BEFORE decomposition begins.

### 11.3 Before /apt-st (C(S) gate)

All 5 crystallization criteria must pass. Evaluation order: cheap rejection first.

| Order | Symbol | Criterion | Gate | On Fail |
|:-----:|:------:|-----------|:----:|---------|
| 1st | v | Complexity <= 500 lines | auto | Split -- too large |
| 2nd | tau | Type Expressibility -- concrete I/O types | auto | Split by type boundary |
| 3rd | iota | Test Feasibility -- concrete assertions | auto | Sharpen with examples |
| 4th | delta | Decomposition Diseconomy -- further split < 100 lines? | auto | Merge upward |
| 5th | sigma | Semantic Completeness | **HUMAN** | sigma_auto first, then sigma_oracle |

**v17 ADDITION**: Between sigma_auto pass and sigma_oracle, run:
1. Adversarial Round (C_S_sigma) -- Section 4
2. Ground Truth verification -- Section 6
3. sigma_oracle receives: proposal + critic findings + ground truth

```cypher
MATCH (span:AptSpan {name: $target})
RETURN span:AtomicSpan AS is_atomic
// If not atomic, all 5 predicates must be verified before proceeding to /apt-st
```

### 11.4 Before /apt-scw (Contract completeness gate)

```cypher
MATCH (st:SemanticTwin {name: $target})-[:HAS_CONTRACT]->(c:AptContract)
RETURN c.name,
  c.input_type IS NOT NULL AS has_input,
  c.output_type IS NOT NULL AS has_output,
  c.acceptance_tests IS NOT NULL AS has_tests,
  c.status AS status
// ALL must be present. If any is missing -> return to /apt-st
```

**v17 ADDITION**: Verify RefinementGate adversarial round completed:
```cypher
MATCH (s:AptSpan {name: $span_name})<-[:TARGETS]-(dl:AptDecisionLog)
WHERE dl.gate_type = 'RefinementGate'
  AND dl.adversarial_verdict IS NOT NULL
  AND dl.decision = 'PASS'
RETURN dl.id, dl.decided_at
```

### 11.5 After /apt-scw (Materialization verification)

```cypher
MATCH (c:AptContract {name: $ct})-[:MATERIALIZES]->(src:SourceCodeNode)
RETURN src.file_path, src.status, src.lines
// src must exist and status = 'implemented'
```

**v17 ADDITION**: Verify FulfillmentGate adversarial round completed AND cargo test passed:
```cypher
MATCH (s:AptSpan {name: $span_name})<-[:TARGETS]-(dl:AptDecisionLog)
WHERE dl.gate_type = 'FulfillmentGate'
  AND dl.adversarial_verdict IS NOT NULL
  AND dl.ground_truth_pass = true
  AND dl.decision = 'PASS'
RETURN dl.id, dl.decided_at
```

---

## 12. Aristotle 4 Causes ↔ APT 7-Phase Mapping (2026-05-11 추가)

> Cross-ref: `THEORY/APT/PHILOSOPHICAL_FOUNDATIONS.md` §1 + `MIND/lean_formalization/APT_Cycle_Functor.lean` (Lean 9 theorems PASS).
> **iter 101 갱신**: 17 APT Lean files / 156 theorems Mathlib-free 0 sorry — 9-tier architecture (1 FOUND + 4 explicit canonical + 6 sub-axis + 1 CAPSTONE + 2 ENGINEERING + 1 LIMIT + 1 CROSS-CANON + 1 META). Phase 매핑 explicit Lean cite:
> - PH1 SemanticAnchor (SA) = Aristotle Material cause (`APT_Cycle_Functor.lean:sa_is_material_cause`)
> - PH2 SemanticPyramid (SP) = Formal cause + DDD Bounded Context + Hegel thesis (`APT_DDD_Conway_BoundedContext.lean:complete_apt_sp_well_formed`)
> - PH3 SemanticTwin (ST) = Formal cause crystallized + Curry-Howard type (`APT_Curry_Howard.lean:cargo_pass_implies_proof`)
> - PH4 SourceCodeWorld (SCW) = Efficient cause + Beck TDD RGR + Boyd OODA action (`APT_TDD_Beck_RGR.lean:apt_scw_complete_iff_full_rgr` + `APT_OODA_Boyd.lean:apt_ooda_production_bound`)
> - PH5 Validation = Final cause + Tarski metalanguage + Adversarial Triple (`APT_Tarski_Metalanguage.lean:apt_tarski_compliant` + `APT_Adversarial_Triple.lean:apt_v17_adversarial_fully_grounded`)
> - PH6 MetaReview = Russell-Lawvere-Yanofsky-Hofstadter bounded recursion (`APT_MetaReview_Bounded.lean:meta_twice_invalid`)
> - PH7 Cleanup = Maturana autopoiesis + Lakatos positive heuristic (`APT_Maturana_Autopoiesis.lean:apt_full_autopoietic_coverage` + `APT_Lakatos_Progressive.lean:apt_cycle_progressive`)
>
> Aristotle *Physics* II.3 + *Metaphysics* V.2 — 모든 것은 4 원인으로 설명. APT 7 phase 가 정확 매핑.

| Aristotle 원인 | APT phase | 의미 | Lean theorem |
|---|---|---|---|
| **Material cause** (causa materialis) | **SA** (SemanticAnchor) | "무엇으로 만드나" — KG anchor + Progressive Disclosure + context budget (apt-sa SKILL grounding) | `sa_is_material_cause` PASS |
| **Formal cause** (causa formalis) | **SP** (SemanticPyramid) | "어떤 형식으로 분해되나" — D(S) recursive + AtomicSpan 5-predicate + MDL stopping | (apt_aristotle_complete coverage) |
| **Efficient cause** (causa efficiens) | **ST** (SemanticTwin) | "무엇이 만드나" — Contract v2 9-axis + Task spec + DTO crystallization | (apt_aristotle_complete coverage) |
| **Final cause** (causa finalis) | **SCW** (SourceCodeWorld) | "무엇 위해" — TDD GREEN + Lesson generation + telos (목적인) | `scw_is_final_cause` PASS |
| **Meta cause** (Lakatos extension) | **MetaReview + Cleanup** | "원인의 원인" — feedback loop + Phase 6 ratchet (5-tier) | `meta_phases_collapse_to_meta` PASS |

**Lakatos 1970 reading**: 4 원인 + meta-causa = research programme 의 *hard core* (Contract v2 9-axis + C(S) 5-predicate, 불변) + *protective belt* (SP decomposition + AtomicSpan, 가변) 구조.

### Phase boundary 의 철학 함의

```
SA (Material) → SP (Formal) — Aristotle 의 *질료 → 형식* 운동
SP (Formal) → ST (Efficient) — *형식 → 운동인* (Contract = 무엇이 만드나)
ST (Efficient) → SCW (Final) — *운동인 → 목적인* (telos = 코드)
SCW → MetaReview (Meta) — Lakatos 가 4 원인 외 *progressive shift* 추가
```

**전체**: APT 사이클 = Aristotle 4 원인 + Lakatos progressive 의 *engineering 결정화*. 2400년 형이상학 chain (Aristotle ~340 BCE → Aquinas 1265 → Hegel 1807 → Lakatos 1970 → Lean 2026).

KG: `apt-philosophical-quadruple-canonical-2026-05-11` (`:Hyperedge:CrossCanonGrounding` STRONG_QUADRUPLE_PHILOSOPHICAL)

---
