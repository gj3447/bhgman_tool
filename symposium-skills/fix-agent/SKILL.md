---
name: fix-agent
kg_ref: ATOM_Skill_fix_agent_v28
version: "0.1.0-draft"
channel: draft
status: PRELIMINARY
draft_of: APT18_SubagentArchitecture
description: >
  APT v28 FixAgent — specialist subagent that consumes :BlockerFinding nodes from TalibanSquad,
  proposes :ProposedPatch nodes, and re-dispatches to TalibanSquad for verification until
  verdict ≠ REJECT or cfg.fix_agent_max_attempts exhausted.
  Implements UserPrinciple_SelfCorrecting_APT: user σ_oracle intervention ONLY at final exit,
  NOT at every retry. If user must catch every defect, FixAgent is failing (K-01 BLOCKER).
  Sibling of DesignAgent + BuildAgent + TalibanSquad. Operates from clean context per spawn.
  Does NOT critique — that is TalibanSquad's role. FixAgent fixes what TalibanSquad found.
  Invoke when: any BlockerFinding emitted by TalibanSquad needs remediation before phase progression.
  # KG: ATOM_Skill_fix_agent_v28, UserPrinciple_SelfCorrecting_APT, APT18_SubagentArchitecture
---

## §0 Resolve-Only Directive

```cypher
MATCH (cfg:MethodologyConfig {name:'MethodologyConfig_default_v28'})
RETURN cfg.fix_agent_max_attempts, cfg.fix_agent_escalation_severity,
       cfg.rigor_level

MATCH (slot:MethodologySlot {name:$slot_name})-[:RESOLVES_TO]->(concrete) RETURN concrete
```

Literal `cfg.fix_agent_max_attempts` write-time snapshot = 3. Runtime authority is the KG slot, not this prose.

# KG: APT_v28_A6_2026-05-14, UserPrinciple_SelfCorrecting_APT

---

## §1 Scope — what FixAgent does NOT do

| Concern | FixAgent | Other role |
|---|---|---|
| Read :BlockerFinding, propose concrete patch | YES | — |
| Apply patch to code (write/edit file) | YES (within the patch scope only) | — |
| Re-dispatch TalibanSquad for verification | YES (via orchestrator) | — |
| Decide when to escalate to user σ_oracle | YES (per §5 termination) | — |
| Critique TalibanSquad's verdict | NO | (no role — verdicts are external by HR2) |
| Re-decompose the span | NO | DesignAgent (if root cause is structural) |
| Rewrite the Contract | NO | DesignAgent — FixAgent emits `escalate_to_design=true` |
| Rebuild from scratch | NO | BuildAgent — FixAgent emits `escalate_to_build=true` if patch scope insufficient |
| Mark verdict APPROVED | NO | TalibanSquad (HR2) |

**Hard rule**: FixAgent ONLY proposes patches in the scope of the BlockerFinding. If the finding's root cause is upstream (Contract wrong, span ill-decomposed), FixAgent escalates rather than papering over.

Cross-reference: TalibanSquad (`taliban-ensemble-critic`) is the re-verifier in the loop. DesignAgent / BuildAgent are upstream escalation targets.

# KG: UserPrinciple_SelfCorrecting_APT, HR2_external_reviewer_2026-05-14

---

## §2 Pre-fetch BlockerFinding

```cypher
// Seed extraction for FixAgent spawn
MATCH (ts:SubagentTaskSpec {skill:'fix-agent', status:'READY'})
OPTIONAL MATCH (ts)-[:TARGETS_FINDING]->(bf:BlockerFinding)
OPTIONAL MATCH (bf)<-[:EMITTED_FINDING]-(vr:ValidationResult)
OPTIONAL MATCH (bf)-[:CITES]->(target)
OPTIONAL MATCH (bf)<-[:RESOLVES]-(prior:ProposedPatch)<-[:ATTEMPTED_BY]-(prior_attempt:CorrectionAttempt)
RETURN ts.name, ts.system_prompt_seed,
       bf.name AS finding, bf.severity, bf.lens, bf.description,
       bf.evidence, bf.proposed_corrective_action,
       vr.name AS source_validation, vr.lenses_used,
       collect(DISTINCT target.name) AS cited_targets,
       collect(DISTINCT {patch: prior.name, attempt: prior_attempt.attempt_number,
                         verdict: prior_attempt.verdict}) AS prior_attempts
```

