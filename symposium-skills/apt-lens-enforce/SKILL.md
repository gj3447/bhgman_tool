---
name: apt-lens-enforce
kg_ref: ATOM_Skill_apt_lens_enforce
version: "1.0.0"
channel: stable
canonical_name: apt-lens-enforce
description: >
  APT Naesengmoon LensSet enforcement 책무 — HR1/HR11/HR13 + AdversarialGate Cypher enforcement.
  Every APPROVED verdict MUST cite specific evidence (HR11 no rubber-stamp).
  Adversarial validation at every gate: critic + ground truth + sigma_oracle + post-gate reflection.
  apt-feedback-lens (4축 진단) 과는 책무 다름:
    - apt-feedback-lens = Inform/Constrain/Verify/Correct 4축 *진단* (어디 위치인지 lens)
    - apt-lens-enforce  = HR rules *강제* (every gate Cypher field 검증 + missing 차단)
  Migrated 2026-05-22: body 본 skill 안에 이전 완료 (was at apt/SKILL.md HARD RULES + v27 HR13 Addendum).
  Invoke when: gate 통과 시 lens 검증 강제, HR11/HR13 Cypher schema 확인.
  # KG: ATOM_Skill_apt_lens_enforce, gate-hr13-adversarial-cypher-2026-05-19, schema-aptdecisionlog-v2-adversarial-gate-2026-05-19, vr-apt-fix2-partial-install-naesengmoon-3lens-2026-05-22
---

# APT Adversarial Validation — Anti-Rubber-Stamp Layer

Master enforcement of adversarial validation at every gate.
No gate may be passed without: (1) adversarial critic review, (2) ground truth verification,
(3) human sigma_oracle approval, (4) evidence-backed verdicts (HR11), (5) post-gate reflection.
These are HARD requirements -- not guidelines.

```
SA --> SP --[adversarial]--> ST --[adversarial]--> SCW --[adversarial + test]--> PH6
            |                     |                       |
       Critic attacks        Critic attacks          Critic + cargo test
            |                     |                       |
       KG log + fix          KG log + fix            KG log + fix
            |                     |                       |
       sigma_oracle (HUMAN)  sigma_oracle (HUMAN)    sigma_oracle (HUMAN)
```

---

## 0. HARD RULES (v21 -- cannot be overridden)

These rules are BLOCKING. If any is violated, the orchestrator MUST halt and refuse to proceed.

| # | Rule | Enforcement |
|---|------|-------------|
| HR1 | **Adversarial round at EVERY gate** | No gate passes without AdversarialRound() completing |
| HR2 | **sigma_oracle is ALWAYS human** | `allow_agent_sigma: false` -- agent cannot self-approve |
| HR3 | **Critic model differs from design model** | Same-model critique is BLOCKED (exception: Lite Mode with full D22.3 template) |
| HR4 | **Minimum `cfg.adversarial_min_findings_per_round` findings per round** | If critic returns less: re-run with stronger prompt (Section 7.2) |
| HR5 | **KG density check before decomposition** | INFORMED_BY < `cfg.density_min_informed_by` or source_types < `cfg.density_min_source_types`: BLOCK and run KAL |
| HR6 | **Ground truth before gate pass** | SCW: cargo test MUST pass. SP/ST: WebSearch evidence cited. |
| HR7 | **Every gate transition logged to KG** | AptDecisionLog node created. No silent transitions. |
| HR8 | **Every adversarial finding logged to KG** | AptFeedback node created per finding. |
| HR9 | **No human response to sigma_oracle = BLOCK** | Do not proceed. Ask again. Never assume approval. |
| HR10 | **Every skip/override requires explicit human reason** | Logged with justification. Agent cannot generate reason. |
| HR11 | **Every APPROVED verdict must cite specific evidence** | Theorem name, test result, or KG query. No evidence = RUBBER_STAMP violation, auto-downgrade to NEEDS_REVIEW. |
| HR12 | **2-Tier Naesengmoon: never mix tiers** | Tier 1 (`LensSet.constitutional`) for artifacts, Tier 2 (`LensSet.mathematical`) for methodology meta-verification only. Cross-tier application BLOCKED (`cfg.taliban_mixing_tiers='BLOCKED'`). lens_count는 LensSet 노드 조회. |
| HR13 | **Essential ✗ are design constraints, not bugs** | Arrow of Time (order-dependent), Edge of Chaos (structured complexity), Gödel (never complete). Do not "fix" these. |
| HR14 | **Mandatory post-gate reflection** | After every gate: identify weakness exposed, log as AptFeedback, confirm next gate checks for it. No reflection = INCOMPLETE_GATE. |
| HR15 | **Lean ground truth (optional per project)** | If enabled: `lake build` must produce sorry=0, error=0, warning=0. Add `lean: "lake build"` to config to activate. |
| HR16 | **SA-가려진 경로에 SCW 없이 편집 금지** | SemanticAnchor 또는 SPAN_*_ROOT가 이미 존재하는 파일/디렉터리(예: landing-site, 333-platform, metahumotonic-web)에 Write/Edit 호출 시 BLOCK — AtomicSpan+Contract+Task 체인 없이 직접 편집 = executor=reviewer 위반(D20). Pre-edit 확인: `MATCH (sa:SemanticAnchor)-[:COVERS_PATH*0..]->(p) WHERE $target_path STARTS WITH p.path RETURN sa` → 매치 존재 시 `/apt-sp` 진입 강제. # KG: lesson-apt-scw-skipped-ritual-css-2026-04-17, lesson-apt-vr-self-fulfilled-executor-reviewer-2026-04-16 |

