"""ooptdd trace-gate over bhgman_tool's Longinus drift-audit flow.

Positive-TDD / log-based gate (ooptdd): the *store* is the judge, not the
function's return value. We drive the REAL engine — seed a couple of real
``ReferenceSite`` states, run a real sha256 baseline + verify (genuine
SHA256_MISMATCH after a disk mutation), then run
``LonginusAudit.run_full()`` — and ship ooptdd lifecycle events whose counts
are DERIVED FROM the real ``AuditReport`` (no hand-typed numbers). The gate in
``gates/drift_audit_flow.yaml`` then independently re-checks arrival.

Two tests:
  * test_drift_audit_flow_arrives_green
        — run the audit, assert its own self-report, then POSITIVELY assert
          arrival via ``evaluate(backend, load_gate(...))['ok'] is True``.
  * test_silent_loss_is_caught_by_gate  (MANDATORY counter-test)
        — same flow against ``MemoryBackend(drop=True)``. The function still
          returns a green ``AuditReport`` (its self-report is unchanged), yet
          the gate goes RED because nothing reached the store. This is the gap
          a return-value assertion cannot see — and the whole point of the gate.

# KG: ATOM_Skill_longinus
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

# ooptdd/ooptdd_loop = dev-only methodology siblings (private, not on any index). CI does not
# install them, so skip these instrumentation tests there — like the leiden/lean optional-tool
# tests. The engine behaviour they trace-gate is covered by the regular tests.
pytest.importorskip("ooptdd.backends")
pytest.importorskip("ooptdd_loop")

from ooptdd.backends.memory import MemoryBackend, reset
from ooptdd.engine.gate import evaluate, load_gate

from engine.longinus_drift_audit import sha256_baseline
from engine.longinus_drift_audit.audit_runner import LonginusAudit
from engine.longinus_drift_audit.kg_client import MockKgClient
from engine.longinus_drift_audit.models import AuditReport, ReferenceSite

_GATE_PATH = str(Path(__file__).parent / "gates" / "drift_audit_flow.yaml")
_REPO_TAG = "bhgman"


@pytest.fixture(autouse=True)
def _clean_store():
    """The MemoryBackend is a module-global store — reset around every test so
    one test's events never bleed into another's gate evaluation."""
    reset()
    yield
    reset()


def _run_real_drift_audit() -> tuple[AuditReport, MockKgClient]:
    """Drive the REAL engine and return its real AuditReport.

    Builds a temp code-root with two real files (each carrying a ``# KG:``
    comment), seeds a ReferenceSite per file, runs a genuine sha256
    ``init_baseline`` (absolute paths resolve to FILE), then mutates one file on
    disk so the audit's verify phase finds a genuine SHA256_MISMATCH. The
    returned report's counts are what the gate thresholds were written against.
    """
    d = tempfile.mkdtemp(prefix="longinus_ooptdd_")
    root = Path(d)
    f_a = root / "alpha.py"
    f_b = root / "beta.py"
    f_a.write_text("# KG: lesson-alpha-2026\ndef alpha():\n    return 1\n")
    f_b.write_text("# KG: lesson-beta-2026\ndef beta():\n    return 2\n")

    site_a = ReferenceSite(sourceId="lesson-alpha-2026", sourcePath=f"{f_a}:1", repo_tag=_REPO_TAG)
    site_b = ReferenceSite(sourceId="lesson-beta-2026", sourcePath=f"{f_b}:1", repo_tag=_REPO_TAG)
    kg = MockKgClient(sites=[site_a, site_b])

    # Real sha256 baseline over the seeded sites — earns the '== 2' baseline count.
    init = sha256_baseline.init_baseline(kg=kg, sites=kg.list_reference_site_states(_REPO_TAG))
    assert init.populated == 2, f"expected 2 baselined sites, got {init.populated}"

    # Mutate beta.py on disk => genuine sha256 drift on the audit's verify phase.
    f_b.write_text("# KG: lesson-beta-2026\ndef beta():\n    return 999\n")

    audit = LonginusAudit(kg=kg, code_root=root, repo_tag=_REPO_TAG)
    report = audit.run_full(verify_sha256=True)
    return report, kg


def _ship_flow_events(backend: MemoryBackend, cid: str, report: AuditReport) -> None:
    """Emit the drift-audit lifecycle to the store, DERIVING every count from the
    real ``AuditReport`` — never a hand-typed literal.

    One ``site.baselined`` per real ``sha256_baseline_count`` and one
    ``drift.detected`` per real ``sha256_drift_events`` entry; the close verdict
    is the report's real ``is_clean``. This is the flow the gate observes.
    """
    backend.ship(
        [
            {
                "cid": cid,
                "event": "audit.started",
                "phase": "scan",
                "audit_id": report.audit_id,
                "repo_tag": _REPO_TAG,
            }
        ]
    )
    for _ in range(report.sha256_baseline_count):
        backend.ship(
            [
                {
                    "cid": cid,
                    "event": "site.baselined",
                    "repo_tag": _REPO_TAG,
                }
            ]
        )
    for ev in report.sha256_drift_events:
        backend.ship(
            [
                {
                    "cid": cid,
                    "event": "drift.detected",
                    "kind": ev.kind,
                    "ref_site": ev.ref_site,
                    "path": ev.path,
                }
            ]
        )
    backend.ship(
        [
            {
                "cid": cid,
                "event": "audit.completed",
                "verdict": "clean" if report.is_clean else "dirty",
                "total_drifts": report.total_drifts,
                "audit_id": report.audit_id,
            }
        ]
    )


def test_drift_audit_flow_arrives_green(monkeypatch):
    """Positive wing: the real audit runs, self-reports drift, AND the store
    independently confirms the whole lifecycle arrived (gate ['ok'] is True)."""
    cid = "longinus-drift-audit-green"
    monkeypatch.setenv("OOPTDD_CID", cid)

    report, _kg = _run_real_drift_audit()

    # (a) the function's own self-report — necessary but NOT sufficient.
    assert report.sha256_baseline_count == 2
    assert len(report.sha256_drift_events) == 1
    assert report.sha256_drift_events[0].kind == "SHA256_MISMATCH"
    assert report.is_clean is False  # one genuine drift => dirty

    backend = MemoryBackend()
    _ship_flow_events(backend, cid, report)

    # (b) the STORE is the judge — positively assert arrival through the gate.
    result = evaluate(backend, load_gate(_GATE_PATH))
    assert result["ok"] is True, _explain(result)
    assert result.get("reachable", True) is True


def test_silent_loss_is_caught_by_gate(monkeypatch):
    """MANDATORY counter-test (the red_proof): a backend that ACCEPTS then
    silently DROPS every event.

    The audit's return value is byte-identical to the green case — its
    self-report still says baselined=2 / drift=1 / dirty. A return-value-only
    test passes here and ships a blind spot. The ooptdd gate, reading the store,
    goes RED (``ok is False``) because nothing arrived. That divergence —
    return says ok, gate says RED — is exactly what the gate buys you.
    """
    cid = "longinus-drift-audit-droploss"
    monkeypatch.setenv("OOPTDD_CID", cid)

    report, _kg = _run_real_drift_audit()

    # The return-value test STILL passes — the function is happy.
    assert report.sha256_baseline_count == 2
    assert len(report.sha256_drift_events) == 1
    assert report.is_clean is False

    # drop=True: the store accepts ship() then loses everything.
    backend = MemoryBackend(drop=True)
    _ship_flow_events(backend, cid, report)

    result = evaluate(backend, load_gate(_GATE_PATH))
    assert result["ok"] is False, (
        f"silent-loss MUST turn the gate RED — a return-value test cannot see this. result={result}"
    )

    # Concretely: the lifecycle count/order checks each failed because the store
    # is empty (got 0 of every expected event). The ``absent`` ERROR wing alone
    # passes vacuously — which is precisely why an existence/forbid-only gate is
    # not enough and the positive counts carry the verdict.
    failed = [c for c in result["checks"] if not c.get("passed", True)]
    assert failed, "expected at least one failed check under silent loss"
    assert any(c.get("got") == 0 for c in failed), (
        f"expected the dropped events to read as got=0; failed={failed}"
    )


def _explain(result: dict) -> str:
    """Surface the failing checks if the green assertion ever regresses."""
    bad = [c for c in result.get("checks", []) if not c.get("passed", True)]
    return f"gate not green; failing checks={bad}; full={result}"
