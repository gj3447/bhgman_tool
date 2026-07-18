# HALO-Loop — infusing the intelligence-uplift mechanism into bhgman_tool

> 2026-07-19 · KG: `project_ultimate_ai_tool_halo_loop_2026_07_19`
> Origin: PROM 16 ×2 (`multi_agent_intelligence_conditions`, `bhgman_pierce_direction`) + an
> 18-agent reverse-engineering workflow over 6 external intelligence-uplift tools, adversarially
> verified by 3 independent critics (all `SOUND_WITH_ADJUSTMENTS`).

**HONESTY LAW (governs this whole document):** operational machinery ≠ cognitive uplift. Nothing
here claims a raised model IQ. The one lever with any positive signal (mechanism 3) is
oracle-channelled **bounded-repair search compute**, and its current evidence is
**PLAUSIBLE-uncontrolled**, not measured. A null is "not shown", never a refutation.

---

## 1. The secret of every tool that genuinely raised capability

Reverse-engineering AlphaCodium, FunSearch, Reflexion, MoA, LATS, and Anthropic's multi-agent
researcher at code level: 4 of 6 (AlphaCodium/FunSearch/Reflexion/LATS) work by **the same
mechanism** — an *external ground-truth oracle channels the search toward correct answers*
(mechanism 3). MoA (2, diversity) has no oracle and is weak by our standard; Anthropic (4,
context breadth) buys throughput at ~15× tokens, not depth.

| mechanism | what actually raises capability | our owner |
|---|---|---|
| 1 more compute / best-of-N | extra samples + vote — lever is compute, ~0 depth by DPI | `evolve_loop.best_of_n` (control arm) |
| 2 diversity → decorrelated errors | genuinely heterogeneous models cancel errors; clones **amplify** (~60% floor) | Naesengmoon panel (**not yet wired** — see §5) |
| **3 external-oracle gen→verify→repair** | **the load-bearing lever; the only one we ever measured positive** | **ooptdd (this session's build)** |
| 4 context extension via decomposition | breadth/coverage, ~15× tokens, not depth | OMD disjoint write-sets |

The reveal: **we already own every part of mechanism 3** — ooptdd is the oracle, LakatoTree the
judge, OMD the parallelism, and `legion/diagnostic_repair.py` already implements the repair loop.
They were just never wired into one loop, and the oracle channel was off.

---

## 2. Measurement (Phase 1, this session — Mac-now, no LLM)

Re-analyzed the committed 32b lean-headroom A/B (`headroom_32b_2026-06-14/seed_*.jsonl`) with the
per-TASK paired view the critics demanded. Reproducible via
`engine/efficacy/analyze_headroom_pertask_paired.py` (+ test).

```
per-SEED sign test:  8W / 2T / 0L over 10 runs   p = 0.007812   ← reproduces committed VERDICT
per-TASK paired net delta (repair − bestN), headroom only:
    sumto_mono  +6.0   ← 46% of the net signal, one task
    dbl_ge      +4.0
    le_sumto    +2.0
    sumlist_app +2.0
    (other 6 headroom tasks ≈ 0; repl_len −1)
  → signal carried by 4/10 tasks; top-task concentration 46%.
```

**Verdict:** the p reproduces (data is real), but "8 wins over 10 runs" counts *seeds* as
independent when they re-draw over the same 4 carrying tasks. Honest label =
**`PLAUSIBLE-uncontrolled (concentrated)`**, matching the repo's own frozen
`PIERCE_PREREGISTRATION.md` (VerdictPending, no-propagation). It is **not** "measured positive
capability", and must never be cited as such.

---

## 3. HALO-Loop architecture (the synthesized design)

Mechanism 3 is the **spine**; mechanism 2 is admitted only as a fenced, measured, INERT-by-default
adjudicator; mechanisms 1 & 4 are honestly-labelled throughput.

```
L0 PREREGISTER   LakatoTree register_prediction — lock task set + Tier-A oracle cmd + pass
                 predicate + metric + ρ-probe, PER-TASK not per-seed, content-addressed.
L1 GENERATE      Hades realizes the spec across ≥3 DISTINCT model endpoints (heterogeneous supply).
L2 ORACLE+REPAIR ooptdd verify_gate → present/absent/inconclusive → structured textual repair tail
   = THE SPINE   → legion/diagnostic_repair bounded climb. COMPLETE iff present; inconclusive NEVER
                 repairs (infra). AlphaCodium fence: reject any green that WEAKENED the gate.
L3 SELECT        the ooptdd oracle argmax-selects the winning candidate (NEVER an LLM vote);
                 Naesengmoon adjudicates only oracle-SILENT sub-claims, ρ measured, never over a
                 Tier-A oracle RED.
L4 DECOMPOSE     OMD disjoint write-set leases fan N loops (throughput); best_of_n = control arm.
L5 DEPLOYED GATE gated_run G1∧G2∧G3 (thread a real ground_truth_cmd so G3 fires live) + signed
                 verdict — auditability only, NOT a quality verdict.
L6 JUDGE         LakatoTree submit_result → progressive/degenerating + BH-FDR across frozen tasks +
                 c1verify byte-exact re-derivation (anti-Goodhart).
L7 BIND + PRUNE  Longinus sha256 bind of the survivor; Occam prunes degenerating branches.
OVERLAY (defer)  LATS judge-tree, node.value = LakatoTree standing — build ONLY after §5 A/B passes.
```

---

## 4. Adversarial verdict (3 critics, unanimous `SOUND_WITH_ADJUSTMENTS`)

Mandatory cuts (all honored in §2/§5):
- **p=0.0078 is not "measured positive"** — per-seed, concentrated, VerdictPending/no-propagation.
- **Mechanism 2 (diversity) is NOT SHOWN, not delivered.** Today's panel is *homogeneous* in code
  (`commanders.py` hardcodes `model_family='anthropic'`; `decorrelation` falls back to
  `DEFAULT_RHO=0.7`; `rho_probe` does not exist) → a K1 fake-heterogeneity condition live in code.
- **The named A/B instrument can't measure mechanism 2** — `hetero_composition_ab.py` routes 6
  roles through ONE model = prompt-diversity of one base = the ~60% clone floor. Needs new code.
- **The 3-arm design is weaker than the repo's already-frozen 5-arm** (decoy + plain-agent-baseline
  + TOST). ARM3 (oracle-removed) is the K3-inadmissible half-tautology.
