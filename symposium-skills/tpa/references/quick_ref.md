# tpa — Quick Ref

> **Lazy-load reference for `tpa` skill.**
> Parent skill: [`../SKILL.md`](../SKILL.md). Mirror reference: [`../../apt/references/quick_ref.md`](../../apt/references/quick_ref.md).
> KG: `tpa-hardening-master-plan-2026-05-06`.

---

## 1. Decision Tree

```
"I need to..."
    |
    +-- "...analyze an existing codebase"
    |       -> /tpa <path> (auto phase detection)
    |
    +-- "...just extract pub symbols + AST"
    |       -> /tpa-tcw <path> (Phase 1)
    |
    +-- "...recover contracts from existing code"
    |       -> /tpa-st <path> (Phase 2; requires TCW VR)
    |
    +-- "...identify GoF / distributed patterns"
    |       -> /tpa-sp <path> (Phase 3; requires ST VR)
    |
    +-- "...anchor recovered design to KG SemanticAnchor"
    |       -> /tpa-ta <anchor_name> (Phase 4; requires SP VR)
    |
    +-- "...drift-audit an existing TA result"
    |       -> /tpa --audit <anchor>
    |
    +-- "...check what phase a target is in"
    |       -> /tpa --status (Phase Detection query)
    |
    +-- "...see open lessons from TPA cycles"
    |       -> /tpa --lessons <target>
    |
    +-- "...understand TPA theory"
    |       -> Read references/theory.md
    |
    +-- "...understand TPA gate sequence"
    |       -> Read references/gates.md
```

---

## 2. When to Use Each Skill

| Situation | Skill | Why |
|-----------|-------|-----|
| New external codebase, no TPA_Execution | `/tpa <path>` | Phase Detection bootstraps TCW |
| TCW done, contracts undefined | `/tpa-st` directly | Clearly ST work |
| ST done, patterns to identify | `/tpa-sp` directly | Clearly SP work |
| SP done, ready to anchor in our KG | `/tpa-ta` | Final anchoring + 5-drift audit |
| "What did we miss?" question | `/tpa --audit <anchor>` | Drift re-measurement |
| "Which lessons came from this scan?" | `/tpa --lessons <target>` | Feedback loop status |
| Suspect rubber-stamp from prior cycle | Re-run Naesengmoon gate (89-lens) | Anti-rubber-stamp |
| Repo > 10K LOC | Set `tpa.parallel.max_agents` ≥ 4 | TR14 mandatory |

---

## 3. Audit Mode (`/tpa --audit`)

Re-runs TA Phase 4 only. Compares prior TA Result's recovered SemanticAnchor against current code state. Reports 5 drift kinds:

| Drift | Symptom |
|-------|---------|
| Missing | KG node references file/symbol that no longer exists in code |
| Orphan | Code symbol with no matching KG Contract |
| SigMismatch | Code signature differs from recovered Contract |
| PatternDiv | Code pattern shifted (e.g. State → Strategy migration) |
| LabelRot | KG label or relation drifted from current convention |

If `coverage_ratio < tpa_drift_coverage_ratio_min` (default 0.8), TA sets `anchor.status = 'SUSPENDED'`. Resume requires fresh `/tpa <path>` cycle.

---

## 4. Phase Order Cheat Sheet

```
[CODE] → /tpa-tcw → AST symbols + manifest
            ↓ (Naesengmoon gate, TCW VR)
         /tpa-st → AptContract + ConventionalContract per symbol
            ↓ (Naesengmoon gate, ST VR)
         /tpa-sp → DesignPattern matches (INSTANCE_OF / RESEMBLES)
            ↓ (Naesengmoon gate + 88-Naesengmoon for Distributed; SP VR)
         /tpa-ta → SemanticAnchor created + 5-drift measured
            ↓ (final Naesengmoon gate, TA VR + Lesson feedback loop fires)
[DESIGN ANCHORED]
```

---

## 5. MIC Slot Cheat Sheet

| TPA need | MIC slot | current concrete |
|----------|----------|------------------|
| AST + symbol harvest | `KgCodeBinder` | Longinus |
| Unknown pattern lookup | `ResearchProvider` | Prometheus |
| Per-phase gate validation | `AdversarialValidator` | Naesengmoon |
| Distributed-pattern math check | `MetaVerifier` | 88-Naesengmoon |
| Parallel large-repo scan | `SubagentSeeder` | 재배맨 |

Resolve via:
```cypher
MATCH (mic:MethodologyIntegrationContract {name:'MIC_v1'})-[:HAS_SLOT]->(s:MethodologySlot)
RETURN s.name, s.currentConcrete, s.invocation
```

---

## 6. Hard Rule Quick Index

| TR | Mnemonic |
|----|----------|
| TR1 | Every gate has adversarial round |
| TR2 | APPROVED → evidence required |
| TR3 | Phase order: TCW → ST → SP → TA |
| TR4 | AST parser, not grep alone |
| TR5 | skipped_files = 0 |
| TR6 | Unknown → ResearchProvider auto |
| TR7 | KG log on every gate |
| TR8 | Tier1 9-lens artifacts; Tier2 88-lens methodology only |
| TR9 | Reflection mandatory |
| TR10 | Lesson on discovery |
| TR11 | executor ≠ reviewer (D20) |
| TR12 | Longinus `# KG:` comment |
| TR13 | treasure_coverage ≥ 0.9 |
| TR14 | >10K LOC → 재배맨 parallel |
| TR15 | Essential ✗ acknowledged |

Full text: `references/hard_rules.md`.

---

## 7. Common BLOCK Causes

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `/tpa-st` denied | TCW VR missing or REJECTED | Run `/tpa-tcw` + `/taliban` first |
| `/tpa-sp` denied | ST VR missing | Run `/tpa-st` + `/taliban` first |
| TA `coverage_ratio < 0.8` | Many post-recovery drifts | Re-scan TCW; consider larger `max_agents` |
| Distributed pattern has no MetaVerify VR | 88-Naesengmoon not auto-fired | Run `/88-taliban` or set `MetaVerifier` slot |
| Lesson never resolves | No `:ActionPlan` linked | Manually create + `(l)-[:TRIGGERS]->(p)` |

---
