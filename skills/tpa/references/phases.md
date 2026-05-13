# tpa — Phases

> **Lazy-load reference for `tpa` skill.**
> Parent skill: [`../SKILL.md`](../SKILL.md). Mirror reference: [`../../apt/references/phases.md`](../../apt/references/phases.md).
> KG: `tpa-hardening-master-plan-2026-05-06`.

---

## 0. Phase Map

```
[CODE]
   │
   ▼
┌──────────────────────┐
│ Phase 1 — TCW       │  /tpa-tcw <path>     (TargetCodeWorld)
│  AST harvest         │  enter: code present
│  manifest assertion  │  output: TPA_TCW_Result + symbol manifest
└──────────────────────┘
   │ Taliban 9-lens VR + Reflection (TR9) + KG log (TR7)
   ▼
┌──────────────────────┐
│ Phase 2 — ST        │  /tpa-st             (TargetSemanticTwin)
│  contract extraction │  enter: TCW VR APPROVED
│  Apt vs Conventional │  output: TPA_ST_Result + AptContract + ConventionalContract
└──────────────────────┘
   │ Taliban 9-lens VR + Reflection + KG log
   ▼
┌──────────────────────┐
│ Phase 3 — SP        │  /tpa-sp             (TargetPyramid)
│  pattern matching    │  enter: ST VR APPROVED
│  GoF + Distributed   │  output: TPA_SP_Result + INSTANCE_OF / RESEMBLES edges
└──────────────────────┘
   │ Taliban 9-lens VR + 88-Taliban for Distributed + KG log
   ▼
┌──────────────────────┐
│ Phase 4 — TA        │  /tpa-ta             (TargetAnchor)
│  anchor + 5-drift    │  enter: SP VR APPROVED
│  coverage_ratio      │  output: SemanticAnchor (or status='SUSPENDED')
└──────────────────────┘
   │ Final Taliban VR + Lesson Loop fires
   ▼
[DESIGN ANCHORED + LESSONS GENERATED]
```

---

## 1. Phase 1 — TargetCodeWorld (TCW)

**Question**: "What pub symbols actually exist in this code?"

### 1.1 Inputs
- `<path>`: directory or repo root
- (optional) `tpa-config.yaml` parallel.max_agents

### 1.2 Steps
1. Manifest construction
   - `find <path> -name '*.{rs,ts,py,go}' -not -path '*/target/*' | sort > manifest.txt`
   - Per-file LOC measured (`wc -l`)
2. Chunking decision
   - `< 10K LOC`: single agent
   - `10K-100K`: 4-agent (재배맨 file-level partition)
   - `100K+`: 8-agent + hierarchical merge
3. AST extraction per agent (TR4)
   - tree-sitter / rust-analyzer / pyright (per language)
   - extract pub symbols: name, kind (fn/struct/trait/etc.), file:line, signature
4. Manifest assertion (TR5)
   - `union(agent_files) == manifest_files` MUST hold
   - failure → BLOCK, supplementary agent
5. ResearchProvider auto-trigger on Unknown (TR6)
   - any unrecognized syntax pattern → /prom auto + KnowledgeNode created
6. TPA_TCW_Result node created (per §1.3)
7. Taliban 9-lens VR (TR1)
8. Reflection (TR9) + KG log (TR7)

### 1.3 Output Schema
```cypher
MERGE (tcw:TPA_TCW_Result {name: 'TCW_' + $target + '_' + $date})
SET tcw.sourcePath = $target,
    tcw.symbol_count = $n,
    tcw.parser_symbol_count = $parser_n,    // TR4 ground truth
    tcw.parsed_with = $parser,              // tree-sitter | rust-analyzer | pyright
    tcw.skipped_files = 0,                  // TR5 invariant
    tcw.manifest = $manifest_file_list,
    tcw.unknown_count = $unknown_n,
    tcw.giant_method_candidates = $giants_n
MERGE (exec)-[:PHASE_OUTPUT {order:1}]->(tcw)
```

---

## 2. Phase 2 — TargetSemanticTwin (ST)

**Question**: "What contract does each pub symbol promise?"

### 2.1 Inputs
- TCW VR APPROVED (Hook pre-gate)
- TPA_TCW_Result + symbol list

