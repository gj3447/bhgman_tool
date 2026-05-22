# Skills connection graph

How the slash commands dispatch each other within an APT cycle. Moved here from root README per PROM 16 README persuasion design cycle 2026-05-22 (reconciliation R4 — keep root README focused on adopter funnel; deep concept material lives under `docs/02-concepts/`).

---

## APT 5-phase cycle + tool dispatch

`/apt` orchestrates a forward design cycle (SemanticAnchor → SemanticPyramid → SemanticTwin → SourceCodeWorld → MetaReview). At each gate it dispatches one or more of the 5 tools (`/prom`, `/longinus`, `/jaebaeman`, `/tlb`, `/harness`). `/tpa` is the reverse-direction mirror (code → design recovery).

```mermaid
flowchart TB
    user(["user: /apt &lt;goal&gt;"]) --> apt{{"/apt orchestrator"}}
    apt --> sa["SA<br/>SemanticAnchor"]
    sa --> sp["SP<br/>SemanticPyramid"]
    sp --> st["ST<br/>SemanticTwin"]
    st --> scw["SCW<br/>SourceCodeWorld"]
    scw --> meta["MetaReview"]
    meta -. feedback loop .-> sa

    sa -. uses .-> prom["/prom<br/>Prometheus"]
    sa -. uses .-> longinus["/longinus<br/>reference binding"]
    sp -. uses .-> jbm["/jaebaeman<br/>SOP dispatch"]
    sp -. uses .-> tlb["/tlb<br/>Naesengmoon critic"]
    st -. uses .-> tlb
    scw -. uses .-> tlb
    meta -. uses .-> tlb

    tpa{{"/tpa reverse cycle"}} -. mirror .-> apt
    harness[("/harness<br/>4-axis · 3-tier")] -. frames .-> apt

    classDef phase fill:#e0e7ff,stroke:#3730a3,stroke-width:2px,color:#1f2937
    classDef weapon fill:#fef3c7,stroke:#92400e,stroke-width:1px,color:#1f2937
    classDef orch fill:#dcfce7,stroke:#166534,stroke-width:2px,color:#1f2937
    class sa,sp,st,scw,meta phase
    class prom,longinus,jbm,tlb,harness weapon
    class apt,tpa orch
```

---

## Per-tool entry points

| Slash command | Tool | Phase it most commonly enters at | Deep doc |
|---|---|---|---|
| `/prom` | Prometheus (parallel research) | SA (Step 1 knowledge ingestion) | [../skills/prometheus/SKILL.md](../../skills/prometheus/SKILL.md) |
| `/longinus` | Longinus reference binding | SA Step 2 (KG ↔ code drift audit) | [../skills/longinus/SKILL.md](../../skills/longinus/SKILL.md) |
| `/jaebaeman` | Jaebaeman SOP (subagent dispatch) | SP Step 4 (D(S) parallel decomposition) | [../skills/jaebaeman/SKILL.md](../../skills/jaebaeman/SKILL.md) |
| `/tlb` | Naesengmoon adversarial critic | SP / ST / SCW / MetaReview gates | [../skills/taliban/SKILL.md](../../skills/taliban/SKILL.md) |
| `/harness` | Harness 4-axis diagnostic | Framing layer (Inform / Constrain / Verify / Correct) | [harness.md](harness.md) |
| `/tpa` | Reverse APT cycle | Reverse design recovery from existing code | [apt-tpa-cycles.md](apt-tpa-cycles.md) |

---

## See also

- [harness.md](harness.md) — 4-axis Harness model + 3-tier family (IDE-host / runtime / managed cloud)
- [apt-tpa-cycles.md](apt-tpa-cycles.md) — forward APT vs reverse TPA cycle, gate hooks
- [../06-philosophy/](../06-philosophy/) — why this tool structure rather than a flat orchestration framework
