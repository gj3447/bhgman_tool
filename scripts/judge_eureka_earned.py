"""Direct deterministic measurement for eureka_mcp_earned_counts.

Recomputes both pre-registered metrics from live surfaces, never from a self-report:

  improve  earned_count_production_surfaces
      Production surfaces whose eureka report is EARNED (stage-payload-derived) rather
      than stages_ok-shaped: (1) the eureka_induce MCP tool — earned counts must equal
      an independent run_from_kg recomputation; (2) the legion _run_induce payload —
      must carry induced/survived keys with honest zeros on an empty KG. Baseline 0
      (audit wf_376c327b-8f3: no eureka MCP tool at all; legion reported the exact
      stages_ok metric that a direct regression proved fake-green on an empty KG).

  novel    empty_kg_zero_discrimination   (judge-P2 independent axis)
      1.0 iff on an EMPTY KG the pipeline stages still run green-ish (stages_ok > 0)
      while earned induced == 0 — proving the two axes measure different things
      (stages_ok cannot see the zero; earned can). Independent of surface counts.

Prints one JSON line; exit 0 (the VALUES carry the verdict).
Run from the repo root:  .venv/bin/python scripts/judge_eureka_earned.py
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))

from engine.kg_local.runner import make_local_runner  # noqa: E402
from engine.kg_local.store import LocalKgStore  # noqa: E402
from engine.legion.commanders import _run_induce  # noqa: E402
from engine.mcp_server.tools.eureka import eureka_induce_impl  # noqa: E402


def _direct_earned(store: LocalKgStore) -> tuple[int, int]:
    from engine.eureka import pipeline, stages

    rc = make_local_runner(store, autosave=False)
    cfg = pipeline.PipelineConfig(cycle_id="judge-direct", **stages.wire_default_stages(rc))
    pr = pipeline.run_from_kg(rc, cfg)

    def count(prefix: str, key: str) -> int:
        for s in pr.stages:
            if s.stage.startswith(prefix) and isinstance(s.payload, dict):
                return int(s.payload.get(key, 0) or 0)
        return 0

    return count("4-induce", "abstract_classes"), count("4.5-quality-gate", "survived")


def main() -> int:
    surfaces = 0

    # surface 1: MCP tool — earned parity with independent recomputation.
    resp = eureka_induce_impl(cycle_id="judge-mcp", store=LocalKgStore())
    want_induced, want_survived = _direct_earned(LocalKgStore())
    if (
        resp.get("earned", {}).get("induced") == want_induced
        and resp.get("earned", {}).get("survived") == want_survived
    ):
        surfaces += 1

    # surface 2: legion payload — earned keys with honest zero on an empty KG.
    with tempfile.TemporaryDirectory() as td:
        rc = make_local_runner(LocalKgStore(Path(td) / "e.json"), autosave=False)
        ab = _run_induce({"run_cypher": rc, "cycle_id": "judge-legion"}).get("abstractions", {})
        if (
            ab.get("induced") == 0
            and ab.get("survived") == 0
            and "induced=0" in ab.get("summary", "")
        ):
            surfaces += 1

        # novel: empty-KG discrimination via the MCP surface.
        empty = eureka_induce_impl(cycle_id="judge-empty", store=LocalKgStore(Path(td) / "e2.json"))
    discrimination = (
        1.0
        if (
            empty["earned"]["induced"] == 0
            and empty["earned"]["survived"] == 0
            and empty["stages_ok"] > 0
        )
        else 0.0
    )

    print(
        json.dumps(
            {
                "earned_count_production_surfaces": surfaces,
                "empty_kg_zero_discrimination": discrimination,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
