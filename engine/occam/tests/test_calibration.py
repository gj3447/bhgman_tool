"""오캄 σ 보정 테스트 — PROM 6 C6 / A5.

# KG: prom6-occam-advancement-synthesis-2026-07-19, rf-occam-adv-A5-2026-07-19
"""

from __future__ import annotations

import json

from engine.occam.calibration import (
    calibrate,
    calibrated_prob,
    expected_calibration_error,
    fit_platt,
    label_to_bool,
    load_decision_log,
    reject_thresholds,
)


def test_label_maps_pass_fail_and_skips_conditional():
    assert label_to_bool("APPROVED") == 1
    assert label_to_bool("REJECT") == 0
    assert label_to_bool(True) == 1 and label_to_bool(0) == 0
    assert label_to_bool("CONDITIONAL") is None  # 불명은 skip


def test_load_decision_log_only_labeled(tmp_path):
    p = tmp_path / "d.jsonl"
    p.write_text(
        json.dumps({"sigma": 0.9, "verdict_label": "APPROVED"}) + "\n"
        + json.dumps({"sigma": 0.4, "verdict_label": None}) + "\n"  # 미라벨 → skip
        + json.dumps({"sigma": 0.2, "verdict_label": "REJECT"}) + "\n",
        encoding="utf-8",
    )
    pairs = load_decision_log(p)
    assert pairs == [(0.9, 1), (0.2, 0)]


def test_fit_platt_needs_enough_and_both_classes():
    assert fit_platt([(0.9, 1)] * 5) is None  # <10
    assert fit_platt([(0.9, 1)] * 20) is None  # 단일 클래스
    pairs = [(0.9, 1)] * 10 + [(0.1, 0)] * 10
    ab = fit_platt(pairs)
    assert ab is not None
    a, _ = ab
    assert a > 0  # σ↑ → P(correct)↑


def test_calibrated_prob_monotone():
    a, b = 5.0, -2.5
    assert calibrated_prob(0.9, a, b) > calibrated_prob(0.1, a, b)


def test_ece_zero_for_perfect_calibration():
    # σ=1.0 전부 correct, σ=0.0 전부 wrong → 완벽 보정 → ECE≈0
    pairs = [(1.0, 1)] * 20 + [(0.0, 0)] * 20
    assert expected_calibration_error(pairs) < 0.05


def test_reject_band_monotone_and_bounded():
    # τ_high = 1 − c_e/d: escalation 비싸지면 τ_high↓ = 밴드 좁아짐(더 auto-decide).
    # archive-only=가역이라 τ_high<1 (절대확신 요구 안 함).
    lo1, hi1 = reject_thresholds(cost_false_archive=10.0, cost_escalate=1.0)
    lo2, hi2 = reject_thresholds(cost_false_archive=10.0, cost_escalate=5.0)
    assert lo1 == 0.5 and hi1 < 1.0
    assert hi2 < hi1  # c_e↑ → τ_high↓ → escalation 밴드 좁아짐
    assert hi1 == 0.9 and hi2 == 0.5  # 1 − 1/10, 1 − 5/10


def test_calibrate_reports_ready_when_no_labels():
    r = calibrate([])
    assert r.fitted is False and r.n == 0
    assert "machinery ready" in r.note


def test_calibrate_fits_on_separable():
    r = calibrate([(0.95, 1)] * 15 + [(0.05, 0)] * 15)
    assert r.fitted is True and r.a is not None
