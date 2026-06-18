---
name: apt
kg_ref: ATOM_Skill_apt_orchestrator
version: "28.0.0-draft"
channel: draft
status: PRELIMINARY
draft_of: rfc-apt-parsimony-pass-2026-05-14
description: >
  APT v28 thin orchestrator (draft) — practitioner-facing methodology only.
  PARSIMONY: research artifact (5-canon convergence / Lean theorems / 27-version history /
  Hyperedge progression) preserved under THEORY/APT/ but NOT loaded by this skill.
  REACTIVATION: 6 lost operational features from v12+v18+v20 (diffusion AutoMode + Multi-
  Naesengmoon + FractalFeedback + DesignAgent/TalibanSquad/BuildAgent/FixAgent split +
  UserPrinciple_SelfCorrecting + KG-as-IPC + Descent Validation depth∝check density) +
  4 dormant seeds (sigma-auto-reviewer / sibling-independence-pragmatic / mcp-subagent-proxy
  / scaling-async-gate, all dormant since 2026-04-17).
  6 operational features: SA bootstrap / SP decomposition with diffusion-style descent /
  ST crystallization (informal-ok in fast_path, typed in full_cycle) / SCW = TDD + KG refs /
  Multi-Naesengmoon descent validation (NOT just endpoint check) / Cleanup 4-tool ratchet.
  5 enforced HARD RULES (down from 16 in v27), 3 rigor modes (fast_path default).
  Subagent architecture: Orchestrator (this skill) + 4 specialist roles (DesignAgent /
  TalibanSquad / BuildAgent / FixAgent), KG-as-IPC, clean context per spawn, jaebaeman
  하노이탑 recursive descent for context-window-bound problems.
  Invoke when: "apt", "start work on", "implement", "develop", "what phase am I in", "auto mode".
  Enforces: per-branch phase detection, 5 enforced HRs (each with Cypher gate), external
  reviewer mandate before PROGRESSIVE Lakatos verdict, fast_path Lakatos verdict ceiling,
  Multi-Naesengmoon descent validation at SP, FixAgent auto-correction loop (user σ_oracle only
  at final exit).
---

# APT v28 (draft) — Thin Production Methodology

> **Status**: PRELIMINARY parallel draft. v27.60 remains the active SKILL.md.
> This file is the candidate v28 reset per [`THEORY/APT/rfc/rfc-apt-parsimony-pass-2026-05-14.md`](../../THEORY/APT/rfc/rfc-apt-parsimony-pass-2026-05-14.md).
> Promotion to active gate: S2 user-test sprint (next session) must show practitioner internalization.

---

## §0 Resolve-Only Directive (kept from v26 A6)

Every magic number / lens count / contract field count resolves from KG, not prose.

```cypher
MATCH (cfg:MethodologyConfig {name:'MethodologyConfig_default_v28'})
RETURN cfg.{field}

MATCH (slot:MethodologySlot {name:$slot_name})-[:RESOLVES_TO]->(concrete)
RETURN concrete
```

If a field appears in this SKILL.md as a literal number, it is a *snapshot at write time*, not the runtime authority.

# KG: APT_v28_A6_2026-05-14 (extends APT_v26_A6_2026-04-21)

---

## §1 HARD RULES (5, all with enforcement Cypher)

Down from 16 prose-only rules in v27 to 5 enforced rules. The 11 retired rules are valid normative guidance preserved under `_archived_rules/HR_legacy_2026-05-14.md` but do not block gate passage in v28.

### HR1 — SA must have Root Span

A SemanticAnchor without a Root Span fails the SA→SP gate. Catches the Phase 1 bootstrap defect surfaced by `lesson-apt-phase1-sa-without-root-span-2026-05-13`.

```cypher
MATCH (sa:SemanticAnchor {name: $sa_name, status: 'active'})
WHERE NOT (sa)-[:HAS_ROOT]->()
   OR sa.context_budget_total IS NULL
RETURN 'HR1_VIOLATION_SA_INCOMPLETE' AS block_reason
// any result → SA→SP gate BLOCKED
```