- **Equal-compute must count ORACLE-CALLS, not just tokens.**

---

## 5. What was built this session vs what remains

**BUILT + verified (this commit):**
- `engine/naesengmoon/ooptdd_oracle.py` — the mechanism-3 spine: ooptdd gate result →
  `DiagnosticOracle` for `legion.diagnostic_repair`. present→COMPLETE, RED→repairable tail,
  infra→ORACLE_ERROR (never success), AlphaCodium strength-regression fence. 8 tests incl. negative
  oracles (cheated green, infra hold) + a real-ooptdd contract cross-check.
- `engine/efficacy/analyze_headroom_pertask_paired.py` (+test) — the Phase-1 measurement, locked so
  the concentrated/PLAUSIBLE reading cannot silently regress.

**REMAINS (buildable, ordered; the genuine uplift test):**
1. `engine/legion/oracle_loop.py` + MCP `legion_oracle_loop` — flat L0–L7 controller wrapping the
   bare stages with the repair stage.
2. Thread `ground_truth_cmd` through `mcp_server/tools/legion.py::legion_run_impl` → G3 fires live
   (today SKIPPED → verified=False by default).
3. Real heterogeneity: drop the `commanders.py` `model_family='anthropic'` hardcode; per-lens
   endpoint via `client.py::endpoint_for_tier`; build `naesengmoon/rho_probe.py`; feed measured ρ.
4. `engine/legion/lakatos_gate.py` — fail-closed `register_prediction` id + BH-FDR + c1verify.
5. **The measurement that would make mechanism 2 SHOWN:** an equal-compute **5-arm** A/B
   {hetero+oracle, homo+oracle(bestN), plain-agent-with-oracle, decoy, oracle-removed} at EQUAL
   tokens AND oracle-calls, on a sha256-frozen ≥20-task held-out set, per-task paired + BH-FDR, ρ
   reported in the same run. K1 auto-kill at ρ≥0.9.

**Honest end-state:** HALO-Loop ships today as operational machinery with mechanism 3 as its only
evidenced lever, and that evidence is PLAUSIBLE-uncontrolled. Mechanism 2 uplift is **not shown —
not refuted.** The idea was never disproven; the prior attempt just failed to measure it cleanly.
