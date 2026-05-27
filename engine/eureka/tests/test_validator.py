import datetime as dt

import pytest

from validator import SchemaViolation, validate_abstract_class, validate_generalizes_edge


def _valid_ac() -> dict:
    return {
        "name": "ac_test_42_v1",
        "summary": "Test concept",
        "inductionMethod": "fca",
        "cycleId": "test-cycle",
        "createdAt": dt.datetime(2026, 5, 20, tzinfo=dt.timezone.utc),
        "status": "PROPOSED",
        "extent": ["node_a", "node_b"],
        "intent": ["attr_x"],
        "stabilityScore": 0.75,
    }


def _valid_manual_ac() -> dict:
    return {
        "name": "ac_manual_test",
        "summary": "Manual concept (no extent/intent required)",
        "inductionMethod": "manual",
        "cycleId": "test-cycle",
        "createdAt": dt.datetime(2026, 5, 20, tzinfo=dt.timezone.utc),
        "status": "PROPOSED",
    }


def _valid_edge_induced() -> dict:
    return {
        "confidence": 0.8,
        "method": "fca",
        "cycleId": "test-cycle",
        "createdAt": dt.datetime(2026, 5, 20, tzinfo=dt.timezone.utc),
        "induced": True,
    }


def _valid_edge_backfilled() -> dict:
    return {
        "method": "unknown",
        "cycleId": "pre-2026-05-20-backfill",
        "createdAt": dt.datetime(2026, 5, 20, tzinfo=dt.timezone.utc),
        "induced": False,
    }


def test_ac_required_fields_missing_fails():
    payload = _valid_ac()
    del payload["summary"]
    with pytest.raises(SchemaViolation):
        validate_abstract_class(payload)


def test_ac_valid_passes():
    ac = validate_abstract_class(_valid_ac())
    assert ac.name == "ac_test_42_v1"
    assert ac.inductionMethod == "fca"


def test_ac_manual_no_extent_passes():
    ac = validate_abstract_class(_valid_manual_ac())
    assert ac.inductionMethod == "manual"
    assert ac.extent is None


def test_ac_automated_missing_extent_fails():
    payload = _valid_ac()
    del payload["extent"]
    with pytest.raises(SchemaViolation):
        validate_abstract_class(payload)


def test_ac_unknown_method_fails():
    payload = _valid_manual_ac()
    payload["inductionMethod"] = "made-up-operator-2099"
    with pytest.raises(SchemaViolation):
        validate_abstract_class(payload)


def test_edge_induced_without_confidence_fails():
    payload = _valid_edge_induced()
    del payload["confidence"]
    with pytest.raises(SchemaViolation):
        validate_generalizes_edge(payload)


def test_edge_backfilled_no_confidence_ok():
    edge = validate_generalizes_edge(_valid_edge_backfilled())
    assert edge.induced is False
    assert edge.confidence is None


def test_edge_invalid_method_fails():
    payload = _valid_edge_backfilled()
    payload["method"] = "made-up-method"
    with pytest.raises(SchemaViolation):
        validate_generalizes_edge(payload)