### HR2 — External reviewer required before PROGRESSIVE Lakatos verdict

The executor of a phase may not assign a PROGRESSIVE Lakatos verdict to their own output. Catches the K-01 BLOCKER pattern surfaced by `taliban-ensemble-bhgman_tool-phase3-2026-05-13`.

```cypher
MATCH (run:AptRun)-[:VALIDATED_BY]->(vr:ValidationResult)
WHERE run.executor = vr.executor
  AND run.lakatos_verdict STARTS WITH 'PROGRESSIVE'
RETURN 'HR2_RUBBER_STAMP' AS block_reason
// any result → verdict force-downgraded to NEEDS_EXTERNAL_REVIEW
```

External review = Naesengmoon LensSet UNION (minimum 2 distinct lenses, recommended 4: constitutional + longinus + solid + lakatos).

### HR3 — AtomicSpan must have a test before SCW completion

```cypher
MATCH (atom:AtomicSpan)-[:CRYSTALLIZES_TO]->(st:SemanticTwin)
                       -[:HAS_CONTRACT]->(c:AptContract)
WHERE NOT (c)-[:HAS_TEST]->()
  AND atom.scw_status = 'completed'
RETURN 'HR3_NO_TEST' AS block_reason
```

### HR4 — `cfg.rigor_level = fast_path` caps Lakatos verdict at PROGRESSIVE_CONDITIONAL

```python
# runtime check, not Cypher (faster path)
if cfg.rigor_level == 'fast_path' and proposed_verdict == 'PROGRESSIVE':
    proposed_verdict = 'PROGRESSIVE_CONDITIONAL'
    reason = 'HR4: fast_path mode caps verdict; external review required for PROGRESSIVE'
```

This is the operational counterpart to HR2 — it prevents the runtime from even producing a PROGRESSIVE candidate that HR2 would then block.

### HR5 — Goodhart safeguard: no scalar headline metric

Any output dictionary that emits a single scalar key named `coverage_ratio`, `accuracy_score`, `quality_score`, `success_rate`, or similar without an accompanying per-axis breakdown is rejected. Mirrors the safeguard pattern enforced in `engine/mcp_server/tools/{apt,taliban,tpa}.py` (bhgman_tool Phase 3 measurement).

```python
SCALAR_GOODHART_BANLIST = {'coverage_ratio', 'accuracy_score', 'quality_score', 'success_rate'}
if any(k in result and isinstance(result[k], (int, float)) and len(result) <= 3
       for k in SCALAR_GOODHART_BANLIST):
    raise ValueError(f'HR5_GOODHART: emit per-axis breakdown, not a scalar headline')
```

---

## §2 cfg.rigor_level — first-class operational mode

This is the single largest usability fix in v28: fast-pathing becomes named and default.

```cypher
MATCH (slot:MethodologySlot {name: 'rigor_level'})
RETURN slot.options, slot.default, slot.semantics
```

| Mode | Scope | Lakatos ceiling | When to use |
|---|---|---|---|
| **fast_path** (default) | SA + SP + SCW with informal ST (module docstring). External review optional. HR14 reflection optional. | PROGRESSIVE_CONDITIONAL | 95% of practitioner sprints — feature work, bug fixes, small refactors |
| **full_cycle** | All phases including adversarial round per gate + typed Pydantic Contract DTO + HR14 reflection + Phase 6 Cleanup ratchet | PROGRESSIVE if external review passes | sprint-end consolidation, paper-grade work, methodology validation |
| **methodology_audit** | full_cycle + self-application meta-test + 4-canon convergence check | PROGRESSIVE_PROVEN if Lean verifies | rare — APT-on-APT runs (Russell-bounded max_depth=1 invariant must hold) |

Calling `/apt` without specifying rigor_level defaults to `fast_path`. The author's prior implicit fast-pathing (which Naesengmoon K-01 caught as a degenerating-shift indicator) becomes *explicit and acknowledged* rather than *silent and rubber-stamped*.

