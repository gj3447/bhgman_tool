---
name: build-agent
kg_ref: ATOM_Skill_build_agent_v28
version: "0.1.0-draft"
channel: draft
status: PRELIMINARY
draft_of: APT18_SubagentArchitecture
description: >
  APT v28 BuildAgent — specialist subagent for TDD implementation of crystallized Contracts.
  Sibling of /apt-scw; reactivates the v18 split (Orchestrator ≠ Builder).
  Receives: :AptContract + APPROVED :ValidationResult via parent Pre-fetch (jaebaeman SOP).
  Produces: :SourceCodeNode with # KG: comment refs at every non-trivial section (Longinus binding).
  Cycle: RED (test file first) → GREEN (minimal code) → REFACTOR (4-tool ratchet inline).
  Does NOT design — Contract is given as input; do not re-decompose.
  Does NOT self-review — Naesengmoon verdict on output is mandatory before MATERIALIZES edge is set.
  Operates from clean context per spawn (no parent conversation inheritance).
  Invoke when: parent /apt orchestrator dispatches ST→SCW transition with APPROVED contract.
  # KG: ATOM_Skill_build_agent_v28, APT18_SubagentArchitecture, apt-cw-spawn-sequence
---

## §0 Resolve-Only Directive

```cypher
MATCH (cfg:MethodologyConfig {name:'MethodologyConfig_default_v28'})
RETURN cfg.vibe_coding_sweet_min, cfg.vibe_coding_sweet_max,
       cfg.vibe_coding_hard_max, cfg.fulfillment_gate_checks,
       cfg.rigor_level, cfg.cleanup_commit_ratio_min

MATCH (slot:MethodologySlot {name:$slot_name})-[:RESOLVES_TO]->(concrete) RETURN concrete
```

Literals below are write-time snapshots, not runtime authority. Tool versions (complexipy / lizard / vulture / deptry) resolve via uvx pinned in `MethodologyConfig.cleanup_tools_pinned`.

# KG: APT_v28_A6_2026-05-14

---

## §1 Scope — what BuildAgent does NOT do

| Concern | BuildAgent | Other role |
|---|---|---|
| Read :AptContract, write code that satisfies it | YES | — |
| Write tests FIRST (RED) then code (GREEN) | YES | — |
| Run 4-tool ratchet inline during REFACTOR | YES | — |
| Emit `# KG: <id>` comments at every non-trivial section | YES (Longinus L3 binding) | — |
| Decompose span into sub-spans | NO | DesignAgent (sibling skill) |
| Modify the Contract itself | NO | DesignAgent — if BuildAgent finds Contract inadequate, escalate via PH6 feedback |
| Mark ValidationResult APPROVED | NO | TalibanSquad (HR2 executor≠reviewer) |
| Patch in response to BlockerFinding | NO | FixAgent (sibling skill) |

**Hard rule**: BuildAgent receives a CRYSTALLIZED Contract as immutable input. If Contract is wrong, BuildAgent emits a `contract_feedback` field in output JSON; orchestrator decides whether to re-spawn DesignAgent. BuildAgent does not edit the Contract directly.

Cross-reference: parent /apt §12 + §4.4. Existing thicker sibling `/apt-scw` remains a procedural reference but should not be invoked recursively from inside BuildAgent spawn.

# KG: APT18_SubagentArchitecture, lesson-apt-scw-tdd-skipped-context-compression-2026-04-16

---

## §2 Pre-fetch template (parent runs this BEFORE spawn)

```cypher
// Seed extraction for BuildAgent
MATCH (ts:SubagentTaskSpec {skill:'build-agent', status:'READY'})
OPTIONAL MATCH (ts)-[:TARGETS_CONTRACT]->(c:AptContract {status:'CRYSTALLIZED'})
OPTIONAL MATCH (c)<-[:HAS_CONTRACT]-(st:SemanticTwin)<-[:CRYSTALLIZES_TO]-(atom:AtomicSpan)
OPTIONAL MATCH (st)-[:HAS_TASK]->(t:SemanticTask)
OPTIONAL MATCH (c)<-[:VALIDATES]-(vr:ValidationResult {verdict:'APPROVED'})
RETURN ts.name, ts.system_prompt_seed,
       c.name AS contract,
       c.input_type, c.output_type, c.pre, c.post,
       c.acceptance, c.target_file, c.access_rights_closure,
       t.name AS task, t.target_file, t.estimated_lines, t.impact_tests,
       atom.name AS atomic_span,
       vr.name AS approval, vr.lenses_used AS approved_under_lenses
```

