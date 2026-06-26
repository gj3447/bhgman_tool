"""ooptdd-loop in_process target — binds naesengmoon 검증(verdict) to REAL engine work.

naesengmoon is the legion's verdict gate: it requires all four upstream provides
(acquired/bindings/abstractions/hygiene) and issues a verdict drawn from a decorrelated oracle
ensemble + a substrate-disjoint Lean floor.

Honest-count contract (verified, STEP-0 baseline):
    - upstream_present (==4): EARNED by genuinely running the FOUR real upstream engines
      (prometheus run_acquire, longinus materialize, eureka run_from_kg, occam run_occam) and
      counting those that produced a real artifact — NOT by hand-building {mode:'ok'} dicts.
      Drop any one engine's seed and the count drops to 3 => RED.
    - n_oracle (==2): a REAL decorrelation.aggregate over >=1 ORACLE CriticVerdict, each
      ``passed`` taken from a real deterministic oracle run (lean-goals + occam-twins).
    - oracle_verified (==1, where passed:true): the REAL ``verify('lean-goals',
      lean/SeedLifecycle.lean)`` subprocess — score = closed goals iff ``lean`` exits 0. Point
      it at a .lean that fails to compile and it is honestly REFUTED (passed=False) => RED. This
      is the ONLY territory-grade leg; no in-memory mock can earn it.

    HONESTY DISCLOSURE: upstream_present and n_oracle are single-authority / derived-self
    (computed by this adapter from its own runs). Only ``naesengmoon_oracle_verified`` is
    corroborated by an independent substrate (the Lean process exit). The gate labels this.

Longinus binding (AST-checked): each must_emit literal lives VERBATIM in its ADAPTER symbol
    (``emit_upstream_phase`` / ``emit_ensemble_phase`` / ``emit_oracle_floor_phase`` /
    ``run_naesengmoon_pipeline``) — NEVER inside ``engine/naesengmoon/``. Rename => UNBOUND/RED.

# KG: finding-ooptdd-bhgman-naesengmoon-adapter-20260625
# KG: naesengmoon-canonical-2026-05-19
"""
from __future__ import annotations

from engine.eureka.pipeline import PipelineConfig, run_from_kg
from engine.longinus_drift_audit import forward_binding_materialize as _fbm
from engine.naesengmoon.decorrelation import CriticKind, CriticVerdict, aggregate
from engine.naesengmoon.verify import verify
from engine.occam.occam_runner import run_occam

# Reuse the four upstream commanders' proven real seeds (this verify commander sits downstream
# of all four — depending on their adapters is the contract, not a leak).
from ooptdd.eureka_adapter import _cluster_runner
from ooptdd.longinus_connect_adapter import _materialize_code_root
from ooptdd.occam_adapter import (
    _CLEAN_ROWS,
    _EXACT_DUP_ROWS,
    _matched_write_runner,
    _read_runner,
)
from ooptdd.prometheus_adapter import _run_real_acquire

_KG_ANCHOR = "finding-ooptdd-bhgman-naesengmoon-adapter-20260625"
_SEED_LEAN = "lean/SeedLifecycle.lean"  # a self-contained, compiling .lean (8 closed goals)


def _ev(cid: str, event: str, **attrs) -> dict:
    """Shape one trace event the way the memory backend keys + counts it (cid + event)."""
    return {
        "cid": cid,
        "correlation_id": cid,
        "cycle_id": cid,
        "service": "bhgman.naesengmoon",
        "event": event,
        **attrs,
    }


def _earn_upstream(*, drop: str | None = None) -> dict:
    """Run the FOUR real upstream engines and return {key: produced_bool}. Each provides is
    EARNED from a real engine artifact (never a hand-built dict). ``drop`` makes one engine's
    seed empty so that provides is absent — the drop-the-seed RED proof."""
    out: dict[str, bool] = {}
    rep = _run_real_acquire(apply=False, corpus=({} if drop == "acquired" else None))
    out["acquired"] = len(rep.findings) > 0
    kg, root = _materialize_code_root(seed_bound=(drop != "bindings"))
    out["bindings"] = _fbm.materialize(kg, root).bound > 0
    runner = (lambda _q, _p: []) if drop == "abstractions" else _cluster_runner
    pr = run_from_kg(runner, PipelineConfig(cycle_id="naesengmoon-upstream"))
    induce = next((s for s in pr.stages if s.stage.startswith("4-induce")), None)
    out["abstractions"] = bool(induce and (induce.payload or {}).get("abstract_classes", 0) > 0)
    rows = _CLEAN_ROWS if drop == "hygiene" else _EXACT_DUP_ROWS
    res = run_occam(_read_runner(rows), write_cypher=_matched_write_runner(), apply=False)
    out["hygiene"] = res.report.superseded_count > 0
    return out


