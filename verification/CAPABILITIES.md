# bhgman_tool — Measurable Capabilities

> ruflo-grade capability inventory. Each row is a *measurable* invariant that
> survives regression — tied to a verification command + JSON ratchet.
> Companion: [`results.md`](results.md) (cumulative session results).
>
> Absorbed from SYMPOSIUM/verification/ (Wave 7 P2-A, 2026-05-14).
> KG: `rs-bhgman-verification-absorb-2026-05-14`

---

## How to read this doc

- **Capability**: one user-visible invariant.
- **Witness**: shell command that returns the current value.
- **Ratchet**: condition for "regressed vs last release" (typically count must not drop).
- **Source**: KG node / file where the canonical definition lives.

Run all witnesses:

```bash
bhgman-tool verify        # smoke-level pytest on engine/
# OR (SYMPOSIUM-compat alias):
bin/symposium verify
```

---

## I. Formal verification (Lean 4)

| # | Capability | Witness | Ratchet | Source |
|---|---|---|---|---|
| F1 | Mathlib build PASS | `cd lean && lake build` (when wired) | exit 0 | `lean-mathlib-functor-actual-build-2026-04-30` |
| F2 | Sorry count = 0 (standalone) | `grep -rc '\bsorry\b' lean/*.lean \| awk -F: '{s+=$2} END{print s}'` | result = 0 | `lean-formalization-sorry-free-baseline` |
| F3 | Theorem count ≥ 50 (bhgman_tool baseline) | `grep -rE '^theorem \|^lemma ' lean/*.lean \| wc -l` | ≥ 50 | `bhgman-50-theorems-baseline-2026-05-13` |
| F4 | Standalone (Mathlib-free) build exit 0 | `lean --version && lean lean/<file>.lean` | exit 0 | `lean-mathlib-free-policy` |

## II. KG structural invariants

| # | Capability | Witness | Ratchet | Source |
|---|---|---|---|---|
| K1 | Canonical node count ≥ baseline | `bhgman-tool status \| grep -i canonical` | ≥ last-release count | `kg-canonical-ratchet` |
| K2 | StructuralPattern count = 5 | Cypher: `MATCH (n:StructuralPattern) RETURN count(n)` | = 5 | `family/relation/disenchantment/family-sub-type/temporal-arc` |
| K3 | 5-tuple identity (AtomicSpan ≡ Contract ≡ Task ≡ Seed ≡ File) | `pytest engine/mcp_server/tests/symposium/test_kg_invariants.py` | all pass | `rs-test-kg-invariants-5tuple-2026-05-14` |
| K4 | 12사도 verdict distribution unchanged | Cypher: `MATCH (a:Apostle) RETURN a.verdict, count(*)` | 7 CONFIRMED + 3 ADJUSTED + 1 OPEN + 1 NOT_FAMILY | `family-expansion-pattern-canonical-2026-04-30` |
| K5 | Hyperedge instance count ≥ 9 | Cypher: `MATCH (h:Hyperedge) RETURN count(h)` | ≥ 9 | `relation-pattern-canonical-2026-04-30` |

## III. 5-weapon integration

| # | Capability | Witness | Ratchet | Source |
|---|---|---|---|---|
| W1 | All 5 weapons have SKILL.md | `for w in harness prometheus taliban longinus jaebaeman; do test -f skills/$w/SKILL.md; done` | exit 0 | `symposium-5-weapons-hardening-overview-2026-05-06` |
| W2 | ErrorPattern count ≥ 65 (SYMPOSIUM cumulative) | Cypher: `MATCH (e) WHERE e:ErrorPattern OR e:*ErrorPattern RETURN count(e)` | ≥ 65 | `symposium-methodology-overview-2026-05-06` |
| W3 | references files count ≥ 63 | `find skills -name 'references*' \| wc -l` | ≥ 63 | `symposium-methodology-overview-2026-05-06` |
| W4 | Longinus 7-Layer reference model bound | `grep -r 'L1.*L7\|7-Layer' engine/longinus_drift_audit/ engine/mcp_server/tools/symposium.py \| wc -l` | ≥ 2 | `longinus-grounding-2026-05-10` |

## IV. CLI / MCP runtime (this absorption)