### 2.2 Steps
1. For each pub symbol:
   - **Explicit interface / trait / abstract class** → `:AptContract`
   - **N ≥ 3 implementors share signature shape** → `:ConventionalContract`
   - **LOC > 100 method** → defer to SP (giant method, not atomic)
2. pre/postcondition parsing
   - docstring / JSDoc / Rust-doc inspected
   - missing → field set to `'NONE — code contract only'` (explicit, not blank)
3. Discrimination check (TR + V7)
   - no node has both `:AptContract` AND `:ConventionalContract`
4. Longinus binding (TR12)
   - each Contract gets `:ReferenceSite { sourcePath: file:line }`
5. TPA_ST_Result node + Taliban 9-lens VR + KG log

### 2.3 Output Schema
```cypher
MERGE (st:TPA_ST_Result {name: 'ST_' + $target + '_' + $date})
SET st.sourcePath = $target,
    st.totalContracts = $apt + $conv,
    st.aptContracts = $apt,
    st.conventionalContracts = $conv,
    st.giantMethodsDeferred = $gm,
    st.prePostParsed = $pp
MERGE (exec)-[:PHASE_OUTPUT {order:2}]->(st)
```

---

## 3. Phase 3 — TargetPyramid (SP)

**Question**: "What design patterns do these contracts compose?"

### 3.1 Inputs
- ST VR APPROVED
- Pattern Library count >= 38 (canonical: 51 — GoF23 + Distributed10 + PL5 + 13 extension)

### 3.2 Steps
1. Pattern Library precondition check
2. Per-category matching strategy:
   - **Structural** (Facade/Adapter/Composite/...) → AST signature matching (Longinus)
   - **Behavioral** (Strategy/Observer/Command/...) → call graph analysis (Longinus)
   - **Creational** (Factory/Builder/Singleton/...) → instantiation trace (Longinus + grep)
   - **Distributed** (CRDT/BFT/HotStuff/Kademlia/...) → math properties (88-Taliban MetaVerifier)
   - **PL** (DuckTyping/TypeClass/Monad/...) → language feature lookup (ResearchProvider)
3. Required-element checklist (TR2)
   - every INSTANCE_OF candidate evaluated against pattern's required-element list
   - every required element present + evidence cited → confidence ≥ 0.7 → INSTANCE_OF
   - some elements present → confidence < 0.7 → RESEMBLES
   - name match only → confidence < 0.4 → not recorded
4. Distributed mandatory MetaVerify
   - any INSTANCE_OF to Distributed pattern → 88-Taliban auto-fire
   - SP-MetaVerify VR APPROVED is gate-blocking
5. NovelPattern recording for unmatched
6. TPA_SP_Result node + Taliban 9-lens VR + KG log

### 3.3 Output Schema
```cypher
MERGE (sp:TPA_SP_Result {name: 'SP_' + $target + '_' + $date})
SET sp.sourcePath = $target,
    sp.totalPatterns = $instance_of + $resembles,
    sp.instanceOf_count = $instance_of,
    sp.resembles_count = $resembles,
    sp.novelPatterns = $novel,
    sp.distributed_metaverified = $mv_count
MERGE (exec)-[:PHASE_OUTPUT {order:3}]->(sp)
```

---

## 4. Phase 4 — TargetAnchor (TA)

**Question**: "Where does this recovered design fit in our KG?"

### 4.1 Inputs
- SP VR APPROVED
- TPA_TCW_Result + TPA_ST_Result + TPA_SP_Result chain complete

### 4.2 Steps
1. SemanticAnchor routing decision
   - **2-A NEW**: no existing :SemanticAnchor sufficiently overlaps → create new
   - **2-B REUSE**: existing :SemanticAnchor with overlap > 0.85 → merge into it
   - **2-C BRANCH**: partial overlap → fork as new anchor with `:SUPERSEDES` to source
2. 5-drift measurement
   - **Missing**: KG nodes referencing files/symbols not in current code
   - **Orphan**: code symbols with no matching KG Contract
   - **SigMismatch**: code signature differs from recovered Contract
   - **PatternDiv**: pattern shifted (e.g. State → Strategy)
   - **LabelRot**: KG label/relation drifted from current convention
