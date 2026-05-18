# tpa — Adversarial

> **Lazy-load reference for `tpa` skill.**
> Parent skill: [`../SKILL.md`](../SKILL.md). Mirror reference: [`../../apt/references/adversarial.md`](../../apt/references/adversarial.md).
> KG: `tpa-hardening-master-plan-2026-05-06`.

---

## 1. Adversarial Targets — TPA-Specific

TPA's critic attacks **recovery claims**, not design proposals. The bypass surface is different from APT.

### 1.1 Bypass Detection Rules

| # | Bypass Attempt | Detection | Response |
|---|---------------|-----------|----------|
| 1 | Critic returns < 3 findings | Count check | Re-run with stronger TPA prompt (§2) |
| 2 | Same model for recovery and critique | Model check | BLOCK — switch critic model |
| 3 | INSTANCE_OF without checklist_pass | KG audit | BLOCK — re-evaluate with checklist |
| 4 | Manifest agent reports `skipped_files > 0` | TR5 check | BLOCK — chunk manifest, retry |
| 5 | AST parser unused (grep-only TCW) | parser field check (TR4) | BLOCK — invoke proper AST tool |
| 6 | Distributed pattern matched without SP-MetaVerify VR | KG audit | BLOCK — fire 88-Naesengmoon |
| 7 | Coverage ratio reported < 0.8 but anchor.status not SUSPENDED | KG audit (V9) | BLOCK — set status |
| 8 | Critic produces only NITPICK 5+ rounds | Severity distribution | Rotate model + alert |
| 9 | Recovered Contract has no ReferenceSite | TR12 audit | BLOCK — Longinus binding required |
| 10 | sigma_oracle approves without seeing drift table | Cannot detect automatically | Include drift table in approval prompt |

---

## 2. Stronger Prompt for Insufficient Findings

When critic returns < 3 findings on a TPA gate, escalate:

```markdown
# ESCALATED ADVERSARIAL REVIEW (TPA RECOVERY)

Your previous review of recovered design produced only {N} findings.
Minimum is 3. This is NOT acceptable.

Mandatory deep-dive checklist for TPA:
1. Did the AST scan miss any pub symbols? (Check manifest_files vs union(agent_files).)
2. Are there pub symbols in feature-gated code (`#[cfg(feature)]`) that the manifest skipped?
3. Did the recovery confuse `:AptContract` with `:ConventionalContract`?
4. Are there N >= 3 implementors but ConventionalContract was not declared?
5. For each INSTANCE_OF: did you verify EVERY required element of the pattern checklist?
6. For each Distributed pattern: was the math property verified, or only name-matched?
7. What does the original author's intent look like that the recovery DID NOT capture?
8. What naming drift between authorial name and recovered name remains unflagged?
9. Are giants (LOC > 100) properly deferred to SP, or skipped silently?
10. What `:Lesson` did this scan produce — and is the wrongAssumption ↔ truth pair complete?

You MUST produce ≥ 3 findings. If genuinely none — produce 3 NITPICKs documenting
your full review methodology + evidence of search.
```

---

## 3. Model Separation Enforcement

Same rules as APT (§7.3 of `apt/references/adversarial.md`). Critic model != recovery model.

**TPA-specific addition**: 88-Naesengmoon (mathematical lens) **must** be a different model from the design-recovery agent that produced the SP pattern matches. If they share weights, the math verification is contaminated by the same priors that produced the false positive.

```cypher
// Model separation enforcement query (TPA)
MATCH (vr:ValidationResult {phase: 'SP-MetaVerify'})
WHERE vr.recovery_agent_model = vr.metaverify_agent_model
RETURN vr.name AS contaminated_metaverify,
       'TR11 VIOLATION: same-model self-verification' AS reason
```

---

## 4. Anti-Rubber-Stamp Techniques (TPA-extended)

The 10 APT techniques apply. TPA adds:

| # | Technique | Mechanism | Detects |
|---|-----------|-----------|---------|
| 11 | Manifest assertion | union(agent_files) == manifest_files (TR5) | Silent file skip |
| 12 | AST ground truth | Parser output cross-checked with `wc -l` | grep-only shortcut |
| 13 | Pattern checklist enforcement | INSTANCE_OF requires `checklist_pass=true` (TR2 evidence) | Pattern hallucination |
| 14 | Math verification gate | Distributed → SP-MetaVerify VR mandatory | "name only CRDT" |
| 15 | Coverage threshold protection | < 0.8 → SUSPENDED, not silent pass | Drift accumulation |
| 16 | Lesson cardinality check | TPA cycle with 0 lessons → suspicious | Empty recovery |
| 17 | Reverse orphan scan (Longinus) | Code symbols → KG mapping audit (TR12) | Recovered design without binding |

---

## 5. Mode Collapse Detection (TPA Variant)

| Signal | Threshold | Action |
|--------|-----------|--------|
| Same set of 3 lessons across 3+ TPA cycles | 3 cycles | Alert: critic may be templating |
| `coverage_ratio` always = 1.0 across 5 cycles | 5 cycles | Alert: drift detection too lenient |
| INSTANCE_OF count > Pattern Library size | any | BLOCK: pattern hallucination |
| All 5 drift kinds = 0 across 3 audits | 3 audits | Alert: drift detector inactive |
| sigma_oracle approves TA without reading drift table | 1 occurrence | Alert: meta-discriminator failure |

---

## 6. KG as Persistent Weight Space

```
Session-scoped:  Context Window  <-->  GAN weights during one recovery run
Persistent:      Knowledge Graph  <-->  GAN weights saved to checkpoint

TPA AdversarialRound findings --> KG:TpaFeedback nodes
  = saving validated recovery knowledge

Next session loads :Lesson + :ActionPlan --> context
  = loading pretrained pattern Library + drift heuristics
```

The Lesson loop is the **gradient** of TPA training. Every resolved Lesson updates the recovery prior for future cycles.

---

## 7. Critic-Recovery Tension (Theory)

APT's critic checks: "is this design correct enough to implement?"
TPA's critic checks: "is this recovery faithful enough to the source?"

Both are GAN-D mechanisms but with reversed direction of fit:
- APT: spec → code (critic ensures spec doesn't lie about code obligations)
- TPA: code → spec (critic ensures spec doesn't lie about code reality)

This asymmetry justifies TPA's 5-drift kinds (semantic distance metric) — APT does not need them because there is no prior code to drift from.

---