# KG: cfg-rigor-level-2026-05-14, lesson-apt-fast-path-vs-full-prescription-2026-05-13

---

## §3 Phase Detection — per branch, KG-first

Same logic as v27, kept verbatim because it was load-bearing:

```cypher
MATCH (span:AptSpan {name: $target_span})
OPTIONAL MATCH (span)-[:CRYSTALLIZES_TO]->(st:SemanticTwin)
OPTIONAL MATCH (st)-[:HAS_CONTRACT]->(c:AptContract)
OPTIONAL MATCH (c)-[:MATERIALIZES]->(src:SourceCodeNode)
RETURN span.name,
  CASE
    WHEN src IS NOT NULL THEN 'PH5/PH6: SCW (code exists)'
    WHEN c IS NOT NULL THEN 'PH5: SCW (contract ready)'
    WHEN st IS NOT NULL THEN 'PH4: ST (twin exists, no contract)'
    WHEN span:AtomicSpan THEN 'PH4: ST (atomic, ready to crystallize)'
    ELSE 'PH3: SP (needs decomposition)'
  END AS current_phase
```

**work_kind routing** (v27 A15, kept):

| work_kind | SA phase | When |
|---|---|---|
| **NEW** | FULL (Step 1 + 2-A + 3 + gate) | no related SemanticAnchor exists |
| **EXTEND** | SHORT_CIRCUIT (Step 1-1/1-2 + 2-B/2-C + 5 core fields verify) | related anchor exists + new scope |
| **MAINTENANCE** | SKIP → ST drift mode | same anchor, same scope, bug fix / refactor |

---

## §4 Four-phase brief

### §4.1 SA — SemanticAnchor (bootstrap)

```cypher
MERGE (sa:SemanticAnchor {name: $project_name})
SET sa.objective = $objective,
    sa.definition = $definition,
    sa.keyAssertion = $key_assertion,
    sa.c_s_predicate = $c_s,
    sa.context_budget_total = 100000,
    sa.work_kind = $work_kind,
    sa.status = 'active'
MERGE (root:AptSpan {name: 'SPAN_' + $project_name + '_ROOT'})
SET root.depth = 0, root.status = 'open', root.context_budget = 50000
MERGE (sa)-[:HAS_ROOT]->(root)
```

**Mandatory**: 5 core fields (objective / definition / keyAssertion / c_s_predicate / context_budget_total) **AND** Root Span (HR1).

### §4.2 SP — Span decomposition (**diffusion-style descent**, reactivated from v12+v20)

D(S) recurrence until every leaf satisfies C(S) 5-predicate (= AtomicSpan). Branches are N:N DAG nodes, not a strict tree. depth=0 (Root) → depth=1 (L1) → depth=2 (L2) → ... → AtomicSpan.

**Diffusion frame (v12 AutoMode reactivation)**: think of SP as a denoising sampler. Each depth step refines from coarse (Root) to fine (AtomicSpan). Sibling spans at the same depth run in parallel — they share context via **KG-as-IPC** (no direct subagent communication; KG = Unix pipe). Refinement metric is *continuous score-like* in spirit (does this leaf satisfy C(S)? how much margin?) even though the C(S) gate is binary at decision time.

**Descent Validation (v20 reactivation)**: Naesengmoon critic dispatch is **depth-proportional**, not endpoint-only.
- depth 0 → 1: single Naesengmoon critic on Root decomposition
- depth N → N+1: 1 Naesengmoon subagent per ~5 atoms (`seed-apt-fix-sigma-auto-reviewer-2026-04-17` reactivated)
- AtomicSpan reached: final TalibanSquad UNION (4 lens: constitutional+longinus+solid+lakatos)

This makes APT/diffusion analogy operational: the score function is checked *along the trajectory*, not just at t=T.