**Critical**: `prior_attempts` count is the loop counter. If `size(prior_attempts) >= cfg.fix_agent_max_attempts`, parent SHOULD NOT spawn FixAgent again — instead escalate to user σ_oracle (§5).

# KG: 재배맨-v2-subagent-runtime-protocol, taliban-ensemble-critic

---

## §3 Patch proposal generation

```
input:  BlockerFinding bf with severity, lens, evidence, proposed_corrective_action
        prior_attempts (list of (patch, verdict) tuples)

1. Classify root cause:
   a. SURFACE — typo, missing import, off-by-one, simple logic bug.
      Action: direct code edit within the cited target's scope.
   b. CONTRACT_MISMATCH — code does what Contract says but Contract is wrong.
      Action: emit escalate_to_design=true. Do NOT patch.
   c. DESIGN_FLAW — span itself is mis-decomposed.
      Action: emit escalate_to_design=true with structural_smell field.
   d. EXTERNAL_DEPENDENCY — failing tool version, missing service.
      Action: emit escalate_to_user=true; FixAgent cannot resolve.

2. For SURFACE class:
   a. Read cited target file(s).
   b. Generate ONE concrete patch (diff format).
   c. Patch scope = ONLY the cited target. Do NOT touch unrelated files.
   d. Run BlockerFinding's stated reproduction (if any) → patch must address it.
   e. Run pre-existing tests (RED phase output from BuildAgent) → patch must
      not regress any passing test.

3. If prior_attempts contains a similar patch (already tried, already rejected):
   - Do NOT repeat. Loop detector: hash patch by AST shape; if hash matches
     prior attempt, escalate with reason="patch_repetition_loop".

4. Emit :ProposedPatch node (orchestrator writes; FixAgent returns JSON spec).
```

**Anti-pattern**: "broaden the patch until it passes" — i.e., touching more files each retry. FixAgent is required to NARROW scope or escalate, not broaden. Broadening is a form of rubber-stamp at the patch level.

# KG: lesson-agent-learns-from-verdict-not-success-2026-04-27

---

## §4 Re-dispatch loop

The loop is orchestrator-driven; FixAgent itself is one-shot per BlockerFinding per attempt.

```
Orchestrator loop (NOT inside FixAgent):

attempt = 1
while attempt <= cfg.fix_agent_max_attempts:
    spawn FixAgent(bf, prior_attempts)
    collect FixAgent output JSON
    if output.escalate_to_design or output.escalate_to_user:
        break  → §5 termination
    apply ProposedPatch to filesystem (via parent Edit/Write tool)
    write :CorrectionAttempt {attempt_number: attempt, patch: <patch>} to KG
    spawn TalibanSquad re-verification on patched output
    collect new ValidationResult
    if vr.verdict != REJECT:
        write :CorrectionAttempt.verdict = vr.verdict
        break  → success exit
    else:
        prior_attempts.append((patch, REJECT))
        attempt += 1

if attempt > cfg.fix_agent_max_attempts:
    → §5 termination (max_attempts exhausted)
```

**KG-as-IPC discipline**: FixAgent does not call TalibanSquad directly. Orchestrator re-dispatches via SubagentTaskSpec. The loop state is in KG (prior_attempts via :ATTEMPTED_BY edges), not in FixAgent's context.

# KG: apt-cw-kg-as-ipc, taliban-ensemble-critic

---

## §5 Loop termination

Three terminal states; each writes to KG with explicit reason:

| Terminal | Trigger | KG state |
|---|---|---|
| **SUCCESS** | latest re-verification verdict ≠ REJECT | `:CorrectionAttempt {status:'SUCCESS', verdict: <new>}` + `:BlockerFinding {status:'RESOLVED'}` |
| **MAX_ATTEMPTS** | attempt counter > `cfg.fix_agent_max_attempts` | `:CorrectionAttempt {status:'MAX_ATTEMPTS_EXHAUSTED'}` + escalate to user σ_oracle |
| **ESCALATED** | FixAgent classified root cause as CONTRACT_MISMATCH / DESIGN_FLAW / EXTERNAL_DEPENDENCY | `:CorrectionAttempt {status:'ESCALATED', target: design\|build\|user}` |

**User σ_oracle boundary**: user is invoked ONLY at MAX_ATTEMPTS or ESCALATED, NEVER between retries. Per `UserPrinciple_SelfCorrecting_APT`:

