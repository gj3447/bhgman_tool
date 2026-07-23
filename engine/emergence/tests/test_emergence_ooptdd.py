"""ooptdd trace-gate over engineboy 창발(emergence) 엔진.

Positive-TDD / log-based gate: the *store* is the judge, not the return value. We drive the
REAL engine through ooptdd/emergence_adapter.py — recover Hebbian clusters, isolate a private
doc from a near-embedding public query, converge a Hawkes stream — and the gate in
gates/emergence_flow.yaml re-checks arrival.

Six tests:
  * test_emergence_flow_arrives_green
        — run the real pipeline, assert its self-report, then POSITIVELY assert arrival.
  * test_silent_loss_is_caught_by_gate            (axis A)
        — MemoryBackend(drop=True): self-report green, gate RED (got=0).
  * test_noise_recovers_no_cluster                (axis C — cluster tracks real Hebbian)
        — global-random co-access (no latent structure) => emergence_cluster_recovered==1 RED.
  * test_leaked_private_is_not_isolated           (axis C — isolation is real)
        — private→public => public query lands => emergence_private_isolated==1 RED.
  * test_short_run_does_not_converge              (axis C — convergence is real)
        — 5-event run => |w−w*| ≫ tol => emergence_weight_converged==1 RED.
  * test_longinus_binding_is_real                 (axis B)
        — each must_emit literal lives in its bound ADAPTER symbol; renamed => UNBOUND.

# KG: finding-ooptdd-bhgman-emergence-adapter-20260713
"""
from __future__ import annotations

from pathlib import Path

import pytest

# ooptdd/ooptdd_loop = dev-only methodology siblings; CI does not install them.
pytest.importorskip("ooptdd.backends")
pytest.importorskip("ooptdd_loop")

from ooptdd.backends.memory import MemoryBackend, reset  # noqa: E402
from ooptdd.engine.gate import evaluate, load_gate  # noqa: E402
from ooptdd_loop.engine.longinus import verify_binding  # noqa: E402
from ooptdd_loop.domain.spec import Longinus  # noqa: E402

from ooptdd.emergence_adapter import _KG_ANCHOR, run_emergence_pipeline  # noqa: E402

_GATE_PATH = str(Path(__file__).parent / "gates" / "emergence_flow.yaml")
_ROOT = str(Path(__file__).resolve().parents[3])
_ADAPTER_SRC = "ooptdd/emergence_adapter.py"


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


def test_emergence_flow_arrives_green(monkeypatch):
    cid = "emergence-green"
    monkeypatch.setenv("OOPTDD_CID", cid)

    backend = MemoryBackend()
    report = run_emergence_pipeline(backend, cid)

    # (a) self-report — necessary but NOT sufficient.
    assert report == {"cluster": 1, "isolated": 1, "converged": 1}

    # (b) the STORE is the judge.
    result = evaluate(backend, load_gate(_GATE_PATH))
    assert result["ok"] is True, _explain(result)


def test_silent_loss_is_caught_by_gate(monkeypatch):
    cid = "emergence-droploss"
    monkeypatch.setenv("OOPTDD_CID", cid)

    backend = MemoryBackend(drop=True)
    report = run_emergence_pipeline(backend, cid)
    assert report == {"cluster": 1, "isolated": 1, "converged": 1}  # green return

    result = evaluate(backend, load_gate(_GATE_PATH))
    assert result["ok"] is False, f"silent-loss MUST turn the gate RED. {result}"
    assert any(c.get("got") == 0 for c in result["checks"] if not c.get("passed", True))


def test_noise_recovers_no_cluster(monkeypatch):
    cid = "emergence-noise"
    monkeypatch.setenv("OOPTDD_CID", cid)

    backend = MemoryBackend()
    report = run_emergence_pipeline(backend, cid, noise=True)
    assert report["cluster"] == 0  # 잠재구조 없음 => 창발 없음

    result = evaluate(backend, load_gate(_GATE_PATH))
    assert result["ok"] is False, f"noise must turn the gate RED. {result}"
    broke = _broke(result, "emergence_cluster_recovered")
    assert broke and broke[0].get("got") == 0


def test_leaked_private_is_not_isolated(monkeypatch):
    cid = "emergence-leak"
    monkeypatch.setenv("OOPTDD_CID", cid)

    backend = MemoryBackend()
    report = run_emergence_pipeline(backend, cid, leak=True)
    assert report["isolated"] == 0  # private→public => 착지 => 격리 실패

    result = evaluate(backend, load_gate(_GATE_PATH))
    assert result["ok"] is False, f"a leaked private must turn the gate RED. {result}"
    broke = _broke(result, "emergence_private_isolated")
    assert broke and broke[0].get("got") == 0


def test_short_run_does_not_converge(monkeypatch):
    cid = "emergence-short"
    monkeypatch.setenv("OOPTDD_CID", cid)

    backend = MemoryBackend()
    report = run_emergence_pipeline(backend, cid, short=True)
    assert report["converged"] == 0  # 5-event => 미수렴

    result = evaluate(backend, load_gate(_GATE_PATH))
    assert result["ok"] is False, f"a short run must turn the gate RED. {result}"
    broke = _broke(result, "emergence_weight_converged")
    assert broke and broke[0].get("got") == 0


def test_longinus_binding_is_real():
    cases = [
        ("run_emergence_pipeline", "emergence_run_complete"),
        ("emit_cluster_phase", "emergence_cluster_recovered"),
        ("emit_isolation_phase", "emergence_private_isolated"),
        ("emit_convergence_phase", "emergence_weight_converged"),
    ]
    for symbol, literal in cases:
        bound = verify_binding(_ROOT, Longinus(_KG_ANCHOR, _ADAPTER_SRC, symbol, literal))
        assert bound.bound is True, f"{symbol} should emit {literal}: {bound.reason}"
        miss = verify_binding(
            _ROOT, Longinus(_KG_ANCHOR, _ADAPTER_SRC, symbol, literal + "_RENAMED")
        )
        assert miss.bound is False, f"{symbol} must NOT bind a renamed literal"
