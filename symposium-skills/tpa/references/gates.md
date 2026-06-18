# tpa — Gates

> **Lazy-load reference for `tpa` skill.**
> Parent skill: [`../SKILL.md`](../SKILL.md). Mirror reference: [`../../apt/references/gates.md`](../../apt/references/gates.md).
> KG: `tpa-hardening-master-plan-2026-05-06`, `per-span-gate-enforcement-canonical-2026-05-06`.

---

## 1. Phase Order Invariant (TR3)

```
TCW → [TCW Gate] → ST → [ST Gate] → SP → [SP Gate] → TA → [TA Gate / Lesson Loop]
```

`apt-gate-check.sh` v0.8-per-span (default 2026-05-06) enforces this order. Any attempt to invoke `/tpa-st` before TCW VR APPROVED returns `permissionDecision: deny`.

---

## 2. Gate Sequence Per Phase

### 2.1 TCW Gate (entry — no pre-gate)

```
1. Manifest assertion
   - find <target> -name '*.{rs,ts,py,go}' | sort > manifest.txt
   - Verify union(agent_files) == manifest_files (TR5: skipped_files = 0)

2. AST extraction ground truth
   - tree-sitter / rust-analyzer / pyright produces symbol list
   - LOC per file matches `wc -l` (TR4: AST parser mandatory)

3. Adversarial round (Naesengmoon 9-lens)
   - critic receives: symbol manifest, LOC distribution, manifest diff
   - critic MUST produce ≥ 3 findings
   - if < 3: re-invoke with stronger prompt (see adversarial.md §2)

4. ResearchProvider auto-trigger if Unknown found
   - any symbol of unrecognized syntax → /prom auto

5. Reflection (TR9)
   - REFLECTION { DISCOVERED, LESSON, QUALITY_ACTION, NEXT_GATE_CHECKS }

6. KG log (TR7)
   - TpaDecisionLog node + VR with phase='TCW'
```

### 2.2 ST Gate (TCW pre-required)

```
1. Pre-gate check (Hook)
   - MATCH (exec:TPA_Execution {status:'IN_PROGRESS_TCW'})-[:HAS_VALIDATION]->(:ValidationResult {phase:'TCW', verdict:'APPROVED'})
   - if not exists → BLOCK with permissionDecision: deny

2. Contract extraction completeness
   - every pub symbol has either AptContract OR ConventionalContract OR explicit "no contract" justification
   - giant methods (LOC > 100) deferred to SP, not skipped

3. Convention discrimination
   - AptContract requires explicit interface/trait declaration
   - ConventionalContract requires N ≥ 3 shared signatures
   - mixing labels = ontology pollution → BLOCK

4. pre/postcondition parsing
   - docstring/JSDoc/Rust-doc inspected
   - missing → field set to "NONE — code contract only" (explicit, not blank)

5. Adversarial round (Naesengmoon 9-lens)
   - critic receives: contract list, AptContract:ConventionalContract ratio, deferred giants list
   - ≥ 3 findings mandatory

6. Reflection + KG log
```

### 2.3 SP Gate (ST pre-required)

```
1. Pre-gate check (Hook)
   - ST VR APPROVED required

2. Pattern Library precondition
   - MATCH (p:DesignPattern) RETURN count(p)
   - count >= 38 (GoF23 + Distributed10 + PL5 baseline) — recommended >= 51

3. Pattern matching with mandatory checklist
   - INSTANCE_OF requires every required-element listed in pattern checklist + evidence cited
   - missing element → confidence < 0.7 → RESEMBLES (not INSTANCE_OF)
   - name-only match → confidence < 0.4 → not recorded (filtered out)

4. Distributed pattern → MetaVerifier auto-trigger
   - Any (src)-[:INSTANCE_OF]->(p:DesignPattern {category:'Distributed'})
   - 88-Naesengmoon math lens (commute / assoc / idempotent / safety / liveness)
   - VR phase='SP-MetaVerify' must exist before SP VR can APPROVE

5. Adversarial round (Naesengmoon 9-lens)
   - critic receives: pattern match list, confidence distribution, novel patterns

6. Reflection + KG log
```

### 2.4 TA Gate (SP pre-required, terminal)