> If user has to manually catch every defect at every retry, FixAgent is failing — system is not self-correcting. This is the K-01 BLOCKER pattern at framework level.

When user is invoked, FixAgent provides the full attempt log (all prior patches, all prior verdicts) so user makes an informed sigma-oracle call, not a blind one.

# KG: UserPrinciple_SelfCorrecting_APT, K-01-rubber-stamp-pattern

---

## §6 KG write — :ProposedPatch + :CorrectionAttempt

Orchestrator (NOT FixAgent itself) writes per jaebaeman Phase 4 UNWIND batch:

```cypher
// ProposedPatch node
MERGE (p:ProposedPatch {name: $patch_name})
SET p.diff = $diff_text,
    p.scope_files = $files_touched,
    p.classification = $surface_or_escalate,
    p.proposed_at = datetime(),
    p.fingerprint_ast_hash = $ast_hash  // for loop detection
MERGE (p)-[:RESOLVES]->(:BlockerFinding {name: $bf_name})

// CorrectionAttempt node (the loop record)
MERGE (ca:CorrectionAttempt {name: $attempt_name})
SET ca.attempt_number = $n,
    ca.status = $terminal_state,
    ca.verdict = $taliban_reverify_verdict,
    ca.attempted_at = datetime()
MERGE (ca)-[:ATTEMPTED_BY]->(p)
MERGE (ca)-[:RE_VERIFIED_BY]->(:ValidationResult {name: $new_vr_name})
```

Per HR5 Goodhart safeguard: no scalar `fix_quality_score` emitted. Per-axis breakdown (classification + patch_size_loc + tests_affected) only.

# KG: schema-ReferenceSite-v1-2026-04-20, jaebaeman Phase 4

---

## §7 Honest limitations

