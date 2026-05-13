# tpa — Error Handling

> **Lazy-load reference for `tpa` skill.**
> Parent skill: [`../SKILL.md`](../SKILL.md). Mirror reference: [`../../apt/references/error_handling.md`](../../apt/references/error_handling.md).
> KG: `tpa-hardening-master-plan-2026-05-06`.

---

## 1. When Critic Disagrees with Recovery

```
IF critic verdict = REJECT (>= 1 BLOCKER):
  1. Recovery agent reviews BLOCKER findings
  2. For ground_truth_testable findings:
     - Manifest mismatch → re-run TCW with stricter manifest assertion
     - Parser count mismatch → re-run AST parser, compare
     - Checklist failure → revise INSTANCE_OF to RESEMBLES
  3. For non-testable findings: present to sigma_oracle with both perspectives
  4. sigma_oracle decides: re-recover | accept with confidence downgrade | escalate
  5. Log decision as TpaDecisionLog

IF critic verdict = CONDITIONAL_PASS (PERFORMANCE / drift findings):
  1. Recovery agent reviews drift findings
  2. Check 5-drift table for trend
  3. sigma_oracle decides: rescan | accept current coverage | escalate
  4. Log decision

IF critic verdict = PASS (only DESIGN_DEBT + NITPICK):
  1. Log findings as residual debt on the recovered anchor
  2. Proceed to sigma_oracle for final approval
  3. sigma_oracle may still RETURN if drift table looks sus
```

---

## 2. When Manifest Assertion Fails (TR5 violation)

```
IF union(agent_files) != manifest_files:
  1. BLOCK gate immediately (TR5 hard rule)
  2. Compute set-difference: missing_files = manifest_files - union(agent_files)
  3. Inspect missing_files:
     - Was a directory boundary missed? (v1 chunking bug — switched to manifest-based v2)
     - Was a feature-gated file (`#[cfg(...)]`) silently skipped? Re-include.
     - Was an agent timeout? Re-dispatch with smaller chunk.
  4. Spawn supplementary agent for missing_files
  5. Re-run V5 (V_TR5_skipped_files = 0)
  6. Only proceed when assertion passes
```

KG: `lesson-tpa-missing-manifest-step-2026-04-16`, `lesson-tpa-conceptual-vs-file-chunking-2026-04-16`.

---

## 3. When AST Parser Output Disagrees with Code (TR4)

```
IF parser_output.symbol_count != actual symbol count:
  1. BLOCK gate immediately
  2. Inspect parser version (tree-sitter / rust-analyzer / pyright version mismatch)
  3. If parser failed on syntax: log :Lesson with parser_failure category, fall back to a different parser
  4. Never silently substitute grep — TR4 hard rule
  5. Re-run TCW with verified parser
```

---

## 4. When Distributed Pattern Has No SP-MetaVerify VR

```
IF (src)-[:INSTANCE_OF]->(p:DesignPattern {category:'Distributed'}) AND no SP-MetaVerify VR:
  1. BLOCK SP gate progression
  2. Auto-fire 88-Taliban via MIC slot:
     MATCH (s:MethodologySlot {name:'MetaVerifier'}) RETURN s.invocation
  3. Verify mathematical properties (commute / assoc / idempotent / safety / liveness)
  4. If math verification fails:
     - Downgrade INSTANCE_OF → RESEMBLES (confidence < 0.7)
     - Log :Lesson with category='pattern_hallucination_distributed'
  5. Only proceed when SP-MetaVerify VR APPROVED OR INSTANCE_OF removed
```

---

## 5. When Coverage Ratio Below Threshold

```
IF tpa_drift_coverage_ratio < tpa_drift_coverage_ratio_min (default 0.8):
  1. SET anchor.status = 'SUSPENDED' (TR + V9)
  2. Log drift table (Missing/Orphan/SigMismatch/PatternDiv/LabelRot counts)
  3. Present to sigma_oracle:
     "Recovery coverage = X.YZ < 0.8 threshold.
      Drift breakdown: {table}.
      Options:
        (a) RESCAN — re-run TCW with larger max_agents (TR14)
        (b) ACCEPT_SUSPENDED — keep status='SUSPENDED', anchor not active
        (c) DOWNGRADE_THRESHOLD — request user override of 0.8 (logged in MethodologyConfig)
        (d) ABORT_TPA_CYCLE — recovered set too lossy, abandon"
  4. sigma_oracle decides
  5. Log TpaDecisionLog with override_reason if (c)
