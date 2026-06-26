"""ooptdd trace-gate over bhgman_tool's prometheus 획득(acquire) flow.

Positive-TDD / log-based gate (ooptdd): the *store* is the judge, not the function's
return value. We drive the REAL engine through ooptdd/prometheus_adapter.py — seed two
real gaps, run a real gap-detect -> query-derive -> fetch(StaticFetcher) -> parse ->
ingest chain (apply wing) — and the gate in gates/prometheus_flow.yaml independently
re-checks arrival, with every threshold matching the real AcquireReport.

Four tests:
  * test_prometheus_flow_arrives_green
        — run the real acquire, assert its self-report, then POSITIVELY assert arrival
          via evaluate(backend, load_gate(...))['ok'] is True.
  * test_silent_loss_is_caught_by_gate   (MANDATORY counter-test, axis A)
        — same flow against MemoryBackend(drop=True): the self-report is byte-identical
          green, yet the gate goes RED because nothing reached the store.
  * test_drop_the_seed_breaks_value_pinned_count   (honest-count proof, axis C)
        — break one corpus->derive_query join: findings drop 2->1 and the value-pinned
          ==2 count goes RED, proving it tracks the real fetch->parse chain, not a constant.
  * test_longinus_binding_is_real   (binding proof, axis B)
        — each must_emit literal genuinely lives in its bound ADAPTER symbol, and a
          renamed literal goes UNBOUND — the binding discriminates, it is not free.

# KG: ATOM_Skill_prometheus
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ooptdd.backends.memory import MemoryBackend, reset
from ooptdd.engine.gate import evaluate, load_gate
from ooptdd_loop.longinus import verify_binding
from ooptdd_loop.spec import Longinus

from ooptdd.prometheus_adapter import _CORPUS, _KG_ANCHOR, run_prometheus_pipeline

_GATE_PATH = str(Path(__file__).parent / "gates" / "prometheus_flow.yaml")
# repo root = tests -> prometheus -> engine -> <root>; Longinus source is repo-relative.
_ROOT = str(Path(__file__).resolve().parents[3])
_ADAPTER_SRC = "ooptdd/prometheus_adapter.py"


@pytest.fixture(autouse=True)
def _clean_store():
    """The MemoryBackend is a module-global store — reset around every test so one test's
    events never bleed into another's gate evaluation."""
    reset()
    yield
    reset()


def _explain(result: dict) -> str:
    bad = [c for c in result.get("checks", []) if not c.get("passed", True)]
    return f"gate not green; failing checks={bad}; full={result}"


def test_prometheus_flow_arrives_green(monkeypatch):
    """Positive wing: the real acquire runs, self-reports, AND the store independently
    confirms the whole lifecycle arrived (gate ['ok'] is True)."""
    cid = "prometheus-acquire-green"
    monkeypatch.setenv("OOPTDD_CID", cid)

    backend = MemoryBackend()
    report = run_prometheus_pipeline(backend, cid)

    # (a) the function's own self-report — necessary but NOT sufficient.
    assert report["gaps"] == 2
    assert report["findings"] == 2
    assert report["proposed"] == 2
    assert report["ingested"] == 2
    assert report["dry_run"] is False

    # (b) the STORE is the judge — positively assert arrival through the gate.
    result = evaluate(backend, load_gate(_GATE_PATH))
    assert result["ok"] is True, _explain(result)
    assert result.get("reachable", True) is True


def test_silent_loss_is_caught_by_gate(monkeypatch):
    """MANDATORY counter-test (axis A): a backend that ACCEPTS then silently DROPS every
    event. The acquire's return value is byte-identical to the green case, yet the gate
    reads the store and goes RED — exactly the blind spot a return-value test cannot see."""
    cid = "prometheus-acquire-droploss"
    monkeypatch.setenv("OOPTDD_CID", cid)

    backend = MemoryBackend(drop=True)
    report = run_prometheus_pipeline(backend, cid)

    # the return-value test STILL passes — the function is happy.
    assert report["findings"] == 2
    assert report["ingested"] == 2
    assert report["dry_run"] is False

    result = evaluate(backend, load_gate(_GATE_PATH))
    assert result["ok"] is False, (
        f"silent-loss MUST turn the gate RED — a return-value test cannot see this. {result}"
    )
    failed = [c for c in result["checks"] if not c.get("passed", True)]
    assert failed, "expected at least one failed check under silent loss"
    assert any(c.get("got") == 0 for c in failed), (
        f"expected the dropped events to read as got=0; failed={failed}"
    )


def test_drop_the_seed_breaks_value_pinned_count(monkeypatch):
    """Honest-count proof (axis C): break the corpus->derive_query join for the
    VerdictPending gap (a wrong key => 0 docs for it). Findings drop 2->1 and the
    value-pinned prometheus_finding_extracted==2 check goes RED — proving the count
    tracks the real fetch->parse chain, not a hard-typed constant."""
    cid = "prometheus-acquire-dropseed"
    monkeypatch.setenv("OOPTDD_CID", cid)

    broken = {
        "Is the Koide relation numerology": _CORPUS["Is the Koide relation numerology"],
        # wrong key: the VerdictPending gap's derive_query output no longer hits the corpus.
        "WRONG KEY eureka": _CORPUS["eureka span maintain 7 evidence resolution"],
    }
    backend = MemoryBackend()
    report = run_prometheus_pipeline(backend, cid, corpus=broken)
    assert report["findings"] == 1  # only the Koide gap matched its corpus key

    result = evaluate(backend, load_gate(_GATE_PATH))
    assert result["ok"] is False, f"dropped seed must turn the gate RED. {result}"
    broke = [
        c
        for c in result["checks"]
        if not c.get("passed", True) and c.get("event") == "prometheus_finding_extracted"
    ]
    assert broke and broke[0].get("got") == 1, (
        f"finding_extracted should read got=1 against the ==2 pin; checks={result['checks']}"
    )


def test_longinus_binding_is_real():
    """Binding proof (axis B): each must_emit literal genuinely lives in its bound ADAPTER
    symbol, and a renamed literal goes UNBOUND — the Longinus binding discriminates."""
    cases = [
        ("run_prometheus_pipeline", "prometheus_acquire_completed"),
        ("emit_gap_phase", "prometheus_gap_detected"),
        ("emit_extract_phase", "prometheus_finding_extracted"),
        ("emit_ingest_phase", "prometheus_finding_ingested"),
    ]
    for symbol, literal in cases:
        bound = verify_binding(_ROOT, Longinus(_KG_ANCHOR, _ADAPTER_SRC, symbol, literal))
        assert bound.bound is True, f"{symbol} should emit {literal}: {bound.reason}"
        miss = verify_binding(
            _ROOT, Longinus(_KG_ANCHOR, _ADAPTER_SRC, symbol, literal + "_RENAMED")
        )
        assert miss.bound is False, f"{symbol} must NOT bind a renamed literal"