**Atomic span = approximately 1 module ≈ 1 file ≈ 200-500 LOC** (`cfg.vibe_coding_sweet_min/max` resolves the exact range).

**Sibling coordination** — **A3 strict independence is KEPT** (Naesengmoon ensemble REJECT verdict 2026-05-14, `taliban-a3-axiom-relaxation-2026-05-14`, coverage 0.42, 5 BLOCKER).

The relaxation was proposed (referencing diffusion cross-attention) but rejected with the following Naesengmoon findings:
- **L1 ad-hoc rescue** — contradiction-to-conclusion flip; Lakatos degenerating problemshift
- **L2 no novel prediction** — "may improve convergence" is not falsifiable
- **L3 predecessor poisoned** — `seed-apt-fix-sibling-dep-pragmatic-carveout-2026-04-17` is TAINTED, not resolved
- **M1 equivocation** — APT-sibling (distinct decomposition units) ≠ Diffusion-sibling (denoising steps on *same* tensor). Category error.
- **S1 SRP/OCP collapse** — A3 is the structural guarantor for isolated reasoning. Removing it breaks Contract-as-interface (APT19 doctrine).

**Recommended path** (Naesengmoon verdict): if generative-modeling grounding is desired, route to **separate APT-D variant track** per `rfc-seed-apt-diffusion-grounding-2026-05-14`. Do NOT surgically remove A3 while keeping the rest of APT discrete.

Sibling spans remain independent under A3 in v28 unless and until a coherent APT-D package is built and externally validated.

### §4.3 ST — Crystallization (rigor-aware)

In **fast_path** mode: informal ST = module docstring + test file. The 9-field SemanticTwinSpecification (`semantic_purpose / runtime_flow_summary / semantic_input_meaning / semantic_output_meaning / side_effects / invariants / failure_semantics / implied_contract_refs / implied_task_slot_refs`) MAY be partially populated. Lakatos ceiling = `PROGRESSIVE_CONDITIONAL`.

In **full_cycle** mode: typed Pydantic Contract DTO with all 9 axes (`input_type / output_type / pre / post / acceptance / nfr_* / target_file / access_rights_closure / cross_axis_invariants`). All 9 ST fields populated. ST → Contract → Task chain crystallized.

In **methodology_audit** mode: full_cycle + Lean theorem `apt_atomic_span_complete` for the span.

**Honest acknowledgement** (preserved from v27 review.md): the three axis schemes (9-axis Contract v2 ∩ 8 ST Decision Area ∩ 9-field ST template) overlap and need subsumption. **Out of scope for v28**; see RFC followup.

### §4.4 SCW — SourceCodeWorld (TDD + KG refs)

TDD with `# KG: <id>` reference comments in every non-trivial code section.

```python
# KG: span-cli-install-skills-2026-05-14
def cmd_install_skills(args: Namespace) -> int:
    ...
```

Tests come first (RED), code makes them pass (GREEN), refactor under cleanup discipline (REFACTOR — see §6). At commit time, `# KG: <id>` references that don't resolve to KG nodes are caught by Longinus drift audit (`bhgman-tool daemon` or manual `longinus-audit`).

---

## §5 External review mandate

Before any phase or sprint can claim **PROGRESSIVE** Lakatos verdict, an external adversarial review must complete with verdict ≠ REJECT.

External = executor ≠ reviewer. Mechanically: invoke `taliban-ensemble-critic` subagent with at least 2 distinct lenses (recommended 4: constitutional-9 + longinus-7 + solid-5 + lakatos).

```cypher
MATCH (sprint:AptSpan)-[:VALIDATED_BY]->(vr:ValidationResult)
WHERE vr.executor <> sprint.executor
  AND size(vr.lenses_used) >= 2
  AND vr.verdict <> 'REJECT'
RETURN 'EXTERNAL_REVIEW_OK' AS gate_status
// no result → PROGRESSIVE claim BLOCKED (HR2)
```

If review verdict = REJECT, BLOCKER findings must be remediated (or explicitly accepted with logged justification) before re-review.

