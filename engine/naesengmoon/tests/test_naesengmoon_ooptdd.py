"""ooptdd trace-gate over bhgman_tool's naesengmoon 검증(verdict) flow.

Positive-TDD / log-based gate (ooptdd): the *store* is the judge, not the return value.
We drive REAL engine work through ooptdd/naesengmoon_adapter.py — EARN all four upstream
provides by running the four real upstream engines, aggregate a real oracle ensemble, and run
the real `verify('lean-goals', lean/SeedLifecycle.lean)` Lean subprocess (the substrate-disjoint
territory floor) — and the gate in gates/naesengmoon_flow.yaml re-checks arrival.

Five tests:
  * test_naesengmoon_flow_arrives_green
        — run the real verdict, assert its self-report, then POSITIVELY assert arrival.
  * test_silent_loss_is_caught_by_gate          (axis A)
        — MemoryBackend(drop=True): self-report byte-identical green, gate RED (got=0).
  * test_upstream_seed_drop_is_red              (axis C — earned upstream)
        — drop one upstream engine's seed => upstream_present 4->3 => the ==4 check is RED.
  * test_lean_floor_refutes_on_broken_target    (axis C — the territory leg)
        — point the Lean leg at a non-compiling .lean: the floor is honestly passed=false, so
          naesengmoon_oracle_verified{passed:true}==1 goes RED. The territory floor cannot be
          faked by an in-memory stub.
  * test_longinus_binding_is_real               (axis B)
        — each must_emit literal lives in its bound ADAPTER symbol; renamed => UNBOUND.

# KG: naesengmoon-canonical-2026-05-19
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from ooptdd.backends.memory import MemoryBackend, reset
from ooptdd.engine.gate import evaluate, load_gate
from ooptdd_loop.longinus import verify_binding
from ooptdd_loop.spec import Longinus

from ooptdd.naesengmoon_adapter import _KG_ANCHOR, run_naesengmoon_pipeline

_GATE_PATH = str(Path(__file__).parent / "gates" / "naesengmoon_flow.yaml")
_ROOT = str(Path(__file__).resolve().parents[3])
_ADAPTER_SRC = "ooptdd/naesengmoon_adapter.py"


@pytest.fixture(autouse=True)
def _clean_store():
    reset()
    yield
    reset()


def _explain(result: dict) -> str:
    bad = [c for c in result.get("checks", []) if not c.get("passed", True)]
    return f"gate not green; failing checks={bad}; full={result}"


def _broke(result: dict, event: str) -> list:
    return [
        c for c in result["checks"]
        if not c.get("passed", True) and c.get("event") == event
    ]


def test_naesengmoon_flow_arrives_green(monkeypatch):
    """Positive wing: the real verdict runs, self-reports, AND the store independently confirms
    the whole lifecycle arrived (gate ['ok'] is True)."""
    cid = "naesengmoon-verdict-green"
    monkeypatch.setenv("OOPTDD_CID", cid)

    backend = MemoryBackend()
    report = run_naesengmoon_pipeline(backend, cid)

    # (a) self-report — necessary but NOT sufficient.
    assert report["upstream_present"] == 4
    assert report["n_oracle"] == 2
    assert report["floor_passed"] is True

    # (b) the STORE is the judge.
    result = evaluate(backend, load_gate(_GATE_PATH))
    assert result["ok"] is True, _explain(result)
    assert result.get("reachable", True) is True


def test_silent_loss_is_caught_by_gate(monkeypatch):
    """MANDATORY counter-test (axis A): drop=True. The return value is byte-identical green,
    yet the gate reads the store and goes RED."""
    cid = "naesengmoon-verdict-droploss"
    monkeypatch.setenv("OOPTDD_CID", cid)

    backend = MemoryBackend(drop=True)
    report = run_naesengmoon_pipeline(backend, cid)
    assert report["upstream_present"] == 4 and report["floor_passed"] is True

    result = evaluate(backend, load_gate(_GATE_PATH))
    assert result["ok"] is False, f"silent-loss MUST turn the gate RED. {result}"
    failed = [c for c in result["checks"] if not c.get("passed", True)]
    assert any(c.get("got") == 0 for c in failed), f"expected got=0; failed={failed}"


def test_upstream_seed_drop_is_red(monkeypatch):
    """Honest-count proof (axis C, earned upstream): drop one upstream engine's seed so that
    provides is genuinely absent — upstream_present 4->3 and the ==4 check goes RED. The count
    tracks four REAL engine runs, not a hand-typed 4."""
    cid = "naesengmoon-verdict-dropup"
    monkeypatch.setenv("OOPTDD_CID", cid)

    backend = MemoryBackend()
    report = run_naesengmoon_pipeline(backend, cid, drop="acquired")
    assert report["upstream_present"] == 3  # one upstream engine produced nothing

    result = evaluate(backend, load_gate(_GATE_PATH))
    assert result["ok"] is False, f"a missing upstream must turn the gate RED. {result}"
    broke = _broke(result, "naesengmoon_upstream_present")
    assert broke and broke[0].get("got") == 3, (
        f"upstream_present should read got=3 against the ==4 pin; checks={result['checks']}"
    )


def test_lean_floor_refutes_on_broken_target(monkeypatch):
    """Honest-count proof (axis C, the territory leg): point the Lean floor at a .lean that does
    not compile. The substrate-disjoint oracle is honestly passed=false, so
    naesengmoon_oracle_verified{passed:true}==1 goes RED. No in-memory stub can manufacture a
    passing Lean exit — this is the corroborated, territory-grade leg."""
    cid = "naesengmoon-verdict-leanfail"
    monkeypatch.setenv("OOPTDD_CID", cid)

    d = Path(tempfile.mkdtemp(prefix="naesengmoon_lean_"))
    (d / "Bad.lean").write_text('example : Nat := "not a nat"\n')  # genuine type error

    backend = MemoryBackend()
    report = run_naesengmoon_pipeline(backend, cid, lean_target=str(d / "Bad.lean"))
    assert report["floor_passed"] is False  # the Lean process refuted it

    result = evaluate(backend, load_gate(_GATE_PATH))
    assert result["ok"] is False, f"a refuted Lean floor must turn the gate RED. {result}"
    broke = _broke(result, "naesengmoon_oracle_verified")
    assert broke and broke[0].get("got") == 0, (
        f"oracle_verified(passed:true) should read got=0 on a broken Lean target; "
        f"checks={result['checks']}"
    )


def test_longinus_binding_is_real():
    """Binding proof (axis B): each must_emit literal genuinely lives in its bound ADAPTER
    symbol, and a renamed literal goes UNBOUND — the Longinus binding discriminates."""
    cases = [
        ("run_naesengmoon_pipeline", "naesengmoon_verdict_complete"),
        ("emit_upstream_phase", "naesengmoon_upstream_present"),
        ("emit_ensemble_phase", "naesengmoon_ensemble_aggregated"),
        ("emit_oracle_floor_phase", "naesengmoon_oracle_verified"),
    ]
    for symbol, literal in cases:
        bound = verify_binding(_ROOT, Longinus(_KG_ANCHOR, _ADAPTER_SRC, symbol, literal))
        assert bound.bound is True, f"{symbol} should emit {literal}: {bound.reason}"
        miss = verify_binding(
            _ROOT, Longinus(_KG_ANCHOR, _ADAPTER_SRC, symbol, literal + "_RENAMED")
        )
        assert miss.bound is False, f"{symbol} must NOT bind a renamed literal"
