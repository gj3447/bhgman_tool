"""Direct deterministic measurement for prometheus_grounding_wire.

Recomputes both pre-registered metrics by driving the live legion measure surface:

  improve  grounding_wired_surfaces
      Legion measure surfaces deriving external_grounding_ratio from REAL citations
      (not the constructor default): 1 iff _measure_prometheus over a mixed citation
      list yields exactly 0.5 AND the deterministic _run_acquire exposes citation_urls.
      Baseline 0 (runtime-dead: ratio pinned at 1.0, key absent).

  novel    self_recurse_fires_on_ungrounded   (judge-P2 independent axis: dispatch 발화)
      1.0 iff all-ungrounded citations make the <0.3 prometheus→prometheus self-recurse
      dispatch ACTUALLY fire AND fully-grounded citations do NOT fire it — an event that
      was structurally impossible while the ratio was dead at 1.0. Independent of the
      ratio-value axis.

Prints one JSON line; exit 0. Run from repo root: .venv/bin/python scripts/judge_prometheus_grounding.py
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
from engine.legion.commanders import _measure_prometheus, _run_acquire  # noqa: E402


def main() -> int:
    # ── improve: 배선된 표면 실측 ────────────────────────────────────────────
    with tempfile.TemporaryDirectory() as td:
        rc = make_local_runner(LocalKgStore(Path(td) / "e.json"), autosave=False)
        acquired = _run_acquire({"run_cypher": rc, "cycle_id": "judge-gw"})["acquired"]
    exposes = "citation_urls" in acquired
    mixed = _measure_prometheus(
        {"acquired": {"findings": 2, "citation_urls": ["http://phys.test/koide", ""]}}
    )
    derives = mixed.measure()["external_grounding_ratio"] == 0.5
    grounding_wired_surfaces = 1 if (exposes and derives) else 0

    # ── novel: self-recurse 발화 판별 (발화 ∧ 반대쪽 미발화) ─────────────────
    dead = _measure_prometheus({"acquired": {"findings": 2, "citation_urls": ["", "not a url"]}})
    fired = [
        d
        for d in dead.decide_dispatch(cycle_id="judge-fire")
        if d.metric_name == "external_grounding_ratio" and d.target_commander == "prometheus"
    ]
    live = _measure_prometheus(
        {"acquired": {"findings": 2, "citation_urls": ["http://a.test/x", "https://b.test/y"]}}
    )
    not_fired = not [
        d
        for d in live.decide_dispatch(cycle_id="judge-nofire")
        if d.metric_name == "external_grounding_ratio"
    ]
    self_recurse_fires_on_ungrounded = 1.0 if (fired and not_fired) else 0.0

    print(
        json.dumps(
            {
                "grounding_wired_surfaces": grounding_wired_surfaces,
                "self_recurse_fires_on_ungrounded": self_recurse_fires_on_ungrounded,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