def _build_ensemble(lean_passed: bool):
    """A REAL decorrelation ensemble of ORACLE critics. Each critic's ``passed`` is a real
    deterministic-oracle result (the Lean floor + a real occam-twins recount), so n_oracle is
    earned, not hand-set."""
    occ = verify("occam-twins", run_cypher=_read_runner(_CLEAN_ROWS))
    critics = [
        CriticVerdict(lens="lean", kind=CriticKind.ORACLE, passed=lean_passed),
        CriticVerdict(lens="occam-twins", kind=CriticKind.ORACLE, passed=occ.passed),
    ]
    return aggregate(critics)


def emit_upstream_phase(backend, cid: str, upstream: dict) -> int:
    """Ship one 'naesengmoon_upstream_present' per upstream provides EARNED from a real engine.
    Count RE-DERIVED from the real engine runs (drop a seed => fewer => RED). Literal lives here."""
    for key, produced in upstream.items():
        if produced:
            backend.ship([_ev(cid, "naesengmoon_upstream_present", provides=key)])
    return sum(1 for v in upstream.values() if v)


def emit_ensemble_phase(backend, cid: str, ensemble) -> int:
    """Ship one 'naesengmoon_ensemble_aggregated' per ORACLE critic in the real aggregate.
    Count = ensemble.n_oracle (single-authority — charged honestly). Literal lives here."""
    for _ in range(ensemble.n_oracle):
        backend.ship([_ev(cid, "naesengmoon_ensemble_aggregated", verdict=ensemble.verdict)])
    return ensemble.n_oracle


def emit_oracle_floor_phase(backend, cid: str, lean_verdict) -> int:
    """Ship 'naesengmoon_oracle_verified' carrying the REAL Lean floor result (passed iff the
    ``lean`` subprocess exited 0). This is the territory-grade leg — a non-compiling target is
    honestly passed=False, which the where:{passed:true} gate reads as RED. Literal lives here."""
    backend.ship([
        _ev(cid, "naesengmoon_oracle_verified", passed=bool(lean_verdict.passed),
            closed_goals=int(lean_verdict.score) if lean_verdict.passed else 0, kind="lean-goals")
    ])
    return 1 if lean_verdict.passed else 0


def run_naesengmoon_pipeline(backend, cid: str, *, drop: str | None = None,
                             lean_target: str = _SEED_LEAN, lean_dir: str = ".") -> dict:
    """Loop entry (called as ``run_naesengmoon_pipeline(backend, cid)``). Runs the REAL verify
    chain — EARN the 4 upstream provides, aggregate a real oracle ensemble, and run the real
    Lean floor — and ships the lifecycle under ``cid``. The 'naesengmoon_verify_entered' and
    'naesengmoon_verdict_complete' literals live verbatim in THIS symbol.

    ``drop`` / ``lean_target`` default to the green path; the twin test overrides them for the
    upstream-seed-drop and Lean-floor-refute RED proofs."""
    backend.ship([_ev(cid, "naesengmoon_verify_entered", phase="gate")])
    upstream = _earn_upstream(drop=drop)
    lean_verdict = verify("lean-goals", lean_target, lean_dir=lean_dir)
    ensemble = _build_ensemble(lean_verdict.passed)

    n_up = emit_upstream_phase(backend, cid, upstream)
    n_oracle = emit_ensemble_phase(backend, cid, ensemble)
    n_floor = emit_oracle_floor_phase(backend, cid, lean_verdict)
    backend.ship([
        _ev(cid, "naesengmoon_verdict_complete", upstream_present=n_up, n_oracle=n_oracle,
            floor_passed=bool(n_floor), verdict=ensemble.verdict)
    ])
    return {
        "upstream_present": n_up,
        "n_oracle": n_oracle,
        "floor_passed": bool(n_floor),
        "verdict": ensemble.verdict,
    }


__all__ = [
    "emit_ensemble_phase",
    "emit_oracle_floor_phase",
    "emit_upstream_phase",
    "run_naesengmoon_pipeline",
]
