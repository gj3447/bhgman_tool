"""Deterministic judge for LakatosTree_BhgmanJaebaeman_20260702 / jbm_s2_seed_germinate_engine.

Recomputes both pre-registered metrics from engine parity, never from the tool's
self-report:

  improve  mcp_engine_derived_cypher_count
      planned_cyphers in the seed_germinate MCP response that are BYTE-IDENTICAL to a
      direct ``plant_seeds(dry_run=True)`` recomputation over the SAME parsed
      SeedRecords. Baseline 0 (the sha256 shim carried no engine artifact at all —
      audit wf_376c327b-8f3 gap G3). A hashed or hand-typed artifact scores 0: parity
      is the oracle, not presence.

  novel    invariant_gate_discrimination_at_mcp   (judge-P2 independent axis)
      fraction of spec pairs (1 valid + 3 violating: dup-PK / depth-range /
      dangling-parent) the MCP boundary splits correctly — PLANNED for valid, BLOCKED
      with an EMPTY plan list for violating (fail-closed). Independent of any count.

Prints one JSON line; exit 0 (the VALUES carry the verdict).
Run from the repo root:  .venv/bin/python scripts/judge_jaebaeman_s2.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from engine.jaebaeman.kg_adapter import plant_seeds  # noqa: E402
from engine.mcp_server.tools.symposium import (  # noqa: E402
    SeedGerminateRequest,
    _seed_germinate_impl,
    seeds_from_payload,
)

_VALID = {
    "seeds": [
        {"name": "sg-root", "expected_outcome": "루트 계획 심기", "depth": 0},
        {"name": "sg-leaf", "anchor": "sg-root", "parent": "sg-root", "depth": 1},
    ]
}
_VIOLATING = [
    {"seeds": [{"name": "sg-dup"}, {"name": "sg-dup"}]},  # DUP_SEED_NAME
    {"seeds": [{"name": "sg-deep", "depth": 99}]},  # E4_DEPTH_RANGE
    {"seeds": [{"name": "sg-orphan", "parent": "sg-nowhere"}]},  # DANGLING_PARENT
]


def _call(payload: dict) -> dict:
    return _seed_germinate_impl(
        SeedGerminateRequest(spec_name="judge-s2", payload=payload, parent_cycle_id="judge-s2")
    )


def main() -> int:
    # ── improve: engine parity count ─────────────────────────────────────────
    resp = _call(_VALID)
    mcp_engine_derived_cypher_count = 0
    if resp.get("status") == "PLANNED":
        seeds = seeds_from_payload("judge-s2", _VALID)
        expected = plant_seeds(
            seeds, write_cypher=None, cycle_id=resp["engine"]["cycle_id"], dry_run=True
        ).planned_cyphers
        got = [(p["cypher"], p["params"]) for p in resp.get("planned_cyphers", [])]
        if got and got == [(c, params) for c, params in expected]:
            mcp_engine_derived_cypher_count = len(got)

    # ── novel: fail-closed discrimination at the MCP boundary ───────────────
    hits = 1 if resp.get("status") == "PLANNED" else 0
    for payload in _VIOLATING:
        r = _call(payload)
        if r.get("status") == "BLOCKED" and r.get("planned_cyphers") == []:
            hits += 1
    invariant_gate_discrimination_at_mcp = hits / (1 + len(_VIOLATING))

    print(
        json.dumps(
            {
                "mcp_engine_derived_cypher_count": mcp_engine_derived_cypher_count,
                "invariant_gate_discrimination_at_mcp": invariant_gate_discrimination_at_mcp,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
