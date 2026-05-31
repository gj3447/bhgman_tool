"""Tests for L2 URDNA2015-equivalent Jaccard drift channel.

# KG: CONTRACT_UrdnaChannel_v1_2026-05-19, sa-longinus-v3.4-multi-channel-urdna2015-2026-05-19
"""

from __future__ import annotations

import pytest

from engine.longinus_drift_audit.urdna2015_channel import (
    _canonicalize,
    compute_urdna_drift,
)


T_AB = ("a", "knows", "b")
T_BC = ("b", "knows", "c")
T_CD = ("c", "knows", "d")
T_DE = ("d", "knows", "e")


def test_identity_distance_is_zero():
    triples = [T_AB, T_BC, T_CD]
    report = compute_urdna_drift(triples_a=triples, triples_b=triples)
    assert report.jaccard_distance == 0.0
    assert report.severity == "PERFECT"
    assert report.shared == 3
    assert not report.warn
    assert not report.halt


def test_disjoint_distance_is_one():
    a = [T_AB, T_BC]
    b = [T_CD, T_DE]
    report = compute_urdna_drift(triples_a=a, triples_b=b)
    assert report.jaccard_distance == 1.0
    assert report.severity == "CRITICAL"
    assert report.shared == 0
    assert report.warn
    assert report.halt


def test_one_third_diff_jaccard():
    """Known case: A={1,2,3}, B={2,3,4}. |A∩B|=2, |A∪B|=4, distance = 1 - 2/4 = 0.5."""
    a = [T_AB, T_BC, T_CD]
    b = [T_BC, T_CD, T_DE]
    report = compute_urdna_drift(triples_a=a, triples_b=b)
    assert report.jaccard_distance == 0.5
    assert report.shared == 2
    assert report.only_in_a == 1
    assert report.only_in_b == 1
    assert report.severity == "CRITICAL"


def test_symmetry():
    """f(A, B) == f(B, A)."""
    a = [T_AB, T_BC]
    b = [T_BC, T_CD, T_DE]
    r_ab = compute_urdna_drift(triples_a=a, triples_b=b)
    r_ba = compute_urdna_drift(triples_a=b, triples_b=a)
    assert r_ab.jaccard_distance == r_ba.jaccard_distance
    assert r_ab.shared == r_ba.shared


def test_both_empty_is_perfect():
    report = compute_urdna_drift(triples_a=[], triples_b=[])
    assert report.jaccard_distance == 0.0
    assert report.severity == "PERFECT"
    assert report.shared == 0
    assert not report.warn


def test_one_empty_other_nonempty_is_critical():
    report = compute_urdna_drift(triples_a=[], triples_b=[T_AB, T_BC])
    assert report.jaccard_distance == 1.0
    assert report.severity == "CRITICAL"
    assert report.halt


def test_warn_threshold_boundary():
    """20-triple set; 1 different → Jaccard 1/21 ≈ 0.0476 < 0.05 warn threshold."""
    base = [(f"n{i}", "knows", f"n{i + 1}") for i in range(20)]
    diff_one = base[:-1] + [("n99", "knows", "n100")]
    report = compute_urdna_drift(triples_a=base, triples_b=diff_one)
    # |A∩B| = 19, |A∪B| = 21, distance = 2/21 ≈ 0.0952
    assert abs(report.jaccard_distance - 2 / 21) < 1e-9
    assert report.warn  # 0.0952 >= 0.05
    assert not report.halt  # 0.0952 < 0.15
    assert report.severity == "ACCEPTABLE"


def test_halt_threshold_boundary():
    """Drift just above halt threshold."""
    base = [(f"n{i}", "knows", f"n{i + 1}") for i in range(10)]
    # Replace 2 triples → |A∩B|=8, |A∪B|=12, distance = 4/12 ≈ 0.333 (>= 0.15)
    diff_two = base[:8] + [("nX", "p", "nY"), ("nZ", "p", "nW")]
    report = compute_urdna_drift(triples_a=base, triples_b=diff_two)
    assert report.jaccard_distance > 0.15
    assert report.warn
    assert report.halt
    assert report.severity in {"DEGRADED", "CRITICAL"}


def test_threshold_validation_warn_out_of_range():
    with pytest.raises(ValueError, match="warn_threshold"):
        compute_urdna_drift(triples_a=[], triples_b=[], warn_threshold=1.5)


def test_threshold_validation_halt_below_warn():
    with pytest.raises(ValueError, match="halt_threshold"):
        compute_urdna_drift(triples_a=[], triples_b=[], warn_threshold=0.2, halt_threshold=0.1)


def test_canonicalize_permutation_invariant():
    """Triple order must not affect the canonical hash set."""
    a = [T_AB, T_BC, T_CD]
    b = [T_CD, T_AB, T_BC]
    assert _canonicalize(a) == _canonicalize(b)


def test_canonicalize_deduplicates():
    """Duplicate triples in input collapse in the canonical set."""
    a = [T_AB, T_AB, T_BC]
    assert len(_canonicalize(a)) == 2


def test_report_serialization():
    """UrdnaDriftReport must be Pydantic-serializable."""
    report = compute_urdna_drift(triples_a=[T_AB], triples_b=[T_BC])
    d = report.model_dump()
    assert d["jaccard_distance"] == 1.0
    # Post-Naesengmoon MEDIUM#3 fix: renamed from "simplified-sorted-sha256" to
    # "blank-node-free-jaccard-sha256" (honest citation — NOT URDNA2015 proper).
    assert d["canonicalization"] == "blank-node-free-jaccard-sha256"
    # Post-Naesengmoon HIGH#2 fix: halt=True forces preliminary_longinus_novel=True.
    assert d["preliminary_longinus_novel"] == d["halt"]


def test_preliminary_tag_set_on_halt():
    """Naesengmoon HIGH#2 fix: halt verdicts must self-tag :PreliminaryLonginusNovel."""
    # disjoint triple sets → distance=1, halt=True
    report = compute_urdna_drift(triples_a=[T_AB], triples_b=[T_CD])
    assert report.halt is True
    assert report.preliminary_longinus_novel is True


def test_preliminary_tag_clear_on_no_halt():
    """Naesengmoon HIGH#2 fix: identity case does NOT carry preliminary tag."""
    report = compute_urdna_drift(triples_a=[T_AB], triples_b=[T_AB])
    assert report.halt is False
    assert report.preliminary_longinus_novel is False