---

## §6 Cleanup 4-tool ratchet (Phase 6)

After SCW completion, before claiming sprint done:

```bash
uvx complexipy <code_paths> --max-complexity-allowed 15
uvx lizard <code_paths> --CCN 15
uvx vulture <code_paths> --min-confidence 80
uvx deptry .
uvx tach check  # if tach.toml present
```

Plus commit ratio metric: `refactor_commits / feature_commits ≥ 0.2` (resolves from `cfg.cleanup_commit_ratio_min`).

**verdict** = `PASS` (all enforcement-active tools clean) / `NEEDS_REFACTOR` (≤2 violations) / `BLOCK` (≥3 violations or any cycle in tach).

---

## §7 References (lazy-load, fast_path does not read)

| File | Read when |
|---|---|
| [`references/phases.md`](references/phases.md) | gate detail needed (full_cycle mode) |
| [`references/gates.md`](references/gates.md) | gate sequence audit |
| [`references/adversarial.md`](references/adversarial.md) | Naesengmoon dispatch detail |
| [`references/kg_logging.md`](references/kg_logging.md) | Friston FEP runtime / KG write |
| [`references/error_handling.md`](references/error_handling.md) | Lakatos hard core / mode collapse |
| [`references/validation.md`](references/validation.md) | V1-V29 query catalog |
| (moved out in v28) | ~~`references/theory.md`~~ → `THEORY/APT/theoretical_foundations.md` (paper artifact) |

`fast_path` mode reads **none** of the references. Only `full_cycle` and `methodology_audit` lazy-load.

---

## §8 Worked example reference

Canonical worked example for v28:
- [`SYMPOSIUM/SKILLS/apt/worked/03-apt-cycle-on-self/`](../../../bhgman_tool/worked/03-apt-cycle-on-self/) (bhgman_tool repo) — APT cycle dogfood, depth=1, `meta_twice_invalid` invariant.

Read `review.md` for an honest assessment of what the cycle got right and wrong (Naesengmoon verdict = REJECT_PENDING_REMEDIATION; honest, not rubber-stamp).

---

## §9 History (link to full log)

This SKILL.md tracks **last 5 versions only**. Full log: `THEORY/APT/SKILL_VERSION_HISTORY.md` (to be created on v28 promotion, contains 27 prior version annotations).

| Version | Date | Summary |
|---|---|---|
| **v28.0.0-draft** | 2026-05-14 | thin reset (this file) per `rfc-apt-parsimony-pass-2026-05-14` — 16 HR → 5 enforced, cfg.rigor_level slot, theory.md moved to THEORY/APT/ |
| v27.60 | 2026-05-11 | 5-canon × methodology cross-comparison sprint |
| v27.59 | 2026-05-11 | 6th Cross-Canon Hyperedge file evidence |
| v27.58 | 2026-05-11 | 5-canon convergence Lean formalization closure |
| v27.57 | 2026-05-11 | 5-canon extension + executive summary 9→10 paper contributions |

(v27.56 and earlier preserved in `THEORY/APT/SKILL_VERSION_HISTORY.md` on promotion.)

---

## §10 Honest limitations of this draft

- **Untested as a runtime spec.** This is the parallel draft per RFC §4 sprint S1. Real test = S2 user-test. If the author and one external user can't follow it, v28 is wrong and v27.60 stays.
- **5 HR may be too few** — HR14 reflection / HR6 ground truth verification were dropped from enforcement; if fast_path runs reveal regression they may need to come back.
- **rigor_level taxonomy is a guess** — 3 modes may collapse to 2 or expand to 4 after S2.
- **Cross-axis subsumption deferred** — 9-axis Contract ∩ 8 ST area ∩ 9-field ST template overlap not resolved here.
- **No external user has read this yet** — sample-of-one author confirmation only.

---

## §11 Disclaimer