| # | Capability | Witness | Ratchet | Source |
|---|---|---|---|---|
| C1 | bhgman-tool console script callable | `bhgman-tool version` | exit 0 + version printed | `SPAN_bhgman_tool_phase3_CLI` |
| C2 | Cohort A subcommands present (native) | `bhgman-tool --help \| grep -E 'install-skills\|verify\|version\|daemon'` | 4 matches | this file |
| C3 | Cohort B subcommands present (SYMPOSIUM-absorbed) | `bhgman-tool --help \| grep -E 'apt\|tpa\|prom\|tlb\|longinus\|harness\|status'` | 7 matches | `rs-cli-symposium-absorb-2026-05-14` |
| C4 | bash alias `bin/symposium` executable | `test -x bin/symposium` | exit 0 | `rs-bin-symposium-bash-alias-2026-05-14` |
| M1 | MCP server build_server() returns 9 tools | `python -c 'from engine.mcp_server.server import list_registered_tool_names; print(len(list_registered_tool_names()))'` | result = 9 | `rs-mcp-symposium-absorb-2026-05-14` |
| M2 | 4 SYMPOSIUM tools present (apt_dispatch / kg_query / gate_check / seed_germinate) | inspect `list_registered_tool_names()` | 4 names match | `rs-mcp-symposium-absorb-2026-05-14` |
| M3 | fail-open semantics (degraded dict, no raise) | `pytest engine/mcp_server/tests/symposium/test_kg_invariants.py::TestFailOpen` | pass | `rs-test-kg-invariants-2026-05-14` |
| M4 | Write-keyword guard | `pytest engine/mcp_server/tests/symposium/test_kg_invariants.py::TestWriteSafety` | 5/5 pass | `rs-test-kg-invariants-2026-05-14` |
| A4 | Phase routing valid for 5 phases | `pytest engine/mcp_server/tests/symposium/test_apt_phase_routing.py` | all pass | `rs-test-apt-phase-routing-2026-05-14` |

## V. Wave extraction (Kahn topo sort)

| # | Capability | Witness | Ratchet | Source |
|---|---|---|---|---|
| WV1 | Linear / diamond / parallel correct | `pytest engine/mcp_server/tests/symposium/test_wave_extraction.py::TestKahnWaves` | all pass | `GAP-1 wave_index 2026-05-13` |
| WV2 | Cycle detection raises ValueError | `pytest engine/mcp_server/tests/symposium/test_wave_extraction.py::TestKahnWaves::test_cycle_detected` | pass | this file |
| WV3 | Dispatch invariant (`idx[child] > idx[parent]`) | `pytest engine/mcp_server/tests/symposium/test_wave_extraction.py::TestWaveIndexAssignment::test_dispatch_invariant` | pass | this file |
| WV4 | APT SP→ST→SCW realistic chain → 4 waves | `pytest engine/mcp_server/tests/symposium/test_wave_extraction.py::TestAptIntegration` | pass | this file |

## VI. Claude Code hooks (host-machine, not in repo)

| # | Capability | Witness | Ratchet | Source |
|---|---|---|---|---|
| H1 | PreToolUse denylist installed | `test -x ~/.claude/hooks/pre_tool_denylist.sh` | exit 0 | `PROM_32 §4 L2` |
| H2 | Stop hook (auto_continue + cost guard) | `test -x ~/.claude/hooks/auto_continue.sh` | exit 0 | `PROM_32 §4 L3` |
| H3 | Churn-guard H1 (fingerprint dedup) | `test -x ~/.claude/hooks/pre_tool_churn_guard.py` | exit 0 | `feedback_autoloop_churn_guard.md` |

---

## Out-of-scope (explicit non-capabilities)

- **Network reliability**: ssh dgx availability not measured here (degraded fallback covered by M3).
- **Wall-clock perf baselines**: ruflo-style perf jsonl deferred to v0.2 (see `results.md` §FutureWork).
- **Subjective drift**: ResearchFinding novelty / quality — not measurable mechanically.

---

## KG provenance

- This file: `rs-bhgman-verification-capabilities-2026-05-14` (`:VerificationCapabilityInventory`)
- Source: SYMPOSIUM/verification/CAPABILITIES.md (`capabilities-doc-2026-05-14`)
- Cross-ref: `symposium-methodology-overview-2026-05-06`, `apt-hardening-master-plan-2026-05-06`
- Companion ratchet: `results.md` (per-session results)

<!-- KG: rs-bhgman-verification-absorb-2026-05-14 -->
<!-- longinus-7tuple: {file_path: "verification/CAPABILITIES.md", line_range: [1,-1], kg_ref: "rs-bhgman-verification-capabilities-2026-05-14", axis: "L1_CAPABILITY_DOC", canonical_status: "PRELIMINARY", source_provenance: "SYMPOSIUM/verification/CAPABILITIES.md@9227c4d2", last_validated: "2026-05-14"} -->