```
1. Pre-gate check (Hook)
   - SP VR APPROVED required

2. SemanticAnchor routing
   - 2-A new anchor (no existing match)
   - 2-B reuse existing anchor (high overlap with prior TA)
   - 2-C branch (partial overlap, fork)

3. 5-drift measurement
   - Missing / Orphan / SigMismatch / PatternDiv / LabelRot
   - coverage_ratio = (non_drifted_recovered) / (total_recovered)

4. coverage_ratio threshold
   - if coverage_ratio < tpa_drift_coverage_ratio_min (default 0.8) → SET anchor.status='SUSPENDED'
   - else proceed to anchor finalization

5. Longinus binding (TR12)
   - every recovered Contract has (:ReferenceSite { sourcePath:file:line })
   - reverse orphan scan: every code symbol → KG node mapping

6. Final adversarial round (Naesengmoon 9-lens)
   - critic receives: anchor proposal, drift table, INSTANCE_OF/RESEMBLES distribution

7. Lesson Feedback Loop fires (cycle terminal)
   - all discoveries (Similarity / QualityGap / NovelPattern / AntiPattern) → :Lesson nodes
   - top-priority Lessons → :ActionPlan nodes for APT /apt-scw

8. Reflection + KG log
```

---

## 3. Gate Evidence Table

```
+--------------+---------------------------------------------------------------+
| Transition   | Required evidence                                             |
+--------------+---------------------------------------------------------------+
| → TCW Gate   | manifest = union(agent_files); AST parser output; LOC match   |
|              | Naesengmoon 9-lens VR APPROVED; reflection; TR5 skipped_files = 0 |
+--------------+---------------------------------------------------------------+
| → ST Gate    | TCW VR APPROVED (pre-req via Hook)                            |
|              | every pub symbol classified (Apt vs Conventional vs deferred) |
|              | giants deferred (not skipped); pre/post parsed or NONE        |
|              | Naesengmoon 9-lens VR APPROVED                                    |
+--------------+---------------------------------------------------------------+
| → SP Gate    | ST VR APPROVED (pre-req via Hook)                             |
|              | Pattern Library count ≥ 38                                    |
|              | every INSTANCE_OF has confidence + evidence + checklist       |
|              | Distributed patterns have SP-MetaVerify VR APPROVED           |
|              | Naesengmoon 9-lens VR APPROVED                                    |
+--------------+---------------------------------------------------------------+
| → TA Gate    | SP VR APPROVED (pre-req via Hook)                             |
|              | anchor routing decided (2-A / 2-B / 2-C)                      |
|              | 5-drift table computed                                        |
|              | coverage_ratio ≥ 0.8 OR status='SUSPENDED' set                |
|              | Longinus ReferenceSite per Contract                           |
|              | Final Naesengmoon 9-lens VR APPROVED                              |
|              | Lesson loop fires (≥1 :Lesson if any discovery)               |
+--------------+---------------------------------------------------------------+
```

---

## 4. Approval Gate Roles

| Gate | Who | SLA | On Timeout |
|------|-----|-----|-----------|
| TCW manifest assertion | automated | < 30s | BLOCK — re-run scan |
| Naesengmoon 9-lens (any phase) | automated subagent (sonnet) | < 60s | ESCALATE — gate blocked |
| MetaVerifier (Distributed) | automated subagent (mathematical lens) | < 90s | BLOCK — math required |
| Ground truth (parser, LOC) | automated | < 60s | BLOCK — manifest required |
| sigma_oracle (HUMAN) | HUMAN (LOCKED) | 0 (immediate) | BLOCK — re-ask |

Same `allow_agent_sigma: false` lock as APT. Auto-mode for `auto_approve_surface: true` only — surface scanning, never gate decisions.

---

## 5. Hook Integration

The `apt-gate-check.sh` v0.8-per-span (default 2026-05-06) shares its Cypher template across APT and TPA. TPA-specific entry queries:

```cypher
// TPA pre-gate query (matches existing v0.7 pattern, phase parameterized)
MATCH (exec:TPA_Execution {name: $exec_name})
      -[:HAS_VALIDATION]->(vr:ValidationResult {phase: $required_phase, verdict: 'APPROVED'})
      -[:USED_LENS]->(ls:LensSet)
WHERE ls.lensCount >= 9 AND ls.deprecated <> true
RETURN exec.name, vr.validated_at LIMIT 1
```

Per-AtomicSpan VR enforcement (post-2026-05-06) applies to TPA's `TPA_TCW_Result` / `TPA_ST_Result` / `TPA_SP_Result` outputs the same way as APT's AtomicSpan leaves.

---