The names `Naesengmoon`, `재배맨`, `Longinus`, `Prometheus` are MIC slot current bindings. Slot rebinding is documented in `MIC_v1` KG node. Canonical resolution:
```cypher
MATCH (mic:MethodologyIntegrationContract {name:'MIC_v1'})-[:HAS_SLOT]->(s)
RETURN s.name, s.currentConcrete
```

---

## §12 Subagent Architecture (reactivated from v18, was dropped in v22-v27)

Per `APT18_SubagentArchitecture` KG node — Main agent (this skill) ≠ doer. Main agent is the Orchestrator only; actual work is delegated to 4 specialist subagent roles.

| Role | Skill | Responsibility | Spawn trigger |
|---|---|---|---|
| **Orchestrator** | `/apt` (this skill) | phase detection, delegation, result collection. Does NOT directly write KG nodes or create Spans. | user invocation |
| **DesignAgent** | (new — to spec out, sibling of /apt-sp + /apt-st) | span decomposition + Contract crystallization | SA→SP transition |
| **TalibanSquad** | `taliban-ensemble-critic` agent (precursor exists) | parallel multi-lens adversarial review (constitutional + longinus + solid + lakatos) | every Descent Validation step + every gate transition |
| **BuildAgent** | (new — sibling of /apt-scw) | TDD implementation (RED → GREEN → REFACTOR) | ST→SCW transition |
| **FixAgent** | (new — implements `UserPrinciple_SelfCorrecting_APT`) | Naesengmoon finding auto-correction loop. Receives BlockerFinding nodes, proposes patches, re-dispatches to TalibanSquad for verification. | any BlockerFinding emitted by TalibanSquad |