- **Untested as a runtime spec.** v0.1.0-draft. The self-correcting loop has never run end-to-end. v28 promotion gate requires demonstrating at least one (BlockerFinding → patch → TalibanSquad re-verify → SUCCESS) cycle without user intervention.
- **`cfg.fix_agent_max_attempts=3` is a guess.** May be too low (real bugs often need 5+ attempts with insight from prior failures) or too high (3 wrong patches signals deeper issue regardless). No empirical basis. Tuning is itself an unresolved sub-sprint.
- **Root cause classification is hard.** Distinguishing SURFACE vs. CONTRACT_MISMATCH vs. DESIGN_FLAW from a BlockerFinding text alone is interpretive. FixAgent may mis-classify, paper over a structural issue with a surface patch, and rubber-stamp through Naesengmoon re-verify by accident.
- **AST hash loop detector is shallow.** Two semantically-equivalent patches with different variable names produce different AST hashes; FixAgent loops re-proposing the same fix in disguise. Mitigation requires semantic patch equivalence detection, which is unimplemented.
- **TalibanSquad re-verification is itself fallible.** If FixAgent + TalibanSquad reach mutual rubber-stamp (FixAgent proposes patch that satisfies the *letter* of TalibanSquad's stated criterion but not the *spirit*), the SUCCESS terminal is false. HR2 catches executor=reviewer at the agent level but not at the patch level. **This is the actually concerning limitation.**
- **No mechanism to detect "fixed but worse"**: a patch may resolve the cited BlockerFinding but introduce new defects in scope-adjacent code that the original review didn't surface. Re-verify uses the same LensSet as original review and may miss orthogonal new issues.
- **σ_oracle escalation timing is binary**: user is either uninvolved (during retries) or invoked at terminal. There is no intermediate "advisory" state where user can nudge classification without committing to full sigma-oracle decision. May produce surprise escalations.
- **Cross-references: TalibanSquad (`taliban-ensemble-critic`) provides input BlockerFindings and re-verifies patches; DesignAgent / BuildAgent are upstream escalation targets.** All siblings are themselves PRELIMINARY drafts.
- **Sample-of-one author.** Same Claude that authored the failure pattern this skill claims to fix (K-01 framework-level rubber-stamp) also wrote this remedy. The remedy has not been independently reviewed.

---

## §8 Rubber-stamp recurrence mitigation (K-01 patch level)

### §8.1 The risk

The FixAgent → TalibanSquad re-verify loop can converge to a *local optimum rubber-stamp*: FixAgent emits a :ProposedPatch that satisfies the **literal text** of the original :BlockerFinding while ignoring its **spirit**, and TalibanSquad re-verifies using the **same LensSet** that produced the BlockerFinding — so the same lens UNION that named the defect cannot, in general, surface "this patch is letter-compliant tautology" as a new finding. The loop terminates SUCCESS without external sigma_oracle ever seeing the patch.

This is the K-01 pattern (executor = reviewer at meaningful resolution) recurring at the **patch level**. APT v28 HR2 (executor != reviewer at the agent-spawn level) catches K-01 between agents but **not between successive patches by the same FixAgent reviewed by the same LensSet UNION**. HR2 alone is insufficient because the executor/reviewer identities differ as agents while their *epistemic basis* (the lenses) overlaps.

Canonical KG: `lesson-fixagent-taliban-mutual-rubberstamp-2026-05-14`.

### §8.2 Mitigation 1: Orthogonal-lens cross-check

Every Nth retry attempt (`cfg.fix_agent_orthogonal_lens_every_n_attempts`, default 2), re-verification MUST use a LensSet UNION that is **disjoint from** (or at minimum non-equal to) the LensSet UNION of the original BlockerFinding. The orthogonal LensSet is chosen by rotation through registered :LensSet nodes, excluding those already used in `prior_attempts`.

```
attempt 1: original_lens_union (e.g., constitutional + longinus)
attempt 2: orthogonal_lens_union (e.g., solid + lakatos + mathematical)
attempt 3: rotated back, but minus any lens that appeared in attempt 1 if size permits
```

```cypher
MERGE (att:CorrectionAttempt {name: $attempt_name})
SET att.attempt_number = $n,
    att.lens_set_used = $current_lens_union,         // list of lens names
    att.previous_lens_set = $prior_attempt_lens_set, // from attempt n-1
    att.orthogonality_check = (size([l IN $current_lens_union
                                     WHERE l IN $prior_attempt_lens_set]) = 0)
MERGE (att)-[:RE_VERIFIED_BY_LENSES]->(:LensSet {name: $current_lens_union_name})
```

If `att.orthogonality_check = false` on an attempt where `n % cfg.fix_agent_orthogonal_lens_every_n_attempts = 0`, the orchestrator MUST re-spawn TalibanSquad with a different LensSet before recording a verdict on this attempt.

### §8.3 Mitigation 2: Patch-fuzzing critique sublens

Define a new lens type `:PatchFuzzingLens` whose target is the **:ProposedPatch itself**, not the artifact under repair. Its core questions:

- "Does this patch resolve the BlockerFinding only by matching its literal wording, or does it address the underlying defect?"
- "Would a minor perturbation of the BlockerFinding text (paraphrase, synonym substitution) leave the patch still 'satisfying' the new wording trivially?"
- "Is the patch tautological with respect to the failing assertion — e.g., does it modify the assertion rather than the cause?"
- "Does the patch narrow the failure surface (good) or broaden the test/contract tolerance (suspect)?"

This lens is registered as a :LensSet member and added to the **FixAgent re-dispatch path only**, NOT to the original BlockerFinding generation path. The asymmetry is intentional: patch-fuzzing critiques the remedy, not the diagnosis.

```cypher
MERGE (pfl:LensSet:PatchFuzzingLens {name: 'lensset-patch-fuzzing'})
SET pfl.target_kind = 'ProposedPatch',
    pfl.applies_in = 'FixAgent_reverify',
    pfl.lensCount = 4
MERGE (pfl)-[:HAS_LENS]->(:LensDefinition {name: 'lens-pf-literal-compliance'})
MERGE (pfl)-[:HAS_LENS]->(:LensDefinition {name: 'lens-pf-perturbation-stability'})
MERGE (pfl)-[:HAS_LENS]->(:LensDefinition {name: 'lens-pf-tautology'})
MERGE (pfl)-[:HAS_LENS]->(:LensDefinition {name: 'lens-pf-narrow-vs-broaden'})
```

### §8.4 Mitigation 3: Attempt-cap sigma_oracle injection

After `cfg.fix_agent_max_attempts_before_human` (default 3) consecutive REJECT verdicts, the orchestrator MUST escalate to **human sigma_oracle directly**, even if Mitigations 1 and 2 are still rotating. The escalation is non-suppressible: no auto-accept verdict on attempt N+1 is permitted.

This is the last-resort fallback when orthogonal-lens rotation and patch-fuzzing both fail to break a local optimum (e.g., FixAgent is consistently mis-classifying root cause as SURFACE when it is CONTRACT_MISMATCH, and no LensSet rotation can surface a contract-level smell).

```cypher
MATCH (fix_run:FixAgentRun {name: $run_name})-[:HAS_ATTEMPT]->(att:CorrectionAttempt)
WHERE att.verdict = 'REJECT'
WITH fix_run, count(att) AS reject_count
WHERE reject_count >= $max_attempts_before_human
SET fix_run.status = 'ESCALATED_TO_SIGMA_ORACLE',
    fix_run.escalation_reason = 'M8_3_attempt_cap_reached'
RETURN fix_run.name, reject_count
// orchestrator surfaces full attempt log + all prior LensSets + all patch diffs to user
```

### §8.5 Combined enforcement Cypher

A single Cypher gate runs at the end of every FixAgent loop iteration (attempt ≥ 2). Failure of all three mitigations on a `verdict = APPROVED` candidate forces escalation:

```cypher
MATCH (fix_run:FixAgentRun {name: $run_name})
OPTIONAL MATCH (fix_run)-[:HAS_ATTEMPT]->(att:CorrectionAttempt)
WITH fix_run,
     count(att) AS attempts,
     collect(att.orthogonality_check) AS ortho_checks,
     collect(att.patch_fuzzing_lens_applied) AS fuzzing_applied,
     collect(att.verdict) AS verdicts
WHERE attempts >= 2
  AND NOT any(c IN ortho_checks WHERE c = true)
  AND NOT any(f IN fuzzing_applied WHERE f = true)
RETURN 'M8_RUBBER_STAMP_RISK' AS block_reason,
       attempts, ortho_checks, fuzzing_applied, verdicts
// any row returned → orchestrator MUST escalate to human sigma_oracle;
// do NOT record a SUCCESS terminal on this fix_run.
```

Per HR5 Goodhart safeguard, this gate emits a per-axis breakdown (`attempts`, `ortho_checks`, `fuzzing_applied`, `verdicts`) and does NOT compute a scalar "mitigation_score". Each axis is independently inspectable.

### §8.6 Honest limitations of this mitigation

- **Orthogonal-lens trades off against lens overlap.** Fully disjoint LensSet UNIONs may be impossible for some targets — `constitutional`, `longinus`, `solid` share concerns at the boundary (e.g., interface-clarity appears in multiple). "Disjoint" here means *name-level disjoint*, not *concern-level disjoint*. Real concern overlap can defeat the cross-check.
- **Patch-fuzzing is recursive.** Who critiques the patch-fuzzing lens? If FixAgent learns the patch-fuzzing lens's questions, it can rubber-stamp those too. Turtles all the way down — acknowledged, no formal termination.
- **`cfg.fix_agent_max_attempts_before_human = 3` is arbitrary.** No empirical basis. May be too low (real bugs sometimes need 5+ informed retries) or too high (3 wrong patches already signals a deeper issue). Requires empirical calibration; this mitigation does not provide one.
- **Same author wrote both the FixAgent spec and this mitigation.** Identical K-01 at the meta-meta level — Claude diagnosed the FixAgent rubber-stamp risk AND wrote the mitigation. External reviewer for §8 itself has not occurred. Cf. §7 sample-of-one note.
- **Mitigation status: PRELIMINARY.** No empirical run of FixAgent + TalibanSquad has been executed with these three mitigations active. The Cypher gates compile against the v28 schema but have not been triggered by a real failure trajectory. v28 promotion gate must include at least one (BlockerFinding → 3 patch attempts → M8 escalation OR M8 pass) cycle as evidence.

# KG: lesson-fixagent-taliban-mutual-rubberstamp-2026-05-14, K-01-rubber-stamp-pattern,
#     HR2_external_reviewer_2026-05-14, taliban-ensemble-critic

# KG roots: ATOM_Skill_fix_agent_v28, UserPrinciple_SelfCorrecting_APT,
#           APT18_SubagentArchitecture, apt-cw-kg-as-ipc, taliban-ensemble-critic,
#           K-01-rubber-stamp-pattern, lesson-agent-learns-from-verdict-not-success-2026-04-27,
#           lesson-fixagent-taliban-mutual-rubberstamp-2026-05-14
