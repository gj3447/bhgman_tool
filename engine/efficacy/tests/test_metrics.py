"""효능 metric 테스트 — AUC 정확값 (오캄 0.409 케이스 포함)."""

from __future__ import annotations

import pytest

from engine.efficacy.metrics import auc_mann_whitney, precision_recall_f1


def test_perfect_separation_auc_one():
    assert auc_mann_whitney([0.9, 0.8], [0.1, 0.2]) == 1.0


def test_inverted_separation_auc_zero():
    assert auc_mann_whitney([0.1, 0.2], [0.9, 0.8]) == 0.0


def test_all_tied_auc_half():
    assert auc_mann_whitney([0.5, 0.5], [0.5, 0.5]) == 0.5


def test_empty_either_side_is_half():
    assert auc_mann_whitney([], [0.1]) == 0.5
    assert auc_mann_whitney([0.1], []) == 0.5


def test_occam_real_case_binary_signal_auc_0409():
    # 실 KG: superseded(pos) twin있음 33 / 없음 48; active(neg) twin있음 66 / 없음 46.
    # cypher Mann-Whitney = 0.409. 이진 신호(1=twin, 0=no)로 재현.
    pos = [1.0] * 33 + [0.0] * 48
    neg = [1.0] * 66 + [0.0] * 46
    auc = auc_mann_whitney(pos, neg)
    assert auc == pytest.approx(3711 / 9072, abs=1e-9)
    assert auc == pytest.approx(0.409, abs=0.001)
    assert auc < 0.5  # chance 미만 (신호 역전 실증)


def test_precision_recall_f1():
    p, r, f = precision_recall_f1(true_pos=8, false_pos=2, false_neg=2)
    assert p == pytest.approx(0.8)
    assert r == pytest.approx(0.8)
    assert f == pytest.approx(0.8)


def test_precision_recall_zero_denominators():
    assert precision_recall_f1(0, 0, 0) == (0.0, 0.0, 0.0)
