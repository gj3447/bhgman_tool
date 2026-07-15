"""ooptdd trace-gate over bhgman_tool's repair-loop production wiring — Q1 of the ceiling-pierce.

Positive-TDD / log-based gate (ooptdd): the *store* is the judge, not the return value. We drive
the REAL ``engine.legion.repair_stage.make_repair_stage`` — which wraps a 1-pass CommanderStage
into an oracle-guided ``evolve()`` repair loop — run it BOTH standalone (to read the real
EvolveResult lift) AND inside a production ``Legion().run()`` (to prove it satisfies the same
Contract and completes), and the gate in gates/repair_loop_flow.yaml re-checks arrival from the store.

Honest-count contract:
    - repair_lift_measured (==1, where outcome:improved): carries the REAL out["repair"]["improved"]
      from the wrapped stage. On a STRUCTURED landscape read-back climbs => outcome:improved. On a
      DECEPTIVE landscape read-back loses and the adapter (honestly, per the seed-preservation guard)
      keeps the seed => outcome:kept => the where:{outcome:improved} count is 0 => RED. Tracks the
      real oracle result, never a constant.
    - repair_stage_wired (==1): shipped ONLY when the wrapped stage runs inside
      Legion().register(stage).run() and returns completed=True — the production-pipeline wiring proof
      (a Contract-breaking wrap would leave this 0 => RED).

Longinus binding (AST-checked): each must_emit literal lives VERBATIM in its ADAPTER symbol
    (run_repair_pipeline / emit_repair_phase), NEVER inside engine/legion/. Rename => UNBOUND/RED.

The synthetic landscapes (structured / deceptive) are the model boundary — like hades's Dog/Cat
family. The code UNDER test is the real make_repair_stage + evolve + Legion.run, not these.

# KG: finding-ooptdd-bhgman-repairloop-20260712
# KG: adr-seven-commander-legion-architecture-2026-05-27 (legion.run 1-pass → loop 승격)
# KG: LakatosTree_BhgmanCeilingPierce_20260712/repair-loop-production-wire (Q1)
"""

from __future__ import annotations

from engine.legion.legion import Legion
from engine.legion.legion_models import CommanderStage
from engine.legion.repair_stage import make_repair_stage
from engine.naesengmoon.oracle_lens import ScalarOracle

_KG_ANCHOR = "finding-ooptdd-bhgman-repairloop-20260712"

_SPACE = 1_000_000
_TARGET = 987_654
_STEPS = (1, -1, 7, -7, 53, -53, 401, -401, 3001, -3001, 21001, -21001)


def _generate(parents, generation):
    if not parents:
        return [(generation * 2654435761 + 12345) % (_SPACE + 1)]  # blind draw
    base = parents[0]
    return [min(max(base + s, 0), _SPACE) for s in _STEPS]  # read-back hill-climb


def _structured_oracle() -> ScalarOracle:
    return ScalarOracle(name="dist", kind="test", score=lambda x: float(-abs(x - _TARGET)))


def _deceptive_oracle() -> ScalarOracle:
    def deceptive(x: float) -> float:
        if x < 100_000:
            return -float(x) * 0.001
        return 500.0 - abs(x - _TARGET) * 0.0001

    return ScalarOracle(name="deceptive", kind="test", score=deceptive)


def _ev(cid: str, event: str, **attrs) -> dict:
    """Shape one trace event the way the memory backend keys + counts it (cid + event)."""
    return {
        "cid": cid,
        "correlation_id": cid,
        "cycle_id": cid,
        "service": "bhgman.repairloop",
        "event": event,
        **attrs,
    }


def _seed_stage(seed: int = 0) -> CommanderStage:
    """A 1-pass creator stage providing a low-score seed under key 'x' (the repair target)."""
    return CommanderStage(
        name="creator", verb="창조", requires=(), provides=("x",), run=lambda _ctx: {"x": seed}
    )


def emit_repair_phase(backend, cid: str, stage) -> dict:
    """Run the wrapped stage standalone to read the REAL EvolveResult telemetry, and ship one
    'repair_lift_measured' carrying the honest outcome (improved|kept) + lift. On a deceptive
    landscape the guard keeps the seed => outcome:kept => the where:{outcome:improved} gate goes
    RED. The literal lives here."""
    out = stage.run({})
    tel = out["repair"]
    outcome = "improved" if tel["improved"] else "kept"
    backend.ship(
        [
            _ev(
                cid,
                "repair_lift_measured",
                outcome=outcome,
                lift=float(tel["lift"]),
                stop_reason=tel["stop_reason"],
            )
        ]
    )
    return tel


def run_repair_pipeline(backend, cid: str, *, deceptive: bool = False) -> dict:
    """Loop entry (called as ``run_repair_pipeline(backend, cid)``). Drives the REAL
    make_repair_stage: wraps a 1-pass seed stage into an oracle-guided evolve() repair loop, ships
    its lifecycle under ``cid``, and proves it completes inside a production Legion().run().
    'repair_started' / 'repair_stage_wired' / 'repair_complete' live verbatim in THIS symbol.
    ``deceptive`` (twin override) flips the landscape so read-back loses (seed kept)."""
    oracle = _deceptive_oracle() if deceptive else _structured_oracle()
    stage = make_repair_stage(
        _seed_stage(0), oracle=oracle, generate=_generate, max_generations=200, patience=5
    )
    backend.ship([_ev(cid, "repair_started", phase="evolve")])
    tel = emit_repair_phase(backend, cid, stage)
    run = Legion().register(stage).run()  # production pipeline — same Contract must complete
    if run.completed:
        backend.ship([_ev(cid, "repair_stage_wired", stages=run.ran)])
    backend.ship([_ev(cid, "repair_complete", outcome="improved" if tel["improved"] else "kept")])
    return {
        "improved": bool(tel["improved"]),
        "lift": float(tel["lift"]),
        "completed": bool(run.completed),
    }


__all__ = ["emit_repair_phase", "run_repair_pipeline"]
