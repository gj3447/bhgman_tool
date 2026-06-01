"""3-falsifier 게이트 테스트 — 순환성/신호부재/신호역전."""

from __future__ import annotations


from engine.efficacy.falsifier import (
    circularity_ratio,
    directional_auc,
    run_preflight,
    signal_availability,
)
from engine.efficacy.models import Direction, FalsifierKind, LabeledItem


def _item(pos, sig, prov=""):
    return LabeledItem(item_id="x", is_positive=pos, signal=sig, provenance=prov)


# ── circularity ───────────────────────────────────────────────────────────────


def test_circularity_all_self_generated():
    items = [_item(True, 1.0, "superseded: duplicate by occam"), _item(True, 1.0, "occam dup")]
    assert circularity_ratio(items, ("occam", "dup")) == 1.0


def test_circularity_none_when_no_keyword_match():
    items = [_item(True, 1.0, "manual user verdict")]
    assert circularity_ratio(items, ("occam", "dup")) == 0.0


def test_circularity_only_counts_positives():
    items = [_item(False, 1.0, "occam dup"), _item(True, 1.0, "clean")]
    assert circularity_ratio(items, ("occam",)) == 0.0


def test_circularity_empty_keywords_is_zero():
    assert circularity_ratio([_item(True, 1.0, "occam")], ()) == 0.0


# ── signal availability ───────────────────────────────────────────────────────


def test_signal_availability_fraction():
    items = [_item(True, 1.0), _item(True, None), _item(False, 0.0), _item(False, None)]
    assert signal_availability(items) == 0.5


def test_signal_availability_empty_zero():
    assert signal_availability([]) == 0.0


# ── directional AUC ───────────────────────────────────────────────────────────


def test_directional_auc_higher():
    items = [_item(True, 0.9), _item(False, 0.1)]
    assert directional_auc(items, Direction.HIGHER) == 1.0


def test_directional_auc_lower_flips():
    # LOWER 기대: positive가 작은 신호 → raw AUC 0.0 이지만 방향보정 후 1.0
    items = [_item(True, 0.1), _item(False, 0.9)]
    assert directional_auc(items, Direction.LOWER) == 1.0


def test_directional_auc_none_when_no_signal_on_a_side():
    items = [_item(True, None), _item(False, 0.5)]
    assert directional_auc(items, Direction.HIGHER) is None


# ── run_preflight (게이트 통합) ───────────────────────────────────────────────


def test_preflight_pass_clean():
    items = [_item(True, 0.9, "manual"), _item(False, 0.1, "manual")] * 5
    pre = run_preflight(items, ("occam",), Direction.HIGHER)
    assert pre.passed
    assert pre.failures == ()


def test_preflight_fails_circularity():
    items = [_item(True, 0.9, "occam dup")] * 5 + [_item(False, 0.1, "x")] * 5
    pre = run_preflight(items, ("occam", "dup"), Direction.HIGHER)
    assert FalsifierKind.CIRCULARITY in pre.failures
    assert not pre.passed


def test_preflight_fails_signal_absent():
    items = [_item(True, None, "m")] * 5 + [_item(False, None, "m")] * 5
    pre = run_preflight(items, ("z",), Direction.HIGHER)
    assert FalsifierKind.SIGNAL_ABSENT in pre.failures


def test_preflight_fails_inverted_like_occam():
    # 오캄 실 케이스: 신호 충분히 있으나 방향 역전 (pos가 신호 낮음)
    items = [_item(True, 0.0, "m")] * 8 + [_item(False, 1.0, "m")] * 8
    pre = run_preflight(items, ("z",), Direction.HIGHER)
    assert FalsifierKind.SIGNAL_INVERTED in pre.failures
    assert pre.raw_auc is not None and pre.raw_auc <= 0.5


def test_preflight_no_double_report_when_signal_absent():
    # 신호 부재면 SIGNAL_INVERTED는 중복 보고 안 함 (auc 의미 없음)
    items = [_item(True, None, "m")] * 5 + [_item(False, None, "m")] * 5
    pre = run_preflight(items, ("z",), Direction.HIGHER)
    assert FalsifierKind.SIGNAL_INVERTED not in pre.failures