User intervention boundary: σ_oracle at final exit + direction setting at start. **NOT at every gate.** If user has to manually catch every defect (as in this session's "너무 빨리" / "kg 잘 연결되었냐"), FixAgent is failing — system is not self-correcting. This is the K-01 BLOCKER pattern at framework level.

### §12.1 KG-as-IPC discipline (reactivated `apt-cw-kg-as-ipc`)

**Subagents do not communicate directly.** All inter-subagent state goes through KG. Pattern:

```
DesignAgent     →  writes  →  :AptSpan + :AptContract nodes
                                        │
TalibanSquad    ←  reads   ←  same nodes; writes :BlockerFinding + :ValidationResult
                                        │
FixAgent        ←  reads   ←  :BlockerFinding; writes :ProposedPatch + :CorrectionAttempt
                                        │
TalibanSquad    ←  reads   ←  :ProposedPatch; writes new :ValidationResult (verify loop)
                                        │
BuildAgent      ←  reads   ←  :AptContract + :ValidationResult (APPROVED); writes :SourceCodeNode
```

KG = Unix pipe equivalent. Parent Orchestrator does Pre-fetch (KG seed extraction) → Dispatch (subagent fire) → Collect (subagent JSON results) → Write (batch MERGE) — exactly the jaebaeman 4-phase SOP.

### §12.2 Spawn sequence (reactivated `apt-cw-spawn-sequence`)

Every subagent spawn starts from **clean context** (no inheritance from parent). Parent does Pre-fetch:

```cypher
// Pre-fetch: collect KG seed for this subagent
MATCH (ts:SubagentTaskSpec {skill: $target_skill, status: 'READY'})
OPTIONAL MATCH (ts)-[:USES_CONTRACT]->(c:AptContract)
OPTIONAL MATCH (ts)-[:INFORMED_BY]->(k:KnowledgeNode)
RETURN ts.name, ts.role, ts.system_prompt_seed,
       collect(DISTINCT c.name) AS contracts,
       collect(DISTINCT k.name) AS knowledge_seeds
```

Spawn command (Agent tool with subagent_type matching the role) — receives only the Pre-fetch payload. No conversation context inheritance.

---

## §13 Jaebaeman 하노이탑 — recursive descent for context-window-bound problems

When Span decomposition depth exceeds parent context capacity, escalate via **jaebaeman 하노이탑** pattern (per KG `재배맨_하노이탑`):

> 컨텍스트 윈도우 한계를 점화식으로 돌파하는 agent 계층 구조. CHU 전체에 접근 가능한 최상위 agent = 비행기맨.

Translated to operational terms:
- L0 (root): Orchestrator with full sprint view
- L1: per-branch DesignAgent, sees only assigned branch
- L2: per-sub-branch DesignAgent recursively spawned for deep decomposition
- ...
- L_max: AtomicSpan-level BuildAgent

Each level operates within its own context window. KG-as-IPC carries state across levels. The recursion is the **diffusion sampler depth**: deeper = more refined = more parallel branches.

`seed-apt-fix-scaling-async-gate-2026-04-17` (reactivated) provides the runtime: async Naesengmoon gate queue + executor pool ≥3 + lazy jaebaeman stream for 100+ atom SP.

---

## §14 Honest limitations of reactivation

- **DesignAgent / BuildAgent / FixAgent subagents do not yet exist**. Only `taliban-ensemble-critic` exists as TalibanSquad precursor. v28 promotion requires building these 3.
- **A3 SiblingIndependence axiom relaxation is PRELIMINARY** — needs external Naesengmoon math-lens (88-taliban or constitutional+mathematical UNION) verdict before CANONICAL.
- **4 dormant seeds reactivated but not implemented** — sigma-auto-reviewer / sibling-independence-pragmatic / mcp-subagent-proxy / scaling-async-gate are referenced here but their implementation is a separate sprint.
- **Diffusion frame is analogy-strength, not formal** — the 7 missing generative-modeling canon (Sohl-Dickstein 2015 / Ho 2020 DDPM / Song 2021 / Karras 2022 EDM / Lipman 2023 Flow Matching / Hoogeboom 2023 Cold Diffusion / Albergo 2023 Stochastic Interpolants) are *cited* but not yet *absorbed as Lean theorems* (cf. APT's existing 141 Lean theorems are all in the philosophy-of-correctness canon family).
- **Same self-application gap as v27** — these reactivations are described by the same agent (Claude) that authored the regression analysis. External KG audit (separate agent, separate sprint) needed before v28 promotion.

---

## §15 Orchestrator Dispatch Protocol

How the Orchestrator (this `/apt` skill) operationalizes the jaebaeman 4-phase SOP to spawn the 4 specialist subagents (DesignAgent / TalibanSquad / BuildAgent / FixAgent).

### §15.1 The 4-phase SOP at orchestrator level

**Pre-fetch** (Cypher seed extraction — parent does KG read for subagent):

```cypher
MATCH (ts:SubagentTaskSpec {skill: $target_skill, status: 'READY'})
OPTIONAL MATCH (ts)-[:USES_CONTRACT]->(c:AptContract)
OPTIONAL MATCH (ts)-[:INFORMED_BY]->(k:KnowledgeNode)
OPTIONAL MATCH (ts)-[:TARGETS_SPAN]->(span:AptSpan)
RETURN ts.name AS seed, ts.role, ts.system_prompt_seed, ts.inputSchema,
       collect(DISTINCT c {.name, .input_type, .output_type, .pre, .post}) AS contracts,
       collect(DISTINCT k.name) AS knowledge_seeds,
       collect(DISTINCT span.name) AS target_spans
```

**Dispatch** (Agent tool — clean context, 5-line template):

```
Agent(subagent_type=$role,
      model=ts.model or 'haiku',
      run_in_background=(N>1),
      prompt="역할: {ts.role}\n씨앗: {ts.name}\n계약: {contracts_json}\n지식_seed: {knowledge_json}\n출력: {ts.outputSchema} JSON 단일 블록")
```

**Collect** (single source-of-truth JSON schema each specialist returns):

```json
{
  "subagent_role": "DesignAgent|TalibanSquad|BuildAgent|FixAgent",
  "seed_id": "<SubagentTaskSpec.name>",
  "kg_writes": [{"label": "AptSpan", "name": "...", "props": {...}}],
  "kg_edges": [{"from": "...", "to": "...", "rel": "..."}],
  "findings": [{"kind": "Blocker|Observation|Patch", "summary": "...", "axis": "..."}],
  "verdict": "APPROVED|NEEDS_REWORK|REJECT|null",
  "evidence_refs": ["..."]
}
```

**Write** (parent batch MERGE — single transaction, idempotent):

```cypher
UNWIND $results AS r
UNWIND r.kg_writes AS w
CALL apoc.merge.node([w.label], {name: w.name}, w.props, w.props) YIELD node
WITH r
UNWIND r.kg_edges AS e
MATCH (a {name: e.from}), (b {name: e.to})
CALL apoc.merge.relationship(a, e.rel, {}, {}, b) YIELD rel
WITH r
MATCH (ts:SubagentTaskSpec {name: r.seed_id})
SET ts.status = 'COLLECTED', ts.collectedAt = datetime()
```

### §15.2 Dispatch matrix

```
SA → SP transition:   DesignAgent dispatch (span decomposition)
SP → ST transition:   DesignAgent (Contract drafting) → TalibanSquad (gate)
ST → SCW transition:  BuildAgent dispatch (TDD RED/GREEN/REFACTOR)
Any BlockerFinding:   FixAgent dispatch (loop until verdict≠REJECT or max_attempts)
Cleanup gate:         no subagent — direct uvx tool ratchet (§6)
```

### §15.3 Parallel dispatch — single-message multi-Agent pattern

When K≥3 sibling spans need the same subagent role, the Orchestrator spawns them as **K Agent tool calls in a single response message**. KG-as-IPC means parallel subagents do not coordinate at runtime — they read/write **disjoint KG node sets** (each seed's `TARGETS_SPAN` partition is disjoint by construction).

GH#29181 self-check: count(Agent invocations emitted) == count(SubagentTaskSpec with status='DISPATCHED' in this turn). If intent N ≠ actual N, the Orchestrator failed to fan out — log as `lesson-apt-degenerated-parallel-jaebaeman-2026-05-14` instance.

### §15.4 Cost discipline (per cfg.rigor_level)

- **fast_path**: 1 DesignAgent (Root span only) + 1 TalibanSquad (2-lens minimum). No BuildAgent fan-out — author implements directly under SCW guidance.
- **full_cycle**: 1 DesignAgent per branch (depth-proportional, see §4.2 Descent Validation) + 1 BuildAgent per AtomicSpan + FixAgent on-demand per BlockerFinding.
- **methodology_audit**: full_cycle + `88-taliban` TalibanSquad invocation with mathematical lens (113-lens batch, see jaebaeman §소비자별 특화).

### §15.5 Honest limitations

- **DesignAgent / BuildAgent / FixAgent are draft skills** (§12 already noted). The dispatch templates above are *target shape*, not currently runnable as-is. Only `taliban-ensemble-critic` (TalibanSquad precursor) exists.
- **Hard-coded `subagent_type` strings are anti-pattern**. Prefer `MIC_v1.SubagentSeeder` slot resolve so role names rebind without editing this section. Current literals (`DesignAgent` etc.) are placeholders for slot `currentConcrete`.
- **No saga compensation wired here** — jaebaeman v2.1 `compensating_action` slot exists in TaskSpec schema but this protocol does not yet invoke it on collect-failure. Default behavior = `best_effort` (partial results + warning).

# KG: dispatch-protocol-apt-v28-2026-05-14, MIC_v1.SubagentSeeder

---

# KG roots: ATOM_Skill_apt_orchestrator_v28_draft, rfc-apt-parsimony-pass-2026-05-14,
#           lesson-apt-degenerated-parallel-jaebaeman-2026-05-14, MIC_v1,
#           재배맨_하노이탑, APT18_SubagentArchitecture, apt-cw-kg-as-ipc,
#           apt-cw-spawn-sequence, UserPrinciple_SelfCorrecting_APT
