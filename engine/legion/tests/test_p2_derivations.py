"""Tests for P2 derivation modules — Bayesian MAP / CUSUM / Brier / config.

PROM 16 P2(a-d) ActionPlan.
"""

from __future__ import annotations

import pytest

from engine.legion.threshold_derivation.bayesian_map import (
    BayesianMAPResult,
    derive_bayesian_map,
)
from engine.legion.threshold_derivation.brier import BrierResult, brier_score
from engine.legion.threshold_derivation.config import load_thresholds
from engine.legion.threshold_derivation.cusum import (
    CusumChart,
    DriftSignal,
    DualWindowCUSUM,
)


class TestBayesianMAP:
    def test_rejects_below_30_samples(self) -> None:
        with pytest.raises(ValueError, match="Cohen 1988"):
            derive_bayesian_map(successes=10, total=20)

    def test_uniform_prior_yields_empirical_mean_minus_correction(self) -> None:
        result = derive_bayesian_map(successes=21, total=30)
        assert isinstance(result, BayesianMAPResult)
        assert 0.6 < result.threshold < 0.75
        assert result.posterior_alpha == 22.0
        assert result.posterior_beta == 10.0

    def test_strong_prior_pulls_toward_prior_mean(self) -> None:
        weak = derive_bayesian_map(successes=21, total=30, prior_alpha=1, prior_beta=1)
        strong = derive_bayesian_map(successes=21, total=30, prior_alpha=50, prior_beta=50)
        assert abs(strong.threshold - 0.5) < abs(weak.threshold - 0.5)

    def test_rejects_invalid_inputs(self) -> None:
        with pytest.raises(ValueError, match="Invalid counts"):
            derive_bayesian_map(successes=40, total=30)
        with pytest.raises(ValueError, match="Prior hyperparameters"):
            derive_bayesian_map(successes=20, total=30, prior_alpha=0)

    def test_kg_props(self) -> None:
        result = derive_bayesian_map(successes=20, total=30)
        props = result.to_kg_props()
        assert props["method"] == "bayesian_map_beta_bernoulli_berger_1985"
        assert "Berger" in props["citation"]


class TestCUSUM:
    def test_no_drift_when_target_centered(self) -> None:
        chart = CusumChart(target=0.7, delta=0.05, h=3.97)
        for _ in range(50):
            assert chart.observe(0.7) == DriftSignal.NO_DRIFT

    def test_detects_persistent_drift(self) -> None:
        chart = CusumChart(target=0.7, delta=0.05, h=3.0)
        result = DriftSignal.NO_DRIFT
        for _ in range(200):
            result = chart.observe(0.95)
            if result == DriftSignal.DETECTED:
                break
        assert result == DriftSignal.DETECTED

    def test_dual_window_long_and_short(self) -> None:
        dual = DualWindowCUSUM.standard_config(target=0.7)
        for _ in range(10):
            dual.observe(0.7)
        assert dual.status() == DriftSignal.NO_DRIFT

    def test_dual_window_short_alarms_first_on_jump(self) -> None:
        dual = DualWindowCUSUM.standard_config(target=0.5)
        for _ in range(100):
            dual.observe(0.95)
        history_charts = [c for _, c, _ in dual.alarm_history]
        assert "short" in history_charts


class TestBrier:
    def test_perfect_predictions_score_zero(self) -> None:
        preds = [(1.0, 1) for _ in range(50)] + [(0.0, 0) for _ in range(50)]
        result = brier_score(preds)
        assert isinstance(result, BrierResult)
        assert result.brier_score == pytest.approx(0.0)

    def test_random_uninformative_score_quarter(self) -> None:
        preds = [(0.5, i % 2) for i in range(100)]
        result = brier_score(preds)
        assert 0.2 < result.brier_score < 0.3

    def test_rejects_empty(self) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            brier_score([])

    def test_rejects_invalid_probability(self) -> None:
        with pytest.raises(ValueError, match="out of"):
            brier_score([(1.5, 1)])

    def test_kg_props(self) -> None:
        preds = [(0.8, 1), (0.2, 0), (0.6, 1), (0.4, 0)]
        result = brier_score(preds)
        props = result.to_kg_props()
        assert "Brier" in props["citation"]


class TestConfigLoader:
    def test_load_returns_dict(self) -> None:
        cfg = load_thresholds()
        assert isinstance(cfg, dict)

    def test_load_naesengmoon_threshold(self) -> None:
        cfg = load_thresholds()
        if cfg:
            assert ("naesengmoon", "rti_fvr") in cfg
            entry = cfg[("naesengmoon", "rti_fvr")]
            assert entry.value == 0.7
            assert entry.comparator == "less"
            assert entry.derivation_method == "roc_youden_j_1950"

    def test_contract_coupling_zero_entry(self) -> None:
        cfg = load_thresholds()
        if cfg:
            assert ("contract", "coupling_degree") in cfg
            entry = cfg[("contract", "coupling_degree")]
            assert entry.value == 0.0
            assert entry.derivation_method == "monoid_identity_uniqueness"
