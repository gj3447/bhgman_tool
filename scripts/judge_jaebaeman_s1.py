"""Deterministic judge for LakatosTree_BhgmanJaebaeman_20260702 / jbm_s1_ooptdd_adapter.

Recomputes both pre-registered metrics from the ARRIVAL side (store + gate), never from
the adapter's self-report — the same dual-oracle discipline as the sibling commanders:

  improve  seeds_planted_observed_at_store
      distinct seed PKs the real ``plant_seeds`` landed in the seed store during one
      green sortie. Baseline 0 (before jbm-s1 the adapter did not exist, so no store
      observation was possible at all — audit wf_376c327b-8f3 gap G1).

  novel    lifecycle_order_discrimination   (judge-P2 independent axis: sequencing)
      1.0 iff the must_order gate check PASSES on the real lifecycle order AND goes RED
      on an order-flipped counter-run of the SAME real event multiset while every
      value-pinned ==N check stays green. 0.0 otherwise. This measures whether the gate
      can *discriminate* order at all — independent of every count.

Prints one JSON line with both values; exit 0 (the VALUES carry the verdict).
Run from the repo root:  .venv/bin/python scripts/judge_jaebaeman_s1.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from ooptdd.backends.memory import MemoryBackend, reset  # noqa: E402
from ooptdd.engine.gate import evaluate, load_gate  # noqa: E402

from ooptdd.jaebaeman_adapter import (  # noqa: E402
    _ev,
    _run_real_sortie,
    emit_germinate_phase,
    emit_plant_phase,
    emit_ready_phase,
    run_jaebaeman_pipeline,
)

_GATE = str(_ROOT / "engine" / "jaebaeman" / "tests" / "gates" / "jaebaeman_flow.yaml")


def _checks(result: dict) -> list[dict]:
    return list(result.get("checks", []))


def main() -> int:
    import os

    # ── improve: seeds observed at the store during one green sortie ────────────
    cid = "judge-jbm-s1-green"
    os.environ["OOPTDD_CID"] = cid
    reset()
    backend = MemoryBackend()
    run_jaebaeman_pipeline(backend, cid)
    store, readback, plant, _ = _run_real_sortie()
    seeds_planted_observed_at_store = len(store.seeds)

    green = evaluate(backend, load_gate(_GATE))
    green_ok = bool(green.get("ok"))
    green_order_passed = all(
        c.get("passed", True) for c in _checks(green) if "must_order" in str(c)
    )

    # ── novel: order discrimination on the SAME real multiset, flipped ─────────
    cid = "judge-jbm-s1-flipped"
    os.environ["OOPTDD_CID"] = cid
    reset()
    flipped = MemoryBackend()
    flipped.ship([
        _ev(cid, "jaebaeman_sortie_completed", dry_run=plant.dry_run,
            planted=len(store.seeds), ready=len(readback),
            germinated=sum(1 for r in store.seeds.values() if r["status"] == "COLLECTED"))
    ])
    emit_germinate_phase(flipped, cid, store)
    emit_ready_phase(flipped, cid, readback)
    emit_plant_phase(flipped, cid, store)
    flipped.ship([_ev(cid, "jaebaeman_sortie_started", phase="plant")])

    flip = evaluate(flipped, load_gate(_GATE))
    flip_failed = [c for c in _checks(flip) if not c.get("passed", True)]
    order_red_counts_green = (
        not flip.get("ok")
        and bool(flip_failed)
        and all("must_order" in str(c) for c in flip_failed)
    )

    lifecycle_order_discrimination = (
        1.0 if (green_ok and green_order_passed and order_red_counts_green) else 0.0
    )

    print(json.dumps({
        "seeds_planted_observed_at_store": seeds_planted_observed_at_store,
        "lifecycle_order_discrimination": lifecycle_order_discrimination,
        "green_gate_ok": green_ok,
        "flipped_only_order_failed": order_red_counts_green,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
