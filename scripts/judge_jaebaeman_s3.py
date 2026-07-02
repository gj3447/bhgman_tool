"""Deterministic judge for LakatosTree_BhgmanJaebaeman_20260702 / jbm_s3_mcp_substrate_parity.

Recomputes both pre-registered metrics from the ARRIVAL side (store + counterfactual),
never from the tool's self-report:

  improve  mcp_jaebaemanrun_record_count
      :JaebaemanRun audit records observed at an injected LocalKgStore after ONE MCP
      legion_run. Baseline 0 (bypass era: legion_run_impl called
      build_default_legion().run directly, so record_to_kg was structurally
      unreachable from MCP — audit wf_376c327b-8f3 gap G4).

  novel    seed_stage_bijection   (judge-P2 independent axis: correspondence)
      1.0 iff (a) a green run collects ALL 7 seeds, AND (b) degrading exactly the
      LAST stage (실현) to a contract violation flips exactly the 실현 leaf to FAILED
      while the other five leaves stay COLLECTED (root aggregates to FAILED). Halt
      semantics make mid-loop degrades cascade, so the last stage is the unique
      single-flip probe. Independent of any record count.

Prints one JSON line; exit 0 (the VALUES carry the verdict).
Run from the repo root:  .venv/bin/python scripts/judge_jaebaeman_s3.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest import mock

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))

from engine.kg_local.store import LocalKgStore  # noqa: E402
from engine.legion.legion import Legion  # noqa: E402
from engine.legion.legion_models import CommanderStage  # noqa: E402
from engine.mcp_server.tools.legion import legion_run_impl  # noqa: E402

_ROOT = "seed-legion-legion-cycle"
_LEAF_PREFIX = "seed-legion-legion::"


def _degraded_last_stage_legion() -> Legion:
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


def _statuses(resp: dict) -> dict[str, str]:
    return {o["seed"]: o["status"] for o in resp.get("jaebaeman", {}).get("seed_outcomes", [])}


def main() -> int:
    # ── improve: :JaebaemanRun records observed at the store ────────────────
    store = LocalKgStore()
    green = legion_run_impl(cycle_id="judge-s3-green", store=store)
    mcp_jaebaemanrun_record_count = len(store.find_nodes(label="JaebaemanRun"))

    green_statuses = _statuses(green)
    green_ok = (
        green.get("completed") is True
        and green_statuses.get(_ROOT) == "COLLECTED"
        and sum(
            1 for k, v in green_statuses.items() if k.startswith(_LEAF_PREFIX) and v == "COLLECTED"
        )
        == 6
    )

    # ── novel: last-stage degrade → exactly one leaf flips ──────────────────
    with mock.patch(
        "engine.legion.jaebaeman_substrate.build_default_legion", _degraded_last_stage_legion
    ):
        degraded = legion_run_impl(cycle_id="judge-s3-degraded", store=LocalKgStore())
    d = _statuses(degraded)
    leaves = {k: v for k, v in d.items() if k.startswith(_LEAF_PREFIX)}
    flipped = {k for k, v in leaves.items() if v == "FAILED"}
    single_flip = (
        degraded.get("completed") is False
        and flipped == {f"{_LEAF_PREFIX}실현"}
        and all(v == "COLLECTED" for k, v in leaves.items() if k not in flipped)
        and d.get(_ROOT) == "FAILED"
    )

    seed_stage_bijection = 1.0 if (green_ok and single_flip) else 0.0

    print(
        json.dumps(
            {
                "mcp_jaebaemanrun_record_count": mcp_jaebaemanrun_record_count,
                "seed_stage_bijection": seed_stage_bijection,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