---

## 🎛 v27 Addendum — HR13 Adversarial Gate Cypher Enforcement (2026-05-19)

> A6 resolve-only 준수. Prose 측 magic number 미박입 — KG `:ValidationGate` 측 enforcement_cypher field 측 단일 정전. PreToolUse hook 측 shadow rollout (warn-only) 측 BLOCK 격상은 1-sprint audit 후 (2026-05-22 BLOCK_NEW 격상 완료, legacy bypass `UNKNOWN_LEGACY`).

```cypher
// HR13 LensSet completeness + adversarial verdict gate (per AptDecisionLog)
MATCH (vg:ValidationGate {name:'gate-hr13-adversarial-cypher-2026-05-19'})
RETURN vg.enforcement_cypher, vg.violation_action

// AptDecisionLog v2 schema (required fields)
MATCH (sch:Schema {name:'schema-aptdecisionlog-v2-adversarial-gate-2026-05-19'})
RETURN sch.required_fields, sch.gate_type_enum, sch.adversarial_verdict_enum
```

PreToolUse hook: `~/.claude/hooks/pre_tool_apt_phase_gate_check.py` (matcher `mcp__neo4j__write_neo4j_cypher`, MODE=BLOCK_NEW post-2026-05-22 audit).

# KG: gate-hr13-adversarial-cypher-2026-05-19 / schema-aptdecisionlog-v2-adversarial-gate-2026-05-19 / sprint-apt-hr1-enforcement-gate-cypher-2026-05-19 / lesson-sprint-apt-hr1-misnomer-actually-hr13-lensset-2026-05-19

### v27-B. RFC2 Contract Substitution Mode Gate (2026-05-19)

> SP→ST mini-RGR 측 contract substitution criteria 측 `rigor_level` 5-tier enum 측 mapping. Binary `fast_path/full_cycle` 측 deprecated (학술 정전 5-tier 측 honor).

```cypher
MATCH (sch:Schema {name:'schema-contract-substitution-mode-rfc2-2026-05-19'})
RETURN sch.tier_mapping, sch.contract_artifact_kinds, sch.substitution_criteria

MATCH (vg:ValidationGate {name:'gate-contract-substitution-rfc2-2026-05-19'})
RETURN vg.enforcement_cypher
```

Tier mapping: `conjecture/heuristic → informal_allowed (docstring|test_signature)` · `semi-rigorous → mixed` · `rigorous → typed_pydantic_dto mandatory` · `proven → typed_pydantic_dto + lake build sorry=0`.

# KG: gate-contract-substitution-rfc2-2026-05-19 / schema-contract-substitution-mode-rfc2-2026-05-19 / sprint-apt-st-informal-contract-rgr-cfg-gate-2026-05-19 / lesson-sprint-rfc2-binary-fast-vs-full-actually-rigor-level-5tier-2026-05-19

---

## ✅ Migration Status (2026-05-22)

- **Status**: MIGRATED (was `SCAFFOLD_BODY_MIGRATION_PENDING`).
- **Source**: was at `SKILLS/apt/SKILL.md` lines 333-374 (HARD RULES intro + table HR1-HR16) + lines 661-693 (v27 HR13 Addendum + v27-B RFC2).
- **Cascade**: 3/4 책무 본문 분해 (apt-magic-resolve 1/4 → apt-autoflow-guard 2/4 → apt-lens-enforce 3/4).
- **Next**: apt-orchestrator (마지막, 가장 큼).
- **Overlap audit vs apt-feedback-lens**: 책무 다름 (강제 vs 진단). 신설 OK.

# KG: scaffold-apt-skill-decomposition-2026-05-22, migration-apt-lens-enforce-body-2026-05-22