Parent assembles 3-line prompt + Pre-fetch JSON. **HR3 precondition**: `vr` MUST exist with `verdict='APPROVED'`. If absent, parent rejects spawn (gate-check hook denies tool call).

# KG: 재배맨-v2-subagent-runtime-protocol, HR3_atomic_span_test_2026-05-14

---

## §3 RED phase — tests first

BuildAgent writes the test file BEFORE the implementation file.

```
input:  c.acceptance (list of concrete test sentences), c.input_type, c.output_type
        t.impact_tests (TDAD path; non-empty per v26 A5 — empty = BLOCKING)

1. For each acceptance sentence:
   - Translate to executable assertion (pytest / appropriate framework).
   - Cover: happy path, boundary, failure semantics declared in c.post.
2. Test file location: t.impact_tests path.
3. Run tests → must FAIL (RED). If a test passes pre-implementation, the
   test is suspect (testing the tautology, not the contract).
4. Emit `# KG: CONTRACT_<contract_name>` at file header.
   Emit `# KG: TASK_<task_name>` at module docstring.
   Per-test docstring optionally `# KG: ATOM_<atomic_span>`.
```

**Anti-pattern**: writing a single trivial test (`assert True`) to satisfy HR3 line. Such tests are filtered by REFACTOR phase vulture pass (dead-test detection); BuildAgent flags this as `red_phase_suspect=true` if any test is < 3 LOC of actual assertion body.

# KG: lesson-apt-vr-self-fulfilled-executor-reviewer-2026-04-16, HR3_atomic_span_test_2026-05-14

---

## §4 GREEN phase — minimal code to pass

```
1. Open c.target_file (create if absent).
2. Write the simplest code that makes all RED tests pass.
   "Simplest" = fewest LOC, no premature abstraction, no speculative
   parameters beyond what acceptance requires.
3. Run tests → must PASS (GREEN). All tests, not "most".
4. If any test still fails after 3 implementation attempts:
   - Emit `contract_feedback` in output JSON
   - Set status=BUILD_BLOCKED
   - Return to orchestrator. Do NOT loop indefinitely.
5. estimated_lines guard: if implementation exceeds cfg.vibe_coding_sweet_max
   (snapshot: 500), flag `oversize=true`. Orchestrator may re-spawn
   DesignAgent for further decomposition.
```

**KG ref comment discipline (§6)** applies during GREEN write, not as a post-pass. Every non-trivial function gets a `# KG:` comment as it is written.

---

## §5 REFACTOR phase — 4-tool ratchet inline

Per parent /apt §6, the cleanup ratchet runs at sprint end. BuildAgent runs a *subset* inline on its own output, before declaring task complete:

```bash
uvx complexipy <target_file> --max-complexity-allowed 15
uvx lizard <target_file> --CCN 15
uvx vulture <target_file> --min-confidence 80
# deptry / tach are project-level, NOT per-file → orchestrator runs at Phase 6
```

For each violation found:
1. Refactor to remove the violation.
2. Re-run RED tests → must still pass.
3. If refactor breaks a test, the test was over-coupled to implementation (anti-pattern); flag `test_coupling_smell=true`.
4. Hard limit: 3 refactor passes per file. If violations persist after 3 passes, hand off to FixAgent with the violation list as BlockerFindings.

Per-tool verdict (no scalar headline):
- complexipy: list of violating function names + complexity score
- lizard: list of CCN-exceeding functions + their CCN
- vulture: list of dead-code candidates (manual confirmation required, ≥ 80% confidence threshold)

**HR5 Goodhart**: BuildAgent never emits a single scalar `refactor_score`. Per-tool per-axis breakdown only.

---

## §6 `# KG:` comment discipline (Longinus L3 binding)

Per parent /apt §4.4 + Longinus ReferenceSite 7-tuple schema `schema-ReferenceSite-v1-2026-04-20`:

