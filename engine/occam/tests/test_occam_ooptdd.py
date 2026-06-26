"""ooptdd trace-gate over bhgman_tool's occam 정리(dedup/supersede) flow.

Positive-TDD / log-based gate (ooptdd): the *store* is the judge, not the return value.
We drive the REAL engine through ooptdd/occam_adapter.py — seed an abs/rel same-sha duplicate,
detect a confident byte-identical SUPERSEDE, and apply it via a matched write — and the gate in
gates/occam_flow.yaml re-checks arrival, every threshold matching the real OccamRunResult.

Six tests:
  * test_occam_flow_arrives_green
        — run the real supersede, assert its self-report, then POSITIVELY assert arrival.
  * test_silent_loss_is_caught_by_gate            (axis A)
        — MemoryBackend(drop=True): self-report byte-identical green, gate RED (got=0).
  * test_dry_run_does_not_emit_node_superseded    (axis C — the PROPOSE/planned trap)
        — apply=False: the candidate is detected and PLANNED (apply_result.superseded is a
          non-empty list), yet nothing was written, so node.superseded is NOT shipped and the
          ==1 check goes RED. node.superseded tracks a real write, never a plan.
  * test_clean_kg_detects_nothing                 (axis C — detected count)
        — a single solo file yields zero candidates => occam.candidate.detected==1 RED.
  * test_unmatched_write_supersedes_nothing       (axis C — applied tracks the matched write)
        — apply=True but the write matched no row => applied_count=0 => node.superseded RED.
  * test_longinus_binding_is_real                 (axis B)
        — each must_emit literal lives in its bound ADAPTER symbol; renamed => UNBOUND.

# KG: occam-kam-canonical-2026-05-26
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
from ooptdd_loop.longinus import verify_binding
from ooptdd_loop.spec import Longinus

from ooptdd.occam_adapter import _CLEAN_ROWS, _KG_ANCHOR, run_occam_pipeline

_GATE_PATH = str(Path(__file__).parent / "gates" / "occam_flow.yaml")
_ROOT = str(Path(__file__).resolve().parents[3])
_ADAPTER_SRC = "ooptdd/occam_adapter.py"


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


def test_occam_flow_arrives_green(monkeypatch):
    """Positive wing: the real dedup/supersede runs, self-reports, AND the store independently
    confirms the whole lifecycle arrived (gate ['ok'] is True)."""
    cid = "occam-supersede-green"
    monkeypatch.setenv("OOPTDD_CID", cid)

    backend = MemoryBackend()
    report = run_occam_pipeline(backend, cid)

    # (a) self-report — necessary but NOT sufficient.
    assert report["detected"] == 1
    assert report["superseded"] == 1
    assert report["dry_run"] is False

    # (b) the STORE is the judge.
    result = evaluate(backend, load_gate(_GATE_PATH))
    assert result["ok"] is True, _explain(result)
    assert result.get("reachable", True) is True


def test_silent_loss_is_caught_by_gate(monkeypatch):
    """MANDATORY counter-test (axis A): drop=True. The return value is byte-identical green,
    yet the gate reads the store and goes RED."""
    cid = "occam-supersede-droploss"
    monkeypatch.setenv("OOPTDD_CID", cid)

    backend = MemoryBackend(drop=True)
    report = run_occam_pipeline(backend, cid)
    assert report["detected"] == 1 and report["superseded"] == 1

    result = evaluate(backend, load_gate(_GATE_PATH))
    assert result["ok"] is False, f"silent-loss MUST turn the gate RED. {result}"
    failed = [c for c in result["checks"] if not c.get("passed", True)]
    assert any(c.get("got") == 0 for c in failed), f"expected got=0; failed={failed}"


def test_dry_run_does_not_emit_node_superseded(monkeypatch):
    """Honest-count proof (axis C, the PROPOSE trap): in dry-run the candidate is detected and
    PLANNED (apply_result.superseded is a non-empty list) but nothing is written. node.superseded
    is bound to applied_count and the dry-run branch, so it is NOT shipped => the ==1 check is
    RED. The supersede event tracks a real KG mutation, never a plan."""
    cid = "occam-supersede-dryrun"
    monkeypatch.setenv("OOPTDD_CID", cid)

    backend = MemoryBackend()
    report = run_occam_pipeline(backend, cid, apply=False)
    assert report["detected"] == 1  # the candidate IS detected...
    assert report["superseded"] == 0  # ...but nothing was superseded (PROPOSE)
    assert report["dry_run"] is True

    result = evaluate(backend, load_gate(_GATE_PATH))
    assert result["ok"] is False, f"dry-run must turn the gate RED. {result}"
    broke = _broke(result, "occam.node.superseded")
    assert broke and broke[0].get("got") == 0, (
        f"node.superseded should read got=0 in dry-run; checks={result['checks']}"
    )


def test_clean_kg_detects_nothing(monkeypatch):
    """Honest-count proof (axis C, detected): a single solo file has no duplicate, so
    occam.candidate.detected==1 goes RED (got=0)."""
    cid = "occam-supersede-clean"
    monkeypatch.setenv("OOPTDD_CID", cid)

    backend = MemoryBackend()
    report = run_occam_pipeline(backend, cid, rows=_CLEAN_ROWS)
    assert report["detected"] == 0 and report["superseded"] == 0

    result = evaluate(backend, load_gate(_GATE_PATH))
    assert result["ok"] is False, f"clean KG must turn the gate RED. {result}"
    broke = _broke(result, "occam.candidate.detected")
    assert broke and broke[0].get("got") == 0, (
        f"candidate.detected should read got=0 on a clean KG; checks={result['checks']}"
    )


def test_unmatched_write_supersedes_nothing(monkeypatch):
    """Honest-count proof (axis C, applied tracks the matched write): apply=True but the write
    matched no row (node absent / already superseded) => applied_count=0 => node.superseded RED.
    Proves the count is backed by a real matched write, not the apply intent alone."""
    cid = "occam-supersede-nomatch"
    monkeypatch.setenv("OOPTDD_CID", cid)

    backend = MemoryBackend()
    report = run_occam_pipeline(backend, cid, write_matches=False)
    assert report["detected"] == 1  # the candidate IS detected and apply was attempted...
    assert report["superseded"] == 0  # ...but the write matched no row => nothing applied

    result = evaluate(backend, load_gate(_GATE_PATH))
    assert result["ok"] is False, f"unmatched write must turn the gate RED. {result}"
    broke = _broke(result, "occam.node.superseded")
    assert broke and broke[0].get("got") == 0, (
        f"node.superseded should read got=0 on an unmatched write; checks={result['checks']}"
    )


def test_longinus_binding_is_real():
    """Binding proof (axis B): each must_emit literal genuinely lives in its bound ADAPTER
    symbol, and a renamed literal goes UNBOUND — the Longinus binding discriminates."""
    cases = [
        ("run_occam_pipeline", "occam.completed"),
        ("emit_dedup_phase", "occam.candidate.detected"),
        ("emit_apply_phase", "occam.node.superseded"),
    ]
    for symbol, literal in cases:
        bound = verify_binding(_ROOT, Longinus(_KG_ANCHOR, _ADAPTER_SRC, symbol, literal))
        assert bound.bound is True, f"{symbol} should emit {literal}: {bound.reason}"
        miss = verify_binding(
            _ROOT, Longinus(_KG_ANCHOR, _ADAPTER_SRC, symbol, literal + "_RENAMED")
        )
        assert miss.bound is False, f"{symbol} must NOT bind a renamed literal"
