"""ooptdd trace-gate over bhgman_tool's jaebaeman 출격(sortie) flow.

Positive-TDD / log-based gate (ooptdd): the *store* is the judge, not the function's
return value. We drive the REAL engine through ooptdd/jaebaeman_adapter.py — plant the
3-seed fixture via plant_seeds (MERGE-only covenant), JOIN the READY seeds back out of
the store via read_ready_seeds, drive them to COLLECTED via drive_seeds (applied status
writes) — and the gate in gates/jaebaeman_flow.yaml independently re-checks arrival,
with every threshold matching what the real chain landed in the store.

jbm-s1 (LakatosTree_BhgmanJaebaeman_20260702): jaebaeman was the SOLE commander of 7
with no ooptdd adapter (audit wf_376c327b-8f3, gap G1) — trace receipts were
structurally impossible. This file is the RED artifact written before the adapter.

Six tests:
  * test_jaebaeman_flow_arrives_green
        — run the real sortie, assert its self-report, then POSITIVELY assert arrival
          via evaluate(backend, load_gate(...))['ok'] is True.
  * test_silent_loss_is_caught_by_gate   (MANDATORY counter-test, axis A)
        — same flow against MemoryBackend(drop=True): the self-report is byte-identical
          green, yet the gate goes RED because nothing reached the store.
  * test_drop_the_seed_breaks_value_pinned_count   (honest-count proof, axis C)
        — plant one child fewer: planted drops 3->2 and the value-pinned ==3 count goes
          RED, proving it tracks the real store, not a constant.
  * test_dry_run_plant_breaks_readback_join   (join proof, axis C)
        — a dry-run plant lands nothing, so read_ready_seeds joins 0 rows back OUT of
          the store despite 3 seeds IN: the counts are store-derived, not input echo.
  * test_lifecycle_order_flip_is_discriminated   (NOVEL axis: order, judge P2)
        — re-ship the SAME real event multiset in flipped order: every ==N stays green
          yet exactly the must_order check goes RED — the order axis discriminates
          independently of every count axis.
  * test_longinus_binding_is_real   (binding proof, axis B)
        — each must_emit literal genuinely lives in its bound ADAPTER symbol, and a
          renamed literal goes UNBOUND — the binding discriminates, it is not free.
  * test_engine_stays_literal_free   (hard-core grep guard)
        — the event literals live ONLY in the adapter, never in engine/jaebaeman/*.py.

# KG: finding-ooptdd-bhgman-jaebaeman-adapter-20260702
"""

from __future__ import annotations

from pathlib import Path

import pytest

# ooptdd/ooptdd_loop = dev-only methodology siblings (private, not on any index). CI does
# not install them, so skip these instrumentation tests there — like the leiden/lean
# optional-tool tests. The engine behaviour they trace-gate is covered by the regular tests.
pytest.importorskip("ooptdd.backends")
pytest.importorskip("ooptdd_loop")

from ooptdd.backends.memory import MemoryBackend, reset
from ooptdd.engine.gate import evaluate, load_gate
from ooptdd_loop.longinus import verify_binding
from ooptdd_loop.spec import Longinus

from ooptdd.jaebaeman_adapter import (
    _KG_ANCHOR,
    _SEEDS,
    _ev,
    _run_real_sortie,
    emit_germinate_phase,
    emit_plant_phase,
    emit_ready_phase,
    run_jaebaeman_pipeline,
)

_GATE_PATH = str(Path(__file__).parent / "gates" / "jaebaeman_flow.yaml")
# repo root = tests -> jaebaeman -> engine -> <root>; Longinus source is repo-relative.
_ROOT = str(Path(__file__).resolve().parents[3])
_ADAPTER_SRC = "ooptdd/jaebaeman_adapter.py"

_EVENT_LITERALS = (
    "jaebaeman_sortie_started",
    "jaebaeman_seed_planted",
    "jaebaeman_seed_ready",
    "jaebaeman_seed_germinated",
    "jaebaeman_sortie_completed",
)


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


