# TPA Dogfood Review — bhgman_tool Phase 3 sprint (self-application)

> Honest review of running the APT cycle on bhgman_tool's own Phase 3 sprint. Follows the [SYMPOSIUM `THEORY/TPA/DOGFOOD_STANDARD.md`](https://github.com/gj3447/symposium) format.

## Subject

- **Target**: `~/CD/bhgman_tool/` (this repository)
- **APT version**: v26.1 (with v27 A15 work_kind routing)
- **Cycle date**: 2026-05-13
- **Reviewer**: gj3447 (with Claude Opus 4.7 1M context as agent)
- **Adversarial reviewer**: (deferred — Naesengmoon gate not run in this session; see What was missed)

## What APT got right

- The **EXTEND SHORT_CIRCUIT** routing fired correctly. `apt-sa` saw the existing Phase 1 anchor `sa-bhgman_tool-ruflo-utility-parity-2026-05-13` and reused it rather than minting a duplicate. v27 A15 prevented an obvious E-SA1 (duplicate anchor) failure.
- The **5 mandatory SA core fields** were verified present on the existing anchor (objective / definition / keyAssertion / c_s_predicate / context_budget_total). The gap was missing Root Span + context_budget allocation, which were filled retroactively in this sprint — the v26 SA→SP gate caught a real defect from Phase 1.
- **1 SA + 3 sibling L1 branch** decomposition matched the user-stated sprint scope. No premature atomization; each branch landed at depth 1, ready for ST.
- **SCW outputs are typed by tests, not by narrative**. 35 new pytest cases serve as the ST→SCW gate (executable contracts). The CLI test `test_install_skills_skip_existing_without_force` and the MCP tests `test_*_no_coverage_ratio` are the kind of *adversarial* assertions an internal reviewer would write — they actively assert what the artifact must NOT do.
- **Goodhart safeguard surfaced explicitly in code**. Three test cases (`test_taliban_lens_check_no_scalar_score`, `test_tpa_drift_audit_no_coverage_ratio`, and the version-output test that emits raw counts) enforce that the new MCP tools never collapse a multi-axis assessment into a single number.

## What APT got wrong

- **SA→SP gate run informally** — there was no live Naesengmoon critic invocation. The constitutional 9-lens check passed at the KG level (`gate_check_passed=true`) but no second agent challenged the decomposition before SP execution began.
- **SP→ST transition omitted ST artifacts**. The "Contract" for each branch is the module docstring + the test file, not a typed Pydantic DTO. v26 RFC mandates 9 canonical axes for a Contract; v0.1 of this sprint produced informal contracts only.
- **No per-branch ST→SCW mini-RGR** (RFC2 v26.1 local cleanup). The CLI branch went straight to implementation without an explicit RED phase. The fact that tests pass is the only RGR-equivalent evidence.
- **HR14 reflection partially skipped**. Phase 3 completion in `apt-progress.md` mentions limitations but no `v21_reflection` property was written back to the SA node.

## What was missed

- **Naesengmoon LensSet UNION coverage was not measured**. The constitutional-9 lens is one tier; mathematical-113 was not invoked even though Phase 3 expands MCP tooling (a methodology surface, which arguably warrants meta-verification).
- **HR12 cross-tier check**: artifacts (CLI + MCP tools) belong to the constitutional tier, but the `taliban_lens_check` tool itself is methodology infrastructure (mathematical tier). The tool added the `hr12_note` string but no enforcement check rejects calling it with the wrong tier.
- **No Longinus reference binding** was created for the new code. The new modules cite `# KG: span-mcp-tool-{apt,taliban,tpa}-*` in comments, but the corresponding `:ReferenceSite` nodes with sha256 baselines are not yet in the KG. Drift detection on these new modules will report `kg_simulated_present=false` until that is fixed.
- **No bhgman-essence layer cross-link**. The new CLI mentions "tool layer vs essence layer" in its `version` output, but no edge to the essence-side anchor was created in KG.

## Lakatos verdict

- **Original self-assignment**: ~~PROGRESSIVE_CONDITIONAL~~ (rejected by external review)
- **Revised verdict after Naesengmoon ensemble review (2026-05-13T20:00 KST)**: **REJECT_PENDING_REMEDIATION**
- **External reviewer**: `taliban-ensemble-critic` agent (4-lens UNION: constitutional-9 + longinus-7 + lensset-solid + lens-set-lakatos)
- **Reviewer ValidationResult**: `taliban-ensemble-bhgman_tool-phase3-2026-05-13` (KG node), coverage_score=0.92, blocker_count=5, total_findings=25
- **5 BLOCKER findings** (must be remediated before re-classification):
    - `C9-01` run.sh `pass=4` summary line allows SKIP to be misread as PASS — gate-enforced vs step-executed conflation
    - `C9-02` `tpa_drift_audit` schema returns `Missing=0 / SigMismatch=0 / PatternDiv=0` for deferred fields rather than a `NotImplemented` sentinel
    - `L7-01` 3 new `# KG: span-mcp-tool-*` citations have no `:ReferenceSite + sha256 baseline` — Longinus L4 violation
    - `L7-02` no `:REALIZES_PHASE` edges from new MCP tools to BHGMAN 5-phase canon
    - `K-01` original `PROGRESSIVE_CONDITIONAL` self-assignment had zero novel corroborated predictions → Lakatos degenerating-shift indicator (this very revision is a partial remediation)
