"""ooptdd trace-gate over the repair-loop production wiring (Q1, ceiling-pierce).

Positive-TDD / log-based gate (ooptdd): the *store* is the judge, not the return value. Drives the
REAL make_repair_stage through ooptdd/repair_loop_adapter.py and re-checks arrival from the store.

Four tests:
  * test_repair_flow_arrives_green
        — run the real repair loop, assert its self-report, then POSITIVELY assert arrival.
  * test_silent_loss_is_caught_by_gate           (axis A)
        — MemoryBackend(drop=True): self-report byte-identical green, gate RED (got=0).
  * test_deceptive_landscape_measures_no_lift     (axis C — outcome tracks the real oracle)
        — a deceptive landscape makes read-back lose; the guard keeps the seed => outcome:kept =>
          the where:{outcome:improved} count is RED. Proves the flag is not a constant.
  * test_longinus_binding_is_real                 (axis B)
        — each must_emit literal lives in its bound ADAPTER symbol; renamed => UNBOUND.

# KG: finding-ooptdd-bhgman-repairloop-20260712
# KG: LakatosTree_BhgmanCeilingPierce_20260712/repair-loop-production-wire (Q1)
"""

from __future__ import annotations

from pathlib import Path

import pytest

# ooptdd/ooptdd_loop = dev-only methodology siblings (private, not on any index). CI does not
# install them, so skip these instrumentation tests there — like the existing commander twins.
pytest.importorskip("ooptdd.backends")
pytest.importorskip("ooptdd_loop")

from ooptdd.backends.memory import MemoryBackend, reset  # noqa: E402
from ooptdd.engine.gate import evaluate, load_gate  # noqa: E402
from ooptdd_loop.domain.spec import Longinus  # noqa: E402
from ooptdd_loop.engine.longinus import verify_binding  # noqa: E402

from ooptdd.repair_loop_adapter import _KG_ANCHOR, run_repair_pipeline  # noqa: E402

_GATE_PATH = str(Path(__file__).parent / "gates" / "repair_loop_flow.yaml")
_ROOT = str(Path(__file__).resolve().parents[3])
_ADAPTER_SRC = "ooptdd/repair_loop_adapter.py"


@pytest.fixture(autouse=True)
def _clean_store():
    reset()
    yield
    reset()


def _explain(result: dict) -> str:
    bad = [c for c in result.get("checks", []) if not c.get("passed", True)]
    return f"gate not green; failing checks={bad}; full={result}"


def _broke(result: dict, event: str) -> list:
    return [c for c in result["checks"] if not c.get("passed", True) and c.get("event") == event]


def test_repair_flow_arrives_green(monkeypatch):
    """Positive wing: the real make_repair_stage repair loop runs, self-reports an improvement AND
    completes inside a production Legion().run(), and the store independently confirms the whole
    lifecycle arrived (gate ['ok'] is True)."""
    cid = "repair-loop-green"
    monkeypatch.setenv("OOPTDD_CID", cid)

    backend = MemoryBackend()
    report = run_repair_pipeline(backend, cid)

    # (a) self-report — necessary but NOT sufficient.
    assert report["improved"] is True
    assert report["completed"] is True

    # (b) the STORE is the judge.
    result = evaluate(backend, load_gate(_GATE_PATH))
    assert result["ok"] is True, _explain(result)
    assert result.get("reachable", True) is True


def test_silent_loss_is_caught_by_gate(monkeypatch):
    """MANDATORY counter-test (axis A): drop=True. The return value is byte-identical green, yet
    the gate reads the store and goes RED."""
    cid = "repair-loop-droploss"
    monkeypatch.setenv("OOPTDD_CID", cid)

    backend = MemoryBackend(drop=True)
    report = run_repair_pipeline(backend, cid)
    assert report["improved"] is True and report["completed"] is True

    result = evaluate(backend, load_gate(_GATE_PATH))
    assert result["ok"] is False, f"silent-loss MUST turn the gate RED. {result}"
    failed = [c for c in result["checks"] if not c.get("passed", True)]
    assert any(c.get("got") == 0 for c in failed), f"expected got=0; failed={failed}"


def test_deceptive_landscape_measures_no_lift(monkeypatch):
    """Honest-count proof (axis C): on a deceptive landscape read-back loses and the adapter keeps
    the seed => outcome:kept => the where:{outcome:improved} count reads got=0 => RED. The outcome
    tracks the REAL oracle result, never a constant 'improved'."""
    cid = "repair-loop-deceptive"
    monkeypatch.setenv("OOPTDD_CID", cid)

    backend = MemoryBackend()
    report = run_repair_pipeline(backend, cid, deceptive=True)
    assert report["improved"] is False  # honest guard kept the seed
    assert report["completed"] is True  # ...yet the stage still wired + completed in Legion

    result = evaluate(backend, load_gate(_GATE_PATH))
    assert result["ok"] is False, f"a no-lift landscape must turn the gate RED. {result}"
    broke = _broke(result, "repair_lift_measured")
    assert broke and broke[0].get("got") == 0, (
        f"repair_lift_measured should read got=0 when the seed is kept; checks={result['checks']}"
    )


def test_longinus_binding_is_real():
    """Binding proof (axis B): each must_emit literal genuinely lives in its bound ADAPTER symbol,
    and a renamed literal goes UNBOUND — the Longinus binding discriminates."""
    cases = [
        ("run_repair_pipeline", "repair_started"),
        ("run_repair_pipeline", "repair_stage_wired"),
        ("run_repair_pipeline", "repair_complete"),
        ("emit_repair_phase", "repair_lift_measured"),
    ]
    for symbol, literal in cases:
        bound = verify_binding(_ROOT, Longinus(_KG_ANCHOR, _ADAPTER_SRC, symbol, literal))
        assert bound.bound is True, f"{symbol} should emit {literal}: {bound.reason}"
        miss = verify_binding(
            _ROOT, Longinus(_KG_ANCHOR, _ADAPTER_SRC, symbol, literal + "_RENAMED")
        )
        assert miss.bound is False, f"{symbol} must NOT bind a renamed literal"