def _failed(result: dict) -> list[dict]:
    return [c for c in result.get("checks", []) if not c.get("passed", True)]


def test_jaebaeman_flow_arrives_green(monkeypatch):
    """Positive wing: the real plant -> read-back -> germinate chain runs, self-reports,
    AND the store independently confirms the whole lifecycle arrived (gate ok True)."""
    cid = "jaebaeman-sortie-green"
    monkeypatch.setenv("OOPTDD_CID", cid)

    backend = MemoryBackend()
    report = run_jaebaeman_pipeline(backend, cid)

    # (a) the function's own self-report — necessary but NOT sufficient.
    assert report["planted"] == 3
    assert report["ready"] == 3
    assert report["germinated"] == 3
    assert report["dry_run"] is False

    # (b) the STORE is the judge — positively assert arrival through the gate.
    result = evaluate(backend, load_gate(_GATE_PATH))
    assert result["ok"] is True, _explain(result)
    assert result.get("reachable", True) is True


def test_silent_loss_is_caught_by_gate(monkeypatch):
    """MANDATORY counter-test (axis A): a backend that ACCEPTS then silently DROPS every
    event. The sortie's return value is byte-identical to the green case (it is derived
    from the seed store, which is intact), yet the gate reads the TRACE store and goes
    RED — exactly the blind spot a return-value test cannot see."""
    cid = "jaebaeman-sortie-droploss"
    monkeypatch.setenv("OOPTDD_CID", cid)

    backend = MemoryBackend(drop=True)
    report = run_jaebaeman_pipeline(backend, cid)

    # the return-value test STILL passes — the function is happy.
    assert report["planted"] == 3
    assert report["germinated"] == 3
    assert report["dry_run"] is False

    result = evaluate(backend, load_gate(_GATE_PATH))
    assert result["ok"] is False, (
        f"silent-loss MUST turn the gate RED — a return-value test cannot see this. {result}"
    )
    failed = _failed(result)
    assert failed, "expected at least one failed check under silent loss"
    assert any(c.get("got") == 0 for c in failed), (
        f"expected the dropped events to read as got=0; failed={failed}"
    )


def test_drop_the_seed_breaks_value_pinned_count(monkeypatch):
    """Honest-count proof (axis C): plant one child fewer (root + leaf-a only). Planted
    drops 3->2 and the value-pinned jaebaeman_seed_planted==3 check goes RED — proving
    the count tracks the real store contents, not a hard-typed constant."""
    cid = "jaebaeman-sortie-dropseed"
    monkeypatch.setenv("OOPTDD_CID", cid)

    backend = MemoryBackend()
    report = run_jaebaeman_pipeline(backend, cid, seeds=list(_SEEDS[:2]))
    assert report["planted"] == 2  # only root + leaf-a landed

    result = evaluate(backend, load_gate(_GATE_PATH))
    assert result["ok"] is False, f"dropped seed must turn the gate RED. {result}"
    broke = [
        c
        for c in _failed(result)
        if c.get("event") == "jaebaeman_seed_planted" and c.get("got") == 2
    ]
    assert broke, f"seed_planted should read got=2 against the ==3 pin; checks={result['checks']}"


def test_dry_run_plant_breaks_readback_join(monkeypatch):
    """Join proof (axis C): a dry-run plant executes NO write, so the store stays empty
    and read_ready_seeds joins back 0 rows — despite 3 seeds going IN. Every count is
    derived from the store side of the plant->read-back join, never echoed from input."""
    cid = "jaebaeman-sortie-dryrun"
    monkeypatch.setenv("OOPTDD_CID", cid)

    backend = MemoryBackend()
    report = run_jaebaeman_pipeline(backend, cid, apply=False)

    assert report["planted"] == 0, "dry-run landed nothing, so the store must show 0"
    assert report["ready"] == 0, "read-back joins the STORE (empty), not the input list"
    assert report["germinated"] == 0
    assert report["dry_run"] is True

    result = evaluate(backend, load_gate(_GATE_PATH))
    assert result["ok"] is False, f"a dry-run sortie must not satisfy the apply gate. {result}"


