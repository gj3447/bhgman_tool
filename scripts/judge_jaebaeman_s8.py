"""Deterministic judge for LakatosTree_BhgmanJaebaeman_20260702 / jbm_s8_germinate_e1_kg_seam.

Recomputes both pre-registered metrics by driving the live MCP boundary:

  improve  mcp_enforced_invariant_codes
      Distinct ViolationCode classes the seed_germinate MCP boundary actually
      discriminates as fail-closed BLOCKED. Baseline 4 (dup-PK / depth / dangling /
      E3 — the s2 local floor; E1 was disclosed-unchecked, no run_cypher seam) →
      5 with the KG seam (E1 orphan anchor).

  novel    orphan_vs_existing_anchor_discrimination   (judge-P2 independent axis)
      1.0 iff the SAME seed spec is BLOCKED(E1) against a store WITHOUT the anchor
      node AND PLANNED against a store WITH it — proving E1 reads the real KG
      (not a constant), independent of the code-count axis. The no-KG call must
      also stay PLANNED with an honest E1-unchecked disclosure (no silent scope
      inflation).

Prints one JSON line; exit 0. Run from repo root: .venv/bin/python scripts/judge_jaebaeman_s8.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))

from engine.jaebaeman.jaebaeman_models import ViolationCode  # noqa: E402
from engine.kg_local.store import LocalKgStore  # noqa: E402
from engine.mcp_server.tools.symposium import (  # noqa: E402
    SeedGerminateRequest,
    _seed_germinate_impl,
)

_ORPHAN_SPEC = {"seeds": [{"name": "e1-seed", "anchor": "e1-anchor-node"}]}


def _call(payload: dict, store=None) -> dict:
    return _seed_germinate_impl(
        SeedGerminateRequest(spec_name="judge-s8", payload=payload, parent_cycle_id="judge-s8"),
        store=store,
    )


def main() -> int:
    # ── improve: MCP 경계에서 실판별되는 위반 코드 종수 ─────────────────────
    cases = {
        ViolationCode.DUP_SEED_NAME: ({"seeds": [{"name": "d"}, {"name": "d"}]}, None),
        ViolationCode.E4_DEPTH_RANGE: ({"seeds": [{"name": "deep", "depth": 99}]}, None),
        ViolationCode.DANGLING_PARENT: ({"seeds": [{"name": "o", "parent": "nowhere"}]}, None),
        ViolationCode.E3_MULTIPLE_SEED_PER_ANCHOR: (
            {"seeds": [{"name": "a1", "anchor": "s"}, {"name": "a2", "anchor": "s"}]},
            None,
        ),
        ViolationCode.E1_ORPHAN_ANCHOR: (_ORPHAN_SPEC, LocalKgStore()),
    }
    observed: set[str] = set()
    for code, (payload, st) in cases.items():
        resp = _call(payload, store=st)
        if resp.get("status") == "BLOCKED" and code.value in {
            v["code"] for v in resp.get("violations", [])
        }:
            observed.add(code.value)
    mcp_enforced_invariant_codes = len(observed)

    # ── novel: orphan vs existing anchor 판별 (+ 무KG 정직 공시) ────────────
    blocked = _call(_ORPHAN_SPEC, store=LocalKgStore())
    with_anchor = LocalKgStore()
    with_anchor.merge_node("Concept", "name", "e1-anchor-node", {"name": "e1-anchor-node"})
    planned = _call(_ORPHAN_SPEC, store=with_anchor)
    no_kg = _call(_ORPHAN_SPEC)
    orphan_vs_existing_anchor_discrimination = (
        1.0
        if (
            blocked.get("status") == "BLOCKED"
            and planned.get("status") == "PLANNED"
            and no_kg.get("status") == "PLANNED"
            and "미검" in no_kg.get("engine", {}).get("invariants", "")
        )
        else 0.0
    )

    print(
        json.dumps(
            {
                "mcp_enforced_invariant_codes": mcp_enforced_invariant_codes,
                "orphan_vs_existing_anchor_discrimination": orphan_vs_existing_anchor_discrimination,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