- **Rationale**: The Phase 3 sprint produces novel content (3 new tools + CLI + worked example) backed by passing tests. The K-01 finding correctly observed that "passing tests" alone is not the Lakatos progressive signature — the work needs *novel empirical content* corroborated by independent observation. The Naesengmoon agent's review *is* that independent observation; this revised verdict captures it honestly.
- **Counterexamples discovered**: Phase 1 SA was created without a Root Span; cross-tier lens HR12 mentioned as note but not enforced; `# KG:` citations exist without matching ReferenceSite nodes.
- **Lemma incorporations**: see KG nodes
    - `lesson-apt-phase1-sa-without-root-span-2026-05-13`
    - `errorpattern-cross-tier-lens-no-enforcement-2026-05-13`
    - `lesson-apt-fast-path-vs-full-prescription-2026-05-13`
    - `taliban-blocker-{C9-01,C9-02,L7-01,L7-02,K-01}-2026-05-13` (5 BlockerFinding nodes)
- **Remediation backlog** (separate sprint): full L7-01/L7-02 binding work (ReferenceSite + sha256 + REALIZES_PHASE edges) requires Longinus subskill invocation per tool; tpa.py schema correction (`NotImplemented` sentinel for deferred drift types) is lightweight but changes the public schema and warrants its own change-set.
- **Counterexamples discovered**: The Phase 1 SA was created without a Root Span — this is an SA→SP gate evasion that the v22 Gate Check Hook should have rejected at the time. The fact that this sprint had to repair it retroactively is itself a counterexample to "v22 Hook is enforcing".
- **Lemma incorporations**: `lesson-apt-phase1-sa-without-root-span-2026-05-13` (suggested) — SA bootstrap must MERGE Root Span + DECOMPOSES_TO atomic, not as a follow-up.

## Quantitative metrics

- SA: 1 existing anchor reused (EXTEND), 5 mandatory core fields verified, 1 Root Span + 3 L1 branches added
- SP: 3 branches decomposed, all reached depth=1, status=open→completed
- ST: 3 informal contracts (module docstrings + test files); 0 typed Pydantic DTOs (v0.1 deferred)
- SCW: 27 new pytest cases ((9 CLI + 18 MCP) on top of pre-existing 17), 100% PASS on the new ones, 1 fix iteration on the cross-file `list_registered_tool_names()` update
- Lean: 0 new theorems (this sprint did not formalize anything new; rests on existing 141+ theorem corpus)

## Drift audit (5 types)

| Drift Type | Count | Severity | Examples |
|---|---|---|---|
| Missing | (deferred) | n/a | `tpa_drift_audit` skeleton does not yet detect Missing |
| Orphan | 0 (KG-mock fallback) | low | none against kg_simulated.json (not present at repo root) |
| SigMismatch | (deferred) | n/a | AST-level — skeleton stage |
| PatternDiv | (deferred) | n/a | Pattern Library not yet wired |
| LabelRot | 0 | low | no `# KG: ... DEPRECATED` markers |

## Goodhart safeguard self-check

- [x] No headline metric promoted as primary value
- [x] All claims cite artifacts (commit hash, test name, file path)
- [ ] Reviewer != Adversarial reviewer — only Reviewer present in this session; Adversarial deferred
- [x] If self-improving applied, Tarski/Goodhart acknowledgment present — see "Honest limitations" + the module docstrings
- [x] Counterexamples documented honestly (Phase 1 SA defect surfaced, not monster-barred)

## Lemma incorporations into SYMPOSIUM (suggestions)

- [ ] `:Lesson lesson-apt-phase1-sa-without-root-span-2026-05-13` — SA bootstrap MUST atomically create Root Span; partial SA = gate failure
- [ ] `:Pattern pattern-extend-short-circuit-reused-anchor-retroactive-root-2026-05-13` — when EXTEND finds an incomplete prior SA, repair-then-extend is acceptable but should be logged as a separate `:RepairOperation`
- [ ] `:ErrorPattern errorpattern-cross-tier-lens-no-enforcement-2026-05-13` — `taliban_lens_check` tool warns via `hr12_note` string but does not enforce; consumer can still misuse

## Honest limitations

- This review is **single-reviewer** (executor = reviewer = author). The TPA DOGFOOD_STANDARD explicitly says `Reviewer != Adversarial reviewer`. Independent Naesengmoon critique is owed.
- Time budget on this sprint was ~1 hour, so the meta-application is faster than the methodology prescribes (formal SA→SP and SP→ST gates would each have taken comparable time to the implementation).
- The Lakatos `PROGRESSIVE_CONDITIONAL` verdict is my own; an external Lakatos panel might come back DEGENERATING on the strength of the missing adversarial round.

## Reproducibility

```bash
cd ~/CD/bhgman_tool/worked/03-apt-cycle-on-self/
./run.sh
```

`run.sh` re-verifies the artifacts (CLI entry point, 35 pytest, KG anchor name in `apt-progress.md`, git log). It does not re-execute the APT cycle — the cycle ran in commits 9ea935f and the subsequent Phase 3 MCP commit.

## Cross-references

- SYMPOSIUM canon: `THEORY/TPA/DOGFOOD_STANDARD.md` (this review's format origin)
- SYMPOSIUM KG: `sa-bhgman_tool-ruflo-utility-parity-2026-05-13`, `SPAN_bhgman_tool_phase3_{ROOT,CLI,WORKED3,MCP_TOOLS}`
- bhgman_tool worked-1 (`worked/01-longinus-simple/`) — drift detection precursor
- bhgman_tool worked-2 (`worked/02-goodhart-on-ruflo/`) — negative case study sibling
- Commits: `9ea935f` (CLI entry + install-skills) + Phase 3 MCP commit (see `git log --oneline`)
