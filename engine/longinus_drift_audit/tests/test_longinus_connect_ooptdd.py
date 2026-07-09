"""ooptdd trace-gate over bhgman_tool's longinus 연결(connect) CREATE-binding flow.

Positive-TDD / log-based gate (ooptdd): the *store* is the judge, not the return value.
We drive the REAL engine through ooptdd/longinus_connect_adapter.py — materialize a seeded
'# KG:' ref into a bound ReferenceSite (with a second un-seeded ref discriminated as an
orphan) + bind_file over real unbound public symbols — and the gate in
gates/longinus_connect_flow.yaml independently re-checks arrival, every threshold matching
the real MaterializeResult / BindResult.

Four tests:
  * test_longinus_connect_flow_arrives_green
        — run the real connect, assert its self-report, then POSITIVELY assert arrival.
  * test_silent_loss_is_caught_by_gate            (axis A)
        — MemoryBackend(drop=True): self-report byte-identical green, gate RED (got=0).
  * test_drop_the_seed_flips_bound_to_orphan      (axis C, orphan_discrimination)
        — seed_bound=False: the bound ref flips to orphan; bound 1->0 so the
          longinus_binding_materialized==1 check goes RED, proving the count tracks the
          real has_node materialization, not a constant.
  * test_longinus_binding_is_real                 (axis B)
        — each must_emit literal lives in its bound ADAPTER symbol; renamed => UNBOUND.

# KG: ATOM_Skill_longinus
"""

from __future__ import annotations

from pathlib import Path

import pytest

# ooptdd/ooptdd_loop = dev-only methodology siblings (private, not on any index). CI does not
# install them, so skip these instrumentation tests there — like the leiden/lean optional-tool
# tests. The engine behaviour they trace-gate is covered by the regular tests.
pytest.importorskip("ooptdd.backends")
pytest.importorskip("ooptdd_loop")

from ooptdd.backends.memory import MemoryBackend, reset
from ooptdd.engine.gate import evaluate, load_gate
from ooptdd_loop.engine.longinus import verify_binding
from ooptdd_loop.domain.spec import Longinus

from ooptdd.longinus_connect_adapter import _KG_ANCHOR, run_longinus_connect_pipeline

_GATE_PATH = str(Path(__file__).parent / "gates" / "longinus_connect_flow.yaml")
# repo root = tests -> longinus_drift_audit -> engine -> <root>; Longinus source is repo-relative.
_ROOT = str(Path(__file__).resolve().parents[3])
_ADAPTER_SRC = "ooptdd/longinus_connect_adapter.py"


@pytest.fixture(autouse=True)
def _clean_store():
    reset()
    yield
    reset()


def _explain(result: dict) -> str:
    bad = [c for c in result.get("checks", []) if not c.get("passed", True)]
    return f"gate not green; failing checks={bad}; full={result}"


def test_longinus_connect_flow_arrives_green(monkeypatch):
    """Positive wing: the real materialize + symbol-bind runs, self-reports, AND the store
    independently confirms the whole lifecycle arrived (gate ['ok'] is True)."""
    cid = "longinus-connect-green"
    monkeypatch.setenv("OOPTDD_CID", cid)

    backend = MemoryBackend()
    report = run_longinus_connect_pipeline(backend, cid)

    # (a) self-report — necessary but NOT sufficient.
    assert report["bound"] == 1  # NODE_BOUND_A materialized (has_node seed)
    assert report["orphans"] == 1  # NODE_ORPHAN_B discriminated as orphan
    assert report["symbols"] == 2  # alpha + beta bound (PROPOSE)

    # (b) the STORE is the judge.
    result = evaluate(backend, load_gate(_GATE_PATH))
    assert result["ok"] is True, _explain(result)
    assert result.get("reachable", True) is True


def test_silent_loss_is_caught_by_gate(monkeypatch):
    """MANDATORY counter-test (axis A): drop=True. The return value is byte-identical green,
    yet the gate reads the store and goes RED — the blind spot a return test cannot see."""
    cid = "longinus-connect-droploss"
    monkeypatch.setenv("OOPTDD_CID", cid)

    backend = MemoryBackend(drop=True)
    report = run_longinus_connect_pipeline(backend, cid)

    assert report["bound"] == 1 and report["orphans"] == 1 and report["symbols"] == 2

    result = evaluate(backend, load_gate(_GATE_PATH))
    assert result["ok"] is False, f"silent-loss MUST turn the gate RED. {result}"
    failed = [c for c in result["checks"] if not c.get("passed", True)]
    assert any(c.get("got") == 0 for c in failed), f"expected got=0; failed={failed}"


def test_drop_the_seed_flips_bound_to_orphan(monkeypatch):
    """Honest-count + orphan_discrimination proof (axis C): without the has_node seed the
    bound ref flips to an orphan, so bound 1->0 and the value-pinned
    longinus_binding_materialized==1 check goes RED — the count tracks the real
    materialization, not a hard-typed constant."""
    cid = "longinus-connect-dropseed"
    monkeypatch.setenv("OOPTDD_CID", cid)

    backend = MemoryBackend()
    report = run_longinus_connect_pipeline(backend, cid, seed_bound=False)
    assert report["bound"] == 0  # nothing pre-exists => everything orphan
    assert report["orphans"] == 2  # both refs now node_absent orphans

    result = evaluate(backend, load_gate(_GATE_PATH))
    assert result["ok"] is False, f"dropped seed must turn the gate RED. {result}"
    broke = [
        c
        for c in result["checks"]
        if not c.get("passed", True) and c.get("event") == "longinus_binding_materialized"
    ]
    assert broke and broke[0].get("got") == 0, (
        f"binding_materialized should read got=0 against the ==1 pin; checks={result['checks']}"
    )


def test_longinus_binding_is_real():
    """Binding proof (axis B): each must_emit literal genuinely lives in its bound ADAPTER
    symbol, and a renamed literal goes UNBOUND — the Longinus binding discriminates."""
    cases = [
        ("run_longinus_connect_pipeline", "longinus_connect_complete"),
        ("emit_materialize_phase", "longinus_binding_materialized"),
        ("emit_materialize_phase", "longinus_orphan_ref_skipped"),
        ("emit_symbol_bind_phase", "longinus_symbol_bound"),
    ]
    for symbol, literal in cases:
        bound = verify_binding(_ROOT, Longinus(_KG_ANCHOR, _ADAPTER_SRC, symbol, literal))
        assert bound.bound is True, f"{symbol} should emit {literal}: {bound.reason}"
        miss = verify_binding(
            _ROOT, Longinus(_KG_ANCHOR, _ADAPTER_SRC, symbol, literal + "_RENAMED")
        )
        assert miss.bound is False, f"{symbol} must NOT bind a renamed literal"
