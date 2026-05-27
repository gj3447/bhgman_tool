import pytest

from ged_drift_detector import (
    COLD_START_NGED_TAU,
    evaluate_drift,
    quantile,
)


def test_cold_start_triple_and_all_breach_fires():
    d = evaluate_drift(
        nged=0.30,
        nmi=0.60,
        silhouette=0.40,
        day_since_cold_start=5,
    )
    assert d.fire is True
    assert d.phase == "cold-start"


def test_cold_start_partial_breach_does_not_fire():
    d = evaluate_drift(
        nged=0.30,
        nmi=0.80,
        silhouette=0.40,
        day_since_cold_start=5,
    )
    assert d.fire is False


def test_cold_start_missing_nmi_does_not_fire():
    d = evaluate_drift(
        nged=0.30,
        nmi=None,
        silhouette=0.40,
        day_since_cold_start=5,
    )
    assert d.fire is False
    assert any("missing inputs" in r for r in d.reasons)


def test_steady_state_q90_breach_fires():
    history = [0.05, 0.06, 0.07, 0.08, 0.09, 0.10, 0.11, 0.12, 0.20, 0.25]
    d = evaluate_drift(
        nged=0.30,
        nmi=None,
        silhouette=None,
        day_since_cold_start=60,
        last_30day_nged_history=history,
    )
    assert d.fire is True
    assert d.phase == "steady-state"


def test_steady_state_below_q90_does_not_fire():
    history = [0.5, 0.6, 0.7, 0.8, 0.9]
    d = evaluate_drift(
        nged=0.40,
        nmi=None,
        silhouette=None,
        day_since_cold_start=60,
        last_30day_nged_history=history,
    )
    assert d.fire is False


def test_steady_state_empty_history_falls_back_to_cold_tau():
    d = evaluate_drift(
        nged=0.30,
        nmi=None,
        silhouette=None,
        day_since_cold_start=60,
        last_30day_nged_history=[],
    )
    assert d.threshold == COLD_START_NGED_TAU


def test_quantile_basic():
    assert quantile([1, 2, 3, 4, 5], 0.5) == pytest.approx(3.0)
    assert quantile([1, 2, 3, 4, 5], 0.9) == pytest.approx(4.6)


def test_quantile_empty_raises():
    with pytest.raises(ValueError):
        quantile([], 0.5)
