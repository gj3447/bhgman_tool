"""ooptdd trace-gate over bhgman_tool's hades 실현(realize) flow — the legion DAG terminus.

Positive-TDD / log-based gate (ooptdd): the *store* is the judge, not the return value.
We drive the REAL engine through ooptdd/hades_adapter.py — seed a Dog/Cat family sharing a
structurally-identical speak(), lift it into a base, and APPLY the refactor only behind a
real characterization-test gate (on-disk path) — and the gate in gates/hades_realize_flow.yaml
re-checks arrival.

Five tests:
  * test_hades_flow_arrives_green
        — run the real realize, assert its self-report, then POSITIVELY assert arrival.
  * test_silent_loss_is_caught_by_gate          (axis A)
        — MemoryBackend(drop=True): self-report byte-identical green, gate RED (got=0).
  * test_divergent_family_extracts_nothing      (axis C — extracted tracks the real ast LGG)
        — Cat.speak returns 'meow': no structurally-identical method => hades_extracted==1 RED.
  * test_failing_gate_reverts_and_does_not_apply (axis C — APPLIED backed by a passing subprocess)
        — a failing test_cmd reverts the file byte-for-byte and ships no hades_gate_applied =>
          the ==1 check is RED. The realization is gated on a genuinely-passing test.
  * test_longinus_binding_is_real               (axis B)
        — each must_emit literal lives in its bound ADAPTER symbol; renamed => UNBOUND.

# KG: hades-canonical-2026-05-27
"""
from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("libcst")  # the on-disk apply path is format-preserving (libcst)

from ooptdd.backends.memory import MemoryBackend, reset  # noqa: E402
from ooptdd.engine.gate import evaluate, load_gate  # noqa: E402
from ooptdd_loop.longinus import verify_binding  # noqa: E402
from ooptdd_loop.spec import Longinus  # noqa: E402

from ooptdd.hades_adapter import _KG_ANCHOR, run_hades_pipeline  # noqa: E402

_GATE_PATH = str(Path(__file__).parent / "gates" / "hades_realize_flow.yaml")
_ROOT = str(Path(__file__).resolve().parents[3])
_ADAPTER_SRC = "ooptdd/hades_adapter.py"


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


def test_hades_flow_arrives_green(monkeypatch):
    """Positive wing: the real on-disk realize runs, self-reports, AND the store independently
    confirms the whole lifecycle arrived (gate ['ok'] is True)."""
    cid = "hades-realize-green"
    monkeypatch.setenv("OOPTDD_CID", cid)

    backend = MemoryBackend()
    report = run_hades_pipeline(backend, cid)

    # (a) self-report — necessary but NOT sufficient.
    assert report["extracted"] == 1
    assert report["applied"] == 1

    # (b) the STORE is the judge.
    result = evaluate(backend, load_gate(_GATE_PATH))
    assert result["ok"] is True, _explain(result)
    assert result.get("reachable", True) is True


def test_silent_loss_is_caught_by_gate(monkeypatch):
    """MANDATORY counter-test (axis A): drop=True. The return value is byte-identical green,
    yet the gate reads the store and goes RED."""
    cid = "hades-realize-droploss"
    monkeypatch.setenv("OOPTDD_CID", cid)

    backend = MemoryBackend(drop=True)
    report = run_hades_pipeline(backend, cid)
    assert report["extracted"] == 1 and report["applied"] == 1

    result = evaluate(backend, load_gate(_GATE_PATH))
    assert result["ok"] is False, f"silent-loss MUST turn the gate RED. {result}"
    failed = [c for c in result["checks"] if not c.get("passed", True)]
    assert any(c.get("got") == 0 for c in failed), f"expected got=0; failed={failed}"


def test_divergent_family_extracts_nothing(monkeypatch):
    """Honest-count proof (axis C, extracted): a divergent family (Cat.speak returns 'meow') has
    NO structurally-identical method, so common_methods==[] => hades_extracted==1 goes RED. The
    count tracks the real ast LGG, not a constant."""
    cid = "hades-realize-divergent"
    monkeypatch.setenv("OOPTDD_CID", cid)

    backend = MemoryBackend()
    report = run_hades_pipeline(backend, cid, divergent=True)
    assert report["extracted"] == 0 and report["applied"] == 0

    result = evaluate(backend, load_gate(_GATE_PATH))
    assert result["ok"] is False, f"a divergent family must turn the gate RED. {result}"
    broke = _broke(result, "hades_extracted")
    assert broke and broke[0].get("got") == 0, (
        f"hades_extracted should read got=0 on a divergent family; checks={result['checks']}"
    )


def test_failing_gate_reverts_and_does_not_apply(monkeypatch):
    """Honest-count proof (axis C, APPLIED backed by a passing subprocess): a failing
    characterization test_cmd reverts the file byte-for-byte and ships no hades_gate_applied =>
    the ==1 check is RED. Proves APPLIED is gated on a genuinely-passing test, not the write."""
    cid = "hades-realize-revert"
    monkeypatch.setenv("OOPTDD_CID", cid)

    backend = MemoryBackend()
    report = run_hades_pipeline(backend, cid, fail_test=True)
    assert report["extracted"] == 1     # the method IS extractable...
    assert report["applied"] == 0       # ...but the gate failed => REVERTED, nothing applied

    result = evaluate(backend, load_gate(_GATE_PATH))
    assert result["ok"] is False, f"a reverted gate must turn the gate RED. {result}"
    broke = _broke(result, "hades_gate_applied")
    assert broke and broke[0].get("got") == 0, (
        f"hades_gate_applied should read got=0 when reverted; checks={result['checks']}"
    )


def test_longinus_binding_is_real():
    """Binding proof (axis B): each must_emit literal genuinely lives in its bound ADAPTER
    symbol, and a renamed literal goes UNBOUND — the Longinus binding discriminates."""
    cases = [
        ("run_hades_pipeline", "hades_realize_complete"),
        ("emit_extract_phase", "hades_extracted"),
        ("emit_gated_apply_phase", "hades_gate_applied"),
    ]
    for symbol, literal in cases:
        bound = verify_binding(_ROOT, Longinus(_KG_ANCHOR, _ADAPTER_SRC, symbol, literal))
        assert bound.bound is True, f"{symbol} should emit {literal}: {bound.reason}"
        miss = verify_binding(
            _ROOT, Longinus(_KG_ANCHOR, _ADAPTER_SRC, symbol, literal + "_RENAMED")
        )
        assert miss.bound is False, f"{symbol} must NOT bind a renamed literal"