```

---

## 6. When Pattern Library Is Empty or Stale

```
IF count((:DesignPattern)) < 38:
  1. BLOCK SP gate
  2. Log :Lesson category='pattern_library_drought'
  3. Bootstrap fallback:
     - Reload from MIND/lean_formalization/design_patterns/ (canonical set)
     - Or fire ResearchProvider (Prometheus) for missing categories
  4. Re-check count >= 38 before proceeding

IF Pattern Library version drift suspected:
  1. Compare DesignPattern node count against MethodologyConfig.tpa_pattern_library_size (default 51)
  2. If diff > 10%, re-canonicalize via :CanonicalPattern audit
```

---

## 7. When sigma_oracle Does Not Respond

Same as APT (§9.3 of `apt/references/error_handling.md`). DO NOT proceed, DO NOT auto-approve. Re-state the question and wait.

TPA-specific: include drift table + coverage ratio in the re-statement. Without those, the human cannot make an informed decision.

---

## 8. When TR14 Triggers Mid-Cycle (large repo)

```
IF (during TCW) total_loc > 10000 AND parallel.max_agents = 1:
  1. PAUSE TCW execution
  2. Compute N = ceil(total_loc / loc_per_agent)
     - haiku: 5K LOC/agent
     - sonnet: 10K LOC/agent
     - opus: 20K LOC/agent
  3. Update tpa-config.yaml parallel.max_agents = N (or use pre-set)
  4. Re-dispatch with file-level partition (TR14 v2 manifest-based)
  5. Verify post-dispatch: union(agent_files) == manifest_files
  6. Resume TCW
```

KG: `lesson-tpa-gap-large-repo-chunking-2026-04-14`.

---

## 9. When Lesson Loop Stalls (loop drift)

```
IF :Lesson resolved=false AND created_at < (now - 7 days) AND no :ActionPlan linked:
  1. Auto-create :ActionPlan stub:
     MERGE (p:ActionPlan {name:'AP-AUTO-' + lesson.name})
     SET p.priority='HIGH', p.created_at=datetime(), p.auto_generated=true
     MERGE (lesson)-[:TRIGGERS]->(p)
  2. Surface to sigma_oracle next session:
     "Stale Lesson detected: {lesson.name}, age={days}d, no ActionPlan."
  3. sigma_oracle decides: schedule APT cycle | dismiss as no longer relevant | escalate
  4. Log decision

IF :Lesson resolved=true but no evidence field:
  1. V14 violation
  2. BLOCK acceptance
  3. Require resolution evidence (commit hash, VR, etc.) before accepting
```

---

## 10. Critic-Recovery Both Wrong (Meta-Failure)

```
IF sigma_oracle detects both agents converged on wrong recovery:
  1. sigma_oracle provides correction (e.g. "this is actually a State pattern, not Strategy")
  2. Log as TpaFeedback category='RecoveryMetaFailure'
  3. Reset to earlier phase if needed (typically SP, sometimes ST)
  4. Record in KG (Lesson + ActionPlan to prevent recurrence)
  5. Rotate both models for next cycle
  6. Update Pattern Library checklist if the failure mode reveals a missing element
```

---

## 11. Parallel Execution Rules (TPA-specific)

| Rule | Description |
|------|-------------|
| ManifestPartition | TR14 v2: file-level partition, never directory-level |
| ChunkOverlap | ≤ 0% overlap between agents (TR5: skipped_files = 0 means no double-counting either) |
| MergeContract | Each agent returns FullFindingRecord JSON; parent UNWIND merges in single transaction |
| FailFast | Any agent skipping a file → manifest assertion FAILS → entire cycle BLOCKS |
| ReSeed | If supplementary agent needed, re-seed via SubagentTaskSpec (재배맨) |

---
