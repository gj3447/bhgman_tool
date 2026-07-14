"""RED-first judge — LakatosTree_BhgmanCeilingPierce_20260712/repair-loop-production-wire (Q1).

Re-derives, from the REAL engine code + a deterministic EXTERNAL oracle (no LLM, no in-memory
claim echo), two INDEPENDENT measurements the LakatoTree submits as a scripted verdict:

  primary  structured_repair_lift    — the lift make_repair_stage achieves on a structured
                                        landscape, re-run here (0 before this increment: no repair
                                        stage existed in the production stage-composition).
  novel    deceptive_seed_preserved  — 1 iff the honest guard keeps the seed when read-back loses
                                        on a DECEPTIVE landscape. A DIFFERENT variable from lift and
                                        revert-proof: delete the `if res.improved` guard in
                                        repair_stage.py and this flips to 0. This is the
                                        counterfactual that a naive "always replace" impl fails.

HONEST SCOPE: this proves the repair-loop *machinery* is wired into the production Legion
stage-composition and behaves honestly — NOT that it yields an equal-compute cognitive uplift on
a real LLM oracle task (that is Q2, a 3-arm equal-compute A/B needing dgx vLLM). The magnitude of
structured_repair_lift is the synthetic landscape's scale, not a capability claim.

Run:  ./.venv/bin/python -m verification.judge_repair_wire   (or  python verification/judge_repair_wire.py)
"""

from __future__ import annotations

import json
from pathlib import Path

from engine.legion.legion import Legion
from engine.legion.legion_models import CommanderStage
from engine.legion.repair_stage import make_repair_stage
from engine.naesengmoon.oracle_lens import ScalarOracle

_SPACE = 1_000_000
_TARGET = 987_654
_STEPS = (1, -1, 7, -7, 53, -53, 401, -401, 3001, -3001, 21001, -21001)


def _generate(parents, generation):
    if not parents:
        return [(generation * 2654435761 + 12345) % (_SPACE + 1)]
    base = parents[0]
    return [min(max(base + s, 0), _SPACE) for s in _STEPS]


def _structured() -> ScalarOracle:
    return ScalarOracle(name="dist", kind="test", score=lambda x: float(-abs(x - _TARGET)))


def _deceptive() -> ScalarOracle:
    def f(x: float) -> float:
        return -float(x) * 0.001 if x < 100_000 else 500.0 - abs(x - _TARGET) * 0.0001

    return ScalarOracle(name="deceptive", kind="test", score=f)


def _seed_stage() -> CommanderStage:
    return CommanderStage(
        name="creator", verb="창조", requires=(), provides=("x",), run=lambda _c: {"x": 0}
    )


def measure() -> dict:
    # primary: real oracle-measured lift when the repair loop is wired into a production stage.
    structured = make_repair_stage(
        _seed_stage(), oracle=_structured(), generate=_generate, max_generations=200, patience=5
    )
    tel = structured.run({})["repair"]
    lift = float(tel["lift"])
    completed = Legion().register(structured).run().completed

    # novel: revert-proof honesty counterfactual — deceptive landscape must keep the seed.
    deceptive = make_repair_stage(
        _seed_stage(), oracle=_deceptive(), generate=_generate, max_generations=50, patience=5
    )
    dec = deceptive.run({})
    preserved = 1 if (dec["x"] == 0 and dec["repair"]["improved"] is False) else 0

    return {
        "structured_repair_lift": lift,
        "deceptive_seed_preserved": preserved,
        "legion_completed": bool(completed),
    }


if __name__ == "__main__":
    result = measure()
    receipt = Path(__file__).resolve().parent / "repair_wire_receipt.json"
    receipt.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
