"""Deterministic judge for LakatosTree_Bhgman6CommanderOoptdd_20260624 / naesengmoon_corroborate_wire.

Recomputes both pre-registered metrics by driving the live verify surface:

  improve  legion_offline_oracle_legs
      ORACLE critics voting in the legion verify path WITHOUT an LLM client, measured
      at the MCP boundary (legion_run over the bundled store). Baseline 1
      (upstream-completeness only — the audited n_eff=1.0 degeneration) → 2 with the
      kg-corroborate separate-source leg wired.

  novel    canon_contradiction_veto   (judge-P2 independent axis: separate-source 판별)
      1.0 iff a claim with OPPOSITE polarity to a seeded CANONICAL fact is vetoed
      (ensemble != PASS) AND the polarity-consistent claim passes — the leg reads the
      real KG canon, independent of the leg-count axis.

Prints one JSON line; exit 0. Run from repo root:
.venv/bin/python scripts/judge_naesengmoon_corroborate.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))

from engine.agents.grounding import LocalGroundingSource  # noqa: E402
from engine.kg_local.runner import make_local_runner  # noqa: E402
from engine.kg_local.store import LocalKgStore  # noqa: E402
from engine.legion.commanders import _run_verify  # noqa: E402
from engine.mcp_server.tools.legion import legion_run_impl  # noqa: E402

_OK_UPSTREAM = {
    "acquired": {"mode": "kg-deterministic"},
    "bindings": {"mode": "ok"},
    "abstractions": {"mode": "fca"},
    "hygiene": {"mode": "ok"},
}


def _verdict(store: LocalKgStore, claim: str) -> dict:
    ctx = {
        "run_cypher": make_local_runner(store, autosave=False),
        "cycle_id": "judge-ncw",
        "grounding": LocalGroundingSource(store),
        "claim": claim,
        **_OK_UPSTREAM,
    }
    return _run_verify(ctx)["verdict"]


def main() -> int:
    # ── improve: MCP 경계에서 관측한 offline ORACLE leg 수 ──────────────────
    resp = legion_run_impl(cycle_id="judge-ncw-mcp", store=LocalKgStore())
    legs = resp.get("verdict", {}).get("oracle_legs", [])
    legion_offline_oracle_legs = len(legs)

    # ── novel: 정전 모순 veto ∧ 정합 통과 ───────────────────────────────────
    truth = "the retrospective mapping is not dispatch"
    store = LocalKgStore()
    store.merge_node("CanonicalName", "name", "canon-fact", {"name": "canon-fact", "claim": truth})
    vetoed = _verdict(store, "the retrospective mapping is dispatch")
    passed = _verdict(store, truth)
    canon_contradiction_veto = (
        1.0 if (vetoed.get("ensemble") != "PASS" and passed.get("ensemble") == "PASS") else 0.0
    )

    print(
        json.dumps(
            {
                "legion_offline_oracle_legs": legion_offline_oracle_legs,
                "canon_contradiction_veto": canon_contradiction_veto,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