3. coverage_ratio computation
   - `(non_drifted_recovered) / (total_recovered)`
   - if `< tpa_drift_coverage_ratio_min` (default 0.8) → SET anchor.status='SUSPENDED'
4. Final Longinus binding (TR12)
   - reverse orphan scan: every code symbol → KG node lookup
   - missing → :ReverseOrphan node logged
5. Lesson Feedback Loop fires (cycle terminal)
   - all discoveries → :Lesson nodes
   - top-priority Lessons → :ActionPlan stubs for APT /apt-scw consumption
6. Final Taliban 9-lens VR + KG log

### 4.3 Output Schema
```cypher
MERGE (ta:TPA_TA_Result {name: 'TA_' + $target + '_' + $date})
SET ta.sourcePath = $target,
    ta.routing_decision = $routing,        // '2-A new' | '2-B reuse' | '2-C branch'
    ta.semantic_anchor_name = $anchor,
    ta.coverage_ratio = $ratio,
    ta.drift_missing = $missing,
    ta.drift_orphan = $orphan,
    ta.drift_sigmismatch = $sig,
    ta.drift_patterndiv = $patt,
    ta.drift_labelrot = $label,
    ta.lesson_count = $lessons_n,
    ta.action_plan_count = $aps_n,
    ta.anchor_suspended = (ta.coverage_ratio < 0.8)
MERGE (exec)-[:PHASE_OUTPUT {order:4}]->(ta)

// Then: SemanticAnchor routing
MERGE (sa:SemanticAnchor {name: $anchor})
ON CREATE SET sa.created_via = 'tpa', sa.created_at = datetime(), sa.status = 'active'
SET sa.status = CASE WHEN $ratio < 0.8 THEN 'SUSPENDED' ELSE sa.status END
MERGE (ta)-[:ANCHORS_TO]->(sa)
```

---

## 5. Phase Detection (Hook + Orchestrator)

```cypher
MATCH (exec:TPA_Execution {name: $exec_name})
OPTIONAL MATCH (exec)-[:PHASE_OUTPUT {order:1}]->(tcw:TPA_TCW_Result)
OPTIONAL MATCH (exec)-[:PHASE_OUTPUT {order:2}]->(st:TPA_ST_Result)
OPTIONAL MATCH (exec)-[:PHASE_OUTPUT {order:3}]->(sp:TPA_SP_Result)
OPTIONAL MATCH (exec)-[:PHASE_OUTPUT {order:4}]->(ta:TPA_TA_Result)
OPTIONAL MATCH (exec)-[:HAS_VALIDATION]->(vr:ValidationResult)
WITH exec, tcw, st, sp, ta, collect(vr.phase) AS validated_phases
RETURN exec.name,
  CASE
    WHEN ta IS NOT NULL THEN 'COMPLETE (use --audit for drift recheck)'
    WHEN 'SP' IN validated_phases THEN 'Phase 4: TA (run /tpa-ta)'
    WHEN 'ST' IN validated_phases THEN 'Phase 3: SP (run /tpa-sp)'
    WHEN 'TCW' IN validated_phases THEN 'Phase 2: ST (run /tpa-st)'
    WHEN tcw IS NOT NULL THEN 'Phase 1: TCW done but unvalidated (run /taliban)'
    ELSE 'Phase 1: TCW (start with /tpa-tcw)'
  END AS current_phase
```

---

## 6. Per-AtomicSpan Enforcement (post-2026-05-06)

Same per-leaf VR enforcement that applies to APT's AtomicSpan applies to TPA's per-symbol Contract Result:

- Every recovered `:AptContract` / `:ConventionalContract` is the equivalent of an APT AtomicSpan leaf
- Each requires its own `:ValidationResult { target_phase: 'ST', verdict: 'APPROVED' }` for v0.8-per-span gate to clear
- Bulk recovery without per-symbol VR = HR17 BatchShortcutAtAnyPhase mirror (TR_BatchShortcut equivalent)

This rule applied retroactively to all post-2026-05-06 TPA cycles. Pre-2026-05-06 TPA executions are flagged `pre_hardcore=true` (mirror of APT's anchor flag) and exempt from per-AtomicSpan enforcement.

---