def test_lifecycle_order_flip_is_discriminated(monkeypatch):
    """NOVEL axis (judge P2, independent of every count): re-ship the SAME real event
    multiset in flipped order (completed -> germinated -> ready -> planted -> started).
    Every value-pinned ==N check stays green — yet exactly the must_order check goes
    RED. The order axis discriminates on sequencing alone."""
    cid = "jaebaeman-sortie-green-order"
    monkeypatch.setenv("OOPTDD_CID", cid)

    # green run: the real lifecycle order passes must_order.
    backend = MemoryBackend()
    run_jaebaeman_pipeline(backend, cid)
    green = evaluate(backend, load_gate(_GATE_PATH))
    assert green["ok"] is True, _explain(green)

    # counter-run: same REAL artifacts (store + read-back), flipped ship order.
    reset()
    cid = "jaebaeman-sortie-flipped"
    monkeypatch.setenv("OOPTDD_CID", cid)
    store, readback, plant, _lifecycle = _run_real_sortie()
    flipped = MemoryBackend()
    flipped.ship(
        [
            _ev(
                cid,
                "jaebaeman_sortie_completed",
                dry_run=plant.dry_run,
                planted=len(store.seeds),
                ready=len(readback),
                germinated=sum(1 for r in store.seeds.values() if r["status"] == "COLLECTED"),
            )
        ]
    )
    emit_germinate_phase(flipped, cid, store)
    emit_ready_phase(flipped, cid, readback)
    emit_plant_phase(flipped, cid, store)
    flipped.ship([_ev(cid, "jaebaeman_sortie_started", phase="plant")])

    result = evaluate(flipped, load_gate(_GATE_PATH))
    assert result["ok"] is False, f"flipped lifecycle order must turn the gate RED. {result}"
    failed = _failed(result)
    assert failed and all("must_order" in str(c) for c in failed), (
        f"ONLY the must_order check may fail on the flipped run (counts are intact) — "
        f"failed={failed}"
    )


def test_longinus_binding_is_real():
    """Binding proof (axis B): each must_emit literal genuinely lives in its bound ADAPTER
    symbol, and a renamed literal goes UNBOUND — the Longinus binding discriminates."""
    cases = [
        ("run_jaebaeman_pipeline", "jaebaeman_sortie_completed"),
        ("emit_plant_phase", "jaebaeman_seed_planted"),
        ("emit_ready_phase", "jaebaeman_seed_ready"),
        ("emit_germinate_phase", "jaebaeman_seed_germinated"),
    ]
    for symbol, literal in cases:
        bound = verify_binding(_ROOT, Longinus(_KG_ANCHOR, _ADAPTER_SRC, symbol, literal))
        assert bound.bound is True, f"{symbol} should emit {literal}: {bound.reason}"
        miss = verify_binding(
            _ROOT, Longinus(_KG_ANCHOR, _ADAPTER_SRC, symbol, literal + "_RENAMED")
        )
        assert miss.bound is False, f"{symbol} must NOT bind a renamed literal"


def test_engine_stays_literal_free():
    """Hard-core grep guard: the event literals live ONLY in ooptdd/jaebaeman_adapter.py.
    engine/jaebaeman/*.py stays emit-free / literal-free (its pure unit tests and the
    LLM-disjoint floor are preserved) — instrumenting the engine directly would violate
    the programme's hard core."""
    engine_dir = Path(_ROOT) / "engine" / "jaebaeman"
    offenders: list[str] = []
    for py in sorted(engine_dir.glob("*.py")):  # top-level modules only, not tests/
        src = py.read_text(encoding="utf-8")
        offenders.extend(f"{py.name}:{lit}" for lit in _EVENT_LITERALS if lit in src)
    assert not offenders, (
        f"event literals must live ONLY in {_ADAPTER_SRC}, never in engine/jaebaeman/: {offenders}"
    )
