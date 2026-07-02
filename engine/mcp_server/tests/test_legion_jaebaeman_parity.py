"""MCP legion_run ↔ 재배맨 substrate parity (jbm-s3, gap G4 of audit wf_376c327b-8f3).

RED-first: written against the bypass — ``legion_run_impl`` called
``build_default_legion().run(ctx)`` directly, so the 재배맨 planner/lifecycle/
``:JaebaemanRun`` telemetry were unreachable from MCP while the CLI path
(``cmd_legion`` → ``run_legion_via_jaebaeman``) recorded all of them. The parity
contract this file pins:

  1. the MCP response carries the substrate's RunRecord surface (``jaebaeman`` block:
     run_id / planned_seeds / dispatched / collected / failed / seed_outcomes).
  2. exactly one ``:JaebaemanRun`` audit record lands in the LocalKgStore per MCP
     legion_run (the improve metric — 0 under the bypass, structurally).
  3. the seed-outcome multiset is IDENTICAL to the CLI substrate path over an
     equivalent context (order-independent multiset — true parity, not field echo).
  4. (NOVEL axis, judge P2) seed↔stage bijection: degrading exactly the LAST stage
     (실현) to a contract violation flips exactly the ``legion::실현`` leaf to FAILED
     while the other five stay COLLECTED. Mid-loop degrades cascade by halt semantics,
     so the last stage is the unique single-flip counterfactual probe.

# KG: LakatosTree_BhgmanJaebaeman_20260702/jbm_s3_mcp_substrate_parity
# KG: adr-seven-commander-legion-architecture-2026-05-27
# KG: 재배맨-v2-subagent-runtime-protocol
"""

from __future__ import annotations

from engine.kg_local.runner import make_local_runner
from engine.kg_local.store import LocalKgStore
from engine.legion import jaebaeman_substrate
from engine.legion.jaebaeman_substrate import run_legion_via_jaebaeman
from engine.legion.legion import Legion
from engine.legion.legion_models import CommanderStage
from engine.mcp_server.tools.legion import legion_run_impl

# to_seeds(skill="legion") prefixes seed PKs: root seed-legion-legion-cycle + 6 leaves.
_ROOT = "seed-legion-legion-cycle"
_LEAF_PREFIX = "seed-legion-legion::"
_LEAVES = {f"{_LEAF_PREFIX}{v}" for v in ("획득", "연결", "창조", "정리", "검증", "실현")}


def test_mcp_legion_run_reaches_substrate():
    """The MCP path must run THROUGH the 재배맨 substrate: the response carries the
    RunRecord surface derived from the real planner→lifecycle chain (7 seeds =
    1 root + 6 commander leaves), not just raw stage outcomes."""
    store = LocalKgStore()
    resp = legion_run_impl(cycle_id="jbm-s3-substrate", store=store)

    assert resp["completed"] is True
    jbm = resp["jaebaeman"]  # bypass era: KeyError — this is the RED
    assert jbm["run_id"] == "mcp-jbm-s3-substrate"
    assert jbm["planned_seeds"] == 7
    assert jbm["dispatched"] == 7
    assert jbm["collected"] == 7
    assert jbm["failed"] == 0

    statuses = {o["seed"]: o["status"] for o in jbm["seed_outcomes"]}
    assert statuses[_ROOT] == "COLLECTED"
    assert {s for s in statuses if s.startswith(_LEAF_PREFIX)} == _LEAVES


def test_jaebaemanrun_record_lands_in_store():
    """Improve metric: one :JaebaemanRun audit record per MCP legion_run, observed at
    the store (bypass era: structurally 0 — record_to_kg was never on the MCP path)."""
    store = LocalKgStore()
    legion_run_impl(cycle_id="jbm-s3-record", store=store)

    recs = store.find_nodes(label="JaebaemanRun")
    assert len(recs) == 1, f"expected exactly one :JaebaemanRun record, got {len(recs)}"
    props = recs[0]["props"]
    assert props["name"] == "mcp-jbm-s3-record"
    assert props["dispatched"] == 7
    assert props["collected"] == 7


def test_cli_mcp_parity_seed_outcome_multiset():
    """True parity: the MCP path and the CLI substrate path over an equivalent context
    yield the SAME seed-outcome multiset (order-independent), not merely similar
    summaries — both are the one run_legion_via_jaebaeman code path."""
    store_a = LocalKgStore()
    resp = legion_run_impl(cycle_id="jbm-s3-parity", store=store_a)
    mcp_multiset = sorted((o["seed"], o["status"]) for o in resp["jaebaeman"]["seed_outcomes"])

    store_b = LocalKgStore()
    run_cypher = make_local_runner(store_b, autosave=False)
    ctx = {"run_cypher": run_cypher, "cycle_id": "jbm-s3-parity-cli"}
    result = run_legion_via_jaebaeman(ctx, run_id="cli-parity", write_cypher=run_cypher, apply=True)
    cli_multiset = sorted((o.seed_name, o.status.value) for o in result["lifecycle"].outcomes)

    assert mcp_multiset == cli_multiset


def _degraded_last_stage_legion() -> Legion:
    """The default legion with the LAST stage (실현) degraded to a contract violation
    (its run returns {}, so `provides` is missing). Halt semantics make mid-loop
    degrades cascade to every downstream seed — the last stage is the unique
    single-flip counterfactual."""
    from engine.legion.commanders import default_stages

    stages = list(default_stages())
    last = stages[-1]
    degraded = CommanderStage(
        name=last.name,
        verb=last.verb,
        requires=last.requires,
        provides=last.provides,
        run=lambda _ctx: {},
        measure=None,
    )
    legion = Legion()
    for s in stages[:-1]:
        legion.register(s)
    legion.register(degraded)
    return legion


def test_seed_stage_bijection_last_stage_degraded(monkeypatch):
    """NOVEL axis (judge P2, independent of record counts): stage↔seed correspondence
    is 1:1 — degrade exactly the last stage and exactly its seed flips to FAILED,
    the other five leaves stay COLLECTED, and the aggregate root mirrors completion."""
    monkeypatch.setattr(jaebaeman_substrate, "build_default_legion", _degraded_last_stage_legion)
    store = LocalKgStore()
    resp = legion_run_impl(cycle_id="jbm-s3-degraded", store=store)

    assert resp["completed"] is False
    assert resp["contract_violation"], "the degraded 실현 stage must violate its contract"

    statuses = {o["seed"]: o["status"] for o in resp["jaebaeman"]["seed_outcomes"]}
    leaves = {k: v for k, v in statuses.items() if k.startswith(_LEAF_PREFIX)}
    assert leaves.pop(f"{_LEAF_PREFIX}실현") == "FAILED"
    assert set(leaves.values()) == {"COLLECTED"}, (
        f"exactly ONE leaf may flip under a last-stage degrade; got {leaves}"
    )
    assert statuses[_ROOT] == "FAILED"
