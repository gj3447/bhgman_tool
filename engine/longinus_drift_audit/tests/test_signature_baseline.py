"""End-to-end: record signature baseline → code drifts → audit fires SigMismatch.

Closes the loop that made the structural detect_sig_mismatch path dormant —
nothing populated expected_signature before. record_signature_baselines() is the
binding-time recorder; kg_client now surfaces it as KgRefRecord.expected_signature.
"""

from __future__ import annotations

from engine.longinus_drift_audit import drift_detector
from engine.longinus_drift_audit.kg_client import MockKgClient
from engine.longinus_drift_audit.models import CodeSymbol, DriftType, ReferenceSite
from engine.longinus_drift_audit.signature_baseline import (
    record_signature_baselines,
    signatures_by_ref,
)


def _sym(sig: str) -> CodeSymbol:
    return CodeSymbol(
        sourcePath="m.py:1", name="foo", kind="function", signature=sig, kg_refs=["foo-ref"]
    )


def _kg_with_site() -> MockKgClient:
    return MockKgClient(sites=[ReferenceSite(sourceId="foo-ref", sourcePath="m.py:1")])


def test_signatures_by_ref_first_wins():
    out = signatures_by_ref([_sym("a, b")])
    assert out == {"foo-ref": "a, b"}


def test_record_sets_baseline_and_is_idempotent():
    kg = _kg_with_site()
    assert record_signature_baselines(kg, [_sym("a, b")]) == 1
    assert kg.sites["foo-ref"].signature_baseline == "a, b"
    # re-record unchanged code → no write
    assert record_signature_baselines(kg, [_sym("a, b")]) == 0


def test_recorded_baseline_surfaces_as_expected_signature():
    kg = _kg_with_site()
    record_signature_baselines(kg, [_sym("a, b")])
    assert kg.refs["foo-ref"].expected_signature == "a, b"


def test_end_to_end_drift_fires_sigmismatch():
    kg = _kg_with_site()
    record_signature_baselines(kg, [_sym("a, b")])  # freeze "a, b"
    # code drifts: a param is added
    drifted = [_sym("a, b, c")]
    out = drift_detector.detect_sig_mismatch(symbols=drifted, kg_refs=kg.refs)
    assert len(out) == 1 and out[0].drift_type == DriftType.SIG_MISMATCH
    assert out[0].expected == "a, b" and out[0].actual == "a, b, c"


def test_no_drift_when_signature_unchanged():
    kg = _kg_with_site()
    record_signature_baselines(kg, [_sym("a, b")])
    out = drift_detector.detect_sig_mismatch(symbols=[_sym("a, b")], kg_refs=kg.refs)
    assert out == []


def test_record_signatures_mode_scans_and_records(tmp_path, capsys):
    """audit_runner --record-signatures wire: scan a real file → freeze its sig."""
    from engine.longinus_drift_audit.audit_runner import _record_signatures_mode

    f = tmp_path / "mod.py"
    f.write_text("def foo(a, b):  # KG: foo-ref\n    return a + b\n", encoding="utf-8")
    kg = MockKgClient(sites=[ReferenceSite(sourceId="foo-ref", sourcePath=f"{f}:1")])
    rc = _record_signatures_mode(kg, str(tmp_path))
    assert rc == 0
    assert kg.sites["foo-ref"].signature_baseline == "a, b"
    assert "1 ReferenceSite" in capsys.readouterr().out
