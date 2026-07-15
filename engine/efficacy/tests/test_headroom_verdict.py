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


# ---- prereg §4 CONFIRM conditions (P1-P5) --------------------------------------------------------


def _pair(a, b, wins, ties, losses, p):
    """analyze-shaped pairwise block for arm a-vs-b."""
    return {
        f"{a}_gt_{b}": wins,
        "ties": ties,
        f"{b}_gt_{a}": losses,
        "non_ties": wins + losses,
        "p_two_sided": p,
    }


def _full_result(*, repair=9, plain_wins=9, plain_losses=0, decoy_equiv=True, parity=None):
    """A full 5-arm analysis dict with all §4 controls present (defaults: everything PASS)."""
    runs = 10
    return {
        "runs": runs,
        "repair_vs_bestN_headroom": _pair("repair", "bestN", repair, 0, runs - repair, 0.002),
        "repair_vs_decoy_headroom": _pair("repair", "decoy", 9, 1, 0, 0.004),
        "repair_vs_plain_headroom": _pair(
            "repair", "plain", plain_wins, runs - plain_wins - plain_losses, plain_losses, 0.004
        ),
        "decoy_vs_bestN_headroom": {"tost": {"equivalent": decoy_equiv}},
        "token_parity": {
            "repair_vs_bestN": parity
            or {"calls_ratio": 1.0, "tokens_ratio": 1.05, "usage_hidden": False}
        },
    }


def test_confirm_conditions_all_pass():
    v = HeadroomVerdict.from_analysis(_full_result())
    cc = v.confirm_conditions()
    assert cc["P1_edge"] == "PASS"
    assert cc["P2_oracle_signal"] == "PASS"
    assert cc["P3_bhgman_specific"] == "PASS"
    assert cc["P4_parity"] == "PASS"
    assert cc["P5_provenance"] == "ABSENT"  # filled by run tooling, not the in-memory verdict
    assert cc["confirm"] is True


def test_confirm_conditions_p2_fails_when_decoy_not_equivalent():
    """K4: if decoy is NOT equivalent to bestN, the oracle-signal isolation did not hold → P2 FAIL."""
    v = HeadroomVerdict.from_analysis(_full_result(decoy_equiv=False))
    cc = v.confirm_conditions()
    assert cc["P2_oracle_signal"] == "FAIL"
    assert cc["confirm"] is False


def test_confirm_conditions_p3_fails_when_repair_not_above_plain():
    """K8: if repair does not beat the plain agent-with-oracle baseline, the edge is a generic
    gen-verify-gap, not bhgman-specific → P3 FAIL."""
    v = HeadroomVerdict.from_analysis(_full_result(plain_wins=2, plain_losses=7))
    cc = v.confirm_conditions()
    assert cc["P3_bhgman_specific"] == "FAIL"
    assert cc["confirm"] is False


def test_confirm_conditions_p4_absent_when_usage_hidden():
    """usage_hidden (backend surfaced no tokens) → P4 ABSENT, never a fabricated PASS."""
    hidden = {"calls_ratio": None, "tokens_ratio": None, "usage_hidden": True}
    v = HeadroomVerdict.from_analysis(_full_result(parity=hidden))
    cc = v.confirm_conditions()
    assert cc["P4_parity"] == "ABSENT"
    assert cc["confirm"] is False  # confirm requires P4 PASS


def test_confirm_conditions_p4_fails_when_repair_overspends():
    """A repair arm that spends >bound× the bestN tokens fails the equal-compute parity gate."""
    overspend = {"calls_ratio": 1.0, "tokens_ratio": 2.0, "usage_hidden": False}
    v = HeadroomVerdict.from_analysis(_full_result(parity=overspend))
    assert v.confirm_conditions(parity_bound=1.25)["P4_parity"] == "FAIL"


def test_confirm_conditions_absent_on_legacy_batch():
    """The committed 3-arm batch has no §4 controls → P2/P3/P4 ABSENT, confirm False."""
    v = HeadroomVerdict.from_analysis(_result(repair=8, ties=2, losses=0, p=0.0078))
    cc = v.confirm_conditions()
    assert cc["P1_edge"] == "PASS"  # the legacy edge itself is significant
    assert cc["P2_oracle_signal"] == "ABSENT"
    assert cc["P3_bhgman_specific"] == "ABSENT"
    assert cc["P4_parity"] == "ABSENT"
    assert cc["confirm"] is False  # a bare edge is NOT a confirmation without the controls


def test_pairwise_tally_conservation_invariant():
    """A present pairwise control whose tally does not conserve against runs must raise."""
    bad = _full_result()
    bad["repair_vs_plain_headroom"] = _pair("repair", "plain", 9, 5, 0, 0.01)  # 9+5+0=14 != 10 runs
    with pytest.raises(InvariantViolation, match="repair_vs_plain tally conservation"):
        HeadroomVerdict.from_analysis(bad)
