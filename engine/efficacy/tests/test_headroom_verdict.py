"""RED-first tests for the HeadroomVerdict invariant-checker (positive-TDD-OO-logged loop).

Each assertion mirrors a positive-invariant contract logged to the KG BEFORE this file was
written (TDD:headroom_verdict:{runs_positive, tally_conservation, non_ties_consistent,
p_two_sided_bounded}). The verdict GATES the 32b lean-headroom write-up: a batch that violates
an invariant must raise, not silently produce a number (verify-before-writeup as positive TDD).

# KG: TDD:headroom_verdict:runs_positive, TDD:headroom_verdict:tally_conservation,
#     TDD:headroom_verdict:non_ties_consistent, TDD:headroom_verdict:p_two_sided_bounded
"""

from __future__ import annotations

import pytest

from engine.efficacy.headroom_verdict import HeadroomVerdict, InvariantViolation


def _result(repair=7, ties=1, losses=2, p=0.18):
    runs = repair + ties + losses
    return {
        "runs": runs,
        "repair_vs_bestN_headroom": {
            "repair_gt_bestN": repair,
            "ties": ties,
            "bestN_gt_repair": losses,
            "non_ties": repair + losses,
            "p_two_sided": p,
        },
    }


def test_valid_result_constructs_and_exposes_verdict():
    v = HeadroomVerdict.from_analysis(_result(repair=8, ties=0, losses=2, p=0.109))
    assert v.runs == 10
    assert v.wins == 8 and v.losses == 2 and v.ties == 0
    assert v.direction == "repair_favored"  # wins > losses
    assert v.p_two_sided == pytest.approx(0.109)
    assert v.significant(alpha=0.05) is False  # p > 0.05
    assert v.significant(alpha=0.20) is True


def test_runs_positive_invariant():
    bad = _result(repair=0, ties=0, losses=0)  # runs == 0
    with pytest.raises(InvariantViolation, match="runs"):
        HeadroomVerdict.from_analysis(bad)


def test_tally_conservation_invariant():
    bad = _result(repair=7, ties=1, losses=2)
    bad["runs"] = 11  # 7+1+2=10 != 11
    with pytest.raises(InvariantViolation, match="conservation|runs"):
        HeadroomVerdict.from_analysis(bad)


def test_non_ties_consistency_invariant():
    bad = _result(repair=7, ties=1, losses=2)
    bad["repair_vs_bestN_headroom"]["non_ties"] = 5  # should be 7+2=9
    with pytest.raises(InvariantViolation, match="non_ties"):
        HeadroomVerdict.from_analysis(bad)


@pytest.mark.parametrize("p", [-0.01, 1.5])
def test_p_two_sided_bounded_invariant(p):
    bad = _result(p=p)
    with pytest.raises(InvariantViolation, match="p_two_sided|probability"):
        HeadroomVerdict.from_analysis(bad)


def test_direction_tie_when_wins_equal_losses():
    v = HeadroomVerdict.from_analysis(_result(repair=4, ties=2, losses=4, p=1.0))
    assert v.direction == "inconclusive"
    assert v.significant(0.05) is False
