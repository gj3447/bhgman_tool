"""Phase C — the reverse legion loop end-to-end over a real tiny code tree.

TCW extracts real `:CodeSymbol` via engine.code_to_kg; ST/SP project them deterministically;
TA runs the real engine.longinus_drift_audit 5-drift detector. No KG / network needed.
"""

from __future__ import annotations

from engine.tpa.tpa_orchestrator import build_tpa_legion, run_tpa

_SRC = '''\
"""tiny module."""


def alpha(x):
    return x + 1


class Bar:
    def beta(self):
        return alpha(2)
'''


def _make_tree(tmp_path):
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "mod.py").write_text(_SRC)
    (pkg / "__pycache__").mkdir()
    (pkg / "__pycache__" / "junk.py").write_text("def ignored(): pass\n")  # must be skipped
    return tmp_path


def test_reverse_loop_completes_and_recovers_structure(tmp_path):
    root = _make_tree(tmp_path)
    run = run_tpa(root)
    assert run.completed is True
    assert run.contract_violation is None
    # all four reverse stages fired in order
    assert [o.stage for o in run.outcomes] == ["tcw", "st", "sp", "ta"]
    assert {"tcw_result", "contracts", "patterns", "drift_report"} <= set(run.final_context_keys)


def test_tcw_extracts_and_skips_pycache(tmp_path):
    root = _make_tree(tmp_path)
    # inspect the recovered context via a capture-gate
    captured: dict = {}

    def _capture(ctx):
        captured.update(ctx)
        return True, "ok"

    build_tpa_legion().run({"code_root": str(root)}, gate=_capture)
    tcw = captured["tcw_result"]
    assert tcw["files_scanned"] == 1  # __pycache__/junk.py skipped
    names = {s.name for s in tcw["symbols"]}
    assert {"alpha", "Bar", "beta"} <= names
    # ST recovers callables/classes as contract candidates
    assert captured["contracts"]["count"] >= 3
    # SP groups by kind
    assert (
        "function" in captured["patterns"]["groups"] or "method" in captured["patterns"]["groups"]
    )
    # TA ran the real 5-drift detector; a clean tree with no `# KG:` claims has nothing to
    # violate -> 0 drift (honest: reverse-orphan is a separate scan, not detect_all's default).
    assert captured["drift_report"]["drift_count"] == 0
    assert captured["drift_report"]["by_type"] == {}


def test_ta_fires_real_detector_on_orphan_kg_ref(tmp_path):
    # Inject a ReferenceSite registry entry the code never references -> detect_orphan fires.
    from engine.longinus_drift_audit.models import KgRefRecord  # noqa: PLC0415

    root = _make_tree(tmp_path)
    kg_refs = {"GHOST_node": KgRefRecord(sourceId="GHOST_node", sourcePath="pkg/mod.py:1")}
    run = run_tpa(root, kg_refs=kg_refs)
    captured: dict = {}

    def _capture(ctx):
        captured.update(ctx)
        return True, "ok"

    build_tpa_legion().run({"code_root": str(root), "kg_refs": kg_refs}, gate=_capture)
    assert run.completed is True
    assert captured["drift_report"]["drift_count"] >= 1


def test_missing_code_root_degrades_not_crashes(tmp_path):
    run = run_tpa(tmp_path / "does_not_exist")
    # Graceful-degrade covenant holds: no crash, no contract violation (TCW still provided
    # its key). FulfillmentGate hardening (seed-tpa-fulfillmentgate-hardening-2026-07-13):
    # the degraded extraction is now surfaced as a gate FAIL, NOT a false-green completion.
    assert run.contract_violation is None
    assert run.completed is not True
    assert run.gate_failure is not None and "TCW" in run.gate_failure


_SRC_SHARED = '''\
"""two classes sharing a method name + a call dependency."""


def helper(x):
    return x


class Reader:
    def run(self):
        return helper(1)


class Writer:
    def run(self):
        return helper(2)
'''


def test_st_dependency_count_and_sp_shared_protocol(tmp_path):
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "m.py").write_text(_SRC_SHARED)
    captured: dict = {}

    def _capture(ctx):
        captured.update(ctx)
        return True, "ok"

    build_tpa_legion().run({"code_root": str(tmp_path)}, gate=_capture)
    # TCW now carries edges too
    assert captured["tcw_result"]["edges"]
    # ST: at least one contract candidate recovered a CALLS dependency (Reader.run/Writer.run call helper)
    cands = captured["contracts"]["candidates"]
    assert any(c["dependency_count"] >= 1 for c in cands)
    # SP: 'run' appears as a method in both Reader and Writer -> a shared-protocol candidate
    shared = captured["patterns"]["shared_protocol_candidates"]
    assert "run" in shared
    assert len(shared["run"]) >= 2
