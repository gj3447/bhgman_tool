"""ooptdd trace-gate over bhgman_tool's eureka 창조(abstraction synthesis) flow.

Positive-TDD / log-based gate (ooptdd): the *store* is the judge, not the return value.
We drive the REAL FCA induction engine through ooptdd/eureka_adapter.py over a seeded
8-object math/compiler cluster (FCA induce -> quality gate -> naesengmoon -> persist
ACCEPTED), and the gate in gates/eureka_flow.yaml re-checks arrival, every threshold
matching the real PipelineRun.

Four tests:
  * test_eureka_flow_arrives_green
        — run the real induction, assert its self-report, then POSITIVELY assert arrival.
  * test_silent_loss_is_caught_by_gate                 (axis A)
        — MemoryBackend(drop=True): self-report byte-identical green, gate RED (got=0).
  * test_empty_runner_is_red_even_though_stages_ok     (axis C + the stages_ok trap)
        — an empty CypherRunner induces ZERO concepts, so the count gate is RED — EVEN
          THOUGH the real pipeline's stages_ok is still > 0 on that empty run. This is
          exactly why the gate binds the earned counts, never stages_ok.
  * test_longinus_binding_is_real                      (axis B)
        — each must_emit literal lives in its bound ADAPTER symbol; renamed => UNBOUND.

# KG: eureka-canonical-2026-05-26
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

from ooptdd.eureka_adapter import _KG_ANCHOR, run_eureka_pipeline

_GATE_PATH = str(Path(__file__).parent / "gates" / "eureka_flow.yaml")
_ROOT = str(Path(__file__).resolve().parents[3])
_ADAPTER_SRC = "ooptdd/eureka_adapter.py"


@pytest.fixture(autouse=True)
def _clean_store():
    reset()
    yield
    reset()


def _explain(result: dict) -> str:
    bad = [c for c in result.get("checks", []) if not c.get("passed", True)]
    return f"gate not green; failing checks={bad}; full={result}"


def test_eureka_flow_arrives_green(monkeypatch):
    """Positive wing: the real FCA induction runs, self-reports, AND the store independently
    confirms the whole lifecycle arrived (gate ['ok'] is True)."""
    cid = "eureka-induction-green"
    monkeypatch.setenv("OOPTDD_CID", cid)

    backend = MemoryBackend()
    report = run_eureka_pipeline(backend, cid)

    # (a) self-report — necessary but NOT sufficient.
    assert report["induced"] == 2
    assert report["survived"] == 2
    assert report["persisted"] == 2

    # (b) the STORE is the judge.
    result = evaluate(backend, load_gate(_GATE_PATH))
    assert result["ok"] is True, _explain(result)
    assert result.get("reachable", True) is True


def test_silent_loss_is_caught_by_gate(monkeypatch):
    """MANDATORY counter-test (axis A): drop=True. The return value is byte-identical green,
    yet the gate reads the store and goes RED."""
    cid = "eureka-induction-droploss"
    monkeypatch.setenv("OOPTDD_CID", cid)

    backend = MemoryBackend(drop=True)
    report = run_eureka_pipeline(backend, cid)
    assert report["induced"] == 2 and report["persisted"] == 2

    result = evaluate(backend, load_gate(_GATE_PATH))
    assert result["ok"] is False, f"silent-loss MUST turn the gate RED. {result}"
    failed = [c for c in result["checks"] if not c.get("passed", True)]
    assert any(c.get("got") == 0 for c in failed), f"expected got=0; failed={failed}"


def test_empty_runner_is_red_even_though_stages_ok(monkeypatch):
    """Honest-count proof (axis C) + the stages_ok trap: an empty CypherRunner induces ZERO
    concepts, so the value-pinned ==2 count gate goes RED — EVEN THOUGH the real pipeline's
    stages_ok is still > 0 on that same empty run. Binding the earned counts (not stages_ok)
    is what makes this RED instead of a fake-green."""
    cid = "eureka-induction-empty"
    monkeypatch.setenv("OOPTDD_CID", cid)

    # the trap, demonstrated directly on the real engine: empty context, yet stages_ok > 0.
    from engine.eureka.pipeline import PipelineConfig, run_from_kg

    pr = run_from_kg(
        lambda q, p: [],
        PipelineConfig(cycle_id="trap", persist_cypher=lambda c, p: [], persist_accept=True),
    )
    stages_ok = sum(1 for s in pr.stages if s.ok)
    assert stages_ok > 0, "stages_ok should be nonzero even on empty input (the trap)"

    backend = MemoryBackend()
    report = run_eureka_pipeline(backend, cid, run_cypher=lambda q, p: [])
    assert report["induced"] == 0  # the earned count is honestly zero

    result = evaluate(backend, load_gate(_GATE_PATH))
    assert result["ok"] is False, (
        f"empty induction must be RED despite stages_ok={stages_ok}. {result}"
    )
    broke = [
        c
        for c in result["checks"]
        if not c.get("passed", True) and c.get("event") == "eureka_concepts_induced"
    ]
    assert broke and broke[0].get("got") == 0, (
        f"concepts_induced should read got=0 against the ==2 pin; checks={result['checks']}"
    )


def test_longinus_binding_is_real():
    """Binding proof (axis B): each must_emit literal genuinely lives in its bound ADAPTER
    symbol, and a renamed literal goes UNBOUND — the Longinus binding discriminates."""
    cases = [
        ("run_eureka_pipeline", "eureka_cycle_complete"),
        ("emit_induction_phase", "eureka_concepts_induced"),
        ("emit_induction_phase", "eureka_quality_survivor"),
        ("emit_persist_phase", "eureka_abstraction_persisted"),
    ]
    for symbol, literal in cases:
        bound = verify_binding(_ROOT, Longinus(_KG_ANCHOR, _ADAPTER_SRC, symbol, literal))
        assert bound.bound is True, f"{symbol} should emit {literal}: {bound.reason}"
        miss = verify_binding(
            _ROOT, Longinus(_KG_ANCHOR, _ADAPTER_SRC, symbol, literal + "_RENAMED")
        )
        assert miss.bound is False, f"{symbol} must NOT bind a renamed literal"