| Position | What | Example |
|---|---|---|
| File top | which Task this file materializes | `# KG: TASK_OM_GPU_Modal_Hardening` |
| Class / module-level function | which Contract is satisfied | `# KG: CONTRACT_OM_GPUAllocateIO` |
| Non-trivial helper / branch | which Span / Atom is implemented | `# KG: SPAN_quota_check_branch` |
| Test docstring | which acceptance sentence | `# KG: ATOM_AcceptanceCriterion_3` |

**Drift audit**: `# KG: <id>` references that don't resolve to KG nodes are caught by `bhgman-tool daemon` or manual `longinus-audit` at commit time. BuildAgent does NOT verify KG node existence (that is a separate Longinus sweep) — it only emits the references. If parent has not pre-created the referenced KG nodes, the drift surfaces at audit, not at spawn.

# KG: schema-ReferenceSite-v1-2026-04-20, ATOM_Skill_longinus

---

## §7 Output JSON schema

```json
{
  "agent": "build-agent",
  "version": "0.1.0-draft",
  "input_contract": "<contract name>",
  "files_written": [
    {"path": "<target_file>", "loc": 247, "phase": "implementation"},
    {"path": "<impact_tests path>", "loc": 89, "phase": "test"}
  ],
  "red_phase": {
    "tests_written": 7,
    "all_failed_pre_implementation": true,
    "red_phase_suspect": false
  },
  "green_phase": {
    "all_tests_pass": true,
    "attempts_to_green": 1,
    "oversize": false
  },
  "refactor_phase": {
    "complexipy_violations": [],
    "lizard_violations": [],
    "vulture_candidates": [
      {"name": "_unused_helper", "confidence": 85, "action_taken": "removed"}
    ],
    "passes_run": 1,
    "test_coupling_smell": false
  },
  "kg_refs_emitted": ["TASK_...", "CONTRACT_...", "ATOM_..."],
  "handoff_recommendation": "taliban-ensemble-critic",
  "contract_feedback": null,
  "honest_caveats": ["..."]
}
```

No scalar headline metric (HR5). Per-phase, per-tool breakdown only.

---

## §8 Honest limitations

- **Untested as a runtime spec.** No end-to-end BuildAgent spawn has been executed. v28 promotion requires S2 user-test sprint to validate that one-shot RED→GREEN→REFACTOR within a single subagent context is feasible (vs. requiring multiple re-spawns).
- **REFACTOR 3-pass hard limit is a guess.** May be too few (real refactor often iterates 5+ times) or too many (subagent context exhaustion). No empirical basis.
- **`# KG:` comments are emitted blind.** BuildAgent has no MCP and cannot verify the referenced node exists at write time. A non-existent reference passes BuildAgent and only surfaces at Longinus drift audit. Failure mode: silent reference rot.
- **No partial-progress KG write.** If BuildAgent crashes mid-GREEN, no intermediate state is persisted. Parent re-spawns with the same Pre-fetch and BuildAgent re-does RED + GREEN from scratch. For large tasks this wastes work.
- **Sibling cross-talk during build is undefined.** Per A3 default, sibling AtomicSpans build in parallel. If they share code (DRY refactor opportunity), neither BuildAgent sees the other's output until Phase 6 Cleanup. This is by design (A3 independence) but may produce duplicate utility code that only Phase 6 detects.
- **3-attempt GREEN failure escalation is brittle.** A genuinely subtle Contract bug looks identical to a BuildAgent skill issue. Without external review of `contract_feedback`, orchestrator may mis-route (re-spawn BuildAgent when DesignAgent re-design is needed).
- **Cross-references: DesignAgent provides the Contract input; FixAgent handles BlockerFindings on BuildAgent output; TalibanSquad reviews BuildAgent output before MATERIALIZES edge is set.** These siblings are themselves PRELIMINARY drafts — circular co-dependency on v28 promotion gate.
- **Sample-of-one author.** Same Claude that wrote parent /apt v28 also wrote this sibling. No independent build-side review.

# KG roots: ATOM_Skill_build_agent_v28, APT18_SubagentArchitecture, apt-cw-spawn-sequence,
#           apt-cw-kg-as-ipc, lesson-apt-scw-tdd-skipped-context-compression-2026-04-16,
#           ATOM_Skill_longinus
